"""
Migration — 2026-06-07 — single "head" day sign-off

Replaces the three generic day-level signatories (Inspection Engineer / AMT
Supervisor / SAIL Supervisor) with one Head sign-off that matches the team:
operators complete their sheets (Carlo = Rooms, Zubair = Infra), then the Head
(e.g. M. Shaikh) reviews and signs once — which submits/locks the day.

Adds inspections.head_id (the employee who signed the day off). The old three
columns are left in place so historical inspections still display, but the new
UI only uses head_id.

Idempotent: column added only if missing.

Usage:
    python3 migrations/2026-06-07-add-inspection-head-signoff.py
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
    dst = os.path.join(backups, f"{stamp}-sail-pre-head-signoff.db")
    shutil.copy2(db_path, dst)
    print(f"Backup: {dst}")
    return dst


def main():
    if not os.path.exists(DB_PATH):
        print(f"No DB at {DB_PATH}. Run init_db.py first.")
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(inspections)").fetchall()}
        if "head_id" in cols:
            print("Column inspections.head_id already present.")
            return
        backup(DB_PATH)
        conn.execute(
            "ALTER TABLE inspections ADD COLUMN head_id "
            "INTEGER REFERENCES employees(id)")
        # Carry any existing engineer sign-off forward as the head, so old
        # submitted days still show a signer.
        conn.execute(
            "UPDATE inspections SET head_id = inspection_engineer_id "
            "WHERE head_id IS NULL AND inspection_engineer_id IS NOT NULL")
        conn.commit()
        print("Added column inspections.head_id (back-filled from engineer).")
        print("Migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
