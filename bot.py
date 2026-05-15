import logging
import asyncio
import json
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler

import config
from scheduler import PostScheduler
from gemini_ai import GeminiAI

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
TITLE, CONTENT, IMAGE_QUERY = range(3)
GENERATE_TOPIC, GENERATE_PREVIEW, GENERATE_EDIT = range(3, 6)

POSTS_FILE = 'posts_data.json'
SETTINGS_FILE = 'user_settings.json'

# Временные слоты для публикации
TIME_SLOTS = {
    'morning': {'hour': 8, 'minute': 0, 'label': '🌅 Утро (8:00)'},
    'day': {'hour': 12, 'minute': 0, 'label': '☀️ День (12:00)'},
    'evening': {'hour': 19, 'minute': 0, 'label': '🌆 Вечер (19:00)'},
    'night': {'hour': 23, 'minute': 0, 'label': '🌙 Ночь (23:00)'}
}

# Стили постов
POST_STYLES = {
    'motivational': {
        'label': '💪 Мотивационный',
        'description': 'Вдохновляющие посты для достижения целей',
        'tone': 'энергичный, вдохновляющий, призывающий к действию'
    },
    'educational': {
        'label': '📚 Образовательный',
        'description': 'Обучающий контент с полезной информацией',
        'tone': 'информативный, структурированный, экспертный'
    },
    'news': {
        'label': '📰 Новостной',
        'description': 'Актуальные новости и события',
        'tone': 'нейтральный, фактический, лаконичный'
    },
    'entertaining': {
        'label': '🎉 Развлекательный',
        'description': 'Лёгкий и интересный контент',
        'tone': 'дружелюбный, весёлый, непринуждённый'
    },
    'sales': {
        'label': '💰 Продающий',
        'description': 'Посты для продвижения продуктов/услуг',
        'tone': 'убедительный, ориентированный на выгоду, призыв к действию'
    },
    'personal': {
        'label': '✍️ Личный блог',
        'description': 'Личные истории и размышления',
        'tone': 'искренний, личный, эмоциональный'
    }
}


class PublicistBot:
    """Telegram бот-публицист для автоматической публикации постов"""

    def __init__(self):
        self.application = Application.builder().token(config.BOT_TOKEN).build()
        self.scheduler = None
        self.gemini = GeminiAI()

    def get_main_keyboard(self):
        """Создание главной клавиатуры с кнопками"""
        keyboard = [
            [KeyboardButton("📊 Статус"), KeyboardButton("📄 Список постов")],
            [KeyboardButton("📝 Добавить пост"), KeyboardButton("🤖 Сгенерировать пост")],
            [KeyboardButton("🧪 Тест"), KeyboardButton("📤 Опубликовать")],
            [KeyboardButton("🗑️ Удалить пост"), KeyboardButton("⏰ Настроить время")],
            [KeyboardButton("🎨 Выбрать стиль")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def load_user_settings(self):
        """Загрузка настроек пользователя"""
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            # Создаём файл с настройками по умолчанию
            default_settings = {
                "default_user": {
                    "post_time": "day",
                    "post_hour": 12,
                    "post_minute": 0,
                    "timezone": "Europe/Moscow",
                    "post_style": "motivational"
                }
            }
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_settings, f, ensure_ascii=False, indent=2)
            return default_settings

    def save_user_settings(self, settings):
        """Сохранение настроек пользователя"""
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        await update.message.reply_text(
            "👋 Привет! Я бот-публицист.\n\n"
            f"Я автоматически публикую посты каждый день в {config.POST_HOUR}:{config.POST_MINUTE:02d} ({config.TIMEZONE}).\n\n"
            "Используй кнопки ниже для управления ботом:",
            reply_markup=self.get_main_keyboard(),
            parse_mode='Markdown'
        )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status"""
        if self.scheduler and self.scheduler.scheduler.running:
            next_run = self.scheduler.scheduler.get_job('daily_post').next_run_time
            await update.message.reply_text(
                f"✅ Планировщик активен\n"
                f"⏰ Следующая публикация: {next_run.strftime('%d.%m.%Y %H:%M:%S %Z')}",
                reply_markup=self.get_main_keyboard()
            )
        else:
            await update.message.reply_text("❌ Планировщик не активен", reply_markup=self.get_main_keyboard())

    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /test - тестовая публикация"""
        try:
            await self.scheduler.send_daily_post()
            await update.message.reply_text("✅ Тестовый пост успешно опубликован!", reply_markup=self.get_main_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при публикации: {e}", reply_markup=self.get_main_keyboard())
            logger.error(f"Ошибка при тестовой публикации: {e}")

    async def listposts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /listposts - список всех постов"""
        try:
            with open(POSTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            posts = data.get('posts', [])

            if not posts:
                await update.message.reply_text("📭 Нет постов", reply_markup=self.get_main_keyboard())
                return

            message = "📝 *Список постов:*\n\n"
            for post in posts:
                # Экранируем специальные символы для Markdown
                title = post['title'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                content_preview = post['content'][:100].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                message += f"*День {post['day']}: {title}*\n"
                message += f"{content_preview}...\n\n"

            message += "\n💡 Используй кнопку 'Опубликовать' для публикации"

            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=self.get_main_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}", reply_markup=self.get_main_keyboard())
            logger.error(f"Ошибка при получении списка постов: {e}")

    async def publish_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /publish <день> - публикация поста"""
        try:
            if not context.args or len(context.args) == 0:
                # Показываем список постов с кнопками для выбора
                with open(POSTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                posts = data.get('posts', [])
                if not posts:
                    await update.message.reply_text("❌ Нет постов для публикации", reply_markup=self.get_main_keyboard())
                    return

                keyboard = []
                for post in posts:
                    keyboard.append([KeyboardButton(f"📤 День {post['day']}: {post['title'][:30]}")])
                keyboard.append([KeyboardButton("🔙 Назад")])

                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text("Выбери пост для публикации:", reply_markup=reply_markup)
                return

            day = int(context.args[0])

            with open(POSTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            post = next((p for p in data['posts'] if p['day'] == day), None)

            if not post:
                await update.message.reply_text(f"❌ Пост для дня {day} не найден", reply_markup=self.get_main_keyboard())
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

            await update.message.reply_text(f"✅ Пост (День {day}) успешно опубликован!", reply_markup=self.get_main_keyboard())
            logger.info(f"Пост (День {day}) успешно опубликован в канал {config.CHANNEL_ID}")

        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Используй: /publish 1", reply_markup=self.get_main_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}", reply_markup=self.get_main_keyboard())
            logger.error(f"Ошибка при публикации поста: {e}")

    async def deletepost_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /deletepost <день> - удаление поста"""
        try:
            if not context.args or len(context.args) == 0:
                # Показываем список постов с кнопками для выбора
                with open(POSTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                posts = data.get('posts', [])
                if not posts:
                    await update.message.reply_text("❌ Нет постов для удаления", reply_markup=self.get_main_keyboard())
                    return

                keyboard = []
                for post in posts:
                    keyboard.append([KeyboardButton(f"🗑️ День {post['day']}: {post['title'][:30]}")])
                keyboard.append([KeyboardButton("🔙 Назад")])

                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text("Выбери пост для удаления:", reply_markup=reply_markup)
                return

            day = int(context.args[0])

            with open(POSTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            original_count = len(data['posts'])
            data['posts'] = [p for p in data['posts'] if p['day'] != day]

            if len(data['posts']) == original_count:
                await update.message.reply_text(f"❌ Пост для дня {day} не найден", reply_markup=self.get_main_keyboard())
                return

            with open(POSTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            await update.message.reply_text(f"✅ Пост (День {day}) удален", reply_markup=self.get_main_keyboard())

        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Используй: /deletepost 1", reply_markup=self.get_main_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}", reply_markup=self.get_main_keyboard())
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
                f"Используй кнопку 'Опубликовать' для публикации",
                parse_mode='Markdown',
                reply_markup=self.get_main_keyboard()
            )

            context.user_data.clear()
            return ConversationHandler.END

        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при сохранении: {e}", reply_markup=self.get_main_keyboard())
            logger.error(f"Ошибка при сохранении поста: {e}")
            return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена добавления поста"""
        context.user_data.clear()
        await update.message.reply_text("❌ Добавление поста отменено", reply_markup=self.get_main_keyboard())
        return ConversationHandler.END

    async def handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        text = update.message.text

        if text == "📊 Статус":
            await self.status_command(update, context)
        elif text == "📄 Список постов":
            await self.listposts_command(update, context)
        elif text == "📝 Добавить пост":
            await self.addpost_start(update, context)
        elif text == "🤖 Сгенерировать пост":
            # Обрабатывается через ConversationHandler
            return
        elif text == "🧪 Тест":
            await self.test_command(update, context)
        elif text == "📤 Опубликовать":
            await self.publish_command(update, context)
        elif text == "🗑️ Удалить пост":
            await self.deletepost_command(update, context)
        elif text == "⏰ Настроить время":
            await self.time_settings_command(update, context)
        elif text == "🎨 Выбрать стиль":
            await self.style_settings_command(update, context)
        elif text == "🔙 Назад":
            await update.message.reply_text("Главное меню:", reply_markup=self.get_main_keyboard())
        elif text.startswith("📤 День "):
            # Извлекаем номер дня из текста кнопки
            try:
                day = int(text.split("День ")[1].split(":")[0])
                context.args = [str(day)]
                await self.publish_command(update, context)
            except:
                await update.message.reply_text("❌ Ошибка обработки", reply_markup=self.get_main_keyboard())
        elif text.startswith("🗑️ День "):
            # Извлекаем номер дня из текста кнопки
            try:
                day = int(text.split("День ")[1].split(":")[0])
                context.args = [str(day)]
                await self.deletepost_command(update, context)
            except:
                await update.message.reply_text("❌ Ошибка обработки", reply_markup=self.get_main_keyboard())
        elif text in [slot['label'] for slot in TIME_SLOTS.values()]:
            # Обработка выбора времени
            await self.set_time_slot(update, context, text)
        elif text in [style['label'] for style in POST_STYLES.values()]:
            # Обработка выбора стиля
            await self.set_post_style(update, context, text)
        else:
            await update.message.reply_text("Используй кнопки ниже для управления ботом", reply_markup=self.get_main_keyboard())

    async def time_settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик настройки времени публикации"""
        settings = self.load_user_settings()
        current_time = settings.get('default_user', {}).get('post_time', 'day')
        current_label = TIME_SLOTS.get(current_time, TIME_SLOTS['day'])['label']

        keyboard = []
        for slot_key, slot_data in TIME_SLOTS.items():
            keyboard.append([KeyboardButton(slot_data['label'])])
        keyboard.append([KeyboardButton("🔙 Назад")])

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            f"⏰ *Настройка времени публикации*\n\n"
            f"Текущее время: {current_label}\n\n"
            f"Выбери новое время:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def set_time_slot(self, update: Update, context: ContextTypes.DEFAULT_TYPE, selected_label: str):
        """Установка выбранного времени публикации"""
        # Находим ключ по label
        selected_slot = None
        for slot_key, slot_data in TIME_SLOTS.items():
            if slot_data['label'] == selected_label:
                selected_slot = slot_key
                break

        if not selected_slot:
            await update.message.reply_text("❌ Ошибка выбора времени", reply_markup=self.get_main_keyboard())
            return

        # Загружаем настройки
        settings = self.load_user_settings()
        settings['default_user']['post_time'] = selected_slot
        settings['default_user']['post_hour'] = TIME_SLOTS[selected_slot]['hour']
        settings['default_user']['post_minute'] = TIME_SLOTS[selected_slot]['minute']

        # Сохраняем настройки
        self.save_user_settings(settings)

        # Перезапускаем планировщик с новым временем
        if self.scheduler:
            self.scheduler.update_schedule(
                TIME_SLOTS[selected_slot]['hour'],
                TIME_SLOTS[selected_slot]['minute']
            )

        await update.message.reply_text(
            f"✅ Время публикации изменено на {selected_label}\n\n"
            f"Посты будут публиковаться в {TIME_SLOTS[selected_slot]['hour']:02d}:{TIME_SLOTS[selected_slot]['minute']:02d}",
            reply_markup=self.get_main_keyboard()
        )

    async def style_settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик настройки стиля постов"""
        settings = self.load_user_settings()
        current_style = settings.get('default_user', {}).get('post_style', 'motivational')
        current_style_data = POST_STYLES.get(current_style, POST_STYLES['motivational'])

        keyboard = []
        for style_key, style_data in POST_STYLES.items():
            # Добавляем галочку к текущему стилю
            label = style_data['label']
            if style_key == current_style:
                label += " ✓"
            keyboard.append([KeyboardButton(style_data['label'])])
        keyboard.append([KeyboardButton("🔙 Назад")])

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        message = f"🎨 *Настройка стиля постов*\n\n"
        message += f"Текущий стиль: {current_style_data['label']}\n"
        message += f"_{current_style_data['description']}_\n\n"
        message += "Выбери новый стиль:"

        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def set_post_style(self, update: Update, context: ContextTypes.DEFAULT_TYPE, selected_label: str):
        """Установка выбранного стиля постов"""
        # Находим ключ по label
        selected_style = None
        for style_key, style_data in POST_STYLES.items():
            if style_data['label'] == selected_label:
                selected_style = style_key
                break

        if not selected_style:
            await update.message.reply_text("❌ Ошибка выбора стиля", reply_markup=self.get_main_keyboard())
            return

        # Загружаем настройки
        settings = self.load_user_settings()
        settings['default_user']['post_style'] = selected_style

        # Сохраняем настройки
        self.save_user_settings(settings)

        style_data = POST_STYLES[selected_style]
        await update.message.reply_text(
            f"✅ Стиль постов изменён на {style_data['label']}\n\n"
            f"_{style_data['description']}_\n\n"
            f"Тон: {style_data['tone']}",
            parse_mode='Markdown',
            reply_markup=self.get_main_keyboard()
        )

    async def generate_post_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало генерации поста через AI"""
        logger.info(f"Пользователь {update.effective_user.id} начал генерацию поста")

        if not config.GEMINI_API_KEY or config.GEMINI_API_KEY == 'your_gemini_api_key_here':
            logger.warning("Gemini API ключ не настроен")
            await update.message.reply_text(
                "❌ Gemini API ключ не настроен\n\n"
                "Для использования AI-генерации нужно:\n"
                "1. Получить API ключ на https://makersuite.google.com/app/apikey\n"
                "2. Добавить его в файл .env: GEMINI_API_KEY=ваш_ключ",
                reply_markup=self.get_main_keyboard()
            )
            return ConversationHandler.END

        logger.info("Gemini API ключ найден, запрашиваем тему")
        await update.message.reply_text(
            "🤖 *Генерация поста через AI*\n\n"
            "Введи тему для поста\n"
            "(Например: Как заработать первый миллион)\n\n"
            "Отправь /cancel для отмены",
            parse_mode='Markdown'
        )
        return GENERATE_TOPIC

    async def generate_post_topic(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение темы и генерация поста"""
        topic = update.message.text
        context.user_data['generate_topic'] = topic

        logger.info(f"Получена тема для генерации: {topic}")

        # Получаем текущий стиль из настроек
        settings = self.load_user_settings()
        current_style = settings.get('default_user', {}).get('post_style', 'motivational')

        logger.info(f"Стиль поста: {current_style}")

        await update.message.reply_text(
            f"⏳ Генерирую пост на тему: *{topic}*\n"
            f"Стиль: {POST_STYLES[current_style]['label']}\n\n"
            f"Подожди несколько секунд...",
            parse_mode='Markdown'
        )

        try:
            logger.info("Начинаем генерацию через Gemini...")
            # Генерируем пост
            generated = self.gemini.generate_post(topic, current_style)
            logger.info(f"Пост сгенерирован: заголовок={generated['title'][:50]}")

            context.user_data['generated_title'] = generated['title']
            context.user_data['generated_content'] = generated['content']
            context.user_data['generated_image_prompt'] = generated['image_prompt']

            # Показываем предпросмотр
            preview_text = f"✅ *Пост сгенерирован!*\n\n"
            preview_text += f"*Заголовок:*\n{generated['title']}\n\n"
            preview_text += f"*Содержание:*\n{generated['content'][:500]}"
            if len(generated['content']) > 500:
                preview_text += "..."

            keyboard = [
                [KeyboardButton("✅ Сохранить пост")],
                [KeyboardButton("🔄 Сгенерировать заново")],
                [KeyboardButton("✏️ Редактировать")],
                [KeyboardButton("❌ Отменить")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            await update.message.reply_text(preview_text, parse_mode='Markdown', reply_markup=reply_markup)
            return GENERATE_PREVIEW

        except Exception as e:
            logger.error(f"Ошибка при генерации поста: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Ошибка при генерации поста:\n{str(e)}",
                reply_markup=self.get_main_keyboard()
            )
            return ConversationHandler.END

    async def generate_post_preview(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка действий с предпросмотром"""
        text = update.message.text

        if text == "✅ Сохранить пост":
            # Сохраняем пост
            try:
                with open(POSTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                existing_days = [p['day'] for p in data['posts']]
                next_day = max(existing_days) + 1 if existing_days else 1

                new_post = {
                    "day": next_day,
                    "title": context.user_data['generated_title'],
                    "content": context.user_data['generated_content'],
                    "image_query": context.user_data['generated_image_prompt']
                }

                data['posts'].append(new_post)

                with open(POSTS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                await update.message.reply_text(
                    f"✅ *Пост успешно сохранён!*\n\n"
                    f"День: {next_day}\n"
                    f"Заголовок: {new_post['title']}\n\n"
                    f"Используй кнопку 'Опубликовать' для публикации",
                    parse_mode='Markdown',
                    reply_markup=self.get_main_keyboard()
                )

                context.user_data.clear()
                return ConversationHandler.END

            except Exception as e:
                await update.message.reply_text(
                    f"❌ Ошибка при сохранении: {e}",
                    reply_markup=self.get_main_keyboard()
                )
                return ConversationHandler.END

        elif text == "🔄 Сгенерировать заново":
            # Генерируем заново
            topic = context.user_data.get('generate_topic', '')
            settings = self.load_user_settings()
            current_style = settings.get('default_user', {}).get('post_style', 'motivational')

            await update.message.reply_text("⏳ Генерирую новый вариант...")

            generated = self.gemini.generate_post(topic, current_style)

            context.user_data['generated_title'] = generated['title']
            context.user_data['generated_content'] = generated['content']
            context.user_data['generated_image_prompt'] = generated['image_prompt']

            preview_text = f"✅ *Новый вариант сгенерирован!*\n\n"
            preview_text += f"*Заголовок:*\n{generated['title']}\n\n"
            preview_text += f"*Содержание:*\n{generated['content'][:500]}"
            if len(generated['content']) > 500:
                preview_text += "..."

            keyboard = [
                [KeyboardButton("✅ Сохранить пост")],
                [KeyboardButton("🔄 Сгенерировать заново")],
                [KeyboardButton("✏️ Редактировать")],
                [KeyboardButton("❌ Отменить")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            await update.message.reply_text(preview_text, parse_mode='Markdown', reply_markup=reply_markup)
            return GENERATE_PREVIEW

        elif text == "✏️ Редактировать":
            await update.message.reply_text(
                "✏️ Введи инструкцию для улучшения поста\n"
                "(Например: Сделай короче, Добавь больше эмодзи, Сделай более формальным)\n\n"
                "Или отправь /cancel для отмены"
            )
            return GENERATE_EDIT

        elif text == "❌ Отменить":
            context.user_data.clear()
            await update.message.reply_text("❌ Генерация отменена", reply_markup=self.get_main_keyboard())
            return ConversationHandler.END

        else:
            await update.message.reply_text("Используй кнопки для выбора действия")
            return GENERATE_PREVIEW

    async def generate_post_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Редактирование сгенерированного поста"""
        instruction = update.message.text

        await update.message.reply_text("⏳ Улучшаю пост...")

        current_content = context.user_data.get('generated_content', '')
        improved_content = self.gemini.improve_post(current_content, instruction)

        context.user_data['generated_content'] = improved_content

        preview_text = f"✅ *Пост улучшён!*\n\n"
        preview_text += f"*Заголовок:*\n{context.user_data['generated_title']}\n\n"
        preview_text += f"*Содержание:*\n{improved_content[:500]}"
        if len(improved_content) > 500:
            preview_text += "..."

        keyboard = [
            [KeyboardButton("✅ Сохранить пост")],
            [KeyboardButton("🔄 Сгенерировать заново")],
            [KeyboardButton("✏️ Редактировать")],
            [KeyboardButton("❌ Отменить")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(preview_text, parse_mode='Markdown', reply_markup=reply_markup)
        return GENERATE_PREVIEW


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

        # ConversationHandler для генерации поста через AI
        generate_handler = ConversationHandler(
            entry_points=[
                CommandHandler("generate", self.generate_post_start),
                MessageHandler(filters.Regex("^🤖 Сгенерировать пост$"), self.generate_post_start)
            ],
            states={
                GENERATE_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.generate_post_topic)],
                GENERATE_PREVIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.generate_post_preview)],
                GENERATE_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.generate_post_edit)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
        self.application.add_handler(generate_handler)

        # Обработчик кнопок (должен быть последним)
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_button))

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
