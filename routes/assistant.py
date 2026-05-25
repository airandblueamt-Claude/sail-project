"""
SAIL Helper — tool-using read-only assistant backed by Ollama.

The agent is wired this way:

  1. Every turn, the server sends Ollama:
       - a small system prompt (role + schema primer + lightweight
         snapshot — see SYSTEM_PROMPT_TEMPLATE + _build_user_snapshot)
       - the full tool registry from routes/assistant_tools.py
       - the conversation history
       - the user's new message

  2. If the model decides it needs SAIL data, it returns a `tool_calls`
     entry in the response. The server executes each call against the
     DB (via routes/assistant_tools.TOOLS), appends the result as a
     `tool` message, and loops back to the model. The loop stops when
     the model returns plain text — or after MAX_TOOL_TURNS, whichever
     comes first.

  3. Read-only by design — every tool is a SELECT. There is no write
     path; the assistant cannot mutate anything. A future phase can
     add a "propose draft" mode that returns structured payloads for a
     human to approve via the existing UI.

The snapshot is now intentionally minimal (counts + user identity).
Before tools, we pre-loaded the user's tickets + recent requests so
the model could answer without DB access; now the model pulls them on
demand via find_tickets / find_gpu_requests, which scales further.

If Ollama is unreachable or times out, we return a friendly JSON
fallback so the widget can render 'service is offline' instead of
crashing.
"""
from __future__ import annotations

import json
import os

import requests
from flask import Blueprint, jsonify, request, g

from database import get_db
from routes.assistant_tools import TOOL_SPECS, execute_tool

assistant_bp = Blueprint('assistant', __name__)

OLLAMA_URL = os.environ.get(
    'SAIL_OLLAMA_URL',
    'http://10.20.6.61:11434/api/chat',
)
OLLAMA_MODEL = os.environ.get('SAIL_OLLAMA_MODEL', 'nemotron3:33b-q8')
# 33B-q8 on a typical local GPU can need 60-120s of generation time
# before the response object lands. Bump the default and let an env var
# override on faster hardware. Tool-calling adds extra round-trips, so
# this timeout is per round-trip, not per whole turn.
REQUEST_TIMEOUT_S = int(os.environ.get('SAIL_OLLAMA_TIMEOUT', '180'))

# Cap on user message length — long messages waste context window and
# usually mean the user pasted something they shouldn't have.
MAX_USER_MESSAGE = 2000
# Cap on history — keep the last N turns so context stays bounded.
MAX_HISTORY_TURNS = 8
# Cap on tool-call rounds per user message. Each round = one Ollama call +
# all tools it asked for. Prevents the model from getting stuck looping
# on the same tool.
MAX_TOOL_TURNS = 5


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
    """Lightweight orientation block — who the user is + high-level counts.

    Detail (the user's actual tickets, request contents, asset records)
    now comes from tool calls, not from pre-loading the prompt. Keeping
    the snapshot small leaves more context window for tool results.
    """
    n_open_tickets = conn.execute(
        "SELECT count(*) FROM tickets WHERE status NOT IN ('resolved','closed')"
    ).fetchone()[0]
    n_open_gpu = conn.execute(
        "SELECT count(*) FROM gpu_requests WHERE decided_at IS NULL"
    ).fetchone()[0]
    return (
        f"You are talking to {user['name']} ({user['role']}) <{user['email']}>.\n"
        f"System totals right now: {n_open_tickets} open tickets, "
        f"{n_open_gpu} open GPU requests."
    )


SYSTEM_PROMPT_TEMPLATE = """\
You are SAIL Helper, a concise read-only assistant inside AMT's SAIL app.

{schema}

{snapshot}

You have READ-ONLY tools that query SAIL's database. Call them whenever
the user asks about a specific record, count, or set of records you do
not already know. Examples:

  - "What tickets do I have open?" -> find_tickets(scope='mine', status='open')
  - "Show me the OrbitronAI request" -> find_gpu_requests(query='OrbitronAI')
    or get_gpu_request(request_number=...)
  - "Is asset SAIL-16038 still in stock?" -> find_assets(query='SAIL-16038')
  - "Is TKT-0005 still open?" -> get_ticket(ticket_number='TKT-0005')

How to answer:
- Be terse. 1-3 sentences for simple questions, a short bulleted list
  for enumerations. No marketing fluff.
- For factual questions about records, CALL A TOOL first. Don't guess.
- For procedural questions (how to raise a ticket / draft a request),
  walk the user through the right URL + the form fields. If you need
  the list of issue categories first, call list_issue_categories().
- Never claim you took an action — you are read-only. Tell the user
  the URL to click to do it themselves (e.g. /tickets/new?type=incident).
- Do not invent ticket numbers, request numbers, or asset tags. If a
  tool returns no rows or an 'error' key, say so plainly.
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


def _ollama_chat(messages: list, tools: list | None) -> dict:
    """Single round-trip to Ollama. Returns the parsed `message` object
    (including any tool_calls). Caller decides whether to execute tools
    and loop."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.2, "num_ctx": 8192},
    }
    if tools:
        payload["tools"] = tools
    r = requests.post(OLLAMA_URL, json=payload, timeout=REQUEST_TIMEOUT_S)
    r.raise_for_status()
    return (r.json().get("message") or {})


def _run_tool_loop(messages: list, user: dict) -> tuple[str, list[dict]]:
    """Send `messages` to Ollama. If the model returns tool_calls, run
    them, append the results, and ask again. Stop when the model
    returns plain text or we hit MAX_TOOL_TURNS.

    Returns (final_text, transcript) — transcript is the list of
    {tool, args, result_preview} dicts for debugging / UI display.
    """
    transcript: list[dict] = []
    for turn in range(MAX_TOOL_TURNS):
        msg = _ollama_chat(messages, tools=TOOL_SPECS)
        tool_calls = msg.get("tool_calls") or []
        content = (msg.get("content") or "").strip()
        if not tool_calls:
            # Model produced its final answer.
            return content, transcript
        # Append the assistant's tool-call message verbatim so Ollama
        # sees the call/result pair next turn.
        messages.append({
            "role": "assistant",
            "content": content,
            "tool_calls": tool_calls,
        })
        for call in tool_calls:
            fn = (call.get("function") or {})
            name = fn.get("name") or ""
            args = fn.get("arguments")
            result = execute_tool(name, args, user)
            messages.append({"role": "tool", "name": name, "content": result})
            preview = result[:300] + ("…" if len(result) > 300 else "")
            transcript.append({"tool": name, "args": args, "result": preview})
    # Last-resort fallback if the model never settles.
    return (
        "I kept looking up data but couldn't reach a final answer in the "
        "allowed number of tool calls. Try narrowing the question.",
        transcript,
    )


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
        reply, transcript = _run_tool_loop(messages, g.user)
    except requests.exceptions.ConnectionError:
        return jsonify({
            "error": "offline",
            "reply": ("The SAIL Helper is offline — the Ollama host at "
                      f"{OLLAMA_URL} isn't reachable. Try again once it's back."),
        }), 503
    except requests.exceptions.Timeout:
        return jsonify({
            "error": "timeout",
            "reply": (f"The model didn't finish in {REQUEST_TIMEOUT_S}s. "
                      "That's a normal latency ceiling for a 33B-q8 model on "
                      "shared hardware — try again, or raise SAIL_OLLAMA_TIMEOUT."),
        }), 504
    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": "upstream",
            "reply": f"The model returned an error: {e}",
        }), 502

    if not reply:
        reply = "I didn't get a usable answer from the model. Try rephrasing?"

    return jsonify({
        "reply": reply,
        "model": OLLAMA_MODEL,
        "tool_calls": transcript,   # widget can render this if it wants
    })
