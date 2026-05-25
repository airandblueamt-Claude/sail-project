# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SAIL (Smart Asset Inventory & Logistics) is a single Flask app for IT asset management at AMT. It handles an equipment catalog, individual asset tracking, and issue tracking (all tickets are recorded as type `incident`).

The booking module (reserve→approve→checkout→return) has been deliberately removed. The only remaining workflow for users is submitting and tracking tickets. Admins manage equipment, assets, and tickets.

The entire app lives in this directory — there is no separate analytics/inventory split.

## Running the App

```bash
pip install -r requirements.txt   # flask, openpyxl
python init_db.py                 # creates an empty sail.db from schema.sql
python import_assets_v3.py        # loads "Assets Inventory _20-04-2026-Tool (V3).xlsx" (230 assets)
python app.py                     # serves http://localhost:5555
```

- The four control-team accounts are seeded by `init_db.py` with password `Aramco@123` and role `admin`. There is no public `/register` route; admins create new users from the Employees page. New users should change their password at `/account/password` after first login.
- Email notifications need `SAIL_SMTP_PASSWORD` (Gmail app password) in the env; without it the app runs fine but silently skips sending.
- `python backup_db.py` — timestamped copy in `backups/`, keeps the last 10.

There is no test suite, linter, or build step configured.

After pulling, apply any new schema migrations before starting the app:

```bash
python migrations/<latest-dated>.py   # idempotent; backs up sail.db first
```

## Architecture

### Flask app factory + blueprints

`app.py` defines `create_app()` and owns auth (login/register/logout) directly. Everything else is a blueprint registered from `routes/`:

| Blueprint | Prefix | Purpose |
|-----------|--------|---------|
| `dashboard_bp` | `/` | Role-aware landing stats |
| `inventory_bp` | `/inventory` | Equipment model browser + admin full-inventory CRUD + photo uploads |
| `tickets_bp` | `/tickets` | Tickets with comments, priority, assignment |
| `employees_bp` | `/employees` | Employee management (admin) |
| `reports_bp` | `/reports` | Admin-only weekly/monthly rollups for inventory & tickets, with CSV export |
| `help_bp` | `/help` | In-app guide |
| `issue_categories_bp` | `/issue-categories` | Admin CRUD for the ticket `issue_categories` catalog |
| `gpu_bp` | `/gpu` | Separate GPU subsystem (see below) |
| `floor_plan_bp` | `/floor-plan` | Interactive floor-plan view of asset locations |
| `api_bp` | `/api/v1` | Read-only JSON API for external agents — bearer-token auth (see below) |

Auth is session-based (email + password, validated against `employees.password_hash` via `werkzeug.security`). `before_request` loads the user from `session['user_id']` into `g.user` and redirects unauthenticated requests to `/login` except for `login` and `static`.

### Data model — the core distinction

The schema draws a hard line between product lines and physical units:

- **`equipment_models`** = one row per product line (e.g. "30 Lenovo Workstations"). Carries brand, specs, `expected_qty`, and the shared photo path.
- **`assets`** = individual physical units with their own `asset_tag` (`SAIL-0001`), serial, location, `condition`, and `status`. `qty_represented > 1` lets one asset row stand for a bulk lot that isn't worth tagging individually.
- **Tickets attach to `assets`** (optionally). The ticket system is the primary user-facing workflow.

Other tables: `categories`, `locations`, `departments`, `tickets` + `ticket_comments`, `issue_categories`, and `audit_log`.

### Database access pattern

`database.py` exposes a single `get_db()` context manager — SQLite with `PRAGMA foreign_keys=ON` and WAL mode, auto-commit on success, rollback on exception. **Always** use it as `with get_db() as conn:`; don't open raw connections. Mutations should call `log_audit(conn, table, record_id, action, …)` in the same transaction so history lands in `audit_log` atomically.

### Status/enum values (enforced by CHECK constraints)

- `employees.role`: `admin` / `manager` / `technician` / `employee`
- `assets.condition`: `good` / `fair` / `damaged` / `decommissioned`
- `assets.status`: `available` / `assigned` / `reserved` / `missing`
- `tickets.type`: `maintenance` / `move` / `new_request` / `incident` / `decommission` / `other`
- `tickets.priority`: `low` / `medium` / `high` / `critical`
- `tickets.status`: `open` / `in_progress` / `waiting` / `resolved` / `closed`

Changing any of these means editing `schema.sql` **and** the form/template values — SQLite will reject non-matching inserts silently-looking but fatally.

### GPU subsystem

The GPU work (cluster nodes, accelerator cards, time-bound access requests) lives in its own tables — `gpu_assets` and `gpu_requests` — and its own blueprint (`routes/gpu.py`). It does **not** share the `assets` / `tickets` schema, deliberately: requests have their own number sequence (`GPUR-NNNN`), an approval flow distinct from tickets, and per-block date/hour validation. Treat it as a sibling subsystem, not a flavour of the main inventory.

### External JSON API (`/api/v1`)

`routes/api.py` exposes a read-only JSON API for external agents (Ollama, Claude, etc.). Conventions worth knowing before extending it:

- **Auth**: `Authorization: Bearer sail_<hex>`. Tokens are minted by `scripts/mint_api_token.py`; the plaintext is printed **once** and only `sha256(plaintext)` is stored in `api_tokens.token_hash`. There is no way to recover a lost token — re-mint and revoke.
- **Scopes**: comma-separated string on the token row. Every current route uses `@require_token('read')`. When you add write routes, introduce a `write` scope rather than widening `read`.
- **Pagination**: `?limit=` (default 50, max 500) + `?offset=`; responses always shape as `{items, total, limit, offset}` (collections) or the bare object (single resource).
- **Serializers**: `_serialize_asset`, `_serialize_ticket`, `_serialize_employee` are the single source of truth for response shape — don't hand-build dicts in route handlers.
- Mint / list / revoke: `python scripts/mint_api_token.py --name X --email Y@… [--scopes read]`, `--list`, `--revoke <id>`.

### Schema migrations

Two parallel mechanisms — pick the right one:

- **`migrations/<YYYY-MM-DD>-<slug>.py`** — dated, idempotent, single-purpose scripts. Each one backs up `sail.db` into `backups/` before mutating, uses `CREATE TABLE IF NOT EXISTS` / equivalent guards, and is safe to re-run. This is the preferred path for new schema changes. Run with `python migrations/<file>.py`.
- **`migrate_db.py`** — older catch-all migration runner. Don't add new logic to it; write a new dated script in `migrations/` instead.

`schema.sql` is still the source of truth for a **fresh** install (`init_db.py` applies it). When you add a migration, also update `schema.sql` so newly-initialised DBs start with the new shape.

### Email

`email_service.py` wraps Gmail SMTP with helpers like `notify_registration`, and ticket notifications (`notify_ticket_created`, `notify_ticket_update`). Config lives in `config.py` (`ADMIN_EMAIL`, `SMTP_EMAIL`, `SMTP_HOST`, `SMTP_PORT`, `APP_URL`); the password comes from `SAIL_SMTP_PASSWORD`.

### Frontend

Jinja2 templates in `templates/`, one shared `static/style.css` driving a custom design system with CSS-variable-based light/dark theme (persisted in localStorage). Lucide icons, Chart.js for dashboard charts. No build step.

Branding: both `static/amt-logo.png` and `static/amt-logo-white.png` are the red AMT logo on transparent; the sidebar's `.logo-wrap` switches its background per theme. Use the logo, not text.

### Data import / export scripts

- `init_db.py` — applies `schema.sql` to create an empty `sail.db`. Wipes any existing DB.
- `import_assets_v3.py` — reads `Assets Inventory _20-04-2026-Tool (V3).xlsx` (sheet `IT Assets`), derives `categories` / `locations` / `equipment_models`, and inserts 230 rows into `assets`. Backs up the DB first; supports `--dry-run` and `--xlsx PATH`. The V3 spreadsheet is the single source of truth for inventory.
- `export_clean.py` — dumps the DB back to a formatted Excel workbook.

## Design docs

`docs/superpowers/specs/` holds design specs; `docs/superpowers/plans/` holds implementation plans (one file per feature, dated). Check these before starting significant new features — recent work: the ticket kanban/SLA board.
