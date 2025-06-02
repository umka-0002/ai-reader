from core.preprocessing import preprocess_image
from core.ocr import recognize_text
from core.postprocess import clean_text
from core.ai_corrector import correct_text
from core.utils import ensure_dir
import os

def process_card(image_path, output_base_dir="data/results"):
    ensure_dir(output_base_dir)

    # Предобработка
    processed_image = preprocess_image(image_path)
    processed_path = image_path.replace("raw", "processed")
    ensure_dir(os.path.dirname(processed_path))
    cv2.imwrite(processed_path, processed_image)

    # OCR
    raw_text = recognize_text(processed_path)
    cleaned_text = clean_text(raw_text)

    # GPT/Деепсик постобработка
    structured_text = correct_text(cleaned_text)

    # Сохранение
    basename = os.path.basename(image_path).split('.')[0]
    result_path = os.path.join(output_base_dir, f"{basename}.txt")
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(structured_text)

    return structured_text

if __name__ == "__main__":
    test_image = "data/raw/test_card.jpg"
    process_card(test_image)
