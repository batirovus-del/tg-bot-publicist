#!/usr/bin/env python3
import os
from google import genai

# API ключ
api_key = "AIzaSyAKBpT-_B8UkNKmZ4iZZWXYxuxXKdiOSmg"

# Создаём клиент
client = genai.Client(api_key=api_key)

print("Получаем список доступных моделей...")
try:
    # Получаем список моделей
    models = client.models.list()

    print("\nДоступные модели:")
    for model in models:
        print(f"- {model.name}")
        if hasattr(model, 'supported_generation_methods'):
            print(f"  Методы: {model.supported_generation_methods}")

except Exception as e:
    print(f"Ошибка: {e}")
