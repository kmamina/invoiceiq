"""
schema_demo.py
Shows how the Invoice schema behaves with good and bad data.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from schemas import Invoice

BASE_DIR = Path(__file__).resolve().parent.parent
TRUTH_DIR = BASE_DIR / "data" / "ground_truth"

print("=" * 60)
print("TEST 1: Load all 5 answer-key files into the schema")
print("=" * 60)
for json_file in sorted(TRUTH_DIR.glob("*.json")):
    data = json.loads(json_file.read_text(encoding="utf-8"))
    invoice = Invoice(**data)
    print(
        f"{invoice.invoice_number} | date: {invoice.invoice_date} "
        f"({type(invoice.invoice_date).__name__}) | total: {invoice.total} "
        f"| {len(invoice.line_items)} line items"
    )

print()
print("=" * 60)
print("TEST 2: Pydantic converts text into the right types")
print("=" * 60)
invoice = Invoice(total="255.00", invoice_date="2026-03-14")
print("total       :", invoice.total, "->", type(invoice.total).__name__)
print("invoice_date:", invoice.invoice_date, "->", type(invoice.invoice_date).__name__)

print()
print("=" * 60)
print("TEST 3: Bad data is rejected with a clear message")
print("=" * 60)
try:
    Invoice(total="abc")
except ValidationError as error:
    print(error)

print()
print("=" * 60)
print("TEST 4: Missing fields become None (no crash, no invented values)")
print("=" * 60)
print(Invoice().model_dump())