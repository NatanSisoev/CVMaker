/**
 * Frontend entry. esbuild bundles this into static/dist/app.js.
 *
 * Two libraries:
 *
 *   - HTMX -- declarative server-driven interactivity. View-side renders
 *     fragments; the server stays the source of truth.
 *   - Alpine -- tiny declarative client-side state for things that
 *     don't round-trip (dropdowns, modals, theme toggle).
 *
 * Anything more elaborate goes through HTMX or a dedicated component;
 * we don't reach for jQuery/Vue/React. Keep this file small.
 */

import 'htmx.org';
import Alpine from 'alpinejs';
import Sortable from 'sortablejs';

window.Alpine = Alpine;
window.Sortable = Sortable;

// CSRF: every HTMX request that mutates state needs Django's CSRF token.
// Cookie name matches Django's CSRF_COOKIE_NAME default.
function csrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

document.body.addEventListener('htmx:configRequest', (evt) => {
  const method = (evt.detail.verb || '').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    evt.detail.headers['X-CSRFToken'] = csrfToken();
  }
});

// Theme toggle: persist the user's pick to localStorage, default to the
// OS preference. The CSS reads `data-theme` on <html>; we mirror it
// here.
const THEME_KEY = 'cvmaker.theme';
function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === 'dark' || theme === 'light') {
    root.setAttribute('data-theme', theme);
  } else {
    root.removeAttribute('data-theme');
  }
}
function preferredTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved) return saved;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}
applyTheme(preferredTheme());

// Expose a global helper so a button anywhere in the app can flip themes
// without re-bundling.
window.toggleTheme = () => {
  const current = document.documentElement.getAttribute('data-theme') || preferredTheme();
  const next = current === 'dark' ? 'light' : 'dark';
  localStorage.setItem(THEME_KEY, next);
  applyTheme(next);
};

// x-sortable="<url>": drag-reorder the element's [data-id] children by
// their [data-drag-handle], then POST the new order as repeated `ids`.
// On failure the DOM is put back and an error toast is shown.
Alpine.directive('sortable', (el, { expression }) => {
  const ids = () => [...el.children].map((child) => child.dataset.id).filter(Boolean);
  let before = [];
  Sortable.create(el, {
    animation: 150,
    handle: '[data-drag-handle]',
    onStart: () => { before = ids(); },
    onEnd: async (evt) => {
      if (evt.oldIndex === evt.newIndex) return;
      const body = new URLSearchParams(ids().map((id) => ['ids', id]));
      let ok = false;
      try {
        const res = await fetch(expression, {
          method: 'POST',
          headers: { 'X-CSRFToken': csrfToken() },
          body,
        });
        ok = res.ok;
      } catch (_) { /* network error -> revert below */ }
      if (ok) {
        el.dispatchEvent(new CustomEvent('sortable-saved', { bubbles: true }));
        return;
      }
      const byId = Object.fromEntries([...el.children].map((c) => [c.dataset.id, c]));
      before.forEach((id) => byId[id] && el.appendChild(byId[id]));
      window.dispatchEvent(new CustomEvent('toast', {
        detail: { message: 'Could not save the new order. Please try again.', variant: 'error' },
      }));
    },
  });
});

// Command palette (templates/cotton/command_palette.html). Results are an
// HTMX fragment of [role=option] items carrying data-url; this component
// only tracks the open state and which option is active.
Alpine.data('palette', () => ({
  open: false,
  active: -1,
  activeId: null,
  // Typed but results not refreshed yet: Enter waits for them instead of
  // opening a stale option.
  stale: false,
  queued: false,
  init() {
    this.$refs.input.addEventListener('input', () => { this.stale = true; });
    this.$el.addEventListener('htmx:afterSwap', () => {
      this.stale = false;
      this.reset();
      if (this.queued) {
        this.queued = false;
        this.go();
      }
    });
  },
  options() {
    return [...this.$refs.results.querySelectorAll('[role=option]')];
  },
  hotkey(evt) {
    if ((evt.metaKey || evt.ctrlKey) && evt.key.toLowerCase() === 'k') {
      evt.preventDefault();
      this.open ? this.hide() : this.show();
    }
  },
  show() {
    this.open = true;
    this.$nextTick(() => {
      this.$refs.input.value = '';
      this.$refs.input.focus();
      this.$refs.input.dispatchEvent(new Event('palette-open'));
    });
  },
  hide() {
    this.open = false;
    this.queued = false;
  },
  reset() {
    this.options().forEach((opt, i) => { opt.id = `palette-opt-${i}`; });
    this.select(this.options().length ? 0 : -1);
  },
  select(index) {
    const opts = this.options();
    opts.forEach((opt, i) => opt.setAttribute('aria-selected', String(i === index)));
    this.active = index;
    this.activeId = index >= 0 ? opts[index].id : null;
    if (index >= 0) opts[index].scrollIntoView({ block: 'nearest' });
  },
  move(delta) {
    const count = this.options().length;
    if (count) this.select((this.active + delta + count) % count);
  },
  go() {
    if (this.stale) {
      this.queued = true;
      return;
    }
    const opt = this.options()[this.active];
    if (opt) window.location.assign(opt.dataset.url);
  },
  pick(evt) {
    const opt = evt.target.closest('[role=option]');
    if (opt) window.location.assign(opt.dataset.url);
  },
}));

Alpine.start();

// Replay server-side Django messages (see base.html) as toasts.
const LEVEL_TO_VARIANT = { success: 'success', error: 'error' };
// A <template>'s children live in its `.content` fragment, not the document tree.
document.getElementById('flash')?.content.querySelectorAll('span').forEach((node) => {
  const level = (node.dataset.level || '').split(' ').find((tag) => tag in LEVEL_TO_VARIANT);
  window.dispatchEvent(new CustomEvent('toast', {
    detail: { message: node.textContent, variant: LEVEL_TO_VARIANT[level] || 'info' },
  }));
});
