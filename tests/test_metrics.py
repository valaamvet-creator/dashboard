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
    def test_shape(self):
        s = flat(D(2025, 1, 1), D(2026, 9, 11), 100)
        gen = dt.datetime(2026, 9, 11, 22, 50, 39, tzinfo=dt.timezone(dt.timedelta(hours=3)))
        p = build_payload(s, D(2026, 9, 11), gen, ["night_fetch_failed"])
        self.assertEqual(p["generated_at"], "2026-09-11T22:50:39+03:00")
        self.assertEqual(set(p["objects"]), {"p1"})
        o = p["objects"]["p1"]
        self.assertEqual(set(o), {"today", "week7", "mtd", "prev_month", "ytd", "months", "warnings"})
        self.assertEqual(o["warnings"], ["night_fetch_failed"])
        self.assertIsInstance(o["today"]["value"], int)


if __name__ == "__main__":
    unittest.main()
