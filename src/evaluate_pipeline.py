r"""
evaluate_pipeline.py
Step 14, part 3: the real test.
Runs the 13 rules on Gemini's EXTRACTED data (not the answer keys) and compares the
route with the expected route. Then puts it next to the rules-only result from Step 13.
No Gemini calls: it only reads data/extracted, so it is fast and repeatable.
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from build_db import build
from checks import run_all_checks
from db import record_processed
from routing import ELIGIBLE, HUMAN, decide
from schemas import Invoice

BASE_DIR = Path(__file__).resolve().parent.parent
TRUTH_DIR = BASE_DIR / "data" / "ground_truth"
EXTRACT_DIR = BASE_DIR / "data" / "extracted"
EVAL_DIR = BASE_DIR / "data" / "eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)

FIELDS = [
    "invoice_number", "vendor", "trn", "po_number", "invoice_date",
    "due_date", "payment_terms", "currency", "subtotal", "vat", "total",
]

parser = argparse.ArgumentParser()
parser.add_argument("--allow-missing", action="store_true",
                    help="treat invoices that were never extracted as extraction failures (HUMAN_REVIEW)")
args = parser.parse_args()


def same(a, b):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 0.005
    return a == b


def diffs(extracted, truth):
    out = [f"{f}: expected {getattr(truth, f)!r}, got {getattr(extracted, f)!r}"
           for f in FIELDS if not same(getattr(extracted, f), getattr(truth, f))]
    items_ok = len(extracted.line_items) == len(truth.line_items) and all(
        same(a.quantity, b.quantity) and same(a.unit_price, b.unit_price) and same(a.line_total, b.line_total)
        for a, b in zip(extracted.line_items, truth.line_items)
    )
    if not items_ok:
        out.append("line_items differ")
    return out


files = sorted(TRUTH_DIR.glob("*.json"))
if not files:
    raise SystemExit("No answer keys found. Run python src\\generate_dataset.py first.")

not_extracted = [f.stem for f in files if not (EXTRACT_DIR / f"{f.stem}.json").exists()]
if not_extracted and not args.allow_missing:
    raise SystemExit(
        f"{len(not_extracted)} invoices are not extracted yet. Finish python src\\extract_batch.py first,\n"
        "or run this script with --allow-missing to count them as extraction failures."
    )

# rules-only results from Step 13, for the side-by-side table
rules_only = {}
rules_csv = EVAL_DIR / "rules_only_results.csv"
if rules_csv.exists():
    with open(rules_csv, newline="", encoding="utf-8") as file:
        rules_only = {r["invoice"]: r for r in csv.DictReader(file)}

build()  # fresh vendor master, POs and an empty invoice history
print()

rows = []
for json_file in files:  # invoice order, so duplicates come after their originals
    stem = json_file.stem
    truth_data = json.loads(json_file.read_text(encoding="utf-8"))
    truth = Invoice(**truth_data)
    labels = truth_data["labels"]
    saved = EXTRACT_DIR / f"{stem}.json"

    if saved.exists():
        extracted = Invoice.model_validate_json(saved.read_text(encoding="utf-8"))
        results = run_all_checks(extracted)
        route, _ = decide(results)
        record_processed(extracted, route)
        failed = ";".join(r.name for r in results if not r.passed)
        field_diffs = diffs(extracted, truth)
    else:
        route, failed, field_diffs = HUMAN, "extraction_failed", ["not extracted"]

    rows.append({
        "stem": stem, "kind": labels["error_type"], "expected": labels["expected_route"],
        "predicted": route, "failed": failed, "diffs": field_diffs,
        "injected": bool(labels.get("injected")),
    })

errors = [r for r in rows if r["expected"] != ELIGIBLE]
clean = [r for r in rows if r["expected"] == ELIGIBLE]
caught = [r for r in errors if r["predicted"] != ELIGIBLE]
false_approvals = [r for r in errors if r["predicted"] == ELIGIBLE]
false_alarms = [r for r in clean if r["predicted"] != ELIGIBLE]
stopped = len(caught) + len(false_alarms)
exact = sum(1 for r in rows if r["predicted"] == r["expected"])

print("=" * 60)
print("RESULTS: full pipeline on AI-extracted data")
print("=" * 60)
if not_extracted:
    print(f"WARNING: {len(not_extracted)} invoices were not extracted and count as HUMAN_REVIEW.")
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
print(f"{'Type':<28}{'Invoices':>9}{'Rules only':>12}{'After AI':>10}")
by_kind = defaultdict(list)
for r in rows:
    by_kind[r["kind"]].append(r)
for kind, group in by_kind.items():
    after = sum(1 for r in group if r["predicted"] == r["expected"])
    before = sum(1 for r in group if rules_only.get(r["stem"], {}).get("route_correct") == "True")
    print(f"{kind:<28}{len(group):>9}{before:>12}{after:>10}")

if false_approvals:
    print()
    print("!!! FALSE APPROVALS (investigate these first) !!!")
    for r in false_approvals:
        print(f"  {r['stem']} ({r['kind']}): expected {r['expected']}, got {r['predicted']}")
        for d in r["diffs"]:
            print(f"      extraction difference -> {d}")
        if not r["diffs"]:
            print("      extraction was perfect, so a rule is missing or wrong")

if false_alarms:
    print()
    print(f"FALSE ALARMS (clean invoices that were stopped), first 15 of {len(false_alarms)}:")
    for r in false_alarms[:15]:
        print(f"  {r['stem']}: failed {r['failed']}; " + "; ".join(r["diffs"])[:200])

# Invoices that were right with perfect extraction but wrong after AI extraction
broke = [r for r in rows if rules_only.get(r["stem"], {}).get("route_correct") == "True"
         and r["predicted"] != r["expected"]]
print()
print(f"Invoices the AI extraction turned from right to wrong: {len(broke)}")

injected = [r for r in rows if r["injected"]]
if injected:
    print()
    print("PROMPT-INJECTION INVOICES:")
    for r in injected:
        verdict = "OK" if r["predicted"] == r["expected"] else "WRONG ROUTE"
        note = "extraction matched the answer key" if not r["diffs"] else "extraction differs: " + "; ".join(r["diffs"])[:150]
        print(f"  {r['stem']} ({r['kind']}): expected {r['expected']}, got {r['predicted']} -> {verdict}; {note}")

csv_path = EVAL_DIR / "pipeline_results.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["invoice", "error_type", "expected_route", "predicted_route", "route_correct",
                     "failed_checks", "extraction_differences"])
    for r in rows:
        writer.writerow([r["stem"], r["kind"], r["expected"], r["predicted"],
                         r["predicted"] == r["expected"], r["failed"], " | ".join(r["diffs"])])
print()
print("Saved:", csv_path)