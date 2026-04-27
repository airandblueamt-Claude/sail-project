# Asset-Data Bootstrap — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the SAIL database's seed data (old equipment list) with the V3 inventory spreadsheet's 230 individual assets, becoming the production source of truth.

**Architecture:** A one-shot `import_assets_v3.py` script reads the Excel, derives `categories` / `locations` / `equipment_models` from the row data, and inserts the 230 assets in a single transaction with built-in invariant checks. `schema.sql` gains `holder_name` + `remark` columns and a `missing` status; `init_db.py` is reduced to schema-only; the old CSV pipeline is deleted. Three Jinja templates get a small conditional to render external image URLs alongside locally-uploaded ones.

**Tech Stack:** Python 3, Flask, SQLite, openpyxl. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-27-asset-data-bootstrap-design.md`

---

## File Structure

**Create:**
- `import_assets_v3.py` — the importer (single file, ~250 lines)

**Modify:**
- `schema.sql` — add `holder_name`/`remark` to `assets`, widen `status` CHECK, remove category seed INSERTs
- `init_db.py` — drop the CSV-import branch; keep only schema bootstrap
- `templates/inventory/models.html` — image URL conditional
- `templates/inventory/detail.html` — image URL conditional
- `templates/inventory/edit.html` — image URL conditional

**Delete:**
- `clean_equipment.py`
- `equipment_clean.csv`

**Verification approach:** This project has no test framework (per CLAUDE.md). Verification is built into the importer itself (dry-run + invariants on row counts), plus a manual smoke test at the end. Each task ends with a concrete check before commit.

---

## Task 1: Update schema.sql for new fields and `missing` status

**Files:**
- Modify: `schema.sql:63-78` (equipment_models table — add missing `image_path` column), `schema.sql:84-103` (assets table), and `schema.sql:217-231` (category seeds)

- [ ] **Step 1a: Add `image_path` to `equipment_models`**

The `routes/inventory.py` model-create form already INSERTs into a column called `image_path` and the templates render `m.image_path`, but the column was never declared in `schema.sql` (this was a latent bug — the INSERT was failing silently when admins tried to upload model photos). Fix it here. Replace the `equipment_models` definition (lines 63–78):

```sql
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
```

(The diff vs. current: `image_path TEXT,` line added before `notes`.)

- [ ] **Step 1b: Add `holder_name` and `remark` columns and widen `status` CHECK on `assets`**

In `schema.sql`, replace the `assets` table definition (lines 84–103) so it reads:

```sql
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
```

(The two diffs vs. the current schema: `'missing'` added to the CHECK list, and two new TEXT columns inserted before `notes`.)

- [ ] **Step 1c: Remove the category seed INSERTs at the bottom of `schema.sql`**

Delete the entire seed block at the bottom (lines 213–231 in the current file):

```sql
-- ============================================================================
-- Seed categories from the cleaned equipment list
-- ============================================================================

INSERT OR IGNORE INTO categories (name) VALUES
    ('Computers & Peripherals'),
    ...
    ('Access Control');
```

The new importer derives categories from the V3 spreadsheet.

- [ ] **Step 2: Verify the schema applies cleanly**

Run:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect(':memory:')
conn.execute('PRAGMA foreign_keys = ON')
with open('schema.sql', encoding='utf-8') as f:
    conn.executescript(f.read())
# New columns on assets:
acols = [r[1] for r in conn.execute('PRAGMA table_info(assets)')]
print('assets columns:', acols)
assert 'holder_name' in acols, 'holder_name missing'
assert 'remark' in acols, 'remark missing'
# image_path on equipment_models:
mcols = [r[1] for r in conn.execute('PRAGMA table_info(equipment_models)')]
print('equipment_models columns:', mcols)
assert 'image_path' in mcols, 'image_path missing on equipment_models'
# 'missing' status is allowed:
conn.execute(\"INSERT INTO categories(name) VALUES ('X')\")
conn.execute(\"INSERT INTO equipment_models(category_id, name) VALUES (1, 'M')\")
conn.execute(\"INSERT INTO assets(asset_tag, equipment_model_id, status) VALUES ('SAIL-T', 1, 'missing')\")
print('missing status accepted: OK')
# Category seeds gone:
n = conn.execute('SELECT COUNT(*) FROM categories').fetchone()[0]
assert n == 1, f'expected 1 (just our test row), got {n}'
print('category seeds removed: OK')
"
```

Expected output:
```
assets columns: ['id', 'asset_tag', 'equipment_model_id', 'serial_number', 'location_id', 'condition', 'status', 'assigned_to', 'qty_represented', 'purchase_date', 'warranty_expiry', 'image_path', 'holder_name', 'remark', 'notes', 'created_at', 'updated_at']
equipment_models columns: ['id', 'category_id', 'name', 'brand', 'model_number', 'specifications', 'unit', 'expected_qty', 'is_bookable', 'image_path', 'notes', 'created_at']
missing status accepted: OK
category seeds removed: OK
```

- [ ] **Step 3: Commit**

```bash
git add schema.sql
git commit -m "$(cat <<'EOF'
Update schema for V3 inventory: holder_name, remark, missing, image_path

assets:           adds holder_name + remark columns; widens the
                  status CHECK to include 'missing'.
equipment_models: adds image_path column (was already INSERTed by
                  routes/inventory.py and rendered in templates,
                  but never declared in schema.sql -- pre-existing
                  silent failure when admins uploaded model photos).
categories:       seed INSERTs removed; categories are now derived
                  from the V3 spreadsheet.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Simplify `init_db.py` to schema-only

**Files:**
- Modify: `init_db.py` (full rewrite — much shorter)

- [ ] **Step 1: Replace the entire file**

Replace the contents of `init_db.py` with:

```python
"""
Initialize the SAIL database from schema.sql.

Usage:  python init_db.py
Output: sail.db (SQLite, empty schema)

After running this, run import_assets_v3.py to load the inventory data.
"""
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "sail.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

    print(f"Schema applied. Database ready at {DB_PATH}")
    print("Next: python import_assets_v3.py")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify `init_db.py` still bootstraps a usable DB**

Run:
```bash
python3 init_db.py
python3 -c "
import sqlite3
conn = sqlite3.connect('sail.db')
tables = sorted(r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\"))
print('tables:', tables)
n_cats = conn.execute('SELECT COUNT(*) FROM categories').fetchone()[0]
n_assets = conn.execute('SELECT COUNT(*) FROM assets').fetchone()[0]
print(f'categories: {n_cats}, assets: {n_assets}')
assert n_cats == 0, 'expected empty categories'
assert n_assets == 0, 'expected empty assets'
print('OK')
"
```

Expected output:
```
Removed existing /home/malkhalifa/sail-project/sail.db
Schema applied. Database ready at /home/malkhalifa/sail-project/sail.db
Next: python import_assets_v3.py
tables: ['assets', 'audit_log', 'bookings', 'categories', 'departments', 'employees', 'equipment_agreements', 'equipment_models', 'locations', 'ticket_comments', 'tickets']
categories: 0, assets: 0
OK
```

- [ ] **Step 3: Commit**

```bash
git add init_db.py
git commit -m "$(cat <<'EOF'
Reduce init_db.py to schema-only bootstrap

The CSV-import branch is dead now that asset data comes from the
V3 spreadsheet via import_assets_v3.py. init_db.py just applies
the schema and exits.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Create `import_assets_v3.py` — readers and pure transformations (dry-run only)

**Files:**
- Create: `import_assets_v3.py`

This task creates the importer with all the pure (no-DB) logic and a working `--dry-run` mode. The next task adds the DB-write path.

- [ ] **Step 1: Create the file with argparse, Excel reader, and pure transformation functions**

Create `import_assets_v3.py` with this content:

```python
"""
Import the V3 asset inventory into SAIL.

Usage:
    python import_assets_v3.py              # full import (wipes + reloads)
    python import_assets_v3.py --dry-run    # parse + summarize, no DB writes
    python import_assets_v3.py --xlsx PATH  # override source Excel path

The Excel sheet "IT Assets" is the source of truth. Categories,
locations, and equipment_models are derived from the row data.
See docs/superpowers/specs/2026-04-27-asset-data-bootstrap-design.md.
"""
import argparse
import os
import re
import sys
from collections import Counter

import openpyxl

from database import get_db
from backup_db import backup as backup_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_XLSX = os.path.join(
    BASE_DIR, "Assets Inventory _20-04-2026-Tool (V3).xlsx"
)
SHEET_NAME = "IT Assets"

# Category names that should NOT default to bookable=1 (fixed installations).
NON_BOOKABLE_CATEGORIES = {"Access Control", "Smart Podium", "Eye Tracking System"}

# Holder values that mean "in the SAIL inventory pool" (status = available).
STORAGE_POOL_HOLDERS = {"SAIL", "SAIL Storage", "-"}

# Header → row-index map (filled by read_rows).
EXPECTED_HEADERS = {
    "sequence": "Sequence",
    "product_id": "Product_ID(SAIL ID)",
    "category": "Category",
    "item_name": "Item Name",
    "description": "Description",
    "availability": "Availability",
    "holder_name": "Holder Name",
    "serial_number": "Serial Number",
    "desk_area": "Desk/Site Area",
    "official_location": "Official location",
    "remark": "Remark",
    "date_from": "Date From",
    "date_to": "Date To",
    "image": "Image",
    "phone": "phone",
    "email": "Email",
}


# ── Pure transformation helpers ─────────────────────────────────────────────


def s(v):
    """Coerce a cell to a stripped string, or None for empty/whitespace."""
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return str(v).strip() or None


def normalize_category(raw):
    """Fold "MONITOR", "Smart board", etc. to a canonical title-case form."""
    if not raw:
        return None
    return raw.strip().title()


def normalize_item_name(raw):
    """Item name used as a model-grouping key. Just trims; preserves brand casing."""
    return raw.strip() if raw else None


def derive_asset_tag(product_id, sequence):
    """SAIL-{id} when present; SAIL-NEW-{seq} fallback for the 3 missing-ID rows."""
    if product_id:
        return f"SAIL-{product_id}"
    if sequence:
        return f"SAIL-NEW-{sequence}"
    raise ValueError("row has neither Product_ID nor Sequence")


def derive_condition(availability):
    """Excel Availability → assets.condition."""
    if not availability:
        return "good"
    a = str(availability).strip().lower()
    if a in ("yes", "1"):
        return "good"
    if a == "damage":
        return "damaged"
    if a == "no":
        return "fair"
    return "good"  # unknown → assume good; let admins fix


def derive_status(holder, remark):
    """
    Derived per the §6 rules in the spec:
      - Remark = Not Found/Missing  -> missing
      - Holder = NOT SAIL           -> decommissioned
      - Holder in storage-pool      -> available
      - Otherwise                   -> in_use
    The 'Found Not in App' remark falls through to the holder rules.
    """
    if remark and remark.strip().lower() == "not found/missing":
        return "missing"
    h = (holder or "").strip()
    if h.upper() == "NOT SAIL":
        return "decommissioned"
    if not h or h in STORAGE_POOL_HOLDERS:
        return "available"
    return "in_use"


def location_code(label):
    """Slug for locations.code: uppercase, slashes/spaces -> '-', collapse runs."""
    if not label:
        return "UNKNOWN"
    code = label.strip().upper()
    code = re.sub(r"[\s/]+", "-", code)
    code = re.sub(r"-+", "-", code).strip("-")
    return code or "UNKNOWN"


def location_for(raw_label):
    """
    Map an "Official location" cell to (code, label, is_storage).
    Blank or 'N/A' collapse to the single UNKNOWN location.
    """
    if not raw_label or raw_label.strip().upper() in ("N/A", ""):
        return ("UNKNOWN", "Unknown / N-A", 0)
    label = raw_label.strip()
    code = location_code(label)
    is_storage = 1 if label.upper() == "STORAGE" else 0
    return (code, label, is_storage)


def is_bookable_for(category):
    """Default bookability flag for a derived equipment_model."""
    return 0 if category in NON_BOOKABLE_CATEGORIES else 1


def build_notes(row):
    """Fold sparse Excel fields into a single notes string for an asset."""
    parts = []
    desk = s(row.get("desk_area"))
    off = s(row.get("official_location"))
    if desk and (not off or desk.lower() != off.lower()):
        parts.append(f"desk: {desk}")
    for key in ("date_from", "date_to", "phone", "email"):
        val = s(row.get(key))
        if val:
            parts.append(f"{key}: {val}")
    return " | ".join(parts) if parts else None


# ── Excel reader ────────────────────────────────────────────────────────────


def read_rows(xlsx_path):
    """Yield dicts keyed by EXPECTED_HEADERS, one per data row."""
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    if SHEET_NAME not in wb.sheetnames:
        raise SystemExit(f"sheet {SHEET_NAME!r} not found in {xlsx_path}")
    ws = wb[SHEET_NAME]
    header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
    idx = {}
    for key, label in EXPECTED_HEADERS.items():
        try:
            idx[key] = header_row.index(label)
        except ValueError:
            raise SystemExit(
                f"missing expected header {label!r} in {xlsx_path} (row 1)"
            )
    for raw in ws.iter_rows(min_row=2, values_only=True):
        # Skip totally empty rows (no Sequence AND no Category).
        if raw[idx["sequence"]] is None and raw[idx["category"]] is None:
            continue
        yield {key: raw[i] for key, i in idx.items()}


# ── Derivation pass (no DB) ─────────────────────────────────────────────────


def derive_all(rows):
    """
    Walk the rows and build the in-memory plan:
      categories: set of names
      locations:  dict {code: (label, is_storage)}
      models:     dict {(category, item_name_lower): {category, name, image, specs}}
      assets:     list of asset-row dicts ready for INSERT
    """
    categories = set()
    locations = {}
    models = {}
    assets = []

    status_counter = Counter()
    no_pid = 0
    badge_holders = 0
    found_not_in_app = 0

    for row in rows:
        cat = normalize_category(s(row["category"]))
        item = normalize_item_name(s(row["item_name"]))
        if not cat:
            continue  # safety; read_rows already filters totally empty rows

        categories.add(cat)

        loc_code, loc_label, loc_is_storage = location_for(s(row["official_location"]))
        if loc_code not in locations:
            locations[loc_code] = (loc_label, loc_is_storage)

        item_key = (cat, (item or "").lower())
        if item_key not in models:
            models[item_key] = {
                "category": cat,
                "name": item or cat,
                "description": None,
                "image": None,
            }
        m = models[item_key]
        if m["description"] is None:
            desc = s(row["description"])
            if desc and desc.lower() != (item or "").lower():
                m["description"] = desc
        if m["image"] is None:
            img = s(row["image"])
            if img and img.lower().startswith("http"):
                m["image"] = img

        product_id = s(row["product_id"])
        sequence = s(row["sequence"])
        if not product_id:
            no_pid += 1
        asset_tag = derive_asset_tag(product_id, sequence)

        holder = s(row["holder_name"])
        remark = s(row["remark"])
        status = derive_status(holder, remark)
        condition = derive_condition(s(row["availability"]))

        if remark and remark.lower() == "found not in app":
            found_not_in_app += 1
        if holder and re.search(r"\d{5,}", holder):
            badge_holders += 1

        status_counter[status] += 1

        assets.append({
            "asset_tag": asset_tag,
            "model_key": item_key,
            "loc_code": loc_code,
            "category": cat,
            "serial_number": s(row["serial_number"]),
            "condition": condition,
            "status": status,
            "holder_name": holder,
            "remark": remark,
            "image_path": m["image"],   # mirrored on the model; not used per-asset
            "notes": build_notes(row),
        })

    return {
        "categories": categories,
        "locations": locations,
        "models": models,
        "assets": assets,
        "status_counter": status_counter,
        "no_pid": no_pid,
        "badge_holders": badge_holders,
        "found_not_in_app": found_not_in_app,
    }


# ── Output ──────────────────────────────────────────────────────────────────


def print_summary(plan):
    cats = plan["categories"]
    locs = plan["locations"]
    models = plan["models"]
    assets = plan["assets"]
    sc = plan["status_counter"]
    bookable = sum(
        1 for (cat, _) in models.keys() if is_bookable_for(cat)
    )

    print("SUMMARY")
    print(f"  Categories:        {len(cats)}")
    print(f"  Locations:         {len(locs)}")
    print(f"  Equipment models:  {len(models)}")
    print(f"  Assets:            {len(assets)}")
    for st in ("available", "in_use", "missing", "decommissioned",
               "reserved", "checked_out", "maintenance"):
        if sc.get(st):
            print(f"    {st + ':':<16} {sc[st]}")
    print(f"  Bookable models:   {bookable} of {len(models)}")
    print("DATA QUALITY")
    print(f"  Rows w/o Product_ID:        {plan['no_pid']}   (assigned SAIL-NEW-{{sequence}})")
    print(f"  Rows w/ holder badge#:      {plan['badge_holders']}")
    print(f"  Rows w/ \"Found Not in App\": {plan['found_not_in_app']}")


# ── Entry point (DB write path stubbed for now) ─────────────────────────────


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="parse + summarize, no DB writes")
    parser.add_argument("--xlsx", default=DEFAULT_XLSX,
                        help=f"path to the V3 Excel (default: {DEFAULT_XLSX})")
    args = parser.parse_args()

    if not os.path.exists(args.xlsx):
        sys.exit(f"Excel not found: {args.xlsx}")

    rows = list(read_rows(args.xlsx))
    print(f"Read {len(rows)} rows from {args.xlsx}")

    plan = derive_all(rows)
    print_summary(plan)

    if args.dry_run:
        print("\n--dry-run: no DB writes performed")
        return

    # Task 4 wires up the actual DB write.
    sys.exit("DB write path not yet implemented — re-run with --dry-run for now")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the dry-run produces the expected counts**

Run:
```bash
python3 import_assets_v3.py --dry-run
```

Expected output (numbers must match exactly — these are computed from the spec's canonical counts):

```
Read 230 rows from /home/malkhalifa/sail-project/Assets Inventory _20-04-2026-Tool (V3).xlsx
SUMMARY
  Categories:        11
  Locations:         40
  Equipment models:  31
  Assets:            230
    available:       127
    in_use:          87
    missing:         15
    decommissioned:  1
  Bookable models:   28 of 31
DATA QUALITY
  Rows w/o Product_ID:        3   (assigned SAIL-NEW-{sequence})
  Rows w/ holder badge#:      11
  Rows w/ "Found Not in App": 3

--dry-run: no DB writes performed
```

Numbers must match exactly. If they don't, the derivation logic is wrong — fix before proceeding to Task 4.

- [ ] **Step 3: Commit**

```bash
git add import_assets_v3.py
git commit -m "$(cat <<'EOF'
Add V3 importer skeleton with dry-run derivation

Reads the V3 Excel, normalizes categories/locations, groups rows
into equipment_models, and derives per-asset status from
(holder, remark). --dry-run prints the SUMMARY without touching
the DB. The DB-write path follows in the next commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Add the DB write path to `import_assets_v3.py`

**Files:**
- Modify: `import_assets_v3.py` — add `write_to_db(plan)` and call it from `main()`

- [ ] **Step 1: Add the write function above `main()`**

Add this function to `import_assets_v3.py`, immediately after `print_summary()`:

```python
# ── DB writer ───────────────────────────────────────────────────────────────


def write_to_db(plan):
    """Wipe + reload assets, equipment_models, categories, locations.

    Single transaction via database.get_db(). On any error the
    context manager rolls back so the DB is unchanged.
    """
    with get_db() as conn:
        # 1. Wipe in FK-safe order. Bookings/tickets are empty (verified in spec).
        conn.execute("DELETE FROM assets")
        conn.execute("DELETE FROM equipment_models")
        conn.execute("DELETE FROM locations")
        conn.execute("DELETE FROM categories")
        # Reset autoincrement counters so IDs start clean.
        conn.execute(
            "DELETE FROM sqlite_sequence WHERE name IN "
            "('assets','equipment_models','locations','categories')"
        )

        # 2. Categories.
        cat_ids = {}
        for name in sorted(plan["categories"]):
            cur = conn.execute(
                "INSERT INTO categories (name) VALUES (?)", (name,)
            )
            cat_ids[name] = cur.lastrowid

        # 3. Locations.
        loc_ids = {}
        for code, (label, is_storage) in sorted(plan["locations"].items()):
            cur = conn.execute(
                "INSERT INTO locations (code, label, is_storage) VALUES (?, ?, ?)",
                (code, label, is_storage),
            )
            loc_ids[code] = cur.lastrowid

        # 4. Equipment models.
        model_ids = {}
        for key, m in plan["models"].items():
            cur = conn.execute(
                """INSERT INTO equipment_models
                       (category_id, name, specifications, image_path, is_bookable)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    cat_ids[m["category"]],
                    m["name"],
                    m["description"],
                    m["image"],
                    is_bookable_for(m["category"]),
                ),
            )
            model_ids[key] = cur.lastrowid

        # 5. Assets.
        for a in plan["assets"]:
            conn.execute(
                """INSERT INTO assets
                       (asset_tag, equipment_model_id, location_id,
                        serial_number, condition, status,
                        holder_name, remark, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    a["asset_tag"],
                    model_ids[a["model_key"]],
                    loc_ids[a["loc_code"]],
                    a["serial_number"],
                    a["condition"],
                    a["status"],
                    a["holder_name"],
                    a["remark"],
                    a["notes"],
                ),
            )

        # 6. Invariant check inside the transaction. A mismatch raises and
        #    the context manager rolls everything back.
        n_assets = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        if n_assets != len(plan["assets"]):
            raise RuntimeError(
                f"asset count mismatch: inserted {n_assets}, "
                f"plan had {len(plan['assets'])}"
            )
        status_total = sum(plan["status_counter"].values())
        if status_total != n_assets:
            raise RuntimeError(
                f"status counts ({status_total}) != asset count ({n_assets})"
            )
```

- [ ] **Step 2: Replace the `main()` exit-stub with the real call**

In `import_assets_v3.py`, find the last lines of `main()`:

```python
    # Task 4 wires up the actual DB write.
    sys.exit("DB write path not yet implemented — re-run with --dry-run for now")
```

Replace with:

```python
    print("\nBacking up DB before destructive write...")
    backup_db()

    print("Writing to DB...")
    write_to_db(plan)
    print("Done.")
```

- [ ] **Step 3: Run the importer for real on a clean DB**

```bash
python3 init_db.py
python3 import_assets_v3.py
```

Expected (the SUMMARY block prints first, then backup + write messages):
```
...
SUMMARY
  Categories:        11
  ...
  Assets:            230
    available:       127
    in_use:          87
    missing:         15
    decommissioned:  1
  ...

Backing up DB before destructive write...
Backup saved to /home/malkhalifa/sail-project/backups/sail_<timestamp>.db
Writing to DB...
Done.
```

- [ ] **Step 4: Verify the data landed correctly**

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('sail.db')
print('categories:', conn.execute('SELECT COUNT(*) FROM categories').fetchone()[0])
print('locations: ', conn.execute('SELECT COUNT(*) FROM locations').fetchone()[0])
print('models:    ', conn.execute('SELECT COUNT(*) FROM equipment_models').fetchone()[0])
print('assets:    ', conn.execute('SELECT COUNT(*) FROM assets').fetchone()[0])
print('--- status breakdown ---')
for r in conn.execute('SELECT status, COUNT(*) FROM assets GROUP BY status ORDER BY 2 DESC'):
    print(f'  {r[0]:<16} {r[1]}')
print('--- spot check: a held asset ---')
r = conn.execute(\"\"\"
    SELECT a.asset_tag, a.holder_name, a.status, a.remark, em.name, c.name
    FROM assets a
    JOIN equipment_models em ON em.id = a.equipment_model_id
    JOIN categories c ON c.id = em.category_id
    WHERE a.holder_name = 'WAF Project'
    LIMIT 3
\"\"\").fetchall()
for row in r:
    print(' ', tuple(row))
"
```

Expected:
```
categories: 11
locations:  40
models:     31
assets:     230
--- status breakdown ---
  available        127
  in_use           87
  missing          15
  decommissioned   1
--- spot check: a held asset ---
  ('SAIL-16038', 'WAF Project', 'in_use', 'Found Not in App', 'DELL ALIENWARE', 'Workstation')
  ('SAIL-NEW-236', 'WAF Project', 'in_use', 'Found Not in App', 'DELL ALIENWARE', 'Workstation')
  ...
```

If the counts don't match, the importer should have already raised — but if it didn't and the data is wrong, restore the latest backup and debug:
```bash
ls -lt backups/ | head -3        # find the most recent
cp backups/sail_<timestamp>.db sail.db
```

- [ ] **Step 5: Commit**

```bash
git add import_assets_v3.py
git commit -m "$(cat <<'EOF'
Wire up V3 importer DB writes with rollback-safe invariants

Backs up sail.db, wipes the asset-side tables, repopulates
categories/locations/models/assets in a single transaction.
Asset-count and status-count invariants raise inside the
transaction, so any mismatch rolls back cleanly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Update three templates to render external image URLs

**Files:**
- Modify: `templates/inventory/models.html` (around line 32)
- Modify: `templates/inventory/detail.html` (around line 19)
- Modify: `templates/inventory/edit.html` (around line 52)

- [ ] **Step 1: Update `templates/inventory/models.html`**

Find this block (around line 32):

```jinja
        {% if m.image_path %}
        <div class="eq-card-img">
            <img src="{{ url_for('static', filename=m.image_path) }}" alt="{{ m.name }}">
        </div>
        {% else %}
```

Replace with:

```jinja
        {% if m.image_path and m.image_path.startswith('http') %}
        <div class="eq-card-img">
            <img src="{{ m.image_path }}" alt="{{ m.name }}">
        </div>
        {% elif m.image_path %}
        <div class="eq-card-img">
            <img src="{{ url_for('static', filename=m.image_path) }}" alt="{{ m.name }}">
        </div>
        {% else %}
```

- [ ] **Step 2: Update `templates/inventory/detail.html`**

Find (around line 19):

```jinja
        {% if model.image_path %}
        <div class="model-image">
            <img src="{{ url_for('static', filename=model.image_path) }}" alt="{{ model.name }}">
        </div>
        {% endif %}
```

Replace with:

```jinja
        {% if model.image_path and model.image_path.startswith('http') %}
        <div class="model-image">
            <img src="{{ model.image_path }}" alt="{{ model.name }}">
        </div>
        {% elif model.image_path %}
        <div class="model-image">
            <img src="{{ url_for('static', filename=model.image_path) }}" alt="{{ model.name }}">
        </div>
        {% endif %}
```

- [ ] **Step 3: Update `templates/inventory/edit.html`**

Find (around line 52):

```jinja
        {% if model.image_path %}
        <div class="current-image">
            <img src="{{ url_for('static', filename=model.image_path) }}" alt="{{ model.name }}">
            <p class="muted">Current image — upload a new one to replace it.</p>
        </div>
        {% endif %}
```

Replace with:

```jinja
        {% if model.image_path and model.image_path.startswith('http') %}
        <div class="current-image">
            <img src="{{ model.image_path }}" alt="{{ model.name }}">
            <p class="muted">Current image (external URL — upload a new file to replace it).</p>
        </div>
        {% elif model.image_path %}
        <div class="current-image">
            <img src="{{ url_for('static', filename=model.image_path) }}" alt="{{ model.name }}">
            <p class="muted">Current image — upload a new one to replace it.</p>
        </div>
        {% endif %}
```

- [ ] **Step 4: Verify the templates parse (no syntax errors)**

```bash
python3 -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates'))
for t in ('inventory/models.html', 'inventory/detail.html', 'inventory/edit.html'):
    env.get_template(t)
    print(f'{t}: OK')
"
```

Expected:
```
inventory/models.html: OK
inventory/detail.html: OK
inventory/edit.html: OK
```

- [ ] **Step 5: Commit**

```bash
git add templates/inventory/models.html templates/inventory/detail.html templates/inventory/edit.html
git commit -m "$(cat <<'EOF'
Render external image URLs alongside locally-uploaded paths

V3 inventory ships external HTTP image URLs in equipment_models
.image_path. Templates now branch on the http(s) prefix and emit
the URL directly, falling back to url_for('static', ...) for
locally-uploaded files.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Delete retired pipeline artifacts

**Files:**
- Delete: `clean_equipment.py`
- Delete: `equipment_clean.csv`

- [ ] **Step 1: Confirm nothing else imports them**

```bash
grep -rn "clean_equipment\|equipment_clean" --include='*.py' --include='*.html' --include='*.md' . | grep -v "^./docs/" | grep -v "^./\.git/"
```

Expected: no matches outside of docs (the spec mentions these files in §10 Cleanup; that's fine).

- [ ] **Step 2: Delete the files**

```bash
git rm clean_equipment.py equipment_clean.csv
```

- [ ] **Step 3: Verify the app still imports cleanly**

```bash
python3 -c "import app; print('app imports OK')"
```

Expected: `app imports OK` (any ImportError here means a stale reference; investigate before committing).

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
Retire equipment_clean CSV pipeline

clean_equipment.py and equipment_clean.csv served the old
SAIL Equipment List spreadsheet. The V3 inventory replaces
that pipeline; init_db.py + import_assets_v3.py is the new
data-bootstrap flow.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: End-to-end smoke test

**Files:** none modified — this is a behavioural check against the running app.

- [ ] **Step 1: Run the full bootstrap fresh**

```bash
python3 init_db.py
python3 import_assets_v3.py
```

Expected: SUMMARY shows `Assets: 230`, status counts `127/87/15/1`, then `Done.`

- [ ] **Step 2: Recreate the admin login**

The DB was wiped, so the `employees` table is empty too (it was preserved in the spec's design — but `init_db.py` recreates the schema from scratch, which removes employees). Re-create your account:

```bash
# Start the app in the background
python3 app.py &
APP_PID=$!
sleep 2
```

Open `http://localhost:5555/register` and register your admin account. Then promote yourself to admin:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('sail.db')
conn.execute(\"UPDATE employees SET role='admin' WHERE email='airandblueamt@gmail.com'\")
conn.commit()
print('promoted')
"
```

- [ ] **Step 3: Walk through the smoke test (per spec §9.1)**

With the app running, open `http://localhost:5555` in a browser and check:

1. **`/inventory`** — bookable model cards render (around 27 cards). External images load (they may be slow / hot-link-blocked for some hosts; broken images are acceptable as long as the page renders).
2. **Click a model** (e.g. "DELL ALIENWARE") — the detail page lists its assets with SAIL-IDs, holder names, and status badges. Some show `WAF Project` or other holders.
3. **Filter for missing assets** — go to `/inventory?status=missing` if the route supports it, or use the admin asset list. 15 rows should show up flagged. (If the filter isn't wired in the UI, run a direct DB check instead — see Step 4.)
4. **Booking action availability** — pick an `in_use` asset and confirm the booking action is hidden / disabled. Pick an `available` asset and confirm it is bookable.
5. **`/reports`** — the rollups don't error out. Counts are consistent with the SUMMARY.

- [ ] **Step 4: Direct DB sanity check (optional, but quick)**

If any UI step is unclear, run:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('sail.db')
print('-- by status --')
for r in conn.execute('SELECT status, COUNT(*) FROM assets GROUP BY status ORDER BY 2 DESC'):
    print(f'  {r[0]:<16} {r[1]}')
print('-- top 5 holders (in_use) --')
for r in conn.execute(\"SELECT holder_name, COUNT(*) FROM assets WHERE status='in_use' GROUP BY holder_name ORDER BY 2 DESC LIMIT 5\"):
    print(f'  {r[1]:>4} {r[0]}')
print('-- bookable model count --')
print(conn.execute('SELECT COUNT(*) FROM equipment_models WHERE is_bookable=1').fetchone()[0])
"
```

Expected:
```
-- by status --
  available        127
  in_use           87
  missing          15
  decommissioned   1
-- top 5 holders (in_use) --
    14 OSD Project
    10 WAF Project
     8 PMCD
     8 OTCOD PoC
     7 TECHNOLOGY ADVOCACY GROUP
-- bookable model count --
  28
```

- [ ] **Step 5: Stop the dev server**

```bash
kill $APP_PID 2>/dev/null
```

- [ ] **Step 6: Final commit (notes-only — no code changes)**

If anything was tweaked in earlier tasks during the smoke test (templates, importer), it's already committed. Otherwise nothing to commit at this step.

---

## Self-review checklist

Spec coverage map (every §section in `2026-04-27-asset-data-bootstrap-design.md` should map to a task):

| Spec section | Task |
|---|---|
| §1 Purpose | n/a (motivation) |
| §2 Non-goals | n/a (boundary) |
| §3.1 Pipeline | Tasks 3, 4 |
| §3.2 Run order | Task 2 (init_db.py) + Task 7 (run order verified) |
| §3.3 Tables changed | Tasks 1, 4 |
| §4 Schema changes | Task 1 |
| §5 Field mapping | Tasks 3 (derivation) + 4 (insert) |
| §5.1 is_bookable defaults | Task 3 (`is_bookable_for`) |
| §6 Status & holder model | Task 3 (`derive_status`) + verified in Task 4 step 4 |
| §7 Importer | Tasks 3 (skeleton) + 4 (DB writes) |
| §8 UI tweak | Task 5 |
| §9 Verification SUMMARY | Task 3 step 2 + Task 4 step 4 |
| §9.1 Smoke test | Task 7 |
| §10 Cleanup deletes | Task 6 |
| §11 Rollback | Task 4 step 1 (backup_db before write) |
| §12 Risks (header-name validation) | Task 3 (`read_rows` raises on missing header) |

All sections covered.
