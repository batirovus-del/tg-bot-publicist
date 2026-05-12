import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
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
            # Здесь будет логика генерации/получения контента для поста
            post_text = self.get_post_content()

            # Отправка поста в канал
            await self.bot.send_message(
                chat_id=config.CHANNEL_ID,
                text=post_text,
                parse_mode='HTML'
            )

            logger.info(f"Пост успешно опубликован в {datetime.now()}")

        except TelegramError as e:
            logger.error(f"Ошибка при отправке поста: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")

    def get_post_content(self) -> str:
        """
        Получение контента для поста.
        TODO: Реализовать логику получения контента
        (из базы данных, API, файла и т.д.)
        """
        current_date = datetime.now(pytz.timezone(config.TIMEZONE)).strftime("%d.%m.%Y")

        # Пример поста
        post = f"""
<b>📰 Ежедневный пост - {current_date}</b>

Здесь будет ваш контент для публикации.

<i>Автоматически опубликовано ботом</i>
"""
        return post.strip()

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
