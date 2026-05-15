import logging
from groq import Groq
import config

logger = logging.getLogger(__name__)


class GeminiAI:
    """Класс для работы с Groq AI"""

    def __init__(self, api_key: str = None):
        """Инициализация Groq AI"""
        self.api_key = api_key or config.GROQ_API_KEY
        if self.api_key:
            self.client = Groq(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("Groq API ключ не установлен")

    def generate_post(self, topic: str, style: str = 'motivational') -> dict:
        """
        Генерация поста по теме и стилю

        Args:
            topic: Тема поста
            style: Стиль поста (motivational, educational, news, entertaining, sales, personal)

        Returns:
            dict: {'title': str, 'content': str, 'image_prompt': str}
        """
        if not self.client:
            return {
                'title': 'Ошибка',
                'content': 'Gemini API ключ не установлен',
                'image_prompt': ''
            }

        # Промпты для разных стилей
        style_prompts = {
            'motivational': 'Напиши мотивационный пост, который вдохновляет и призывает к действию. Используй энергичный тон.',
            'educational': 'Напиши образовательный пост с полезной информацией. Используй структурированный, экспертный тон.',
            'news': 'Напиши новостной пост. Используй нейтральный, фактический, лаконичный тон.',
            'entertaining': 'Напиши развлекательный пост. Используй дружелюбный, весёлый, непринуждённый тон.',
            'sales': 'Напиши продающий пост. Используй убедительный тон, ориентированный на выгоду, с призывом к действию.',
            'personal': 'Напиши пост в стиле личного блога. Используй искренний, личный, эмоциональный тон.'
        }

        style_instruction = style_prompts.get(style, style_prompts['motivational'])

        prompt = f"""
{style_instruction}

Тема: {topic}

Требования:
1. Заголовок: короткий и цепляющий (до 60 символов)
2. Содержание: 150-300 слов, разбитое на абзацы
3. Используй эмодзи для визуального оформления (но не переборщи)
4. В конце добавь призыв к действию или вопрос для вовлечения

Формат ответа (строго соблюдай):
ЗАГОЛОВОК: [заголовок поста]
СОДЕРЖАНИЕ:
[текст поста]
ПРОМПТ_ДЛЯ_КАРТИНКИ: [короткое описание для генерации изображения на английском]
"""

        try:
            # Используем Groq API с моделью llama-3.3-70b-versatile
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1024
            )
            text = response.choices[0].message.content

            # Парсим ответ
            title = ''
            content = ''
            image_prompt = ''

            lines = text.split('\n')
            current_section = None

            for line in lines:
                if line.startswith('ЗАГОЛОВОК:'):
                    title = line.replace('ЗАГОЛОВОК:', '').strip()
                    current_section = 'title'
                elif line.startswith('СОДЕРЖАНИЕ:'):
                    current_section = 'content'
                elif line.startswith('ПРОМПТ_ДЛЯ_КАРТИНКИ:'):
                    image_prompt = line.replace('ПРОМПТ_ДЛЯ_КАРТИНКИ:', '').strip()
                    current_section = 'image'
                elif current_section == 'content' and line.strip():
                    content += line + '\n'

            content = content.strip()

            # Если парсинг не удался, используем весь текст как контент
            if not content:
                content = text
                title = topic

            logger.info(f"Пост успешно сгенерирован для темы: {topic}")

            return {
                'title': title or topic,
                'content': content,
                'image_prompt': image_prompt or topic
            }

        except Exception as e:
            logger.error(f"Ошибка генерации поста: {e}")
            return {
                'title': 'Ошибка генерации',
                'content': f'Не удалось сгенерировать пост: {str(e)}',
                'image_prompt': ''
            }

    def improve_post(self, content: str, instruction: str) -> str:
        """
        Улучшение существующего поста по инструкции

        Args:
            content: Текущий контент поста
            instruction: Инструкция по улучшению

        Returns:
            str: Улучшенный контент
        """
        if not self.client:
            return content

        prompt = f"""
Улучши следующий пост согласно инструкции.

Текущий пост:
{content}

Инструкция: {instruction}

Верни только улучшенный текст поста, без дополнительных комментариев.
"""

        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=512
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Ошибка улучшения поста: {e}")
            return content
