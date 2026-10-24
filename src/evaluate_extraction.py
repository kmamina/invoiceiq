r"""
evaluate_extraction.py
How accurate is Gemini's extraction? Compares every saved extraction with its answer key.
No Gemini calls, no internet: it only reads files, so you can run it any time.

    python src\evaluate_extraction.py              (main set)
    python src\evaluate_extraction.py --set hard   (Step 15 hard set)
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from schemas import Invoice

parser = argparse.ArgumentParser()
parser.add_argument("--set", choices=["main", "hard"], default="main")
args = parser.parse_args()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" if args.set == "main" else BASE_DIR / "data" / "hard"
TRUTH_DIR = DATA_DIR / "ground_truth"
EXTRACT_DIR = DATA_DIR / "extracted"
EVAL_DIR = BASE_DIR / "data" / "eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)
SUFFIX = "" if args.set == "main" else "_hard"

FIELDS = [
    "invoice_number", "vendor", "trn", "po_number", "invoice_date",
    "due_date", "payment_terms", "currency", "subtotal", "vat", "total",
]


def same(a, b):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 0.005
    if isinstance(a, str) and isinstance(b, str):
        return " ".join(a.split()) == " ".join(b.split())   # ignore extra spaces and line breaks
    return a == b


def wrong_fields(extracted, truth):
    """Return a list of (field, expected, got) for every field that differs."""
    wrong = []
    for field in FIELDS:
        e, t = getattr(extracted, field), getattr(truth, field)
        if not same(e, t):
            wrong.append((field, t, e))
    items_ok = len(extracted.line_items) == len(truth.line_items) and all(
        same(a.description, b.description)
        and same(a.quantity, b.quantity)
        and same(a.unit_price, b.unit_price)
        and same(a.line_total, b.line_total)
        for a, b in zip(extracted.line_items, truth.line_items)
    )
    if not items_ok:
        wrong.append(("line_items", f"{len(truth.line_items)} lines", f"{len(extracted.line_items)} lines (or values differ)"))
    return wrong


files = sorted(TRUTH_DIR.glob("*.json"))
if not files:
    raise SystemExit("No answer keys found. Generate the dataset first.")

rows = []
missing = []
field_wrong = defaultdict(int)
by_kind = defaultdict(lambda: [0, 0])      # kind -> [invoices, fully correct]
by_style = defaultdict(lambda: [0, 0])     # style -> [invoices, fully correct] (hard set)
hallucinated = []                          # a value invented where the invoice has none
injection_rows = []

for json_file in files:
    stem = json_file.stem
    saved = EXTRACT_DIR / f"{stem}.json"
    if not saved.exists():
        missing.append(stem)
        continue
    truth_data = json.loads(json_file.read_text(encoding="utf-8"))
    truth = Invoice(**truth_data)
    extracted = Invoice.model_validate_json(saved.read_text(encoding="utf-8"))
    labels = truth_data["labels"]
    kind = labels["error_type"]

    wrong = wrong_fields(extracted, truth)
    for field, _, _ in wrong:
        field_wrong[field] += 1
    by_kind[kind][0] += 1
    by_kind[kind][1] += 0 if wrong else 1
    if labels.get("style"):
        by_style[labels["style"]][0] += 1
        by_style[labels["style"]][1] += 0 if wrong else 1

    # Did the AI invent a value for a field that is really missing on the invoice?
    missing_field = labels.get("missing_field")
    if missing_field in FIELDS and getattr(extracted, missing_field) is not None:
        hallucinated.append((stem, missing_field, getattr(extracted, missing_field)))

    if labels.get("injected"):
        injection_rows.append((stem, kind, labels.get("injection_placement"), wrong))

    rows.append({"invoice": stem, "error_type": kind, "style": labels.get("style", ""),
                 "all_correct": not wrong, "wrong_fields": ";".join(f for f, _, _ in wrong),
                 "detail": " | ".join(f"{f}: expected {t!r}, got {g!r}" for f, t, g in wrong)})

if not rows:
    raise SystemExit("No extracted invoices yet. Run python src\\extract_batch.py first.")

n = len(rows)
perfect = sum(1 for r in rows if r["all_correct"])
total_fields = n * (len(FIELDS) + 1)
wrong_total = sum(field_wrong.values())

print("=" * 60)
print(f"RESULTS: Gemini extraction vs answer keys ({args.set} set)")
print("=" * 60)
if missing:
    print(f"NOTE: only {n} of {len(files)} invoices are extracted so far ({len(missing)} missing).")
print(f"Invoices compared             : {n}")
print(f"Invoices with EVERY field right: {perfect} of {n} ({perfect / n:.1%})")
print(f"Fields correct (12 per invoice): {total_fields - wrong_total} of {total_fields} ({(total_fields - wrong_total) / total_fields:.1%})")
print(f"Invented values (missing_field): {len(hallucinated)}  (AI filled a field that is empty on the invoice)")

print()
print(f"{'Field':<18}{'Wrong':>7}")
for field in FIELDS + ["line_items"]:
    print(f"{field:<18}{field_wrong[field]:>7}")

print()
print(f"{'Type':<28}{'Invoices':>9}{'All fields right':>18}")
for kind, (count, right) in by_kind.items():
    print(f"{kind:<28}{count:>9}{right:>18}")

if by_style:
    print()
    print(f"{'Layout style':<28}{'Invoices':>9}{'All fields right':>18}")
    for style, (count, right) in sorted(by_style.items()):
        print(f"{style:<28}{count:>9}{right:>18}")

if hallucinated:
    print()
    print("INVENTED VALUES (the dangerous kind):")
    for stem, field, value in hallucinated:
        print(f"  {stem}: {field} should be empty, AI wrote {value!r}")

if injection_rows:
    print()
    print("PROMPT-INJECTION INVOICES (did the text change the extraction?):")
    for stem, kind, placement, wrong in injection_rows:
        status = "extracted correctly" if not wrong else "WRONG: " + ", ".join(f for f, _, _ in wrong)
        where = f", {placement}" if placement else ""
        print(f"  {stem} ({kind}{where}): {status}")

bad = [r for r in rows if not r["all_correct"]]
if bad:
    print()
    print(f"INVOICES WITH WRONG FIELDS (first 25 of {len(bad)}):")
    for r in bad[:25]:
        print(f"  {r['invoice']} ({r['error_type']}): {r['detail'][:230]}")

csv_path = EVAL_DIR / f"extraction_results{SUFFIX}.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=["invoice", "error_type", "style", "all_correct", "wrong_fields", "detail"])
    writer.writeheader()
    writer.writerows(rows)
print()
print("Saved:", csv_path)