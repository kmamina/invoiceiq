"""
db_demo.py
Tries every lookup function on your real extracted invoices.
Running it resets the database first, so you can run it as often as you like.
"""

from pathlib import Path

from build_db import build
from db import (
    find_duplicate,
    find_po,
    find_vendor_by_trn,
    get_vendor_history,
    query_all,
    record_processed,
)
from schemas import Invoice

BASE_DIR = Path(__file__).resolve().parent.parent
EXTRACT_DIR = BASE_DIR / "data" / "extracted"

build()  # start from a fresh database
print()

files = sorted(EXTRACT_DIR.glob("*.json"))
if not files:
    raise SystemExit("No files in data\\extracted. Run python src\\extract.py first.")
invoices = [Invoice.model_validate_json(f.read_text(encoding="utf-8")) for f in files]
first = invoices[0]

print("=" * 60)
print("TEST 1: Is the vendor in the vendor master?")
print("=" * 60)
vendor = find_vendor_by_trn(first.trn)
print("Real TRN    :", vendor["name"] if vendor else "NOT FOUND")
unknown = find_vendor_by_trn("100000000000000")
print("Made-up TRN :", unknown["name"] if unknown else "NOT FOUND")

print()
print("=" * 60)
print("TEST 2: Does the purchase order exist?")
print("=" * 60)
po = find_po(first.po_number)
if po:
    print(f"{po['po_number']}: PO amount {po['po_amount']:,.2f} AED | invoice total {first.total:,.2f} AED")
else:
    print("PO NOT FOUND")
print("PO-9999     :", "FOUND" if find_po("PO-9999") else "NOT FOUND")

print()
print("=" * 60)
print("TEST 3: Duplicate check")
print("=" * 60)
print("Before processing:", "DUPLICATE" if find_duplicate(first.invoice_number, first.trn) else "not a duplicate")
for invoice in invoices:
    record_processed(invoice, "approved")
dup = find_duplicate(first.invoice_number, first.trn)
print("After processing :", f"DUPLICATE (earlier decision: {dup['decision']})" if dup else "not a duplicate")
print("Vendor history   :", len(get_vendor_history(first.trn)), "invoice(s) from this vendor")

print()
print("=" * 60)
print("TEST 4: A first SQL summary query")
print("=" * 60)
rows = query_all(
    """
    SELECT vendor_name, COUNT(*) AS invoice_count, SUM(total) AS total_amount
    FROM processed_invoices
    GROUP BY vendor_name
    ORDER BY total_amount DESC
    """
)
for row in rows:
    print(f"{row['vendor_name']}: {row['invoice_count']} invoice(s), {row['total_amount']:,.2f} AED")