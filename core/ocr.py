import pytesseract
from PIL import Image

def recognize_text(image_path):
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img, lang='rus+eng')
    return text.strip()
