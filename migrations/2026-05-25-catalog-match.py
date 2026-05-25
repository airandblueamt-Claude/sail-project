"""
Migration — 2026-05-25c — catalog-match adjustments

Closes the last gaps between the request form and what the three real
sample docs in docs/samples/ actually contain:

  1. estimated_hours_max on gpu_request_workloads
     ThakaaMed lists workload effort as a RANGE ("200-300 hours",
     "150-250 hours", "200-400 hours"). Today we collapse that to a
     single integer and lose half the info. Existing column
     'estimated_hours' now means MIN; the new 'estimated_hours_max' is
     nullable so single-value workloads keep working.

  2. notes on gpu_request_vm_groups
     OrbitronAI's database & cache group carries variant data that doesn't
     fit the standard role columns:
       PostgreSQL "Databases Hosted: logto, agent_dns, ..."
       Redis     "Version: 7.0 / Eviction: allkeys-lru"
     This is a group-level textarea — the per-role 'notes' column already
     exists for role-specific quirks.

Document metadata (prepared_for, document_date, email_from, ...) needs no
schema change — it persists into the existing gpu_request_fields table
under section='document'. The form gains a typed UI for it.

Idempotent.

Usage:
    python3 migrations/2026-05-25-catalog-match.py
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


def backup(db_path):
    if not os.path.exists(db_path):
        return None
    backups = os.path.join(ROOT, "backups")
    os.makedirs(backups, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(backups, f"{stamp}-sail-pre-catalog-match.db")
    shutil.copy2(db_path, dst)
    print(f"Backup: {dst}")
    return dst


def column_exists(conn, table, column):
    return any(r[1] == column for r in conn.execute(f"PRAGMA table_info({table})").fetchall())


def add(conn, table, column, decl):
    if column_exists(conn, table, column):
        print(f"  · {table}.{column} already present")
    else:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        print(f"  + {table}.{column}")


def main():
    if not os.path.exists(DB_PATH):
        print(f"No DB at {DB_PATH}. Run init_db.py first.")
        return
    backup(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        print("gpu_request_workloads:")
        add(conn, "gpu_request_workloads", "estimated_hours_max", "INTEGER")

        print("gpu_request_vm_groups:")
        add(conn, "gpu_request_vm_groups", "notes", "TEXT")

        conn.commit()
        print("\nMigration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
