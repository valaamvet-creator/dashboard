#!/usr/bin/env python3
"""Собирает data.json для дашборда из локальных файлов сервера. В API не ходит.

Запуск на сервере (из крона): см. server/publish.sh и hourly_update_paaso_revenue_summary.sh.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from .metrics import build_payload
from .series import merge_series, read_day_z, read_night_sell, read_sync_dump

MSK = dt.timezone(dt.timedelta(hours=3))
WS = Path("/root/.openclaw/workspace/revenue_sources")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build dashboard data.json from local revenue files.")
    ap.add_argument("--day-z", default=str(WS / "paaso_day_platforma_ofd_z_2025_2026/ofd_z.csv"))
    ap.add_argument("--night-sell", default=str(WS / "paaso_night_ofd_ru/ofd_sell.csv"))
    ap.add_argument("--sync-dump", default=str(WS / "paaso_daily_series.json"))
    ap.add_argument("--out", default=str(WS / "dashboard_data.json"))
    ap.add_argument("--today", help="YYYY-MM-DD (по умолчанию — сегодня по Москве)")
    ap.add_argument("--night-fetch-status", type=int, default=0)
    ap.add_argument("--max-dump-age-min", type=int, default=60)
    args = ap.parse_args()

    now = dt.datetime.now(MSK)
    today = dt.date.fromisoformat(args.today) if args.today else now.date()

    day = read_day_z(Path(args.day_z))
    night = read_night_sell(Path(args.night_sell))
    dump, dump_updated = read_sync_dump(Path(args.sync_dump))
    series = merge_series(day, night, dump)

    warnings = []
    if args.night_fetch_status != 0:
        warnings.append("night_fetch_failed")
    if not dump:
        warnings.append("sync_dump_missing")
    elif dump_updated is not None:
        age_min = (now - dump_updated.astimezone(MSK)).total_seconds() / 60
        if age_min > args.max_dump_age_min:
            warnings.append("sync_dump_stale")

    payload = build_payload(series, today, now, warnings)
    tb = payload["objects"]["p1"]["today"]
    if args.night_fetch_status != 0:
        tb["complete"] = False
    if not tb["complete"] and "today_incomplete" not in warnings:
        warnings.append("today_incomplete")
    payload["objects"]["p1"]["warnings"] = warnings

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(out)

    print(json.dumps({
        "ok": True,
        "out": str(out),
        "today": tb["date"],
        "today_value": tb["value"],
        "out_rows_days": len(series),
        "warnings": warnings,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
