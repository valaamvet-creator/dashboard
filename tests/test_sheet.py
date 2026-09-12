from __future__ import annotations
import datetime as dt
import unittest

from server.fetch_sheet_daily import parse_daily_block


class ParseDailyBlock(unittest.TestCase):
    def test_parses_dates_and_money_with_nbsp(self):
        values = [["Выручка по дням"], ["2026-09-12", "819\xa0329"], ["2026-09-11", "461\xa0730"], [], ["мусор", "x"]]
        self.assertEqual(parse_daily_block(values), {dt.date(2026, 9, 12): 819329.0, dt.date(2026, 9, 11): 461730.0})

    def test_empty(self):
        self.assertEqual(parse_daily_block([]), {})


if __name__ == "__main__":
    unittest.main()
