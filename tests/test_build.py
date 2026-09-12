from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FX = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


def run(*extra: str) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "data.json"
        cmd = [sys.executable, "-m", "server.build_dashboard_data",
               "--day-z", str(FX / "day_z.csv"), "--night-sell", str(FX / "night_sell.csv"),
               "--sync-dump", str(FX / "sync_dump.json"), "--out", str(out),
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


if __name__ == "__main__":
    unittest.main()
