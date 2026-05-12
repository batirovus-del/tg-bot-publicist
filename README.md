# ТГ БОТ Публицист

Telegram бот для автоматической публикации постов в канал/группу по расписанию.

## Возможности

- ⏰ Автоматическая публикация постов каждый день в 12:00 МСК
- 🤖 Простая настройка через переменные окружения
- 📝 Команды для управления и тестирования
- 🔄 Надежный планировщик задач

## Требования

- Python 3.10 или выше
- Telegram бот (токен от @BotFather)
- ID канала/группы для публикации

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd "ТГ БОТ Публицист"
```

2. Создайте виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте файл `.env` на основе `.env.example`:
```bash
cp .env.example .env
```

5. Заполните `.env` файл своими данными:
```env
BOT_TOKEN=your_bot_token_here
CHANNEL_ID=your_channel_id_here
TIMEZONE=Europe/Moscow
POST_HOUR=12
POST_MINUTE=0
```

## Получение токена бота

1. Найдите [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям и получите токен
4. Скопируйте токен в `.env` файл

## Получение ID канала/группы

1. Добавьте бота в канал/группу как администратора
2. Отправьте любое сообщение в канал/группу
3. Перейдите по ссылке: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Найдите `"chat":{"id":-1001234567890}` - это ID вашего канала
5. Скопируйте ID в `.env` файл

## Запуск

```bash
python bot.py
```

## Команды бота

- `/start` - Информация о боте
- `/status` - Статус планировщика и время следующей публикации
- `/test` - Тестовая публикация поста (для проверки)

## Настройка контента

Контент для постов настраивается в файле `scheduler.py` в методе `get_post_content()`.

Вы можете:
- Читать контент из файла
- Получать из базы данных
- Использовать API для генерации контента
- Использовать шаблоны

## Деплой на хостинг

### VPS/VDS

1. Загрузите код на сервер
2. Установите зависимости
3. Создайте systemd service для автозапуска:

```bash
sudo nano /etc/systemd/system/tg-bot.service
```

```ini
[Unit]
Description=Telegram Publicist Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/bot
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

4. Запустите сервис:
```bash
sudo systemctl enable tg-bot
sudo systemctl start tg-bot
```

## Структура проекта

```
ТГ БОТ Публицист/
├── bot.py              # Основной файл бота
├── config.py           # Конфигурация
├── scheduler.py        # Планировщик постов
├── requirements.txt    # Зависимости
├── .env               # Переменные окружения (не в git)
├── .env.example       # Пример переменных
├── .gitignore         # Игнорируемые файлы
└── README.md          # Документация
```

## Лицензия

MIT

## Автор

Создано с помощью Claude Code
