#!/usr/bin/env bash
# Обновление репозитория и зависимостей (Linux/macOS), запускать из корня проекта: bash scripts/update.sh
set -euo pipefail
cd "$(dirname "$0")/.."
git fetch origin
git pull origin main
if [ -f .venv/bin/activate ]; then
  # shellcheck source=/dev/null
  . .venv/bin/activate
fi
pip install -r requirements.txt
echo "Готово. Перезапустите процесс бота (python -m bot.main или systemd)."
