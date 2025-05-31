import os
from pdf2image import convert_from_path
from pytesseract import pytesseract


def pdf_images_to_text(pdf_path: str, dpi: int = 300, lang: str = 'eng') -> str:
    """
    1) Convert each PDF page to a PIL Image using pdf2image.
    2) Run Tesseract OCR on that image (with pytesseract).
    3) Return a single string containing concatenated text from all pages.
    """

    # This call uses Poppler under the hood, so make sure pdftoppm is installed
    pages = convert_from_path(pdf_path, dpi=dpi, fmt='jpeg')

    all_text = []
    for page_num, pil_img in enumerate(pages, start=1):
        # If your PDF is black‐and‐white scans only, you can skip this. But
        # sometimes converting to grayscale helps Tesseract:
        # pil_img = pil_img.convert("L")

        # Run Tesseract. lang='rus' for Russian, 'eng' for English, etc.
        page_text = pytesseract.image_to_string(pil_img, lang=lang)

        all_text.append(f"----- Page {page_num} -----\n")
        all_text.append(page_text)
        all_text.append("\n\n")

    return "".join(all_text)


if __name__ == "__main__":
    # Example usage: if your file is in the same directory as this script,
    # otherwise pass a full or relative path.
    pdf_filename = "transfer-receipt-№13_716407545724527521.pdf"

    if not os.path.exists(pdf_filename):
        print(f"ERROR: File not found: {pdf_filename}")
        exit(1)

    # We specify lang='rus' since your receipt is in Russian.
    extracted = pdf_images_to_text(pdf_filename, dpi=300, lang='rus')

    # Print to console (this can be large)
    print(extracted)

    print("OCR output written to extracted_receipt.txt")
