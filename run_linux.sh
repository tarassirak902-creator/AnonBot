#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ ! -f .env ]]; then
  echo "Ошибка: не найден файл $PROJECT_DIR/.env" >&2
  echo "Создайте его на основе .env.example и заполните реальные значения." >&2
  exit 1
fi

python3 -c 'import aiogram, aiosqlite, dotenv, openpyxl' 2>/dev/null || {
  echo "Не установлены зависимости. Выполните:" >&2
  echo "  python3 -m pip install -r requirements.txt" >&2
  exit 1
}

exec python3 run.py
