import logging
import asyncio
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

import config
from scheduler import PostScheduler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class PublicistBot:
    """Telegram бот-публицист для автоматической публикации постов"""

    def __init__(self):
        self.application = Application.builder().token(config.BOT_TOKEN).build()
        self.scheduler = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        keyboard = [
            [
                InlineKeyboardButton("🚀 Открыть панель управления", web_app={"url": "https://batirovus-del.github.io/tg-bot-publicist/"})
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "👋 Привет! Я бот-публицист.\n\n"
            f"Я автоматически публикую посты каждый день в {config.POST_HOUR}:{config.POST_MINUTE:02d} ({config.TIMEZONE}).\n\n"
            "Открой панель управления для контроля бота:",
            reply_markup=reply_markup
        )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status"""
        if self.scheduler and self.scheduler.scheduler.running:
            next_run = self.scheduler.scheduler.get_job('daily_post').next_run_time
            await update.message.reply_text(
                f"✅ Планировщик активен\n"
                f"⏰ Следующая публикация: {next_run.strftime('%d.%m.%Y %H:%M:%S %Z')}"
            )
        else:
            await update.message.reply_text("❌ Планировщик не активен")

    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /test - тестовая публикация"""
        try:
            await self.scheduler.send_daily_post()
            await update.message.reply_text("✅ Тестовый пост успешно опубликован!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при публикации: {e}")
            logger.error(f"Ошибка при тестовой публикации: {e}")


    async def post_init(self, application: Application):
        """Инициализация после запуска приложения"""
        # Создание и запуск планировщика
        self.scheduler = PostScheduler(application.bot)
        self.scheduler.start()
        logger.info("Бот успешно запущен и готов к работе")

    async def post_shutdown(self, application: Application):
        """Действия при остановке бота"""
        if self.scheduler:
            self.scheduler.stop()
        logger.info("Бот остановлен")

    def run(self):
        """Запуск бота"""
        # Регистрация обработчиков команд
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("test", self.test_command))

        # Регистрация хуков инициализации и остановки
        self.application.post_init = self.post_init
        self.application.post_shutdown = self.post_shutdown

        # Запуск бота
        logger.info("Запуск бота...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    try:
        bot = PublicistBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
