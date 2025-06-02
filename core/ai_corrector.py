import openai
import os
import logging

openai.api_key = os.getenv("OPENAI_API_KEY")

def correct_text(text):
    prompt = f"Исправь ошибки OCR и структурируй по полям: Автор, Название, Год, Город, Страницы.\n\n{text}"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        logging.exception("AI correction failed")
        return "Ошибка AI-коррекции: " + str(e)