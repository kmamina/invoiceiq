"""
run_pipeline.py
Part 1: run every invoice PDF through the pipeline.
Part 2: three test cases that should NOT be approved.
Part 3: read back the audit trail for one invoice.
The invoice history is reset at the start. The audit log is never wiped.
"""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from audit import get_events
from build_db import build
from pipeline import ELIGIBLE, FLAG, HUMAN, get_invoice, process_pdf, route_invoice

BASE_DIR = Path(__file__).resolve().parent.parent
INVOICE_DIR = BASE_DIR / "data" / "invoices"


def print_result(result):
    print(f"{result['name']}: {result['route']}")
    for reason in result["reasons"]:
        print(f"    - {reason}")


pdf_files = sorted(INVOICE_DIR.glob("*.pdf"))
if not pdf_files:
    raise SystemExit("No PDFs in data\\invoices. Run python src\\generate_invoices.py first.")

build()  # fresh vendor master, POs and an empty invoice history
print()

run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
print("Run id:", run_id)

print()
print("=" * 60)
print("PART 1: Process all invoice PDFs")
print("=" * 60)
results = []
for pdf_file in pdf_files:
    result = process_pdf(pdf_file, run_id)
    print_result(result)
    results.append(result)

counts = Counter(r["route"] for r in results)
print()
print("Summary:")
for route in (ELIGIBLE, FLAG, HUMAN):
    print(f"  {route}: {counts.get(route, 0)}")

print()
print("=" * 60)
print("PART 2: Test cases that should NOT be approved")
print("=" * 60)
first_name = pdf_files[0].stem
base, _ = get_invoice(pdf_files[0])

test_cases = [
    ("TEST resubmitted invoice", base),
    ("TEST missing TRN", base.model_copy(update={"invoice_number": "INV-TEST-0001", "trn": None})),
    ("TEST total +100", base.model_copy(update={"invoice_number": "INV-TEST-0002", "total": base.total + 100})),
]
for name, invoice in test_cases:
    print_result(route_invoice(invoice, name, run_id, "test case"))

print()
print("=" * 60)
print(f"PART 3: Audit trail for {first_name}")
print("=" * 60)
events = get_events(run_id, first_name)
print(f"{len(events)} events saved:")
for event in events:
    details = json.loads(event["details"])
    if event["event_type"] == "check":
        label = f"{details['name']} -> {'PASS' if details['passed'] else 'FAIL'}"
    elif event["event_type"] == "decision":
        label = f"route = {details['route']}"
    else:
        label = f"loaded from {details['source']}"
    print(f"  {event['event_type']:<10} {label}")