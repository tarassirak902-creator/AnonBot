#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 не найден. Установите python3, python3-venv и python3-pip."
  exit 1
fi

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
mkdir -p data logs

echo
echo "Зависимости установлены. Запустите:"
echo "  .venv/bin/python run.py"
echo
echo "Для автозапуска смотрите deploy/README_SYSTEMD.md"
