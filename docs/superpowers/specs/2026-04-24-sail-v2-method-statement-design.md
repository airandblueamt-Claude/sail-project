# SAIL Program Method Statement — Design Requirements

**Status:** Draft for review
**Date:** 2026-04-24
**Scope:** Program-level direction for the next three phases of SAIL. Per-feature design specs and implementation plans follow this document.

---

## 1. Executive Summary

SAIL is AMT's IT asset and ticketing system. This method statement proposes a three-phase evolution from the current internal tool into AMT's primary coordination point for LAB resource booking and technical support, with a locally-hosted AI agent participating from Phase 3.

**Phase 1 — Internal test release (~4 weeks).** Polish and close the loop on what exists today: every ticket is tied to an asset record, every ticket has a visible story history, every category routes alerts to the right people automatically, and scheduled report digests flow to configured recipients. Big tickets (e.g. HPC user onboarding) get simple checklists so progress is visible. Deployed to an internal VM; SQLite retained; backups on cron. Target users: AMT internal team, using the real inventory data collected over the last several weeks.

**Phase 2 — Production release + WhatsApp channel (~3 weeks after Phase 1 stabilizes).** Roll out to SAIL owners (managers/admins) and end users. Add WhatsApp one-way notifications alongside email via Meta WhatsApp Business Cloud API — outbound alerts only; ticket creation stays in the web app. Multi-week dependency: AMT's WhatsApp Business sender approval status (open question, see §9).

**Phase 3 — AI-in-the-loop (~6-8 weeks, gated by HPC refresh completion).** A locally-hosted LLM on the refreshed HPC Linux cluster performs two read-only roles: (i) auto-classifies incoming tickets and suggests priority, and (ii) answers natural-language questions grounded in a RAG index of SAIL's tickets, assets, agreements, and history. The AI never writes to SAIL in this phase — it assists humans. Autonomous provisioning (e.g. executing an HPC sandbox setup end-to-end) is explicitly out of scope and left to a follow-up brainstorm.

**What this document is for.** Approval of phasing, scope, and architecture direction — not approval of per-feature implementation detail. Each Phase 1 feature will get its own design spec (`docs/superpowers/specs/`) and implementation plan (`docs/superpowers/plans/`) before code is written, following the convention established by the existing asset-agreements and ticket-board/SLA documents.

**What it is not.** Not a replacement for security review (WhatsApp and cross-network HPC access will require that), not a commitment to the AI agent's scope beyond Phase-3 triage + Q&A, and not a re-architecture of the existing application.

---

## 2. Current State

The application is a single Flask app with blueprint-based routing, a SQLite database (WAL + foreign keys enforced), session-based email-only authentication, and a custom CSS design system with light/dark theming. There is no build step, no test suite, and no linter configured.

### 2.1 Implemented and in use

- **Equipment catalog** (`equipment_models`) — one row per product line, with brand, specs, photo, `is_bookable` flag, and `expected_qty`.
- **Individual asset tracking** (`assets`) — physical units with `SAIL-####` tags, serial numbers, location, condition, status; `qty_represented > 1` supports bulk lots that don't warrant per-unit tagging.
- **Reserve → approve → checkout → return booking flow** against individual assets; approvals routed to admins.
- **Ticketing** — types (`maintenance`, `move`, `new_request`, `incident`, `decommission`, `other`), priorities (`low`-`critical`), status lifecycle (`open → in_progress → waiting → resolved → closed`), assignee, submitter, `asset_id` FK already linking tickets to asset records, and a `ticket_comments` thread per ticket.
- **Equipment agreements** (warranty / license / support) with end-date tracking and type indexing.
- **Reports** — on-demand weekly and monthly rollups for inventory and tickets, with CSV export and a full-database Excel export.
- **Audit log** — every mutation written through `get_db()` records to `audit_log` with table, record id, action, and actor.
- **Email notifications** via Gmail SMTP (registration, booking status transitions, ticket updates). Silently no-ops when `SAIL_SMTP_PASSWORD` is not set.
- **Role model** — `admin`, `manager`, `technician`, `employee`.

### 2.2 Designed but not yet built (already in `docs/superpowers/`)

- **Ticket kanban board + SLA tracking** — drag-drop status transitions; admin-configurable per-priority SLA hours; computed `is_overdue` flag. Spec and plan exist; implementation pending.

### 2.3 Not yet designed — this document introduces

- Configurable per-category alert routing (§3.1)
- Ticket checklists for big-ticket progress visibility (§3.2)
- Unified story-history timeline on the ticket detail page (§3.3)
- Scheduled report digests (§3.4)
- VM deployment and operational model (§3.5)
- WhatsApp channel (Phase 2, §4)
- Local AI agent on the HPC cluster (Phase 3, §5)

---

## 3. Phase 1 — Internal Test Release

Target: ~4 weeks. Every item below becomes its own spec + plan file in `docs/superpowers/` before any code is written.

### 3.1 Configurable per-category alert routing

Admin-edited table maps `(category, minimum_priority) → [recipient emails]`. When a ticket is created or transitions status, the existing email service fans out to the computed recipient set based on the ticket's category and priority. Current hard-coded "notify admin" paths are replaced by this lookup.

**Acceptance:** admin page at `/admin/alerts` lists rules, add/edit/delete; a matching rule sends email within seconds of the triggering event; no match falls back to the existing admin email so nothing is silently dropped; all rule changes land in `audit_log`.

### 3.2 Ticket checklists

New `ticket_checklist_items` table. Ticket creator or assignee can add, tick, reorder, and delete items. Checklist renders as a progress bar on the ticket card (kanban) and as a list with checkboxes on the detail page. No templates in Phase 1.

**Acceptance:** a ticket shows `"3 / 7"` on its card when 3 of 7 items are done; completing the last item does not auto-close the ticket (closing stays explicit); each toggle writes to `audit_log` and appears in the story history.

### 3.3 Unified story-history timeline

On the ticket detail page, render a single chronological feed merging `ticket_comments` with `audit_log` rows scoped to that ticket (status transitions, assignment changes, checklist toggles, asset re-links). Human-readable labels for each event type; actor and timestamp on every row.

**Acceptance:** every mutation to the ticket is visible in the feed without refreshing assumptions about what "recent activity" means; comments and events interleave in true chronological order; feed is read-only (composing stays in the existing comment form).

### 3.4 Scheduled report digests

New `report_schedules` table. A cron-driven job (`python send_digests.py` via systemd timer) dispatches the configured digest at its cadence using the existing report queries, rendered to HTML email. Phase 1 cadences: daily, weekly, monthly. Arbitrary cron expressions are deferred.

**Acceptance:** admin page at `/admin/digests` lists, adds, edits, pauses, and deletes schedules; a "Send now" button on each row runs immediately for testing; every dispatch is audit-logged; a failed SMTP send is retried once then recorded on the schedule row (`last_status`, `last_error`).

### 3.5 VM deployment

Internal VM (Ubuntu LTS), reachable on corporate LAN / VPN only. Stack: `nginx` (TLS termination with internal cert) → `gunicorn` → the existing Flask app; `systemd` unit manages lifecycle; `systemd` timers run `backup_db.py` nightly and `send_digests.py` every 15 minutes; `SAIL_SMTP_PASSWORD` and any future secrets loaded from `/etc/sail/env`. SQLite stays (WAL mode already on). A `deploy/` directory in the repo holds nginx config, systemd units, the env template, and a one-page README.

**Acceptance:** fresh VM → cloned repo → `deploy/install.sh` → working site behind the internal hostname; nightly backup lands in a dated folder; `systemctl restart sail` cycles cleanly; the `deploy/README.md` runbook is short enough that anyone on the team can redeploy from it after a VM reimage.

### 3.6 Ticket ↔ asset UI polish

Data linkage is already there (`tickets.asset_id`). Phase 1 surfaces it better: asset picker on ticket-create with search by tag/serial/model; asset detail page lists all tickets that reference it, grouped by status; dashboard shows "assets with open tickets" as a tile.

**Acceptance:** creating a ticket, typing `SAIL-0042` or a serial fragment narrows the picker live; opening an asset shows its ticket history inline; an asset's status badge on the inventory list shows a small flag when it has any open ticket.

### 3.7 Kanban board + SLA tracking (fold-in)

Implementation of the existing spec `docs/superpowers/specs/2026-04-13-ticket-board-sla-design.md`. No design changes. Folded into Phase 1 because the board is the most visible deliverable and the SLA overdue flag drives a valuable subset of alerting (the overdue compute is reused as an alert trigger in §3.1).

**Acceptance:** the existing plan's task list runs to completion; the overdue flag is usable by the alert rules in §3.1 (a rule can specify "only if overdue").

---

## 4. Phase 2 — WhatsApp Channel

Target: ~3 weeks, starting once Phase 1 is stable in production. Contains one multi-week external dependency (WhatsApp Business sender approval) that should be kicked off **at Phase 1 start**, not Phase 2 start.

### 4.1 Scope

Outbound, one-way WhatsApp notifications delivered through Meta WhatsApp Business Cloud API, as an additional channel alongside email. Inbound messages, ticket creation via WhatsApp, and two-way conversations are explicitly out of scope for Phase 2.

### 4.2 Delivery model

The alert routing table from §3.1 gains a per-rule channel selector: `email`, `whatsapp`, or both. Recipients gain an optional `whatsapp_number` field (E.164 format) on their employee record; rules with `channel = whatsapp` skip recipients who haven't provided a number and fall back to email for those recipients so nothing is silently dropped.

WhatsApp's rules require pre-approved **message templates** for any outbound notification outside a 24-hour service window. Phase 2 registers three templates: `ticket_assigned`, `ticket_overdue`, `ticket_status_changed`. Free-form WhatsApp replies are not expected and not handled.

### 4.3 Implementation shape

A thin `whatsapp_service.py` module mirrors `email_service.py` — one sender function that accepts a template key and variables, posts to the Cloud API, returns success/failure. A `whatsapp_deliveries` table records each attempted send (template, recipient, ticket ref, status, message id, error) for audit and debugging. No message queue — synchronous send with one retry, mirroring the digest dispatch pattern.

### 4.4 Acceptance criteria

- A ticket triggers both an email and a WhatsApp message when a matching rule specifies both channels.
- Recipients without a WhatsApp number fall back to email on WhatsApp-only rules; this fallback is logged.
- All three templates are approved in the Meta dashboard before first production send.
- An admin can view `whatsapp_deliveries` history per ticket (delivery receipts land in the story history from §3.3).
- A Cloud API outage fails-soft: email is still attempted and the WhatsApp failure is logged, not raised.

### 4.5 Dependencies and blockers

| Item | Risk | Mitigation |
|---|---|---|
| **Meta WhatsApp Business sender approval** | 2-4 weeks, can be longer if the business verification is incomplete | Start application at Phase 1 kickoff so approval window runs in parallel with Phase 1 build |
| **Template approval** | ~1 week per template once sender is approved; rejections require rewording | Submit all three templates immediately after sender approval; keep wording plain |
| **Phone number capture for existing employees** | Users have to supply WhatsApp numbers; adoption may be slow | Opt-in field on profile page; reminder on first login after Phase 2 ships |
| **Data residency / consent** | Sending employee numbers + ticket metadata to Meta's API may need legal sign-off under AMT's data policy | Flag to legal/compliance at Phase 1 start; document the data types sent in §9 |

### 4.6 Explicitly out of scope (deferred)

- Inbound WhatsApp messages
- Creating or updating tickets via WhatsApp
- Teams, Slack, SMS, or other channels (evaluated after Phase 2 adoption is measured)
- Rich media (images, PDFs) in messages — text-only templates in Phase 2

---

## 5. Phase 3 — AI-in-the-loop

Target: ~6-8 weeks. **Gated by HPC refresh completion** — the cluster hardware must be online and Linux-configured before this phase can start. Method statement commits to the role and architecture; concrete model choice and prompt design get their own design spec before build starts.

### 5.1 Role (Phase 3 only)

The AI agent performs two **read-only** functions from day one:

1. **Ticket triage.** On ticket creation, the agent receives the title, description, submitter, and any linked asset record. It returns a suggested category, suggested priority, and a one-line summary. Suggestions appear on the ticket as **editable pre-fills**, never as committed values — a human clicks save.
2. **Grounded Q&A.** An authenticated user on SAIL can ask natural-language questions in a chat pane: *"who has the Infiniband card?"*, *"what failed on rack 3 last month?"*, *"which assets have agreements expiring in the next 30 days?"*. The agent retrieves from an index of SAIL data (tickets, comments, assets, agreements, audit log) and answers with citations back to source records.

The agent has **no write path** to SAIL, to WhatsApp, or to the HPC cluster. Autonomous actions (creating tickets, changing status, provisioning HPC sandboxes, sending messages) are explicitly out of scope for Phase 3.

### 5.2 Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  SAIL web app (internal VM, SQLite)                          │
│                                                              │
│   Ticket create → calls AI /triage → gets suggestion         │
│   Chat pane    → calls AI /ask    → gets grounded answer     │
└───────────────┬──────────────────────────────────────────────┘
                │ HTTPS, internal network only, bearer token
                ▼
┌──────────────────────────────────────────────────────────────┐
│  AI agent service (HPC cluster, Linux, GPU)                  │
│                                                              │
│   FastAPI endpoints: /triage  /ask  /reindex                 │
│   │                                                          │
│   ├─ Local LLM (Ollama or vLLM serving e.g. Llama/Qwen)      │
│   ├─ Vector index (e.g. Chroma/Qdrant on local disk)         │
│   └─ Nightly reindex job (pulls SAIL DB snapshot via SSH)    │
└──────────────────────────────────────────────────────────────┘
```

Data flow is **strictly pull-from-SAIL**: a nightly job on the HPC side fetches a read-only SQLite snapshot over SSH, extracts rows into the vector store. Day-1 freshness is "up to 24 hours" — acceptable for Q&A. Triage does **not** rely on the index (it operates on the ticket payload alone), so triage latency is model-bound, not index-bound.

### 5.3 Model and infra choices (direction; finalized in Phase-3 design spec)

- **Model size**: small-to-mid open-weight models (7B-30B class) running locally. Choice driven by the refreshed cluster's GPU memory budget; document the selection and benchmark at spec time.
- **Serving**: Ollama for simplicity, or vLLM for higher throughput — decided in the Phase-3 design spec based on expected query volume.
- **Vector store**: Chroma or Qdrant — local disk, single-node, no clustering. Re-indexable from source SQLite at any time.
- **Embeddings**: a local embedding model of the same provenance as the LLM (no external API calls).

**All AI data stays on AMT infrastructure.** No OpenAI, Anthropic, or other external API is called. This is a hard requirement from the "locally hosted" framing and affects every component choice.

### 5.4 Integration surface with SAIL

- One new config file: `AI_AGENT_URL`, `AI_AGENT_TOKEN`, both optional — if unset, SAIL runs exactly as today with no AI UI.
- Ticket-create form gets a "Suggest" button (calls `/triage`); suggestions render as filled but editable fields.
- New chat route `/ask` renders a simple chat pane; restricted to `manager` and `admin` roles in Phase 3 (broader rollout after we see how it's used).
- An `ai_interactions` table logs every `/triage` and `/ask` call for audit: user, prompt, response, latency, model version, confidence score if available. Auditability matters because this is a stakeholder-facing introduction of AI.

### 5.5 Acceptance criteria

- A new ticket's Suggest button returns a category + priority + summary within ~5 seconds on the target cluster.
- Suggestions are wrong as often as they are right at first — the measure is **no regression** on current behavior (human still decides), not suggestion accuracy. Accuracy is tracked over time via the `ai_interactions` log.
- A Q&A query returns an answer with at least one clickable citation to a SAIL record; clicking the citation opens that record in SAIL.
- The system degrades gracefully: if the agent service is down, SAIL behaves as today (no Suggest button, chat pane shows "AI offline"), never with a crash or a blocking error.
- All AI calls are logged to `ai_interactions`.
- No outbound traffic from the agent service to the public internet during normal operation (verified by firewall rule or at minimum by monitoring).

### 5.6 Dependencies and blockers

| Item | Risk | Mitigation |
|---|---|---|
| **HPC refresh completion** | Unknown timeline outside this project | Phase 3 design spec cannot begin build until cluster is Linux-ready and GPUs are addressable; flag as the first gating question |
| **Network path SAIL VM ↔ HPC cluster** | If the HPC cluster is on a different VLAN, firewall rules must be opened | Scope during Phase 3 design spec, involve network/security early |
| **Model selection & eval** | Picking a model that underperforms on AMT's domain | Allocate a week of the Phase 3 build to benchmarking 2-3 candidate models on a seeded eval set of real historical tickets |
| **Dataset quality** | Triage quality depends on current ticket data being well-labelled | Phase 1 incentivizes accurate categorization (alert rules key on category), which should improve label quality passively; Phase 3 may also need a one-off relabelling pass on historical tickets — scope during the Phase-3 design spec. |

### 5.7 Explicitly out of scope (for Phase 3)

- Writing to SAIL from the agent (auto-assign, auto-close, auto-reply).
- Writing to WhatsApp from the agent.
- Autonomous HPC provisioning — e.g. executing the big-ticket example of onboarding a lab user with a GPU budget and container sandbox. This deserves its own brainstorm once triage + Q&A are proven.
- Training or fine-tuning on AMT data — Phase 3 is RAG-only.
- Multi-tenant or per-user model isolation.

---

## 6. Architecture Overview

```
┌───────────────────────────────────────────────────────────────────────────────┐
│  AMT corporate network (LAN / VPN)                                            │
│                                                                               │
│    ┌─────────────────┐                                                        │
│    │ End users       │  browser                                               │
│    │ (employees,     │ ─────────┐                                             │
│    │  managers,      │          │                                             │
│    │  technicians,   │          ▼                                             │
│    │  admins)        │   ┌───────────────────────────────────────────┐        │
│    └─────────────────┘   │  SAIL web app  (Phase 1 — internal VM)    │        │
│                          │                                           │        │
│                          │   nginx (TLS, internal cert)              │        │
│                          │    └─ gunicorn ─ Flask app                │        │
│                          │         │                                 │        │
│                          │         ├─ SQLite (WAL)  ◄── backup cron  │        │
│                          │         │                                 │        │
│                          │         ├─ email_service.py ──┐           │        │
│                          │         ├─ whatsapp_service.py┼──┐ Phase 2│        │
│                          │         └─ send_digests.py    │  │        │        │
│                          └─────────────────┬─────────────┴──┴────────┘        │
│                                            │                │                 │
│                                   HTTPS    │                │                 │
│                                  (bearer)  │                │                 │
│                                            ▼                │                 │
│    ┌────────────────────────────────────────────────────┐   │                 │
│    │  HPC cluster (refreshed Linux)  — Phase 3          │   │                 │
│    │                                                    │   │                 │
│    │    AI agent service (FastAPI)                      │   │                 │
│    │       ├─ /triage  /ask  /reindex                   │   │                 │
│    │       ├─ Local LLM (Ollama or vLLM)  ◄── GPUs      │   │                 │
│    │       ├─ Vector index (Chroma/Qdrant)              │   │                 │
│    │       └─ Nightly reindex job ◄── SSH pull sail.db  │   │                 │
│    └────────────────────────────────────────────────────┘   │                 │
│                                                             │                 │
└─────────────────────────────────────────────────────────────┼─────────────────┘
                                                              │
                                        public internet (TLS) │
                                                              ▼
                              ┌──────────────────────┐    ┌────────────────────┐
                              │  Gmail SMTP (exists) │    │ Meta WhatsApp      │
                              │  — transactional mail│    │ Business Cloud API │
                              └──────────────────────┘    │     (Phase 2)      │
                                                          └────────────────────┘
```

### 6.1 Notes on the diagram

- **Phase 1 surface** is everything inside the SAIL VM plus the existing Gmail SMTP outbound path. No HPC, no WhatsApp.
- **Phase 2 adds** `whatsapp_service.py` inside the Flask app and one new outbound TLS path to Meta's Cloud API. No new hosts, no new inbound surface.
- **Phase 3 adds** the HPC-side AI service and two internal HTTPS call paths (SAIL → agent). The agent pulls SAIL's DB snapshot via SSH once per day — that is SAIL's only exposure to the HPC side. No new public-internet egress.
- **Authentication**: users log in to SAIL with the existing email-session auth. SAIL → AI agent uses a bearer token. Agent → SAIL (for the nightly snapshot pull) uses an SSH key with read-only access to the backup directory. No end-user traffic reaches the HPC cluster directly.
- **All three external dependencies** (Gmail SMTP, WhatsApp API, HPC cluster) can fail without taking SAIL down — the app degrades to "no email", "no WhatsApp", and "no AI suggestions" respectively.

### 6.2 Network posture

| Path | Direction | Protocol | Notes |
|---|---|---|---|
| User browser → SAIL | inbound to VM | HTTPS (internal cert) | LAN / VPN only, not internet-reachable |
| SAIL → Gmail SMTP | outbound to internet | SMTP+STARTTLS, port 587 | existing |
| SAIL → Meta Cloud API | outbound to internet | HTTPS | **Phase 2** |
| SAIL → AI agent | outbound within corporate network | HTTPS + bearer token | **Phase 3** |
| AI agent → SAIL VM | outbound within corporate network | SSH (read-only, key-based) | **Phase 3**, nightly |
| AI agent → internet | **blocked** | — | **Phase 3** requirement: firewall denies public egress |

### 6.3 What the diagram deliberately does not show

- The existing `backup_db.py` cron path and the `/etc/sail/env` secret file — mentioned in §3.5, not critical at architecture level.
- Internal monitoring / log shipping — deferred to §8 (Operations).
- The employee / asset / ticket entity relationships — those live in §7 (Data model).

---

## 7. Data Model Deltas (Phase 1)

Only Phase 1 changes are listed. Phase 2 (`whatsapp_deliveries`, recipient `whatsapp_number` column) and Phase 3 (`ai_interactions`) land in their own specs.

Every new table follows the existing conventions: `INTEGER PRIMARY KEY AUTOINCREMENT`, `created_at TEXT DEFAULT (datetime('now'))`, `CHECK` constraints on enum-like columns, indexes on foreign keys and common filter columns. All mutations go through `get_db()` so they write to `audit_log` automatically.

### 7.1 `alert_rules` (§3.1)

```sql
CREATE TABLE IF NOT EXISTS alert_rules (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id    INTEGER REFERENCES categories(id),   -- NULL = matches all categories
    min_priority   TEXT NOT NULL
                   CHECK(min_priority IN ('low','medium','high','critical')),
    event          TEXT NOT NULL
                   CHECK(event IN ('ticket_created','status_changed','overdue','any')),
    channels       TEXT NOT NULL DEFAULT 'email'
                   CHECK(channels IN ('email','whatsapp','both')),
    recipients     TEXT NOT NULL,                       -- comma-separated emails
    is_active      INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_alert_rules_active ON alert_rules(is_active, category_id);
```

**Notes.** `recipients` as a comma-separated TEXT column (not a join table) is deliberate: admins edit rules in a simple textarea, external partner emails are supported without needing an employee record, and the volume (dozens of rules) doesn't justify a join. `category_id NULL` supports a catch-all rule. `channels = 'whatsapp'` or `'both'` is accepted at the schema level but is only honored after Phase 2 ships — Phase 1 code treats whatsapp channels as email fallback (per §4.2).

### 7.2 `ticket_checklist_items` (§3.2)

```sql
CREATE TABLE IF NOT EXISTS ticket_checklist_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id    INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    label        TEXT NOT NULL,
    is_done      INTEGER NOT NULL DEFAULT 0,
    sort_order   INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT DEFAULT (datetime('now')),
    completed_at TEXT,                                  -- set when is_done flips 0→1
    completed_by INTEGER REFERENCES employees(id)
);
CREATE INDEX IF NOT EXISTS idx_checklist_ticket ON ticket_checklist_items(ticket_id, sort_order);
```

**Notes.** `ON DELETE CASCADE` is intentional — if a ticket is hard-deleted, its checklist disappears with it. `completed_at` + `completed_by` let the story-history timeline (§3.3) render a meaningful event row (e.g. "Mohammad completed 'allocate GPU budget' at 14:03").

### 7.3 `report_schedules` (§3.4)

```sql
CREATE TABLE IF NOT EXISTS report_schedules (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    report_key    TEXT NOT NULL
                  CHECK(report_key IN ('tickets_weekly','tickets_monthly',
                                       'inventory_weekly','inventory_monthly',
                                       'agreements_expiring')),
    cadence       TEXT NOT NULL
                  CHECK(cadence IN ('daily','weekly','monthly')),
    recipients    TEXT NOT NULL,                        -- comma-separated emails
    is_active     INTEGER NOT NULL DEFAULT 1,
    last_run_at   TEXT,
    last_status   TEXT CHECK(last_status IN ('success','failed') OR last_status IS NULL),
    last_error    TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_digests_active ON report_schedules(is_active, cadence);
```

**Notes.** Cadence is fixed at `daily / weekly / monthly` per §3.4 — arbitrary cron expressions are deferred to a later phase. `last_run_at` / `last_status` / `last_error` live on the row itself rather than in a separate `digest_failures` table because the volume is low (a few schedules, one row per schedule) and this keeps the admin UI's "last run" indicator a single JOIN-free query. If full history becomes useful, a `digest_runs` table is added then.

### 7.4 `sla_thresholds` (fold-in from §3.7)

Already defined in `docs/superpowers/specs/2026-04-13-ticket-board-sla-design.md`:

```sql
CREATE TABLE IF NOT EXISTS sla_thresholds (
    priority     TEXT PRIMARY KEY
                 CHECK(priority IN ('low','medium','high','critical')),
    hours        INTEGER NOT NULL CHECK(hours > 0),
    updated_at   TEXT DEFAULT (datetime('now'))
);
```

No change to that spec. Listed here for completeness because it's part of Phase 1.

### 7.5 No schema changes required for

- **§3.3 story history** — renders from existing `audit_log` and `ticket_comments`.
- **§3.5 VM deployment** — infra only.
- **§3.6 ticket ↔ asset UI polish** — `tickets.asset_id` already exists with an index.

### 7.6 Migration

New tables are additive. Applied to production via `init_db.py` re-running `schema.sql` — `CREATE TABLE IF NOT EXISTS` is safe against the existing `sail.db`. No destructive migration, no data backfill required. A backup via `backup_db.py` runs immediately before the schema step as a precaution.

---

## 8. Operations

Scope: how the system runs day-to-day after Phase 1 ships. Phase 2 and 3 operational additions are noted where relevant but not elaborated — they belong to those phases' own specs.

### 8.1 Deployment

**Machine:** one internal VM, Ubuntu 22.04 LTS (or the AMT-standard LTS), 2 vCPU / 4 GB RAM / 40 GB disk is more than enough for current scale. Hostname on corporate DNS; reachable on LAN/VPN only; no public internet ingress.

**Stack:**

```
nginx (TLS termination, internal cert)
  └─ proxy_pass → gunicorn (unix socket)
                    └─ Flask app (create_app())
```

**Files shipped via `deploy/`:**

| File | Purpose |
|---|---|
| `deploy/install.sh` | Idempotent bootstrap: apt packages, Python venv, clone/pull, run `init_db.py` if `sail.db` missing, install services |
| `deploy/nginx/sail.conf` | Server block with TLS and the unix-socket upstream |
| `deploy/systemd/sail.service` | `gunicorn` under systemd; `Restart=on-failure`; reads `/etc/sail/env` |
| `deploy/systemd/sail-digests.timer` + `.service` | Runs `send_digests.py` every 15 minutes (the script itself decides which schedules are due) |
| `deploy/systemd/sail-backup.timer` + `.service` | Runs `backup_db.py` nightly at 02:00 |
| `deploy/env.template` | Documents all required env vars (`SAIL_SMTP_PASSWORD`, `SAIL_SECRET_KEY`, etc.) |
| `deploy/README.md` | One page: fresh-VM bringup in under 15 minutes |

systemd timers are preferred over raw cron because they log through journalctl with the rest of the service, which makes incident triage one command (`journalctl -u sail`).

### 8.2 Backups

- **Database**: `backup_db.py` runs nightly, writes `backups/sail-YYYYMMDD-HHMMSS.db`, keeps the last 10 (existing behavior, unchanged).
- **Photos / uploaded files** (`static/uploads/`): added to the nightly job as a `tar.gz` alongside the DB snapshot. Same 10-generation retention.
- **Off-VM copy**: the `backups/` directory is rsynced nightly to a second internal location (NFS share, another VM, or IT's standard backup target — to be decided with IT ops, documented in §9 as an open item).
- **Restore drill**: documented one-pager in `deploy/README.md`: stop service, restore latest `.db`, untar uploads, restart, verify login. Target: executable in under 10 minutes with no reference material.

### 8.3 Monitoring and logs

Phase 1 is deliberately light — instrument enough to debug problems, no dashboards:

- **Application logs** → stdout → systemd journal → `journalctl -u sail`. Rotation handled by journald.
- **Access logs** → nginx, rotated by logrotate (default Ubuntu config is fine).
- **Digest/backup success** → visible in `report_schedules.last_status` and the file dates of `backups/` respectively. One small admin page at `/admin/ops-health` shows: uptime, last backup timestamp, pending/failed digests, last 10 audit-log rows. No Prometheus, no Grafana in Phase 1.
- **Email deliverability** → failures are caught in `email_service.py`, logged with the ticket/digest id, and surfaced on the `/admin/ops-health` page. No separate alerting — if the team isn't getting expected emails, the ops-health page tells you why.

Phase 2 adds `whatsapp_deliveries` as the equivalent surface for WhatsApp failures. Phase 3 adds `ai_interactions` for AI call observability and introduces a separate health check endpoint on the agent service.

### 8.4 Ownership

| Area | Owner |
|---|---|
| Application code, schema, specs, plans | SAIL engineering (this team) |
| VM provisioning, OS patching, network rules, TLS cert renewal | AMT IT ops |
| Backups destination and offsite copy | AMT IT ops (directory location to be decided) |
| WhatsApp Business account + sender approval (Phase 2) | To be assigned — see §9 |
| HPC cluster refresh and agent host infra (Phase 3) | HPC team — see §9 |
| User role assignments, alert rule content, digest schedules | SAIL admins (operational, not engineering) |

### 8.5 Change management

- Every schema or route change lands via a spec → plan → commit sequence in `docs/superpowers/`.
- `audit_log` is the canonical record of production data changes; `journalctl` is the canonical record of deploys and restarts.
- Releases to the VM: pull from `master`, run `deploy/install.sh` which re-applies schema (additive), restart the service. No blue-green, no staging env in Phase 1 — the existing backup cadence plus the low change volume make rollback (restore backup + `git checkout <prev>`) acceptable.
- A **staging VM** becomes warranted once WhatsApp and AI integrations are in play (Phase 2/3); noted as §9 open item.

---

## 9. Risks & Open Questions

Honest inventory of what this document doesn't yet resolve. Each row has an owner or an "owner TBD" flag — resolving these is the path from approved method statement to confident execution.

### 9.1 Must resolve before Phase 2 can start

| # | Item | Impact | Action needed |
|---|---|---|---|
| R1 | **WhatsApp Business sender approval status** — does AMT already have an approved sender, or do we start from scratch? | 2-4 weeks of calendar time on the critical path for Phase 2 | Confirm with AMT admin/IT. If starting from scratch, kick off business verification at **Phase 1 start**, not Phase 2 start. |
| R2 | **Data residency / consent for WhatsApp payloads** — sending employee phone numbers + ticket metadata to Meta's API may need legal sign-off under AMT's data policy. | Could invalidate Phase 2 scope if legal declines | Raise to AMT legal/compliance; document the exact data types sent (ticket title/id, employee display name, phone number). |
| R3 | **Who owns the WhatsApp Business account?** | Approval paperwork cannot proceed without a named owner and billing account | Assign an owner at Phase 1 kickoff. |

### 9.2 Must resolve before Phase 3 can start

| # | Item | Impact | Action needed |
|---|---|---|---|
| R4 | **HPC cluster refresh completion timeline** | Phase 3 cannot start until the cluster is Linux-operational with addressable GPUs | Get expected ready date from the HPC team; adjust Phase 3 kickoff accordingly. Until this is known, Phase 3 is a placeholder, not a scheduled phase. |
| R5 | **Network path SAIL VM ↔ HPC cluster** | If the two are on different VLANs, firewall rules must be opened before build begins | Involve network/security ops during Phase 3 design spec, not during build. |
| R6 | **Model selection and eval set** | Picking the wrong model or having no evaluation baseline means triage quality is unmeasurable | Allocate the first week of Phase 3 to benchmarking 2-3 candidate models against a seeded eval set of real historical tickets; document the selection and the numbers. |
| R7 | **Agent host ownership** — who administers the AI agent service on the cluster (updates, restarts, GPU resource sharing with other HPC workloads)? | Operational muddy middle: SAIL engineering doesn't own HPC, HPC team doesn't own SAIL | Define a joint runbook during Phase 3 design spec; name a responsible engineer on each side. |

### 9.3 Should resolve during Phase 1

| # | Item | Impact | Action needed |
|---|---|---|---|
| R8 | **Offsite / secondary backup destination** | Without it, a VM loss is a recovery from the most recent DB copy on the same host — unacceptable for production | Decide with AMT IT ops where `backups/` gets rsynced (internal NFS, dedicated backup VM, etc.) and when it runs. |
| R9 | **Staging environment** | Phase 1 accepts no staging (rollback via backup restore). Phase 2+ with WhatsApp templates and AI integrations needs at minimum a second VM to exercise outbound integrations without hitting production | Provision a staging VM at the start of Phase 2; identical stack, separate DB, test recipients only. |
| R10 | **"SAIL owners" role definition** — "SAIL owners" is referenced in §1 and §4 as a distinct audience, but it may or may not warrant a separate role from the existing `admin / manager / technician / employee` model | Low, but worth a decision so Phase 2 rollout messaging is clear | Treat "SAIL owners" as shorthand for `admin` + `manager`. No new role added unless a Phase 2 review surfaces a reason. |

### 9.4 Known-unknowns deferred to their own brainstorms

| # | Item | Why deferred |
|---|---|---|
| R11 | **Autonomous HPC provisioning** — executing the big-ticket onboarding example end-to-end (container sandbox, GPU budget allocation, credential delivery) | Security surface and workflow complexity warrant their own design cycle once Phase 3 read-only AI is proven. Listed here so stakeholders see it on the roadmap, not forgotten. |
| R12 | **GPU budget enforcement** — how "1,500 hours per user" is tracked and enforced | Depends on the HPC cluster's job-scheduler choice (Slurm, Kubernetes, etc.), which is an HPC-team decision, not a SAIL decision. SAIL will reference budgets on big-ticket checklists once the enforcement layer exists. |
| R13 | **Inbound WhatsApp / ticket-creation via WhatsApp** | Deferred per §4.6. Revisit only after Phase 2 one-way adoption is measured. |
| R14 | **Additional channels (Teams, Slack, SMS)** | Deferred per §4.6. The §3.1 alert-rule `channels` column is forward-compatible; adding a channel later is a service module + a `CHECK` constraint update. |
| R15 | **Ticket templates** | Deferred per §3.2. Revisit once a second repeatable big-ticket pattern emerges beyond HPC onboarding. |

### 9.5 Risks that are accepted, not mitigated

| # | Risk | Why accepted |
|---|---|---|
| A1 | SQLite under concurrent writes from future WhatsApp webhooks + scheduled digests + AI reindex job | Write volume is very low at AMT's scale; WAL handles it. If contention ever appears, migration to Postgres is a half-day of work — schema is tiny. Not worth doing pre-emptively. |
| A2 | No automated test suite | Inherited state. Adding tests is valuable but not a Phase 1 blocker for a system at this scale with this team size. Evaluating tests-first for Phase 2 specifically where WhatsApp/AI integration points are non-trivial to exercise manually. |
| A3 | Email-only session auth (no password) | Current design choice — keeps onboarding fast inside a trusted internal network. Revisit if SAIL is ever exposed beyond LAN/VPN. |

---

## 10. Next Steps

### 10.1 On approval of this method statement

The following per-feature design specs get written and committed under `docs/superpowers/specs/`, each followed by an implementation plan under `docs/superpowers/plans/`. They are ordered by dependency, not by delivery date — several can be built in parallel.

**Phase 1 specs (write in this order):**

| # | Spec | Depends on |
|---|---|---|
| S1 | `YYYY-MM-DD-alert-rules-design.md` — §3.1 routing table, admin UI, notification dispatcher refactor | — |
| S2 | `YYYY-MM-DD-ticket-checklists-design.md` — §3.2 table, UI, progress bar | — |
| S3 | `YYYY-MM-DD-story-history-design.md` — §3.3 merged timeline query and renderer | — |
| S4 | `YYYY-MM-DD-report-digests-design.md` — §3.4 scheduler, templates, admin page | S1 (reuses recipient handling pattern) |
| S5 | `YYYY-MM-DD-ticket-asset-ui-design.md` — §3.6 asset picker, asset-page ticket list, dashboard tile | — |
| S6 | `YYYY-MM-DD-deploy-vm-design.md` — §3.5 `deploy/` scaffolding, systemd units, nginx, install script, backup wiring | — |

The kanban + SLA work (§3.7) already has its spec and plan from 2026-04-13 — it gets executed as part of Phase 1 without a new spec.

**Phase 2 spec (written during Phase 1 so approvals can run in parallel):**

| # | Spec | Depends on |
|---|---|---|
| S7 | `YYYY-MM-DD-whatsapp-channel-design.md` — §4 outbound service, templates, delivery log | S1 (channel column on `alert_rules`) |

**Phase 3 spec (written once HPC refresh date is known):**

| # | Spec | Depends on |
|---|---|---|
| S8 | `YYYY-MM-DD-ai-agent-design.md` — §5 local LLM service, RAG index, triage & Q&A endpoints, model selection and eval | R4, R5, R7 |

### 10.2 Review cadence

- Each spec above goes through the same brainstorm → design-doc → review → plan → execute cycle that produced this method statement, per the repository's existing `docs/superpowers/` convention.
- Implementation starts on a per-spec basis as soon as that spec is approved — no need to wait for all Phase 1 specs to be written before building the first one.

### 10.3 What this document leaves for each spec

Each per-feature spec will add what this document deliberately omits: exact route paths, template markup, CSS, JavaScript behaviour, edge-case handling, and task-level build steps. The method statement stops at the level of "what capabilities, in what phases, on what architecture, with what acceptance criteria" — deeper than that would be premature.

### 10.4 Kickoff checklist (to start in the week this document is approved)

- [ ] Assign WhatsApp Business account owner (R3) and begin Meta business verification (R1, R2 cleared in parallel).
- [ ] Confirm HPC refresh expected-ready date with the HPC team (R4).
- [ ] Confirm offsite backup destination with AMT IT ops (R8).
- [ ] Provision the Phase 1 internal VM (hostname, DNS, internal TLS cert).
- [ ] Start S1 (alert-rules) and S6 (deploy-vm) design specs in parallel — they have no dependencies on each other and unblock most of the rest.
