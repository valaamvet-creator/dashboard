from __future__ import annotations
import datetime as dt
import unittest
from pathlib import Path

from server.series import DayValue, merge_series, read_day_z, read_night_sell, read_sync_dump

FX = Path(__file__).parent / "fixtures"


class ReadDayZ(unittest.TestCase):
    def test_sums_income_minus_refund_by_close_date(self):
        s = read_day_z(FX / "day_z.csv")
        self.assertEqual(s[dt.date(2026, 9, 10)], 149000.0)   # 100000 + (50000-1000)
        self.assertEqual(s[dt.date(2025, 9, 11)], 70000.0)
        self.assertEqual(s[dt.date(2026, 9, 11)], 30000.0)

    def test_missing_file_gives_empty(self):
        self.assertEqual(read_day_z(FX / "nope.csv"), {})


class ReadNightSell(unittest.TestCase):
    def test_dedups_receipt_positions_and_subtracts_refunds(self):
        s = read_night_sell(FX / "night_sell.csv")
        self.assertEqual(s[dt.date(2026, 9, 10)], 1100.0)      # 1600 (один раз) - 500
        self.assertEqual(s[dt.date(2025, 9, 11)], 900.0)


class ReadSyncDump(unittest.TestCase):
    def test_reads_days_and_updated_at(self):
        days, updated = read_sync_dump(FX / "sync_dump.json")
        self.assertEqual(days[dt.date(2026, 9, 11)], DayValue(241050, 2300, False))
        self.assertEqual(updated, dt.datetime.fromisoformat("2026-09-11T22:50:39+03:00"))

    def test_missing_dump(self):
        days, updated = read_sync_dump(FX / "nope.json")
        self.assertEqual(days, {})
        self.assertIsNone(updated)


class Merge(unittest.TestCase):
    def test_dump_overrides_csv_for_same_date(self):
        day = read_day_z(FX / "day_z.csv")
        night = read_night_sell(FX / "night_sell.csv")
        dump, _ = read_sync_dump(FX / "sync_dump.json")
        s = merge_series(day, night, dump)
        self.assertEqual(s[dt.date(2025, 9, 11)], DayValue(70000.0, 900.0, True))   # только CSV
        self.assertEqual(s[dt.date(2026, 9, 11)], DayValue(241050, 2300, False))    # дамп важнее
        self.assertAlmostEqual(s[dt.date(2026, 9, 11)].total, 243350)


if __name__ == "__main__":
    unittest.main()


class Waterfalls(unittest.TestCase):
    def test_read_waterfalls_csv_sums_two_registers(self):
        from server.series import DayTotal, read_waterfalls_csv
        s = read_waterfalls_csv(FX / "wf_daily_2025.csv")
        self.assertEqual(s[dt.date(2025, 9, 11)], DayTotal(8000.0, True))
        self.assertEqual(s[dt.date(2025, 9, 12)], DayTotal(7000.0, True))
        self.assertEqual(read_waterfalls_csv(FX / "nope.csv"), {})

    def test_read_waterfalls_dump_uses_wf_fields(self):
        from server.series import DayTotal, read_waterfalls_dump
        s = read_waterfalls_dump(FX / "sync_dump.json")
        self.assertEqual(s[dt.date(2026, 9, 10)], DayTotal(336050.0, True))
        self.assertEqual(s[dt.date(2026, 9, 11)], DayTotal(348750.0, False))

    def test_read_waterfalls_dump_skips_days_without_wf(self):
        from server.series import read_waterfalls_dump
        import json, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "d.json"
            p.write_text(json.dumps({"updated_at": "2026-09-11T22:50:39+03:00",
                                     "days": {"2026-09-10": {"day": 1, "night": 2, "complete": True}}}), encoding="utf-8")
            self.assertEqual(read_waterfalls_dump(p), {})

    def test_sum_series_adds_totals_and_ands_complete(self):
        from server.series import DayTotal, sum_series
        a = {dt.date(2026, 9, 10): DayValue(100.0, 10.0, True), dt.date(2026, 9, 11): DayValue(50.0, 0.0, False)}
        b = {dt.date(2026, 9, 10): DayTotal(1000.0, True), dt.date(2026, 9, 12): DayTotal(7.0, True)}
        s = sum_series(a, b)
        self.assertEqual(s[dt.date(2026, 9, 10)], DayTotal(1110.0, True))
        self.assertEqual(s[dt.date(2026, 9, 11)], DayTotal(50.0, False))   # только a, complete=False
        self.assertEqual(s[dt.date(2026, 9, 12)], DayTotal(7.0, True))     # только b
