#!/bin/bash

# Скрипт для настройки API на Beget

# Останавливаем старые процессы
pkill -f api.py
pkill -f gunicorn

# Переходим в директорию
cd ~/telegram_bot

# Обновляем код
git pull

# Устанавливаем зависимости
pip3 install --user flask flask-cors gunicorn

# Запускаем API через gunicorn
nohup ~/.local/bin/gunicorn -w 1 -b 0.0.0.0:5000 api:app > api.log 2>&1 &

# Ждем 3 секунды
sleep 3

# Проверяем статус
echo "=== Процессы ==="
ps aux | grep -E "(gunicorn|bot.py)" | grep -v grep

echo ""
echo "=== API логи ==="
tail -20 api.log

echo ""
echo "=== Bot логи ==="
tail -10 bot.log
