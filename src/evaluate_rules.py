"""
evaluate_rules.py
Runs the 13 rules on the ANSWER KEYS (perfect extraction, no AI at all)
and measures how well the rule engine catches the planted errors.
It also saves a spreadsheet (CSV) with one row per invoice.
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

from build_db import build
from checks import run_all_checks
from db import record_processed
from routing import ELIGIBLE, decide
from schemas import Invoice

BASE_DIR = Path(__file__).resolve().parent.parent
TRUTH_DIR = BASE_DIR / "data" / "ground_truth"
EVAL_DIR = BASE_DIR / "data" / "eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)

files = sorted(TRUTH_DIR.glob("*.json"))
if not files:
    raise SystemExit("No answer keys found. Run python src\\generate_dataset.py first.")

build()  # fresh vendor master, POs and an empty invoice history
print()

rows = []
for json_file in files:  # in invoice order, so duplicates come after their originals
    truth = json.loads(json_file.read_text(encoding="utf-8"))
    invoice = Invoice(**truth)
    results = run_all_checks(invoice)
    route, reasons = decide(results)
    record_processed(invoice, route)
    labels = truth["labels"]
    rows.append(
        {
            "stem": json_file.stem,
            "kind": labels["error_type"],
            "expected": labels["expected_route"],
            "predicted": route,
            "failed": ";".join(r.name for r in results if not r.passed),
        }
    )

# ---------- the numbers ----------
errors = [r for r in rows if r["expected"] != ELIGIBLE]        # should NOT be auto-approved
clean = [r for r in rows if r["expected"] == ELIGIBLE]         # should pass
caught = [r for r in errors if r["predicted"] != ELIGIBLE]
false_approvals = [r for r in errors if r["predicted"] == ELIGIBLE]
false_alarms = [r for r in clean if r["predicted"] != ELIGIBLE]
stopped = len(caught) + len(false_alarms)
exact = sum(1 for r in rows if r["predicted"] == r["expected"])

print("=" * 60)
print("RESULTS: rules only, perfect extraction, no AI")
print("=" * 60)
print(f"Invoices                      : {len(rows)} ({len(clean)} should pass, {len(errors)} have a planted error)")
print(f"Error recall                  : {len(caught)} of {len(errors)} caught ({len(caught) / len(errors):.1%})")
print(f"Precision                     : {len(caught)} of {stopped} stopped invoices were real errors "
      f"({(len(caught) / stopped if stopped else 0):.1%})")
print(f"FALSE APPROVALS               : {len(false_approvals)}  (errors that would have been approved)")
print(f"False alarms                  : {len(false_alarms)}  (clean invoices that were stopped)")
print(f"Straight-through rate (clean) : {len(clean) - len(false_alarms)} of {len(clean)} "
      f"({(len(clean) - len(false_alarms)) / len(clean):.1%})")
print(f"Exact route match             : {exact} of {len(rows)} ({exact / len(rows):.1%})")

print()
print(f"{'Type':<28}{'Invoices':>9}{'As expected':>13}")
by_kind = defaultdict(list)
for r in rows:
    by_kind[r["kind"]].append(r)
for kind, group in by_kind.items():
    right = sum(1 for r in group if r["predicted"] == r["expected"])
    print(f"{kind:<28}{len(group):>9}{right:>13}")

wrong = [r for r in rows if r["predicted"] != r["expected"]]
if wrong:
    print()
    print("INVOICES WITH THE WRONG ROUTE:")
    for r in wrong:
        print(f"  {r['stem']} ({r['kind']}): expected {r['expected']}, got {r['predicted']}, failed checks: {r['failed'] or 'none'}")

# ---------- save a spreadsheet ----------
csv_path = EVAL_DIR / "rules_only_results.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["invoice", "error_type", "expected_route", "predicted_route", "route_correct", "failed_checks"])
    for r in rows:
        writer.writerow([r["stem"], r["kind"], r["expected"], r["predicted"], r["predicted"] == r["expected"], r["failed"]])
print()
print("Saved:", csv_path)