"""
llm_hello.py
Our first call to an LLM (Gemini).
Test 1: a simple question.
Test 2: give it the text of one invoice and ask about it.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from read_pdf import extract_text

BASE_DIR = Path(__file__).resolve().parent.parent
INVOICE_DIR = BASE_DIR / "data" / "invoices"

# Load the key from the .env file
load_dotenv(BASE_DIR / ".env")
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("GEMINI_API_KEY not found. Check your .env file and save it.")

client = genai.Client(api_key=api_key)
MODEL = "gemini-3.8-flash"

print("=" * 60)
print("TEST 1: A simple question")
print("=" * 60)
response = client.models.generate_content(
    model=MODEL,
    contents="In one short sentence, what is a supplier invoice?",
)
print(response.text)

print()
print("=" * 60)
print("TEST 2: Ask about a real (fake) invoice")
print("=" * 60)
invoice_text = extract_text(INVOICE_DIR / "INV-2026-0001.pdf")

prompt = f"""Below is the text of an invoice.
Tell me the invoice number, the vendor name, and the total amount.
Answer in 3 short lines.

INVOICE TEXT:
{invoice_text}
"""

response = client.models.generate_content(model=MODEL, contents=prompt)
print(response.text)