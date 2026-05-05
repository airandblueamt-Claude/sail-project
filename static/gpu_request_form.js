/* Builder controls for the GPU allocation request form.
 *
 * The form starts nearly empty. Clicking "+ Add models requested" /
 * "+ Add a workload" / etc. reveals the corresponding block container and
 * appends a row built from a hidden <template>. Each row has a "-" button
 * that removes it. Each block container has its own "+ Add row" button so
 * multiple rows can be added without re-clicking the top-level + button.
 *
 * Field naming uses indexed bracket syntax — e.g. workloads[2][name] —
 * which the server's _parse_blocks() in routes/gpu.py picks up.
 *
 * Uses only safe DOM APIs: textContent, appendChild, cloneNode(true),
 * removeChild, querySelector. No innerHTML.
 */
(function () {
    /* Per-block row counter so newly added rows get unique indices. The
     * counter never decreases when rows are removed (gaps are fine; the
     * server tolerates non-contiguous indices). On first call we seed each
     * counter from the highest existing index so server-rendered rows
     * (after a validation re-render) keep working. */
    const counters = {};
    document.querySelectorAll('[data-block-container]').forEach(container => {
        const block = container.getAttribute('data-block-container');
        const indices = Array.from(
            container.querySelectorAll('[data-row-index]')
        ).map(el => parseInt(el.getAttribute('data-row-index'), 10));
        counters[block] = indices.length ? Math.max(...indices) + 1 : 0;
    });

    function rewriteIndices(row, block, idx) {
        // For every input/select/textarea inside the row, replace 'block[__INDEX__]'
        // in its name with the real index.
        row.querySelectorAll('[name]').forEach(input => {
            const old = input.getAttribute('name');
            if (old) {
                input.setAttribute(
                    'name', old.replace('__INDEX__', String(idx)));
            }
        });
        row.setAttribute('data-row-index', String(idx));
    }

    function addRow(block) {
        const tpl = document.querySelector(`template[data-row-template="${block}"]`);
        const container = document.querySelector(`[data-block-container="${block}"]`);
        if (!tpl || !container) return;
        const idx = counters[block] || 0;
        counters[block] = idx + 1;
        const fragment = tpl.content.cloneNode(true);
        const row = fragment.querySelector('[data-row]');
        if (row) {
            rewriteIndices(row, block, idx);
        }
        const rowsHost = container.querySelector('[data-rows]') || container;
        rowsHost.appendChild(fragment);
    }

    function showBlock(block) {
        const container = document.querySelector(`[data-block-container="${block}"]`);
        if (!container) return;
        if (container.hasAttribute('hidden')) {
            container.removeAttribute('hidden');
        }
    }

    function hideBlock(block) {
        const container = document.querySelector(`[data-block-container="${block}"]`);
        if (!container) return;
        // Clear all rows and hide.
        const rowsHost = container.querySelector('[data-rows]') || container;
        const rows = rowsHost.querySelectorAll('[data-row]');
        rows.forEach(r => rowsHost.removeChild(r));
        container.setAttribute('hidden', '');
        // Reset counter so re-adding starts at 0.
        counters[block] = 0;
    }

    document.addEventListener('click', (e) => {
        const target = e.target;
        if (!(target instanceof Element)) return;

        // "+ Add a <block>" — top-level button. Reveal the block, and if it
        // has no rows yet, add the first one.
        const addBlockBtn = target.closest('[data-add-block]');
        if (addBlockBtn) {
            e.preventDefault();
            const block = addBlockBtn.getAttribute('data-add-block');
            showBlock(block);
            const container = document.querySelector(`[data-block-container="${block}"]`);
            if (container) {
                const rowsHost = container.querySelector('[data-rows]') || container;
                const hasRow = rowsHost.querySelector('[data-row]');
                if (!hasRow && block !== 'notes') {
                    addRow(block);
                }
            }
            return;
        }

        // "+ Add row" inside a block container.
        const addRowBtn = target.closest('[data-add-row]');
        if (addRowBtn) {
            e.preventDefault();
            const block = addRowBtn.getAttribute('data-add-row');
            addRow(block);
            return;
        }

        // "-" on a single row.
        const removeRowBtn = target.closest('[data-remove-row]');
        if (removeRowBtn) {
            e.preventDefault();
            const row = removeRowBtn.closest('[data-row]');
            if (row && row.parentNode) {
                row.parentNode.removeChild(row);
            }
            return;
        }

        // "- remove section" on a block header.
        const removeBlockBtn = target.closest('[data-remove-block]');
        if (removeBlockBtn) {
            e.preventDefault();
            const block = removeBlockBtn.getAttribute('data-remove-block');
            hideBlock(block);
            return;
        }
    });
})();
