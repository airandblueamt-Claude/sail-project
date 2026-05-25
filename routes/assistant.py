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
import re
from pathlib import Path

import requests
from flask import Blueprint, jsonify, request, g

from database import get_db
from routes.assistant_tools import TOOL_SPECS, execute_tool


# Text-format tool-call protocol — works with any Ollama model regardless
# of whether the model was fine-tuned for OpenAI-style function calling.
# Models that DO support native tool_calls still work; we just check that
# field first and only fall back to text parsing if native is absent.
#
# The protocol is described to the model verbatim in agents/sail_helper.md.
TOOL_CALL_RE = re.compile(
    r'<tool_call>\s*(\{.*?\})\s*</tool_call>',
    re.DOTALL,
)

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
AGENT_DIR        = Path(__file__).resolve().parent.parent / 'agents'
AGENT_PROMPT_PATH = AGENT_DIR / 'sail_helper.md'
SKILLS_DIR       = AGENT_DIR / 'skills'
_HOTRELOAD = os.environ.get('SAIL_AGENT_HOTRELOAD', '1') != '0'
_CACHED_BASE: str | None = None
_CACHED_SKILLS: tuple[str, str] | None = None  # (combined_text, signature)


def _load_base_prompt() -> str:
    """Return the base agent definition (identity + schema + rules).
    Re-reads each call unless hot-reload is disabled."""
    global _CACHED_BASE
    if _HOTRELOAD or _CACHED_BASE is None:
        try:
            _CACHED_BASE = AGENT_PROMPT_PATH.read_text(encoding='utf-8')
        except FileNotFoundError:
            raise RuntimeError(
                f"Agent definition not found at {AGENT_PROMPT_PATH}. "
                "Restore agents/sail_helper.md or set a different path."
            )
    return _CACHED_BASE


def _load_skills() -> str:
    """Scan agents/skills/*.md and concatenate them under a header.

    Files starting with `_` or ending in `.md.off` are skipped — useful
    for temporarily parking a skill without deleting it. Hot-reloaded
    per request (~1ms for a handful of small files).
    """
    global _CACHED_SKILLS
    if not SKILLS_DIR.exists():
        return ""
    paths = sorted(
        p for p in SKILLS_DIR.glob('*.md')
        if p.name not in ('README.md',) and not p.name.startswith('_')
    )
    # Cheap signature so cached version invalidates on file change.
    signature = ";".join(f"{p.name}:{p.stat().st_mtime_ns}:{p.stat().st_size}" for p in paths)
    if not _HOTRELOAD and _CACHED_SKILLS and _CACHED_SKILLS[1] == signature:
        return _CACHED_SKILLS[0]

    if not paths:
        combined = ""
    else:
        chunks = ["\n\n---\n\n## Skills available\n\n"
                  "Each subsection below is a task playbook. Apply the one whose\n"
                  "`use_when:` matches the user's request; use steps verbatim.\n"]
        for p in paths:
            chunks.append(f"\n### Skill: {p.stem}\n")
            chunks.append(p.read_text(encoding='utf-8').strip())
            chunks.append("\n")
        combined = "".join(chunks)
    _CACHED_SKILLS = (combined, signature)
    return combined


def _load_system_prompt_template() -> str:
    """Compose the full system prompt template: base agent file +
    every skill file under agents/skills/. {snapshot} placeholder is
    left intact for the caller to substitute."""
    return _load_base_prompt() + _load_skills()


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


def _parse_text_tool_calls(content: str) -> list[dict]:
    """Extract <tool_call>{...}</tool_call> JSON blocks from a plain-text
    assistant reply. Returns a list shaped like Ollama's native tool_calls
    so the loop can treat both paths uniformly."""
    calls: list[dict] = []
    for m in TOOL_CALL_RE.finditer(content):
        raw = m.group(1)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        name = (payload.get("name") or "").strip()
        if not name:
            continue
        args = payload.get("arguments", payload.get("args", {}))
        calls.append({"function": {"name": name, "arguments": args}})
    return calls


def _strip_tool_calls_from_text(content: str) -> str:
    """Remove <tool_call>...</tool_call> blocks from the visible reply
    so we only show prose to the user."""
    return TOOL_CALL_RE.sub("", content).strip()


def _run_tool_loop(messages: list, user: dict) -> tuple[str, list[dict]]:
    """Send `messages` to Ollama, execute any tool calls the model
    returns (native or text-format), feed results back, repeat. Stop
    when the model returns plain text or we hit MAX_TOOL_TURNS.

    Two paths are supported in parallel so this works with any model:

      a) NATIVE — `tool_calls` field in the response. We append a
         `tool` role message with the JSON result, the OpenAI convention.

      b) TEXT — `<tool_call>{...}</tool_call>` blocks in the reply text.
         We append a `user` role message with `<tool_result>{...}`,
         which every model understands as part of the conversation.

    Returns (final_text, transcript).
    """
    transcript: list[dict] = []
    for _ in range(MAX_TOOL_TURNS):
        msg = _ollama_chat(messages, tools=TOOL_SPECS)
        native_calls = msg.get("tool_calls") or []
        content = (msg.get("content") or "").strip()

        # Native first; fall back to text parsing if absent.
        text_calls: list[dict] = []
        if not native_calls:
            text_calls = _parse_text_tool_calls(content)

        if not native_calls and not text_calls:
            # Model has nothing more to look up — this is its final answer.
            # Strip any partial / malformed tool-call markup that didn't
            # parse, so the user never sees raw protocol noise.
            return _strip_tool_calls_from_text(content), transcript

        if native_calls:
            # Replay the assistant turn with its tool_calls intact, then
            # one `tool` role message per call carrying the JSON result.
            messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": native_calls,
            })
            for call in native_calls:
                fn = (call.get("function") or {})
                name = fn.get("name") or ""
                args = fn.get("arguments")
                result = execute_tool(name, args, user)
                messages.append({"role": "tool", "name": name, "content": result})
                preview = result[:300] + ("…" if len(result) > 300 else "")
                transcript.append({"tool": name, "args": args, "result": preview})
        else:
            # Text path: replay the assistant's reply as-is (the
            # <tool_call> blocks stay so the model sees its own call),
            # then a single user message carrying every <tool_result>.
            messages.append({"role": "assistant", "content": content})
            result_blocks: list[str] = []
            for call in text_calls:
                fn = call.get("function") or {}
                name = fn.get("name") or ""
                args = fn.get("arguments")
                result = execute_tool(name, args, user)
                result_blocks.append(
                    f'<tool_result name="{name}">{result}</tool_result>'
                )
                preview = result[:300] + ("…" if len(result) > 300 else "")
                transcript.append({"tool": name, "args": args, "result": preview})
            messages.append({"role": "user", "content": "\n".join(result_blocks)})

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
