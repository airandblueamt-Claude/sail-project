"""
Migration — 2026-06-07 — photo on an inspection result

Adds `photo_path` to inspection_results so an inspector can attach a photo to an
item (mainly an Inactive / broken one) as evidence for the maintenance team.
Stores the same kind of relative path the inventory uploader uses
("uploads/<name>.jpg"), served via url_for('static', ...).

Idempotent: column added only if missing.

Usage:
    python3 migrations/2026-06-07-add-inspection-result-photo.py
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
    dst = os.path.join(backups, f"{stamp}-sail-pre-result-photo.db")
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
            "PRAGMA table_info(inspection_results)").fetchall()}
        if "photo_path" in cols:
            print("Column inspection_results.photo_path already present.")
            return
        backup(DB_PATH)
        conn.execute(
            "ALTER TABLE inspection_results ADD COLUMN photo_path TEXT")
        conn.commit()
        print("Added column inspection_results.photo_path")
        print("Migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
