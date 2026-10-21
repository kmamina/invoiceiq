"""
run_agent_demo.py
Sends three problem invoices through the pipeline WITH the agent turned on.
Each one needs several Gemini calls, so this takes a few minutes.
"""

from datetime import datetime
from pathlib import Path

from audit import query_all
from build_db import build
from pipeline import ELIGIBLE, get_invoice, route_invoice

BASE_DIR = Path(__file__).resolve().parent.parent
INVOICE_DIR = BASE_DIR / "data" / "invoices"


def print_result(result):
    print(f"\n{result['name']}: {result['route']}")
    for reason in result["reasons"]:
        print(f"    - {reason}")
    if result["explanation"]:
        print("\n  AGENT REPORT:")
        for line in result["explanation"].splitlines():
            print("  " + line)
    elif result["route"] == ELIGIBLE:
        print("    (eligible, so no investigation is needed)")


pdf_files = sorted(INVOICE_DIR.glob("*.pdf"))
if not pdf_files:
    raise SystemExit("No PDFs in data\\invoices. Run python src\\generate_invoices.py first.")

build()  # fresh vendor master, POs and an empty invoice history
run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
print("Run id:", run_id)

base, _ = get_invoice(pdf_files[0])

# First, a normal invoice. It should pass, so no agent is needed.
print_result(route_invoice(base, "INV-2026-0001 (normal)", run_id, "saved result", use_agent=True))

# Case 1: the same invoice sent again
print("\n" + "=" * 60)
print("CASE 1: the same invoice is sent a second time")
print("=" * 60)
print_result(route_invoice(base, "CASE 1 resubmitted", run_id, "test case", use_agent=True))

# Case 2: VAT charged at 10% instead of 5%
print("\n" + "=" * 60)
print("CASE 2: VAT charged at 10%")
print("=" * 60)
wrong_vat = round(base.subtotal * 0.10, 2)
case2 = base.model_copy(
    update={
        "invoice_number": "INV-TEST-0002",
        "vat": wrong_vat,
        "total": round(base.subtotal + wrong_vat, 2),
    }
)
print_result(route_invoice(case2, "CASE 2 wrong VAT", run_id, "test case", use_agent=True))

# Case 3: a vendor that is not in the vendor master
print("\n" + "=" * 60)
print("CASE 3: unknown vendor")
print("=" * 60)
case3 = base.model_copy(
    update={
        "invoice_number": "INV-TEST-0003",
        "trn": "100000000000000",
        "vendor": "Sunrise Trading FZE",
    }
)
print_result(route_invoice(case3, "CASE 3 unknown vendor", run_id, "test case", use_agent=True))

# How many tool calls did the agent make, according to the audit log?
count = query_all(
    "SELECT COUNT(*) AS n FROM audit_log WHERE run_id = ? AND event_type = 'tool_call'",
    (run_id,),
)[0]["n"]
print("\n" + "=" * 60)
print(f"The audit log recorded {count} tool call(s) in this run.")
print("=" * 60)