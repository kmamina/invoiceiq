"""
build_db.py
Creates the SQLite database (data/invoiceiq.db) from scratch:
  - vendors             : the approved supplier list, with each vendor's contract payment terms
  - purchase_orders     : each PO and its approved amount
  - processed_invoices  : invoices we have already handled (starts empty)
Running this file again resets these three tables.
(The audit_log table is never touched.)
"""

import json
import sqlite3
from pathlib import Path

from config import VENDOR_TERMS_DAYS
from generate_invoices import VENDORS

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "invoiceiq.db"
TRUTH_DIR = BASE_DIR / "data" / "ground_truth"

SCHEMA = """
DROP TABLE IF EXISTS vendors;
DROP TABLE IF EXISTS purchase_orders;
DROP TABLE IF EXISTS processed_invoices;

CREATE TABLE vendors (
    vendor_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT NOT NULL,
    trn                TEXT NOT NULL UNIQUE,
    address            TEXT,
    payment_terms_days INTEGER
);

CREATE TABLE purchase_orders (
    po_number   TEXT PRIMARY KEY,
    vendor_name TEXT NOT NULL,
    trn         TEXT NOT NULL,
    po_amount   REAL NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open'
);

CREATE TABLE processed_invoices (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL,
    vendor_name    TEXT,
    trn            TEXT,
    invoice_date   TEXT,
    total          REAL,
    decision       TEXT,
    processed_at   TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def build():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)

        # 1. Vendor master: the approved vendors and their contract terms
        for index, vendor in enumerate(VENDORS):
            conn.execute(
                "INSERT INTO vendors (name, trn, address, payment_terms_days) VALUES (?, ?, ?, ?)",
                (vendor["name"], vendor["trn"], vendor["address"], VENDOR_TERMS_DAYS[index]),
            )

        # 2. Purchase orders: read from the answer-key files.
        #    po_amount is what the PO says (it can differ from the invoice total).
        #    po_in_master is False for invoices whose PO number does not exist.
        for json_file in sorted(TRUTH_DIR.glob("*.json")):
            data = json.loads(json_file.read_text(encoding="utf-8"))
            po_number = data.get("po_number")
            if not po_number or not data.get("po_in_master", True):
                continue
            po_amount = data.get("po_amount", data.get("total"))
            if po_amount is None:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO purchase_orders "
                "(po_number, vendor_name, trn, po_amount) VALUES (?, ?, ?, ?)",
                (
                    po_number,
                    data.get("po_vendor_name", data.get("vendor")),
                    data.get("po_trn", data.get("trn")),
                    po_amount,
                ),
            )

        conn.commit()

        vendor_count = conn.execute("SELECT COUNT(*) FROM vendors").fetchone()[0]
        po_count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
        print(f"Database ready: {DB_PATH.name}")
        print(f"  vendors: {vendor_count} rows | purchase_orders: {po_count} rows | processed_invoices: 0 rows")
    finally:
        conn.close()


if __name__ == "__main__":
    build()