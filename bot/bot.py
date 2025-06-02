import os
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from core.ocr import recognize_text

API_TOKEN = os.getenv("BOT_TOKEN")  # Use environment variable!

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

IMAGE_DIR = "images"
os.makedirs(IMAGE_DIR, exist_ok=True)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("👋 Привет! Отправьте фото карточки, и я распознаю текст.")

@dp.message()
async def handle_message(message: Message):
    if not message.photo:
        await message.answer("📷 Пожалуйста, отправьте фото карточки.")
        return

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_path = file.file_path
    photo_bytes = await bot.download_file(file_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    img_filename = f"photo_{timestamp}_{message.from_user.id}.jpg"
    img_path = os.path.join(IMAGE_DIR, img_filename)
    with open(img_path, "wb") as f:
        f.write(photo_bytes.read())

    loop = asyncio.get_running_loop()
    try:
        text = await loop.run_in_executor(None, recognize_text, img_path)
    except Exception as e:
        await message.answer(f"❗ Ошибка при распознавании: {e}")
        return

    txt_filename = img_filename.replace('.jpg', '.txt')
    txt_path = os.path.join(IMAGE_DIR, txt_filename)
    with open(txt_path, "w", encoding="utf-8") as txt_file:
        txt_file.write(text)

    if text.strip():
        await message.answer("📝 Распознанный текст:\n\n" + text, parse_mode=None)
    else:
        await message.answer("❗ Не удалось распознать текст. Попробуйте отправить фото чётче.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


# python -m bot.bot
# Запускать этот файл для запуска бота
