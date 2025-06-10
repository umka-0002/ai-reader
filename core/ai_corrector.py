import os
import logging
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

def correct_text(text):
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-11-20")  # подбери актуальный из Azure Portal

    client = AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=endpoint,
    )

    prompt = (
        "Исправь ошибки OCR и структурируй по полям: Автор, Название, Год, Город, Страницы.\n\n"
        + text
    )

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Ты полезный ассистент, исправляющий OCR ошибки."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,  # Параметр в Azure называется max_tokens, не max_completion_tokens
            temperature=0.7,
            model=deployment
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.exception("AI correction failed")
        return "Ошибка AI-коррекции: " + str(e)