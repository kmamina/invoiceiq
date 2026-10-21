"""
checks_demo.py
Test 1: run the checks on the real extracted invoices (should all pass).
Test 2: break an invoice on purpose and see that the right check catches it.
"""

from datetime import timedelta
from pathlib import Path

from checks import run_all_checks
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


# Load the extracted invoices
files = sorted(EXTRACT_DIR.glob("*.json"))
if not files:
    raise SystemExit("No files in data\\extracted. Run python src\\extract.py first.")
invoices = [(f.stem, Invoice.model_validate_json(f.read_text(encoding="utf-8"))) for f in files]

print("=" * 60)
print("TEST 1: Real extracted invoices (all checks should pass)")
print("=" * 60)
for name, invoice in invoices:
    show(name, invoice)

# Use the first invoice as the base for broken copies
base_name, base = invoices[0]

print()
print("=" * 60)
print(f"TEST 2: Broken copies of {base_name} (each should be caught)")
print("=" * 60)

# 1. Wrong total
show("Wrong total (+100)", base.model_copy(update={"total": base.total + 100}))

# 2. Wrong VAT: 10% instead of 5%, with the total changed to match
wrong_vat = round(base.subtotal * 0.10, 2)
show(
    "VAT charged at 10%",
    base.model_copy(update={"vat": wrong_vat, "total": round(base.subtotal + wrong_vat, 2)}),
)

# 3. Missing TRN
show("Missing TRN", base.model_copy(update={"trn": None}))

# 4. One line total is wrong (+50)
items = [item.model_copy() for item in base.line_items]
items[0] = items[0].model_copy(update={"line_total": items[0].line_total + 50})
show("Line 1 total wrong (+50)", base.model_copy(update={"line_items": items}))

# 5. Due date before the invoice date
show(
    "Due date before invoice date",
    base.model_copy(update={"due_date": base.invoice_date - timedelta(days=5)}),
)