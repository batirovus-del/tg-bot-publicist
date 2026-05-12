import logging
import asyncio
import json
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler

import config
from scheduler import PostScheduler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
TITLE, CONTENT, IMAGE_QUERY = range(3)

POSTS_FILE = 'posts_data.json'


class PublicistBot:
    """Telegram бот-публицист для автоматической публикации постов"""

    def __init__(self):
        self.application = Application.builder().token(config.BOT_TOKEN).build()
        self.scheduler = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        await update.message.reply_text(
            "👋 Привет! Я бот-публицист.\n\n"
            f"Я автоматически публикую посты каждый день в {config.POST_HOUR}:{config.POST_MINUTE:02d} ({config.TIMEZONE}).\n\n"
            "📋 *Доступные команды:*\n\n"
            "📝 /addpost - добавить новый пост\n"
            "📄 /listposts - список всех постов\n"
            "📤 /publish <день> - опубликовать пост\n"
            "🗑️ /deletepost <день> - удалить пост\n\n"
            "📊 /status - статус планировщика\n"
            "🧪 /test - тестовая публикация",
            parse_mode='Markdown'
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

    async def listposts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /listposts - список всех постов"""
        try:
            with open(POSTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            posts = data.get('posts', [])

            if not posts:
                await update.message.reply_text("📭 Нет постов")
                return

            message = "📝 *Список постов:*\n\n"
            for post in posts:
                # Экранируем специальные символы для Markdown
                title = post['title'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                content_preview = post['content'][:100].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                message += f"*День {post['day']}: {title}*\n"
                message += f"{content_preview}...\n\n"

            message += "\n💡 Используй /publish <день> для публикации"

            await update.message.reply_text(message, parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
            logger.error(f"Ошибка при получении списка постов: {e}")

    async def publish_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /publish <день> - публикация поста"""
        try:
            if not context.args or len(context.args) == 0:
                await update.message.reply_text("❌ Укажи номер дня: /publish 1")
                return

            day = int(context.args[0])

            with open(POSTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            post = next((p for p in data['posts'] if p['day'] == day), None)

            if not post:
                await update.message.reply_text(f"❌ Пост для дня {day} не найден")
                return

            # Формируем текст поста
            post_text = f"""БИСМИЛЛАХ

{post['content']}

ИНШААЛЛАХ"""

            # Получаем картинку
            if post.get('image_query'):
                import random
                random_id = random.randint(1, 1000)
                image_url = f"https://picsum.photos/1200/630?random={random_id}"

                await self.application.bot.send_photo(
                    chat_id=config.CHANNEL_ID,
                    photo=image_url,
                    caption=post_text,
                    parse_mode='Markdown'
                )
            else:
                await self.application.bot.send_message(
                    chat_id=config.CHANNEL_ID,
                    text=post_text,
                    parse_mode='Markdown'
                )

            await update.message.reply_text(f"✅ Пост (День {day}) опубликован!")

        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Используй: /publish 1")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
            logger.error(f"Ошибка при публикации поста: {e}")

    async def deletepost_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /deletepost <день> - удаление поста"""
        try:
            if not context.args or len(context.args) == 0:
                await update.message.reply_text("❌ Укажи номер дня: /deletepost 1")
                return

            day = int(context.args[0])

            with open(POSTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            original_count = len(data['posts'])
            data['posts'] = [p for p in data['posts'] if p['day'] != day]

            if len(data['posts']) == original_count:
                await update.message.reply_text(f"❌ Пост для дня {day} не найден")
                return

            with open(POSTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            await update.message.reply_text(f"✅ Пост (День {day}) удален")

        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Используй: /deletepost 1")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
            logger.error(f"Ошибка при удалении поста: {e}")

    async def addpost_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало добавления поста"""
        await update.message.reply_text(
            "📝 *Добавление нового поста*\n\n"
            "Шаг 1/3: Введи заголовок поста\n"
            "(Например: SaaS продукт для бизнеса)\n\n"
            "Отправь /cancel для отмены",
            parse_mode='Markdown'
        )
        return TITLE

    async def addpost_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение заголовка"""
        context.user_data['title'] = update.message.text
        await update.message.reply_text(
            "✅ Заголовок сохранен\n\n"
            "Шаг 2/3: Введи содержание поста\n"
            "(Можно использовать Markdown форматирование)",
            parse_mode='Markdown'
        )
        return CONTENT

    async def addpost_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение содержания"""
        context.user_data['content'] = update.message.text
        await update.message.reply_text(
            "✅ Содержание сохранено\n\n"
            "Шаг 3/3: Введи ключевые слова для картинки Unsplash\n"
            "(Например: business success money)\n\n"
            "Или отправь /skip чтобы пропустить",
            parse_mode='Markdown'
        )
        return IMAGE_QUERY

    async def addpost_image_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение ключевых слов для картинки"""
        context.user_data['image_query'] = update.message.text
        return await self.save_post(update, context)

    async def addpost_skip_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Пропуск картинки"""
        context.user_data['image_query'] = ''
        return await self.save_post(update, context)

    async def save_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохранение поста"""
        try:
            with open(POSTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Определяем следующий день
            existing_days = [p['day'] for p in data['posts']]
            next_day = max(existing_days) + 1 if existing_days else 1

            # Создаем новый пост
            new_post = {
                "day": next_day,
                "title": context.user_data['title'],
                "content": context.user_data['content'],
                "image_query": context.user_data.get('image_query', '')
            }

            data['posts'].append(new_post)

            with open(POSTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            await update.message.reply_text(
                f"✅ *Пост успешно добавлен!*\n\n"
                f"День: {next_day}\n"
                f"Заголовок: {new_post['title']}\n\n"
                f"Используй /publish {next_day} для публикации",
                parse_mode='Markdown'
            )

            context.user_data.clear()
            return ConversationHandler.END

        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при сохранении: {e}")
            logger.error(f"Ошибка при сохранении поста: {e}")
            return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена добавления поста"""
        context.user_data.clear()
        await update.message.reply_text("❌ Добавление поста отменено")
        return ConversationHandler.END


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
        self.application.add_handler(CommandHandler("listposts", self.listposts_command))
        self.application.add_handler(CommandHandler("publish", self.publish_command))
        self.application.add_handler(CommandHandler("deletepost", self.deletepost_command))

        # ConversationHandler для добавления поста
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("addpost", self.addpost_start)],
            states={
                TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.addpost_title)],
                CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.addpost_content)],
                IMAGE_QUERY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.addpost_image_query),
                    CommandHandler("skip", self.addpost_skip_image)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
        self.application.add_handler(conv_handler)

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
