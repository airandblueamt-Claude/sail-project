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
| Mohammad Khalifa | airandblueamt@gmail.com | Aramco@123 |
| M. Shaikh | m.shaikh@amt-arabia.net | Aramco@123 |
| Omar Bawadod | omar.bawadod@aramco.com | Aramco@123 |
| Ali Almatrood | ali.almatrood@aramco.com | Aramco@123 |

All four accounts have role `admin`. The seed password is intentionally weak so the team can log in immediately — change yours at `/account/password` after first login. New users are added via **Employees → + Add Employee** (no public registration).

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SAIL_SECRET_KEY` | dev placeholder | Flask session secret — **must** be set to a random string in production |
| `SAIL_SMTP_PASSWORD` | _(none)_ | Gmail app password for outbound email; app works without it |
| `SAIL_DEBUG` | `0` | Set to `1` to enable Flask debug mode |
| `SAIL_HOST` | `127.0.0.1` | Bind address; set to `0.0.0.0` to expose to LAN |
| `SAIL_PORT` | `5555` | Port to listen on |
| `SAIL_DB_PATH` | `./sail.db` | Where to keep the SQLite file (point at a mounted volume in prod) |
| `SAIL_DATA_DIR` | `./` | Used by the Docker entrypoint as the parent for the uploads symlink |
| `SAIL_APP_URL` | `http://localhost:5555` | Used in outbound email templates |

## Deploying to Fly.io

Free-tier Fly.io is a good fit for this app — it gives you persistent volumes (so `sail.db` survives restarts) and HTTPS out of the box. Files in the repo:

- `Dockerfile` — Python 3.12-slim image
- `entrypoint.sh` — symlinks `static/uploads` → the persistent volume, runs `init_db.py` + `import_assets_v3.py` if the DB doesn't exist yet, then starts gunicorn on port 8080
- `fly.toml` — app name, region, volume mount, HTTP service config
- `wsgi.py` — gunicorn entrypoint (`wsgi:app`)

One-time setup:

```bash
# 1. Install flyctl and sign in.
curl -L https://fly.io/install.sh | sh
fly auth signup       # or: fly auth login

# 2. Edit fly.toml — pick a unique app name and a region near you.
#    `fly platform regions` lists options (e.g. fra, dxb, sin, iad, lhr).

# 3. Create the app and the persistent volume.
fly apps create <your-app-name>
fly volumes create sail_data --region <your-region> --size 1

# 4. Set production secrets.
fly secrets set \
    SAIL_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')" \
    SAIL_SMTP_PASSWORD="<gmail-app-password>" \
    SAIL_APP_URL="https://<your-app-name>.fly.dev"

# 5. Deploy.
fly deploy
```

The first boot runs `init_db.py + import_assets_v3.py` automatically because the volume is empty. Subsequent deploys keep the data — they just restart gunicorn.

Useful commands:

```bash
fly logs              # tail app logs
fly ssh console       # shell into the running container
fly status            # health + restart count
fly secrets list      # see which env vars are set (values not shown)
fly volumes list      # confirm sail_data exists and is mounted
```

If you ever need to wipe and re-seed:

```bash
fly ssh console
> rm /data/sail.db        # next restart will rebuild
> exit
fly machine restart
```

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
