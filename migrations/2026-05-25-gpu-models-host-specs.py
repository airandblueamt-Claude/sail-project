"""
Migration — 2026-05-25b — extend gpu_request_models with host specs

The OrbitronAI BYOC sample doc treats each GPU option as a full HOST
configuration, not just a card. The doc's GPU table has:

    Use Case | Count | vCPU | RAM | GPU | VRAM | Disk | OS

Our gpu_request_models row had only the (GPU, VRAM, Count) trio, so a
chunk of real-world data was being dropped into notes or split awkwardly
into VM groups. This migration adds:

    use_case_label  — e.g. "Up to 14B FP16", "70B FP16 / on-prem best value"
    host_vcpu       — vCPUs on the GPU node (not the card)
    host_ram_gb     — RAM on the GPU node
    host_disk_gb    — disk on the GPU node
    host_os         — OS on the GPU node, e.g. "Ubuntu 24.04 LTS"

All nullable, so KFUPM-style short lists keep working unchanged.
Idempotent.

Usage:
    python3 migrations/2026-05-25-gpu-models-host-specs.py
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


def backup(db_path):
    if not os.path.exists(db_path):
        return None
    backups = os.path.join(ROOT, "backups")
    os.makedirs(backups, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(backups, f"{stamp}-sail-pre-gpu-host-specs.db")
    shutil.copy2(db_path, dst)
    print(f"Backup: {dst}")
    return dst


def column_exists(conn, table, column):
    return any(r[1] == column for r in conn.execute(f"PRAGMA table_info({table})").fetchall())


def add(conn, table, column, decl):
    if column_exists(conn, table, column):
        print(f"  · {table}.{column} already present")
    else:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        print(f"  + {table}.{column}")


def main():
    if not os.path.exists(DB_PATH):
        print(f"No DB at {DB_PATH}. Run init_db.py first.")
        return
    backup(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        print("gpu_request_models:")
        add(conn, "gpu_request_models", "use_case_label", "TEXT")
        add(conn, "gpu_request_models", "host_vcpu",      "INTEGER")
        add(conn, "gpu_request_models", "host_ram_gb",    "INTEGER")
        add(conn, "gpu_request_models", "host_disk_gb",   "INTEGER")
        add(conn, "gpu_request_models", "host_os",        "TEXT")
        conn.commit()
        print("\nMigration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
