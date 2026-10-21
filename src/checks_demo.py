"""
checks_demo.py
Test 1: the real extracted invoices (all 11 checks should pass).
Test 2: invoices broken in ways that only the invoice itself can show.
Test 3: invoices broken in ways that need the database to detect.
The database is reset first, so you can run this as often as you like.
"""

from datetime import timedelta
from pathlib import Path

from build_db import build
from checks import run_all_checks
from db import record_processed
from schemas import Invoice

BASE_DIR = Path(__file__).resolve().parent.parent
EXTRACT_DIR = BASE_DIR / "data" / "extracted"


def show(title, invoice):
    results = run_all_checks(invoice)
    failed = [r for r in results if not r.passed]
    if not failed:
        print(f"{title}: all {len(results)} checks passed")
    else:
        print(f"{title}: {len(failed)} check(s) FAILED")
        for r in failed:
            print(f"    - {r.name}: {r.message}")


def add_one_unit(invoice):
    """Bill one extra unit on line 1 and fix ALL the maths, so the invoice is
    internally consistent. Only the PO amount can reveal the over-billing."""
    items = [item.model_copy() for item in invoice.line_items]
    first = items[0]
    new_quantity = first.quantity + 1
    items[0] = first.model_copy(
        update={"quantity": new_quantity, "line_total": round(new_quantity * first.unit_price, 2)}
    )
    subtotal = round(sum(item.line_total for item in items), 2)
    vat = round(subtotal * 0.05, 2)
    return invoice.model_copy(
        update={"line_items": items, "subtotal": subtotal, "vat": vat, "total": round(subtotal + vat, 2)}
    )


build()  # start from a fresh, empty database
print()

files = sorted(EXTRACT_DIR.glob("*.json"))
if not files:
    raise SystemExit("No files in data\\extracted. Run python src\\extract.py first.")
invoices = [(f.stem, Invoice.model_validate_json(f.read_text(encoding="utf-8"))) for f in files]
base_name, base = invoices[0]

print("=" * 60)
print("TEST 1: Real extracted invoices (all checks should pass)")
print("=" * 60)
for name, invoice in invoices:
    show(name, invoice)

print()
print("=" * 60)
print(f"TEST 2: Errors visible on the invoice itself ({base_name})")
print("=" * 60)

show("Wrong total (+100)", base.model_copy(update={"total": base.total + 100}))

wrong_vat = round(base.subtotal * 0.10, 2)
show(
    "VAT charged at 10%",
    base.model_copy(update={"vat": wrong_vat, "total": round(base.subtotal + wrong_vat, 2)}),
)

show("Missing TRN", base.model_copy(update={"trn": None}))

items = [item.model_copy() for item in base.line_items]
items[0] = items[0].model_copy(update={"line_total": items[0].line_total + 50})
show("Line 1 total wrong (+50)", base.model_copy(update={"line_items": items}))

show(
    "Due date before invoice date",
    base.model_copy(update={"due_date": base.invoice_date - timedelta(days=5)}),
)

print()
print("=" * 60)
print(f"TEST 3: Errors that need the database ({base_name})")
print("=" * 60)

show("Vendor not in master (unknown TRN)", base.model_copy(update={"trn": "100000000000000"}))
show("Vendor name does not match its TRN", base.model_copy(update={"vendor": "Fake Trading LLC"}))
show("PO number does not exist", base.model_copy(update={"po_number": "PO-9999"}))
show("Over-billed (maths correct, but above the PO)", add_one_unit(base))

record_processed(base, "approved")  # pretend we already handled this invoice
show("Same invoice sent a second time", base)