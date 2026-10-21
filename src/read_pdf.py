"""
read_pdf.py
Reads the text out of a text-based invoice PDF using pdfplumber.
"""

import sys
from pathlib import Path

import pdfplumber

BASE_DIR = Path(__file__).resolve().parent.parent
INVOICE_DIR = BASE_DIR / "data" / "invoices"


def extract_text(pdf_path):
    """Open a PDF and return all its text as one string."""
    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""  # empty string if the page has no text
            pages_text.append(text)
    return "\n".join(pages_text)


if __name__ == "__main__":
    # If you type a file name after the command, use it. Otherwise use invoice 1.
    if len(sys.argv) > 1:
        first_pdf = Path(sys.argv[1])
    else:
        first_pdf = INVOICE_DIR / "INV-2026-0001.pdf"

    print("=" * 60)
    print("TEXT FROM:", first_pdf.name)
    print("=" * 60)
    print(extract_text(first_pdf))

    print()
    print("=" * 60)
    print("CHECK ALL INVOICES")
    print("=" * 60)
    for pdf_file in sorted(INVOICE_DIR.glob("*.pdf")):
        text = extract_text(pdf_file)
        print(f"{pdf_file.name}: {len(text)} characters read")