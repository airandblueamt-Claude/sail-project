"""
SAIL Helper — tool registry.

The chat handler (routes/assistant.py) sends these tool definitions to
Ollama on every turn. When the model decides to call one, the handler
runs `execute_tool(name, args, user)` here and feeds the result back as
a `tool` message.

Design rules:
  - Every tool is READ-ONLY. No INSERT/UPDATE/DELETE. The assistant
    can't mutate the DB. (Write-mode is a deliberate future phase.)
  - Every tool respects the user's role. Employees only see their own
    tickets; reviewers (admin/manager/technician) can search across.
  - Every tool caps result count so the model can't accidentally pull
    the entire DB into a context window.
  - Tool return values are JSON-serialisable dicts/lists. Dates and
    enums stay as-is (the schema uses TEXT for both).

Tool specifications follow the Ollama / OpenAI function-calling shape:
    {"type": "function",
     "function": {"name": ..., "description": ...,
                  "parameters": {<JSON Schema>}}}
which Ollama models with native tool support consume directly.
"""
from __future__ import annotations

import json
from typing import Any

from database import get_db


# ── Tool specs (sent to the model) ────────────────────────────────────────

TOOL_SPECS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "find_tickets",
            "description": (
                "Search SAIL tickets by free-text, status, type, or scope. "
                "Use this whenever the user asks about tickets you don't already "
                "see in the snapshot (e.g. 'do I have any password issues open?', "
                "'what's assigned to me?', 'show me decommission tickets')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query":  {"type": "string", "description": "Free-text match against ticket title and description."},
                    "status": {"type": "string", "enum": ["open", "in_progress", "waiting", "resolved", "closed"]},
                    "ticket_type": {"type": "string", "enum": ["maintenance", "move", "new_request", "incident", "decommission", "other"]},
                    "scope":  {"type": "string", "enum": ["mine", "assigned_to_me", "all"],
                                "description": "'mine' = submitted by the current user; 'assigned_to_me' = currently assigned to them; 'all' = everyone (reviewer roles only)."},
                    "limit":  {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ticket",
            "description": "Fetch the full record of a single ticket by its number (TKT-NNNN). Returns status, priority, asset, comments count, and linked GPU request if any.",
            "parameters": {
                "type": "object",
                "properties": {"ticket_number": {"type": "string", "description": "e.g. TKT-0005"}},
                "required": ["ticket_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_gpu_requests",
            "description": (
                "Search SAIL GPU/BYOC requests. Use this when the user asks about "
                "pending compute requests, agent-drafted requests, requests from a "
                "particular vendor, or requests of a given kind."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind":   {"type": "string", "enum": ["new_infra", "gpu_allocation", "compute_partnership", "other"]},
                    "status": {"type": "string", "enum": ["open", "decided", "all"], "default": "open"},
                    "source": {"type": "string", "enum": ["manual", "agent", "imported"]},
                    "scope":  {"type": "string", "enum": ["mine", "all"], "default": "all",
                                "description": "'mine' = submitted by the current user."},
                    "limit":  {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gpu_request",
            "description": "Fetch the full record of a single GPU/BYOC request by its number (GPU-YYYY-NNNN). Includes VM groups, GPU options, workloads, phases, contributions, document metadata, networking and access fields, and any linked maintenance tickets.",
            "parameters": {
                "type": "object",
                "properties": {"request_number": {"type": "string", "description": "e.g. GPU-2026-0001"}},
                "required": ["request_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_assets",
            "description": "Search the asset inventory by free text (asset tag, serial, model, location, holder). Returns up to `limit` rows with status and condition.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":  {"type": "string"},
                    "status": {"type": "string", "enum": ["available", "assigned", "reserved", "missing"]},
                    "limit":  {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_issue_categories",
            "description": "List the active ticket issue categories. Use this when guiding the user through raising a ticket so you can name a real category.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


REVIEWER_ROLES = {'admin', 'manager', 'technician'}


# ── Tool implementations ──────────────────────────────────────────────────

def _ticket_row(row) -> dict:
    return {
        "ticket_number": row["ticket_number"],
        "title":         row["title"],
        "type":          row["type"],
        "priority":      row["priority"],
        "status":        row["status"],
        "submitted_by":  row["submitter_name"] if "submitter_name" in row.keys() else None,
        "assigned_to":   row["assignee_name"] if "assignee_name" in row.keys() else None,
        "asset_tag":     row["asset_tag"] if "asset_tag" in row.keys() else None,
        "gpu_request":   row["gpu_request_number"] if "gpu_request_number" in row.keys() else None,
        "created_at":    (row["created_at"][:16] if row["created_at"] else None),
    }


def find_tickets(args: dict, user: dict) -> dict:
    with get_db() as conn:
        where, params = ["t.title NOT LIKE 'Booking request:%'"], []
        scope = args.get("scope") or "mine"
        if scope not in ("mine", "assigned_to_me", "all"):
            scope = "mine"
        if scope == "all" and user["role"] not in REVIEWER_ROLES:
            scope = "mine"          # employee tried to use 'all' — silently downgrade
        if scope == "mine":
            where.append("t.submitted_by = ?"); params.append(user["id"])
        elif scope == "assigned_to_me":
            where.append("t.assigned_to = ?"); params.append(user["id"])

        if (q := (args.get("query") or "").strip()):
            where.append("(t.title LIKE ? OR t.description LIKE ?)"); params += [f"%{q}%", f"%{q}%"]
        if (s := args.get("status")):
            where.append("t.status = ?"); params.append(s)
        if (ty := args.get("ticket_type")):
            where.append("t.type = ?"); params.append(ty)

        limit = min(int(args.get("limit") or 10), 25)
        rows = conn.execute(f"""
            SELECT t.*, e.name AS submitter_name, ea.name AS assignee_name,
                   a.asset_tag, gr.request_number AS gpu_request_number
            FROM tickets t
            JOIN employees e ON t.submitted_by = e.id
            LEFT JOIN employees ea ON t.assigned_to = ea.id
            LEFT JOIN assets a ON t.asset_id = a.id
            LEFT JOIN gpu_requests gr ON t.gpu_request_id = gr.id
            WHERE {' AND '.join(where)}
            ORDER BY t.created_at DESC LIMIT ?
        """, params + [limit]).fetchall()
        return {"count": len(rows), "tickets": [_ticket_row(r) for r in rows]}


def get_ticket(args: dict, user: dict) -> dict:
    number = (args.get("ticket_number") or "").strip()
    if not number:
        return {"error": "ticket_number is required"}
    with get_db() as conn:
        row = conn.execute("""
            SELECT t.*, e.name AS submitter_name, ea.name AS assignee_name,
                   a.asset_tag, em.name AS equipment_name,
                   ic.name AS category_name,
                   gr.request_number AS gpu_request_number,
                   gr.title AS gpu_request_title
            FROM tickets t
            JOIN employees e ON t.submitted_by = e.id
            LEFT JOIN employees ea ON t.assigned_to = ea.id
            LEFT JOIN assets a ON t.asset_id = a.id
            LEFT JOIN equipment_models em ON a.equipment_model_id = em.id
            LEFT JOIN issue_categories ic ON t.issue_category_id = ic.id
            LEFT JOIN gpu_requests gr ON t.gpu_request_id = gr.id
            WHERE t.ticket_number = ?
        """, (number,)).fetchone()
        if not row:
            return {"error": f"no ticket found with number {number}"}
        # Non-reviewer employees only see their own tickets via this tool.
        if user["role"] not in REVIEWER_ROLES and row["submitted_by"] != user["id"]:
            return {"error": f"you don't have access to {number}"}
        n_comments = conn.execute(
            "SELECT count(*) FROM ticket_comments WHERE ticket_id = ?",
            (row["id"],)
        ).fetchone()[0]
        out = _ticket_row(row)
        out.update({
            "description":      row["description"],
            "resolution":       row["resolution"],
            "category":         row["category_name"],
            "affected_user":    row["affected_user_name"],
            "comments_count":   n_comments,
            "gpu_request_title": row["gpu_request_title"],
            "resolved_at":      row["resolved_at"],
        })
        return out


def find_gpu_requests(args: dict, user: dict) -> dict:
    with get_db() as conn:
        where, params = ["1=1"], []
        if (k := args.get("kind")):
            where.append("request_kind = ?"); params.append(k)
        status = args.get("status") or "open"
        if status == "open":
            where.append("decided_at IS NULL")
        elif status == "decided":
            where.append("decided_at IS NOT NULL")
        if (s := args.get("source")):
            where.append("source = ?"); params.append(s)
        if (args.get("scope") or "all") == "mine":
            where.append("requester_id = ?"); params.append(user["id"])

        limit = min(int(args.get("limit") or 10), 25)
        rows = conn.execute(f"""
            SELECT r.request_number, r.title, r.request_kind, r.use_case,
                   r.requester_org, r.source, r.agent_confidence,
                   r.requested_hours, r.duration_text, r.existing_resource_ref,
                   r.decided_at, r.decision, r.created_at,
                   e.name AS requester_name_resolved
            FROM gpu_requests r
            LEFT JOIN employees e ON r.requester_id = e.id
            WHERE {' AND '.join(where)}
            ORDER BY (r.decided_at IS NOT NULL), r.created_at DESC
            LIMIT ?
        """, params + [limit]).fetchall()
        return {
            "count": len(rows),
            "requests": [{
                "request_number": r["request_number"],
                "kind":           r["request_kind"],
                "title":          r["title"],
                "use_case":       r["use_case"],
                "requester":      r["requester_org"] or r["requester_name_resolved"],
                "source":         r["source"],
                "agent_confidence": r["agent_confidence"],
                "requested_hours": r["requested_hours"],
                "duration":       r["duration_text"],
                "existing_resource": r["existing_resource_ref"],
                "status":         "decided" if r["decided_at"] else "open",
                "decision":       r["decision"],
                "created_at":     (r["created_at"][:16] if r["created_at"] else None),
            } for r in rows],
        }


def get_gpu_request(args: dict, user: dict) -> dict:
    number = (args.get("request_number") or "").strip()
    if not number:
        return {"error": "request_number is required"}
    with get_db() as conn:
        req = conn.execute("""
            SELECT r.*, e.name AS requester_name_resolved
            FROM gpu_requests r
            LEFT JOIN employees e ON r.requester_id = e.id
            WHERE r.request_number = ?
        """, (number,)).fetchone()
        if not req:
            return {"error": f"no request found with number {number}"}
        rid = req["id"]
        models = [dict(r) for r in conn.execute(
            "SELECT use_case_label, model_name, vram_gb, gpu_count, gpu_count_max, "
            " host_vcpu, host_ram_gb, host_disk_gb, host_os "
            "FROM gpu_request_models WHERE request_id=? ORDER BY sort_order", (rid,))]
        groups = []
        for g in conn.execute("SELECT * FROM gpu_request_vm_groups WHERE request_id=? ORDER BY sort_order", (rid,)):
            roles = [dict(r) for r in conn.execute(
                "SELECT role_name, vm_count, vcpu_per_vm, ram_gb_per_vm, disk_gb_per_vm, disk_type, os, notes "
                "FROM gpu_request_vm_roles WHERE group_id=? ORDER BY sort_order", (g["id"],))]
            groups.append({"name": g["name"], "summary": g["summary"], "notes": g["notes"], "roles": roles})
        workloads = [dict(r) for r in conn.execute(
            "SELECT name, config, estimated_hours, estimated_hours_max "
            "FROM gpu_request_workloads WHERE request_id=? ORDER BY sort_order", (rid,))]
        phases = [dict(r) for r in conn.execute(
            "SELECT name, target_date, description FROM gpu_request_phases WHERE request_id=? ORDER BY sort_order", (rid,))]
        contributions = [dict(r) for r in conn.execute(
            "SELECT name, description, benefit FROM gpu_request_contributions WHERE request_id=? ORDER BY sort_order", (rid,))]
        fields = {}
        for r in conn.execute(
            "SELECT section, key, value FROM gpu_request_fields WHERE request_id=?", (rid,)
        ):
            fields.setdefault(r["section"], {})[r["key"]] = r["value"]
        related_tickets = [dict(r) for r in conn.execute(
            "SELECT ticket_number, title, status, priority "
            "FROM tickets WHERE gpu_request_id = ? ORDER BY created_at DESC LIMIT 10", (rid,))]
        return {
            "request_number":     req["request_number"],
            "kind":               req["request_kind"],
            "title":              req["title"],
            "use_case":           req["use_case"],
            "requester":          req["requester_org"] or req["requester_name_resolved"],
            "source":             req["source"],
            "agent_confidence":   req["agent_confidence"],
            "status":             "decided" if req["decided_at"] else "open",
            "decision":           req["decision"],
            "requested_hours":    req["requested_hours"],
            "duration":           req["duration_text"],
            "existing_resource":  req["existing_resource_ref"],
            "vm_groups":          groups,
            "gpu_options":        models,
            "workloads":          workloads,
            "phases":             phases,
            "contributions":      contributions,
            "fields":             fields,
            "related_tickets":    related_tickets,
        }


def find_assets(args: dict, user: dict) -> dict:
    with get_db() as conn:
        where, params = ["1=1"], []
        if (q := (args.get("query") or "").strip()):
            where.append(
                "(a.asset_tag LIKE ? OR a.serial_number LIKE ? OR a.holder_name LIKE ? "
                " OR em.name LIKE ? OR em.brand LIKE ? OR l.code LIKE ?)")
            params += [f"%{q}%"] * 6
        if (s := args.get("status")):
            where.append("a.status = ?"); params.append(s)
        limit = min(int(args.get("limit") or 10), 25)
        rows = conn.execute(f"""
            SELECT a.asset_tag, a.serial_number, a.condition, a.status,
                   em.name AS model_name, em.brand,
                   l.code  AS location_code,
                   e.name  AS assigned_to_name,
                   a.holder_name
            FROM assets a
            JOIN equipment_models em ON a.equipment_model_id = em.id
            LEFT JOIN locations l ON a.location_id = l.id
            LEFT JOIN employees e ON a.assigned_to = e.id
            WHERE {' AND '.join(where)}
            ORDER BY a.asset_tag LIMIT ?
        """, params + [limit]).fetchall()
        return {"count": len(rows), "assets": [dict(r) for r in rows]}


def list_issue_categories(args: dict, user: dict) -> dict:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT name FROM issue_categories WHERE is_active = 1 ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return {"categories": [r["name"] for r in rows]}


TOOLS: dict[str, Any] = {
    "find_tickets":          find_tickets,
    "get_ticket":            get_ticket,
    "find_gpu_requests":     find_gpu_requests,
    "get_gpu_request":       get_gpu_request,
    "find_assets":           find_assets,
    "list_issue_categories": list_issue_categories,
}


def execute_tool(name: str, raw_args: Any, user: dict) -> str:
    """Run a tool by name. Returns a JSON-encoded string for the model
    to consume as a `tool` message. Catches errors so a bad tool call
    doesn't crash the whole chat turn."""
    fn = TOOLS.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool: {name}"})
    # Ollama may pass args as a string OR an object. Normalise.
    if isinstance(raw_args, str):
        try:
            args = json.loads(raw_args) if raw_args.strip() else {}
        except json.JSONDecodeError:
            return json.dumps({"error": f"args were not valid JSON: {raw_args!r}"})
    elif isinstance(raw_args, dict):
        args = raw_args
    else:
        args = {}
    try:
        result = fn(args, user)
    except Exception as e:
        return json.dumps({"error": f"tool {name} failed: {e}"})
    return json.dumps(result, default=str)
