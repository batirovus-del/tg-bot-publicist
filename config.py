import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv('BOT_TOKEN')

# ID канала/группы для публикации
CHANNEL_ID = os.getenv('CHANNEL_ID')

# Часовой пояс
TIMEZONE = os.getenv('TIMEZONE', 'Europe/Moscow')

# Время публикации
POST_HOUR = int(os.getenv('POST_HOUR', 12))
POST_MINUTE = int(os.getenv('POST_MINUTE', 0))

# Groq API Key
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Проверка обязательных параметров
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в .env файле")

if not CHANNEL_ID:
    raise ValueError("CHANNEL_ID не установлен в .env файле")
