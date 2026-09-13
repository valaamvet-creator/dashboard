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

from .metrics import build_payload, object_block, sum_forecasts
from .series import (DayTotal, TICKET_GROUPS, W1_TICKET_GROUPS, merge_series, read_daily_total_csv, read_day_z,
                     read_night_sell, read_paaso_tickets, read_sync_dump, read_waterfalls_dump,
                     read_waterfalls_tickets, sum_series)

MSK = dt.timezone(dt.timedelta(hours=3))
WS = Path("/root/.openclaw/workspace/revenue_sources")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build dashboard data.json from local revenue files.")
    ap.add_argument("--day-z", default=str(WS / "paaso_day_platforma_ofd_z_2025_2026/ofd_z.csv"))
    ap.add_argument("--night-sell", default=str(WS / "paaso_night_ofd_ru/ofd_sell.csv"))
    ap.add_argument("--sync-dump", default=str(WS / "paaso_daily_series.json"))
    ap.add_argument("--waterfalls-csv", default=str(WS / "waterfalls_daily_2025.csv"),
                    help="Статичный дневной ряд объекта w1 за прошлые годы")
    ap.add_argument("--vashun-history-csv", default=str(WS / "vashun_daily_history.csv"),
                    help="Статичный дневной ряд объекта v1 (2025 и начало 2026)")
    ap.add_argument("--vashun-sheet-csv", default=str(WS / "vashun_daily_sheet.csv"),
                    help="Дневной ряд v1 из Google-таблицы (пишет fetch_sheet_daily.py)")
    ap.add_argument("--vashun-sheet-status", type=int, default=0,
                    help="Код возврата fetch_sheet_daily.py в этом тике (≠0 — сегодня v1 неполный)")
    ap.add_argument("--out", default=str(WS / "dashboard_data.json"))
    ap.add_argument("--today", help="YYYY-MM-DD (по умолчанию — сегодня по Москве)")
    ap.add_argument("--night-fetch-status", type=int, default=0)
    ap.add_argument("--max-dump-age-min", type=int, default=60)
    ap.add_argument("--p1-receipts", default=str(WS / "paaso_day_platforma_ofd_receipts_2025_2026_full/ofd_sell.csv"),
                    help="Позиции чеков дневных касс p1 — для подсчёта посетителей по билетам")
    ap.add_argument("--w1-receipts", default=str(WS / "waterfalls_ofd_2026/ofd_sell.csv"),
                    help="Позиции чеков касс w1 (только текущий год) — посетители по билетам")
    ap.add_argument("--w1-extra-csv", default=str(WS / "waterfalls_fedotov_2026.csv"),
                    help="Доп. касса w1 (закрыта 01.05.2026): date,total,grp_full,grp_conc — добавляется к выручке и людям")
    args = ap.parse_args()

    now = dt.datetime.now(MSK)
    today = dt.date.fromisoformat(args.today) if args.today else now.date()

    day = read_day_z(Path(args.day_z))
    night = read_night_sell(Path(args.night_sell))
    dump, dump_updated = read_sync_dump(Path(args.sync_dump))
    p1 = merge_series(day, night, dump)
    w1 = read_daily_total_csv(Path(args.waterfalls_csv))
    w1.update(read_waterfalls_dump(Path(args.sync_dump)))
    w1_extra = read_daily_total_csv(Path(args.w1_extra_csv))       # доп. касса: не перекрывает, а прибавляется
    if w1_extra:
        w1 = sum_series(w1, w1_extra)
    v1 = read_daily_total_csv(Path(args.vashun_history_csv))
    v1.update(read_daily_total_csv(Path(args.vashun_sheet_csv)))
    objects = {"p1": p1, "w1": w1, "v1": v1, "all": sum_series(sum_series(p1, w1), v1)}

    # Предупреждения по источникам. Дамп sync-скрипта → p1 и w1; ночная касса → p1; таблица → v1; «Всё» — всё вместе.
    dump_warnings = []
    if not dump:
        dump_warnings.append("sync_dump_missing")
    elif dump_updated is None:
        dump_warnings.append("sync_dump_stale")
    else:
        if dump_updated.tzinfo is None:
            dump_updated = dump_updated.replace(tzinfo=MSK)
        age_min = (now - dump_updated.astimezone(MSK)).total_seconds() / 60
        if age_min > args.max_dump_age_min:
            dump_warnings.append("sync_dump_stale")
    night_warnings = ["night_fetch_failed"] if args.night_fetch_status != 0 else []
    sheet_warnings = ["vashun_sheet_failed"] if args.vashun_sheet_status != 0 else []
    warnings = {
        "p1": dump_warnings + night_warnings,
        "w1": list(dump_warnings),
        "v1": list(sheet_warnings),
    }
    warnings["all"] = warnings["p1"] + [w for w in warnings["w1"] if w not in warnings["p1"]] + warnings["v1"]

    payload = build_payload(objects, today, now, warnings)
    # Посетители (режим «чел.»): всего и по группам билетов; сегодня неполный, если неполна выручка объекта.
    def add_people(code: str, tickets: dict, groups) -> None:
        if not tickets:
            return
        def people_series(pick):
            return {d: DayTotal(float(pick(t)), t.complete) for d, t in tickets.items()}
        people = object_block(people_series(lambda t: t.total), today, warnings[code])
        people["today"]["complete"] = people["today"]["complete"] and payload["objects"][code]["today"]["complete"]
        payload["objects"][code]["people"] = people
        payload["objects"][code]["people_groups"] = {
            g: object_block(people_series(lambda t, g=g: t.groups.get(g, 0)), today, []) for g in groups
        }
    add_people("p1", read_paaso_tickets(Path(args.p1_receipts), Path(args.night_sell)), TICKET_GROUPS)
    add_people("w1", read_waterfalls_tickets(Path(args.w1_receipts), Path(args.w1_extra_csv)), W1_TICKET_GROUPS)

    # «Всё»: прогноз — сумма прогнозов объектов, чтобы цифры на вкладках сходились.
    payload["objects"]["all"]["forecast"] = sum_forecasts(
        [payload["objects"][c]["forecast"] for c in ("p1", "w1", "v1")])
    for code, block in payload["objects"].items():
        tb = block["today"]
        if warnings[code]:
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
        "v1_today_value": payload["objects"]["v1"]["today"]["value"],
        "out_rows_days": len(p1),
        "warnings": payload["objects"]["p1"]["warnings"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
