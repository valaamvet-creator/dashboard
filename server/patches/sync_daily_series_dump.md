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
