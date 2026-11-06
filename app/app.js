'use strict';

const TZ = 'Europe/Prague';
const VENUE_ORDER = ['o2arena', 'o2universum', 'unyp'];
const VENUE_NAMES = { o2arena: 'O2 arena', o2universum: 'O2 universum', unyp: 'UNYP Arena' };

let data = null;
let day = 0;

// YYYY-MM-DD v pražskom čase, posunuté o `offset` dní
function pragueDate(offset = 0) {
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  const [y, m, d] = today.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d + offset)).toISOString().slice(0, 10);
}
function niceDate(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d, 12)).toLocaleDateString('sk-SK', { weekday: 'short', day: 'numeric', month: 'numeric', timeZone: 'UTC' });
}
function timeOf(ev) {
  if (!ev.hasTime) return 'celý deň';
  return new Date(ev.start).toLocaleTimeString('sk-SK', { hour: '2-digit', minute: '2-digit', timeZone: TZ });
}
function el(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'style') n.style.cssText = v;
    else if (v != null) n.setAttribute(k, v);
  }
  for (const c of children) if (c != null) n.append(c);
  return n;
}

function render() {
  const date = pragueDate(day);
  document.getElementById('d0').textContent = niceDate(pragueDate(0));
  document.getElementById('d1').textContent = niceDate(pragueDate(1));
  document.querySelectorAll('.tab').forEach(t => t.setAttribute('aria-selected', String(+t.dataset.day === day)));

  const list = document.getElementById('list');
  if (!data) return;
  list.replaceChildren();

  const todays = data.events.filter(e => e.date === date);
  for (const v of VENUE_ORDER) {
    const evs = todays.filter(e => e.venue === v);
    const color = `var(--${v})`;
    const sec = el('section', { class: 'venue', style: `--c:${color}` },
      el('h2', { class: 'venue-head' }, el('span', { class: 'dot' }), VENUE_NAMES[v],
        el('span', { class: 'count' }, evs.length ? String(evs.length) : '')));
    if (data.errors && data.errors[v] && !evs.length) {
      sec.append(el('p', { class: 'empty' }, 'Program sa nepodarilo načítať.'));
    } else if (!evs.length) {
      sec.append(el('p', { class: 'empty' }, day === 0 ? 'Dnes žiadna akcia.' : 'Zajtra žiadna akcia.'));
    }
    for (const e of evs) {
      sec.append(el('a', { class: 'card', href: e.url, target: '_blank', rel: 'noopener' },
        el('div', { class: 'thumb', style: e.image ? `background-image:url("${encodeURI(e.image)}")` : '' }),
        el('div', { class: 'card-body' },
          el('div', { class: 'time' }, timeOf(e)),
          el('div', { class: 'title' }, e.title),
          e.description ? el('div', { class: 'desc' }, e.description) : null)));
    }
    list.append(sec);
  }

  if (data.generatedAt) {
    const g = new Date(data.generatedAt);
    document.getElementById('updated').textContent =
      'Aktualizované ' + g.toLocaleString('sk-SK', { timeZone: TZ, day: 'numeric', month: 'numeric', hour: '2-digit', minute: '2-digit' });
  }
}

async function load() {
  const btn = document.getElementById('refresh');
  btn.classList.add('spin');
  try {
    const r = await fetch('events.json', { cache: 'no-cache' });
    if (!r.ok) throw new Error(r.status);
    data = await r.json();
    document.getElementById('offline').hidden = true;
  } catch (err) {
    document.getElementById('offline').hidden = false;
    if (!data) document.getElementById('list').innerHTML = '<p class="state">Program sa nepodarilo načítať. Skús to neskôr.</p>';
  } finally {
    btn.classList.remove('spin');
  }
  render();
}

document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => { day = +t.dataset.day; render(); }));
document.getElementById('refresh').addEventListener('click', load);
// po návrate do appky (napr. ďalší deň) prekresli a obnov dáta
document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });

if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js');
load();
