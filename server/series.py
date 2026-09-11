"""Чтение дневного ряда выручки Паасо из локальных файлов сервера.

Ничего не скачивает: только CSV/JSON, уже лежащие в revenue_sources/.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class DayValue:
    day: float = 0.0        # дневные кассы (Платформа ОФД)
    night: float = 0.0      # ночная касса (ОФД.ру)
    complete: bool = True   # False — за дату не удалось получить одну из касс

    @property
    def total(self) -> float:
        return self.day + self.night


def parse_day(value: Optional[str]) -> Optional[dt.date]:
    value = (value or "").strip()
    if len(value) < 10:
        return None
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


def _num(value: Optional[str]) -> float:
    try:
        return float((value or "0").replace(" ", "").replace(",", "."))
    except ValueError:
        return 0.0


def read_day_z(path: Path) -> Dict[dt.date, float]:
    """Дневные кассы по Z-отчётам: выручка дня = incomeSumm − refundIncomeSumm, дата — закрытие смены."""
    result: Dict[dt.date, float] = defaultdict(float)
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            day = parse_day(row.get("shiftCloseDate"))
            if not day:
                continue
            result[day] += _num(row.get("incomeSumm")) - _num(row.get("refundIncomeSumm"))
    return dict(result)


def read_night_sell(path: Path) -> Dict[dt.date, float]:
    """Ночная касса по чекам. В CSV одна строка на позицию — считаем каждый чек один раз."""
    result: Dict[dt.date, float] = defaultdict(float)
    if not path.exists():
        return {}
    seen: set = set()
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            day = parse_day(row.get("receiptDate"))
            if not day:
                continue
            key = (row.get("rqId") or "", row.get("fiscalDocumentNumber") or "", row.get("requestNumber") or "")
            if key in seen:
                continue
            seen.add(key)
            op = str(row.get("operationType") or "1")
            sign = -1 if op in {"2", "3", "PAYBACK", "REFUND"} else 1
            result[day] += sign * _num(row.get("totalSum") or row.get("amount"))
    return dict(result)


def read_sync_dump(path: Path) -> Tuple[Dict[dt.date, DayValue], Optional[dt.datetime]]:
    """Дамп дневного ряда, который пишет sync_paaso_revenue_google_sheet.py (см. server/patches/)."""
    if not path.exists():
        return {}, None
    data = json.loads(path.read_text(encoding="utf-8"))
    days: Dict[dt.date, DayValue] = {}
    for key, v in (data.get("days") or {}).items():
        day = parse_day(key)
        if not day:
            continue
        days[day] = DayValue(float(v.get("day") or 0), float(v.get("night") or 0), bool(v.get("complete", True)))
    updated: Optional[dt.datetime] = None
    if data.get("updated_at"):
        try:
            updated = dt.datetime.fromisoformat(str(data["updated_at"]))
        except ValueError:
            updated = None
    return days, updated


def merge_series(
    day: Dict[dt.date, float],
    night: Dict[dt.date, float],
    dump: Dict[dt.date, DayValue],
) -> Dict[dt.date, DayValue]:
    """База — CSV (оба года), поверх — дамп sync-скрипта (в нём сегодняшний день из API)."""
    result: Dict[dt.date, DayValue] = {}
    for d in set(day) | set(night):
        result[d] = DayValue(day.get(d, 0.0), night.get(d, 0.0), True)
    result.update(dump)
    return result
