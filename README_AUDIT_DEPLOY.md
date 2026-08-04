# Применение ветки аудита на сервере

До объединения PR не переключайте рабочий сервер на эту ветку.

После проверки и merge:

```bash
cd "/root/Тестовый бот/Бот"
git pull --ff-only origin main
python3 -m pip install -r requirements.txt
python3 -m compileall -q app tools run.py
sudo systemctl restart anonymous-chat-bot
sudo systemctl status anonymous-chat-bot --no-pager
```

Перед обновлением обязательно сохраните рабочую базу вне Git-репозитория:

```bash
cp data/bot.db "$HOME/bot-$(date +%F-%H%M%S).db"
```
