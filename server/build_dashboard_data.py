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
from .series import (merge_series, read_day_z, read_night_sell, read_sync_dump,
                     read_waterfalls_csv, read_waterfalls_dump, sum_series)

MSK = dt.timezone(dt.timedelta(hours=3))
WS = Path("/root/.openclaw/workspace/revenue_sources")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build dashboard data.json from local revenue files.")
    ap.add_argument("--day-z", default=str(WS / "paaso_day_platforma_ofd_z_2025_2026/ofd_z.csv"))
    ap.add_argument("--night-sell", default=str(WS / "paaso_night_ofd_ru/ofd_sell.csv"))
    ap.add_argument("--sync-dump", default=str(WS / "paaso_daily_series.json"))
    ap.add_argument("--waterfalls-csv", default=str(WS / "waterfalls_daily_2025.csv"),
                    help="Статичный дневной ряд объекта w1 за прошлые годы")
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
    p1 = merge_series(day, night, dump)
    w1 = read_waterfalls_csv(Path(args.waterfalls_csv))
    w1.update(read_waterfalls_dump(Path(args.sync_dump)))
    objects = {"p1": p1, "w1": w1, "all": sum_series(p1, w1)}

    # Предупреждения источника данных — общие для всех объектов; ночная касса — только Паасо и «Всё».
    common = []
    if not dump:
        common.append("sync_dump_missing")
    elif dump_updated is None:
        common.append("sync_dump_stale")
    else:
        if dump_updated.tzinfo is None:
            dump_updated = dump_updated.replace(tzinfo=MSK)
        age_min = (now - dump_updated.astimezone(MSK)).total_seconds() / 60
        if age_min > args.max_dump_age_min:
            common.append("sync_dump_stale")
    night_failed = args.night_fetch_status != 0
    warnings = {code: list(common) + (["night_fetch_failed"] if night_failed and code != "w1" else [])
                for code in objects}

    payload = build_payload(objects, today, now, warnings)
    for code, block in payload["objects"].items():
        tb = block["today"]
        if common or (night_failed and code != "w1"):
            tb["complete"] = False
        if not tb["complete"]:
            block["warnings"].append("today_incomplete")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(out)

    print(json.dumps({
        "ok": True,
        "out": str(out),
        "today": today.isoformat(),
        "today_value": payload["objects"]["p1"]["today"]["value"],
        "w1_today_value": payload["objects"]["w1"]["today"]["value"],
        "out_rows_days": len(p1),
        "warnings": payload["objects"]["p1"]["warnings"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
