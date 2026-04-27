-- ============================================================================
-- SAIL — Smart Asset Inventory & Logistics
-- Database Schema  (SQLite, WAL mode, FK enforced)
-- ============================================================================
--
-- Key design decisions:
--   - equipment_models = the "product line" (one row per CSV line: 30 Lenovo
--     Workstations is one model).  assets = individual physical units that
--     get asset tags, serial numbers, locations, and bookings.
--   - Tickets cover maintenance requests, move requests, new-equipment
--     requests, and incident reports — all in one table with a type column.
--   - Bookings mirror the room-reservation pattern: request → approve →
--     check-out → return.
-- ============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ── Lookup / reference tables ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,              -- "Computers & Peripherals"
    description TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS locations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,              -- "W-1300", "DC-01", "STORAGE-A"
    label       TEXT,                              -- "Main Lab", "Data Center Room 1"
    building    TEXT,
    floor       TEXT,
    is_storage  INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS departments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- ── People ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS employees (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    badge_number    TEXT UNIQUE,
    department_id   INTEGER REFERENCES departments(id),
    phone           TEXT,
    email           TEXT,
    role            TEXT DEFAULT 'employee'
                    CHECK(role IN ('admin','manager','technician','employee')),
    password_hash   TEXT,
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_employees_badge ON employees(badge_number);
CREATE INDEX IF NOT EXISTS idx_employees_dept  ON employees(department_id);

-- ── Equipment models (one row per product line / CSV line) ──────────────────

CREATE TABLE IF NOT EXISTS equipment_models (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id     INTEGER NOT NULL REFERENCES categories(id),
    name            TEXT NOT NULL,                 -- "Workstation", "Monitor", "Smart Board"
    brand           TEXT,                          -- "Lenovo", "Dell"
    model_number    TEXT,                          -- "TS P350_W580_ES_TW_R"
    specifications  TEXT,                          -- merged specs from continuation rows
    unit            TEXT DEFAULT 'EA',             -- EA, LOT, Item
    expected_qty    INTEGER,                       -- qty from the equipment list (for tracking)
    is_bookable     INTEGER DEFAULT 0,             -- can individual units be reserved?
    image_path      TEXT,                          -- shared photo: local file under static/, or external http(s) URL
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_eqmodels_category ON equipment_models(category_id);
CREATE INDEX IF NOT EXISTS idx_eqmodels_brand    ON equipment_models(brand);

-- ── Individual asset units ──────────────────────────────────────────────────
-- Each physical device/unit gets a row here.  For bulk items that the team
-- decides to track as a single line (e.g. "111 speakers → 1 summary row"),
-- qty_represented lets one asset row stand for many physical units.

CREATE TABLE IF NOT EXISTS assets (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_tag           TEXT NOT NULL UNIQUE,      -- "SAIL-16038"
    equipment_model_id  INTEGER NOT NULL REFERENCES equipment_models(id),
    serial_number       TEXT,
    location_id         INTEGER REFERENCES locations(id),
    condition           TEXT DEFAULT 'good'
                        CHECK(condition IN ('good','fair','damaged','decommissioned')),
    status              TEXT DEFAULT 'available'
                        CHECK(status IN ('available','in_use','reserved','checked_out',
                                         'maintenance','decommissioned','missing')),
    assigned_to         INTEGER REFERENCES employees(id),
    qty_represented     INTEGER DEFAULT 1,
    purchase_date       TEXT,
    warranty_expiry     TEXT,
    image_path          TEXT,
    holder_name         TEXT,                      -- free-text from V3 inventory
    remark              TEXT,                      -- raw "Found"/"Not Found/Missing"/"Found Not in App"
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_assets_tag       ON assets(asset_tag);
CREATE INDEX IF NOT EXISTS idx_assets_model     ON assets(equipment_model_id);
CREATE INDEX IF NOT EXISTS idx_assets_location  ON assets(location_id);
CREATE INDEX IF NOT EXISTS idx_assets_status    ON assets(status);
CREATE INDEX IF NOT EXISTS idx_assets_condition ON assets(condition);
CREATE INDEX IF NOT EXISTS idx_assets_assigned  ON assets(assigned_to);

-- ── Bookings (reservation system) ──────────────────────────────────────────
-- Same flow as room booking:  request → approve → check out → return.

CREATE TABLE IF NOT EXISTS bookings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id            INTEGER NOT NULL REFERENCES assets(id),
    requested_by        INTEGER NOT NULL REFERENCES employees(id),
    approved_by         INTEGER REFERENCES employees(id),
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending','approved','checked_out',
                                         'returned','cancelled','rejected')),
    booked_from         TEXT NOT NULL,             -- ISO date or datetime
    booked_to           TEXT NOT NULL,
    checkout_date       TEXT,
    actual_return       TEXT,
    return_condition    TEXT CHECK(return_condition IN ('good','fair','damaged')),
    pickup_location_id  INTEGER REFERENCES locations(id),
    return_location_id  INTEGER REFERENCES locations(id),
    purpose             TEXT,                      -- why they need it
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_bookings_asset    ON bookings(asset_id);
CREATE INDEX IF NOT EXISTS idx_bookings_user     ON bookings(requested_by);
CREATE INDEX IF NOT EXISTS idx_bookings_status   ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_dates    ON bookings(booked_from, booked_to);

-- ── Tickets (maintenance, requests, incidents) ─────────────────────────────

CREATE TABLE IF NOT EXISTS tickets (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number       TEXT NOT NULL UNIQUE,
    type                TEXT NOT NULL
                        CHECK(type IN ('maintenance','move','new_request',
                                       'incident','decommission','other')),
    priority            TEXT DEFAULT 'medium'
                        CHECK(priority IN ('low','medium','high','critical')),
    status              TEXT DEFAULT 'open'
                        CHECK(status IN ('open','in_progress','waiting','resolved','closed')),
    asset_id            INTEGER REFERENCES assets(id),
    submitted_by        INTEGER NOT NULL REFERENCES employees(id),
    assigned_to         INTEGER REFERENCES employees(id),
    title               TEXT NOT NULL,
    description         TEXT,
    resolution          TEXT,
    resolved_at         TEXT,
    closed_at           TEXT,
    affected_user_name  TEXT,
    affected_user_email TEXT,
    issue_category_id   INTEGER REFERENCES issue_categories(id),
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tickets_number   ON tickets(ticket_number);
CREATE INDEX IF NOT EXISTS idx_tickets_asset    ON tickets(asset_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status   ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_type     ON tickets(type);
CREATE INDEX IF NOT EXISTS idx_tickets_assignee ON tickets(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority, status);
CREATE INDEX IF NOT EXISTS idx_tickets_issue_cat ON tickets(issue_category_id);

CREATE TABLE IF NOT EXISTS ticket_comments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id   INTEGER NOT NULL REFERENCES tickets(id),
    author_id   INTEGER NOT NULL REFERENCES employees(id),
    body        TEXT NOT NULL,
    is_internal INTEGER DEFAULT 0,                 -- 1 = tech-only note
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tcomments_ticket ON ticket_comments(ticket_id);

-- ── Issue categories (team-managed dropdown for tickets) ───────────────────

CREATE TABLE IF NOT EXISTS issue_categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    is_active   INTEGER DEFAULT 1,
    created_by  INTEGER REFERENCES employees(id),
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_issue_categories_active ON issue_categories(is_active);

-- ── Audit log ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name  TEXT NOT NULL,
    record_id   INTEGER NOT NULL,
    action      TEXT NOT NULL
                CHECK(action IN ('create','update','delete','status_change')),
    field_name  TEXT,
    old_value   TEXT,
    new_value   TEXT,
    changed_by  INTEGER REFERENCES employees(id),
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_table_record ON audit_log(table_name, record_id);
CREATE INDEX IF NOT EXISTS idx_audit_date         ON audit_log(created_at);

-- ── Equipment agreements / licenses ────────────────────────────────────────

CREATE TABLE IF NOT EXISTS equipment_agreements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id        INTEGER NOT NULL REFERENCES equipment_models(id) ON DELETE CASCADE,
    agreement_type  TEXT    NOT NULL,           -- 'Warranty', 'Support Contract', 'Software License', 'Subscription'
    provider        TEXT,                       -- vendor name
    start_date      TEXT,                       -- ISO YYYY-MM-DD
    end_date        TEXT,                       -- ISO YYYY-MM-DD
    notes           TEXT,
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_agreements_model    ON equipment_agreements(model_id);
CREATE INDEX IF NOT EXISTS idx_agreements_end_date ON equipment_agreements(end_date);
CREATE INDEX IF NOT EXISTS idx_agreements_type     ON equipment_agreements(agreement_type);

