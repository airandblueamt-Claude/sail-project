# Asset Edit Page — Design Spec

## Summary

Add an asset edit page at `/inventory/asset/<id>/edit` so authorised staff can update individual assets in place — status, condition, location, serial number, quantity, and notes — without re-registering the asset. Each field-level change is recorded in `audit_log` so the history stays intact.

The asset tag and equipment model remain immutable. Bulk edit, model reclassification, and a separate inline-status-flip widget are explicitly out of scope.

No schema change. One new route, one new template, one entry-point button on the asset detail page.

## Motivation

Asset records drift over time: a workstation moves from one room to another, a drive fails and the condition becomes "damaged", a unit gets pulled into maintenance. Today the UI exposes register-only and read-only views (`/inventory/assets/register/<model_id>` and `/inventory/asset/<id>`); there is no way to update an existing asset without editing the SQLite file directly. This spec closes that gap with the smallest viable form.

## Permissions

| Role | Access |
|---|---|
| `admin` | full access |
| `manager` | full access |
| `technician` | full access |
| `employee` | redirected with "Access denied." |
| anonymous | redirected to `/login` by the global `before_request` |

This matches the existing pattern used by `register_asset` and `add_location` in `routes/inventory.py`.

## Route

```
GET  /inventory/asset/<int:asset_id>/edit   → render form prefilled with current values
POST /inventory/asset/<int:asset_id>/edit   → validate, update, audit, redirect
```

Implemented as `def edit_asset(asset_id)` in `routes/inventory.py`, registered on `inventory_bp`.

If `asset_id` does not exist, flash `"Asset not found."` and redirect to `/inventory/assets` (matching `asset_detail`).

## Editable fields

| Field | Column | Input type | Validation |
|---|---|---|---|
| Status | `assets.status` | `<select>` | enum: `available / in_use / reserved / checked_out / maintenance / decommissioned` |
| Condition | `assets.condition` | `<select>` | enum: `good / fair / damaged / decommissioned` |
| Location | `assets.location_id` | `<select>` (loaded from `locations`) | optional; empty value → `NULL` |
| Serial number | `assets.serial_number` | `<input type="text">` | trimmed; empty → `NULL` |
| Quantity represented | `assets.qty_represented` | `<input type="number" min="1">` | integer ≥ 1 |
| Notes | `assets.notes` | `<textarea>` | free text, trimmed |

The form's enum dropdowns must list values in the exact spelling that the schema's CHECK constraints accept. SQLite reports CHECK violations as opaque `IntegrityError`s, so the route also validates server-side before the UPDATE — bad values flash a friendly error rather than a 500.

## Read-only fields (shown on the form, not editable)

- **Asset tag** (`SAIL-NNNN`) — primary human-facing identifier; renaming would invalidate every printed label and external reference.
- **Equipment model** — switching the model silently moves the asset between product lines, which would corrupt rollups in the inventory and reports views. A model change is rare; if needed, it gets its own dedicated flow.
- **Created at**, **Updated at** — informational only.

## Validation behaviour

On `POST`:

1. Re-fetch the asset; 404-equivalent flash + redirect if it has been deleted in another tab.
2. Read each field. Trim strings; coerce `qty_represented` to `int`.
3. Reject and re-render with the user's submitted values + a flash if:
   - `status` not in the status enum.
   - `condition` not in the condition enum.
   - `qty_represented` is missing, non-integer, or `< 1`.
   - `location_id` is non-empty but not a valid `locations.id`.
4. If all validation passes, build a diff against the current row.
5. If the diff is empty, redirect back to the detail page with `flash("No changes.", "info")`.
6. Otherwise apply the UPDATE and write one audit row per changed field (see below).

The form preserves submitted values on validation failure so the user does not have to retype.

## Audit log

Each changed field is its own `audit_log` row, written in the same `with get_db() as conn:` block as the UPDATE so either everything commits or everything rolls back.

```python
log_audit(conn, 'assets', asset_id, 'update',
          field_name=col, old_value=old, new_value=new,
          changed_by=g.user['id'])
```

This matches the per-field convention `log_audit` is already designed for (it's the reason `field_name`, `old_value`, `new_value` exist as separate parameters in `database.py`).

If no fields changed, no audit rows are written.

## Template

New file: `templates/inventory/edit_asset.html`.

Structured like `register_asset.html` for visual consistency:

- Page header with breadcrumb back to the asset detail page.
- Read-only summary block at the top: asset tag, model name, brand, created-at.
- One `<form method="post" class="form-card">` containing the six editable fields.
- "Save changes" primary button + "Cancel" ghost link back to the asset detail page.

## Entry point

In `templates/inventory/asset_detail.html`, add an "Edit asset" button visible only when `g.user.role` is in `('admin', 'manager', 'technician')`. Place it in the existing page header next to any other actions, mirroring how the inventory model pages expose their edit action.

## Out of scope

The following are intentionally excluded from this spec:

- **Editing `asset_tag`.** Tags are stable identifiers; rename support adds risk for no current need.
- **Editing `equipment_model_id`.** Reclassification is rare; it deserves its own flow with confirmation.
- **Bulk edit.** Selecting multiple assets and applying a status change in one shot is a separate feature.
- **Inline status-only widget on the detail page.** The full edit form covers status; one place, one mental model.
- **Soft delete / archive.** Status `decommissioned` already covers retirement.

## Acceptance criteria

1. An admin/manager/technician can navigate from `/inventory/asset/<id>` → "Edit asset" → submit changes → land back on the detail page with the new values displayed and a success flash.
2. An employee role visiting `/inventory/asset/<id>/edit` is redirected to the dashboard with "Access denied."
3. Submitting an out-of-enum status or condition (e.g. via a tampered request) produces a friendly flash error and re-renders the form with the user's other inputs preserved — no 500, no silent failure.
4. After a save that changes three fields, `audit_log` contains exactly three new rows scoped to that asset, each with `field_name`, `old_value`, and `new_value` populated and `changed_by = g.user['id']`.
5. Submitting the form without changing anything redirects with `flash("No changes.", "info")` and writes zero audit rows.
6. The asset tag and equipment model are visible on the form but cannot be edited via any input on the page.
