"""
SAIL Helper — read-only Q&A assistant backed by Ollama.

Sidebar chat widget (see static/assistant_widget.js). When the user asks
a question, the server builds a system prompt with:

  - A short schema overview so the model knows what SAIL tracks.
  - The user's role + email so answers can be personalised.
  - A live snapshot of high-signal data: counts, the user's own open
    tickets, recent GPU requests.

It then calls the configured Ollama endpoint with the conversation and
returns the reply. Read-only by design — the assistant cannot mutate
anything; the chat endpoint does no INSERT/UPDATE/DELETE.

If Ollama is unreachable or the request times out, we return a friendly
fallback so the widget can show 'service is offline' instead of crashing.

Phase 6 (ADR-equivalent): read-only Q&A only. A future phase can extend
this to a draft mode (LLM proposes a request/ticket) once we add a write
scope on /api/v1.
"""
from __future__ import annotations

import json
import os

import requests
from flask import Blueprint, jsonify, request, g

from database import get_db

assistant_bp = Blueprint('assistant', __name__)

OLLAMA_URL = os.environ.get(
    'SAIL_OLLAMA_URL',
    'http://10.20.6.61:11434/api/chat',
)
OLLAMA_MODEL = os.environ.get('SAIL_OLLAMA_MODEL', 'nemotron3:33b-q8')
REQUEST_TIMEOUT_S = int(os.environ.get('SAIL_OLLAMA_TIMEOUT', '60'))

# Cap on user message length — long messages waste context window and
# usually mean the user pasted something they shouldn't have.
MAX_USER_MESSAGE = 2000
# Cap on history — keep the last N turns so context stays bounded.
MAX_HISTORY_TURNS = 8


SCHEMA_PRIMER = """\
SAIL (Smart Asset Inventory & Logistics) is AMT's IT asset and ticketing app.

Core tables and how they fit together:
  - equipment_models : product lines (e.g. "30 Lenovo Workstations")
  - assets           : individual physical units, tagged SAIL-NNNNN
  - tickets          : maintenance / move / incident / decommission /
                       new_request, numbered TKT-NNNN. Tickets can
                       reference an asset_id and/or a gpu_request_id.
  - gpu_assets       : the GPU / BYOC infrastructure (hosts + cards)
  - gpu_requests     : GPU/BYOC request drafts and decisions, numbered
                       GPU-YYYY-NNNN. Has a request_kind:
                         new_infra            (BYOC VM brief)
                         gpu_allocation       (short list of GPU models)
                         compute_partnership  (time on existing infra
                                               + workloads + phases)
                         other
                       Source = manual | agent | imported. Agent-sourced
                       rows have an agent_confidence and raw_extraction_json.

User-facing URLs you can refer them to:
  /tickets/new           : raise a ticket (asset-tied or against a GPU request)
  /gpu/requests/new      : draft a new GPU request — pick the kind first
  /gpu/requests/<NUM>    : view / approve a specific request
  /gpu/                  : GPU inventory (hosts + accelerator cards)
  /inventory/            : the full equipment catalog
  /floor-plan/           : interactive floor plan with bookings

Roles: admin / manager / technician / employee. Reviewer-only actions
(approve/respond to requests, change ticket status) are restricted to
admin / manager / technician.
"""


def _build_user_snapshot(conn, user) -> str:
    """Pull a small, high-signal slice of live DB state for the prompt.

    Kept small on purpose — context window pressure scales with this
    string. Skip anything the user can't act on from chat (e.g. raw
    audit log entries).
    """
    parts: list[str] = []
    parts.append(f"You are talking to {user['name']} ({user['role']}) <{user['email']}>.")

    # System-wide counts
    n_assets = conn.execute("SELECT count(*) FROM assets").fetchone()[0]
    n_open_tickets = conn.execute(
        "SELECT count(*) FROM tickets WHERE status NOT IN ('resolved','closed')"
    ).fetchone()[0]
    n_open_gpu = conn.execute(
        "SELECT count(*) FROM gpu_requests WHERE decided_at IS NULL"
    ).fetchone()[0]
    n_agent_drafts = conn.execute(
        "SELECT count(*) FROM gpu_requests WHERE source='agent' AND decided_at IS NULL"
    ).fetchone()[0]
    parts.append(
        f"System totals: {n_assets} assets, {n_open_tickets} open tickets, "
        f"{n_open_gpu} open GPU requests ({n_agent_drafts} of those drafted by the AI agent)."
    )

    # The user's own open tickets
    mine = conn.execute("""
        SELECT ticket_number, title, type, priority, status, created_at
        FROM tickets
        WHERE submitted_by = ? AND status NOT IN ('resolved','closed')
        ORDER BY created_at DESC LIMIT 5
    """, (user['id'],)).fetchall()
    if mine:
        parts.append("User's open tickets (most recent first):")
        for t in mine:
            parts.append(
                f"  - {t['ticket_number']} [{t['priority']}/{t['status']}] "
                f"{t['type']} — {t['title']}"
            )

    # Tickets assigned to the user (only relevant for reviewers)
    if user['role'] in ('admin', 'manager', 'technician'):
        assigned = conn.execute("""
            SELECT ticket_number, title, status, priority
            FROM tickets
            WHERE assigned_to = ? AND status NOT IN ('resolved','closed')
            ORDER BY
                CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                              WHEN 'medium' THEN 3 ELSE 4 END,
                created_at DESC
            LIMIT 5
        """, (user['id'],)).fetchall()
        if assigned:
            parts.append("Tickets assigned to the user (highest priority first):")
            for t in assigned:
                parts.append(
                    f"  - {t['ticket_number']} [{t['priority']}/{t['status']}] — {t['title']}"
                )

    # Recent open GPU requests overall (so reviewers can ask "what's pending")
    recent_req = conn.execute("""
        SELECT request_number, request_kind, title, source, agent_confidence
        FROM gpu_requests
        WHERE decided_at IS NULL
        ORDER BY created_at DESC LIMIT 5
    """).fetchall()
    if recent_req:
        parts.append("Most recent open GPU requests:")
        for r in recent_req:
            src = r['source'] or 'manual'
            conf = f" (conf {r['agent_confidence']:.0%})" if (r['source'] == 'agent' and r['agent_confidence']) else ''
            parts.append(
                f"  - {r['request_number']} [{r['request_kind'] or '?'}/{src}{conf}] — {r['title']}"
            )

    return "\n".join(parts)


SYSTEM_PROMPT_TEMPLATE = """\
You are SAIL Helper, a concise read-only assistant inside AMT's SAIL app.

{schema}

Live snapshot (regenerated for every message):
{snapshot}

How to answer:
- Be terse. 1-3 sentences for simple questions, a short bulleted list for
  enumerations. No marketing fluff.
- If the user asks about a specific ticket / request / asset that is in
  the snapshot above, cite it by its number.
- If the user asks about something not in the snapshot ("what's the
  status of TKT-0099?"), say you can't see it from here and point them
  to the relevant URL (e.g. /tickets/<id>).
- If asked how to do something (raise a ticket, draft a GPU request),
  walk them through the right URL + the fields the form expects.
- Never claim you took an action — you are read-only. Suggest the URL
  the user should click to do it themselves.
- Do not invent ticket numbers, request numbers, or asset tags. If you
  do not know, say so.
"""


def _build_messages(history: list, user_message: str, system: str) -> list:
    """Compose the Ollama chat-format messages array."""
    msgs = [{"role": "system", "content": system}]
    for turn in history[-MAX_HISTORY_TURNS:]:
        role = turn.get('role')
        content = (turn.get('content') or '').strip()
        if role not in ('user', 'assistant') or not content:
            continue
        msgs.append({"role": role, "content": content[:MAX_USER_MESSAGE]})
    msgs.append({"role": "user", "content": user_message})
    return msgs


def _call_ollama(messages: list) -> str:
    """Hit Ollama's /api/chat endpoint and return the assistant text."""
    r = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 4096},
        },
        timeout=REQUEST_TIMEOUT_S,
    )
    r.raise_for_status()
    body = r.json()
    msg = body.get("message") or {}
    return (msg.get("content") or "").strip()


@assistant_bp.route('/chat', methods=['POST'])
def chat():
    if not g.user:
        return jsonify({"error": "not authenticated"}), 401

    data = request.get_json(silent=True) or {}
    user_message = (data.get('message') or '').strip()
    if not user_message:
        return jsonify({"error": "message is required"}), 400
    user_message = user_message[:MAX_USER_MESSAGE]
    history = data.get('history') or []
    if not isinstance(history, list):
        history = []

    with get_db() as conn:
        # Make rows act like dicts for the snapshot builder.
        snapshot = _build_user_snapshot(conn, g.user)

    system = SYSTEM_PROMPT_TEMPLATE.format(
        schema=SCHEMA_PRIMER.strip(), snapshot=snapshot
    )
    messages = _build_messages(history, user_message, system)

    try:
        reply = _call_ollama(messages)
    except requests.exceptions.ConnectionError:
        return jsonify({
            "error": "offline",
            "reply": ("The SAIL Helper is offline — the Ollama host at "
                      f"{OLLAMA_URL} isn't reachable. Try again once it's back."),
        }), 503
    except requests.exceptions.Timeout:
        return jsonify({
            "error": "timeout",
            "reply": ("The model took too long to answer (>"
                      f"{REQUEST_TIMEOUT_S}s). Your question may be too broad — try a shorter one."),
        }), 504
    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": "upstream",
            "reply": f"The model returned an error: {e}",
        }), 502

    if not reply:
        reply = "I didn't get a usable answer from the model. Try rephrasing?"

    return jsonify({"reply": reply, "model": OLLAMA_MODEL})
