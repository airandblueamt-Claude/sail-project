"""Backup the SAIL database to a timestamped file."""
import shutil
import os
from datetime import datetime
from config import DB_PATH

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")


def backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"sail_{timestamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup saved to {backup_path}")

    # Keep only last 10 backups
    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')],
        reverse=True
    )
    for old in backups[10:]:
        os.remove(os.path.join(BACKUP_DIR, old))
        print(f"  Removed old backup: {old}")

    return backup_path


if __name__ == "__main__":
    backup()
