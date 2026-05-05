"""
Migration — 2026-05-05 — separate GPU subsystem (six tables)

Lives entirely apart from the existing assets/tickets domain:

    gpu_assets              — hosts + GPUs (parent_asset_id self-ref)
    gpu_requests            — allocation requests (parent record)
    gpu_request_models      — line items: requested models / VRAM / count
    gpu_request_workloads   — line items: workload breakdown
    gpu_request_deliverables - line items: partner deliverables
    gpu_request_phases      — line items: phased timeline

Idempotent: safe to re-run via CREATE TABLE/INDEX IF NOT EXISTS.

Usage:
    python3 migrations/2026-05-05-add-gpu-system.py
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
CREATE TABLE IF NOT EXISTS gpu_assets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_tag       TEXT NOT NULL UNIQUE,
    kind            TEXT NOT NULL CHECK(kind IN ('host','gpu')),
    model           TEXT,
    vram_gb         INTEGER,
    xcc_ip          TEXT,
    cluster         TEXT,
    node_role       TEXT,
    pci_slot        INTEGER,
    parent_asset_id INTEGER REFERENCES gpu_assets(id),
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_gpu_assets_parent ON gpu_assets(parent_asset_id);
CREATE INDEX IF NOT EXISTS idx_gpu_assets_kind   ON gpu_assets(kind);

CREATE TABLE IF NOT EXISTS gpu_requests (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    request_number       TEXT NOT NULL UNIQUE,
    title                TEXT NOT NULL,
    use_case             TEXT,
    requester_id         INTEGER REFERENCES employees(id),
    requester_name       TEXT,
    requester_email      TEXT,
    requester_org        TEXT,
    requester_type       TEXT DEFAULT 'internal'
                         CHECK(requester_type IN ('internal','partner','academic','vendor')),
    requested_hours      INTEGER,
    start_date           TEXT,
    end_date             TEXT,
    duration_text        TEXT,
    notes                TEXT,
    decision             TEXT,
    fit_notes            TEXT,
    response_notes       TEXT,
    allocated_asset_tags TEXT,
    decided_by           INTEGER REFERENCES employees(id),
    decided_at           TEXT,
    created_at           TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_gpu_requests_decided   ON gpu_requests(decided_at);
CREATE INDEX IF NOT EXISTS idx_gpu_requests_requester ON gpu_requests(requester_id);

CREATE TABLE IF NOT EXISTS gpu_request_models (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id  INTEGER NOT NULL REFERENCES gpu_requests(id) ON DELETE CASCADE,
    sort_order  INTEGER DEFAULT 0,
    model_name  TEXT NOT NULL,
    vram_gb     INTEGER,
    gpu_count   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_gpu_request_models_req ON gpu_request_models(request_id);

CREATE TABLE IF NOT EXISTS gpu_request_workloads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id      INTEGER NOT NULL REFERENCES gpu_requests(id) ON DELETE CASCADE,
    sort_order      INTEGER DEFAULT 0,
    name            TEXT NOT NULL,
    config          TEXT,
    estimated_hours INTEGER
);
CREATE INDEX IF NOT EXISTS idx_gpu_request_workloads_req ON gpu_request_workloads(request_id);

CREATE TABLE IF NOT EXISTS gpu_request_deliverables (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id  INTEGER NOT NULL REFERENCES gpu_requests(id) ON DELETE CASCADE,
    sort_order  INTEGER DEFAULT 0,
    description TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gpu_request_deliverables_req ON gpu_request_deliverables(request_id);

CREATE TABLE IF NOT EXISTS gpu_request_phases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id  INTEGER NOT NULL REFERENCES gpu_requests(id) ON DELETE CASCADE,
    sort_order  INTEGER DEFAULT 0,
    name        TEXT NOT NULL,
    target_date TEXT,
    description TEXT
);
CREATE INDEX IF NOT EXISTS idx_gpu_request_phases_req ON gpu_request_phases(request_id);
"""


def backup(db_path):
    if not os.path.exists(db_path):
        return None
    backups = os.path.join(ROOT, "backups")
    os.makedirs(backups, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(backups, f"{stamp}-sail-pre-gpu-system.db")
    shutil.copy2(db_path, dst)
    print(f"Backup: {dst}")
    return dst


def main():
    if not os.path.exists(DB_PATH):
        print(f"No DB at {DB_PATH}. Run init_db.py first.")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        existing = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'gpu_%'"
        ).fetchall()}
        wanted = {'gpu_assets', 'gpu_requests', 'gpu_request_models',
                  'gpu_request_workloads', 'gpu_request_deliverables',
                  'gpu_request_phases'}
        if wanted.issubset(existing):
            print("All six gpu_* tables already present — refreshing indexes.")
        else:
            backup(DB_PATH)
        conn.executescript(DDL)
        conn.commit()
        print("Migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
