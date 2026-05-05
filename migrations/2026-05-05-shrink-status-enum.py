"""
Migration — 2026-05-05 — shrink assets.status enum

Aligns the live sail.db with the assets.status CHECK constraint declared in
schema.sql (per commit 0e3ea9b "housekeeping: shrink asset-status enum...").

Old values -> new values:
    in_use, checked_out  -> assigned
    maintenance          -> reserved
    decommissioned       -> missing
    available, assigned, reserved, missing -> unchanged

Idempotent: if the assets table already has the new CHECK constraint, the
script logs and exits without modification. Backs up sail.db first.

Usage:
    python3 migrations/2026-05-05-shrink-status-enum.py
"""
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
sys.path.insert(0, ROOT)

from config import DB_PATH

NEW_VALUES = ("available", "assigned", "reserved", "missing")

VALUE_MAP = {
    "in_use":         "assigned",
    "checked_out":    "assigned",
    "maintenance":    "reserved",
    "decommissioned": "missing",
}


def backup(db_path):
    if not os.path.exists(db_path):
        return None
    backups = os.path.join(ROOT, "backups")
    os.makedirs(backups, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(backups, f"{stamp}-sail-pre-status-enum.db")
    shutil.copy2(db_path, dst)
    print(f"Backup: {dst}")
    return dst


def assets_check_clause(conn):
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='assets'"
    ).fetchone()
    if not row:
        return None
    m = re.search(r"CHECK\s*\(\s*status\s+IN\s*\(([^)]+)\)\s*\)", row[0], re.IGNORECASE)
    if not m:
        return None
    return tuple(re.findall(r"'([^']+)'", m.group(1)))


def is_already_new(values):
    return values is not None and set(values) == set(NEW_VALUES)


def main():
    if not os.path.exists(DB_PATH):
        print(f"No DB at {DB_PATH}. Run init_db.py first.")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        current = assets_check_clause(conn)
        print(f"Current assets.status values: {current}")
        if is_already_new(current):
            print("CHECK constraint already in new shape — nothing to do.")
            return

        backup(DB_PATH)

        rows = conn.execute(
            "SELECT status, COUNT(*) FROM assets GROUP BY status"
        ).fetchall()
        print("Existing status distribution:")
        for status, count in rows:
            target = VALUE_MAP.get(status, status if status in NEW_VALUES else None)
            label = "(unchanged)" if target == status else f"-> {target}"
            if target is None:
                label = "-> ??? (will be left as-is and may fail CHECK; review)"
            print(f"  {status!r}: {count} {label}")

        # SQLite ALTER TABLE can't change a CHECK; canonical pattern is
        # rename -> create -> copy with CASE mapping -> drop -> rebuild indexes.
        # IMPORTANT: legacy_alter_table = ON prevents SQLite (>= 3.26) from
        # silently rewriting foreign-key references in OTHER tables to point
        # to the renamed `assets_old` (and then dangling once we DROP it).
        # Without this, tickets.asset_id and asset_custom_values.asset_id
        # end up referencing a non-existent assets_old table.
        conn.execute("PRAGMA legacy_alter_table = ON")
        conn.execute("BEGIN")
        conn.execute("ALTER TABLE assets RENAME TO assets_old")
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as f:
            schema_text = f.read()
        m = re.search(
            r"CREATE TABLE IF NOT EXISTS assets\s*\((.*?)\);",
            schema_text, re.DOTALL | re.IGNORECASE)
        if not m:
            raise RuntimeError(
                "Could not find the assets CREATE TABLE block in schema.sql.")
        create_sql = "CREATE TABLE assets (" + m.group(1) + ")"
        conn.execute(create_sql)

        when_clauses = " ".join(
            f"WHEN status = '{old}' THEN '{new}'"
            for old, new in VALUE_MAP.items()
        )
        case_expr = f"CASE {when_clauses} ELSE status END"
        new_cols = [r[1] for r in conn.execute("PRAGMA table_info(assets)").fetchall()]
        old_cols = [r[1] for r in conn.execute("PRAGMA table_info(assets_old)").fetchall()]
        select_parts = []
        for col in new_cols:
            if col == "status":
                select_parts.append(case_expr + " AS status")
            elif col in old_cols:
                select_parts.append(col)
            else:
                select_parts.append(f"NULL AS {col}")
        copy_sql = (
            f"INSERT INTO assets ({', '.join(new_cols)}) "
            f"SELECT {', '.join(select_parts)} FROM assets_old"
        )
        conn.execute(copy_sql)

        for stmt in re.findall(
                r"CREATE INDEX IF NOT EXISTS idx_assets_\w+ ON assets\([^)]+\);",
                schema_text):
            conn.execute(stmt)

        conn.execute("DROP TABLE assets_old")
        conn.execute("COMMIT")
        conn.execute("PRAGMA legacy_alter_table = OFF")
        conn.execute("PRAGMA foreign_keys = ON")
        # Sanity: any FK that still points at the absent assets_old?
        bad = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND sql LIKE '%assets_old%'"
        ).fetchall()
        if bad:
            print(f"WARNING: tables still reference assets_old: {[r[0] for r in bad]}")
            print("  Run a fix-up to recreate them with the correct FK.")

        post = assets_check_clause(conn)
        print(f"New assets.status values: {post}")
        n = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        print(f"Rows in assets after migration: {n}")
        print("Migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
