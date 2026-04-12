# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SAIL (Smart Asset Inventory & Logistics) is a dual-application system for IT asset management at AMT. It consists of two independent Flask apps:

- **AssetInventory** (`C:/Users/m.alkhalifa/AssetInventory/`) — Main CRUD app for managing assets, bookings, employees, and audit trails. Runs on port **5000**.
- **AssetAnalytics** (`C:/Users/m.alkhalifa/AssetAnalytics/`) — Standalone upload-and-analyze tool for Excel/CSV asset data with Chart.js visualizations. Runs on port **5001**.

The `sail-project/` directory itself holds reference data (the master Excel equipment list).

## Running the Apps

```bash
# AssetInventory
python C:/Users/m.alkhalifa/AssetInventory/app.py
# → http://localhost:5000

# AssetAnalytics
python C:/Users/m.alkhalifa/AssetAnalytics/app.py
# → http://localhost:5001
```

Dependencies: Flask, openpyxl (no requirements.txt exists — install manually via pip).

## Architecture

### AssetInventory

Flask app factory pattern in `app.py` → registers 6 blueprints:

| Blueprint | Prefix | File | Purpose |
|-----------|--------|------|---------|
| `dashboard_bp` | `/` | `routes/dashboard.py` | Landing page with stats |
| `assets_bp` | `/assets` | `routes/assets.py` | Asset browsing & detail |
| `bookings_bp` | `/bookings` | `routes/bookings.py` | Booking lifecycle (create → approve → checkout → return) |
| `employees_bp` | `/employees` | `routes/employees.py` | Employee CRUD (admin only) |
| `admin_bp` | `/admin` | `routes/admin.py` | Admin panel, audit log, CSV export |
| `api_bp` | `/api` | `routes/api.py` | REST endpoints for AJAX calls |

**Database:** SQLite with WAL mode, foreign keys enabled. Schema is in `database.py` (inline SQL). Tables: `categories`, `locations`, `employees`, `assets`, `bookings`, `audit_log`. The `get_db()` context manager handles connection lifecycle with auto-commit/rollback.

**Auth:** Session-based login by badge number or employee name (no password). User loaded into `g.user` via `before_request`. Admin vs employee role check gates certain routes.

**Data import:** `import_csv.py` imports from AppSheet-exported CSV, normalizing categories (see `CATEGORY_FIXES` in `config.py`) and locations.

**Config:** `config.py` defines `DB_PATH`, `UPLOAD_FOLDER`, `PAGE_SIZE`, `BOOKABLE_CATEGORIES` (only IT equipment is bookable, not furniture), and `SECRET_KEY`.

### AssetAnalytics

Single-file Flask app (`app.py`). No database — uses in-memory `DATASETS` dict keyed by session ID. Pipeline: upload → parse (Excel via openpyxl or CSV) → configure column mapping → dashboard with analytics. Supports CRUD on the in-memory dataset and CSV export.

### Frontend

Both apps use Jinja2 templates with a shared design language: custom CSS with light/dark theme (CSS variables, persisted in localStorage), Lucide icons, and Chart.js for visualizations. No frontend build step — all static assets served directly.

### Branding

AMT logo files are in `static/`: `amt-logo.png` (red logo on transparent, for light backgrounds) and `amt-logo-white.png` (same logo — both are red on transparent). The sidebar wraps the logo in a `.logo-wrap` container that switches background: white in light theme, dark in dark theme. Always use the AMT logo for branding, not text logos.

## Key Business Rules

- Only categories in `BOOKABLE_CATEGORIES` (config.py) can be booked — these are IT equipment types, not furniture
- Booking status workflow: `pending` → `approved` → `checked_out` → `returned`
- All data mutations in AssetInventory are tracked in the `audit_log` table
- Asset conditions: `good`, `fair`, `damaged`, `decommissioned`
