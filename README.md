# Дашборд выручки

Статическая страница на GitHub Pages: https://valaamvet-creator.github.io/dashboard/

- `index.html` — страница. Читает `data.json`, обновляет сама себя каждые 5 минут.
- `data.json` — готовые цифры; сервер перезаписывает каждые 15 минут (крон `hourly_update_paaso_revenue_summary.sh`).
- `server/` — скрипты сервера: `build_dashboard_data.py` (расчёт), `publish.sh` (git push), `patches/` (что изменено в серверных скриптах).
- `tests/` — `python3 -m unittest discover -s tests`.
- `docs/superpowers/` — дизайн и план (не в репозитории, только локально).

Объекты в `data.json` — под кодами (`p1`); названия — только в `index.html`.
Правила сравнения с прошлым годом: сегодня и 7 дней — тот же день недели (−364 дня); месяц/год в моменте, прошлый месяц, месяцы — календарные даты.
