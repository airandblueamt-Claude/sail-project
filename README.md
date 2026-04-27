# SAIL — Smart Asset Inventory & Logistics

SAIL is an internal asset issue tracker for the AMT control team. The team logs equipment faults against individual assets, assigns repair work to operation-team technicians, and accumulates a per-asset issue history over time. End users email the control team; the team raises the ticket in SAIL on their behalf.

## Setup

```bash
pip install -r requirements.txt
python init_db.py            # creates sail.db from schema.sql + seeds 4 admin accounts
python import_assets_v3.py  # loads "Assets Inventory _20-04-2026-Tool (V3).xlsx" (230 assets)
python app.py                # serves http://127.0.0.1:5555
```

## Login Credentials (seeded by init_db.py)

| Name | Email | Password |
|------|-------|----------|
| Mohammed Al-Khalifa | airandblueamt@gmail.com | Aramco@123 |
| Ahmed Al-Rashidi | ahmed.alrashidi@amt.sa | Aramco@123 |
| Sara Al-Mutairi | sara.almutairi@amt.sa | Aramco@123 |
| Khalid Al-Dosari | khalid.aldosari@amt.sa | Aramco@123 |

All four accounts have role `admin` and will be prompted to change their password on first login. New users are added via **Employees → + Add Employee** (no public registration).

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SAIL_SECRET_KEY` | dev placeholder | Flask session secret — **must** be set to a random string in production |
| `SAIL_SMTP_PASSWORD` | _(none)_ | Gmail app password for outbound email; app works without it |
| `SAIL_DEBUG` | `0` | Set to `1` to enable Flask debug mode |
| `SAIL_HOST` | `127.0.0.1` | Bind address; set to `0.0.0.0` to expose to LAN |
| `SAIL_PORT` | `5555` | Port to listen on |

## Project Layout

```
app.py                  # Flask app factory, auth routes (login / password change)
config.py               # Configuration (DB path, SMTP, secret key)
database.py             # SQLite context manager, audit logging
email_service.py        # Email notification helpers (Gmail SMTP)
schema.sql              # Full database schema
init_db.py              # Bootstrap empty sail.db + seed admin accounts
import_assets_v3.py     # Load V3 inventory spreadsheet → assets table
routes/
    dashboard.py        # Role-aware landing page with stats
    inventory.py        # Equipment catalog + asset management + photo uploads
    tickets.py          # Ticket lifecycle (raise, assign, update, resolve)
    employees.py        # Employee management (admin)
    reports.py          # Weekly/monthly rollups with CSV export
    issue_categories.py # Issue category management
    help.py             # In-app guide
templates/              # Jinja2 HTML templates
static/style.css        # Design system (CSS variables, light/dark theme)
```

See `CLAUDE.md` for architectural detail, schema notes, and status/enum values.

## License

Internal use — AMT.
