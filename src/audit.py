"""
audit.py
The audit log: a table that records every step of every run.
It is append-only: we only ever add rows, never change or delete them.
(Rebuilding the database does not wipe it.)
"""

import json

from db import execute, query_all


def init_audit_table():
    execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id     TEXT NOT NULL,
            invoice_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            details    TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


init_audit_table()  # make sure the table exists whenever this file is used


def log_event(run_id, invoice_id, event_type, details):
    """Save one event, for example 'extracted', 'check' or 'decision'."""
    execute(
        "INSERT INTO audit_log (run_id, invoice_id, event_type, details) VALUES (?, ?, ?, ?)",
        (run_id, invoice_id, event_type, json.dumps(details, default=str)),
    )


def get_events(run_id, invoice_id):
    """Read back all events for one invoice in one run, in order."""
    return query_all(
        "SELECT * FROM audit_log WHERE run_id = ? AND invoice_id = ? ORDER BY id",
        (run_id, invoice_id),
    )