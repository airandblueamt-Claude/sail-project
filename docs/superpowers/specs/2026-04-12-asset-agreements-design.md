# Asset Agreements & License Tracking — Design Spec

## Summary

Add flexible support agreement and license tracking to AssetInventory. A new `asset_agreements` table allows admins to attach any number of agreement entries (warranties, support contracts, software licenses, subscriptions) to any asset. Assets without agreements simply have zero rows — no forced fields.

## Database

### New table: `asset_agreements`

```sql
CREATE TABLE IF NOT EXISTS asset_agreements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id        INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    agreement_type  TEXT    NOT NULL,  -- 'Warranty', 'Support Contract', 'Software License', 'Subscription'
    provider        TEXT,              -- Vendor name (e.g., 'Dell', 'Microsoft')
    start_date      TEXT,              -- ISO YYYY-MM-DD, nullable
    end_date        TEXT,              -- ISO YYYY-MM-DD, nullable
    notes           TEXT,              -- Free text: contract numbers, license keys, etc.
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX idx_agreements_asset ON asset_agreements(asset_id);
CREATE INDEX idx_agreements_end_date ON asset_agreements(end_date);
CREATE INDEX idx_agreements_type ON asset_agreements(agreement_type);
```

### Computed status (not stored)

Status is derived from `end_date` relative to today:

| Condition | Status |
|-----------|--------|
| end_date is NULL | Active (no expiry) |
| end_date > today + 30 days | Active |
| end_date between today and today + 30 days | Expiring Soon |
| end_date < today | Expired |

This follows the existing pattern where asset availability is computed, not stored.

### Migration strategy

Add the `CREATE TABLE` and `CREATE INDEX` statements to `database.py`'s `init_db()` function, using `IF NOT EXISTS` so it's safe to run on existing databases.

## Agreement Types

Predefined options presented in a dropdown:

- Warranty
- Support Contract
- Software License
- Subscription

These are UI suggestions, not database constraints — the `agreement_type` column is free text to allow future types without schema changes.

## UI Changes

### 1. Asset Detail Page — Agreements Card

A new card section below the existing asset info on `templates/assets/detail.html`:

- **Title**: "Agreements & Licenses" with a count badge
- **Table columns**: Type, Provider, Start Date, End Date, Status (badge), Notes (truncated)
- **Status badges**: Green = Active, Yellow = Expiring Soon, Red = Expired
- **Admin actions**: "Add Agreement" button opens a modal/form. Each row has Edit and Delete buttons (admin only).
- **Empty state**: "No agreements recorded for this asset."

### 2. Admin Agreements Overview — `/admin/agreements`

A new page accessible from the admin panel sidebar:

- **Table columns**: Asset (product_id + name, linked to detail), Type, Provider, Start Date, End Date, Status, Notes
- **Filters**: Agreement type dropdown, Status dropdown (Active / Expiring Soon / Expired / All)
- **Sort**: By end_date ascending by default (most urgent first)
- **Pagination**: Using existing PAGE_SIZE from config

### 3. Dashboard Widget

A small summary card on the dashboard showing:

- Count of agreements expiring within 30 days
- Count of already-expired agreements
- Link to the admin agreements overview

Only visible to admin users.

## Routes

### New blueprint or extend existing routes

Since agreements are tightly coupled to assets, extend `routes/assets.py` for per-asset operations and `routes/admin.py` for the overview.

### Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/assets/<id>` | user | Existing detail route — now also fetches agreements |
| POST | `/assets/<id>/agreements/add` | admin | Add new agreement |
| POST | `/assets/<id>/agreements/<aid>/edit` | admin | Update agreement |
| POST | `/assets/<id>/agreements/<aid>/delete` | admin | Delete agreement |
| GET | `/admin/agreements` | admin | Overview of all agreements |

### Audit logging

All add/edit/delete operations on agreements are logged to `audit_log` using the existing `log_audit()` function, with:

- `entity_type`: 'agreement'
- `entity_id`: agreement ID
- `action`: 'create', 'update', 'delete'
- `details`: JSON with changed fields and the parent asset_id

## Form Fields

The add/edit agreement form (modal or inline):

| Field | Input Type | Required | Notes |
|-------|-----------|----------|-------|
| Agreement Type | Select dropdown | Yes | Predefined options + free text option |
| Provider | Text input | No | Vendor name |
| Start Date | date input | No | HTML5 date picker |
| End Date | date input | No | HTML5 date picker |
| Notes | Textarea | No | Contract numbers, license keys, etc. |

Validation:
- Agreement type is required
- If both start and end dates are provided, end must be >= start
- All other fields optional

## Design Decisions

1. **Separate table, not columns on assets**: Flexible — assets can have 0 to many agreements. No wasted nullable columns.
2. **Computed status, not stored**: Follows existing pattern (asset availability). Always accurate, no stale data.
3. **Free text agreement_type**: Dropdown suggests common types but doesn't constrain. Future-proof without migrations.
4. **ON DELETE CASCADE**: If an asset is deleted, its agreements are cleaned up automatically.
5. **No separate agreements blueprint**: Keeps related code together — per-asset ops in assets.py, admin overview in admin.py.

## Files to Create or Modify

| File | Action | What |
|------|--------|------|
| `database.py` | Modify | Add asset_agreements table creation to init_db() |
| `routes/assets.py` | Modify | Add agreement CRUD routes, fetch agreements in detail view |
| `routes/admin.py` | Modify | Add /admin/agreements overview route |
| `templates/assets/detail.html` | Modify | Add agreements card section |
| `templates/assets/agreement_form.html` | Create | Modal/form partial for add/edit |
| `templates/admin/agreements.html` | Create | Admin overview page |
| `templates/dashboard.html` | Modify | Add expiring agreements widget (admin only) |
