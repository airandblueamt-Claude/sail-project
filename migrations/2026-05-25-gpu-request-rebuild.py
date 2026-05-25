"""
Migration — 2026-05-25 — GPU request rebuild

Reshape the GPU request schema to hold the three real-world request shapes
we've seen so far in docs/samples/:

  1. new_infra            — BYOC infrastructure brief (e.g. OrbitronAI):
                            multiple VM groups, optional GPU block,
                            networking + remote-access requirements.
  2. gpu_allocation       — short GPU-models list (e.g. KFUPM email):
                            6 GPU alternatives, count range "2 per module,
                            up to 8".
  3. compute_partnership  — time on existing infra (e.g. ThakaaMed):
                            workloads + phases + what the requester
                            provides back to SAIL.

Changes:
  * gpu_requests: + request_kind, source, agent_confidence,
                   raw_extraction_json, existing_resource_ref
  * gpu_request_models: + gpu_count_max
  * NEW gpu_request_vm_groups       — VM-group header
  * NEW gpu_request_vm_roles        — per-role VM specs under each group
  * NEW gpu_request_contributions   — what the requester provides back
  * NEW gpu_request_fields          — generic section/key/value for the
                                       long tail (networking, access,
                                       relationship_context, custom...)
  * tickets: + gpu_request_id (FK) so maintenance tickets can link to a
             provisioned request.

Idempotent. Existing gpu_requests rows are stamped with
request_kind='new_infra', source='manual'. sail.db is backed up first.

Usage:
    python3 migrations/2026-05-25-gpu-request-rebuild.py
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


NEW_TABLES_DDL = """
CREATE TABLE IF NOT EXISTS gpu_request_vm_groups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id  INTEGER NOT NULL REFERENCES gpu_requests(id) ON DELETE CASCADE,
    sort_order  INTEGER DEFAULT 0,
    name        TEXT NOT NULL,                  -- "Kubernetes Cluster Nodes"
    summary     TEXT                            -- "30 VMs recommended"
);
CREATE INDEX IF NOT EXISTS idx_gpu_request_vm_groups_req ON gpu_request_vm_groups(request_id);

CREATE TABLE IF NOT EXISTS gpu_request_vm_roles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id        INTEGER NOT NULL REFERENCES gpu_request_vm_groups(id) ON DELETE CASCADE,
    sort_order      INTEGER DEFAULT 0,
    role_name       TEXT NOT NULL,              -- "Control Plane (platform services, Temporal, ...)"
    vm_count        INTEGER,
    vcpu_per_vm     INTEGER,
    ram_gb_per_vm   INTEGER,
    disk_gb_per_vm  INTEGER,
    disk_type       TEXT,                       -- 'SSD' / 'NVMe'
    os              TEXT,                       -- 'Ubuntu 24.04 LTS'
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_gpu_request_vm_roles_group ON gpu_request_vm_roles(group_id);

CREATE TABLE IF NOT EXISTS gpu_request_contributions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id  INTEGER NOT NULL REFERENCES gpu_requests(id) ON DELETE CASCADE,
    sort_order  INTEGER DEFAULT 0,
    name        TEXT NOT NULL,                  -- "ClearML Integration"
    description TEXT,
    benefit     TEXT                            -- "Automated resource optimization"
);
CREATE INDEX IF NOT EXISTS idx_gpu_request_contributions_req ON gpu_request_contributions(request_id);

CREATE TABLE IF NOT EXISTS gpu_request_fields (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id  INTEGER NOT NULL REFERENCES gpu_requests(id) ON DELETE CASCADE,
    section     TEXT NOT NULL,                  -- 'networking' | 'access' | 'relationship' | 'custom'
    key         TEXT NOT NULL,                  -- 'subnet' | 'wa_ed_investment' | ...
    value       TEXT,
    UNIQUE(request_id, section, key)
);
CREATE INDEX IF NOT EXISTS idx_gpu_request_fields_req ON gpu_request_fields(request_id);
"""


def backup(db_path):
    if not os.path.exists(db_path):
        return None
    backups = os.path.join(ROOT, "backups")
    os.makedirs(backups, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(backups, f"{stamp}-sail-pre-gpu-rebuild.db")
    shutil.copy2(db_path, dst)
    print(f"Backup: {dst}")
    return dst


def column_exists(conn, table, column):
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def add_column_if_missing(conn, table, column, decl):
    if not column_exists(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        print(f"  + {table}.{column}")
    else:
        print(f"  · {table}.{column} already present")


def main():
    if not os.path.exists(DB_PATH):
        print(f"No DB at {DB_PATH}. Run init_db.py first.")
        return
    backup(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        # 1. gpu_requests new columns ──────────────────────────────────────
        print("gpu_requests:")
        add_column_if_missing(
            conn, "gpu_requests", "request_kind",
            # NOTE: SQLite doesn't enforce CHECK on columns added via ALTER,
            # but the column is still there. Code must guard the values.
            "TEXT"
        )
        add_column_if_missing(
            conn, "gpu_requests", "source",
            "TEXT NOT NULL DEFAULT 'manual'"
        )
        add_column_if_missing(
            conn, "gpu_requests", "agent_confidence", "REAL"
        )
        add_column_if_missing(
            conn, "gpu_requests", "raw_extraction_json", "TEXT"
        )
        add_column_if_missing(
            conn, "gpu_requests", "existing_resource_ref", "TEXT"
        )

        # Stamp existing rows with a sensible default kind. The original
        # form only handled BYOC-style new-infra requests, so that's the
        # right backfill value.
        conn.execute(
            "UPDATE gpu_requests SET request_kind = 'new_infra' "
            "WHERE request_kind IS NULL"
        )

        # 2. gpu_request_models gets a count range ────────────────────────
        print("gpu_request_models:")
        add_column_if_missing(
            conn, "gpu_request_models", "gpu_count_max", "INTEGER"
        )

        # 3. tickets gain a GPU-request FK ────────────────────────────────
        print("tickets:")
        add_column_if_missing(
            conn, "tickets", "gpu_request_id",
            "INTEGER REFERENCES gpu_requests(id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_gpu_request "
            "ON tickets(gpu_request_id)"
        )

        # 4. New child tables ─────────────────────────────────────────────
        print("New tables:")
        conn.executescript(NEW_TABLES_DDL)
        for t in (
            "gpu_request_vm_groups",
            "gpu_request_vm_roles",
            "gpu_request_contributions",
            "gpu_request_fields",
        ):
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (t,),
            ).fetchone()
            print(f"  {'+' if row else '!'} {t}")

        conn.commit()
        print("\nMigration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
