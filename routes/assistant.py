"""
SAIL Helper — tool-using read-only assistant backed by Ollama.

The agent is wired this way:

  1. Every turn, the server sends Ollama:
       - a small system prompt loaded from agents/sail_helper.md
         with the live {snapshot} placeholder substituted in
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
from pathlib import Path

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


# Where the externalised agent definition lives. The file is read on
# every request so edits land without a server restart. Setting
# SAIL_AGENT_HOTRELOAD=0 caches the file in memory for a tiny speedup
# (and to "freeze" the prompt while editing).
AGENT_PROMPT_PATH = Path(__file__).resolve().parent.parent / 'agents' / 'sail_helper.md'
_HOTRELOAD = os.environ.get('SAIL_AGENT_HOTRELOAD', '1') != '0'
_CACHED_PROMPT: str | None = None


def _load_system_prompt_template() -> str:
    """Return the markdown system-prompt template (with {snapshot}
    placeholder still in place). Re-reads from disk unless hot-reload
    is disabled."""
    global _CACHED_PROMPT
    if _HOTRELOAD or _CACHED_PROMPT is None:
        try:
            _CACHED_PROMPT = AGENT_PROMPT_PATH.read_text(encoding='utf-8')
        except FileNotFoundError:
            # If the markdown is missing, fail loud — there's no useful
            # behaviour without the agent definition.
            raise RuntimeError(
                f"Agent definition not found at {AGENT_PROMPT_PATH}. "
                "Restore agents/sail_helper.md or set a different path."
            )
    return _CACHED_PROMPT


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


# SYSTEM_PROMPT_TEMPLATE used to live here as a Python string. It moved
# to agents/sail_helper.md — see _load_system_prompt_template above.


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

    # Direct replace (not str.format) — the markdown contains literal
    # `{"error": ...}` examples that would confuse Python's brace parser.
    system = _load_system_prompt_template().replace('{snapshot}', snapshot)
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
