# SAIL Helper — skills

This folder holds task-specific playbooks the agent can pick up. Each
`*.md` file in here is appended to the system prompt at request time,
under a `## Skills available` heading.

```
agents/
├── sail_helper.md          ← identity + schema + answer rules
└── skills/
    ├── README.md           ← this file
    ├── raise-ticket.md     ← one skill, one file
    └── ...                 ← drop new skill files here, no code changes needed
```

The runtime (`routes/assistant.py`) globs `agents/skills/*.md` on every
chat message — adding, editing, or removing a file takes effect on the
next message with no restart (same hot-reload contract as the main
agent file).

## What goes in a skill

A skill is a **procedure**, not an identity. It tells the model "when
the user asks for X, walk them through Y". It does **not** redefine
the agent's persona or the read-only contract — those stay anchored in
`sail_helper.md`.

Recommended format:

````markdown
---
title: Raise a ticket
use_when: User wants to file a maintenance, move, or incident ticket
---

## Steps

1. Ask which type fits: maintenance / move / new_request / incident /
   decommission / other.
2. Call `list_issue_categories()` and quote a real category name so the
   user picks one that exists.
3. Tell them to open `/tickets/new?type=<chosen>` and which fields to
   fill in (title, description, priority, affected user email if any).
4. If the issue is tied to a GPU request, point them to the
   "Raise maintenance ticket" button on the request detail page
   (`/gpu/requests/<NUM>`) instead — that pre-links the FK.

## Don'ts

- Don't claim you raised the ticket; you can't write.
- Don't invent a category name — always pull one via the tool.
````

Frontmatter is optional but useful for human readers / future
filtering. The runtime currently uses the whole file as-is.

## What does NOT go in a skill

- **Identity** (you are SAIL Helper) — that's in `sail_helper.md`.
- **Schema knowledge** (tables, request kinds, role hierarchy) — same.
- **Tool implementations** — tools live in
  `routes/assistant_tools.py` because each one is a real Python
  function. A skill can *reference* a tool by name (e.g. "call
  `list_issue_categories()`") but the tool's existence is established
  in Python.
- **Read-only enforcement** — the runtime never sends write tools to
  the model, so a skill can't accidentally grant write capability.

## Skills vs Claude Code skills

A separate thing entirely. The "skills" listed in the user's Claude
Code session (e.g. `ruflo-core:witness`, `verify`, `code-review`) live
on the developer's local machine and never reach the SAIL Ollama
host. The skills here are SAIL Helper's task playbooks, scoped to
this app.

## How to add a new skill

1. Create `agents/skills/<short-kebab-name>.md`.
2. Start with a one-line `use_when:` so the model knows when to apply it.
3. Number the steps so the model follows them in order.
4. List don'ts to prevent obvious failure modes.
5. Save the file. Next chat message picks it up.

## How to disable a skill temporarily

Either:
- Rename the file to `*.md.off` (the glob ignores it).
- Or move it to `agents/skills/_disabled/`.
- Or set `SAIL_AGENT_HOTRELOAD=0` if you're mid-edit and don't want
  half-written content sent to the model.
