"""
Migration — 2026-05-21 — add api_tokens table

Bearer-token auth for the external-agent API at /api/v1/*. Token plaintext
is generated at mint time and shown once; only the sha256 hex hash is
stored in token_hash. Idempotent — safe to re-run.

Usage:
    python3 migrations/2026-05-21-add-api-tokens.py
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
sys.path.insert(0, ROOT)

from config import DB_PATH

DDL = """
CREATE TABLE IF NOT EXISTS api_tokens (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    token_hash    TEXT NOT NULL UNIQUE,
    employee_id   INTEGER NOT NULL REFERENCES employees(id),
    scopes        TEXT NOT NULL DEFAULT 'read',
    last_used_at  TEXT,
    revoked_at    TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_api_tokens_hash     ON api_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_api_tokens_employee ON api_tokens(employee_id);
"""


def backup(db_path):
    if not os.path.exists(db_path):
        return None
    backups = os.path.join(ROOT, "backups")
    os.makedirs(backups, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(backups, f"{stamp}-sail-pre-api-tokens.db")
    shutil.copy2(db_path, dst)
    print(f"Backup: {dst}")
    return dst


def main():
    if not os.path.exists(DB_PATH):
        print(f"No DB at {DB_PATH}. Run init_db.py first.")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        existing = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='api_tokens'"
        ).fetchone()
        if existing:
            print("api_tokens already present — refreshing indexes.")
        else:
            backup(DB_PATH)
        conn.executescript(DDL)
        conn.commit()
        print("Migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
