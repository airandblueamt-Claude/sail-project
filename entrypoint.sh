#!/bin/sh
# Container entrypoint: ensure the persistent volume is wired up,
# bootstrap the DB on first boot, then hand off to gunicorn.

set -e

DATA_DIR="${SAIL_DATA_DIR:-/data}"
DB_FILE="${SAIL_DB_PATH:-$DATA_DIR/sail.db}"

mkdir -p "$DATA_DIR/uploads"

# Templates use url_for('static', filename='uploads/...') so uploads MUST
# resolve under /app/static/uploads. Replace the baked (empty) directory
# with a symlink to the persistent volume so files survive restarts.
if [ ! -L /app/static/uploads ]; then
    rm -rf /app/static/uploads
    ln -sfn "$DATA_DIR/uploads" /app/static/uploads
fi

# Bootstrap the schema + seed + asset import on first boot only.
if [ ! -f "$DB_FILE" ]; then
    echo "[entrypoint] No DB at $DB_FILE — running init_db.py + import_assets_v3.py"
    python init_db.py
    python import_assets_v3.py
else
    # schema.sql is fully idempotent (CREATE TABLE/INDEX IF NOT EXISTS).
    # Re-applying it on every boot picks up any newly added tables/indexes
    # without touching existing data.
    echo "[entrypoint] DB exists at $DB_FILE — applying schema.sql for any new tables"
    python -c "import sqlite3, os; conn = sqlite3.connect(os.environ.get('SAIL_DB_PATH', '$DB_FILE')); conn.executescript(open('schema.sql').read()); conn.commit(); conn.close()"
fi

# Run the production WSGI server.
exec gunicorn \
    -b 0.0.0.0:8080 \
    -w 2 \
    -k gthread \
    --threads 4 \
    --access-logfile - \
    --error-logfile - \
    wsgi:app
