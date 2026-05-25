/* Builder controls for the GPU request form.
 *
 * The form is kind-aware: the top dropdown (data-kind-select) toggles
 * which "+ Add" buttons and kind-scoped sections are visible, but does
 * not gate which sections are submittable — already-revealed sections
 * stay in the DOM and post their data.
 *
 * Each top-level section is one of:
 *   - flat block:    [data-block-container="<name>"] with [data-rows] +
 *                    a sibling <template data-row-template="<name>">
 *   - vm_groups:     a flat block where each row is a *group*, and each
 *                    group contains [data-vm-roles] populated from
 *                    <template data-vm-role-template>
 *   - networking / access: not row-based; the block container's hide/show
 *                    just toggles the hidden attribute (data fields stay
 *                    in the DOM ready to post).
 *   - notes:         single textarea — same hide/show treatment.
 *
 * Indexed bracket form names (block[2][field], vm_groups[0][roles][3][role_name])
 * are matched by the server's _parse_blocks / _parse_vm_groups regexes.
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
        const rowsHost = container.querySelector('[data-rows]') || container;
        const indices = Array.from(
            rowsHost.querySelectorAll(':scope > [data-row-index]')
        ).map(el => parseInt(el.getAttribute('data-row-index'), 10));
        counters[block] = indices.length ? Math.max(...indices) + 1 : 0;
    });

    // Per-group role counters for vm_groups (keyed by group_idx).
    const roleCounters = new Map();
    document.querySelectorAll('[data-vm-group]').forEach(group => {
        const gIdx = parseInt(group.getAttribute('data-row-index'), 10);
        const rolesHost = group.querySelector('[data-vm-roles]');
        const indices = Array.from(
            rolesHost ? rolesHost.querySelectorAll(':scope > [data-vm-role]') : []
        ).map(el => parseInt(el.getAttribute('data-role-index'), 10));
        roleCounters.set(gIdx, indices.length ? Math.max(...indices) + 1 : 0);
    });

    function rewriteIndices(row, block, idx) {
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
            // VM-group rows ship with __INDEX__ baked into their nested role
            // template names too, but the role template is a sibling — the
            // group itself just needs the group-level rewrite. Seed the
            // role counter for this new group.
            if (block === 'vm_groups') {
                roleCounters.set(idx, 0);
            }
        }
        const rowsHost = container.querySelector('[data-rows]') || container;
        rowsHost.appendChild(fragment);
    }

    function addVmRole(groupEl) {
        const gIdx = parseInt(groupEl.getAttribute('data-row-index'), 10);
        if (Number.isNaN(gIdx)) return;
        const tpl = document.querySelector('template[data-vm-role-template]');
        const rolesHost = groupEl.querySelector('[data-vm-roles]');
        if (!tpl || !rolesHost) return;
        const rIdx = roleCounters.get(gIdx) || 0;
        roleCounters.set(gIdx, rIdx + 1);
        const fragment = tpl.content.cloneNode(true);
        const role = fragment.querySelector('[data-vm-role]');
        if (role) {
            role.querySelectorAll('[name]').forEach(input => {
                const old = input.getAttribute('name');
                if (old) {
                    input.setAttribute(
                        'name',
                        old.replace('__GINDEX__', String(gIdx))
                           .replace('__RINDEX__', String(rIdx)));
                }
            });
            role.setAttribute('data-role-index', String(rIdx));
        }
        rolesHost.appendChild(fragment);
    }

    function showBlock(block) {
        const container = document.querySelector(`[data-block-container="${block}"]`);
        if (!container) return;
        if (container.hasAttribute('hidden')) {
            container.removeAttribute('hidden');
        }
    }

    // Blocks that have no rows (notes, networking, access) just hide; we
    // don't blow away their inputs because the user might re-open the
    // section and expect their data back.
    const ROWLESS_BLOCKS = new Set(['notes', 'networking', 'access', 'relationship']);

    // For each kind, which sections to auto-reveal on first selection. The
    // user can still + Add anything else, and can remove these. Picked from
    // the dominant shape of each real sample doc — see docs/samples/.
    const KIND_AUTOEXPAND = {
        new_infra:           ['vm_groups', 'models', 'networking', 'access'],
        gpu_allocation:      ['models'],
        compute_partnership: ['models', 'workloads', 'phases', 'contributions'],
        other:               [],
    };
    // Track which kinds the user has visited so we only auto-expand the
    // first time they select each one. Otherwise re-selecting a kind they
    // already touched would resurrect sections they explicitly removed.
    const autoExpandedFor = new Set();

    function hideBlock(block) {
        const container = document.querySelector(`[data-block-container="${block}"]`);
        if (!container) return;
        if (!ROWLESS_BLOCKS.has(block)) {
            const rowsHost = container.querySelector('[data-rows]') || container;
            const rows = rowsHost.querySelectorAll(':scope > [data-row]');
            rows.forEach(r => rowsHost.removeChild(r));
            counters[block] = 0;
            if (block === 'vm_groups') {
                roleCounters.clear();
            }
        }
        container.setAttribute('hidden', '');
    }

    // ── Kind-driven visibility ────────────────────────────────────────────
    function applyKindVisibility() {
        const select = document.querySelector('[data-kind-select]');
        if (!select) return;
        const kind = select.value;
        // Show/hide kind-scoped sections + the "+ Add" buttons.
        document.querySelectorAll('[data-kinds]').forEach(el => {
            const allowed = el.getAttribute('data-kinds').split(',').map(s => s.trim());
            // Empty kind selection — show everything so a user who hasn't
            // picked yet can still see what's available.
            const visible = !kind || allowed.includes(kind);
            el.style.display = visible ? '' : 'none';
        });
    }

    function autoExpandForKind(kind) {
        if (!kind || autoExpandedFor.has(kind)) return;
        autoExpandedFor.add(kind);
        const sections = KIND_AUTOEXPAND[kind] || [];
        sections.forEach(block => {
            const container = document.querySelector(`[data-block-container="${block}"]`);
            if (!container) return;
            // Only auto-expand if the section is currently hidden and empty.
            // Don't blow away rows the user already filled in.
            if (!container.hasAttribute('hidden')) return;
            const rowsHost = container.querySelector('[data-rows]') || container;
            if (rowsHost.querySelector(':scope > [data-row]')) return;
            showBlock(block);
            if (!ROWLESS_BLOCKS.has(block)) {
                addRow(block);
                if (block === 'vm_groups') {
                    const lastGroup = rowsHost.querySelector(':scope > [data-vm-group]:last-of-type');
                    if (lastGroup) addVmRole(lastGroup);
                }
            }
        });
    }

    const kindSelect = document.querySelector('[data-kind-select]');
    if (kindSelect) {
        kindSelect.addEventListener('change', () => {
            applyKindVisibility();
            autoExpandForKind(kindSelect.value);
        });
        applyKindVisibility();
        // On first load, if a kind is already pre-selected (e.g. after a
        // failed POST), seed it as "already expanded" so we don't add empty
        // sections on top of the user's existing data.
        if (kindSelect.value) autoExpandedFor.add(kindSelect.value);
    }

    // ── Single delegated click handler ─────────────────────────────────────
    document.addEventListener('click', (e) => {
        const target = e.target;
        if (!(target instanceof Element)) return;

        // "+ Add <section>" — top-level button. Reveal the block, and if it
        // has no rows yet (and is row-based), add the first one.
        const addBlockBtn = target.closest('[data-add-block]');
        if (addBlockBtn) {
            e.preventDefault();
            const block = addBlockBtn.getAttribute('data-add-block');
            showBlock(block);
            if (!ROWLESS_BLOCKS.has(block)) {
                const container = document.querySelector(`[data-block-container="${block}"]`);
                if (container) {
                    const rowsHost = container.querySelector('[data-rows]') || container;
                    const hasRow = rowsHost.querySelector(':scope > [data-row]');
                    if (!hasRow) {
                        addRow(block);
                        // For a freshly-added vm_group, also seed one role row.
                        if (block === 'vm_groups') {
                            const lastGroup = rowsHost.querySelector(':scope > [data-vm-group]:last-of-type');
                            if (lastGroup) addVmRole(lastGroup);
                        }
                    }
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
            if (block === 'vm_groups') {
                const container = document.querySelector('[data-block-container="vm_groups"]');
                const lastGroup = container ? container.querySelector('[data-vm-group]:last-of-type') : null;
                if (lastGroup) addVmRole(lastGroup);
            }
            return;
        }

        // "+ Add role to this group" inside a vm_group row.
        const addRoleBtn = target.closest('[data-add-vm-role]');
        if (addRoleBtn) {
            e.preventDefault();
            const group = addRoleBtn.closest('[data-vm-group]');
            if (group) addVmRole(group);
            return;
        }

        // "-" on a single vm-role.
        const removeRoleBtn = target.closest('[data-remove-vm-role]');
        if (removeRoleBtn) {
            e.preventDefault();
            const role = removeRoleBtn.closest('[data-vm-role]');
            if (role && role.parentNode) role.parentNode.removeChild(role);
            return;
        }

        // "-" on a single row (flat blocks or vm_group itself).
        const removeRowBtn = target.closest('[data-remove-row]');
        if (removeRowBtn) {
            e.preventDefault();
            const row = removeRowBtn.closest('[data-row]');
            if (row && row.parentNode) row.parentNode.removeChild(row);
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
