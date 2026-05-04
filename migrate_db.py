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


def _table_sql(conn, table):
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row[0] if row else ""


def _rebuild_assets_status_enum(conn):
    """Shrink assets.status enum to {available,assigned,reserved,missing}.

    SQLite cannot ALTER a CHECK constraint, so we rebuild the table.
    Old → new mapping:
      in_use, checked_out          → assigned
      maintenance, decommissioned  → missing
    """
    sql_def = _table_sql(conn, "assets")
    if "'assigned'" in sql_def and "'in_use'" not in sql_def:
        return  # already migrated
    print("[migrate] rebuilding assets table with new status enum")
    conn.executescript("""
        PRAGMA foreign_keys=OFF;
        BEGIN;
        CREATE TABLE assets__new (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_tag           TEXT NOT NULL UNIQUE,
            equipment_model_id  INTEGER NOT NULL REFERENCES equipment_models(id),
            serial_number       TEXT,
            model_number        TEXT,
            location_id         INTEGER REFERENCES locations(id),
            condition           TEXT DEFAULT 'good'
                                CHECK(condition IN ('good','fair','damaged','decommissioned')),
            status              TEXT DEFAULT 'available'
                                CHECK(status IN ('available','assigned','reserved','missing')),
            assigned_to         INTEGER REFERENCES employees(id),
            qty_represented     INTEGER DEFAULT 1,
            purchase_date       TEXT,
            warranty_expiry     TEXT,
            image_path          TEXT,
            holder_name         TEXT,
            remark              TEXT,
            notes               TEXT,
            created_at          TEXT DEFAULT (datetime('now')),
            updated_at          TEXT DEFAULT (datetime('now'))
        );
        INSERT INTO assets__new (
            id, asset_tag, equipment_model_id, serial_number, model_number,
            location_id, condition, status, assigned_to, qty_represented,
            purchase_date, warranty_expiry, image_path, holder_name, remark,
            notes, created_at, updated_at
        )
        SELECT
            id, asset_tag, equipment_model_id, serial_number, model_number,
            location_id, condition,
            CASE
                WHEN status IN ('in_use','checked_out')        THEN 'assigned'
                WHEN status IN ('maintenance','decommissioned') THEN 'missing'
                ELSE status
            END,
            assigned_to, qty_represented, purchase_date, warranty_expiry,
            image_path, holder_name, remark, notes, created_at, updated_at
        FROM assets;
        DROP TABLE assets;
        ALTER TABLE assets__new RENAME TO assets;
        CREATE INDEX IF NOT EXISTS idx_assets_tag       ON assets(asset_tag);
        CREATE INDEX IF NOT EXISTS idx_assets_model     ON assets(equipment_model_id);
        CREATE INDEX IF NOT EXISTS idx_assets_location  ON assets(location_id);
        CREATE INDEX IF NOT EXISTS idx_assets_status    ON assets(status);
        CREATE INDEX IF NOT EXISTS idx_assets_condition ON assets(condition);
        CREATE INDEX IF NOT EXISTS idx_assets_assigned  ON assets(assigned_to);
        COMMIT;
        PRAGMA foreign_keys=ON;
    """)
    print("[migrate] assets.status enum migrated")


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        if "model_number" not in _columns(conn, "assets"):
            conn.execute("ALTER TABLE assets ADD COLUMN model_number TEXT")
            print("[migrate] added assets.model_number")
        # Backfill any NULL per-unit model_number from the parent equipment_model.
        # Safe to re-run: only touches rows that are still NULL.
        cur = conn.execute("""
            UPDATE assets
            SET model_number = (SELECT model_number FROM equipment_models
                                WHERE id = assets.equipment_model_id)
            WHERE model_number IS NULL
        """)
        if cur.rowcount:
            print(f"[migrate] backfilled assets.model_number for {cur.rowcount} rows")
        conn.commit()
        _rebuild_assets_status_enum(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
