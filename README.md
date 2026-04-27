# SAIL — Smart Asset Inventory & Logistics

Internal asset management system for AMT. Tracks equipment inventory, handles bookings (reserve → approve → checkout → return), and manages support tickets — all in one place.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-green)
![SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey)

## Features

- **Equipment Inventory** — 151 equipment models imported from the master equipment list, organized by category
- **Browse & Book** — employees see only bookable items (38 models), pick an asset, select dates, submit a request
- **Booking Workflow** — admin approves/rejects → hands over equipment → receives return
- **Ticketing** — maintenance, incidents, move requests, new equipment requests with priority and assignment
- **Role-Based Access** — employees vs admin/manager, each sees only what they need
- **Email Notifications** — automatic emails on registration, booking status changes, and ticket updates via Gmail SMTP
- **Equipment Photos** — upload images per equipment model, shown on browse cards and detail pages
- **Audit Log** — all changes tracked
- **Dark/Light Theme**

## Quick Start

```bash
# Clone
git clone https://github.com/YOUR_ORG/sail-project.git
cd sail-project

# Install dependencies
pip install -r requirements.txt

# Initialize the database (creates an empty sail.db from schema.sql)
python init_db.py

# Load the V3 inventory spreadsheet (230 assets)
python import_assets_v3.py

# Run
python app.py
```

Open **http://localhost:5555** — register with your email, then log in.

### First-Time Admin Setup

1. Register your account at `/register`
2. Open the database and set your role to admin:
   ```bash
   python -c "
   from database import get_db
   with get_db() as conn:
       conn.execute(\"UPDATE employees SET role='admin' WHERE email='your@email.com'\")
   "
   ```
3. You now have access to: Booking Approvals, Full Inventory, Manage Assets, Employees

## Email Notifications

SAIL sends automated emails via Gmail SMTP. To enable:

1. Go to [Google App Passwords](https://myaccount.google.com/apppasswords) for your sender account
2. Generate an App Password
3. Set it as an environment variable before running:
   ```bash
   # Windows
   set SAIL_SMTP_PASSWORD=xxxx xxxx xxxx xxxx

   # Linux/Mac
   export SAIL_SMTP_PASSWORD="xxxx xxxx xxxx xxxx"
   ```
4. Update `ADMIN_EMAIL` and `SMTP_EMAIL` in `config.py`

Without a password configured, the app works normally but skips sending emails.

## Project Structure

```
sail-project/
├── app.py                  # Flask app factory, auth routes
├── config.py               # Configuration (DB, SMTP, etc.)
├── database.py             # SQLite connection helpers, audit logging
├── email_service.py        # Email notification functions
├── schema.sql              # Full database schema
├── init_db.py              # DB schema bootstrap (empty sail.db)
├── import_assets_v3.py     # Loads V3 inventory spreadsheet → assets
├── export_clean.py         # DB → formatted Excel export
├── backup_db.py            # Database backup utility
├── requirements.txt
├── routes/
│   ├── dashboard.py        # Landing page with role-aware stats
│   ├── inventory.py        # Browse, book, manage equipment
│   ├── bookings.py         # Booking flow + admin approvals
│   ├── tickets.py          # Ticketing system
│   ├── employees.py        # Employee management
│   └── help.py             # In-app guide
├── templates/              # Jinja2 HTML templates
├── static/
│   ├── style.css           # Full design system (light/dark)
│   ├── amt-logo.png
│   ├── amt-logo-white.png
│   └── uploads/            # Equipment photos
└── backups/                # Database snapshots
```

## Database

SQLite with WAL mode and foreign keys. Key tables:

| Table | Purpose |
|-------|---------|
| `categories` | Equipment categories (14) |
| `equipment_models` | Product lines — brand, specs, qty, bookable flag, photo |
| `assets` | Individual physical units with asset tags (SAIL-0001) |
| `employees` | Users with roles (employee, technician, manager, admin) |
| `bookings` | Reservations: pending → approved → checked_out → returned |
| `tickets` | Support requests with priority, assignment, comments |
| `audit_log` | Change history |

### Backup

```bash
python backup_db.py
```

Creates a timestamped copy in `backups/`, keeps the last 10.

## Booking Workflow

```
Employee submits request
        ↓
   [PENDING] ── admin rejects ──→ [REJECTED]
        ↓
   [APPROVED] ── employee picks up
        ↓
   [CHECKED OUT] ── employee returns
        ↓
   [RETURNED] ── asset back to available
```

## License

Internal use — AMT.
