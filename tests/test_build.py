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
