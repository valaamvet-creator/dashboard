from __future__ import annotations
import datetime as dt
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FX = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


def run(*extra: str, sync_dump: Path | None = None) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "data.json"
        sync_dump_path = sync_dump if sync_dump else FX / "sync_dump.json"
        cmd = [sys.executable, "-m", "server.build_dashboard_data",
               "--day-z", str(FX / "day_z.csv"), "--night-sell", str(FX / "night_sell.csv"),
               "--sync-dump", str(sync_dump_path), "--out", str(out),
               "--today", "2026-09-11", "--max-dump-age-min", "999999", *extra]
        res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
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

    def test_naive_updated_at_treated_as_msk(self):
        # Read fixture, replace updated_at with naive datetime (now in MSK)
        MSK = dt.timezone(dt.timedelta(hours=3))
        with tempfile.TemporaryDirectory() as tmp:
            original = json.loads((FX / "sync_dump.json").read_text(encoding="utf-8"))
            # Create naive timestamp: now in MSK, but without tzinfo
            now_msk = dt.datetime.now(MSK).replace(tzinfo=None)
            original["updated_at"] = now_msk.isoformat(timespec="seconds")

            dump_file = Path(tmp) / "dump.json"
            dump_file.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")

            # Run with default --max-dump-age-min (60 minutes), without passing 999999
            data, _ = run(sync_dump=dump_file)
            warnings = data["objects"]["p1"]["warnings"]
            # Naive timestamp should be treated as MSK, so dump is fresh, no stale warning
            self.assertNotIn("sync_dump_stale", warnings)


if __name__ == "__main__":
    unittest.main()
