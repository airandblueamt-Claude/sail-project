"""
SAIL Helper diagnostic — answers the question 'why isn't the agent
answering?' by testing each link in the chain independently.

    .venv/bin/python scripts/assistant_diag.py

Checks:
  1. Can we reach the Ollama host at all?
  2. Does the configured model exist there?
  3. Does plain chat (no tools) come back?
  4. When we send tool definitions, does the model return tool_calls,
     or does it ignore them and reply in prose? (This is the most
     common failure: a model that hasn't been fine-tuned for OpenAI-
     style function calling.)
  5. Round-trip through Flask's /assistant/chat with a real user
     session.

For each step, prints either OK + a short snippet of what was returned,
or FAIL + the underlying error and what to do about it.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

OLLAMA_URL   = os.environ.get('SAIL_OLLAMA_URL', 'http://10.20.6.61:11434/api/chat')
OLLAMA_MODEL = os.environ.get('SAIL_OLLAMA_MODEL', 'nemotron3:33b-q8')
OLLAMA_BASE  = OLLAMA_URL.split('/api/', 1)[0]


def step(n: int, label: str) -> None:
    print(f"\n— Step {n}: {label} " + "─" * max(2, 70 - len(label)))


def ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def fail(msg: str, hint: str = "") -> None:
    print(f"  ✗ {msg}")
    if hint:
        print(f"    HINT: {hint}")


# ── 1. Host reachable? ─────────────────────────────────────────────────────
step(1, f"Ollama host reachable ({OLLAMA_BASE})")
try:
    r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
    r.raise_for_status()
    models = [m['name'] for m in r.json().get('models', [])]
    ok(f"reached {OLLAMA_BASE}; {len(models)} models installed")
except requests.exceptions.ConnectionError as e:
    fail("connection refused / no route to host",
         f"Verify {OLLAMA_BASE} is up and reachable from this machine. "
         f"From the SAIL host: `curl {OLLAMA_BASE}/api/tags`")
    sys.exit(1)
except requests.exceptions.Timeout:
    fail("timed out (>5s)",
         "Network path is slow; if this works in a browser the SAIL backend may need a higher timeout")
    sys.exit(1)
except Exception as e:
    fail(f"{type(e).__name__}: {e}")
    sys.exit(1)


# ── 2. Model installed? ────────────────────────────────────────────────────
step(2, f"Model '{OLLAMA_MODEL}' is installed")
if OLLAMA_MODEL in models:
    ok("present in /api/tags")
else:
    # Loose match for versioned tags
    matches = [m for m in models if OLLAMA_MODEL.split(':')[0] in m]
    if matches:
        fail(f"exact tag not found; close matches: {matches}",
             f"set SAIL_OLLAMA_MODEL to one of: {', '.join(matches)}")
    else:
        fail(f"model not installed",
             f"On the Ollama host run:  ollama pull {OLLAMA_MODEL}")
    print("\nAll installed models:")
    for m in models:
        print(f"    - {m}")


# ── 3. Plain chat round-trip (no tools) ────────────────────────────────────
step(3, "Plain chat (no tools)")
try:
    r = requests.post(OLLAMA_URL, json={
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": "Reply with the word: alive"}],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 16},
    }, timeout=180)
    r.raise_for_status()
    body = r.json()
    content = (body.get('message') or {}).get('content', '').strip()
    if content:
        ok(f"got reply ({len(content)} chars): {content[:60]!r}")
    else:
        fail("empty response from model", "Try a smaller model or restart Ollama")
except Exception as e:
    fail(f"{type(e).__name__}: {e}")
    sys.exit(1)


# ── 4. Tool-call support test ──────────────────────────────────────────────
step(4, "Native tool-calling support")
tool_spec = [{
    "type": "function",
    "function": {
        "name": "list_tickets",
        "description": "Get the user's open tickets.",
        "parameters": {"type": "object", "properties": {}},
    },
}]
try:
    r = requests.post(OLLAMA_URL, json={
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content":
                "You have a tool `list_tickets()`. ALWAYS call it before answering."},
            {"role": "user", "content": "What tickets do I have open?"},
        ],
        "tools": tool_spec,
        "stream": False,
        "options": {"temperature": 0},
    }, timeout=180)
    r.raise_for_status()
    body = r.json()
    msg = body.get('message') or {}
    tool_calls = msg.get('tool_calls') or []
    if tool_calls:
        ok(f"model returned tool_calls (good!): {[tc['function']['name'] for tc in tool_calls]}")
    else:
        fail("model did NOT return tool_calls; it replied with prose instead",
             "This model isn't fine-tuned for OpenAI-style function calling. "
             "Options:\n"
             "      a) Try a tool-native model:  ollama pull qwen2.5:7b\n"
             "         then:  SAIL_OLLAMA_MODEL=qwen2.5:7b python app.py\n"
             "      b) Other known-good tags:  llama3.1:8b, mistral-nemo:12b, hermes3:8b\n"
             "      c) Ask Claude to add a ReAct text-parsing fallback to assistant.py\n"
             "         so non-native models can still trigger tools.")
        print(f"\n    What the model actually said: {msg.get('content','')[:200]!r}")
except Exception as e:
    fail(f"{type(e).__name__}: {e}")


# ── 5. Round-trip through the Flask /assistant/chat endpoint ──────────────
step(5, "End-to-end through Flask /assistant/chat")
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location('app_mod', str(REPO_ROOT / 'app.py'))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    app = mod.create_app(); app.config['TESTING'] = True
    with app.test_client() as cli:
        # Use the seeded admin from init_db.py
        login = cli.post('/login',
                         data={'email': 'airandblueamt@gmail.com', 'password': 'Aramco@123'},
                         follow_redirects=False)
        if login.status_code != 302:
            fail(f"could not log in test admin (HTTP {login.status_code})")
            sys.exit(1)
        r = cli.post('/assistant/chat',
                     json={'message': 'what open tickets do I have?', 'history': []})
        if r.status_code == 200:
            body = r.get_json()
            reply = (body.get('reply') or '')[:160]
            tool_calls = body.get('tool_calls') or []
            ok(f"HTTP 200; reply (first 160 chars): {reply!r}")
            if tool_calls:
                ok(f"tools fired: {[tc['tool'] for tc in tool_calls]}")
            else:
                print("    no tool calls in the trace — likely the same issue as step 4")
        elif r.status_code in (502, 503, 504):
            fail(f"HTTP {r.status_code} {r.get_json().get('error')}",
                 f"Upstream Ollama failed. Check step 1-3 above.")
        else:
            fail(f"HTTP {r.status_code}: {r.data[:200]!r}")
except Exception as e:
    fail(f"{type(e).__name__}: {e}")

print("\nDone.\n")
