import os
from pdf2image import convert_from_path
from pytesseract import pytesseract


def pdf_images_to_text(pdf_path: str, dpi: int = 300, lang: str = 'eng') -> str:
    """
    1) Convert each PDF page to a PIL Image using pdf2image.
    2) Run Tesseract OCR on that image (with pytesseract).
    3) Return a single string containing concatenated text from all pages.
    """

    pages = convert_from_path(pdf_path, dpi=dpi, fmt='jpeg')

    all_text = []
    for page_num, pil_img in enumerate(pages, start=1):
        page_text = pytesseract.image_to_string(pil_img, lang=lang)

        all_text.append(f"----- Page {page_num} -----\n")
        all_text.append(page_text)
        all_text.append("\n\n")
    text = "\n".join(all_text)
    return text
