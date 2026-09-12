#!/usr/bin/env python3
"""Читает блок «Выручка по дням» из Google-таблицы (через gog) и сохраняет дневной CSV date,total.

Для объекта, у которого текущий год ведётся скриптом внутри Google-таблицы (v1).
При ошибке чтения старый CSV не трогается, код возврата ≠ 0 — крон передаст его сборщику как статус.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

from .series import _num, parse_day

WS = Path("/root/.openclaw/workspace/revenue_sources")
DEFAULT_RANGE = "'📊 СВОДКА'!E7:F1200"


def parse_daily_block(values: List[List[str]]) -> Dict[dt.date, float]:
    """Строки вида ['2026-09-12', '819\\xa0329'] → {date: 819329.0}; остальное пропускается."""
    result: Dict[dt.date, float] = {}
    for row in values or []:
        if len(row) < 2:
            continue
        day = parse_day(str(row[0]))
        if not day:
            continue
        result[day] = _num(str(row[1]).replace("\xa0", ""))
    return result


def fetch_values(spreadsheet_id: str, rng: str, account: str, timeout: int) -> List[List[str]]:
    raw = subprocess.check_output(
        ["gog", "sheets", "get", spreadsheet_id, rng, "--json", "--no-input", "--account", account],
        text=True, timeout=timeout,
    )
    return json.loads(raw).get("values") or []


def write_csv(path: Path, days: Dict[dt.date, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "total"])
        for day in sorted(days):
            w.writerow([day.isoformat(), round(days[day])])
    tmp.replace(path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch daily revenue block from a Google Sheet into CSV.")
    ap.add_argument("--spreadsheet-id", required=True)
    ap.add_argument("--range", default=DEFAULT_RANGE)
    ap.add_argument("--account", default="vet.valaam@ya.ru")
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()
    try:
        days = parse_daily_block(fetch_values(args.spreadsheet_id, args.range, args.account, args.timeout))
    except Exception as exc:  # gog не установлен / нет сети / битый ответ — старый файл остаётся
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}, ensure_ascii=False))
        return 1
    if not days:
        print(json.dumps({"ok": False, "error": "empty daily block"}))
        return 1
    write_csv(Path(args.out), days)
    last = max(days)
    print(json.dumps({"ok": True, "out": args.out, "days": len(days), "last": last.isoformat(), "last_value": round(days[last])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
