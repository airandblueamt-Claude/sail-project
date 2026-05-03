"""Apply additive migrations that schema.sql cannot express idempotently.

SQLite's `CREATE TABLE IF NOT EXISTS` is a no-op when the table already
exists — it does not diff columns. Any new column added to an existing
table needs an explicit ALTER TABLE here, guarded by `PRAGMA table_info`
so the migration is safe to re-run.
"""
import sqlite3
from config import DB_PATH


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        if "model_number" not in _columns(conn, "assets"):
            conn.execute("ALTER TABLE assets ADD COLUMN model_number TEXT")
            conn.execute("""
                UPDATE assets
                SET model_number = (SELECT model_number FROM equipment_models
                                    WHERE id = assets.equipment_model_id)
                WHERE model_number IS NULL
            """)
            print("[migrate] added assets.model_number and backfilled from equipment_models")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
