from __future__ import annotations
import datetime as dt
import unittest

from server.series import DayValue
from server.metrics import (
    build_payload, months_block, mtd_block, pct, prev_month_block,
    same_date_prev_year, sum_range, today_block, week7_block, ytd_block,
)

D = dt.date


def flat(start: D, end: D, value: float) -> dict:
    """Ряд с одинаковой выручкой каждый день (только дневная касса)."""
    out, d = {}, start
    while d <= end:
        out[d] = DayValue(value, 0.0, True)
        d += dt.timedelta(days=1)
    return out


class Pct(unittest.TestCase):
    def test_growth_and_fall(self):
        self.assertEqual(pct(115, 100), 15)
        self.assertEqual(pct(85, 100), -15)

    def test_prev_zero_or_negative_is_none(self):
        self.assertIsNone(pct(100, 0))
        self.assertIsNone(pct(100, -5))

    def test_rounds_half_away_from_zero_like_humans_expect(self):
        self.assertEqual(pct(1125, 1000), 13)   # 12.5 → 13
        self.assertEqual(pct(875, 1000), -13)   # -12.5 → -13


class Ranges(unittest.TestCase):
    def test_sum_range_inclusive(self):
        s = flat(D(2026, 9, 1), D(2026, 9, 10), 10)
        self.assertEqual(sum_range(s, D(2026, 9, 1), D(2026, 9, 3)), 30)

    def test_same_date_prev_year_leap(self):
        self.assertEqual(same_date_prev_year(D(2028, 2, 29)), D(2027, 2, 28))
        self.assertEqual(same_date_prev_year(D(2026, 9, 11)), D(2025, 9, 11))


class Today(unittest.TestCase):
    def test_compares_with_364_days_back(self):
        s = flat(D(2025, 9, 1), D(2026, 9, 11), 100)
        s[D(2026, 9, 11)] = DayValue(90, 0, False)
        s[D(2025, 9, 12)] = DayValue(100, 0, True)   # четверг 12.09.2025 = 11.09.2026 − 364
        b = today_block(s, D(2026, 9, 11))
        self.assertEqual(b["date"], "2026-09-11")
        self.assertEqual(b["prev_date"], "2025-09-12")
        self.assertEqual((b["value"], b["prev"], b["pct"], b["complete"]), (90, 100, -10, False))

    def test_no_data_today_is_zero_and_complete_false(self):
        s = flat(D(2025, 9, 1), D(2026, 9, 10), 100)
        b = today_block(s, D(2026, 9, 11))
        self.assertEqual(b["value"], 0)
        self.assertFalse(b["complete"])


class Week7(unittest.TestCase):
    def test_seven_full_days_before_today(self):
        s = flat(D(2025, 8, 1), D(2026, 9, 11), 100)
        for i in range(1, 8):
            s[D(2026, 9, 11) - dt.timedelta(days=i)] = DayValue(200, 0, True)
        b = week7_block(s, D(2026, 9, 11))
        self.assertEqual((b["from"], b["to"]), ("2026-09-04", "2026-09-10"))
        self.assertEqual(b["value"], 1400)
        self.assertEqual(b["prev"], 700)          # 2025-09-05 … 2025-09-11 по 100
        self.assertEqual(b["pct"], 100)
        self.assertEqual((b["avg_day"], b["prev_avg_day"]), (200, 100))


class MonthYear(unittest.TestCase):
    def setUp(self):
        self.s = flat(D(2025, 1, 1), D(2026, 9, 11), 100)
        for d in list(self.s):
            if d.year == 2025:
                self.s[d] = DayValue(80, 0, True)

    def test_mtd_calendar_dates(self):
        b = mtd_block(self.s, D(2026, 9, 11))
        self.assertEqual((b["from"], b["to"]), ("2026-09-01", "2026-09-11"))
        self.assertEqual((b["value"], b["prev"], b["pct"]), (1100, 880, 25))

    def test_prev_month_full(self):
        b = prev_month_block(self.s, D(2026, 9, 11))
        self.assertEqual(b["month"], "2026-08")
        self.assertEqual((b["value"], b["prev"], b["pct"]), (3100, 2480, 25))

    def test_prev_month_in_january_is_december_last_year(self):
        b = prev_month_block(self.s, D(2026, 1, 15))
        self.assertEqual(b["month"], "2025-12")
        self.assertEqual(b["value"], 31 * 80)
        self.assertIsNone(b["pct"])              # 2024 данных нет

    def test_ytd(self):
        b = ytd_block(self.s, D(2026, 9, 11))
        self.assertEqual((b["from"], b["to"]), ("2026-01-01", "2026-09-11"))
        self.assertEqual(b["value"], 254 * 100)
        self.assertEqual(b["prev"], 254 * 80)
        self.assertEqual(b["pct"], 25)

    def test_months_block_future_is_none(self):
        ms = months_block(self.s, D(2026, 9, 11))
        self.assertEqual(len(ms), 12)
        self.assertEqual(ms[0], {"m": 1, "cur": 3100, "prev": 2480, "pct": 25})
        self.assertEqual(ms[8]["cur"], 1100)     # сентябрь — в моменте
        # Текущий месяц: prev/pct — по сопоставимым датам (как MTD), а не за весь прошлый сентябрь.
        self.assertEqual(ms[8], {"m": 9, "cur": 1100, "prev": 880, "pct": 25})
        self.assertIsNone(ms[9]["cur"])          # октябрь ещё не наступил
        self.assertEqual(ms[9]["prev"], 31 * 80)
        self.assertIsNone(ms[9]["pct"])


class Payload(unittest.TestCase):
    def test_shape_multi_object(self):
        s = flat(D(2025, 1, 1), D(2026, 9, 11), 100)
        w = flat(D(2025, 1, 1), D(2026, 9, 11), 10)
        gen = dt.datetime(2026, 9, 11, 22, 50, 39, tzinfo=dt.timezone(dt.timedelta(hours=3)))
        p = build_payload({"p1": s, "w1": w}, D(2026, 9, 11), gen, {"p1": ["night_fetch_failed"], "w1": []})
        self.assertEqual(p["generated_at"], "2026-09-11T22:50:39+03:00")
        self.assertEqual(list(p["objects"]), ["p1", "w1"])
        for code in ("p1", "w1"):
            self.assertEqual(set(p["objects"][code]), {"today", "week7", "mtd", "prev_month", "ytd", "months", "warnings", "forecast"})
        self.assertEqual(p["objects"]["w1"]["forecast"]["year"]["fact"], 254 * 10)
        self.assertEqual(p["objects"]["p1"]["warnings"], ["night_fetch_failed"])
        self.assertEqual(p["objects"]["w1"]["warnings"], [])
        self.assertEqual(p["objects"]["p1"]["today"]["value"], 100)
        self.assertEqual(p["objects"]["w1"]["today"]["value"], 10)
        self.assertIsInstance(p["objects"]["p1"]["today"]["value"], int)


if __name__ == "__main__":
    unittest.main()


class Forecast(unittest.TestCase):
    """2025 = 80/день, 2026 = 100/день до 11.09 → оба темпа 1.25, диапазон схлопывается."""
    def setUp(self):
        from server.metrics import forecast_block
        self.fb = forecast_block
        self.s = flat(D(2025, 1, 1), D(2026, 9, 11), 100)
        for d in list(self.s):
            if d.year == 2025:
                self.s[d] = DayValue(80, 0, True)

    def test_tempos_and_blend(self):
        f = self.fb(self.s, D(2026, 9, 11))
        self.assertAlmostEqual(f["k_ytd"], 1.25, places=3)
        self.assertAlmostEqual(f["k_recent"], 1.25, places=3)
        self.assertAlmostEqual(f["k"], 1.25, places=3)

    def test_current_month_is_fact_plus_rest(self):
        f = self.fb(self.s, D(2026, 9, 11))
        sep = next(m for m in f["months"] if m["m"] == 9)
        self.assertEqual(sep["fact"], 1100)                      # 11 × 100
        self.assertEqual(sep["point"], 1100 + round(19 * 80 * 1.25))   # остаток 12–30 сен: 19 дней × 80 × 1.25
        self.assertEqual(sep["low"], sep["point"]); self.assertEqual(sep["high"], sep["point"])

    def test_future_months_and_year(self):
        f = self.fb(self.s, D(2026, 9, 11))
        self.assertEqual([m["m"] for m in f["months"]], [9, 10, 11, 12])
        octo = next(m for m in f["months"] if m["m"] == 10)
        self.assertIsNone(octo["fact"])
        self.assertEqual(octo["point"], round(31 * 80 * 1.25))
        year_fact = 254 * 100
        rest = round(19 * 80 * 1.25) + round(31 * 80 * 1.25) + round(30 * 80 * 1.25) + round(31 * 80 * 1.25)
        self.assertEqual(f["year"]["fact"], year_fact)
        self.assertEqual(f["year"]["point"], year_fact + rest)
        self.assertEqual(f["year"]["prev_year"], 365 * 80)

    def test_range_between_two_tempos(self):
        s = dict(self.s)
        for i in range(1, 57):                                    # последние 8 недель 2026 — 150/день
            s[D(2026, 9, 11) - dt.timedelta(days=i)] = DayValue(150, 0, True)
        f = self.fb(s, D(2026, 9, 11))
        self.assertGreater(f["k_recent"], f["k_ytd"])
        self.assertAlmostEqual(f["k_recent"], 150 / 80, places=3)
        octo = next(m for m in f["months"] if m["m"] == 10)
        self.assertEqual(octo["low"], round(31 * 80 * f["k_ytd"]))
        self.assertEqual(octo["high"], round(31 * 80 * f["k_recent"]))
        self.assertEqual(octo["point"], round(31 * 80 * f["k"]))

    def test_no_previous_year_gives_none(self):
        s = flat(D(2026, 1, 1), D(2026, 9, 11), 100)
        self.assertIsNone(self.fb(s, D(2026, 9, 11)))


class SumForecasts(unittest.TestCase):
    def test_sums_points_and_ranges_by_month(self):
        from server.metrics import sum_forecasts
        a = {"k": 1.1, "months": [{"m": 9, "fact": 10, "point": 20, "low": 15, "high": 25}, {"m": 10, "fact": None, "point": 30, "low": 20, "high": 40}],
             "year": {"fact": 100, "point": 150, "low": 130, "high": 170, "prev_year": 120}}
        b = {"k": 0.9, "months": [{"m": 9, "fact": 5, "point": 8, "low": 7, "high": 9}, {"m": 10, "fact": None, "point": 12, "low": 10, "high": 14}],
             "year": {"fact": 50, "point": 70, "low": 65, "high": 75, "prev_year": 80}}
        t = sum_forecasts([a, b, None])
        self.assertEqual(t["months"][0], {"m": 9, "fact": 15, "point": 28, "low": 22, "high": 34})
        self.assertEqual(t["months"][1], {"m": 10, "fact": None, "point": 42, "low": 30, "high": 54})
        self.assertEqual(t["year"], {"fact": 150, "point": 220, "low": 195, "high": 245, "prev_year": 200})
        self.assertIsNone(t["k"])                                 # у суммы нет единого темпа

    def test_all_none(self):
        from server.metrics import sum_forecasts
        self.assertIsNone(sum_forecasts([None, None]))
