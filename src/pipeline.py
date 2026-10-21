"""
pipeline.py
The full flow for one invoice:
  PDF -> extract -> 13 checks -> route -> (agent investigates) -> save to history -> audit log

Rule: the LLM never decides. It only extracts (extract.py) and explains (agent.py).
The routing rules are in routing.py (plain Python).
"""

import json
from pathlib import Path

from agent import investigate
from audit import log_event
from checks import run_all_checks
from db import record_processed
from extract import EXTRACT_DIR, extract_invoice
from routing import ELIGIBLE, FLAG, HUMAN, decide
from schemas import Invoice


def get_invoice(pdf_path):
    """Get the extracted invoice. Reuse the saved result if there is one,
    otherwise call Gemini and save the result."""
    pdf_path = Path(pdf_path)
    saved = EXTRACT_DIR / f"{pdf_path.stem}.json"
    if saved.exists():
        return Invoice.model_validate_json(saved.read_text(encoding="utf-8")), "saved result"
    invoice = extract_invoice(pdf_path)
    saved.write_text(invoice.model_dump_json(indent=2), encoding="utf-8")
    return invoice, "Gemini"


def route_invoice(invoice, name, run_id, source, use_agent=False):
    """Run the checks on an already-extracted invoice, decide, and log everything."""
    log_event(
        run_id, name, "extracted",
        {"source": source, "invoice": json.loads(invoice.model_dump_json())},
    )

    results = run_all_checks(invoice)
    for result in results:
        log_event(run_id, name, "check", result.model_dump())

    route, reasons = decide(results)
    log_event(run_id, name, "decision", {"route": route, "reasons": reasons})

    # The agent explains flagged or unclear invoices. It runs BEFORE we save the invoice
    # to the history, so its tools see the same records the checks saw.
    explanation = None
    if use_agent and route != ELIGIBLE:
        explanation = investigate(invoice, name, run_id, route, results)

    # Remember this invoice, so a second copy will be caught as a duplicate
    record_processed(invoice, route)

    return {"name": name, "route": route, "reasons": reasons, "explanation": explanation}


def process_pdf(pdf_path, run_id, use_agent=False):
    """The whole flow, starting from a PDF file."""
    name = Path(pdf_path).stem
    try:
        invoice, source = get_invoice(pdf_path)
    except Exception as error:
        # If extraction fails, never guess. Send it to a person.
        reasons = [f"Extraction failed: {error}"]
        log_event(run_id, name, "extraction_failed", {"error": str(error)})
        log_event(run_id, name, "decision", {"route": HUMAN, "reasons": reasons})
        return {"name": name, "route": HUMAN, "reasons": reasons, "explanation": None}

    return route_invoice(invoice, name, run_id, source, use_agent=use_agent)