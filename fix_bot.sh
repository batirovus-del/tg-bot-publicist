#!/bin/bash

# Скрипт для исправления бота на Beget

echo "=== Проверка запущенных процессов бота ==="
ps aux | grep bot.py | grep -v grep

echo ""
echo "=== Остановка всех процессов бота ==="
pkill -f bot.py
sleep 2

echo ""
echo "=== Проверка, что процессы остановлены ==="
ps aux | grep bot.py | grep -v grep

echo ""
echo "=== Переход в папку бота ==="
cd ~/telegram_bot

echo ""
echo "=== Запуск бота ==="
nohup python3 bot.py > bot.log 2>&1 &

sleep 3

echo ""
echo "=== Проверка, что бот запустился ==="
ps aux | grep bot.py | grep -v grep

echo ""
echo "=== Последние 20 строк логов ==="
tail -20 bot.log
