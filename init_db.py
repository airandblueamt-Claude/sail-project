"""
Initialize the SAIL database from schema.sql.

Usage:  python init_db.py
Output: sail.db (SQLite, empty schema). Any existing sail.db is deleted.

After running this, run import_assets_v3.py to load the inventory data.
"""
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "sail.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

    print(f"Schema applied. Database ready at {DB_PATH}")
    print("Next: python import_assets_v3.py")


if __name__ == "__main__":
    main()
