"""
Migration — 2026-06-07 — Daily Inspection: add 22 room/lab areas

Extends the inspection catalogue with the Incubators, Labs, Workshops and the
public/operational areas from the team's room list:

    Incubator 2-6, Metaverse Lab, Aramco.AI, 5G/Space Technology Lab, AR/VR Lab,
    IoT Lab, UX Testing, UX Observation, Motion Studio, Digital Theater,
    Public Display, Systems, Control Room, Workshop 1-3, Division Head Office,
    Huddle room (Director Room).

Catalogue-only: the per-day X / N marks in the source sheet are *daily results*,
not catalogue rows, so they are not seeded here — supervisors record those on the
inspection page each day.

Spreadsheet typos are normalised to the existing catalogue convention so we don't
create near-duplicate items:
    "Micorosoft"  -> "Microsoft"   (matches seeded "Smart Board - Microsoft")
    "Recodring"   -> "Recording"
    recording/smart-glass casing    -> "Recording Camera" / "Smart Glass"

New areas are appended after the current highest display_order, so they sort below
the originally-seeded areas. Idempotent: INSERT OR IGNORE on the UNIQUE name /
(area_id, name) constraints means re-running is a no-op for rows that already exist.

Usage:
    python3 migrations/2026-06-07-add-inspection-areas-incubators-labs.py
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

# Area name -> ordered list of check items (normalised spelling/casing).
SEED = [
    ("Incubator 2 - RPA", [
        "6 large LG 86 Screen",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Light",
        "Smart Board - Microsoft",
        "Recording Camera",
    ]),
    ("Incubator 3 - Quantum/IPD", [
        "Smart Board - Microsoft",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Light",
        "Recording Camera",
    ]),
    ("Incubator 4 - Data Drill", [
        "Smart Board - Microsoft",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Light",
        "Recording Camera",
    ]),
    ("Incubator 5 - Analytics", [
        "Smart Board - Microsoft",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Light",
        "Blind",
        "Recording Camera",
    ]),
    ("Incubator 6 - Finance", [
        "Smart Board - Microsoft",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Light",
        "Blind",
        "Recording Camera",
    ]),
    ("Metaverse Lab", [
        "Smart Board - Microsoft",
        "LG TV",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Light",
    ]),
    ("Aramco.AI", [
        "Smart Board - Microsoft",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Light",
    ]),
    ("5G/Space Technology Lab", [
        "Smart Board - Microsoft",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Light",
    ]),
    ("AR/VR Lab", [
        "Smart Board - Microsoft",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Light",
    ]),
    ("IoT Lab", [
        "Smart Board - Microsoft - 86",
        "TV Screen 8pcs",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Light",
    ]),
    ("UX Testing", [
        "Smart Board - Microsoft",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Light",
        "Blind",
        "Recording Camera",
        "Smart Glass",
    ]),
    ("UX Observation", [
        "3 TV screens (LG)",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Microphone station",
        "Light",
        "Smart Glass",
    ]),
    ("Motion Studio", [
        "Smart Board - Microsoft",
        "TV Screen (LG)",
        "Shooting set",
        "Room Access Control",
        "Room Schedule Screen",
        "Room Control screen",
        "Light",
        "Smart Glass",
    ]),
    ("Digital Theater", [
        "Room Control screen",
        "Room Access Control",
        "Cooling system",
        "Display Screens Video Wall",
        "Sound system (mic - Speakers)",
        "Recording System",
        "Conferencing System",
        "Smart Board",
        "Encoder - HDMI",
        "Light",
    ]),
    ("Public Display", [
        "Curved Video Wall",
        "6 screens (LG)",
        "Long Video Wall",
        "Exhibit Strip Video Wall",
        "Exhibition Journey Video Wall",
        "13 Transparent Screen",
        "Operational offices - 3 TV Screen",
        "Kiosk 1, 2",
    ]),
    ("Systems", [
        "Booking system",
        "LG Signage",
        "7th sense",
        "Access Control",
        "Microphone - Public",
        "Reservation - Robin power",
        "Paging systems",
    ]),
    ("Control Room", [
        "Room Access Control",
        "Room Schedule Screen",
        "Room Control screen",
        "Blind",
        "Light",
        "Fridge",
    ]),
    ("Workshop 1", [
        "Smart Board - Microsoft",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Light",
        "LG TV",
        "Blind",
        "Smart Glass",
    ]),
    ("Workshop 2", [
        "Smart Board - Microsoft",
        "Smart Board Huawei",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Blind",
        "LG TV",
        "Smart Glass",
    ]),
    ("Workshop 3", [
        "Smart Board - Microsoft",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Light",
        "Recording Camera",
        "Blind",
        "LG TV",
        "Smart Glass",
    ]),
    ("Division Head Office", [
        "Smart Board - Microsoft",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Blind",
        "Light",
        "LG TV",
    ]),
    ("Huddle room (Director Room)", [
        "Smart Board - Microsoft",
        "Room Schedule Screen",
        "Room Control screen",
        "Room Access Control",
        "Blind",
        "Light",
    ]),
]


def backup(db_path):
    if not os.path.exists(db_path):
        return None
    backups = os.path.join(ROOT, "backups")
    os.makedirs(backups, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(backups, f"{stamp}-sail-pre-inspection-areas.db")
    shutil.copy2(db_path, dst)
    print(f"Backup: {dst}")
    return dst


def seed_catalog(conn):
    """Append new areas after the current max display_order. Idempotent."""
    base = conn.execute(
        "SELECT COALESCE(MAX(display_order), 0) FROM inspection_areas"
    ).fetchone()[0]
    inserted_areas = inserted_items = 0
    for area_idx, (area_name, items) in enumerate(SEED):
        area_order = base + (area_idx + 1) * 10
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
        if not {'inspection_areas', 'inspection_items'}.issubset(existing):
            print("inspection_* tables missing — run the "
                  "2026-06-04 checklist migration first.")
            return
        backup(DB_PATH)
        areas, items = seed_catalog(conn)
        conn.commit()
        print(f"Seeded {areas} new area(s), {items} new item(s).")
        print("Migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
