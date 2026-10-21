"""
build_db.py
Creates the SQLite database (data/invoiceiq.db) from scratch:
  - vendors             : the approved supplier list (vendor master)
  - purchase_orders     : each PO and its amount
  - processed_invoices  : invoices we have already handled (starts empty)
Running this file again resets the database.
"""

import json
import sqlite3
from pathlib import Path

from generate_invoices import VENDORS

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "invoiceiq.db"
TRUTH_DIR = BASE_DIR / "data" / "ground_truth"

SCHEMA = """
DROP TABLE IF EXISTS vendors;
DROP TABLE IF EXISTS purchase_orders;
DROP TABLE IF EXISTS processed_invoices;

CREATE TABLE vendors (
    vendor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    trn       TEXT NOT NULL UNIQUE,
    address   TEXT
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

        # 1. Vendor master: every vendor from the invoice generator
        for vendor in VENDORS:
            conn.execute(
                "INSERT INTO vendors (name, trn, address) VALUES (?, ?, ?)",
                (vendor["name"], vendor["trn"], vendor["address"]),
            )

        # 2. Purchase orders: one PO per correct invoice (the answer-key files)
        for json_file in sorted(TRUTH_DIR.glob("*.json")):
            data = json.loads(json_file.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT OR IGNORE INTO purchase_orders "
                "(po_number, vendor_name, trn, po_amount) VALUES (?, ?, ?, ?)",
                (data["po_number"], data["vendor"], data["trn"], data["total"]),
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