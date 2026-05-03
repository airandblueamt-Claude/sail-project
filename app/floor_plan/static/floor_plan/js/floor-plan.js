const DEFAULT_ZONES = {
  'academia': {
    id: 'Z-01', name: 'Academia Solution Development',
    sub: 'Inc-1 · Long-term program', type: 'program', typeLabel: 'Program',
    capacity: '8 / 74', occupancy: 11, capSub: 'utilization · 8 of 74 seats',
    timeline: { start: '2022-11', end: '2025-12' },
    desc: 'Long-running joint program between corporate and partner universities. Focus on translating academic research into deployable solutions.',
    assets: [
      ['Open desks', '24'], ['Brainstorm pods (4-seat)', '4'],
      ['Whiteboard wall', '1'], ['Long meeting table', '1'], ['Phone booth', '2']
    ]
  },
  'ux-test-small': {
    id: 'Z-02', name: 'UX Test (Shared)',
    sub: 'Small testing room', type: 'research', typeLabel: 'Research',
    capacity: '1 + 3', occupancy: 50, capSub: 'participant + observers',
    desc: 'Compact UX testing room for quick session studies. Shared resource, bookable per slot.',
    assets: [
      ['Test workstation', '1'], ['Camera + mic', '1'],
      ['Observer chairs', '3'], ['Screen recording setup', '1']
    ]
  },
  'remote-incubation': {
    id: 'Z-03', name: 'Remote Incubation',
    sub: 'Distributed-team workspace', type: 'program', typeLabel: 'Program',
    capacity: '7 / 22', occupancy: 32, capSub: 'utilization · 7 of 22 seats',
    timeline: { start: '2023-01', end: '2025-12' },
    desc: 'Hybrid workspace for teams operating partly remote. Equipped for high-quality video calls and asynchronous collaboration.',
    assets: [
      ['Hot desks', '22'], ['Video-call booths', '4'],
      ['4K monitors', '22'], ['Acoustic panels', '12']
    ]
  },
  'east-cluster-a': {
    id: 'Z-04', name: 'East Wing — Cluster A',
    sub: 'Open office', type: 'open', typeLabel: 'Open desk',
    capacity: '12 desks', occupancy: 75, capSub: '3 rows of 4',
    desc: 'Open-plan workspace on the east wing. Standard desk pods for resident teams. Direct access to east corridor and natural light.',
    assets: [
      ['Workstations', '12'], ['Dual monitors', '24'],
      ['Locker units', '12'], ['Standing-desk converters', '3']
    ]
  },
  'metaverse-xr': {
    id: 'Z-05', name: 'Metaverse Extended Reality (XR)',
    sub: 'Immersive prototyping zone', type: 'program', typeLabel: 'Program',
    capacity: '8 / 21', occupancy: 38, capSub: 'utilization · 8 of 21 seats',
    timeline: { start: '2023-06', end: '2025-12' },
    desc: 'Dedicated XR development zone. Open volume for VR/AR play areas, motion-capture rigs, and immersive build-test cycles.',
    assets: [
      ['VR headsets (Quest/Varjo)', '12'], ['AR headsets (HoloLens)', '4'],
      ['Tracked play area', '6×4 m'], ['Mocap cameras', '8'],
      ['XR dev workstations', '16'], ['Haptic peripherals', '6']
    ]
  },
  'open-workshop': {
    id: 'Z-06', name: 'Open Workshop',
    sub: 'Prototype bay', type: 'research', typeLabel: 'Research',
    capacity: '12 stations', occupancy: 58, capSub: 'flex-use',
    desc: 'Multi-purpose prototyping floor. Movable furniture, ceiling power drops, and tool storage along the walls.',
    assets: [
      ['Workbenches', '6'], ['Mobile tool carts', '4'],
      ['3D printers', '3'], ['Soldering stations', '4'], ['Materials storage', '1 wall']
    ]
  },
  'it-infrastructure': {
    id: 'Z-07', name: 'I.T. Infrastructure',
    sub: 'Data center / server hall', type: 'infra', typeLabel: 'Infrastructure',
    capacity: '42 racks', occupancy: 88, capSub: 'mixed compute / storage',
    desc: 'Central server hall hosting compute, storage, and network gear for the entire incubation floor. Climate-controlled, badge-restricted.',
    assets: [
      ['Server racks', '42'], ['Network core switches', '4'],
      ['UPS / power distribution', '2 banks'], ['CRAC units', '3'],
      ['Fire suppression', 'FM-200']
    ]
  },
  'boardroom-1': {
    id: 'Z-08', name: 'Workshop 1',
    sub: 'West wing meeting room', type: 'meeting', typeLabel: 'Meeting',
    capacity: '8 seats', occupancy: 65, capSub: 'oval table',
    desc: 'Bookable workshop room. Used for hands-on sessions, design reviews, and small-team training.',
    assets: [
      ['Oval conference table', '1'], ['Executive chairs', '8'],
      ['Wall display (75")', '1'], ['Conference phone', '1']
    ]
  },
  'boardroom-2': {
    id: 'Z-09', name: 'Workshop 2',
    sub: 'West wing meeting room', type: 'meeting', typeLabel: 'Meeting',
    capacity: '6 seats', occupancy: 45, capSub: 'huddle format',
    desc: 'Bookable workshop room. Used for hands-on sessions, design reviews, and small-team training.',
    assets: [
      ['Round table', '1'], ['Chairs', '6'], ['Display (55")', '1'], ['Whiteboard', '1']
    ]
  },
  'conference-long': {
    id: 'Z-10', name: 'Workshop 3',
    sub: 'West wing — large meeting', type: 'meeting', typeLabel: 'Meeting',
    capacity: '14 seats', occupancy: 70, capSub: 'long table',
    desc: 'Bookable workshop room. Used for hands-on sessions, design reviews, and small-team training.',
    assets: [
      ['Long table (14-seat)', '1'], ['Mesh chairs', '14'],
      ['Dual displays (75")', '2'], ['Polycom system', '1'], ['Whiteboard wall', '1']
    ]
  },
  'west-cluster': {
    id: 'Z-11', name: 'West Cluster',
    sub: 'Open desks', type: 'open', typeLabel: 'Open desk',
    capacity: '8 desks', occupancy: 42, capSub: '2 rows × 4',
    desc: 'Quiet-side desk cluster for focused individual work. Lower foot traffic compared to the east wing.',
    assets: [
      ['Workstations', '8'], ['Dual monitors', '16'], ['Locker columns', '2']
    ]
  },
  'west-lounge': {
    id: 'Z-12', name: 'West Lounge',
    sub: 'Casual seating', type: 'support', typeLabel: 'Support',
    capacity: '~10 seats', occupancy: 25, capSub: 'informal',
    desc: 'Soft-seating lounge for informal meetings, breaks, and quick chats. Coffee bar adjacent.',
    assets: [
      ['Lounge sofas', '3'], ['Armchairs', '4'],
      ['Coffee tables', '2'], ['Wall TV', '1']
    ]
  },
  'pod-1': {
    id: 'Z-13', name: 'Collaboration Pod 1',
    sub: 'Round meeting room', type: 'meeting', typeLabel: 'Meeting',
    capacity: '8 seats', occupancy: 55, capSub: 'circular layout',
    desc: 'Round acoustic pod for small-team collaboration. Curved walls reduce echo, ideal for design discussions.',
    assets: [
      ['Round table', '1'], ['Task chairs', '8'],
      ['Display (55")', '1'], ['Whiteboard surface', '1']
    ]
  },
  'pod-2': {
    id: 'Z-14', name: 'Collaboration Pod 2',
    sub: 'Round meeting room', type: 'meeting', typeLabel: 'Meeting',
    capacity: '6 seats', occupancy: 60, capSub: 'circular layout',
    desc: 'Smaller circular pod, ideal for focused 4-6 person discussions or interview panels.',
    assets: [
      ['Round table', '1'], ['Task chairs', '6'],
      ['Display (43")', '1'], ['Wall whiteboard', '1']
    ]
  },
  'pod-3': {
    id: 'Z-15', name: 'Collaboration Pod 3',
    sub: 'Round meeting room', type: 'meeting', typeLabel: 'Meeting',
    capacity: '6 seats', occupancy: 48, capSub: 'circular layout',
    desc: 'Adjacent round pod, often paired with Pod 2 for breakout sessions during workshops.',
    assets: [
      ['Round table', '1'], ['Task chairs', '6'],
      ['Display (43")', '1'], ['Mobile whiteboard', '1']
    ]
  },
  'east-cluster-b': {
    id: 'Z-16', name: 'East Wing — Cluster B',
    sub: 'Open office', type: 'open', typeLabel: 'Open desk',
    capacity: '24 desks', occupancy: 82, capSub: '6 pods × 4',
    desc: 'Densest east-side cluster. Standard desk pods for resident program teams. Closest to IT infrastructure.',
    assets: [
      ['Workstations', '24'], ['Dual monitors', '48'], ['Locker units', '24']
    ]
  },
  'east-cluster-c': {
    id: 'Z-17', name: 'East Wing — Cluster C',
    sub: 'Open office', type: 'open', typeLabel: 'Open desk',
    capacity: '24 desks', occupancy: 78, capSub: '6 pods × 4',
    desc: 'Mid-section east cluster. Mirrors Cluster B in layout. Adjacent to the central pavilion and theater.',
    assets: [
      ['Workstations', '24'], ['Dual monitors', '48'], ['Locker units', '24']
    ]
  },
  'east-cluster-d': {
    id: 'Z-18', name: 'East Wing — Cluster D',
    sub: 'Open office', type: 'open', typeLabel: 'Open desk',
    capacity: '20 desks', occupancy: 60, capSub: '5 pods × 4',
    desc: 'Bottom east cluster. Slightly fewer desks; quieter due to position near the rear stairs and exit.',
    assets: [
      ['Workstations', '20'], ['Dual monitors', '40'], ['Locker units', '20']
    ]
  },
  'global-theater': {
    id: 'Z-19', name: 'Theater',
    sub: 'Tiered amphitheater', type: 'meeting', typeLabel: 'Meeting',
    capacity: '60 seats', occupancy: 35, capSub: 'tiered seating',
    desc: 'Centerpiece amphitheater for all-hands events, partner showcases, and demo days. Tiered arcs face a stage with media wall.',
    assets: [
      ['Tiered seats', '60'], ['Stage area', '1'], ['Media wall (LED)', '1'],
      ['Microphones', '6'], ['Sound system', '1'], ['Streaming rig', '1']
    ]
  },
  'mid-pavilion': {
    id: 'Z-20', name: 'Pavilion',
    sub: 'Flex meeting space', type: 'meeting', typeLabel: 'Meeting',
    capacity: '16 seats', occupancy: 50, capSub: 'reconfigurable',
    desc: 'Flexible meeting pavilion between the theater and IT zone. Reconfigurable for workshops, training, or partner intake.',
    assets: [
      ['Modular tables', '6'], ['Stackable chairs', '20'],
      ['Mobile displays (65")', '2'], ['Mobile whiteboards', '3']
    ]
  },
  'ux-test-zone': {
    id: 'Z-21', name: 'UX Test Zone',
    sub: 'Dedicated session room', type: 'research', typeLabel: 'Research',
    capacity: '1 participant', occupancy: 65, capSub: 'single-user',
    desc: 'Dedicated UX testing room. Eye-tracking equipment, controlled lighting, and one-way glass into the adjacent observation room.',
    assets: [
      ['Eye-tracking station', '1'], ['Test workstation', '1'],
      ['Test devices', '6'], ['Microphones', '2'], ['One-way glass', '1']
    ]
  },
  'ux-obs': {
    id: 'Z-22', name: 'UX Observation',
    sub: 'One-way observation room', type: 'research', typeLabel: 'Research',
    capacity: '4 observers', occupancy: 65, capSub: 'with notetakers',
    desc: 'Observation room paired with UX Test Zone. Real-time view through one-way glass with audio feed and screen mirror.',
    assets: [
      ['Observer chairs', '4'], ['Note-taking desk', '1'],
      ['Live screen mirror', '1'], ['Audio feed monitor', '1']
    ]
  },
  'lobby': {
    id: 'Z-23', name: 'Reception Lobby',
    sub: 'Visitor entry', type: 'support', typeLabel: 'Support',
    capacity: '~12 visitors', occupancy: 30, capSub: 'waiting area',
    desc: 'Curved reception area at the visitor entrance. Greeter station, waiting seating, and visitor sign-in tablets.',
    assets: [
      ['Reception desk', '1'], ['Sign-in tablets', '2'],
      ['Waiting seats', '12'], ['Welcome screen', '1']
    ]
  },
  'restrooms': {
    id: 'Z-24', name: 'Restrooms',
    sub: 'Male / Female / Accessible', type: 'support', typeLabel: 'Support',
    capacity: 'Standard', occupancy: 0, capSub: '3 facilities',
    desc: 'Restroom facilities serving the west and central zones. Includes an accessible single-occupancy room.',
    assets: [
      ['Male restroom', '1'], ['Female restroom', '1'], ['Accessible / family', '1']
    ]
  },
  'main-boardroom': {
    id: 'Z-25', name: 'Main Boardroom',
    sub: 'Executive boardroom', type: 'meeting', typeLabel: 'Meeting',
    capacity: '16 seats', occupancy: 80, capSub: 'long table',
    desc: 'Largest boardroom on the floor. Used for executive committee meetings, partner pitches, and high-stakes program reviews.',
    assets: [
      ['Long boardroom table', '1'], ['Executive chairs', '16'],
      ['Wall displays (85")', '2'], ['Polycom + ceiling mics', '1 system'], ['Sideboard', '1']
    ]
  },
  'corporate-innovation': {
    id: 'Z-26', name: 'Corporate Innovation Zone',
    sub: 'Partner intake', type: 'program', typeLabel: 'Program',
    capacity: 'Variable', occupancy: 55, capSub: 'rotating partners',
    desc: 'Front-facing zone for corporate partner intake. Rotating partners use this space for residencies, demos, and joint sessions.',
    assets: [
      ['Hot desks', '8'], ['Demo display walls', '2'],
      ['Touch table', '1'], ['Partner branding panels', '4']
    ]
  }
};

let ZONES = JSON.parse(JSON.stringify(DEFAULT_ZONES));
let activeKey = null;
let editMode = false;

const NOW = new Date('2026-04-30');
const MIN = new Date('2022-01');
const MAX = new Date('2026-12');

function dateToPct(d) {
  const t = new Date(d).getTime();
  return ((t - MIN.getTime()) / (MAX.getTime() - MIN.getTime())) * 100;
}

function occColor(pct) {
  if (pct < 40) return 'low';
  if (pct < 75) return 'mid';
  return 'high';
}

function occRGBA(pct, alpha) {
  if (pct < 40) return `rgba(45,138,79,${alpha})`;
  if (pct < 75) return `rgba(214,143,31,${alpha})`;
  return `rgba(200,54,45,${alpha})`;
}

const zoneEls = document.querySelectorAll('.zone');
const tooltip = document.getElementById('tooltip');

zoneEls.forEach(el => {
  const key = el.dataset.z;
  el.addEventListener('click', () => selectZone(key));
  el.addEventListener('mouseenter', e => showTooltip(e, key));
  el.addEventListener('mousemove', e => moveTooltip(e));
  el.addEventListener('mouseleave', () => hideTooltip());
});

function selectZone(key) {
  zoneEls.forEach(z => z.classList.remove('active'));
  const el = document.querySelector(`.zone[data-z="${key}"]`);
  if (el) el.classList.add('active');
  activeKey = key;
  showZone(key);
}

function showTooltip(e, key) {
  const z = ZONES[key];
  if (!z) return;
  tooltip.querySelector('.tt-name').textContent = z.name;
  tooltip.querySelector('.tt-meta').textContent =
    `${z.id} · ${z.typeLabel} · ${z.capacity}`;
  tooltip.classList.add('show');
  moveTooltip(e);
}
function moveTooltip(e) {
  const w = tooltip.offsetWidth;
  let x = e.clientX + 14;
  let y = e.clientY + 14;
  if (x + w > window.innerWidth - 8) x = e.clientX - w - 14;
  tooltip.style.left = x + 'px';
  tooltip.style.top = y + 'px';
}
function hideTooltip() { tooltip.classList.remove('show'); }

function showZone(key) {
  const z = ZONES[key];
  if (!z) return;
  document.getElementById('empty').style.display = 'none';
  document.getElementById('content').style.display = 'block';
  document.getElementById('d-tag').textContent = z.id;
  document.getElementById('d-name').textContent = z.name;
  document.getElementById('d-sub').textContent = z.sub;
  document.getElementById('d-cap').textContent = z.capacity;
  document.getElementById('d-cap-sub').textContent = z.capSub || '';
  document.getElementById('d-type').textContent = z.typeLabel;
  document.getElementById('d-desc').textContent = z.desc;

  const tlWrap = document.getElementById('d-timeline-wrap');
  if (z.timeline) {
    tlWrap.style.display = 'block';
    const startPct = dateToPct(z.timeline.start);
    const endPct = dateToPct(z.timeline.end);
    const nowPct = Math.max(0, Math.min(100, dateToPct(NOW)));
    const bar = document.getElementById('d-tl-bar');
    bar.style.left = startPct + '%';
    bar.style.width = (endPct - startPct) + '%';
    document.getElementById('d-tl-now').style.left = nowPct + '%';
    const fmt = d => new Date(d).toLocaleString('en-US', { month: 'short', year: 'numeric' });
    document.getElementById('d-tl-start').textContent = fmt(z.timeline.start);
    document.getElementById('d-tl-end').textContent = fmt(z.timeline.end);
  } else {
    tlWrap.style.display = 'none';
  }

  const occWrap = document.getElementById('d-occupancy');
  if (typeof z.occupancy === 'number') {
    occWrap.style.display = 'block';
    const fill = document.getElementById('d-occ-fill');
    fill.className = 'occupancy-fill ' + occColor(z.occupancy);
    setTimeout(() => { fill.style.width = z.occupancy + '%'; }, 30);
    document.getElementById('d-occ-pct').textContent = z.occupancy + '%';
    document.getElementById('d-occ-label').textContent = 'Occupancy (live estimate)';
  } else {
    occWrap.style.display = 'none';
  }

  renderAssets(z);

  const room = BOOKABLE.get(key);
  const headerEl = document.getElementById('d-name');
  const oldBadge = headerEl.parentElement.querySelector('.fp-bookable-badge');
  if (oldBadge) oldBadge.remove();
  if (room) {
    const badge = document.createElement('span');
    badge.className = 'fp-bookable-badge';
    badge.textContent = 'Bookable';
    headerEl.insertAdjacentElement('afterend', badge);
    renderRoomAssets(key);
    renderBookButton(key);
  } else {
    clearRoomAssets();
    clearBookButton();
  }
}

function _emptyAssetMessage(text) {
  const p = document.createElement('p');
  p.className = 'fp-asset-empty';
  p.textContent = text;
  return p;
}

async function renderRoomAssets(zoneKey) {
  const container = document.getElementById('zone-detail-extra');
  container.replaceChildren(_emptyAssetMessage('Loading assets…'));
  let list;
  try {
    const r = await fetch(`${API_BASE}/rooms/${encodeURIComponent(zoneKey)}/assets`);
    if (!r.ok) {
      container.replaceChildren(_emptyAssetMessage('No assets in this room.'));
      return;
    }
    list = await r.json();
  } catch (e) {
    container.replaceChildren(_emptyAssetMessage('Could not load assets.'));
    return;
  }
  if (!list.length) {
    container.replaceChildren(_emptyAssetMessage('No assets in this room.'));
    return;
  }
  const ul = document.createElement('ul');
  ul.className = 'fp-asset-list';
  ul.dataset.zone = zoneKey;
  list.forEach(a => {
    const li = document.createElement('li');
    li.dataset.assetId = String(a.id);

    const left = document.createElement('span');
    left.textContent = (a.model_name || '') + (a.brand ? ' ' + a.brand : '');

    const right = document.createElement('span');
    right.className = 'asset-tag';
    right.textContent = a.asset_tag || '';

    li.appendChild(left);
    li.appendChild(right);
    ul.appendChild(li);
  });
  container.replaceChildren(ul);
}

function clearRoomAssets() {
  const c = document.getElementById('zone-detail-extra');
  if (c) c.replaceChildren();
}

function renderBookButton(zoneKey) {
  const slot = document.getElementById('zone-detail-actions');
  if (!slot) return;
  slot.replaceChildren();
  const btn = document.createElement('button');
  btn.className = 'fp-book-btn';
  btn.textContent = 'Request to book';
  btn.addEventListener('click', () => openBookingModal(zoneKey));
  slot.appendChild(btn);
}

function clearBookButton() {
  const slot = document.getElementById('zone-detail-actions');
  if (slot) slot.replaceChildren();
}

function openBookingModal(zoneKey) {
  const modal = document.getElementById('fp-booking-modal');
  const form = document.getElementById('fp-booking-form');
  const checks = document.getElementById('fp-asset-checks');
  const errorBox = document.getElementById('fp-booking-error');

  form.reset();
  errorBox.hidden = true;
  errorBox.textContent = '';
  form.elements['zone_key'].value = zoneKey;

  // Default date = today, min = today
  const today = new Date().toISOString().slice(0, 10);
  form.elements['date'].value = today;
  form.elements['date'].min = today;

  // Build asset checkboxes from the panel's already-rendered list
  checks.replaceChildren();
  const ul = document.querySelector('.fp-asset-list');
  if (ul && ul.dataset.zone === zoneKey && ul.children.length) {
    Array.from(ul.querySelectorAll('li')).forEach(li => {
      const id = Number(li.dataset.assetId);
      const tagEl = li.querySelector('.asset-tag');
      const labelText = li.firstElementChild ? li.firstElementChild.textContent.trim() : '';
      const tagText = tagEl ? tagEl.textContent : '';

      const lbl = document.createElement('label');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.name = 'asset_ids';
      cb.value = String(id);
      cb.id = `fp-asset-${id}`;
      lbl.appendChild(cb);

      const text = document.createTextNode(' ' + labelText + ' ');
      lbl.appendChild(text);

      const tag = document.createElement('span');
      tag.className = 'asset-tag';
      tag.textContent = tagText;
      lbl.appendChild(tag);

      checks.appendChild(lbl);
    });
  } else {
    const p = document.createElement('p');
    p.className = 'fp-asset-empty';
    p.textContent = 'No assets in this room.';
    checks.appendChild(p);
  }

  modal.hidden = false;
}

function closeBookingModal() {
  document.getElementById('fp-booking-modal').hidden = true;
}

// Close on backdrop / [data-close] click
document.addEventListener('click', e => {
  if (e.target.closest('#fp-booking-modal [data-close]')) closeBookingModal();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeBookingModal();
});

// Submit
document.getElementById('fp-booking-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  const fd = new FormData(form);
  const errorBox = document.getElementById('fp-booking-error');
  errorBox.hidden = true;
  errorBox.textContent = '';
  const submitBtn = form.querySelector('button[type="submit"]');
  submitBtn.disabled = true;

  const payload = {
    zone_key: fd.get('zone_key'),
    date: fd.get('date'),
    start_time: fd.get('start_time'),
    end_time: fd.get('end_time'),
    attendees: Number(fd.get('attendees')),
    purpose: fd.get('purpose'),
    asset_ids: fd.getAll('asset_ids').map(Number),
  };

  try {
    const r = await fetch(`${API_BASE}/bookings`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    const body = await r.json();
    if (!r.ok) {
      errorBox.textContent = body.error || 'Booking failed.';
      errorBox.hidden = false;
      return;
    }
    closeBookingModal();
    toast(`Booking request submitted - ticket ${body.ticket_number}`);
  } catch (err) {
    errorBox.textContent = 'Network error. Please try again.';
    errorBox.hidden = false;
  } finally {
    submitBtn.disabled = false;
  }
});

function renderAssets(z) {
  const ul = document.getElementById('d-assets');
  ul.innerHTML = '';
  z.assets.forEach((pair, idx) => {
    const li = document.createElement('li');
    const [name, count] = pair;
    li.innerHTML = `
      <span class="asset-name" data-idx="${idx}" data-field="0">${name}</span>
      <span class="asset-count" data-idx="${idx}" data-field="1">${count}</span>
      <button class="del-asset" data-idx="${idx}" title="Remove">×</button>
    `;
    ul.appendChild(li);
  });
  bindEditableFields();
  document.querySelectorAll('.del-asset').forEach(b => {
    b.addEventListener('click', e => {
      const idx = parseInt(b.dataset.idx);
      ZONES[activeKey].assets.splice(idx, 1);
      renderAssets(ZONES[activeKey]);
      toast('Asset removed');
    });
  });
}

function bindEditableFields() {
  if (!editMode) return;
  document.querySelectorAll('.asset-name, .asset-count').forEach(el => {
    el.contentEditable = 'true';
    el.addEventListener('blur', () => {
      const idx = parseInt(el.dataset.idx);
      const field = parseInt(el.dataset.field);
      ZONES[activeKey].assets[idx][field] = el.textContent.trim();
      toast('Saved');
    });
  });
}

// Pills filter
document.querySelectorAll('.pill').forEach(p => {
  p.addEventListener('click', () => {
    document.querySelectorAll('.pill').forEach(x => x.classList.remove('on'));
    p.classList.add('on');
    const f = p.dataset.filter;
    zoneEls.forEach(el => {
      const z = ZONES[el.dataset.z];
      if (!z) return;
      if (f === 'all' || z.type === f) el.classList.remove('faded');
      else el.classList.add('faded');
    });
  });
});

// Search
const searchInput = document.getElementById('search');
const searchResults = document.getElementById('search-results');
searchInput.addEventListener('input', () => {
  const q = searchInput.value.trim().toLowerCase();
  if (!q) { searchResults.classList.remove('open'); return; }
  const matches = [];
  for (const [key, z] of Object.entries(ZONES)) {
    const haystack = [z.name, z.sub, z.id, z.typeLabel, z.desc, ...(z.assets.flat())].join(' ').toLowerCase();
    if (haystack.includes(q)) matches.push({ key, z });
  }
  if (!matches.length) {
    searchResults.innerHTML = '<div class="no-results">No matches</div>';
  } else {
    searchResults.innerHTML = matches.slice(0, 12).map(m => `
      <div class="search-result" data-z="${m.key}">
        <div class="search-result-name">${m.z.name}</div>
        <div class="search-result-meta">${m.z.id} · ${m.z.typeLabel} · ${m.z.capacity}</div>
      </div>
    `).join('');
    searchResults.querySelectorAll('.search-result').forEach(r => {
      r.addEventListener('click', () => {
        selectZone(r.dataset.z);
        const el = document.querySelector(`.zone[data-z="${r.dataset.z}"]`);
        if (el) {
          el.classList.add('search-hit');
          setTimeout(() => el.classList.remove('search-hit'), 3500);
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        searchInput.value = '';
        searchResults.classList.remove('open');
      });
    });
  }
  searchResults.classList.add('open');
});
document.addEventListener('click', e => {
  if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
    searchResults.classList.remove('open');
  }
});

// View toggle (heat mode)
document.querySelectorAll('.view-toggle button').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.view-toggle button').forEach(x => x.classList.remove('on'));
    b.classList.add('on');
    const v = b.dataset.view;
    const plan = document.getElementById('plan');
    if (v === 'heat') {
      plan.classList.add('heat');
      zoneEls.forEach(el => {
        const z = ZONES[el.dataset.z];
        if (z && typeof z.occupancy === 'number') {
          el.style.setProperty('--zone-heat', occRGBA(z.occupancy, 0.32));
        }
      });
      document.getElementById('legend').innerHTML = `
        <div class="legend-item"><span class="legend-swatch sw-low"></span>&lt; 40%</div>
        <div class="legend-item"><span class="legend-swatch sw-mid"></span>40 – 75%</div>
        <div class="legend-item"><span class="legend-swatch sw-high"></span>&gt; 75%</div>
      `;
    } else {
      plan.classList.remove('heat');
      zoneEls.forEach(el => el.style.removeProperty('--zone-heat'));
      document.getElementById('legend').innerHTML = `
        <div class="legend-item"><span class="legend-swatch sw-default"></span>Available</div>
        <div class="legend-item"><span class="legend-swatch sw-hover"></span>Hover</div>
        <div class="legend-item"><span class="legend-swatch sw-active"></span>Selected</div>
      `;
    }
  });
});

// Theme toggle
const themeBtn = document.getElementById('theme-toggle');
themeBtn.addEventListener('click', () => {
  const cur = document.documentElement.getAttribute('data-theme');
  document.documentElement.setAttribute('data-theme', cur === 'dark' ? 'light' : 'dark');
});

// Edit mode
const editBtn = document.getElementById('edit-toggle');
editBtn.addEventListener('click', () => {
  editMode = !editMode;
  document.body.classList.toggle('editing', editMode);
  editBtn.classList.toggle('on', editMode);

  ['d-name', 'd-desc', 'd-cap'].forEach(id => {
    const el = document.getElementById(id);
    el.contentEditable = editMode ? 'true' : 'false';
  });

  if (editMode && activeKey) bindEditableFields();
  toast(editMode ? 'Edit mode on' : 'Edit mode off');
});

['d-name', 'd-desc', 'd-cap'].forEach(id => {
  document.getElementById(id).addEventListener('blur', e => {
    if (!editMode || !activeKey) return;
    const z = ZONES[activeKey];
    const map = { 'd-name': 'name', 'd-desc': 'desc', 'd-cap': 'capacity' };
    z[map[id]] = e.target.textContent.trim();
    toast('Saved');
  });
});

// Add asset
document.getElementById('add-asset-btn').addEventListener('click', () => {
  if (!activeKey) return;
  ZONES[activeKey].assets.push(['New asset', '1']);
  renderAssets(ZONES[activeKey]);
  toast('Asset added');
});

// Export / Import
document.getElementById('export-btn').addEventListener('click', () => {
  const blob = new Blob([JSON.stringify(ZONES, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'incubation-floor-data.json';
  a.click();
  URL.revokeObjectURL(url);
  toast('Exported JSON');
});
document.getElementById('import-btn').addEventListener('click', () =>
  document.getElementById('import-file').click());
document.getElementById('import-file').addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = ev => {
    try {
      ZONES = JSON.parse(ev.target.result);
      renderDashboard();
      if (activeKey && ZONES[activeKey]) showZone(activeKey);
      toast('Imported successfully');
    } catch (err) {
      toast('Invalid JSON file');
    }
  };
  reader.readAsText(file);
});

// Toast
let toastTimer;
function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 1800);
}

// Dashboard
function renderDashboard() {
  const all = Object.values(ZONES);
  const totalZones = all.length;
  const programs = all.filter(z => z.type === 'program').length;
  const meetingRooms = all.filter(z => z.type === 'meeting').length;
  const occVals = all.map(z => typeof z.occupancy === 'number' ? z.occupancy : null).filter(v => v !== null);
  const avgOcc = occVals.length ? Math.round(occVals.reduce((a, b) => a + b, 0) / occVals.length) : 0;
  const totalDesks = all
    .filter(z => z.type === 'open')
    .reduce((sum, z) => {
      const m = (z.capacity || '').match(/\d+/);
      return sum + (m ? parseInt(m[0]) : 0);
    }, 0);

  const cards = [
    { label: 'Total zones', value: totalZones, delta: '26 distinct spaces' },
    { label: 'Active programs', value: programs, delta: '4 dated' },
    { label: 'Meeting rooms', value: meetingRooms, delta: 'Boardrooms + pods' },
    { label: 'Open desks', value: totalDesks, delta: 'East + West wings' },
    { label: 'Avg occupancy', value: avgOcc + '%', delta: 'Live estimate' }
  ];
  const dash = document.getElementById('dashboard');
  dash.innerHTML = cards.map(c => `
    <div class="stat-card">
      <div class="label">${c.label}</div>
      <div class="value">${c.value}</div>
      <div class="delta">${c.delta}</div>
    </div>
  `).join('');
  setTimeout(() => {
    document.querySelectorAll('.stat-card').forEach((card, i) => {
      setTimeout(() => card.classList.add('animated'), i * 80);
    });
  }, 100);
  document.getElementById('zone-count').textContent = totalZones + ' zones';
}

// Init
renderDashboard();

// ============================================================
// ISOMETRIC AUTHORING VIEW
// User drops pins on the SAIL image and names them.
// Pins are draggable, persistent (auto-saved to memory + JSON).
// ============================================================

let SAIL_PINS = [];
let isoActiveKey = null;
let isoNextId = 1;
let isoPlacingMode = false;

const STORAGE_KEY = 'sail-floor-pins-v1';

// API base — Flask blueprint mounts at /floor-plan, API at /floor-plan/api
const API_BASE = (window.SAIL_API_BASE || '/floor-plan/api');

// Bookable rooms (server source of truth). Populated on page load.
const BOOKABLE = new Map();   // zone_key -> {label, capacity, sail_location_id}

async function loadBookableRooms() {
  try {
    const r = await fetch(`${API_BASE}/bookable-rooms`);
    if (!r.ok) return;
    const list = await r.json();
    BOOKABLE.clear();
    list.forEach(room => BOOKABLE.set(room.zone_key, room));
    document.querySelectorAll('g.zone[data-z]').forEach(g => {
      if (BOOKABLE.has(g.dataset.z)) g.classList.add('zone--bookable');
    });
  } catch (e) {
    console.warn('bookable-rooms fetch failed', e);
  }
}

// Local mirror used as offline fallback. Server is the source of truth when reachable.
const memoryStore = {
  data: null,
  save(d) { this.data = JSON.parse(JSON.stringify(d)); },
  load() { return this.data ? JSON.parse(JSON.stringify(this.data)) : null; }
};

let _saveDebounce = null;
let _lastServerError = null;

function saveAuto() {
  // Update local mirrors immediately so the UI feels instant
  memoryStore.save(SAIL_PINS);
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(SAIL_PINS));
    }
  } catch(e) {}

  // Debounce server PUT — pin drags emit lots of mousemove updates
  clearTimeout(_saveDebounce);
  _saveDebounce = setTimeout(saveAutoToServer, 250);
}

async function saveAutoToServer() {
  try {
    const res = await fetch(`${API_BASE}/pins`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(SAIL_PINS)
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    _lastServerError = null;
  } catch(e) {
    _lastServerError = e;
    if (typeof toast === 'function') toast('Saved offline — server unreachable');
  }
}

async function loadAuto() {
  // Try server first
  try {
    const res = await fetch(`${API_BASE}/pins`, { credentials: 'same-origin' });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data)) {
        memoryStore.save(data);
        try {
          if (typeof localStorage !== 'undefined') {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
          }
        } catch(e) {}
        return data;
      }
    }
  } catch(e) {
    _lastServerError = e;
  }
  // Fallback: local mirror (localStorage > memory > [])
  try {
    if (typeof localStorage !== 'undefined') {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) return parsed;
      }
    }
  } catch(e) {}
  return memoryStore.load() || [];
}

function pinId() {
  return 'P-' + String(isoNextId++).padStart(2, '0');
}

// View switcher (plan / iso)
const viewSwitcherBtns = document.querySelectorAll('#view-switcher button');
const planView = document.querySelector('.plan-view');
const isoView = document.querySelector('.iso-view');
let currentViewMode = 'plan';

viewSwitcherBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    viewSwitcherBtns.forEach(b => b.classList.remove('on'));
    btn.classList.add('on');
    currentViewMode = btn.dataset.vsw;
    if (currentViewMode === 'plan') {
      planView.classList.add('active');
      isoView.classList.remove('active');
      if (activeKey) showZone(activeKey);
      else { document.getElementById('empty').style.display = 'block'; document.getElementById('content').style.display = 'none'; }
    } else {
      planView.classList.remove('active');
      isoView.classList.add('active');
      if (isoActiveKey) showIsoPin(isoActiveKey);
      else { document.getElementById('empty').style.display = 'block'; document.getElementById('content').style.display = 'none'; }
    }
  });
});

// === Rendering ===
const isoStage = document.getElementById('iso-stage');
const isoPinsEl = document.getElementById('iso-pins');
const isoEmptyEl = document.getElementById('iso-empty');

function renderPins() {
  isoPinsEl.innerHTML = '';
  SAIL_PINS.forEach(p => {
    const m = document.createElement('div');
    m.className = 'pin-marker';
    m.dataset.key = p.id;
    m.style.left = p.x + '%';
    m.style.top = p.y + '%';
    if (p.id === isoActiveKey) m.classList.add('active');
    m.innerHTML = `
      <div class="pin-dot"></div>
      <div class="pin-label">${escapeHtml(p.name || 'Untitled')}<span class="pin-label-id">${p.id}</span></div>
    `;
    isoPinsEl.appendChild(m);
    bindPin(m, p);
  });
  isoEmptyEl.style.display = SAIL_PINS.length === 0 ? 'flex' : 'none';
  document.getElementById('iso-pin-count').textContent =
    SAIL_PINS.length + ' pin' + (SAIL_PINS.length === 1 ? '' : 's');
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);
}

function bindPin(el, pin) {
  let dragging = false;
  let moved = false;
  let startX, startY, origX, origY;

  el.addEventListener('mousedown', e => {
    if (e.button !== 0) return;
    dragging = true;
    moved = false;
    el.classList.add('dragging');
    startX = e.clientX;
    startY = e.clientY;
    origX = pin.x;
    origY = pin.y;
    e.preventDefault();
  });

  document.addEventListener('mousemove', e => {
    if (!dragging) return;
    const rect = isoStage.getBoundingClientRect();
    const dxPct = ((e.clientX - startX) / rect.width) * 100;
    const dyPct = ((e.clientY - startY) / rect.height) * 100;
    pin.x = Math.max(0, Math.min(100, origX + dxPct));
    pin.y = Math.max(0, Math.min(100, origY + dyPct));
    el.style.left = pin.x + '%';
    el.style.top = pin.y + '%';
    if (Math.abs(dxPct) > 0.3 || Math.abs(dyPct) > 0.3) moved = true;
  });

  document.addEventListener('mouseup', e => {
    if (!dragging) return;
    dragging = false;
    el.classList.remove('dragging');
    if (moved) {
      saveAuto();
      toast('Pin moved');
    } else {
      // Treat as click to select
      selectIsoPin(pin.id);
    }
  });

  el.addEventListener('dblclick', e => {
    e.stopPropagation();
    openNamerForExisting(pin);
  });
}

function selectIsoPin(key) {
  isoActiveKey = key;
  document.querySelectorAll('.pin-marker').forEach(m => m.classList.toggle('active', m.dataset.key === key));
  showIsoPin(key);
}

// === Detail panel for iso pins ===
function showIsoPin(key) {
  const p = SAIL_PINS.find(x => x.id === key);
  if (!p) return;
  document.getElementById('empty').style.display = 'none';
  document.getElementById('content').style.display = 'block';
  document.getElementById('d-tag').textContent = p.id;
  document.getElementById('d-name').textContent = p.name || 'Untitled';
  document.getElementById('d-sub').textContent = p.sub || 'User-placed pin';
  document.getElementById('d-cap').textContent = p.capacity || '—';
  document.getElementById('d-cap-sub').textContent = p.capSub || '';
  document.getElementById('d-type').textContent = p.typeLabel || 'Custom';
  document.getElementById('d-desc').textContent = p.desc || 'Click edit mode to add a description for this zone.';
  document.getElementById('d-timeline-wrap').style.display = 'none';

  const occWrap = document.getElementById('d-occupancy');
  if (typeof p.occupancy === 'number') {
    occWrap.style.display = 'block';
    const fill = document.getElementById('d-occ-fill');
    fill.className = 'occupancy-fill ' + occColor(p.occupancy);
    setTimeout(() => { fill.style.width = p.occupancy + '%'; }, 30);
    document.getElementById('d-occ-pct').textContent = p.occupancy + '%';
    document.getElementById('d-occ-label').textContent = 'Occupancy';
  } else {
    occWrap.style.display = 'none';
  }

  // Render assets
  const ul = document.getElementById('d-assets');
  ul.innerHTML = '';
  (p.assets || []).forEach((pair, idx) => {
    const li = document.createElement('li');
    const [name, count] = pair;
    li.innerHTML = `
      <span class="asset-name" data-idx="${idx}" data-field="0">${escapeHtml(name)}</span>
      <span class="asset-count" data-idx="${idx}" data-field="1">${escapeHtml(String(count))}</span>
      <button class="del-asset" data-idx="${idx}" title="Remove">×</button>
    `;
    ul.appendChild(li);
  });

  document.getElementById('iso-active-meta').textContent = p.name || 'Untitled';
}

// === Add new pin flow ===
const addBtn = document.getElementById('iso-add-btn');
const emptyAddBtn = document.getElementById('iso-empty-add');

function startPlacingMode() {
  isoPlacingMode = true;
  isoStage.classList.add('placing');
  addBtn.classList.add('on');
  toast('Click anywhere on the image to place a pin');
}

function stopPlacingMode() {
  isoPlacingMode = false;
  isoStage.classList.remove('placing');
  addBtn.classList.remove('on');
}

addBtn.addEventListener('click', () => {
  if (isoPlacingMode) stopPlacingMode();
  else startPlacingMode();
});
emptyAddBtn.addEventListener('click', startPlacingMode);

isoStage.addEventListener('click', e => {
  if (!isoPlacingMode) return;
  // Don't fire when clicking on existing pin
  if (e.target.closest('.pin-marker')) return;
  if (e.target.closest('.pin-namer')) return;

  // Stop propagation so the document-level "click-outside-to-close" handler
  // doesn't immediately close the namer we're about to open.
  e.stopPropagation();

  const rect = isoStage.getBoundingClientRect();
  const xPct = ((e.clientX - rect.left) / rect.width) * 100;
  const yPct = ((e.clientY - rect.top) / rect.height) * 100;

  // Open inline namer
  openNamerForNew(xPct, yPct);
  stopPlacingMode();
});

// === Namer dialog ===
function openNamerForNew(xPct, yPct) {
  closeNamer();
  const dlg = document.createElement('div');
  dlg.className = 'pin-namer';
  dlg.style.left = xPct + '%';
  dlg.style.top = yPct + '%';
  dlg.innerHTML = `
    <label>Pin name</label>
    <input type="text" id="namer-input" placeholder="e.g. Aramco.ai" autocomplete="off" />
    <label style="margin-top:6px">Sub-label (optional)</label>
    <input type="text" id="namer-sub" placeholder="e.g. Flagship AI Showcase" autocomplete="off" />
    <div class="pin-namer-actions">
      <button id="namer-cancel">Cancel</button>
      <button class="primary" id="namer-save">Add pin</button>
    </div>
  `;
  isoStage.appendChild(dlg);
  setTimeout(() => document.getElementById('namer-input').focus(), 30);

  const close = () => closeNamer();
  document.getElementById('namer-cancel').addEventListener('click', close);
  document.getElementById('namer-save').addEventListener('click', () => {
    const name = document.getElementById('namer-input').value.trim() || 'Untitled';
    const sub = document.getElementById('namer-sub').value.trim();
    const id = pinId();
    SAIL_PINS.push({
      id, name, sub: sub || 'User-placed pin',
      x: xPct, y: yPct,
      type: 'custom', typeLabel: 'Custom',
      assets: []
    });
    saveAuto();
    renderPins();
    selectIsoPin(id);
    close();
    toast('Pin added');
  });

  // Submit on Enter
  document.getElementById('namer-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('namer-save').click();
    if (e.key === 'Escape') close();
  });
  document.getElementById('namer-sub').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('namer-save').click();
    if (e.key === 'Escape') close();
  });
}

function openNamerForExisting(pin) {
  closeNamer();
  const dlg = document.createElement('div');
  dlg.className = 'pin-namer';
  dlg.style.left = pin.x + '%';
  dlg.style.top = pin.y + '%';
  dlg.innerHTML = `
    <label>Edit pin name</label>
    <input type="text" id="namer-input" value="${escapeHtml(pin.name || '')}" autocomplete="off" />
    <label style="margin-top:6px">Sub-label</label>
    <input type="text" id="namer-sub" value="${escapeHtml(pin.sub || '')}" autocomplete="off" />
    <div class="pin-namer-actions">
      <button id="namer-delete" style="margin-right:auto;color:var(--accent);border-color:var(--accent)">Delete</button>
      <button id="namer-cancel">Cancel</button>
      <button class="primary" id="namer-save">Save</button>
    </div>
  `;
  isoStage.appendChild(dlg);
  setTimeout(() => document.getElementById('namer-input').focus(), 30);

  const close = () => closeNamer();
  document.getElementById('namer-cancel').addEventListener('click', close);
  document.getElementById('namer-save').addEventListener('click', () => {
    pin.name = document.getElementById('namer-input').value.trim() || 'Untitled';
    pin.sub = document.getElementById('namer-sub').value.trim() || 'User-placed pin';
    saveAuto();
    renderPins();
    selectIsoPin(pin.id);
    close();
    toast('Pin updated');
  });
  document.getElementById('namer-delete').addEventListener('click', () => {
    if (!confirm('Delete this pin?')) return;
    SAIL_PINS = SAIL_PINS.filter(p => p.id !== pin.id);
    if (isoActiveKey === pin.id) isoActiveKey = null;
    saveAuto();
    renderPins();
    document.getElementById('empty').style.display = 'block';
    document.getElementById('content').style.display = 'none';
    close();
    toast('Pin deleted');
  });

  document.getElementById('namer-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('namer-save').click();
    if (e.key === 'Escape') close();
  });
}

function closeNamer() {
  const existing = isoStage.querySelector('.pin-namer');
  if (existing) existing.remove();
}

// Close namer if clicking outside
document.addEventListener('click', e => {
  if (currentViewMode !== 'iso') return;
  if (e.target.closest('.pin-namer')) return;
  if (e.target.closest('.pin-marker')) return;
  if (e.target.closest('#iso-toolbar')) return;
  if (isoPlacingMode) return; // placing handler manages it
  closeNamer();
});

// === Clear / export / import ===
document.getElementById('iso-clear-btn').addEventListener('click', () => {
  if (!SAIL_PINS.length) { toast('Nothing to clear'); return; }
  if (!confirm(`Clear all ${SAIL_PINS.length} pins?`)) return;
  SAIL_PINS = [];
  isoActiveKey = null;
  saveAuto();
  renderPins();
  document.getElementById('empty').style.display = 'block';
  document.getElementById('content').style.display = 'none';
  toast('All pins cleared');
});

document.getElementById('iso-export-btn').addEventListener('click', () => {
  const blob = new Blob([JSON.stringify(SAIL_PINS, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'sail-pins.json';
  a.click();
  URL.revokeObjectURL(url);
  toast('Pins exported');
});

document.getElementById('iso-import-btn').addEventListener('click', () => {
  document.getElementById('iso-import-file').click();
});
document.getElementById('iso-import-file').addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = ev => {
    try {
      const parsed = JSON.parse(ev.target.result);
      if (!Array.isArray(parsed)) throw new Error('Not an array');
      SAIL_PINS = parsed;
      // Keep next-id ahead of any imported P-XX
      isoNextId = 1;
      parsed.forEach(p => {
        const m = String(p.id || '').match(/P-(\d+)/);
        if (m) isoNextId = Math.max(isoNextId, parseInt(m[1]) + 1);
      });
      saveAuto();
      renderPins();
      toast(`Imported ${parsed.length} pins`);
    } catch (err) {
      toast('Invalid pins file');
    }
  };
  reader.readAsText(file);
  e.target.value = '';
});

// === Init: load any saved pins (async — server first, local fallback) ===
(async () => {
  const loaded = await loadAuto();
  if (loaded && loaded.length) {
    SAIL_PINS = loaded;
    loaded.forEach(p => {
      const m = String(p.id || '').match(/P-(\d+)/);
      if (m) isoNextId = Math.max(isoNextId, parseInt(m[1]) + 1);
    });
  }
  renderPins();
  loadBookableRooms();
})();
