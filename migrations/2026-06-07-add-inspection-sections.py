"""
Migration — 2026-06-07 — Daily Inspection: group areas into sections

Adds a `section` column to inspection_areas and classifies every area into one
of five themed sections, so the inspection page can render collapsible section
groups instead of one flat 31-area scroll:

    Facilities & Infrastructure   (the originally-seeded 9 areas)
    Incubators                    (Incubator 2-6)
    Labs                          (Metaverse, Aramco.AI, 5G, AR/VR, IoT)
    Workshops & Studios           (UX Testing/Observation, Motion Studio, Workshop 1-3)
    Operations & Offices          (Systems, Control Room, offices, Digital Theater, Public Display)

Section ordering and the "Other" fallback for any unclassified area live in
routes/inspections.py (SECTION_ORDER) — this migration only stores the label.

Idempotent: the column is added only if missing, and the backfill is a plain
UPDATE keyed by area name (re-running just re-sets the same labels).

Usage:
    python3 migrations/2026-06-07-add-inspection-sections.py
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

# Area name -> section label.
SECTION_OF = {}
for _name in ["AV system", "Data Center", "Male's Restroom", "Female's Restroom",
              "Coffee Area 1", "Coffee Area 2", "AV Room", "Open Area",
              "Collaboration Area"]:
    SECTION_OF[_name] = "Facilities & Infrastructure"
for _name in ["Incubator 2 - RPA", "Incubator 3 - Quantum/IPD",
              "Incubator 4 - Data Drill", "Incubator 5 - Analytics",
              "Incubator 6 - Finance"]:
    SECTION_OF[_name] = "Incubators"
for _name in ["Metaverse Lab", "Aramco.AI", "5G/Space Technology Lab",
              "AR/VR Lab", "IoT Lab"]:
    SECTION_OF[_name] = "Labs"
for _name in ["UX Testing", "UX Observation", "Motion Studio",
              "Workshop 1", "Workshop 2", "Workshop 3"]:
    SECTION_OF[_name] = "Workshops & Studios"
for _name in ["Systems", "Control Room", "Division Head Office",
              "Huddle room (Director Room)", "Digital Theater", "Public Display"]:
    SECTION_OF[_name] = "Operations & Offices"


def backup(db_path):
    if not os.path.exists(db_path):
        return None
    backups = os.path.join(ROOT, "backups")
    os.makedirs(backups, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(backups, f"{stamp}-sail-pre-inspection-sections.db")
    shutil.copy2(db_path, dst)
    print(f"Backup: {dst}")
    return dst


def ensure_column(conn):
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(inspection_areas)").fetchall()}
    if "section" not in cols:
        conn.execute(
            "ALTER TABLE inspection_areas "
            "ADD COLUMN section TEXT NOT NULL DEFAULT ''")
        print("Added column inspection_areas.section")
    else:
        print("Column inspection_areas.section already present")


def backfill(conn):
    updated = unmatched = 0
    names = {r[0] for r in conn.execute(
        "SELECT name FROM inspection_areas").fetchall()}
    for name in names:
        section = SECTION_OF.get(name)
        if section is None:
            unmatched += 1
            continue
        cur = conn.execute(
            "UPDATE inspection_areas SET section = ? WHERE name = ?",
            (section, name))
        updated += cur.rowcount
    return updated, unmatched


def main():
    if not os.path.exists(DB_PATH):
        print(f"No DB at {DB_PATH}. Run init_db.py first.")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        backup(DB_PATH)
        ensure_column(conn)
        updated, unmatched = backfill(conn)
        conn.commit()
        print(f"Classified {updated} area(s) into sections.")
        if unmatched:
            print(f"{unmatched} area(s) had no mapping — they will show under "
                  f"'Other' on the page until an admin assigns a section.")
        print("Migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
