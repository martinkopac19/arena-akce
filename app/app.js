'use strict';

const TZ = 'Europe/Prague';
const VENUE_ORDER = ['o2arena', 'o2universum', 'unyp'];
const VENUE_NAMES = { o2arena: 'O2 arena', o2universum: 'O2 universum', unyp: 'UNYP Arena' };

const SPORT_ICONS = { Florbal: '🏑', Volejbal: '🏐' };

const DAYS = 8; // dnes + 7 dní

let data = null;
let day = 0;
let tabsBuiltFor = null;

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
function weekdayName(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  const w = new Date(Date.UTC(y, m - 1, d, 12)).toLocaleDateString('sk-SK', { weekday: 'long', timeZone: 'UTC' });
  return w.charAt(0).toUpperCase() + w.slice(1);
}
function shortDate(iso) {
  const [, m, d] = iso.split('-').map(Number);
  return `${d}. ${m}.`;
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

// Prúžok dní: Dnes, Zajtra a ďalších 6 dní (horizontálne posúvanie).
// Prestavia sa len pri zmene dňa, aby sa nestratila pozícia posunutia.
function buildTabs() {
  const today = pragueDate(0);
  if (tabsBuiltFor === today) return;
  tabsBuiltFor = today;
  const nav = document.getElementById('tabs');
  nav.replaceChildren();
  for (let i = 0; i < DAYS; i++) {
    const iso = pragueDate(i);
    const label = i === 0 ? 'Dnes' : i === 1 ? 'Zajtra' : weekdayName(iso);
    const date = i < 2 ? niceDate(iso) : shortDate(iso);
    const btn = el('button', { role: 'tab', class: 'tab', 'data-day': String(i), 'aria-selected': 'false' },
      el('span', { class: 'tab-label' }, label), el('span', { class: 'tab-date' }, date));
    btn.addEventListener('click', () => { day = i; render(); });
    nav.append(btn);
  }
  nav.scrollLeft = 0;
  updateScrollHint();
}

function updateScrollHint() {
  const nav = document.getElementById('tabs');
  nav.classList.toggle('more-left', nav.scrollLeft > 4);
  nav.classList.toggle('more-right', nav.scrollLeft + nav.clientWidth < nav.scrollWidth - 4);
}

function render() {
  buildTabs();
  const date = pragueDate(day);
  document.querySelectorAll('.tab').forEach(t => {
    const sel = +t.dataset.day === day;
    t.setAttribute('aria-selected', String(sel));
    if (sel && t.offsetParent) t.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
  });

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
    const failed = Object.keys(data.errors || {}).some(k => k === v || k.startsWith(v + '-'));
    if (failed && !evs.length) {
      sec.append(el('p', { class: 'empty' }, 'Program sa nepodarilo načítať.'));
    } else if (!evs.length) {
      sec.append(el('p', { class: 'empty' }, day === 0 ? 'Dnes žiadna akcia.' : day === 1 ? 'Zajtra žiadna akcia.' : 'V tento deň žiadna akcia.'));
    }
    for (const e of evs) {
      sec.append(el('a', { class: 'card', href: e.url, target: '_blank', rel: 'noopener' },
        e.image || !SPORT_ICONS[e.tag]
          ? el('div', { class: 'thumb', style: e.image ? `background-image:url("${encodeURI(e.image)}")` : '' })
          : el('div', { class: 'thumb sport', 'aria-hidden': 'true' }, SPORT_ICONS[e.tag]),
        el('div', { class: 'card-body' },
          el('div', { class: 'time' }, timeOf(e), e.tag ? el('span', { class: 'tag' }, e.tag) : null),
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

document.getElementById('refresh').addEventListener('click', load);
// po návrate do appky (napr. ďalší deň) prekresli a obnov dáta
document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });

if ('serviceWorker' in navigator) {
  // Keď sa nainštaluje nová verzia appky, raz sa obnovíme, aby sa hneď prejavila.
  const hadController = !!navigator.serviceWorker.controller;
  let reloaded = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (hadController && !reloaded) { reloaded = true; location.reload(); }
  });
  navigator.serviceWorker.register('sw.js', { updateViaCache: 'none' }).then(r => r.update()).catch(() => {});
}
document.getElementById('tabs').addEventListener('scroll', updateScrollHint, { passive: true });
window.addEventListener('resize', updateScrollHint);
buildTabs();
load();
