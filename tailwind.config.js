/**
 * Tailwind configuration -- Phase 4.1.
 *
 * Tokens live in CSS custom properties (see static/src/app.css's `@layer
 * base` block) so dark mode is a single attribute flip on <html> rather
 * than a Tailwind variant rebuild. The values below extract the
 * design-system scales from docs/DESIGN.md.
 *
 * If you change a token here, change DESIGN.md too -- the two are meant
 * to stay in sync, and DESIGN.md is the prose canonical source.
 */

/** @type {import('tailwindcss').Config} */
module.exports = {
  // Toggle dark mode by the `data-theme="dark"` attribute on <html>.
  // The selector strategy avoids relying on `prefers-color-scheme`, which
  // we want to override per-user.
  darkMode: ['selector', '[data-theme="dark"]'],

  // Scan every place a class name might appear. Django-cotton components
  // live under `templates/cotton/`; app-level templates live per-app and
  // under `templates/`.
  content: [
    './templates/**/*.html',
    './apps/**/templates/**/*.html',
    './apps/**/*.py',
    './static/src/**/*.{js,ts}',
  ],

  theme: {
    // Spacing / sizing follow an 8pt grid. Named stops only -- the
    // off-grid temptation gets removed at the config level.
    spacing: {
      0: '0',
      px: '1px',
      0.5: '2px',
      1: '4px',
      2: '8px',
      3: '12px',
      4: '16px',
      5: '20px',
      6: '24px',
      8: '32px',
      10: '40px',
      12: '48px',
      14: '56px',
      16: '64px',
      20: '80px',
      24: '96px',
      32: '128px',
      40: '160px',
      48: '192px',
      64: '256px',
    },

    fontFamily: {
      display: ['"Fraunces"', 'Georgia', 'ui-serif', 'serif'],
      sans: ['"Inter"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
    },

    // 8pt base, 1.25 minor-third (rounded to nearest 4px for legibility).
    fontSize: {
      xs:   ['12px', { lineHeight: '16px' }],
      sm:   ['14px', { lineHeight: '20px' }],
      base: ['16px', { lineHeight: '24px' }],
      lg:   ['18px', { lineHeight: '28px' }],
      xl:   ['20px', { lineHeight: '28px' }],
      '2xl': ['24px', { lineHeight: '32px' }],
      '3xl': ['30px', { lineHeight: '40px' }],
      '4xl': ['36px', { lineHeight: '44px' }],
      '5xl': ['48px', { lineHeight: '56px' }],
      '6xl': ['60px', { lineHeight: '68px' }],
    },

    borderRadius: {
      none: '0',
      sm:   '4px',  // inputs, chips
      md:   '8px',  // buttons, cards
      lg:   '12px', // modals, large surfaces
      full: '9999px',
    },

    // Shadows are soft + colored-with-bg (alpha on black), light-mode only.
    // Dark mode strips them entirely -- separation by border, not by depth.
    boxShadow: {
      none: 'none',
      1: '0 1px 2px rgb(0 0 0 / 0.04), 0 1px 1px rgb(0 0 0 / 0.02)',
      2: '0 8px 24px rgb(0 0 0 / 0.06), 0 2px 4px rgb(0 0 0 / 0.03)',
      // Focus ring -- 2px accent with a transparent buffer for layered UI.
      focus: '0 0 0 2px var(--bg), 0 0 0 4px var(--accent)',
    },

    extend: {
      colors: {
        bg: 'var(--bg)',
        surface: 'var(--surface)',
        'surface-2': 'var(--surface-2)',
        border: 'var(--border)',
        text: 'var(--text)',
        'text-muted': 'var(--text-muted)',
        accent: 'var(--accent)',
        'accent-ink': 'var(--accent-ink)',
        danger: 'var(--danger)',
      },

      transitionDuration: {
        // The two interaction speeds; everything snaps to one or the other.
        DEFAULT: '150ms',
        slow: '300ms',
      },
    },
  },

  plugins: [
    require('@tailwindcss/forms')({ strategy: 'class' }),
    require('@tailwindcss/typography'),
  ],
};
