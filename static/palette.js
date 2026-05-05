/* Cmd+K command palette.
 *
 * Press Cmd+K (Mac) or Ctrl+K (Win/Linux) anywhere to open. Type to
 * filter. Up/Down to navigate, Enter to open, Esc to close. Searches
 * across pages, assets, tickets, GPU assets/requests, equipment models,
 * and employees — index is fetched once per session on first open and
 * cached in memory. Uses only safe DOM APIs (textContent, no innerHTML).
 */
(function () {
    if (window.__sailPaletteLoaded) return;
    window.__sailPaletteLoaded = true;

    let cache = null;
    let activeIndex = 0;
    let visibleResults = [];
    let overlay = null;
    let input = null;
    let resultsList = null;

    const MAX_RESULTS = 12;

    function buildOverlay() {
        if (overlay) return overlay;
        overlay = document.createElement('div');
        overlay.className = 'palette-overlay';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-label', 'Quick search');
        overlay.hidden = true;

        const modal = document.createElement('div');
        modal.className = 'palette-modal';

        const inputWrap = document.createElement('div');
        inputWrap.className = 'palette-input-wrap';
        const inputIcon = document.createElement('span');
        inputIcon.className = 'palette-input-icon';
        inputIcon.textContent = '⌕';
        input = document.createElement('input');
        input.type = 'text';
        input.className = 'palette-input';
        input.placeholder = 'Jump to anything — type a tag, ticket #, name…';
        input.setAttribute('aria-label', 'Search');
        inputWrap.appendChild(inputIcon);
        inputWrap.appendChild(input);

        resultsList = document.createElement('ul');
        resultsList.className = 'palette-results';

        const hint = document.createElement('div');
        hint.className = 'palette-hint';
        hint.textContent = '↑↓ navigate · ↵ open · Esc close';

        modal.appendChild(inputWrap);
        modal.appendChild(resultsList);
        modal.appendChild(hint);
        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        // Close on backdrop click. Don't close if click is inside the modal.
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) close();
        });
        input.addEventListener('input', () => render(input.value));
        input.addEventListener('keydown', onKey);

        return overlay;
    }

    function open() {
        buildOverlay();
        overlay.hidden = false;
        input.value = '';
        if (!cache) {
            renderEmpty('Loading…');
            fetch('/api/palette', {credentials: 'same-origin'})
                .then(r => r.json())
                .then(data => {
                    cache = data.items || [];
                    if (!overlay.hidden) render('');
                })
                .catch(() => renderEmpty('Could not load index.'));
        } else {
            render('');
        }
        // Focus after the browser paints; avoids the open animation hiccup.
        setTimeout(() => input.focus(), 0);
    }

    function close() {
        if (overlay) overlay.hidden = true;
    }

    function isOpen() {
        return overlay && !overlay.hidden;
    }

    function tokenMatch(haystack, tokens) {
        // All tokens must appear (substring, case-insensitive).
        for (const t of tokens) {
            if (!haystack.includes(t)) return false;
        }
        return true;
    }

    function score(item, query, tokens) {
        const label = item.label.toLowerCase();
        const sub = (item.subtitle || '').toLowerCase();
        const haystack = label + ' ' + sub;
        if (!tokenMatch(haystack, tokens)) return -1;
        // Prefer matches in the label, especially prefix matches.
        let s = 0;
        if (label === query) s += 1000;
        else if (label.startsWith(query)) s += 500;
        else if (label.includes(query)) s += 200;
        if (sub.startsWith(query)) s += 50;
        // Tie-break: shorter label wins.
        s -= label.length;
        return s;
    }

    function render(query) {
        if (!cache) return;
        query = (query || '').trim().toLowerCase();
        let results;
        if (!query) {
            // No query: show top pages first, then a sample of each kind.
            results = cache.slice(0, MAX_RESULTS);
        } else {
            const tokens = query.split(/\s+/).filter(Boolean);
            results = cache
                .map(item => ({item, s: score(item, query, tokens)}))
                .filter(r => r.s >= 0)
                .sort((a, b) => b.s - a.s)
                .slice(0, MAX_RESULTS)
                .map(r => r.item);
        }
        visibleResults = results;
        activeIndex = 0;
        drawResults();
    }

    function drawResults() {
        // Clear existing children.
        while (resultsList.firstChild) {
            resultsList.removeChild(resultsList.firstChild);
        }
        if (!visibleResults.length) {
            renderEmpty('No matches.');
            return;
        }
        visibleResults.forEach((item, i) => {
            const li = document.createElement('li');
            li.className = 'palette-result' + (i === activeIndex ? ' active' : '');
            li.setAttribute('role', 'option');
            li.dataset.index = String(i);

            const icon = document.createElement('i');
            icon.setAttribute('data-lucide', item.icon || 'corner-down-right');
            icon.className = 'palette-result-icon';

            const main = document.createElement('div');
            main.className = 'palette-result-main';
            const label = document.createElement('div');
            label.className = 'palette-result-label';
            label.textContent = item.label;
            main.appendChild(label);
            if (item.subtitle) {
                const sub = document.createElement('div');
                sub.className = 'palette-result-sub';
                sub.textContent = item.subtitle;
                main.appendChild(sub);
            }

            const kind = document.createElement('span');
            kind.className = 'palette-result-kind';
            kind.textContent = item.kind;

            li.appendChild(icon);
            li.appendChild(main);
            li.appendChild(kind);
            li.addEventListener('mouseenter', () => {
                activeIndex = i;
                updateActive();
            });
            li.addEventListener('click', () => go(item));
            resultsList.appendChild(li);
        });
        // Re-render lucide icons inside the list.
        if (window.lucide && window.lucide.createIcons) {
            window.lucide.createIcons();
        }
    }

    function renderEmpty(msg) {
        while (resultsList.firstChild) {
            resultsList.removeChild(resultsList.firstChild);
        }
        const li = document.createElement('li');
        li.className = 'palette-empty';
        li.textContent = msg;
        resultsList.appendChild(li);
    }

    function updateActive() {
        const items = resultsList.querySelectorAll('.palette-result');
        items.forEach((el, i) => {
            if (i === activeIndex) el.classList.add('active');
            else el.classList.remove('active');
        });
        const cur = items[activeIndex];
        if (cur) cur.scrollIntoView({block: 'nearest'});
    }

    function go(item) {
        close();
        if (item && item.url) window.location.href = item.url;
    }

    function onKey(e) {
        if (e.key === 'Escape') {
            e.preventDefault();
            close();
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (visibleResults.length) {
                activeIndex = (activeIndex + 1) % visibleResults.length;
                updateActive();
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (visibleResults.length) {
                activeIndex = (activeIndex - 1 + visibleResults.length) % visibleResults.length;
                updateActive();
            }
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (visibleResults[activeIndex]) go(visibleResults[activeIndex]);
        }
    }

    document.addEventListener('keydown', (e) => {
        const isCmdK = (e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K');
        if (isCmdK) {
            e.preventDefault();
            if (isOpen()) close();
            else open();
        } else if (e.key === 'Escape' && isOpen()) {
            // Already handled in onKey when input has focus, but covers other elements.
            close();
        }
    });
})();
