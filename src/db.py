"""
db.py
Small functions that ask the database questions.
The agent will use these as tools later.
"""

import sqlite3
from pathlib import Path

from schemas import Invoice

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "invoiceiq.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us read columns by name
    return conn


def query_one(sql, params=()):
    """Run a SELECT and return the first row as a dictionary (or None)."""
    conn = _connect()
    try:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def query_all(sql, params=()):
    """Run a SELECT and return all rows as a list of dictionaries."""
    conn = _connect()
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def execute(sql, params=()):
    """Run an INSERT or UPDATE and save it."""
    conn = _connect()
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


# The ? marks below are placeholders. The database fills them in safely,
# so text from an invoice can never be run as SQL code.

def find_vendor_by_trn(trn):
    """Is this vendor in the approved vendor master?"""
    return query_one("SELECT * FROM vendors WHERE trn = ?", (trn,))


def find_po(po_number):
    """Does this purchase order exist, and for how much?"""
    return query_one("SELECT * FROM purchase_orders WHERE po_number = ?", (po_number,))


def find_duplicate(invoice_number, trn):
    """Have we already processed an invoice with this number from this vendor?"""
    return query_one(
        "SELECT * FROM processed_invoices WHERE invoice_number = ? AND trn = ?",
        (invoice_number, trn),
    )


def get_vendor_history(trn):
    """All past invoices from this vendor, oldest first."""
    return query_all(
        "SELECT * FROM processed_invoices WHERE trn = ? ORDER BY invoice_date",
        (trn,),
    )


def record_processed(invoice: Invoice, decision):
    """Save a handled invoice in the history table."""
    if not invoice.invoice_number:
        # Without an invoice number it can never be matched as a duplicate later,
        # so we do not store it (the history table requires a number).
        return
    execute(
        "INSERT INTO processed_invoices "
        "(invoice_number, vendor_name, trn, invoice_date, total, decision) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            invoice.invoice_number,
            invoice.vendor,
            invoice.trn,
            str(invoice.invoice_date) if invoice.invoice_date else None,
            invoice.total,
            decision,
        ),
    )