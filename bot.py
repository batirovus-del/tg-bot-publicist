import logging
import asyncio
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

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
                InlineKeyboardButton("📊 Статус", callback_data='status'),
                InlineKeyboardButton("🧪 Тест", callback_data='test')
            ],
            [
                InlineKeyboardButton("ℹ️ Помощь", callback_data='help')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "👋 Привет! Я бот-публицист.\n\n"
            f"Я автоматически публикую посты каждый день в {config.POST_HOUR}:{config.POST_MINUTE:02d} ({config.TIMEZONE}).\n\n"
            "Выбери действие:",
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

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на инлайн-кнопки"""
        query = update.callback_query
        await query.answer()

        keyboard = [
            [
                InlineKeyboardButton("📊 Статус", callback_data='status'),
                InlineKeyboardButton("🧪 Тест", callback_data='test')
            ],
            [
                InlineKeyboardButton("ℹ️ Помощь", callback_data='help')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if query.data == 'status':
            if self.scheduler and self.scheduler.scheduler.running:
                next_run = self.scheduler.scheduler.get_job('daily_post').next_run_time
                text = (
                    f"✅ Планировщик активен\n\n"
                    f"⏰ Следующая публикация:\n"
                    f"{next_run.strftime('%d.%m.%Y %H:%M:%S %Z')}\n\n"
                    f"Выбери действие:"
                )
            else:
                text = "❌ Планировщик не активен\n\nВыбери действие:"

            await query.edit_message_text(text=text, reply_markup=reply_markup)

        elif query.data == 'test':
            try:
                await self.scheduler.send_daily_post()
                text = "✅ Тестовый пост успешно опубликован!\n\nВыбери действие:"
            except Exception as e:
                text = f"❌ Ошибка при публикации: {e}\n\nВыбери действие:"
                logger.error(f"Ошибка при тестовой публикации: {e}")

            await query.edit_message_text(text=text, reply_markup=reply_markup)

        elif query.data == 'help':
            text = (
                "ℹ️ <b>Помощь</b>\n\n"
                "📊 <b>Статус</b> - проверить статус планировщика и время следующей публикации\n\n"
                "🧪 <b>Тест</b> - отправить тестовый пост в канал прямо сейчас\n\n"
                f"⏰ Бот автоматически публикует посты каждый день в {config.POST_HOUR}:{config.POST_MINUTE:02d} ({config.TIMEZONE})\n\n"
                "Выбери действие:"
            )
            await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='HTML')

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

        # Регистрация обработчика инлайн-кнопок
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

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
