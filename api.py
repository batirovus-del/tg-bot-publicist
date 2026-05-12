from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
from datetime import datetime
import asyncio
from telegram import Bot
from telegram.error import TelegramError
import config

app = Flask(__name__)
CORS(app)

POSTS_FILE = 'posts_data.json'
IMAGES_DIR = 'images'

# Создаем папку для картинок
os.makedirs(IMAGES_DIR, exist_ok=True)


def load_posts():
    """Загрузка постов из JSON"""
    try:
        with open(POSTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"posts": []}


def save_posts(data):
    """Сохранение постов в JSON"""
    with open(POSTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.route('/api/posts', methods=['GET'])
def get_posts():
    """Получить все посты"""
    data = load_posts()
    return jsonify(data)


@app.route('/api/posts', methods=['POST'])
def add_post():
    """Добавить новый пост"""
    try:
        data = load_posts()

        # Получаем данные из формы
        title = request.form.get('title')
        content = request.form.get('content')
        image_query = request.form.get('image_query', '')

        # Обработка загруженной картинки
        image_url = None
        if 'image' in request.files:
            image = request.files['image']
            if image.filename:
                # Генерируем уникальное имя файла
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{image.filename}"
                filepath = os.path.join(IMAGES_DIR, filename)
                image.save(filepath)
                image_url = f"/images/{filename}"

        # Определяем следующий день
        existing_days = [p['day'] for p in data['posts']]
        next_day = max(existing_days) + 1 if existing_days else 1

        # Создаем новый пост
        new_post = {
            "day": next_day,
            "title": title,
            "content": content,
            "image_query": image_query,
            "image_url": image_url,
            "created_at": datetime.now().isoformat()
        }

        data['posts'].append(new_post)
        save_posts(data)

        return jsonify({"success": True, "post": new_post})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/posts/<int:day>', methods=['PUT'])
def update_post(day):
    """Обновить пост"""
    try:
        data = load_posts()

        # Находим пост
        post = next((p for p in data['posts'] if p['day'] == day), None)
        if not post:
            return jsonify({"success": False, "error": "Post not found"}), 404

        # Обновляем данные
        if 'title' in request.form:
            post['title'] = request.form['title']
        if 'content' in request.form:
            post['content'] = request.form['content']
        if 'image_query' in request.form:
            post['image_query'] = request.form['image_query']

        # Обработка новой картинки
        if 'image' in request.files:
            image = request.files['image']
            if image.filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{image.filename}"
                filepath = os.path.join(IMAGES_DIR, filename)
                image.save(filepath)
                post['image_url'] = f"/images/{filename}"

        post['updated_at'] = datetime.now().isoformat()
        save_posts(data)

        return jsonify({"success": True, "post": post})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/posts/<int:day>', methods=['DELETE'])
def delete_post(day):
    """Удалить пост"""
    try:
        data = load_posts()
        data['posts'] = [p for p in data['posts'] if p['day'] != day]
        save_posts(data)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/publish/<int:day>', methods=['POST'])
def publish_post(day):
    """Опубликовать пост немедленно"""
    try:
        data = load_posts()
        post = next((p for p in data['posts'] if p['day'] == day), None)

        if not post:
            return jsonify({"success": False, "error": "Post not found"}), 404

        # Формируем текст поста
        post_text = f"""БИСМИЛЛАХ

{post['content']}

ИНШААЛЛАХ"""

        # Отправляем пост
        bot = Bot(token=config.BOT_TOKEN)

        async def send():
            if post.get('image_url'):
                # Если есть загруженная картинка
                image_path = post['image_url'].replace('/images/', '')
                with open(os.path.join(IMAGES_DIR, image_path), 'rb') as photo:
                    await bot.send_photo(
                        chat_id=config.CHANNEL_ID,
                        photo=photo,
                        caption=post_text,
                        parse_mode='Markdown'
                    )
            elif post.get('image_query'):
                # Если есть запрос для Unsplash
                image_url = f"https://source.unsplash.com/1200x630/?{post['image_query']}"
                await bot.send_photo(
                    chat_id=config.CHANNEL_ID,
                    photo=image_url,
                    caption=post_text,
                    parse_mode='Markdown'
                )
            else:
                # Только текст
                await bot.send_message(
                    chat_id=config.CHANNEL_ID,
                    text=post_text,
                    parse_mode='Markdown'
                )

        asyncio.run(send())

        return jsonify({"success": True, "message": "Post published successfully"})
    except TelegramError as e:
        return jsonify({"success": False, "error": f"Telegram error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/images/<path:filename>')
def serve_image(filename):
    """Отдача загруженных картинок"""
    return send_from_directory(IMAGES_DIR, filename)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
