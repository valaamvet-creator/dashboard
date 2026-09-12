"""Расчёт блоков дашборда из дневного ряда. Чистые функции, без ввода-вывода."""
from __future__ import annotations

import calendar
import datetime as dt
import math
from typing import Dict, List, Optional

from .series import DayValue

Series = Dict[dt.date, DayValue]
WEEK_SHIFT = dt.timedelta(days=364)   # 52 недели: тот же день недели год назад


def pct(cur: float, prev: float) -> Optional[int]:
    if prev <= 0:
        return None
    raw = (cur - prev) / prev * 100
    return int(math.floor(abs(raw) + 0.5)) * (1 if raw >= 0 else -1)


def sum_range(series: Series, start: dt.date, end: dt.date) -> float:
    total = 0.0
    d = start
    while d <= end:
        v = series.get(d)
        if v:
            total += v.total
        d += dt.timedelta(days=1)
    return total


def has_data(series: Series, start: dt.date, end: dt.date) -> bool:
    d = start
    while d <= end:
        if d in series:
            return True
        d += dt.timedelta(days=1)
    return False


def same_date_prev_year(d: dt.date) -> dt.date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:            # 29 февраля
        return d.replace(year=d.year - 1, day=28)


def _cmp(series: Series, start: dt.date, end: dt.date, pstart: dt.date, pend: dt.date) -> dict:
    cur = sum_range(series, start, end)
    prev = sum_range(series, pstart, pend) if has_data(series, pstart, pend) else None
    return {
        "value": int(round(cur)),
        "prev": None if prev is None else int(round(prev)),
        "pct": None if prev is None else pct(cur, prev),
    }


def today_block(series: Series, today: dt.date) -> dict:
    prev_date = today - WEEK_SHIFT
    v = series.get(today)
    p = series.get(prev_date)
    return {
        "date": today.isoformat(),
        "value": int(round(v.total)) if v else 0,
        "prev_date": prev_date.isoformat(),
        "prev": int(round(p.total)) if p else None,
        "pct": pct(v.total, p.total) if (v and p) else None,
        "complete": bool(v and v.complete),
    }


def week7_block(series: Series, today: dt.date) -> dict:
    end = today - dt.timedelta(days=1)
    start = end - dt.timedelta(days=6)
    b = _cmp(series, start, end, start - WEEK_SHIFT, end - WEEK_SHIFT)
    b.update({
        "from": start.isoformat(),
        "to": end.isoformat(),
        "avg_day": int(round(b["value"] / 7)),
        "prev_avg_day": None if b["prev"] is None else int(round(b["prev"] / 7)),
    })
    return b


def mtd_block(series: Series, today: dt.date) -> dict:
    start = today.replace(day=1)
    b = _cmp(series, start, today, same_date_prev_year(start), same_date_prev_year(today))
    b.update({"from": start.isoformat(), "to": today.isoformat()})
    return b


def _month_bounds(year: int, month: int):
    return dt.date(year, month, 1), dt.date(year, month, calendar.monthrange(year, month)[1])


def prev_month_block(series: Series, today: dt.date) -> dict:
    y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    start, end = _month_bounds(y, m)
    pstart, pend = _month_bounds(y - 1, m)
    b = _cmp(series, start, end, pstart, pend)
    b.update({"month": f"{y:04d}-{m:02d}"})
    return b


def ytd_block(series: Series, today: dt.date) -> dict:
    start = dt.date(today.year, 1, 1)
    b = _cmp(series, start, today, dt.date(today.year - 1, 1, 1), same_date_prev_year(today))
    b.update({"from": start.isoformat(), "to": today.isoformat()})
    return b


def months_block(series: Series, today: dt.date) -> List[dict]:
    out: List[dict] = []
    for m in range(1, 13):
        start, end = _month_bounds(today.year, m)
        pstart, pend = _month_bounds(today.year - 1, m)
        if start <= today <= end:
            # Текущий месяц: % должен считаться по тем же датам, что и «месяц в моменте» (MTD),
            # иначе на графике проценты для текущего месяца не совпадают с блоком MTD.
            pend = same_date_prev_year(today)
        prev = sum_range(series, pstart, pend) if has_data(series, pstart, pend) else None
        if start > today:
            cur = None
        else:
            cur = sum_range(series, start, min(end, today))
        out.append({
            "m": m,
            "cur": None if cur is None else int(round(cur)),
            "prev": None if prev is None else int(round(prev)),
            "pct": pct(cur, prev) if (cur is not None and prev is not None) else None,
        })
    return out


def object_block(series: Series, today: dt.date, warnings: List[str]) -> dict:
    return {
        "today": today_block(series, today),
        "week7": week7_block(series, today),
        "mtd": mtd_block(series, today),
        "prev_month": prev_month_block(series, today),
        "ytd": ytd_block(series, today),
        "months": months_block(series, today),
        "warnings": list(warnings),
    }


def build_payload(
    objects: Dict[str, Series],
    today: dt.date,
    generated_at: dt.datetime,
    warnings: Dict[str, List[str]],
) -> dict:
    """data.json: по блоку на каждый объект (коды p1, w1, all); имена объектов живут только в index.html."""
    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "objects": {code: object_block(series, today, warnings.get(code, [])) for code, series in objects.items()},
    }
