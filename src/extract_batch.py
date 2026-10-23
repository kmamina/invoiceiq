r"""
extract_batch.py
Step 14, part 1: extract the invoice PDFs with Gemini in small batches.

- Safe to stop (Ctrl+C) and run again: every finished invoice is saved at once
  in data/extracted, and invoices that are already saved are skipped.
- Waits a few seconds between invoices to stay inside the free-tier rate limit.
- Stops by itself after 3 failures in a row (usually a quota limit or an outage).
- Failed invoices are listed in data/eval\extraction_failures.csv and retried next run.

Usage (from the invoiceiq folder):
    python src\extract_batch.py                 (25 invoices)
    python src\extract_batch.py --limit 50      (50 invoices)
    python src\extract_batch.py --limit 5 --delay 8
    python src\extract_batch.py --limit 9 --risky-first   (injection + missing_field first)
"""

import argparse
import csv
import json
import time
from pathlib import Path

import extract as extract_module
from extract import EXTRACT_DIR, INVOICE_DIR, extract_invoice

BASE_DIR = Path(__file__).resolve().parent.parent
EVAL_DIR = BASE_DIR / "data" / "eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)
FAIL_CSV = EVAL_DIR / "extraction_failures.csv"
MODEL_CSV = EVAL_DIR / "extraction_models.csv"   # which model extracted which invoice
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


parser = argparse.ArgumentParser()
parser.add_argument("--limit", type=int, default=25, help="how many invoices to extract in this run")
parser.add_argument("--delay", type=float, default=4, help="seconds to wait between invoices")
parser.add_argument("--risky-first", action="store_true",
                    help="evaluation helper: extract the injection and missing_field invoices first")
args = parser.parse_args()

pdfs = sorted(INVOICE_DIR.glob("*.pdf"))
if not pdfs:
    raise SystemExit("No PDFs in data\\invoices. Run python src\\generate_invoices.py first.")

todo = [p for p in pdfs if not (EXTRACT_DIR / f"{p.stem}.json").exists()]
print(f"{len(pdfs) - len(todo)} of {len(pdfs)} already extracted. {len(todo)} left.")
if args.risky_first:
    # Uses the answer keys only to choose the ORDER. Extraction itself never sees them.
    def is_risky(pdf):
        key = BASE_DIR / "data" / "ground_truth" / f"{pdf.stem}.json"
        if not key.exists():
            return False
        kind = json.loads(key.read_text(encoding="utf-8"))["labels"]["error_type"]
        return kind == "missing_field" or kind.startswith("injection")
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
if total_done < len(pdfs):
    print("Run the same command again to continue.")
else:
    print("All done. Next: python src\\evaluate_extraction.py")