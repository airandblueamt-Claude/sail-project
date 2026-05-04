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

  // Real inventory from sail.db (works for any zone with a location mapping;
  // shows "No inventory linked" otherwise). Replaces the old hardcoded list.
  renderRoomAssets(key);

  const room = BOOKABLE.get(key);
  const headerEl = document.getElementById('d-name');
  const oldBadge = headerEl.parentElement.querySelector('.fp-bookable-badge');
  if (oldBadge) oldBadge.remove();
  if (room) {
    const badge = document.createElement('span');
    badge.className = 'fp-bookable-badge';
    badge.textContent = 'Bookable';
    headerEl.insertAdjacentElement('afterend', badge);
    renderBookButton(key);
  } else {
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
  let body;
  try {
    const r = await fetch(`${API_BASE}/zones/${encodeURIComponent(zoneKey)}/assets`);
    if (!r.ok) {
      container.replaceChildren(_emptyAssetMessage('Could not load assets.'));
      return;
    }
    body = await r.json();
  } catch (e) {
    container.replaceChildren(_emptyAssetMessage('Could not load assets.'));
    return;
  }
  if (!body.linked) {
    container.replaceChildren(_emptyAssetMessage(
      'No inventory linked to this zone yet — admin can configure.'));
    return;
  }
  const list = body.assets || [];
  if (!list.length) {
    container.replaceChildren(_emptyAssetMessage(
      'No assets currently in this room.'));
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

// Lab hours / slot config — keep in sync with booking.py (LAB_OPEN, LAB_CLOSE, SLOT_MINUTES)
const LAB_OPEN_MIN = 7 * 60;
const LAB_CLOSE_MIN = 16 * 60;
const SLOT_MIN = 15;

function _formatSlot(min) {
  const h = String(Math.floor(min / 60)).padStart(2, '0');
  const m = String(min % 60).padStart(2, '0');
  return `${h}:${m}`;
}

function _populateTimeSlots(selectEl, min, max, defaultValue) {
  selectEl.replaceChildren();
  for (let t = min; t <= max; t += SLOT_MIN) {
    const opt = document.createElement('option');
    opt.value = _formatSlot(t);
    // 12-hour display for friendlier reading
    const h24 = Math.floor(t / 60);
    const m = t % 60;
    const ampm = h24 >= 12 ? 'PM' : 'AM';
    const h12 = h24 === 0 ? 12 : h24 > 12 ? h24 - 12 : h24;
    opt.textContent = `${h12}:${String(m).padStart(2, '0')} ${ampm}`;
    selectEl.appendChild(opt);
  }
  if (defaultValue) selectEl.value = defaultValue;
}

async function openBookingModal(zoneKey) {
  const modal = document.getElementById('fp-booking-modal');
  const form = document.getElementById('fp-booking-form');
  const checks = document.getElementById('fp-asset-checks');
  const errorBox = document.getElementById('fp-booking-error');
  const subtitleEl = document.getElementById('fp-modal-subtitle');
  const attWarn = document.getElementById('fp-attendees-warning');
  const startSel = document.getElementById('fp-start-select');
  const endSel = document.getElementById('fp-end-select');

  form.reset();
  errorBox.hidden = true;
  errorBox.textContent = '';
  form.elements['zone_key'].value = zoneKey;

  // Title + capacity subtitle from BOOKABLE map
  const room = BOOKABLE.get(zoneKey);
  if (room) {
    document.getElementById('fp-modal-title').textContent = `Book ${room.label}`;
    subtitleEl.textContent = room.capacity ? `Capacity: ${room.capacity} people` : '';
  }

  // Default date = today, min = today
  const today = new Date().toISOString().slice(0, 10);
  form.elements['date'].value = today;
  form.elements['date'].min = today;

  // Time slots: start can be 07:00..15:45, end can be 07:15..16:00 (must be > start)
  _populateTimeSlots(startSel, LAB_OPEN_MIN, LAB_CLOSE_MIN - SLOT_MIN, '09:00');
  _populateTimeSlots(endSel, LAB_OPEN_MIN + SLOT_MIN, LAB_CLOSE_MIN, '10:00');
  // Keep end > start: when start changes, restrict end to slots after the new start
  startSel.onchange = () => {
    const startMins = parseInt(startSel.value.split(':')[0]) * 60 + parseInt(startSel.value.split(':')[1]);
    Array.from(endSel.options).forEach(opt => {
      const t = parseInt(opt.value.split(':')[0]) * 60 + parseInt(opt.value.split(':')[1]);
      opt.hidden = t <= startMins;
    });
    // If currently selected end is now invalid, bump to first visible
    const curEnd = parseInt(endSel.value.split(':')[0]) * 60 + parseInt(endSel.value.split(':')[1]);
    if (curEnd <= startMins) {
      const next = Array.from(endSel.options).find(o => !o.hidden);
      if (next) endSel.value = next.value;
    }
  };
  startSel.onchange();   // sync end-options to default start

  // Attendee-vs-capacity live warning
  attWarn.hidden = true;
  form.elements['attendees'].oninput = () => {
    const n = Number(form.elements['attendees'].value);
    if (room && room.capacity && n > room.capacity) {
      attWarn.textContent = `Note: ${n} exceeds the room capacity of ${room.capacity}.`;
      attWarn.hidden = false;
    } else {
      attWarn.hidden = true;
    }
  };

  // Date-change refetch of pending count + day-schedule strip
  const refreshForDate = () => {
    const d = form.elements['date'].value;
    loadPendingCount(zoneKey, d);
    renderSchedule(zoneKey, d);
  };
  form.elements['date'].onchange = refreshForDate;
  loadPendingCount(zoneKey, today);
  renderSchedule(zoneKey, today);

  // Equipment-catalog picker — user picks model + qty; ops allocates
  // specific assets at approval time.
  await _initEquipmentPicker();

  modal.hidden = false;
}

function _slotMins(hhmm) {
  const [h, m] = hhmm.split(':').map(Number);
  return h * 60 + m;
}

async function renderSchedule(zoneKey, date) {
  const wrap = document.getElementById('fp-schedule');
  const bar = document.getElementById('fp-schedule-bar');
  const axis = document.getElementById('fp-schedule-axis');
  if (!wrap || !bar || !axis) return;

  let data;
  try {
    const r = await fetch(`${API_BASE}/rooms/${encodeURIComponent(zoneKey)}/schedule?date=${encodeURIComponent(date)}`);
    if (!r.ok) { wrap.hidden = true; return; }
    data = await r.json();
  } catch (_) {
    wrap.hidden = true;
    return;
  }
  wrap.hidden = false;

  const openMin = _slotMins(data.lab_open || '07:00');
  const closeMin = _slotMins(data.lab_close || '16:00');
  const slot = data.slot_minutes || 15;
  const totalSlots = (closeMin - openMin) / slot;

  // Build slot cells
  bar.replaceChildren();
  const startSel = document.getElementById('fp-start-select');
  for (let i = 0; i < totalSlots; i++) {
    const slotStart = openMin + i * slot;
    const slotEnd = slotStart + slot;
    const div = document.createElement('div');
    div.className = 'fp-slot';
    div.dataset.start = _formatSlot(slotStart);
    div.dataset.end = _formatSlot(slotEnd);

    // Mark busy if any booking overlaps this 15-min cell
    const busyBooking = (data.bookings || []).find(b => {
      const bs = _slotMins(b.start_time);
      const be = _slotMins(b.end_time);
      return slotStart < be && bs < slotEnd;
    });
    if (busyBooking) {
      div.classList.add('busy');
      div.title = `${busyBooking.ticket_number} · ${busyBooking.start_time}–${busyBooking.end_time}`
        + (busyBooking.submitter_name ? ` · ${busyBooking.submitter_name}` : '')
        + ` (${busyBooking.status})`;
    } else {
      div.title = `Click to start at ${_formatSlot(slotStart)}`;
      div.addEventListener('click', () => {
        // Set start_time to this slot, bump end if needed
        if (startSel) {
          startSel.value = div.dataset.start;
          if (startSel.onchange) startSel.onchange();
        }
        // Visual selection feedback
        bar.querySelectorAll('.fp-slot.selected').forEach(s => s.classList.remove('selected'));
        div.classList.add('selected');
      });
    }
    bar.appendChild(div);
  }

  // Axis labels — every hour
  axis.replaceChildren();
  for (let m = openMin; m <= closeMin; m += 60) {
    const t = document.createElement('span');
    t.textContent = _formatSlot(m);
    axis.appendChild(t);
  }
}


async function loadPendingCount(zoneKey, date) {
  const banner = document.getElementById('fp-pending-banner');
  if (!banner) return;
  try {
    const r = await fetch(`${API_BASE}/rooms/${encodeURIComponent(zoneKey)}/bookings?date=${encodeURIComponent(date)}`);
    if (!r.ok) { banner.hidden = true; return; }
    const data = await r.json();
    if (data.open_count > 0) {
      banner.textContent = `Heads-up: ${data.open_count} other booking request${data.open_count === 1 ? '' : 's'} for this room on ${date}. Ops team will sort overlaps.`;
      banner.hidden = false;
    } else {
      banner.hidden = true;
    }
  } catch (_) {
    banner.hidden = true;
  }
}

// Modal-state: equipment-catalog picker.
// _equipmentRequests: model_id -> {model_id, name, brand, total_count, quantity}
const _equipmentRequests = new Map();
let _equipmentCatalog = [];   // cached catalog list

async function _initEquipmentPicker() {
  _equipmentRequests.clear();
  _renderEquipmentList();
  _updateCartSummary();

  const sel = document.getElementById('fp-equip-select');
  const qty = document.getElementById('fp-equip-qty');
  const addBtn = document.getElementById('fp-equip-add');
  if (!sel || !qty || !addBtn) return;

  // Load catalog once per modal-open
  try {
    const r = await fetch(`${API_BASE}/equipment-catalog`);
    if (r.ok) _equipmentCatalog = await r.json();
  } catch (_) {
    _equipmentCatalog = [];
  }

  // Populate the dropdown (group by category)
  sel.replaceChildren();
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = '— pick equipment —';
  sel.appendChild(placeholder);
  const byCategory = {};
  _equipmentCatalog.forEach(m => {
    (byCategory[m.category || 'Other'] = byCategory[m.category || 'Other'] || []).push(m);
  });
  Object.keys(byCategory).sort().forEach(cat => {
    const og = document.createElement('optgroup');
    og.label = cat;
    byCategory[cat].forEach(m => {
      const opt = document.createElement('option');
      opt.value = String(m.id);
      const labelParts = [m.name];
      if (m.brand) labelParts.push(m.brand);
      labelParts.push(`(${m.total_count} in stock)`);
      opt.textContent = labelParts.join(' · ');
      og.appendChild(opt);
    });
    sel.appendChild(og);
  });

  // Reset qty
  qty.value = '1';

  // Wire add button (idempotent)
  if (!addBtn._wired) {
    addBtn._wired = true;
    addBtn.addEventListener('click', () => {
      const mid = parseInt(sel.value, 10);
      const q = parseInt(qty.value, 10);
      if (!mid || !q || q < 1) return;
      const model = _equipmentCatalog.find(m => m.id === mid);
      if (!model) return;
      const existing = _equipmentRequests.get(mid);
      const newQty = (existing ? existing.quantity : 0) + q;
      if (newQty > model.total_count) {
        alert(`Only ${model.total_count} ${model.name} in inventory total. ` +
              `Even when free, you cannot ask for more than that.`);
        return;
      }
      _equipmentRequests.set(mid, {
        model_id: mid,
        name: model.name,
        brand: model.brand,
        total_count: model.total_count,
        quantity: newQty,
      });
      _renderEquipmentList();
      _updateCartSummary();
      sel.value = '';
      qty.value = '1';
    });
  }
}

function _renderEquipmentList() {
  const ul = document.getElementById('fp-equip-list');
  if (!ul) return;
  ul.replaceChildren();
  _equipmentRequests.forEach((er, mid) => {
    const li = document.createElement('li');
    const name = document.createElement('span');
    name.className = 'equip-name';
    name.textContent = er.name + (er.brand ? ' · ' + er.brand : '');
    const q = document.createElement('span');
    q.className = 'equip-qty';
    q.textContent = `× ${er.quantity}`;
    const x = document.createElement('button');
    x.type = 'button';
    x.setAttribute('aria-label', 'Remove ' + er.name);
    x.textContent = '×';
    x.addEventListener('click', () => {
      _equipmentRequests.delete(mid);
      _renderEquipmentList();
      _updateCartSummary();
    });
    li.appendChild(name);
    li.appendChild(q);
    li.appendChild(x);
    ul.appendChild(li);
  });
}

async function _runAssetSearch(q, zoneKey) {
  const seq = ++_searchSeq;
  if (!q.trim()) {
    // Empty -> reset to room default
    let list = [];
    try {
      const r = await fetch(`${API_BASE}/zones/${encodeURIComponent(zoneKey)}/assets`);
      if (r.ok) {
        const body = await r.json();
        list = body.assets || [];
      }
    } catch (_) {}
    if (seq !== _searchSeq) return;
    _renderResults(list, list.length === 0
      ? 'No assets currently in this room — start typing to search.'
      : null);
    return;
  }
  let list = [];
  try {
    const r = await fetch(`${API_BASE}/inventory/search?q=${encodeURIComponent(q)}&limit=50`);
    if (r.ok) list = await r.json();
  } catch (_) {}
  if (seq !== _searchSeq) return;
  _renderResults(list, list.length === 0 ? 'No matches.' : null);
}

function _renderResults(list, emptyText) {
  const results = document.getElementById('fp-asset-results');
  if (!results) return;
  results.replaceChildren();
  if (!list.length) {
    const e = document.createElement('div');
    e.className = 'fp-empty';
    e.textContent = emptyText || 'No matches.';
    results.appendChild(e);
    return;
  }
  list.forEach(a => {
    const row = document.createElement('div');
    row.className = 'fp-result';
    if (_selectedAssets.has(a.id)) row.classList.add('selected');
    row.dataset.id = String(a.id);

    const grow = document.createElement('div');
    grow.className = 'grow';
    const name = document.createElement('div');
    name.textContent = (a.model_name || '') + (a.brand ? ' · ' + a.brand : '');
    grow.appendChild(name);
    const meta = document.createElement('div');
    meta.className = 'where';
    meta.textContent = (a.location_label || 'No location') + ' · ' + (a.status || '');
    grow.appendChild(meta);
    row.appendChild(grow);

    const tag = document.createElement('span');
    tag.className = 'tag';
    tag.textContent = a.asset_tag || '';
    row.appendChild(tag);

    row.addEventListener('click', () => {
      if (_selectedAssets.has(a.id)) {
        _selectedAssets.delete(a.id);
        row.classList.remove('selected');
      } else {
        _selectedAssets.set(a.id, {
          asset_tag: a.asset_tag, model_name: a.model_name,
          brand: a.brand, status: a.status,
        });
        row.classList.add('selected');
      }
      _renderSelectedChips();
      _updateCartSummary();
    });

    results.appendChild(row);
  });
}

function _renderSelectedChips() {
  const wrap = document.getElementById('fp-selected-chips');
  if (!wrap) return;
  wrap.replaceChildren();
  if (_selectedAssets.size === 0) {
    wrap.hidden = true;
    return;
  }
  wrap.hidden = false;
  _selectedAssets.forEach((meta, id) => {
    const chip = document.createElement('span');
    chip.className = 'fp-selected-chip';
    chip.dataset.id = String(id);
    const label = (meta.model_name || 'Asset') + ' (' + (meta.asset_tag || '') + ')';
    chip.appendChild(document.createTextNode(label));
    const x = document.createElement('button');
    x.type = 'button';
    x.setAttribute('aria-label', 'Remove ' + label);
    x.textContent = '×';
    x.addEventListener('click', () => {
      _selectedAssets.delete(id);
      _renderSelectedChips();
      _updateCartSummary();
      // Refresh result-row state if the row is still rendered
      const row = document.querySelector(`#fp-asset-results .fp-result[data-id="${id}"]`);
      if (row) row.classList.remove('selected');
    });
    chip.appendChild(x);
    wrap.appendChild(chip);
  });
}

function _updateCartSummary() {
  const summary = document.getElementById('fp-cart-summary');
  if (!summary) return;
  let totalUnits = 0, kinds = 0;
  _equipmentRequests.forEach(er => { totalUnits += er.quantity; kinds += 1; });
  if (kinds === 0) {
    summary.textContent = 'No equipment added yet';
    summary.classList.remove('has-items');
  } else {
    summary.textContent =
      `${kinds} item${kinds === 1 ? '' : 's'} · ${totalUnits} unit${totalUnits === 1 ? '' : 's'}`;
    summary.classList.add('has-items');
  }
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
    equipment_requests: Array.from(_equipmentRequests.values()).map(er => ({
      model_id: er.model_id, quantity: er.quantity,
    })),
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

// (Occupancy heat toggle removed — feature simplified out.)

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
  isoPinsEl.replaceChildren();
  SAIL_PINS.forEach((p, i) => {
    const m = document.createElement('div');
    m.className = 'pin-marker t-' + (p.type || 'custom');
    m.dataset.key = p.id;
    m.style.left = p.x + '%';
    m.style.top = p.y + '%';
    if (p.id === isoActiveKey) m.classList.add('active');

    const dot = document.createElement('div');
    dot.className = 'pin-dot';
    // Show the pin's numeric suffix (P-01 -> "1") inside the chip
    const match = String(p.id || '').match(/(\d+)$/);
    dot.textContent = match ? String(parseInt(match[1], 10)) : String(i + 1);
    m.appendChild(dot);

    const label = document.createElement('div');
    label.className = 'pin-label';
    label.textContent = p.name || 'Untitled';
    const id = document.createElement('span');
    id.className = 'pin-label-id';
    id.textContent = p.id;
    label.appendChild(id);
    m.appendChild(label);

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
  await loadBookableRooms();

  // If we arrived from the calendar page with ?book=zone&date=&start=&end=,
  // auto-open the booking modal pre-filled for that slot.
  const params = new URLSearchParams(window.location.search);
  const bookZone = params.get('book');
  if (bookZone && BOOKABLE.has(bookZone)) {
    selectZone(bookZone);
    await openBookingModal(bookZone);
    const form = document.getElementById('fp-booking-form');
    if (form) {
      const d = params.get('date');
      const s = params.get('start');
      const e = params.get('end');
      if (d) form.elements['date'].value = d;
      const startSel = document.getElementById('fp-start-select');
      const endSel = document.getElementById('fp-end-select');
      if (s && startSel) {
        startSel.value = s;
        if (startSel.onchange) startSel.onchange();
      }
      if (e && endSel) endSel.value = e;
      // Trigger schedule strip refresh for the chosen date
      if (d && form.elements['date'].onchange) form.elements['date'].onchange();
    }
  }
})();
