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
