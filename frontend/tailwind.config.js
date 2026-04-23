/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          0: 'var(--bg-0)', 1: 'var(--bg-1)', 2: 'var(--bg-2)',
          3: 'var(--bg-3)', 4: 'var(--bg-4)',
        },
        text: {
          hi: 'var(--text-hi)', DEFAULT: 'var(--text)',
          dim: 'var(--text-dim)', faint: 'var(--text-faint)',
          ghost: 'var(--text-ghost)',
        },
        brand: 'var(--brand)',
        up: 'var(--up)',
        down: 'var(--down)',
        'panel-border': 'var(--panel-border)',
        'panel-border-soft': 'var(--panel-border-soft)',
      },
      fontFamily: {
        ui: ['var(--f-ui)'],
        mono: ['var(--f-mono)'],
        serif: ['var(--f-serif)'],
      },
    },
  },
  plugins: [],
}
