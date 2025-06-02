import re

def clean_text(text):
    text = text.replace('\n', ' ').strip()
    text = re.sub(r'\s+', ' ', text)
    return text