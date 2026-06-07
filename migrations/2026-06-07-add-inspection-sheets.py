"""
Migration — 2026-06-07 — Inspection sheets (Infra / Rooms) + per-sheet sign-off

Splits the daily inspection into two "sheets", each owned by one person, matching
the team's two source Excel sheets:

    Infra  = the "Facilities & Infrastructure" section        (e.g. Mohammed Zobir)
    Rooms  = Incubators + Labs + Workshops & Studios +
             Operations & Offices                              (e.g. Carlo)

The section -> sheet mapping itself lives in routes/inspections.py (SHEET_OF_SECTION);
this migration only stores each sheet's display order + assignee, and the per-sheet
sign-off records.

Tables:
    inspection_sheets           — one row per sheet, with the responsible employee
    inspection_sheet_signoffs   — "<person> signed off <sheet> on <day>"

Assignees are seeded NULL (Carlo / Zobir don't exist as users yet) — set them in
Admin → Sheets once their accounts are created.

Idempotent: CREATE IF NOT EXISTS + INSERT OR IGNORE.

Usage:
    python3 migrations/2026-06-07-add-inspection-sheets.py
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
CREATE TABLE IF NOT EXISTS inspection_sheets (
    name          TEXT PRIMARY KEY,
    display_order INTEGER NOT NULL DEFAULT 0,
    assignee_id   INTEGER REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS inspection_sheet_signoffs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id INTEGER NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    sheet         TEXT NOT NULL,
    signed_by     INTEGER REFERENCES employees(id),
    signed_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(inspection_id, sheet)
);
CREATE INDEX IF NOT EXISTS idx_sheet_signoffs_insp
    ON inspection_sheet_signoffs(inspection_id);
"""

SHEETS = [("Infra", 10), ("Rooms", 20)]


def backup(db_path):
    if not os.path.exists(db_path):
        return None
    backups = os.path.join(ROOT, "backups")
    os.makedirs(backups, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(backups, f"{stamp}-sail-pre-sheets.db")
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
        backup(DB_PATH)
        conn.executescript(DDL)
        n = 0
        for name, order in SHEETS:
            cur = conn.execute(
                "INSERT OR IGNORE INTO inspection_sheets (name, display_order) "
                "VALUES (?, ?)", (name, order))
            n += cur.rowcount
        conn.commit()
        print(f"Seeded {n} sheet(s) (assignees left NULL — set in Admin → Sheets).")
        print("Migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
