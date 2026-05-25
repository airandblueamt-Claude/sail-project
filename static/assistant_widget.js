/* SAIL Helper — floating chat widget.
 *
 * Renders a "Ask SAIL" floating button in the bottom-right corner. Click
 * to open a small chat panel that POSTs questions to /assistant/chat
 * and renders the model's reply. Read-only: the widget never asks the
 * model to perform actions, and the chat endpoint cannot mutate.
 *
 * State is in-memory only — refresh wipes history. That's by design;
 * the snapshot the server builds is recomputed every turn anyway.
 *
 * Uses only safe DOM APIs (textContent, no innerHTML).
 */
(function () {
    'use strict';

    // Don't mount on the login page — there's no user to serve.
    if (document.body && document.body.classList.contains('no-chrome')) return;
    if (window.location.pathname === '/login') return;

    const history = []; // {role:'user'|'assistant', content:string}

    // ── Root container ────────────────────────────────────────────────
    const root = document.createElement('div');
    root.id = 'sail-helper';
    document.body.appendChild(root);

    // ── Toggle button ─────────────────────────────────────────────────
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'sail-helper-toggle';
    toggle.setAttribute('aria-label', 'Open SAIL Helper');
    toggle.title = 'Ask SAIL';
    toggle.textContent = '💬 Ask SAIL';
    root.appendChild(toggle);

    // ── Panel ─────────────────────────────────────────────────────────
    const panel = document.createElement('div');
    panel.className = 'sail-helper-panel';
    panel.setAttribute('hidden', '');
    root.appendChild(panel);

    const header = document.createElement('div');
    header.className = 'sail-helper-header';
    const titleEl = document.createElement('strong');
    titleEl.textContent = 'SAIL Helper';
    const sub = document.createElement('span');
    sub.className = 'sail-helper-sub';
    sub.textContent = 'read-only · powered by Ollama';
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'sail-helper-close';
    close.textContent = '×';
    close.setAttribute('aria-label', 'Close');
    header.appendChild(titleEl);
    header.appendChild(sub);
    header.appendChild(close);
    panel.appendChild(header);

    const log = document.createElement('div');
    log.className = 'sail-helper-log';
    panel.appendChild(log);

    const form = document.createElement('form');
    form.className = 'sail-helper-form';
    const input = document.createElement('textarea');
    input.rows = 2;
    input.placeholder = 'Ask about tickets, GPU requests, or how to do something…';
    input.maxLength = 2000;
    const submit = document.createElement('button');
    submit.type = 'submit';
    submit.className = 'sail-helper-send';
    submit.textContent = 'Send';
    form.appendChild(input);
    form.appendChild(submit);
    panel.appendChild(form);

    // First-time greeting so the panel isn't blank.
    appendMessage('assistant',
        "Hi — ask me about your open tickets, recent GPU requests, or how to do something in SAIL. I can't change anything; I can only read.");

    // ── Behaviour ────────────────────────────────────────────────────
    function setOpen(open) {
        if (open) {
            panel.removeAttribute('hidden');
            toggle.setAttribute('hidden', '');
            input.focus();
        } else {
            panel.setAttribute('hidden', '');
            toggle.removeAttribute('hidden');
        }
    }

    toggle.addEventListener('click', () => setOpen(true));
    close.addEventListener('click', () => setOpen(false));

    function appendMessage(role, text) {
        const row = document.createElement('div');
        row.className = 'sail-helper-msg sail-helper-msg-' + role;
        // Multi-paragraph wrapping: split on \n\n and emit a <p> per chunk.
        // Within a chunk, single \n becomes <br>. textContent keeps it safe.
        const chunks = (text || '').split(/\n\n+/);
        chunks.forEach((chunk, i) => {
            const p = document.createElement('p');
            chunk.split('\n').forEach((line, j) => {
                if (j > 0) p.appendChild(document.createElement('br'));
                p.appendChild(document.createTextNode(line));
            });
            row.appendChild(p);
        });
        log.appendChild(row);
        log.scrollTop = log.scrollHeight;
        return row;
    }

    async function send(message) {
        appendMessage('user', message);
        history.push({ role: 'user', content: message });
        const placeholder = appendMessage('assistant', '…');
        submit.disabled = true;
        input.disabled = true;
        try {
            const r = await fetch('/assistant/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, history: history.slice(0, -1) }),
            });
            const ct = r.headers.get('content-type') || '';
            if (!ct.includes('application/json')) {
                // Most likely a session-expired HTML redirect to /login.
                placeholder.textContent = "Your session looks expired. Refresh the page and sign in again.";
                return;
            }
            const data = await r.json();
            const reply = data.reply || data.error || 'No reply.';
            placeholder.textContent = '';
            // Re-render the placeholder with the new content (preserves wrap).
            reply.split(/\n\n+/).forEach((chunk, i) => {
                const p = document.createElement('p');
                chunk.split('\n').forEach((line, j) => {
                    if (j > 0) p.appendChild(document.createElement('br'));
                    p.appendChild(document.createTextNode(line));
                });
                if (i === 0 && placeholder.firstChild) {
                    placeholder.replaceChild(p, placeholder.firstChild);
                } else {
                    placeholder.appendChild(p);
                }
            });
            if (r.ok) {
                history.push({ role: 'assistant', content: reply });
            }
        } catch (err) {
            placeholder.textContent = 'Network error: ' + err.message;
        } finally {
            submit.disabled = false;
            input.disabled = false;
            input.focus();
        }
    }

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        input.value = '';
        send(text);
    });

    // Enter sends, Shift+Enter inserts a newline.
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            form.dispatchEvent(new Event('submit', { cancelable: true }));
        }
    });
})();
