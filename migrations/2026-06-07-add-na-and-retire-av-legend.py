"""
Migration — 2026-06-07 — N/A items + retire the "AV system" legend row

Two checklist-fidelity fixes from the team's source sheets:

1. `is_applicable` flag on inspection_items.
   The source sheets mark some items "X" — the item does not apply to that room
   (e.g. Incubator 5 has no Blind to check). Those should show greyed and be
   EXCLUDED from completion %, not left as blank "unrecorded" items dragging the
   day below 100%. This adds a per-item flag (default 1 = applicable) and marks
   the known X items as not-applicable.

2. Retire "AV system".
   In the sheets "AV system / Active / Inactive / None — No items" is a LEGEND
   row explaining the three statuses, not a real inspection area. It was seeded
   as an area with one synthetic "Overall" item; this deactivates it so it drops
   off the checklist. Reversible from Admin → Areas (Reactivate).

Idempotent: column added only if missing; flag/area updates are plain UPDATEs.

Usage:
    python3 migrations/2026-06-07-add-na-and-retire-av-legend.py
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

# (area name, item name) pairs marked "X" (not applicable) in the source sheets.
NA_ITEMS = [
    ("Incubator 5 - Analytics", "Blind"),
    ("Metaverse Lab", "Room Control screen"),
    ("Metaverse Lab", "Room Access Control"),
    ("Systems", "Booking system"),
    ("Systems", "Reservation - Robin power"),
    ("Huddle room (Director Room)", "Room Control screen"),
    ("Huddle room (Director Room)", "Blind"),
]

LEGEND_AREA = "AV system"


def backup(db_path):
    if not os.path.exists(db_path):
        return None
    backups = os.path.join(ROOT, "backups")
    os.makedirs(backups, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(backups, f"{stamp}-sail-pre-na-flag.db")
    shutil.copy2(db_path, dst)
    print(f"Backup: {dst}")
    return dst


def ensure_column(conn):
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(inspection_items)").fetchall()}
    if "is_applicable" not in cols:
        conn.execute(
            "ALTER TABLE inspection_items "
            "ADD COLUMN is_applicable INTEGER NOT NULL DEFAULT 1")
        print("Added column inspection_items.is_applicable")
    else:
        print("Column inspection_items.is_applicable already present")


def mark_na(conn):
    n = 0
    for area_name, item_name in NA_ITEMS:
        cur = conn.execute(
            """UPDATE inspection_items
                  SET is_applicable = 0
                WHERE name = ?
                  AND area_id = (SELECT id FROM inspection_areas WHERE name = ?)""",
            (item_name, area_name))
        if cur.rowcount:
            n += cur.rowcount
        else:
            print(f"  (no match for N/A item: {area_name} / {item_name})")
    return n


def retire_legend(conn):
    cur = conn.execute(
        "UPDATE inspection_areas SET is_active = 0 "
        "WHERE name = ? AND is_active = 1", (LEGEND_AREA,))
    return cur.rowcount


def main():
    if not os.path.exists(DB_PATH):
        print(f"No DB at {DB_PATH}. Run init_db.py first.")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        backup(DB_PATH)
        ensure_column(conn)
        na = mark_na(conn)
        legend = retire_legend(conn)
        conn.commit()
        print(f"Marked {na} item(s) as not-applicable (N/A).")
        print(f"Retired the '{LEGEND_AREA}' legend area." if legend
              else f"'{LEGEND_AREA}' already inactive / absent.")
        print("Migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
