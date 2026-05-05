"""
Seed — 2026-05-05 — load 16 hosts + 30 GPUs into gpu_assets.

Source: real hardware list provided by the user (XCC management IP +
Lenovo serial + per-host GPU count). Asset tag = the Lenovo serial
sticker for hosts; GPU asset tags follow GPU-HPC-NNN / GPU-CLOUD-NNN.

Idempotent: existing rows (matched by asset_tag) are left alone.

Usage:
    python3 migrations/2026-05-05-seed-gpu-system.py
"""
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
sys.path.insert(0, ROOT)

from config import DB_PATH

# (serial, cluster, role, xcc_ip, model, notes)
HOSTS = [
    ('J30A1YBH', 'VMware Cloud', 'Cloud / HCI',  '10.158.104.85',  'ESXi Host',            None),
    ('J30A1YBM', 'VMware Cloud', 'Cloud / HCI',  '10.158.104.86',  'ESXi Host',            None),
    ('J30A1YBK', 'VMware Cloud', 'Cloud / HCI',  '10.158.104.87',  'ESXi Host',            None),
    ('J30A1YBL', 'VMware Cloud', 'Cloud / HCI',  '10.158.104.88',  'ESXi Host',            None),
    ('J30A21Y3', 'HPC-Linux',    'Head',         '10.158.104.80',  'HPC Head Node',        'No GPU'),
    ('J30A23YL', 'HPC-Linux',    'Accelerator',  '10.158.104.91',  'HPC Accelerator Node', '1x A40'),
    ('J30A23YK', 'HPC-Linux',    'Compute',      '10.158.104.92',  'HPC Compute Node',     '2x T4'),
    ('J30A23YG', 'HPC-Linux',    'Compute',      '10.158.104.93',  'HPC Compute Node',     '2x T4'),
    ('J30A23YH', 'HPC-Linux',    'Compute',      '10.158.104.94',  'HPC Compute Node',     '2x T4'),
    ('J30A238V', 'HPC-Linux',    'Accelerator',  '10.158.104.95',  'HPC Accelerator Node', '4x A40'),
    ('J30A21Y2', 'HPC-Linux',    'Head',         '10.158.104.110', 'HPC Head Node',        'No GPU'),
    ('J30A23YD', 'HPC-Linux',    'Accelerator',  '10.158.104.111', 'HPC Accelerator Node', '1x A40'),
    ('J30A23YF', 'HPC-Linux',    'Compute',      '10.158.104.112', 'HPC Compute Node',     '2x T4'),
    ('J30A23YN', 'HPC-Linux',    'Compute',      '10.158.104.113', 'HPC Compute Node',     '2x T4'),
    ('J30A23YE', 'HPC-Linux',    'Compute',      '10.158.104.114', 'HPC Compute Node',     '2x T4'),
    ('J30A238T', 'HPC-Linux',    'Accelerator',  '10.158.104.115', 'HPC Accelerator Node', '4x A40'),
]

# (gpu_tag, parent_serial, model, vram_gb, pci_slot)
GPUS = [
    ('GPU-CLOUD-001', 'J30A1YBH', 'NVIDIA A40', 48, 1),
    ('GPU-CLOUD-002', 'J30A1YBH', 'NVIDIA A40', 48, 2),
    ('GPU-CLOUD-003', 'J30A1YBM', 'NVIDIA A40', 48, 1),
    ('GPU-CLOUD-004', 'J30A1YBM', 'NVIDIA A40', 48, 2),
    ('GPU-CLOUD-005', 'J30A1YBK', 'NVIDIA A40', 48, 1),
    ('GPU-CLOUD-006', 'J30A1YBK', 'NVIDIA A40', 48, 2),
    ('GPU-CLOUD-007', 'J30A1YBL', 'NVIDIA A40', 48, 1),
    ('GPU-CLOUD-008', 'J30A1YBL', 'NVIDIA A40', 48, 2),
    ('GPU-HPC-001',   'J30A23YL', 'NVIDIA A40', 48, 1),
    ('GPU-HPC-002',   'J30A23YK', 'NVIDIA T4',  16, 1),
    ('GPU-HPC-003',   'J30A23YK', 'NVIDIA T4',  16, 2),
    ('GPU-HPC-004',   'J30A23YG', 'NVIDIA T4',  16, 1),
    ('GPU-HPC-005',   'J30A23YG', 'NVIDIA T4',  16, 2),
    ('GPU-HPC-006',   'J30A23YH', 'NVIDIA T4',  16, 1),
    ('GPU-HPC-007',   'J30A23YH', 'NVIDIA T4',  16, 2),
    ('GPU-HPC-008',   'J30A238V', 'NVIDIA A40', 48, 1),
    ('GPU-HPC-009',   'J30A238V', 'NVIDIA A40', 48, 2),
    ('GPU-HPC-010',   'J30A238V', 'NVIDIA A40', 48, 3),
    ('GPU-HPC-011',   'J30A238V', 'NVIDIA A40', 48, 4),
    ('GPU-HPC-012',   'J30A23YD', 'NVIDIA A40', 48, 1),
    ('GPU-HPC-013',   'J30A23YF', 'NVIDIA T4',  16, 1),
    ('GPU-HPC-014',   'J30A23YF', 'NVIDIA T4',  16, 2),
    ('GPU-HPC-015',   'J30A23YN', 'NVIDIA T4',  16, 1),
    ('GPU-HPC-016',   'J30A23YN', 'NVIDIA T4',  16, 2),
    ('GPU-HPC-017',   'J30A23YE', 'NVIDIA T4',  16, 1),
    ('GPU-HPC-018',   'J30A23YE', 'NVIDIA T4',  16, 2),
    ('GPU-HPC-019',   'J30A238T', 'NVIDIA A40', 48, 1),
    ('GPU-HPC-020',   'J30A238T', 'NVIDIA A40', 48, 2),
    ('GPU-HPC-021',   'J30A238T', 'NVIDIA A40', 48, 3),
    ('GPU-HPC-022',   'J30A238T', 'NVIDIA A40', 48, 4),
]


def main():
    if not os.path.exists(DB_PATH):
        print(f"No DB at {DB_PATH}. Run init_db.py first.")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        host_ids = {}
        for serial, cluster, role, xcc_ip, model, notes in HOSTS:
            row = conn.execute(
                "SELECT id FROM gpu_assets WHERE asset_tag = ?", (serial,)
            ).fetchone()
            if row:
                host_ids[serial] = row["id"]
                print(f"  host exists: {serial}")
                continue
            cur = conn.execute(
                "INSERT INTO gpu_assets "
                "(asset_tag, kind, model, xcc_ip, cluster, node_role, notes) "
                "VALUES (?, 'host', ?, ?, ?, ?, ?)",
                (serial, model, xcc_ip, cluster, role, notes))
            host_ids[serial] = cur.lastrowid
            print(f"  host created: {serial}  ({xcc_ip}, {role})")

        for tag, parent_serial, model, vram, slot in GPUS:
            row = conn.execute(
                "SELECT id FROM gpu_assets WHERE asset_tag = ?", (tag,)
            ).fetchone()
            if row:
                print(f"  GPU exists: {tag}")
                continue
            parent_id = host_ids.get(parent_serial)
            if parent_id is None:
                print(f"  ! skip {tag}: parent {parent_serial} missing")
                continue
            host_row = conn.execute(
                "SELECT cluster, node_role FROM gpu_assets WHERE id = ?",
                (parent_id,)).fetchone()
            conn.execute(
                "INSERT INTO gpu_assets "
                "(asset_tag, kind, model, vram_gb, cluster, node_role, "
                " pci_slot, parent_asset_id) "
                "VALUES (?, 'gpu', ?, ?, ?, ?, ?, ?)",
                (tag, model, vram, host_row["cluster"], host_row["node_role"],
                 slot, parent_id))
            print(f"  GPU created: {tag} -> {parent_serial} (slot {slot})")

        conn.commit()
        n_hosts = conn.execute(
            "SELECT COUNT(*) FROM gpu_assets WHERE kind='host'").fetchone()[0]
        n_gpus = conn.execute(
            "SELECT COUNT(*) FROM gpu_assets WHERE kind='gpu'").fetchone()[0]
        print(f"\nDone. gpu_assets has {n_hosts} hosts, {n_gpus} GPUs.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
