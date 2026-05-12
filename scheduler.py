import logging
import json
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import httpx
from telegram import Bot
from telegram.error import TelegramError

import config

logger = logging.getLogger(__name__)


class PostScheduler:
    """Планировщик для автоматической публикации постов"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone(config.TIMEZONE))

    async def send_daily_post(self):
        """Отправка ежедневного поста в канал/группу"""
        try:
            # Получаем контент поста
            post_text, image_url = await self.get_post_content()

            # Отправка поста с картинкой в канал
            if image_url:
                await self.bot.send_photo(
                    chat_id=config.CHANNEL_ID,
                    photo=image_url,
                    caption=post_text,
                    parse_mode='Markdown'
                )
            else:
                await self.bot.send_message(
                    chat_id=config.CHANNEL_ID,
                    text=post_text,
                    parse_mode='Markdown'
                )

            logger.info(f"Пост успешно опубликован в {datetime.now()}")

        except TelegramError as e:
            logger.error(f"Ошибка при отправке поста: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")

    async def get_post_content(self) -> tuple[str, str]:
        """
        Получение контента для поста на основе дня недели.
        Возвращает (текст_поста, url_картинки)
        """
        # Загружаем посты из JSON
        with open('posts_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Определяем день недели (1 = понедельник, 7 = воскресенье)
        current_day = datetime.now(pytz.timezone(config.TIMEZONE)).isoweekday()

        # Находим пост для текущего дня
        post = next((p for p in data['posts'] if p['day'] == current_day), data['posts'][0])

        # Получаем картинку из Unsplash
        image_url = await self.get_unsplash_image(post['image_query'])

        # Формируем текст поста
        post_text = f"""БИСМИЛЛАХ

{post['content']}

ИНШААЛЛАХ"""

        return post_text, image_url

    async def get_unsplash_image(self, query: str) -> str:
        """
        Получение случайной картинки из Unsplash по запросу
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    'https://source.unsplash.com/1200x630/',
                    params={'q': query},
                    follow_redirects=True
                )
                if response.status_code == 200:
                    return str(response.url)
        except Exception as e:
            logger.error(f"Ошибка получения картинки: {e}")

        # Возвращаем дефолтную картинку при ошибке
        return 'https://source.unsplash.com/1200x630/?business,success'

    def start(self):
        """Запуск планировщика"""
        # Добавление задачи на ежедневную публикацию в 12:00 МСК
        self.scheduler.add_job(
            self.send_daily_post,
            trigger=CronTrigger(
                hour=config.POST_HOUR,
                minute=config.POST_MINUTE,
                timezone=config.TIMEZONE
            ),
            id='daily_post',
            name='Ежедневная публикация поста',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info(f"Планировщик запущен. Посты будут публиковаться каждый день в {config.POST_HOUR}:{config.POST_MINUTE:02d} ({config.TIMEZONE})")

    def stop(self):
        """Остановка планировщика"""
        self.scheduler.shutdown()
        logger.info("Планировщик остановлен")
