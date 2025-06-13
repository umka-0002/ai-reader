from core.preprocessing import preprocess_image
from core.ocr import recognize_text
from core.postprocess import clean_text
from core.ai_corrector import correct_text
from core.utils import ensure_dir
import cv2
import os
import re
from typing import Dict, List, Any

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

def validate_card_data(card_data: Dict[str, Any]) -> List[str]:
    """
    Validates the processed card data and returns a list of validation errors.
    
    Args:
        card_data: Dictionary containing the processed card data
        
    Returns:
        List of validation error messages. Empty list if no errors found.
    """
    errors = []
    
    # Check if required fields are present
    required_fields = ['processed_text', 'original_text', 'fields']
    for field in required_fields:
        if field not in card_data:
            errors.append(f"Missing required field: {field}")
    
    # Validate processed text
    if 'processed_text' in card_data:
        text = card_data['processed_text']
        if not text or len(text.strip()) == 0:
            errors.append("Processed text is empty")
        elif len(text) < 10:  # Arbitrary minimum length
            errors.append("Processed text is too short")
    
    # Validate original text
    if 'original_text' in card_data:
        text = card_data['original_text']
        if not text or len(text.strip()) == 0:
            errors.append("Original text is empty")
    
    # Validate fields
    if 'fields' in card_data:
        fields = card_data['fields']
        if not isinstance(fields, dict):
            errors.append("Fields must be a dictionary")
        else:
            # Check for empty field values
            for field_name, value in fields.items():
                if not value or len(str(value).strip()) == 0:
                    errors.append(f"Empty value for field: {field_name}")
    
    # Validate status
    if 'status' in card_data:
        valid_statuses = ['new', 'verified', 'rejected']
        if card_data['status'] not in valid_statuses:
            errors.append(f"Invalid status: {card_data['status']}")
    
    return errors

if __name__ == "__main__":
    test_image = "data/raw/test_card.jpg"
    process_card(test_image)
