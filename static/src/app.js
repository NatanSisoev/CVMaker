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

window.Alpine = Alpine;

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

Alpine.start();
