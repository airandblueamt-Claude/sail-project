# Asset-Data Bootstrap — Design Spec

**Date:** 2026-04-27
**Status:** Specced (awaiting plan)
**Source data:** `Assets Inventory _20-04-2026-Tool (V3).xlsx`, sheet `IT Assets` — 230 individual asset rows.

## 1 — Purpose

Replace the existing seed data in the SAIL database with the V3 inventory spreadsheet, so the live system runs on the real, audited asset list. The spreadsheet is the single source of truth going forward; older equipment-list artifacts (`equipment_clean.csv`, the per-product-line `SAIL Equipment List` Excel) are retired.

This is not a throwaway prototype. The SAIL app, including the booking flow and ticket flow, will be built and operated against this data.

## 2 — Non-goals

- Real-time sync from the spreadsheet. The import is a one-shot rebuild; re-running it wipes and reloads.
- Linking holder names to existing employee rows. Holder is stored as free text; matching to `employees` can come later if it earns its keep.
- Downloading external image URLs into local storage. URLs render in the browser as-is; if a host blocks hotlinking we revisit.
- A new `projects` or `teams` table. Most non-employee holders are 1-off labels (`Personal`, `-`, badge-only individuals); a separate table is unjustified at this size.
- Migrating live bookings, tickets, comments, or audit history. The current DB contains no such records (verified 2026-04-27: `bookings=0`, `tickets=0`, `ticket_comments=0`, `audit_log=0`); they're considered empty.

## 3 — Architecture

### 3.1 Pipeline

```
Assets Inventory _20-04-2026-Tool (V3).xlsx
  └─ IT Assets sheet (230 rows)
      └─ import_assets_v3.py
          ├─ backup sail.db → backups/
          ├─ wipe: assets, equipment_models, categories, locations
          ├─ derive categories  (11 rows after case normalization)
          ├─ derive locations   (~39 rows from "Official location"; messy, expected to be cleaned up post-import)
          ├─ derive equipment_models  (group by category + item name → 31 rows)
          └─ insert assets (one per Excel row)
```

### 3.2 Run order (replaces current init flow)

```
python init_db.py            # schema only; no CSV import branch
python import_assets_v3.py   # loads the V3 Excel
python app.py                # serves on :5555
```

### 3.3 Tables that change vs. tables that don't

| Table | Action |
|---|---|
| `assets` | wiped + reloaded (230 rows) — schema gains `holder_name`, `remark`; `status` CHECK widened |
| `equipment_models` | wiped + reloaded (31 rows derived) |
| `categories` | wiped + reloaded (11 rows derived); seed INSERTs removed from `schema.sql` |
| `locations` | wiped + reloaded (~39 rows derived; data is dirty — duplicates and typos expected, to be cleaned up post-import) |
| `employees` | untouched (login accounts preserved) |
| `bookings`, `tickets`, `ticket_comments`, `equipment_agreements`, `audit_log` | untouched (currently empty) |

## 4 — Schema changes

Edit `schema.sql` in place (DB is being rebuilt anyway):

1. Add two columns to `assets`:
   ```
   holder_name TEXT,
   remark      TEXT,
   ```
2. Widen `assets.status` CHECK constraint to include `missing`:
   ```
   status TEXT DEFAULT 'available'
       CHECK(status IN ('available','in_use','reserved','checked_out',
                        'maintenance','decommissioned','missing'))
   ```
3. Remove the hard-coded `INSERT OR IGNORE INTO categories ...` block at the bottom of `schema.sql`. Categories are now derived from the import.

No other schema changes.

## 5 — Field mapping (Excel → DB)

| Excel column | DB destination | Notes |
|---|---|---|
| `Product_ID(SAIL ID)` | `assets.asset_tag` | `SAIL-{id}` (e.g. `16038` → `SAIL-16038`) |
| `Sequence` | fallback for missing IDs | 3 rows have no Product_ID → `SAIL-NEW-{sequence}` |
| `Category` | `categories.name` → `equipment_models.category_id` | Normalize: `MONITOR` → `Monitor`, `Smart board` → `Smart Board` |
| `Item Name` | `equipment_models.name` | Group key with category; 31 distinct (cat, item) pairs |
| `Description` | `equipment_models.specifications` | NULL when equal to `Item Name` |
| `Image` | `equipment_models.image_path` | External URL, stored as-is; first non-null per group |
| `Serial Number` | `assets.serial_number` | |
| `Holder Name` | `assets.holder_name` | Free text, raw |
| `Official location` | `locations.label` → `assets.location_id` | Slugify uppercase to `locations.code` (e.g. `AR/VR` → `AR-VR`); `is_storage=1` only when label = `STORAGE`. Blank or `N/A` becomes a single `UNKNOWN` location with `is_storage=0` |
| `Desk/Site Area` | `assets.notes` | Only when meaningfully different from `Official location` |
| `Availability` | `assets.condition` | `yes`/`1` → `good`; `damage` → `damaged`; `no` → `fair`; blank → `good` |
| `Remark` | `assets.remark` + drives `assets.status` | See §6 |
| `Date From`, `Date To`, `phone`, `Email` | `assets.notes` | Sparse (~3 rows); folded into notes as `key: value` lines |

### 5.1 `is_bookable` defaults

Set on `equipment_models` at import time. **Bookable = 1** for all categories *except* fixed installations:

- `Access Control`
- `Smart Podium`
- `Eye Tracking System`

Admins can override via the existing model-edit UI.

## 6 — Status & holder model

Holder is stored as free text on the asset; `assets.status` is **derived** at import time from `(holder_name, remark)`:

| Condition | Status |
|---|---|
| `Remark = "Not Found/Missing"` | `missing` |
| `Holder ∈ {"SAIL", "SAIL Storage", "-", blank}` AND `Remark = "Found"` | `available` |
| `Holder = "NOT SAIL"` | `decommissioned` |
| Anything else (project / person) AND `Remark = "Found"` | `in_use` |
| `Remark = "Found Not in App"` | derived from holder using rules above; remark preserved verbatim for review |

`assets.remark` always stores the raw Excel value (`Found` / `Not Found/Missing` / `Found Not in App`) so audit reviewers can see the original classification regardless of derived status.

The booking lifecycle is unchanged: only `status='available'` assets are bookable. Of the 230 rows: **127 become book-ready** (75 storage-pool holders + 51 blank-holder Found + 1 `-`); **87 are visible-but-locked** as `in_use` under a project/person; **15 are flagged** as `missing` for follow-up; **1 is decommissioned** (`NOT SAIL`).

## 7 — Importer (`import_assets_v3.py`)

Single transactional script using `database.get_db()`. Runs sequentially — no parallelism, no chunking (230 rows is trivial).

```
1. Call backup_db.py first → backups/sail_<timestamp>.db
2. Open Excel; read sheet "IT Assets"; skip rows where Sequence and Category are both empty.
3. with get_db() as conn:
   a. DELETE in FK-safe order: assets, equipment_models, locations, categories.
   b. Build category set from Category column → INSERT, capture {name: id} map.
   c. Build location set from Official location → INSERT, capture {label: id} map.
   d. Build model set from (category, item_name) → INSERT, capture {(cat,item): id} map;
      pick the first non-null Image URL and Description encountered for each group.
   e. For each Excel row: derive asset_tag, status, condition; INSERT into assets.
   f. Print per-section counts as the script runs.
4. Print final SUMMARY block (see §9).
5. Exit non-zero if asset count != 230 or status counts don't sum to 230 (transaction rolls back via the context manager).
```

Flags:

- `--dry-run` — performs all derivation and prints the SUMMARY without writing.
- `--xlsx PATH` — override the source file (default: the V3 file at repo root).

No audit-log entries are written for the bulk import (the DB is freshly seeded; an audit row per insert is just noise). Audit logging resumes for normal app operations after import.

## 8 — UI tweak (image URLs)

The Excel image cells are external HTTP URLs (`bhphotovideo.com`, `appsheet.com`, `bing.com`, etc.). The current templates pass `image_path` through `url_for('static', filename=...)` which would break for absolute URLs.

Three template files need a Jinja conditional around the `<img>` tag:

- `templates/inventory/models.html`
- `templates/inventory/detail.html`
- `templates/inventory/edit.html`

Pattern:
```jinja
{% if m.image_path and m.image_path.startswith('http') %}
    <img src="{{ m.image_path }}" alt="{{ m.name }}">
{% elif m.image_path %}
    <img src="{{ url_for('static', filename=m.image_path) }}" alt="{{ m.name }}">
{% endif %}
```

If a host blocks hotlinking and an image fails to render, we'll address it case-by-case (download + rehost, or remove the URL) — out of scope for this spec.

## 9 — Verification (printed by the importer)

```
SUMMARY
  Categories:        11
  Locations:         ~39
  Equipment models:  31
  Assets:            230
    available:       127    (75 storage-pool + 51 blank Found + 1 "-")
    in_use:          87     (project/team/person holders)
    missing:         15     (Remark = "Not Found/Missing")
    decommissioned:  1      (NOT SAIL)
  Bookable models:   ~27 of 31
DATA QUALITY
  Rows w/o Product_ID:        3    (assigned SAIL-NEW-{sequence})
  Rows w/ holder badge#:      ~17  (kept as free text)
  Rows w/ "Found Not in App": 3    (status from holder, remark preserved)
```

Hard invariant: `assets COUNT = 230` AND status counts sum to 230. If not, the transaction is rolled back and the script exits non-zero.

### 9.1 Smoke test (manual, ~5 min)

After import, with `python app.py` running:

1. `/inventory` — bookable model cards render; external image URLs load.
2. Click any model → asset list shows individual SAIL-IDs with holder name and status badge.
3. Admin asset list (or `/inventory?status=missing`) — 15 rows visible, all flagged.
4. Try to book an `in_use` asset — booking action is unavailable (only `available` is bookable).
5. `/reports` — counts match the SUMMARY block above.

## 10 — Cleanup (deletes)

Per "replace, don't add":

- `clean_equipment.py` — **delete**
- `equipment_clean.csv` — **delete**
- `init_db.py` — **simplify**: keep schema bootstrap, remove the CSV-import branch
- `SAIL Equipment List (AMT_SCOPE).xlsx`, `SAIL_Equipment_Clean.xlsx`, `SAIL_Equipment_Clean_v2.xlsx` — leave on disk (already gitignored or untracked); they are no longer referenced

## 11 — Rollback

The importer takes a backup before any destructive operation:

```
cp backups/sail_<timestamp>.db sail.db
```

Schema-file edits and template tweaks are git-tracked and reversible with `git checkout`.

## 12 — Risks & open questions

| Risk | Mitigation |
|---|---|
| External image hosts block hotlinking | Out of scope; address case-by-case after import |
| Holder badge-numbers are stored as free text and may diverge from the future `employees` table | Acceptable for now; spec a follow-up to backfill `assigned_to` once employees are loaded |
| Excel column order/name drift on a future V4 sheet | Importer reads by header name (not column index); a missing header fails fast with a clear error |
| The 3 `Found Not in App` rows have no Product_ID — the synthetic `SAIL-NEW-{seq}` tags may collide with real future tags | Synthetic tags use a `NEW-` prefix that is reserved for unmatched rows; admins rename them once a real ID is assigned |

No open questions block implementation.
