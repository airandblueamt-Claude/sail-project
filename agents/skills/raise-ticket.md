---
title: Raise a ticket
use_when: The user wants to file a maintenance, move, incident,
          new-equipment, or decommission ticket — or asks "how do I
          report X" / "how do I log a problem".
---

## Steps

1. **Identify the type.** Ask one short question to pick from:
   - `maintenance` — something is broken or degraded
   - `move` — equipment needs to be relocated
   - `incident` — a one-off problem affecting a user (password reset,
     account locked, login error)
   - `new_request` — they want a new piece of equipment
   - `decommission` — equipment is being retired
   - `other` — when none of the above clearly fit

2. **Find the right category.** Call `list_issue_categories()` and
   quote a real category to use. Do **not** invent category names —
   if the user's issue doesn't fit an existing one, say so and point
   them to `/issue-categories/` (admin only) to add one first.

3. **If the issue is tied to a GPU/BYOC request**, the right path is
   `/gpu/requests/<NUM>` → click "Raise maintenance ticket". That
   pre-fills the link via `?gpu_request_id=N&type=maintenance` so the
   ticket is filed against the request, not against a physical asset.
   In that case skip step 4 below; the linked-ticket flow has its own
   form.

4. **Otherwise, send them to `/tickets/new`.** Required fields:
   - **Asset** — pick from the dropdown; the asset tag is on the
     device sticker (`SAIL-NNNNN`). If they don't know which asset,
     suggest searching the catalog at `/inventory/` first.
   - **Issue Category** — the one chosen in step 2.
   - **Priority** — default `medium`; bump to `high` if it blocks
     work, `critical` if it's affecting production.
   - **Title** — one short line summarising the symptom.
   - **Description** — what happened, when, anything tried.
   - **Affected user** (optional) — fill in their email if you want
     them to receive notifications when the ticket is updated.

## Don'ts

- Don't claim you raised the ticket. You can only point at the URL.
- Don't pick a category at random. If the tool returns categories the
  user dislikes, say so plainly and suggest adding one.
- Don't tell employees to use a category they haven't seen — only
  reviewers (admin/manager/technician) can create new categories.

## Quick reply template

> Sounds like a `<type>` ticket in the `<category>` category. Open
> `/tickets/new?type=<type>` and fill in:
>
> - **Asset:** the device you're reporting (search `/inventory/` if
>   you don't know the tag)
> - **Title:** a one-line summary
> - **Priority:** `<recommended>`
> - **Description:** what happened + anything you've tried
>
> I can't file it for you — you'll need to click submit yourself.
