from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

_DDL = """
CREATE TABLE IF NOT EXISTS purchase_orders (
    id TEXT PRIMARY KEY,
    action_key TEXT NOT NULL UNIQUE,
    payload_hash TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    receipt_hour INTEGER NOT NULL,
    created_hour INTEGER NOT NULL
);
"""


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


class SimulatedERP:
    def __init__(self, path: Path):
        self.path = Path(path)
        conn = _connect(self.path)
        try:
            conn.executescript(_DDL)
            conn.commit()
        finally:
            conn.close()

    def execute(self, action_key: str, payload: dict, payload_hash: str,
                created_hour: int, receipt_hour: int) -> dict:
        conn = _connect(self.path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM purchase_orders WHERE action_key = ?", (action_key,)
            ).fetchone()
            if row is not None:
                if row["payload_hash"] != payload_hash:
                    conn.rollback()
                    raise ValueError("action key reused with a different payload")
                conn.commit()
                return dict(row)
            po_id = "PO-" + hashlib.sha256(action_key.encode()).hexdigest()[:12]
            conn.execute(
                "INSERT INTO purchase_orders (id, action_key, payload_hash, payload, status, receipt_hour, created_hour)"
                " VALUES (?, ?, ?, ?, 'CONFIRMED', ?, ?)",
                (po_id, action_key, payload_hash, json.dumps(payload, sort_keys=True),
                 receipt_hour, created_hour),
            )
            conn.commit()
            return dict(conn.execute(
                "SELECT * FROM purchase_orders WHERE id = ?", (po_id,)
            ).fetchone())
        finally:
            conn.close()

    def lookup(self, action_key: str) -> dict | None:
        conn = _connect(self.path)
        try:
            row = conn.execute(
                "SELECT * FROM purchase_orders WHERE action_key = ?", (action_key,)
            ).fetchone()
            return dict(row) if row is not None else None
        finally:
            conn.close()

    def count_orders(self, action_key: str) -> int:
        conn = _connect(self.path)
        try:
            return conn.execute(
                "SELECT COUNT(*) FROM purchase_orders WHERE action_key = ?", (action_key,)
            ).fetchone()[0]
        finally:
            conn.close()

    def due_receipts(self, now_hour: int) -> list[dict]:
        conn = _connect(self.path)
        try:
            rows = conn.execute(
                "SELECT * FROM purchase_orders WHERE receipt_hour <= ?", (now_hour,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
