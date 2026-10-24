r"""
extract_batch.py
Extract the invoice PDFs with Gemini in small batches.

- Safe to stop (Ctrl+C) and run again: every finished invoice is saved at once,
  and invoices that are already saved are skipped.
- 429 (quota) is handled in extract.py: that model rests and the backup model is used.
- Stops by itself after 3 failures in a row (usually a quota limit or an outage).
- Failed invoices are listed in data/eval/extraction_failures*.csv and retried next run.
- The model that answered each invoice is logged in data/eval/extraction_models*.csv.

Usage (from the invoiceiq folder):
    python src\extract_batch.py                          (main set, 25 invoices)
    python src\extract_batch.py --limit 50 --delay 6
    python src\extract_batch.py --risky-first            (injection + missing_field first)
    python src\extract_batch.py --set hard --limit 40    (the Step 15 hard set)
"""

import argparse
import csv
import json
import time
from pathlib import Path

import extract as extract_module
from extract import extract_invoice

parser = argparse.ArgumentParser()
parser.add_argument("--set", choices=["main", "hard"], default="main", help="which dataset to extract")
parser.add_argument("--limit", type=int, default=25, help="how many invoices to extract in this run")
parser.add_argument("--delay", type=float, default=4, help="seconds to wait between invoices")
parser.add_argument("--risky-first", action="store_true",
                    help="evaluation helper: extract the injection and missing_field invoices first")
args = parser.parse_args()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" if args.set == "main" else BASE_DIR / "data" / "hard"
INVOICE_DIR = DATA_DIR / "invoices"
TRUTH_DIR = DATA_DIR / "ground_truth"
EXTRACT_DIR = DATA_DIR / "extracted"
EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
EVAL_DIR = BASE_DIR / "data" / "eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)
SUFFIX = "" if args.set == "main" else "_hard"
FAIL_CSV = EVAL_DIR / f"extraction_failures{SUFFIX}.csv"
MODEL_CSV = EVAL_DIR / f"extraction_models{SUFFIX}.csv"   # which model extracted which invoice
MAX_IN_A_ROW = 3


def load_failures():
    if not FAIL_CSV.exists():
        return {}
    with open(FAIL_CSV, newline="", encoding="utf-8") as file:
        return {row["invoice"]: row["error"] for row in csv.DictReader(file)}


def save_failures(failures):
    with open(FAIL_CSV, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["invoice", "error"])
        for stem, error in sorted(failures.items()):
            writer.writerow([stem, error[:300].replace("\n", " ")])


pdfs = sorted(INVOICE_DIR.glob("*.pdf"))
if not pdfs:
    raise SystemExit(f"No PDFs in {INVOICE_DIR}. Generate the dataset first "
                     "(generate_dataset.py for main, generate_hard_set.py for hard).")

todo = [p for p in pdfs if not (EXTRACT_DIR / f"{p.stem}.json").exists()]
print(f"[{args.set} set] {len(pdfs) - len(todo)} of {len(pdfs)} already extracted. {len(todo)} left.")

if args.risky_first:
    # Uses the answer keys only to choose the ORDER. Extraction itself never sees them.
    def is_risky(pdf):
        key = TRUTH_DIR / f"{pdf.stem}.json"
        if not key.exists():
            return False
        labels = json.loads(key.read_text(encoding="utf-8"))["labels"]
        return labels["error_type"] in ("missing_field", "fmt_missing_field") or bool(labels.get("injected"))
    todo.sort(key=lambda pdf: not is_risky(pdf))  # stable sort: risky first, order kept

batch = todo[: args.limit]
if not batch:
    raise SystemExit("Nothing to do. All invoices are extracted.")
print(f"This run: {len(batch)} invoices. Press Ctrl+C any time; progress is saved.\n")

failures = load_failures()
done = 0
failed = 0
in_a_row = 0

try:
    for number, pdf in enumerate(batch, start=1):
        print(f"[{number}/{len(batch)}] {pdf.name}")
        try:
            invoice = extract_invoice(pdf)
            (EXTRACT_DIR / f"{pdf.stem}.json").write_text(
                invoice.model_dump_json(indent=2), encoding="utf-8"
            )
            failures.pop(pdf.stem, None)
            new_file = not MODEL_CSV.exists()
            with open(MODEL_CSV, "a", newline="", encoding="utf-8") as log:
                writer = csv.writer(log)
                if new_file:
                    writer.writerow(["invoice", "model"])
                writer.writerow([pdf.stem, extract_module.LAST_MODEL])
            done += 1
            in_a_row = 0
        except Exception as error:  # extraction must never crash the whole batch
            failures[pdf.stem] = str(error)
            failed += 1
            in_a_row += 1
            print(f"  FAILED: {str(error)[:150]}")
            if in_a_row >= MAX_IN_A_ROW:
                print(f"\n{MAX_IN_A_ROW} failures in a row. Probably a quota limit or an outage. Stopping.")
                break
        if number < len(batch):
            time.sleep(args.delay)
except KeyboardInterrupt:
    print("\nStopped by you. Everything finished so far is saved.")

save_failures(failures)
total_done = len(list(EXTRACT_DIR.glob("*.json")))
print()
print("=" * 60)
print(f"This run: {done} extracted, {failed} failed")
print(f"Overall : {total_done} of {len(pdfs)} extracted, {len(failures)} on the failure list")
print("=" * 60)
set_flag = "" if args.set == "main" else " --set hard"
if total_done < len(pdfs):
    print(f"Run the same command again to continue: python src\\extract_batch.py{set_flag}")
else:
    print(f"All done. Next: python src\\evaluate_extraction.py{set_flag}")