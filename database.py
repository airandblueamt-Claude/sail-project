"""Database connection helpers for SAIL."""
import sqlite3
from contextlib import contextmanager
from config import DB_PATH


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_audit(conn, table_name, record_id, action, field_name=None,
              old_value=None, new_value=None, changed_by=None):
    conn.execute(
        """INSERT INTO audit_log
           (table_name, record_id, action, field_name, old_value, new_value, changed_by)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (table_name, record_id, action, field_name,
         str(old_value) if old_value is not None else None,
         str(new_value) if new_value is not None else None,
         changed_by))
