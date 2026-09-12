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
