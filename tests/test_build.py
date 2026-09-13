from __future__ import annotations
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FX = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


def run(*extra: str, sync_dump: Path | None = None, max_dump_age_min: int | None = None) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "data.json"
        sync_dump_path = sync_dump if sync_dump else FX / "sync_dump.json"
        cmd = [sys.executable, "-m", "server.build_dashboard_data",
               "--day-z", str(FX / "day_z.csv"), "--night-sell", str(FX / "night_sell.csv"),
               "--sync-dump", str(sync_dump_path), "--out", str(out),
               "--waterfalls-csv", str(FX / "wf_daily_2025.csv"),
               "--vashun-history-csv", str(FX / "v1_history.csv"), "--vashun-sheet-csv", str(FX / "v1_sheet.csv"),
               "--p1-receipts", str(FX / "p1_receipts.csv"), "--w1-receipts", str(FX / "w1_receipts.csv"),
               "--w1-extra-csv", str(FX / "w1_extra.csv"),
               "--today", "2026-09-11"]
        if max_dump_age_min is None:
            cmd.extend(["--max-dump-age-min", "999999"])
        else:
            cmd.extend(["--max-dump-age-min", str(max_dump_age_min)])
        cmd.extend(extra)
        res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env={**os.environ, "TZ": "UTC"})
        assert res.returncode == 0, res.stderr
        return json.loads(out.read_text(encoding="utf-8")), json.loads(res.stdout)


class Build(unittest.TestCase):
    def test_waterfalls_object_from_dump_and_csv(self):
        data, report = run()
        w = data["objects"]["w1"]
        self.assertEqual(w["today"]["value"], 348750 + 1000)    # wf1+wf2 из дампа + доп. касса
        self.assertFalse(w["today"]["complete"])                # wf_complete=false
        self.assertEqual(w["today"]["prev"], 7000)              # 2025-09-12 из CSV (−364 дня)
        self.assertIn("today_incomplete", w["warnings"])
        self.assertNotIn("night_fetch_failed", w["warnings"])   # ночная касса — только Паасо

    def test_vashun_object_from_history_and_sheet(self):
        data, _ = run()
        v = data["objects"]["v1"]
        self.assertEqual(v["today"]["value"], 461730)           # из CSV таблицы
        self.assertTrue(v["today"]["complete"])                 # статус чтения таблицы 0
        self.assertEqual(v["today"]["prev"], 30000)             # 2025-09-12 из истории
        self.assertEqual(v["warnings"], [])                     # дамп/ночная касса к v1 не относятся

    def test_vashun_sheet_failure_marks_v1_and_all_incomplete(self):
        data, _ = run("--vashun-sheet-status", "1")
        self.assertFalse(data["objects"]["v1"]["today"]["complete"])
        self.assertIn("vashun_sheet_failed", data["objects"]["v1"]["warnings"])
        self.assertIn("vashun_sheet_failed", data["objects"]["all"]["warnings"])
        self.assertNotIn("vashun_sheet_failed", data["objects"]["w1"]["warnings"])

    def test_all_forecast_is_sum_of_object_forecasts(self):
        data, _ = run()
        fs = [data["objects"][k]["forecast"] for k in ("p1", "w1", "v1")]
        a = data["objects"]["all"]["forecast"]
        self.assertEqual(a["year"]["point"], sum(f["year"]["point"] for f in fs if f))
        self.assertIsNone(a["k"])

    def test_p1_people_from_tickets(self):
        data, _ = run()
        ppl = data["objects"]["p1"]["people"]
        self.assertEqual(set(ppl), {"today", "week7", "mtd", "prev_month", "ytd", "months", "warnings", "forecast"})
        self.assertEqual(ppl["today"]["value"], 6)                # 2+1+1+2 (вездеход не человек)
        self.assertEqual(ppl["today"]["prev"], 3)                 # 2025-09-12
        self.assertEqual(ppl["today"]["pct"], 100)
        g = data["objects"]["p1"]["people_groups"]
        self.assertEqual(list(g), ["full", "conc", "grp_full", "grp_conc", "extra"])
        self.assertEqual(g["full"]["today"]["value"], 2)
        self.assertEqual(g["extra"]["today"]["value"], 1)
        w = data["objects"]["w1"]["people"]
        self.assertEqual(w["today"]["value"], 15)                 # 10 по чекам + 5 доп. кассы, включая бесплатных
        self.assertIsNone(w["today"]["prev"])                     # 2025 по билетам нет
        self.assertIsNone(w["forecast"])                          # без прошлого года прогноза нет
        self.assertEqual(list(data["objects"]["w1"]["people_groups"]), ["full", "conc", "grp_full", "grp_conc", "free"])
        self.assertNotIn("people", data["objects"]["v1"])

    def test_all_object_is_sum_of_three(self):
        data, _ = run()
        p1, w1, v1, a = (data["objects"][k] for k in ("p1", "w1", "v1", "all"))
        self.assertEqual(a["today"]["value"], p1["today"]["value"] + w1["today"]["value"] + v1["today"]["value"])
        self.assertEqual(w1["today"]["value"], 349750)
        self.assertEqual(a["today"]["prev"], 7000 + 30000)      # у Паасо prev нет
        self.assertFalse(a["today"]["complete"])                # Паасо и Водопады неполные
        self.assertEqual(list(data["objects"]), ["p1", "w1", "v1", "all"])

    def test_night_fetch_failure_marks_p1_and_all_incomplete_only(self):
        data, _ = run("--night-fetch-status", "1")
        self.assertFalse(data["objects"]["p1"]["today"]["complete"])
        self.assertFalse(data["objects"]["all"]["today"]["complete"])
        self.assertIn("night_fetch_failed", data["objects"]["all"]["warnings"])

    def test_writes_payload_from_fixtures(self):
        data, report = run()
        o = data["objects"]["p1"]
        self.assertEqual(o["today"]["value"], 243350)          # из дампа
        self.assertFalse(o["today"]["complete"])
        self.assertEqual(o["today"]["prev"], None)              # 12.09.2025 в фикстурах нет
        self.assertIn("today_incomplete", o["warnings"])
        self.assertEqual(report["out_rows_days"], 3)            # 2025-09-11, 2026-09-10, 2026-09-11

    def test_night_fetch_failure_adds_warning(self):
        data, _ = run("--night-fetch-status", "1")
        self.assertIn("night_fetch_failed", data["objects"]["p1"]["warnings"])

    def test_stale_dump_warning(self):
        data, _ = run("--max-dump-age-min", "1")
        self.assertIn("sync_dump_stale", data["objects"]["p1"]["warnings"])

    def test_naive_updated_at_stale(self):
        # Naive timestamp = now - 90 minutes in MSK, treated as MSK (not UTC).
        # With max_dump_age_min=60, should detect as stale.
        # Without the fix: naive read as UTC machine-local time, would appear 3h in future on UTC → not stale.
        MSK = dt.timezone(dt.timedelta(hours=3))
        with tempfile.TemporaryDirectory() as tmp:
            original = json.loads((FX / "sync_dump.json").read_text(encoding="utf-8"))
            now_msk = dt.datetime.now(MSK)
            # Naive timestamp: 90 minutes ago, without tzinfo
            old_naive = (now_msk - dt.timedelta(minutes=90)).replace(tzinfo=None)
            original["updated_at"] = old_naive.isoformat(timespec="seconds")

            dump_file = Path(tmp) / "dump.json"
            dump_file.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")

            data, _ = run(sync_dump=dump_file, max_dump_age_min=60)
            self.assertIn("sync_dump_stale", data["objects"]["p1"]["warnings"])

    def test_missing_dump_marks_today_incomplete(self):
        data, _ = run(sync_dump=FX / "nope.json")
        o = data["objects"]["p1"]
        self.assertIn("sync_dump_missing", o["warnings"])
        self.assertFalse(o["today"]["complete"])

    def test_stale_dump_marks_today_incomplete(self):
        # База уже содержит complete:false для сегодня — подменяем на true, чтобы
        # проверка действительно упиралась в устаревший дамп, а не в исходные данные.
        MSK = dt.timezone(dt.timedelta(hours=3))
        with tempfile.TemporaryDirectory() as tmp:
            original = json.loads((FX / "sync_dump.json").read_text(encoding="utf-8"))
            original["days"]["2026-09-11"]["complete"] = True
            now_msk = dt.datetime.now(MSK)
            old_naive = (now_msk - dt.timedelta(minutes=90)).replace(tzinfo=None)
            original["updated_at"] = old_naive.isoformat(timespec="seconds")

            dump_file = Path(tmp) / "dump.json"
            dump_file.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")

            data, _ = run(sync_dump=dump_file, max_dump_age_min=60)
            o = data["objects"]["p1"]
            self.assertIn("sync_dump_stale", o["warnings"])
            self.assertFalse(o["today"]["complete"])

    def test_naive_updated_at_fresh(self):
        # Naive timestamp = now in MSK, treated as MSK (not UTC).
        # With max_dump_age_min=60, should NOT detect as stale.
        # Without the fix: naive read as UTC machine-local time, would appear 3h in future on UTC → negative age → not stale (accidental).
        MSK = dt.timezone(dt.timedelta(hours=3))
        with tempfile.TemporaryDirectory() as tmp:
            original = json.loads((FX / "sync_dump.json").read_text(encoding="utf-8"))
            now_msk = dt.datetime.now(MSK)
            # Naive timestamp: now in MSK, without tzinfo
            now_naive = now_msk.replace(tzinfo=None)
            original["updated_at"] = now_naive.isoformat(timespec="seconds")

            dump_file = Path(tmp) / "dump.json"
            dump_file.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")

            data, _ = run(sync_dump=dump_file, max_dump_age_min=60)
            self.assertNotIn("sync_dump_stale", data["objects"]["p1"]["warnings"])


if __name__ == "__main__":
    unittest.main()
