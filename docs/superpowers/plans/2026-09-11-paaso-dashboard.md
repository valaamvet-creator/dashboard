# Дашборд выручки Паасо — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сайт-дашборд на GitHub Pages, который каждые 15 минут получает с сервера готовый `data.json` с выручкой Паасо (сегодня, 7 дней, месяц/год в моменте, прошлый месяц, 12 месяцев) и процентами к прошлому году.

**Architecture:** На сервере (`ssh my-server`, `/root/.openclaw/workspace`) уже есть 15-минутный крон, который собирает дневной ряд Паасо и заливает Google-таблицу. Мы (1) заставляем его дополнительно сохранять этот ряд в локальный JSON, (2) добавляем чистый скрипт `build_dashboard_data.py`, который из локальных файлов (дневные Z-отчёты 2025–2026, ночные чеки 2025–2026, дамп синхронизации) считает метрики в `data.json`, (3) публикуем `data.json` в публичный репозиторий `valaamvet-creator/dashboard` (клон на сервере `/root/dashboard-pub`), откуда GitHub Pages раздаёт `index.html`. Страница — один HTML-файл без библиотек.

**Tech Stack:** Python 3.9+ (на Маке 3.9.6, на сервере 3.14.4 — код должен работать на обоих: `from __future__ import annotations`, без `match`, без `X | Y` в рантайме), `unittest` (pytest на сервере нет), bash, git, GitHub Pages, ванильный HTML/CSS/JS.

**Spec:** `docs/superpowers/specs/2026-09-11-paaso-dashboard-design.md`

## Global Constraints

- Локальный проект (Мак): `/Users/vet/Claude/projects/paaso-dashboard` — это и есть будущий репозиторий `valaamvet-creator/dashboard`. GitHub Pages раздаёт корень ветки `main`.
- Сервер: доступ `ssh my-server`, пользователь root. Рабочая папка `/root/.openclaw/workspace` (git-репозиторий с корнем `/root/.openclaw`). Клон дашборда: `/root/dashboard-pub`.
- В репозитории `dashboard` — никаких названий компаний: объект Паасо в данных под кодом `p1`. Понятное имя «Паасо» — только в `index.html`.
- Секреты (ключи ОФД, токены) в репозиторий не попадают. Скрипты читают только локальные CSV/JSON — в API они не ходят.
- Правила сравнения: «сегодня» и «7 дней» — сдвиг 364 дня; месяц/год в моменте, прошлый месяц, график по месяцам — календарные даты прошлого года.
- «7 дней» = 7 **полных** дней до сегодня: `today-7 … today-1`.
- Процент = `round((cur − prev) / prev × 100)`; если `prev ≤ 0` или данных нет → `null`.
- Суммы в `data.json` — целые рубли.
- Ошибка в шагах дашборда никогда не должна ломать обновление Google-таблицы.
- Коммиты на Маке: `git -c user.name="Виталий" -c user.email="valaam.vet@gmail.com" commit …` (глобальный git config не настроен). На сервере автор задаётся через `GIT_AUTHOR_*`/`GIT_COMMITTER_*`.
- Все сообщения пользователю — по-русски, просто.

## Структура файлов

```
paaso-dashboard/                      ← репозиторий valaamvet-creator/dashboard
├── index.html                        ← страница (Task 5)
├── data.json                         ← стартовый образец; на проде перезаписывает сервер
├── robots.txt, .nojekyll             ← запрет индексации, отключение Jekyll
├── server/
│   ├── __init__.py
│   ├── series.py                     ← чтение дневного ряда из CSV/JSON (Task 2)
│   ├── metrics.py                    ← расчёт блоков и процентов, чистые функции (Task 3)
│   ├── build_dashboard_data.py       ← CLI: файлы → data.json (Task 4)
│   ├── publish.sh                    ← git pull/commit/push data.json (Task 6)
│   └── patches/sync_daily_series_dump.md  ← как пропатчен серверный sync-скрипт (Task 6)
├── tests/
│   ├── __init__.py
│   ├── fixtures/                     ← маленькие CSV/JSON для тестов
│   ├── test_series.py
│   ├── test_metrics.py
│   └── test_build.py
└── docs/superpowers/{specs,plans}/
```

Серверные изменения вне репозитория:
- `tools/revenue/sync_paaso_revenue_google_sheet.py` — +дамп дневного ряда (Task 6).
- `tools/revenue/hourly_update_paaso_revenue_summary.sh` — +2 шага в конце (Task 8).
- `revenue_sources/paaso_night_ofd_ru/` — догрузка 2025 (Task 1).

---

### Task 1: Догрузить ночную кассу за 2025 в рабочий набор (сервер)

**Files:**
- Modify (данные, сервер): `/root/.openclaw/workspace/revenue_sources/paaso_night_ofd_ru/ofd_sell.csv`, `ofd_z.csv`

**Interfaces:**
- Produces: `ofd_sell.csv` содержит чеки ночной кассы с 2025-01-20 по сегодня. Task 4 читает его.

Скрипт `tools/ofd_ru/fetch_paaso_night_cashbox.py` в режиме `--mode full` **сливает** новые строки с существующими (функция `merge_rows`, строки 524–527), ничего не стирает. Пробный запуск 11.09.2026 в `/tmp/night_2025_probe` дал 358 Z-отчётов и 5076 строк чеков, 0 ошибок API. Google-таблица не изменится: `sync_paaso_revenue_google_sheet.py` отбрасывает даты раньше `START_DATE = 2026-01-01`.

- [ ] **Step 1: Зафиксировать состояние до**

```bash
ssh my-server 'cd /root/.openclaw/workspace/revenue_sources/paaso_night_ofd_ru && wc -l ofd_sell.csv ofd_z.csv && cp ofd_sell.csv /root/night_sell_before_2025_backfill.csv && cp ofd_z.csv /root/night_z_before_2025_backfill.csv'
```
Ожидаемо: ~4433 и ~254 строки (с заголовком). Копии — страховка для отката.

- [ ] **Step 2: Догрузить 2025 (не в час :05/:20/:35/:50, чтобы не пересечься с кроном)**

```bash
ssh my-server 'cd /root/.openclaw/workspace && timeout 900 /usr/bin/python3 tools/ofd_ru/fetch_paaso_night_cashbox.py --mode full --date-from 2025-01-01 --date-to 2025-12-31 --chunk-days 30'
```
Ожидаемо в JSON-выводе: `"ok": true`, `"api_errors": 0`, `total_sell_rows` ≈ 4432+5076 ≈ 9500, `total_z_rows` ≈ 253+358 ≈ 611.

- [ ] **Step 3: Проверить, что 2026 не пострадал и 2025 появился**

```bash
ssh my-server 'cd /root/.openclaw/workspace/revenue_sources/paaso_night_ofd_ru && python3 - <<PY
import csv
rows=list(csv.DictReader(open("ofd_sell.csv",encoding="utf-8")))
ds=sorted(r["receiptDate"][:10] for r in rows if r.get("receiptDate"))
print("чеки:", len(rows), ds[0], "…", ds[-1])
print("2025:", sum(1 for d in ds if d.startswith("2025")), "2026:", sum(1 for d in ds if d.startswith("2026")))
PY'
```
Ожидаемо: период `2025-01-20 … <сегодня>`, 2026 ≈ 4432 (как было), 2025 ≈ 5076.

- [ ] **Step 4: Убедиться, что ближайший запуск крона прошёл штатно**

Подождать следующей отметки :05/:20/:35/:50 + 2 минуты, затем:
```bash
ssh my-server 'cat /root/.openclaw/workspace/revenue_sources/paaso_night_ofd_ru/logs/revenue_summary_status.env; tail -3 /root/.openclaw/workspace/revenue_sources/paaso_night_ofd_ru/logs/hourly_update.log'
```
Ожидаемо: `status=ok`, `fetch=0 sync=0 mobile=0`. Если `error` — откатить копиями из Step 1 и разбираться.

- [ ] **Step 5: Удалить пробную папку**

```bash
ssh my-server 'rm -rf /tmp/night_2025_probe'
```

---

### Task 2: Каркас проекта + чтение дневного ряда (`server/series.py`)

**Files:**
- Create: `.gitignore` (дополнить), `server/__init__.py`, `tests/__init__.py`, `server/series.py`, `tests/test_series.py`, `tests/fixtures/day_z.csv`, `tests/fixtures/night_sell.csv`, `tests/fixtures/sync_dump.json`

**Interfaces:**
- Produces:
  - `DayValue(day: float, night: float, complete: bool)` с `.total`
  - `read_day_z(path: Path) -> Dict[date, float]` — выручка дневных касс по дате закрытия смены: `incomeSumm − refundIncomeSumm`
  - `read_night_sell(path: Path) -> Dict[date, float]` — ночная касса по `receiptDate`, дедуп по `(rqId, fiscalDocumentNumber, requestNumber)`, возвраты (`operationType` 2/3) со знаком минус
  - `read_sync_dump(path: Path) -> Tuple[Dict[date, DayValue], Optional[datetime]]` — ряд из дампа sync-скрипта + его `updated_at`
  - `merge_series(day, night, dump) -> Dict[date, DayValue]` — база из CSV, поверх — дамп

Форматы входа проверены на реальных файлах сервера 11.09.2026:
- `ofd_z.csv`: колонки `shiftCloseDate` (`2025-01-01 20:49:00.0`), `incomeSumm`, `refundIncomeSumm`, `kktName`.
- `ofd_sell.csv`: **одна строка на позицию чека**, `totalSum` чека повторяется в каждой строке → обязателен дедуп по чеку. Колонки `rqId, fiscalDocumentNumber, requestNumber, receiptDate (2026-07-26T13:59:00), totalSum, operationType`.

- [ ] **Step 1: Каркас**

```bash
cd /Users/vet/Claude/projects/paaso-dashboard
printf ".superpowers/\n__pycache__/\n*.pyc\n.DS_Store\n" > .gitignore
mkdir -p server tests/fixtures
touch server/__init__.py tests/__init__.py
```

- [ ] **Step 2: Фикстуры**

`tests/fixtures/day_z.csv`:
```csv
branchId,shiftNumber,shiftOpenDate,shiftCloseDate,incomeCount,incomeSumm,refundIncomeSumm,kktName
0,1,2026-09-10 09:00:00.0,2026-09-10 20:00:00.0,10,100000.00,0.00,Городище Паасо
0,2,2026-09-10 09:10:00.0,2026-09-10 20:10:00.0,5,50000.00,1000.00,Билетная касса
0,3,2025-09-11 09:00:00.0,2025-09-11 20:00:00.0,7,70000.00,0.00,Городище Паасо
0,4,2026-09-11 09:00:00.0,2026-09-11 13:00:00.0,3,30000.00,0.00,Городище Паасо
```

`tests/fixtures/night_sell.csv` (чек A из двух позиций, чек B — возврат):
```csv
rqId,kktName,shiftNumber,receiptDate,operator,requestNumber,totalSum,cashTotalSum,ecashTotalSum,fiscalDocumentNumber,operationType,name,quantity,price,sum
A,Терминал,,2026-09-10T22:15:00,,,1600.00,0.00,1600.00,1,1,билет,2,800.00,1600.00
A,Терминал,,2026-09-10T22:15:00,,,1600.00,0.00,1600.00,1,1,сувенир,1,0.00,0.00
B,Терминал,,2026-09-10T23:00:00,,,500.00,0.00,500.00,2,2,билет,1,500.00,500.00
C,Терминал,,2025-09-11T22:00:00,,,900.00,0.00,900.00,3,1,билет,1,900.00,900.00
```

`tests/fixtures/sync_dump.json`:
```json
{"updated_at": "2026-09-11T22:50:39+03:00",
 "days": {"2026-09-10": {"day": 149000, "night": 1100, "complete": true},
          "2026-09-11": {"day": 241050, "night": 2300, "complete": false}}}
```

- [ ] **Step 3: Падающие тесты**

`tests/test_series.py`:
```python
from __future__ import annotations
import datetime as dt
import unittest
from pathlib import Path

from server.series import DayValue, merge_series, read_day_z, read_night_sell, read_sync_dump

FX = Path(__file__).parent / "fixtures"


class ReadDayZ(unittest.TestCase):
    def test_sums_income_minus_refund_by_close_date(self):
        s = read_day_z(FX / "day_z.csv")
        self.assertEqual(s[dt.date(2026, 9, 10)], 149000.0)   # 100000 + (50000-1000)
        self.assertEqual(s[dt.date(2025, 9, 11)], 70000.0)
        self.assertEqual(s[dt.date(2026, 9, 11)], 30000.0)

    def test_missing_file_gives_empty(self):
        self.assertEqual(read_day_z(FX / "nope.csv"), {})


class ReadNightSell(unittest.TestCase):
    def test_dedups_receipt_positions_and_subtracts_refunds(self):
        s = read_night_sell(FX / "night_sell.csv")
        self.assertEqual(s[dt.date(2026, 9, 10)], 1100.0)      # 1600 (один раз) - 500
        self.assertEqual(s[dt.date(2025, 9, 11)], 900.0)


class ReadSyncDump(unittest.TestCase):
    def test_reads_days_and_updated_at(self):
        days, updated = read_sync_dump(FX / "sync_dump.json")
        self.assertEqual(days[dt.date(2026, 9, 11)], DayValue(241050, 2300, False))
        self.assertEqual(updated, dt.datetime.fromisoformat("2026-09-11T22:50:39+03:00"))

    def test_missing_dump(self):
        days, updated = read_sync_dump(FX / "nope.json")
        self.assertEqual(days, {})
        self.assertIsNone(updated)


class Merge(unittest.TestCase):
    def test_dump_overrides_csv_for_same_date(self):
        day = read_day_z(FX / "day_z.csv")
        night = read_night_sell(FX / "night_sell.csv")
        dump, _ = read_sync_dump(FX / "sync_dump.json")
        s = merge_series(day, night, dump)
        self.assertEqual(s[dt.date(2025, 9, 11)], DayValue(70000.0, 900.0, True))   # только CSV
        self.assertEqual(s[dt.date(2026, 9, 11)], DayValue(241050, 2300, False))    # дамп важнее
        self.assertAlmostEqual(s[dt.date(2026, 9, 11)].total, 243350)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Убедиться, что тесты падают**

```bash
cd /Users/vet/Claude/projects/paaso-dashboard && python3 -m unittest tests.test_series -v 2>&1 | tail -5
```
Ожидаемо: `ModuleNotFoundError: No module named 'server.series'`.

- [ ] **Step 5: Реализация `server/series.py`**

```python
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
```

- [ ] **Step 6: Тесты зелёные**

```bash
python3 -m unittest tests.test_series -v 2>&1 | tail -3
```
Ожидаемо: `OK` (7 тестов).

- [ ] **Step 7: Коммит**

```bash
git add .gitignore server tests
git -c user.name="Виталий" -c user.email="valaam.vet@gmail.com" commit -q -m "series: чтение дневного ряда из Z-отчётов, ночных чеков и дампа sync

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Расчёт метрик (`server/metrics.py`)

**Files:**
- Create: `server/metrics.py`, `tests/test_metrics.py`

**Interfaces:**
- Consumes: `DayValue`, `Dict[date, DayValue]` из Task 2.
- Produces (все суммы — `int`, проценты — `Optional[int]`):
  - `pct(cur: float, prev: float) -> Optional[int]`
  - `sum_range(series, start: date, end: date) -> float` (включительно)
  - `has_data(series, start, end) -> bool`
  - `same_date_prev_year(d: date) -> date` (29 фев → 28 фев)
  - `today_block(series, today) -> dict` — ключи `date, value, prev_date, prev, pct, complete`
  - `week7_block(series, today) -> dict` — `from, to, value, prev, pct, avg_day, prev_avg_day`
  - `mtd_block(series, today) -> dict` — `from, to, value, prev, pct`
  - `prev_month_block(series, today) -> dict` — `month ("YYYY-MM"), value, prev, pct`
  - `ytd_block(series, today) -> dict` — `from, to, value, prev, pct`
  - `months_block(series, today) -> list[dict]` — 12 × `{m, cur, prev, pct}`; `cur=None` для месяцев после текущего
  - `build_payload(series, today, generated_at: datetime, warnings: list[str]) -> dict` — итоговый `data.json` со структурой из спеки (`objects.p1.*`)

- [ ] **Step 1: Падающие тесты**

`tests/test_metrics.py`:
```python
from __future__ import annotations
import datetime as dt
import unittest

from server.series import DayValue
from server.metrics import (
    build_payload, months_block, mtd_block, pct, prev_month_block,
    same_date_prev_year, sum_range, today_block, week7_block, ytd_block,
)

D = dt.date


def flat(start: D, end: D, value: float) -> dict:
    """Ряд с одинаковой выручкой каждый день (только дневная касса)."""
    out, d = {}, start
    while d <= end:
        out[d] = DayValue(value, 0.0, True)
        d += dt.timedelta(days=1)
    return out


class Pct(unittest.TestCase):
    def test_growth_and_fall(self):
        self.assertEqual(pct(115, 100), 15)
        self.assertEqual(pct(85, 100), -15)

    def test_prev_zero_or_negative_is_none(self):
        self.assertIsNone(pct(100, 0))
        self.assertIsNone(pct(100, -5))

    def test_rounds_half_away_from_zero_like_humans_expect(self):
        self.assertEqual(pct(1125, 1000), 13)   # 12.5 → 13
        self.assertEqual(pct(875, 1000), -13)   # -12.5 → -13


class Ranges(unittest.TestCase):
    def test_sum_range_inclusive(self):
        s = flat(D(2026, 9, 1), D(2026, 9, 10), 10)
        self.assertEqual(sum_range(s, D(2026, 9, 1), D(2026, 9, 3)), 30)

    def test_same_date_prev_year_leap(self):
        self.assertEqual(same_date_prev_year(D(2028, 2, 29)), D(2027, 2, 28))
        self.assertEqual(same_date_prev_year(D(2026, 9, 11)), D(2025, 9, 11))


class Today(unittest.TestCase):
    def test_compares_with_364_days_back(self):
        s = flat(D(2025, 9, 1), D(2026, 9, 11), 100)
        s[D(2026, 9, 11)] = DayValue(90, 0, False)
        s[D(2025, 9, 12)] = DayValue(100, 0, True)   # четверг 12.09.2025 = 11.09.2026 − 364
        b = today_block(s, D(2026, 9, 11))
        self.assertEqual(b["date"], "2026-09-11")
        self.assertEqual(b["prev_date"], "2025-09-12")
        self.assertEqual((b["value"], b["prev"], b["pct"], b["complete"]), (90, 100, -10, False))

    def test_no_data_today_is_zero_and_complete_false(self):
        s = flat(D(2025, 9, 1), D(2026, 9, 10), 100)
        b = today_block(s, D(2026, 9, 11))
        self.assertEqual(b["value"], 0)
        self.assertFalse(b["complete"])


class Week7(unittest.TestCase):
    def test_seven_full_days_before_today(self):
        s = flat(D(2025, 8, 1), D(2026, 9, 11), 100)
        for i in range(1, 8):
            s[D(2026, 9, 11) - dt.timedelta(days=i)] = DayValue(200, 0, True)
        b = week7_block(s, D(2026, 9, 11))
        self.assertEqual((b["from"], b["to"]), ("2026-09-04", "2026-09-10"))
        self.assertEqual(b["value"], 1400)
        self.assertEqual(b["prev"], 700)          # 2025-09-05 … 2025-09-11 по 100
        self.assertEqual(b["pct"], 100)
        self.assertEqual((b["avg_day"], b["prev_avg_day"]), (200, 100))


class MonthYear(unittest.TestCase):
    def setUp(self):
        self.s = flat(D(2025, 1, 1), D(2026, 9, 11), 100)
        for d in list(self.s):
            if d.year == 2025:
                self.s[d] = DayValue(80, 0, True)

    def test_mtd_calendar_dates(self):
        b = mtd_block(self.s, D(2026, 9, 11))
        self.assertEqual((b["from"], b["to"]), ("2026-09-01", "2026-09-11"))
        self.assertEqual((b["value"], b["prev"], b["pct"]), (1100, 880, 25))

    def test_prev_month_full(self):
        b = prev_month_block(self.s, D(2026, 9, 11))
        self.assertEqual(b["month"], "2026-08")
        self.assertEqual((b["value"], b["prev"], b["pct"]), (3100, 2480, 25))

    def test_prev_month_in_january_is_december_last_year(self):
        b = prev_month_block(self.s, D(2026, 1, 15))
        self.assertEqual(b["month"], "2025-12")
        self.assertEqual(b["value"], 31 * 80)
        self.assertIsNone(b["pct"])              # 2024 данных нет

    def test_ytd(self):
        b = ytd_block(self.s, D(2026, 9, 11))
        self.assertEqual((b["from"], b["to"]), ("2026-01-01", "2026-09-11"))
        self.assertEqual(b["value"], 254 * 100)
        self.assertEqual(b["prev"], 254 * 80)
        self.assertEqual(b["pct"], 25)

    def test_months_block_future_is_none(self):
        ms = months_block(self.s, D(2026, 9, 11))
        self.assertEqual(len(ms), 12)
        self.assertEqual(ms[0], {"m": 1, "cur": 3100, "prev": 2480, "pct": 25})
        self.assertEqual(ms[8]["cur"], 1100)     # сентябрь — в моменте
        self.assertIsNone(ms[9]["cur"])          # октябрь ещё не наступил
        self.assertEqual(ms[9]["prev"], 31 * 80)
        self.assertIsNone(ms[9]["pct"])


class Payload(unittest.TestCase):
    def test_shape(self):
        s = flat(D(2025, 1, 1), D(2026, 9, 11), 100)
        gen = dt.datetime(2026, 9, 11, 22, 50, 39, tzinfo=dt.timezone(dt.timedelta(hours=3)))
        p = build_payload(s, D(2026, 9, 11), gen, ["night_fetch_failed"])
        self.assertEqual(p["generated_at"], "2026-09-11T22:50:39+03:00")
        self.assertEqual(set(p["objects"]), {"p1"})
        o = p["objects"]["p1"]
        self.assertEqual(set(o), {"today", "week7", "mtd", "prev_month", "ytd", "months", "warnings"})
        self.assertEqual(o["warnings"], ["night_fetch_failed"])
        self.assertIsInstance(o["today"]["value"], int)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Убедиться, что падают**

```bash
python3 -m unittest tests.test_metrics 2>&1 | tail -3
```
Ожидаемо: `ModuleNotFoundError: No module named 'server.metrics'`.

- [ ] **Step 3: Реализация `server/metrics.py`**

```python
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


def build_payload(series: Series, today: dt.date, generated_at: dt.datetime, warnings: List[str]) -> dict:
    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "objects": {
            "p1": {
                "today": today_block(series, today),
                "week7": week7_block(series, today),
                "mtd": mtd_block(series, today),
                "prev_month": prev_month_block(series, today),
                "ytd": ytd_block(series, today),
                "months": months_block(series, today),
                "warnings": list(warnings),
            }
        },
    }
```

- [ ] **Step 4: Тесты зелёные**

```bash
python3 -m unittest tests.test_metrics -v 2>&1 | tail -3
```
Ожидаемо: `OK` (14 тестов). Если падает `test_ytd` на числе дней — 1 января–11 сентября 2026 = 254 дня (2026 не високосный), проверить `flat`.

- [ ] **Step 5: Коммит**

```bash
git add server/metrics.py tests/test_metrics.py
git -c user.name="Виталий" -c user.email="valaam.vet@gmail.com" commit -q -m "metrics: сегодня/7 дней/месяц/год в моменте, прошлый месяц, 12 месяцев с процентами

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: CLI `server/build_dashboard_data.py`

**Files:**
- Create: `server/build_dashboard_data.py`, `tests/test_build.py`

**Interfaces:**
- Consumes: Task 2 (`read_*`, `merge_series`), Task 3 (`build_payload`).
- Produces: команда
  ```
  python3 -m server.build_dashboard_data --day-z PATH --night-sell PATH --sync-dump PATH --out PATH
         [--today YYYY-MM-DD] [--night-fetch-status N] [--max-dump-age-min 60]
  ```
  пишет `data.json` атомарно (через `.tmp` + `replace`), печатает краткий JSON-отчёт, код возврата 0. Предупреждения в `objects.p1.warnings`:
  - `night_fetch_failed` — если `--night-fetch-status != 0` (тогда `today.complete = false`)
  - `sync_dump_missing` — дампа нет (сегодняшний день будет только из Z-отчётов = 0 до закрытия смены)
  - `sync_dump_stale` — дамп старше `--max-dump-age-min`
  - `today_incomplete` — `today.complete == false` по любой причине

- [ ] **Step 1: Падающий тест**

`tests/test_build.py`:
```python
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
```

- [ ] **Step 2: Убедиться, что падает**

```bash
python3 -m unittest tests.test_build 2>&1 | tail -3
```
Ожидаемо: `No module named server.build_dashboard_data`.

- [ ] **Step 3: Реализация**

`server/build_dashboard_data.py`:
```python
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
```

- [ ] **Step 4: Все тесты зелёные**

```bash
python3 -m unittest discover -s tests -v 2>&1 | tail -3
```
Ожидаемо: `OK` (24 теста).

- [ ] **Step 5: Коммит**

```bash
git add server/build_dashboard_data.py tests/test_build.py
git -c user.name="Виталий" -c user.email="valaam.vet@gmail.com" commit -q -m "build: CLI собирает data.json из локальных файлов, предупреждения о неполных данных

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Страница `index.html` + стартовый `data.json`

**Files:**
- Create: `index.html`, `data.json` (образец), `robots.txt`, `.nojekyll`

**Interfaces:**
- Consumes: формат `data.json` из Task 3/4 (`objects.p1.{today,week7,mtd,prev_month,ytd,months,warnings}`, `generated_at`).
- Produces: статическая страница; переключатель объектов читает `objects[code]`; коды → названия в константе `OBJECTS` внутри страницы.

- [ ] **Step 1: Стартовый `data.json` из фикстур (чтобы страница не была пустой до первого прогона сервера)**

```bash
cd /Users/vet/Claude/projects/paaso-dashboard
python3 -m server.build_dashboard_data --day-z tests/fixtures/day_z.csv --night-sell tests/fixtures/night_sell.csv --sync-dump tests/fixtures/sync_dump.json --out data.json --today 2026-09-11 --max-dump-age-min 999999
printf 'User-agent: *\nDisallow: /\n' > robots.txt
touch .nojekyll
```

- [ ] **Step 2: Написать `index.html`**

```html
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Выручка</title>
<style>
  :root{
    --bg:#0f1419; --card:#161c23; --line:#232b35; --text:#e6edf3; --muted:#8b98a8;
    --cur:#3b82f6; --prev:#3a4654; --up:#34d399; --dn:#f87171; --warn:#f59e0b;
  }
  *{box-sizing:border-box}
  html,body{margin:0;background:var(--bg);color:var(--text);
    font:15px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif;
    font-variant-numeric:tabular-nums}
  .wrap{max-width:1100px;margin:0 auto;padding:16px}
  header{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:10px}
  h1{font-size:20px;margin:0;font-weight:800}
  #updated{color:var(--muted);font-size:12px;white-space:nowrap}
  .chips{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
  .chip{padding:6px 14px;border-radius:999px;border:1px solid var(--line);color:var(--muted);font-size:13px;background:none;cursor:pointer}
  .chip.on{background:var(--cur);border-color:var(--cur);color:#fff;font-weight:700}
  .chip:disabled{cursor:default;opacity:.5}
  .banner{display:none;background:rgba(245,158,11,.12);border:1px solid var(--warn);color:#fcd34d;
    border-radius:10px;padding:10px 12px;font-size:13px;margin-bottom:12px}
  .banner.show{display:block}
  .tiles{display:grid;grid-template-columns:1.5fr 1fr;gap:10px;margin-bottom:10px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
  .l{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
  .v{font-size:26px;font-weight:800;margin-top:4px;line-height:1.1}
  .sub{font-size:12px;color:var(--muted);margin-top:4px}
  .up{color:var(--up)} .dn{color:var(--dn)} .na{color:var(--muted)}
  .blocks{display:grid;grid-template-columns:1fr;gap:10px;margin-bottom:10px}
  .cmp{display:flex;gap:14px;align-items:center}
  .pair{flex:1;min-width:0}
  .row{display:flex;justify-content:space-between;font-size:13px;color:var(--muted)}
  .row b{color:var(--text);font-weight:600}
  .bar{height:10px;border-radius:5px;margin:4px 0 10px;background:var(--prev)}
  .bar.cur{background:var(--cur)}
  .big{font-size:26px;font-weight:800;min-width:84px;text-align:right}
  .t{display:flex;justify-content:space-between;margin-bottom:8px}
  .t span:last-child{color:var(--muted);font-size:12px}
  .chart{display:grid;grid-template-columns:repeat(12,1fr);gap:4px;align-items:end;height:150px;margin-top:6px}
  .m{display:flex;gap:2px;align-items:flex-end;height:100%}
  .m i{flex:1;display:block;border-radius:3px 3px 0 0;background:var(--cur);min-height:0}
  .m i.p{background:var(--prev)}
  .axis,.pcts{display:grid;grid-template-columns:repeat(12,1fr);gap:4px;font-size:11px;text-align:center;margin-top:4px}
  .axis{color:var(--muted)}
  .legend{display:flex;gap:14px;font-size:12px;color:var(--muted);margin-top:8px}
  .legend b{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
  footer{color:var(--muted);font-size:12px;text-align:center;margin:18px 0 8px}
  @media (min-width:800px){
    .tiles{grid-template-columns:2fr 1fr 1fr}
    .blocks{grid-template-columns:1fr 1fr 1fr}
    .v,.big{font-size:30px}
    .chart{height:220px}
  }
  @media (max-width:799px){ #tile-avg{display:none} }
</style>
</head>
<body>
<div class="wrap">
  <header><h1 id="title">Выручка</h1><div id="updated">загрузка…</div></header>
  <div class="chips" id="chips"></div>
  <div class="banner" id="banner"></div>

  <section class="tiles">
    <div class="card"><div class="l" id="today-l">Сегодня</div><div class="v" id="today-v">—</div><div class="sub" id="today-s"></div></div>
    <div class="card"><div class="l">7 дней</div><div class="v" id="week-v">—</div><div class="sub" id="week-s"></div></div>
    <div class="card" id="tile-avg"><div class="l">Средний день, 7 дн.</div><div class="v" id="avg-v">—</div><div class="sub" id="avg-s"></div></div>
  </section>

  <section class="blocks">
    <div class="card" id="blk-mtd"></div>
    <div class="card" id="blk-pm"></div>
    <div class="card" id="blk-ytd"></div>
  </section>

  <section class="card">
    <div class="t"><span>По месяцам</span><span id="months-years"></span></div>
    <div class="chart" id="chart"></div>
    <div class="axis">
      <span>янв</span><span>фев</span><span>мар</span><span>апр</span><span>май</span><span>июн</span>
      <span>июл</span><span>авг</span><span>сен</span><span>окт</span><span>ноя</span><span>дек</span>
    </div>
    <div class="pcts" id="pcts"></div>
    <div class="legend" id="legend"></div>
  </section>

  <footer>Данные: кассы ОФД · обновляется каждые 15 мин</footer>
</div>

<script>
(function () {
  // Код объекта в data.json → как показывать. Понятные названия живут только здесь.
  const OBJECTS = [
    { code: 'p1', name: 'Паасо', active: true },
    { code: 'w1', name: 'Водопады', active: false },
    { code: 'all', name: 'Всё', active: false },
  ];
  const MONTHS_GEN = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];
  const MONTHS_NOM = ['январь','февраль','март','апрель','май','июнь','июль','август','сентябрь','октябрь','ноябрь','декабрь'];
  const WEEKDAYS = ['вс','пн','вт','ср','чт','пт','сб'];
  const STALE_MIN = 60;
  let current = 'p1';
  let data = null;

  const $ = (id) => document.getElementById(id);
  const fmt = (n) => (n === null || n === undefined) ? '—' : Math.round(n).toLocaleString('ru-RU') + ' ₽';
  const short = (n) => {
    if (n === null || n === undefined) return '—';
    if (Math.abs(n) >= 1e6) return (n / 1e6).toLocaleString('ru-RU', { maximumFractionDigits: 1 }) + ' млн';
    if (Math.abs(n) >= 1e3) return Math.round(n / 1e3).toLocaleString('ru-RU') + ' тыс.';
    return Math.round(n).toLocaleString('ru-RU');
  };
  const pctHtml = (p) => {
    if (p === null || p === undefined) return '<span class="na">—</span>';
    if (p > 0) return `<span class="up">▲ ${p}%</span>`;
    if (p < 0) return `<span class="dn">▼ ${Math.abs(p)}%</span>`;
    return '<span class="na">0%</span>';
  };
  const d = (iso) => { const [y, m, dd] = iso.split('-').map(Number); return new Date(y, m - 1, dd); };
  const dayLabel = (iso) => { const x = d(iso); return `${WEEKDAYS[x.getDay()]}, ${x.getDate()} ${MONTHS_GEN[x.getMonth()]}`; };
  const rangeLabel = (a, b) => { const x = d(a), y = d(b);
    return x.getMonth() === y.getMonth() ? `${x.getDate()}–${y.getDate()} ${MONTHS_GEN[y.getMonth()]}`
      : `${x.getDate()} ${MONTHS_GEN[x.getMonth()]} – ${y.getDate()} ${MONTHS_GEN[y.getMonth()]}`; };

  function cmpBlock(title, range, b, prevLabel) {
    const max = Math.max(b.value || 0, b.prev || 0, 1);
    const w = (v) => (v === null || v === undefined) ? 0 : Math.max(2, Math.round(v / max * 100));
    const prevRow = (b.prev === null || b.prev === undefined)
      ? `<div class="row"><span>${prevLabel}</span><b class="na">нет данных</b></div>`
      : `<div class="row"><span>${prevLabel}</span><b>${short(b.prev)}</b></div><div class="bar" style="width:${w(b.prev)}%"></div>`;
    return `<div class="t"><span>${title}</span><span>${range}</span></div>
      <div class="cmp"><div class="pair">
        <div class="row"><span>${new Date().getFullYear()}</span><b>${short(b.value)}</b></div><div class="bar cur" style="width:${w(b.value)}%"></div>
        ${prevRow}
      </div><div class="big">${pctHtml(b.pct)}</div></div>`;
  }

  function render() {
    const o = data && data.objects && data.objects[current];
    if (!o) { $('banner').textContent = 'Нет данных по этому объекту'; $('banner').classList.add('show'); return; }
    const year = d(o.today.date).getFullYear(), prevYear = year - 1;
    const name = OBJECTS.find(x => x.code === current).name;
    $('title').textContent = 'Выручка · ' + name;
    document.title = 'Выручка · ' + name;

    // сегодня / 7 дней / средний день
    $('today-l').textContent = 'Сегодня · ' + dayLabel(o.today.date);
    $('today-v').textContent = fmt(o.today.value);
    $('today-s').innerHTML = `${pctHtml(o.today.pct)} к ${dayLabel(o.today.prev_date)} ${prevYear}` + (o.today.complete ? '' : ' <span class="dn">⚠</span>');
    $('week-v').textContent = short(o.week7.value);
    $('week-s').innerHTML = `${pctHtml(o.week7.pct)} к тем же дням ${prevYear} · ${rangeLabel(o.week7.from, o.week7.to)}`;
    $('avg-v').textContent = short(o.week7.avg_day);
    $('avg-s').textContent = o.week7.prev_avg_day === null ? '' : `в ${prevYear} — ${short(o.week7.prev_avg_day)}`;

    // три сравнения
    $('blk-mtd').innerHTML = cmpBlock('Месяц в моменте', rangeLabel(o.mtd.from, o.mtd.to), o.mtd, String(prevYear));
    const pm = o.prev_month.month.split('-'); const pmName = MONTHS_NOM[Number(pm[1]) - 1];
    $('blk-pm').innerHTML = cmpBlock('Прошлый месяц', pmName, o.prev_month, `${pmName} ${Number(pm[0]) - 1}`);
    $('blk-ytd').innerHTML = cmpBlock('Год в моменте', rangeLabel(o.ytd.from, o.ytd.to), o.ytd, String(prevYear));

    // по месяцам
    $('months-years').textContent = `${year} / ${prevYear} · % год к году`;
    const max = Math.max(1, ...o.months.flatMap(m => [m.cur || 0, m.prev || 0]));
    $('chart').innerHTML = o.months.map(m => {
      const h = (v) => (v === null || v === undefined) ? 0 : Math.max(v > 0 ? 1 : 0, Math.round(v / max * 100));
      return `<div class="m" title="${MONTHS_NOM[m.m - 1]}: ${fmt(m.cur)} / ${fmt(m.prev)}"><i style="height:${h(m.cur)}%"></i><i class="p" style="height:${h(m.prev)}%"></i></div>`;
    }).join('');
    $('pcts').innerHTML = o.months.map(m => pctHtml(m.pct)).join('');
    $('legend').innerHTML = `<span><b style="background:var(--cur)"></b>${year}</span><span><b style="background:var(--prev)"></b>${prevYear}</span>`;

    // время обновления и плашки
    const gen = new Date(data.generated_at);
    $('updated').textContent = 'обновлено ' + gen.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) + ' · ' + gen.getDate() + ' ' + MONTHS_GEN[gen.getMonth()];
    const msgs = [];
    const ageMin = (Date.now() - gen.getTime()) / 60000;
    if (ageMin > STALE_MIN) msgs.push('данные не обновлялись с ' + gen.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) + ' — цифры за сегодня могут отставать');
    if (!o.today.complete) msgs.push('данные за сегодня могут быть неполными (одна из касс не ответила)');
    $('banner').textContent = msgs.join(' · ');
    $('banner').classList.toggle('show', msgs.length > 0);
  }

  function renderChips() {
    $('chips').innerHTML = OBJECTS.map(x =>
      `<button class="chip${x.code === current ? ' on' : ''}" data-code="${x.code}" ${x.active ? '' : 'disabled title="скоро"'}>${x.name}</button>`).join('');
    $('chips').querySelectorAll('button:not(:disabled)').forEach(b => b.onclick = () => { current = b.dataset.code; renderChips(); render(); });
  }

  async function load() {
    try {
      const r = await fetch('data.json?t=' + Date.now(), { cache: 'no-store' });
      if (!r.ok) throw new Error(r.status);
      data = await r.json();
      render();
    } catch (e) {
      $('updated').textContent = 'нет связи с данными';
      $('banner').textContent = 'Не удалось загрузить data.json — попробуй обновить страницу';
      $('banner').classList.add('show');
    }
  }

  renderChips();
  load();
  setInterval(load, 5 * 60 * 1000);
})();
</script>
</body>
</html>
```

- [ ] **Step 3: Локальная проверка страницы**

```bash
cd /Users/vet/Claude/projects/paaso-dashboard && (python3 -m http.server 8765 >/dev/null 2>&1 &) && sleep 1 && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8765/ && curl -s http://localhost:8765/data.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('generated_at:', d['generated_at'], '| today:', d['objects']['p1']['today']['value'])"
```
Ожидаемо: `200` и строка с `today: 243350`.

Затем открыть `http://localhost:8765/` в браузере (или через Playwright MCP: `browser_navigate` → `browser_take_screenshot`, размер 390×844 и 1280×800) и сверить с утверждёнными макетами: тёмный фон, плитки, три блока с полосами и процентом, график по месяцам с процентами, переключатель (Водопады/Всё неактивны), плашка «данные за сегодня могут быть неполными» (в фикстуре `complete: false`) и, поскольку `generated_at` в фикстуре старый, — плашка «данные не обновлялись с …». Убить сервер: `pkill -f "http.server 8765"`.

- [ ] **Step 4: Коммит**

```bash
git add index.html data.json robots.txt .nojekyll
git -c user.name="Виталий" -c user.email="valaam.vet@gmail.com" commit -q -m "page: дашборд выручки — плитки, три сравнения, график по месяцам, плашки

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Публикация (`server/publish.sh`) и дамп дневного ряда из sync-скрипта (сервер)

**Files:**
- Create: `server/publish.sh`, `server/patches/sync_daily_series_dump.md`
- Modify (сервер): `/root/.openclaw/workspace/tools/revenue/sync_paaso_revenue_google_sheet.py` — после строки `daily, monthly, yearly = build_tables(...)` (в `main()`), плюс новый аргумент и функция.

**Interfaces:**
- Produces:
  - `revenue_sources/paaso_daily_series.json` — `{"updated_at": ISO, "days": {"YYYY-MM-DD": {"day": int, "night": int, "complete": bool}}}` за 2026+ (то, что уходит в таблицу). Читается `read_sync_dump` (Task 2).
  - `server/publish.sh [SRC]` — копирует `SRC` (по умолчанию `revenue_sources/dashboard_data.json`) в `/root/dashboard-pub/data.json`, коммитит и пушит, если изменился. Коды: 0 ок/без изменений, 2 pull не удался, 3 push не удался.

- [ ] **Step 1: `server/publish.sh`**

```bash
#!/usr/bin/env bash
# Публикует data.json дашборда в GitHub Pages (репозиторий dashboard, клон /root/dashboard-pub).
# Вызывается из hourly_update_paaso_revenue_summary.sh после сборки data.json.
set -uo pipefail
REPO="${DASHBOARD_REPO:-/root/dashboard-pub}"
SRC="${1:-/root/.openclaw/workspace/revenue_sources/dashboard_data.json}"
export GIT_AUTHOR_NAME="revenue-bot" GIT_AUTHOR_EMAIL="valaam.vet@gmail.com"
export GIT_COMMITTER_NAME="revenue-bot" GIT_COMMITTER_EMAIL="valaam.vet@gmail.com"

[ -f "$SRC" ] || { echo "publish: нет файла $SRC"; exit 1; }
cd "$REPO" || { echo "publish: нет клона $REPO"; exit 1; }

# Подтянуть изменения страницы/скриптов с Мака; без сети — пробуем опубликовать локально накопленное.
if ! git pull --rebase -q origin main; then
  echo "publish: git pull не удался"; git rebase --abort 2>/dev/null; exit 2
fi

cp "$SRC" data.json
if git diff --quiet -- data.json && ! git log origin/main..main --oneline | grep -q .; then
  echo "publish: data.json не изменился"; exit 0
fi
git add data.json
git diff --cached --quiet || git commit -q -m "data: $(date '+%Y-%m-%d %H:%M')"
if ! git push -q origin main; then
  echo "publish: git push не удался"; exit 3
fi
echo "publish: ok $(date '+%H:%M')"
```
```bash
chmod +x server/publish.sh
```

- [ ] **Step 2: Описание патча sync-скрипта (кладём в репозиторий, чтобы не потерять)**

`server/patches/sync_daily_series_dump.md`:
````markdown
# Патч: дамп дневного ряда из sync_paaso_revenue_google_sheet.py

Файл на сервере: `/root/.openclaw/workspace/tools/revenue/sync_paaso_revenue_google_sheet.py`.
Цель: дашборд показывает те же цифры, что Google-таблица, включая сегодняшний день из API.

1. Новый аргумент в `main()` (рядом с `--format`):
```python
    parser.add_argument("--daily-series-dump", default="revenue_sources/paaso_daily_series.json",
                        help="Локальный JSON с дневным рядом Паасо для дашборда")
```
2. Новая функция (перед `def main()`):
```python
def write_daily_series_dump(path: Path, paaso_day_cash: dict, paaso_night_cash: dict, today_complete: bool) -> None:
    """Локальный дамп дневного ряда Паасо (для дашборда). Ошибка здесь не должна ломать синхронизацию."""
    msk = dt.timezone(dt.timedelta(hours=3))
    today = dt.datetime.now(msk).date()
    days = {}
    for day in sorted(set(paaso_day_cash) | set(paaso_night_cash)):
        days[day.isoformat()] = {
            "day": round(paaso_day_cash.get(day, 0.0)),
            "night": round(paaso_night_cash.get(day, 0.0)),
            "complete": True if day != today else bool(today_complete),
        }
    payload = {"updated_at": dt.datetime.now(msk).isoformat(timespec="seconds"), "days": days}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
```
3. Вызов в `main()` сразу после `daily, monthly, yearly = build_tables(...)`:
```python
    try:
        write_daily_series_dump(Path(args.daily_series_dump), paaso_day_cash, paaso_night_cash,
                                today_complete=paaso_day_today_stats is not None)
    except Exception as exc:
        print(f"WARNING: daily series dump failed: {exc}", file=sys.stderr)
```
`paaso_day_today_stats is None` ровно тогда, когда `update_paaso_day_today_from_api` упал и остался кэш.
````

- [ ] **Step 3: Применить патч на сервере**

```bash
ssh my-server 'cd /root/.openclaw/workspace && cp tools/revenue/sync_paaso_revenue_google_sheet.py /root/sync_paaso_before_dump_patch.py && python3 - <<'"'"'PY'"'"'
from pathlib import Path
p = Path("tools/revenue/sync_paaso_revenue_google_sheet.py")
s = p.read_text(encoding="utf-8")
assert "daily-series-dump" not in s, "уже пропатчен"
s = s.replace(
'    parser.add_argument("--format", action="store_true", help="Apply basic formatting after sync")\n',
'    parser.add_argument("--format", action="store_true", help="Apply basic formatting after sync")\n'
'    parser.add_argument("--daily-series-dump", default="revenue_sources/paaso_daily_series.json",\n'
'                        help="Локальный JSON с дневным рядом Паасо для дашборда")\n', 1)
func = \'\'\'
def write_daily_series_dump(path: Path, paaso_day_cash: dict, paaso_night_cash: dict, today_complete: bool) -> None:
    """Локальный дамп дневного ряда Паасо (для дашборда). Ошибка здесь не должна ломать синхронизацию."""
    msk = dt.timezone(dt.timedelta(hours=3))
    today = dt.datetime.now(msk).date()
    days = {}
    for day in sorted(set(paaso_day_cash) | set(paaso_night_cash)):
        days[day.isoformat()] = {
            "day": round(paaso_day_cash.get(day, 0.0)),
            "night": round(paaso_night_cash.get(day, 0.0)),
            "complete": True if day != today else bool(today_complete),
        }
    payload = {"updated_at": dt.datetime.now(msk).isoformat(timespec="seconds"), "days": days}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def main() -> int:
\'\'\'
s = s.replace("\ndef main() -> int:\n", func, 1)
call = \'\'\'    daily, monthly, yearly = build_tables(paaso_day_cash, paaso_night_cash, waterfalls_main_cash, waterfalls_second_cash)
    try:
        write_daily_series_dump(Path(args.daily_series_dump), paaso_day_cash, paaso_night_cash,
                                today_complete=paaso_day_today_stats is not None)
    except Exception as exc:
        print(f"WARNING: daily series dump failed: {exc}", file=sys.stderr)
\'\'\'
old = "    daily, monthly, yearly = build_tables(paaso_day_cash, paaso_night_cash, waterfalls_main_cash, waterfalls_second_cash)\n"
assert old in s
s = s.replace(old, call, 1)
p.write_text(s, encoding="utf-8")
print("patched")
PY
python3 -m py_compile tools/revenue/sync_paaso_revenue_google_sheet.py && echo compile-ok && grep -n "daily_series_dump\|daily-series-dump" tools/revenue/sync_paaso_revenue_google_sheet.py'
```
Ожидаемо: `patched`, `compile-ok`, 4–5 строк с упоминанием. Если `assert` сработал — вывести контекст и править вручную через `sed -n`.

- [ ] **Step 4: Дождаться ближайшего крона и проверить дамп**

После следующей отметки :05/:20/:35/:50 + 2 мин:
```bash
ssh my-server 'cd /root/.openclaw/workspace && cat revenue_sources/paaso_night_ofd_ru/logs/revenue_summary_status.env | head -3 && python3 -c "
import json; d=json.load(open(\"revenue_sources/paaso_daily_series.json\")); days=d[\"days\"]
print(\"updated_at:\", d[\"updated_at\"], \"| дней:\", len(days), \"| первый:\", min(days), \"| последний:\", max(days)); print(\"сегодня:\", days[max(days)])"'
```
Ожидаемо: `status=ok`; дней ≈ 254 (с 2026-01-01); `сегодня: {'day': ..., 'night': ..., 'complete': True}` и `day+night` совпадает с ячейкой «Паасо всего» за сегодня в Google-таблице (лист `📊 СВОДКА`, строка 3).

- [ ] **Step 5: Закоммитить серверное изменение в репозиторий `/root/.openclaw`**

```bash
ssh my-server 'cd /root/.openclaw && GIT_AUTHOR_NAME="Виталий" GIT_AUTHOR_EMAIL="valaam.vet@gmail.com" GIT_COMMITTER_NAME="Виталий" GIT_COMMITTER_EMAIL="valaam.vet@gmail.com" git add workspace/tools/revenue/sync_paaso_revenue_google_sheet.py && git -c user.name="Виталий" -c user.email="valaam.vet@gmail.com" commit -q -m "revenue: дамп дневного ряда Паасо для дашборда (paaso_daily_series.json)" && git log --oneline | head -1'
```

- [ ] **Step 6: Коммит на Маке**

```bash
git add server/publish.sh server/patches
git -c user.name="Виталий" -c user.email="valaam.vet@gmail.com" commit -q -m "publish: скрипт публикации data.json в GitHub Pages + описание патча sync

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Репозиторий GitHub, GitHub Pages, клон на сервере

**Files:**
- Create (GitHub): публичный репозиторий `valaamvet-creator/dashboard`
- Create (сервер): `/root/dashboard-pub`

**Interfaces:**
- Produces: `https://valaamvet-creator.github.io/dashboard/` отдаёт `index.html`; сервер может `git push` в `main`.

На Маке `gh` не установлен — репозиторий создаём через `gh` на сервере (там он авторизован под `valaamvet-creator`, SSH-ключ сервера добавлен в GitHub).

- [ ] **Step 1: Создать репозиторий**

```bash
ssh my-server 'gh repo create valaamvet-creator/dashboard --public --description "Revenue dashboard (static)" 2>&1 | tail -2'
```
Ожидаемо: `https://github.com/valaamvet-creator/dashboard`. Если «already exists» — идти дальше.

- [ ] **Step 2: Первый push с Мака**

Проверить, что SSH к GitHub с Мака работает: `ssh -T git@github.com 2>&1 | head -1` → «Hi valaamvet-creator!». Если нет — пушить через сервер (Step 2b).
```bash
cd /Users/vet/Claude/projects/paaso-dashboard
git branch -M main
git remote add origin git@github.com:valaamvet-creator/dashboard.git 2>/dev/null || git remote set-url origin git@github.com:valaamvet-creator/dashboard.git
git push -u origin main
```

Step 2b (если с Мака SSH к GitHub нет): `tar czf /tmp/dash.tgz -C /Users/vet/Claude/projects/paaso-dashboard . && scp /tmp/dash.tgz my-server:/tmp/ && ssh my-server 'rm -rf /root/dashboard-pub && mkdir -p /root/dashboard-pub && tar xzf /tmp/dash.tgz -C /root/dashboard-pub && cd /root/dashboard-pub && git remote remove origin 2>/dev/null; git remote add origin git@github.com:valaamvet-creator/dashboard.git && git branch -M main && git push -u origin main'` — и тогда Step 3 пропустить (клон уже есть).

- [ ] **Step 3: Клон на сервере**

```bash
ssh my-server 'test -d /root/dashboard-pub/.git || git clone -q git@github.com:valaamvet-creator/dashboard.git /root/dashboard-pub; cd /root/dashboard-pub && git log --oneline | head -1 && ls'
```
Ожидаемо: последний коммит и файлы `index.html data.json robots.txt server tests docs`.

- [ ] **Step 4: Включить GitHub Pages (ветка main, корень)**

```bash
ssh my-server 'gh api -X POST repos/valaamvet-creator/dashboard/pages -f "source[branch]=main" -f "source[path]=/" 2>&1 | head -3; sleep 5; gh api repos/valaamvet-creator/dashboard/pages --jq ".html_url, .status"'
```
Ожидаемо: `https://valaamvet-creator.github.io/dashboard/` и статус `building`/`built`. Если POST вернул 409 «already exists» — нормально.

- [ ] **Step 5: Дождаться публикации и проверить**

```bash
for i in $(seq 1 20); do code=$(curl -s -o /dev/null -w "%{http_code}" https://valaamvet-creator.github.io/dashboard/); echo "$i: $code"; [ "$code" = "200" ] && break; sleep 15; done; curl -s https://valaamvet-creator.github.io/dashboard/ | grep -o "<title>[^<]*" ; curl -s https://valaamvet-creator.github.io/dashboard/robots.txt
```
Ожидаемо: `200`, `<title>Выручка`, `Disallow: /`.

- [ ] **Step 6: Проверить публикацию с сервера вручную (без крона)**

```bash
ssh my-server 'cd /root/dashboard-pub && /usr/bin/python3 -m server.build_dashboard_data --out /root/.openclaw/workspace/revenue_sources/dashboard_data.json && bash server/publish.sh'
```
Ожидаемо: JSON-отчёт с `"ok": true`, `today_value` > 0 (если смена открыта), затем `publish: ok HH:MM`. Через 1–2 минуты `curl -s https://valaamvet-creator.github.io/dashboard/data.json | head -c 200` показывает свежий `generated_at`.

---

### Task 8: Встроить в 15-минутный крон

**Files:**
- Modify (сервер): `/root/.openclaw/workspace/tools/revenue/hourly_update_paaso_revenue_summary.sh` — перед строкой `echo "[$(date '+%Y-%m-%d %H:%M:%S')] done paaso revenue hourly update: …"`.

**Interfaces:**
- Consumes: `fetch_status` (переменная скрипта — статус ночной ОФД.ру), `/root/dashboard-pub/server/build_dashboard_data.py`, `/root/dashboard-pub/server/publish.sh`.
- Produces: строки в логе `dashboard build=N publish=N`; файл `revenue_sources/paaso_night_ofd_ru/logs/dashboard_status.env`. **Не влияет** на `write_status`/алерты таблицы.

- [ ] **Step 1: Бэкап и вставка**

```bash
ssh my-server 'cd /root/.openclaw/workspace && cp tools/revenue/hourly_update_paaso_revenue_summary.sh /root/hourly_update_before_dashboard.sh && python3 - <<'"'"'PY'"'"'
from pathlib import Path
p = Path("tools/revenue/hourly_update_paaso_revenue_summary.sh")
s = p.read_text(encoding="utf-8")
assert "dashboard build" not in s, "уже вставлено"
marker = "echo \"[$(date '+%Y-%m-%d %H:%M:%S')] done paaso revenue hourly update: fetch=$fetch_status sync=$sync_status mobile=$mobile_status\"\n"
assert marker in s
block = \'\'\'# --- Дашборд (GitHub Pages): собрать data.json и опубликовать. Ошибки не влияют на статус таблицы. ---
dash_build_status=0
dash_publish_status=0
if [ -d /root/dashboard-pub/server ]; then
  ( cd /root/dashboard-pub && timeout 120 /usr/bin/python3 -m server.build_dashboard_data \\
      --out /root/.openclaw/workspace/revenue_sources/dashboard_data.json \\
      --night-fetch-status "$fetch_status" )
  dash_build_status=$?
  if [ "$dash_build_status" -eq 0 ]; then
    timeout 120 bash /root/dashboard-pub/server/publish.sh
    dash_publish_status=$?
  fi
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] dashboard build=$dash_build_status publish=$dash_publish_status"
  {
    echo "updated_at=$(date '+%Y-%m-%d %H:%M:%S')"
    echo "build_status=$dash_build_status"
    echo "publish_status=$dash_publish_status"
  } > "${LOG_DIR}/dashboard_status.env"
fi
# --- конец дашборда ---

\'\'\'
s = s.replace(marker, block + marker, 1)
p.write_text(s, encoding="utf-8")
print("inserted")
PY
bash -n tools/revenue/hourly_update_paaso_revenue_summary.sh && echo syntax-ok'
```
Ожидаемо: `inserted`, `syntax-ok`.

- [ ] **Step 2: Дождаться крона и проверить**

После ближайшей отметки :05/:20/:35/:50 + 3 мин:
```bash
ssh my-server 'tail -4 /root/.openclaw/workspace/revenue_sources/paaso_night_ofd_ru/logs/hourly_update.log; cat /root/.openclaw/workspace/revenue_sources/paaso_night_ofd_ru/logs/dashboard_status.env; cat /root/.openclaw/workspace/revenue_sources/paaso_night_ofd_ru/logs/revenue_summary_status.env | head -2'
```
Ожидаемо: `dashboard build=0 publish=0`, `status=ok` у таблицы.

- [ ] **Step 3: Сверить сайт с таблицей**

```bash
curl -s "https://valaamvet-creator.github.io/dashboard/data.json?t=$(date +%s)" | python3 -c "
import json,sys; d=json.load(sys.stdin); o=d['objects']['p1']
print('generated_at:', d['generated_at']); print('сегодня:', o['today']); print('mtd:', o['mtd']); print('prev_month:', o['prev_month']); print('ytd:', o['ytd']); print('warnings:', o['warnings'])"
```
Сравнить с листом `📊 СВОДКА` Google-таблицы `1w4UB3vAmH1j7ZKArqIp0lAfG7MyPK4tl-prdR5iq1B0` (через `mcp__google-workspace__read_sheet_values`, диапазон `📊 СВОДКА!A1:L10`): «Паасо всего» за сегодня = `today.value`; месяц `2026-09` из блока «Выручка по месяцам» = `mtd.value`; `2026-08` = `prev_month.value` (**20 386 600** на 11.09.2026); годовой итог из `raw_years` = `ytd.value`.

- [ ] **Step 4: Коммит серверного скрипта**

```bash
ssh my-server 'cd /root/.openclaw && git add workspace/tools/revenue/hourly_update_paaso_revenue_summary.sh && git -c user.name="Виталий" -c user.email="valaam.vet@gmail.com" commit -q -m "revenue: публикация дашборда после обновления таблицы" && git log --oneline | head -1'
```

---

### Task 9: Контрольные суммы за 2025, README, заметка в память

**Files:**
- Create: `README.md`
- Modify: `~/.claude/projects/-Users-vet/memory/MEMORY.md` (+ новый файл `paaso-dashboard.md`)

- [ ] **Step 1: Контрольные суммы на реальных данных сервера**

```bash
ssh my-server 'cd /root/dashboard-pub && /usr/bin/python3 - <<PY
import datetime as dt
from pathlib import Path
from server.series import read_day_z, read_night_sell, read_sync_dump, merge_series
from server.metrics import sum_range
WS = Path("/root/.openclaw/workspace/revenue_sources")
day = read_day_z(WS/"paaso_day_platforma_ofd_z_2025_2026/ofd_z.csv")
night = read_night_sell(WS/"paaso_night_ofd_ru/ofd_sell.csv")
dump,_ = read_sync_dump(WS/"paaso_daily_series.json")
s = merge_series(day, night, dump)
def m(y,mo):
    import calendar; return sum_range(s, dt.date(y,mo,1), dt.date(y,mo,calendar.monthrange(y,mo)[1]))
def m_day(y,mo):
    import calendar; return sum(v for d,v in day.items() if d.year==y and d.month==mo)
print("янв 2025 день (ожид. 4 867 300):", round(m_day(2025,1)))
print("фев 2025 день (ожид. 2 132 150):", round(m_day(2025,2)))
print("июн 2025 день (ожид. 7 391 510):", round(m_day(2025,6)))
print("авг 2026 всего (ожид. 20 386 600):", round(m(2026,8)))
print("ночная 2025 всего (ожид. ~4,3–4,9 млн):", round(sum(v for d,v in night.items() if d.year==2025)))
print("год 2025 всего:", round(sum_range(s, dt.date(2025,1,1), dt.date(2025,12,31))))
PY'
```
Ожидаемо: первые четыре совпадают точно. Если «авг 2026» не совпал — проверить, что дамп (Task 6) содержит август (он перекрывает Z-отчёты).

- [ ] **Step 2: README.md**

```markdown
# Дашборд выручки

Статическая страница на GitHub Pages: https://valaamvet-creator.github.io/dashboard/

- `index.html` — страница. Читает `data.json`, обновляет сама себя каждые 5 минут.
- `data.json` — готовые цифры; сервер перезаписывает каждые 15 минут (крон `hourly_update_paaso_revenue_summary.sh`).
- `server/` — скрипты сервера: `build_dashboard_data.py` (расчёт), `publish.sh` (git push), `patches/` (что изменено в серверных скриптах).
- `tests/` — `python3 -m unittest discover -s tests`.
- `docs/superpowers/` — дизайн и план.

Объекты в `data.json` — под кодами (`p1`); названия — только в `index.html`.
Правила сравнения с прошлым годом: сегодня и 7 дней — тот же день недели (−364 дня); месяц/год в моменте, прошлый месяц, месяцы — календарные даты.
```

- [ ] **Step 3: Коммит и push**

```bash
git add README.md
git -c user.name="Виталий" -c user.email="valaam.vet@gmail.com" commit -q -m "docs: README

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git pull --rebase -q origin main && git push -q origin main
```

- [ ] **Step 4: Заметка в память Claude Code**

Создать `~/.claude/projects/-Users-vet/memory/paaso-dashboard.md`:
```markdown
---
name: paaso-dashboard
description: Сайт-дашборд выручки Паасо на GitHub Pages (valaamvet-creator/dashboard); сервер каждые 15 мин собирает data.json и пушит; правила сравнений; как чинить.
metadata:
  type: project
---

Сделан 11–12 сентября 2026. Адрес: https://valaamvet-creator.github.io/dashboard/ (без пароля, noindex).
Локальный проект/репо: `~/Claude/projects/paaso-dashboard` (= GitHub `valaamvet-creator/dashboard`, Pages из корня `main`).
Сервер: клон `/root/dashboard-pub`; крон `tools/revenue/hourly_update_paaso_revenue_summary.sh` (:05/:20/:35/:50) в конце вызывает
`python3 -m server.build_dashboard_data` → `revenue_sources/dashboard_data.json` → `server/publish.sh` (git push). Статус: `revenue_sources/paaso_night_ofd_ru/logs/dashboard_status.env`.
Источник цифр: `revenue_sources/paaso_daily_series.json` (дамп из `sync_paaso_revenue_google_sheet.py`, патч описан в `server/patches/`), 2025 — Z-отчёты `paaso_day_platforma_ofd_z_2025_2026/ofd_z.csv` (приход − возвраты) + ночные чеки `paaso_night_ofd_ru/ofd_sell.csv` (2025 догружен 11.09.2026, начинается с 20.01.2025).
Решения Виталия: компоновка «сравнения — главное», тёмный стиль, только общая цифра Паасо, без графика по дням; «сегодня»/«7 дней» сравнивать с тем же днём недели (−364), остальное — календарно. Объекты в data.json под кодами (p1), Водопады (w1) и «Всё» — заложены кнопками, не реализованы.
Спека/план: `docs/superpowers/{specs,plans}/2026-09-11-*.md`.

**Why:** Виталий будет открывать это каждый день и захочет добавить Водопады/Вашунь.
**How to apply:** для Водопадов — добавить объект `w1` в build_payload и series (данные `waterfalls_ofd_2026`), включить кнопку в OBJECTS. Если сайт «не обновлялся» — смотреть dashboard_status.env и hourly_update.log.
```
И добавить строку в `MEMORY.md`: `- [Дашборд выручки Паасо](paaso-dashboard.md) — GitHub Pages valaamvet-creator/dashboard; сервер пушит data.json каждые 15 мин; правила сравнений; где статус.`

- [ ] **Step 5: Показать Виталию адрес и попросить открыть с телефона**

Сообщение: адрес, что смотреть (сегодня/7 дней/сравнения/месяцы), что плашка ⚠ появится только при проблемах, и что Водопады — следующий шаг по желанию.

---

## Self-review (выполнен при написании)

- **Покрытие спеки:** п.3 страница → Task 5; п.4 правила → Task 3 (тесты на 364 и календарь); п.5 источники, ночная 2025, дамп → Tasks 1, 2, 6; п.6 публикация, robots, noindex → Tasks 5, 7; п.7 страница, 5-мин перечитывание, «нет связи» → Task 5; п.8 ошибки → Task 4 (warnings) + Task 5 (плашки) + Task 8 (не ломает таблицу); п.9 проверки → Tasks 4, 5, 8, 9; п.10 вне рамок — не делаем.
- **Оговорка 1–19 января 2025** (спека п.5): на странице не показывается отдельно — январь 2025 просто меньше на ~6 тыс. ₽ (ночная касса заработала 20.01.2025, декабрь-январь — минимальные суммы). Сознательно упрощено; отражено в README/памяти.
- **Согласованность имён:** `DayValue`, `read_day_z`, `read_night_sell`, `read_sync_dump`, `merge_series` (Task 2) используются в Tasks 3, 4, 9 с теми же сигнатурами; поля `data.json` (`today.value/prev/pct/complete/prev_date`, `week7.avg_day/prev_avg_day`, `prev_month.month`, `months[].m/cur/prev/pct`, `warnings`) одинаковы в Tasks 3, 4, 5.
- **Заглушек нет:** каждый код-шаг содержит полный код или полную команду.
