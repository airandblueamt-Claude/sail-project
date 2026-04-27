"""
Initialize the SAIL database from schema.sql, then seed the four
control-team accounts and the starter issue categories.

Usage:  python init_db.py
Output: sail.db (SQLite, schema applied, seed data inserted).
        Any existing sail.db is deleted.

After running this, run import_assets_v3.py to load the inventory data.
"""
import sqlite3
import os
from werkzeug.security import generate_password_hash
from config import DB_PATH

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

CONTROL_TEAM = [
    ("Mohammad Khalifa",      "airandblueamt@gmail.com"),
    ("M. Shaikh",             "m.shaikh@amt-arabia.net"),
    ("Omar Bawadod",          "omar.bawadod@aramco.com"),
    ("Ali Almatrood",         "ali.almatrood@aramco.com"),
]
SEED_PASSWORD = "Aramco@123"

ISSUE_CATEGORIES = [
    "Display / Screen issue",
    "Touch / Calibration failure",
    "Won't power on",
    "Slow / Freezing",
    "Software / OS issue",
    "Network / Connectivity",
    "Printer issue (jam, toner, quality)",
    "Peripheral issue (keyboard, mouse, audio, camera)",
    "Physical damage",
    "Other",
]


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())

    # Seed the four control-team accounts.
    pw_hash = generate_password_hash(SEED_PASSWORD)
    for name, email in CONTROL_TEAM:
        conn.execute(
            "INSERT INTO employees (name, email, role, password_hash, is_active) "
            "VALUES (?, ?, 'admin', ?, 1)",
            (name, email, pw_hash))
    print(f"Seeded {len(CONTROL_TEAM)} control-team accounts (password: {SEED_PASSWORD!r}).")

    # Seed the starter issue categories.
    creator_id = conn.execute(
        "SELECT id FROM employees WHERE email = ?",
        (CONTROL_TEAM[0][1],)).fetchone()[0]
    for name in ISSUE_CATEGORIES:
        conn.execute(
            "INSERT INTO issue_categories (name, is_active, created_by) "
            "VALUES (?, 1, ?)",
            (name, creator_id))
    print(f"Seeded {len(ISSUE_CATEGORIES)} issue categories.")

    conn.commit()
    conn.close()

    print(f"Schema + seed applied. Database ready at {DB_PATH}")
    print("Next: python import_assets_v3.py")


if __name__ == "__main__":
    main()
