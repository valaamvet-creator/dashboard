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

# На ошибке pull: откатываем rebase и выходим 2 (ничего не публикуется).
git checkout -q -- data.json 2>/dev/null || true
if ! git pull --rebase -q origin main; then
  echo "publish: git pull не удался"; git rebase --abort 2>/dev/null; exit 2
fi

cp "$SRC" data.json || { echo "publish: cp не удался"; exit 1; }
if git diff --quiet -- data.json && [ -z "$(git rev-list origin/main..HEAD)" ]; then
  echo "publish: data.json не изменился"; exit 0
fi
git add data.json
if ! git diff --cached --quiet; then git commit -q -m "data: $(date '+%Y-%m-%d %H:%M')" || { echo "publish: git commit не удался"; exit 1; }; fi
if ! git push -q origin main; then
  echo "publish: git push не удался"; exit 3
fi
echo "publish: ok $(date '+%H:%M')"
