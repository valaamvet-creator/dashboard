# Дашборд выручки

Статическая страница на GitHub Pages: https://valaamvet-creator.github.io/dashboard/

- `index.html` — страница. Читает `data.json`, обновляет сама себя каждые 5 минут.
- `data.json` — готовые цифры; сервер перезаписывает каждые 15 минут (крон `hourly_update_paaso_revenue_summary.sh`).
- `server/` — скрипты сервера: `build_dashboard_data.py` (расчёт), `publish.sh` (git push), `patches/` (что изменено в серверных скриптах).
- `tests/` — `python3 -m unittest discover -s tests`.
- `docs/superpowers/` — дизайн и план (не в репозитории, только локально).

Объекты в `data.json` — под кодами (`p1`, `w1`, `v1`, `all` = сумма трёх); названия — только в `index.html`.
`v1`: история (2025 и 2026 до 11.07) — статичный CSV на сервере `revenue_sources/vashun_daily_history.csv`; с 12.07.2026 — `server/fetch_sheet_daily.py` читает блок «Выручка по дням» Google-таблицы объекта в `revenue_sources/vashun_daily_sheet.csv` каждый тик крона; при ошибке чтения «сегодня» помечается неполным.
Прошлый год для `w1` — статичный CSV на сервере (`revenue_sources/waterfalls_daily_2025.csv`), текущий — из дампа sync-скрипта (поля `wf1/wf2/wf_complete`).
Правила сравнения с прошлым годом: сегодня и 7 дней — тот же день недели (−364 дня); месяц/год в моменте, прошлый месяц, месяцы — календарные даты.
