"""
Migration — 2026-06-04 — Daily Inspection Checklist (four tables)

Adds the lab-cleanliness inspection module:

    inspection_areas    — top-level groupings (Data Center, Coffee Area 1, …)
    inspection_items    — one row per check item inside an area
    inspections         — one row per calendar day (UNIQUE inspection_date)
    inspection_results  — per-item Active / Inactive / None result + note

Also seeds the catalogue with the areas + items from the team's Excel sheet
so the team can start using the page the same day the migration runs.

Idempotent: safe to re-run via CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE.

Usage:
    python3 migrations/2026-06-04-add-inspection-checklist.py
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
CREATE TABLE IF NOT EXISTS inspection_areas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_inspection_areas_order ON inspection_areas(display_order);

CREATE TABLE IF NOT EXISTS inspection_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    area_id       INTEGER NOT NULL REFERENCES inspection_areas(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(area_id, name)
);
CREATE INDEX IF NOT EXISTS idx_inspection_items_area ON inspection_items(area_id, display_order);

CREATE TABLE IF NOT EXISTS inspections (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_date        TEXT NOT NULL UNIQUE,
    created_by             INTEGER REFERENCES employees(id),
    inspection_engineer_id INTEGER REFERENCES employees(id),
    amt_supervisor_id      INTEGER REFERENCES employees(id),
    sail_supervisor_id     INTEGER REFERENCES employees(id),
    notes                  TEXT,
    submitted_at           TEXT,
    created_at             TEXT DEFAULT (datetime('now')),
    updated_at             TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_inspections_date ON inspections(inspection_date);

CREATE TABLE IF NOT EXISTS inspection_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id INTEGER NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    item_id       INTEGER NOT NULL REFERENCES inspection_items(id),
    status        TEXT NOT NULL CHECK(status IN ('active','inactive','none')),
    notes         TEXT,
    updated_by    INTEGER REFERENCES employees(id),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(inspection_id, item_id)
);
CREATE INDEX IF NOT EXISTS idx_inspection_results_inspection ON inspection_results(inspection_id);
CREATE INDEX IF NOT EXISTS idx_inspection_results_item       ON inspection_results(item_id, status);
"""

# Areas + items from the team's Daily Inspection Checklist spreadsheet.
# "AV system" is a header-level marker in the original sheet (Active/Inactive/None
# at the area level only), so it gets a single synthetic "Overall" item.
SEED = [
    ("AV system", ["Overall"]),
    ("Data Center", [
        "External Door - Front",
        "External Door - Back",
        "Internal Door - Front",
        "Internal Door - Back",
        "Data center Roof (fire cover)",
        "Access Control system",
        "A01 Rack",
        "A02 Rack",
        "UBS (A) Rack",
        "UBS (B) Rack",
        "PDU (A) Rack",
        "PDU (B) Rack",
        "AC - A01 Rack",
        "AC - A02 Rack",
        "AC - A03 Rack",
        "AC - A04 Rack",
        "AC - A05 Rack",
        "AC - B01 Rack",
        "AC - B02 Rack",
        "AC - B03 Rack",
        "AC - B04 Rack",
        "Racks General Health",
        "External lights",
        "Internal lights",
        "Other (Racks)",
    ]),
    ("Male's Restroom", [
        "Clean and orderly",
        "Doors",
        "Smart Glass (Water & Soap)",
    ]),
    ("Female's Restroom", [
        "Clean and orderly",
        "Doors",
        "Smart Glass (Water & Soap)",
    ]),
    ("Coffee Area 1", ["Coffee machine", "iPad", "Mini Fridge"]),
    ("Coffee Area 2", ["Coffee machine", "Interactive Screen"]),
    ("AV Room",
        ["External Door"]
        + [f"Equipment Rack #{i}" for i in range(1, 12)]
        + ["Cooling system"]),
    ("Open Area", ["Smart Board - Microsoft", "Phone Booth", "Cubicles", "Light"]),
    ("Collaboration Area", [
        "Smart Board - Microsoft",
        "Room Schedule Screen",
        "Light",
        "LG TV",
    ]),
]


def backup(db_path):
    if not os.path.exists(db_path):
        return None
    backups = os.path.join(ROOT, "backups")
    os.makedirs(backups, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(backups, f"{stamp}-sail-pre-inspection-checklist.db")
    shutil.copy2(db_path, dst)
    print(f"Backup: {dst}")
    return dst


def seed_catalog(conn):
    """Insert areas + items idempotently. Existing rows are left untouched."""
    inserted_areas = inserted_items = 0
    for area_idx, (area_name, items) in enumerate(SEED):
        area_order = (area_idx + 1) * 10
        cur = conn.execute(
            "INSERT OR IGNORE INTO inspection_areas (name, display_order) "
            "VALUES (?, ?)",
            (area_name, area_order))
        if cur.rowcount:
            inserted_areas += 1
        area_id = conn.execute(
            "SELECT id FROM inspection_areas WHERE name = ?",
            (area_name,)).fetchone()[0]
        for item_idx, item_name in enumerate(items):
            item_order = (item_idx + 1) * 10
            cur = conn.execute(
                "INSERT OR IGNORE INTO inspection_items "
                "(area_id, name, display_order) VALUES (?, ?, ?)",
                (area_id, item_name, item_order))
            if cur.rowcount:
                inserted_items += 1
    return inserted_areas, inserted_items


def main():
    if not os.path.exists(DB_PATH):
        print(f"No DB at {DB_PATH}. Run init_db.py first.")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        existing = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name LIKE 'inspection%'"
        ).fetchall()}
        wanted = {'inspection_areas', 'inspection_items',
                  'inspections', 'inspection_results'}
        if wanted.issubset(existing):
            print("All four inspection_* tables already present — "
                  "refreshing indexes and seeding new catalog rows.")
        else:
            backup(DB_PATH)
        conn.executescript(DDL)
        areas, items = seed_catalog(conn)
        conn.commit()
        print(f"Seeded {areas} new area(s), {items} new item(s).")
        print("Migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
