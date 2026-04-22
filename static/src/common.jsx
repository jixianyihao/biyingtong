// Shared small components
const { useState, useEffect, useRef, useMemo, useCallback } = React;

// Icon set (tiny inline SVGs — 16x16 stroke)
function Icon({ name, size = 14, className = '', style = {} }) {
  const paths = {
    dashboard: <><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/></>,
    code: <><polyline points="8 6 2 12 8 18"/><polyline points="16 6 22 12 16 18"/><line x1="14" y1="4" x2="10" y2="20"/></>,
    filter: <><polygon points="3 4 21 4 14 13 14 20 10 20 10 13 3 4"/></>,
    backtest: <><path d="M3 17 L8 11 L12 14 L16 7 L21 10"/><circle cx="8" cy="11" r="1.5"/><circle cx="16" cy="7" r="1.5"/></>,
    agent: <><circle cx="12" cy="9" r="4"/><path d="M5 21 v-1 a5 5 0 0 1 5-5 h4 a5 5 0 0 1 5 5 v1"/><circle cx="10" cy="9" r="0.6" fill="currentColor"/><circle cx="14" cy="9" r="0.6" fill="currentColor"/></>,
    live: <><path d="M12 2 L3 14 L11 14 L9 22 L21 10 L13 10 L15 2 Z"/></>,
    market: <><rect x="3" y="3" width="18" height="18" rx="1"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="3" x2="9" y2="21"/></>,
    risk: <><path d="M12 3 L21 20 L3 20 Z"/><line x1="12" y1="10" x2="12" y2="14"/><circle cx="12" cy="17" r="0.8" fill="currentColor"/></>,
    search: <><circle cx="11" cy="11" r="6"/><line x1="20" y1="20" x2="16" y2="16"/></>,
    bell: <><path d="M6 10 a6 6 0 0 1 12 0 v4 l2 3 H4 l2-3 Z"/><path d="M10 20 a2 2 0 0 0 4 0"/></>,
    play: <><polygon points="5 3 19 12 5 21"/></>,
    pause: <><rect x="5" y="4" width="4" height="16"/><rect x="15" y="4" width="4" height="16"/></>,
    zap: <><polygon points="13 2 3 14 11 14 9 22 21 10 13 10 15 2"/></>,
    plus: <><line x1="12" y1="4" x2="12" y2="20"/><line x1="4" y1="12" x2="20" y2="12"/></>,
    close: <><line x1="5" y1="5" x2="19" y2="19"/><line x1="19" y1="5" x2="5" y2="19"/></>,
    check: <><polyline points="4 12 10 18 20 6"/></>,
    chevR: <><polyline points="9 5 16 12 9 19"/></>,
    chevD: <><polyline points="5 9 12 16 19 9"/></>,
    arrowUp: <><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></>,
    arrowDown: <><line x1="12" y1="5" x2="12" y2="19"/><polyline points="5 12 12 19 19 12"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19 12 a7 7 0 0 0 -0.1 -1.4 l2 -1.5 -2 -3.5 -2.4 0.8 a7 7 0 0 0 -2.4 -1.4 l-0.4 -2.5 h-4 l-0.4 2.5 a7 7 0 0 0 -2.4 1.4 l-2.4 -0.8 -2 3.5 2 1.5 a7 7 0 0 0 0 2.8 l-2 1.5 2 3.5 2.4 -0.8 a7 7 0 0 0 2.4 1.4 l0.4 2.5 h4 l0.4 -2.5 a7 7 0 0 0 2.4 -1.4 l2.4 0.8 2 -3.5 -2 -1.5 a7 7 0 0 0 0.1 -1.4 z"/></>,
    save: <><path d="M19 21 H5 a2 2 0 0 1 -2 -2 V5 a2 2 0 0 1 2 -2 h11 l5 5 v11 a2 2 0 0 1 -2 2 Z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></>,
    copy: <><rect x="8" y="8" width="13" height="13" rx="2"/><path d="M4 16 V5 a2 2 0 0 1 2 -2 h11"/></>,
    star: <><polygon points="12 3 15 9 21 10 17 14 18 20 12 17 6 20 7 14 3 10 9 9"/></>,
    brain: <><path d="M9 4 a3 3 0 0 0 -3 3 a2.5 2.5 0 0 0 -2 4 a2.5 2.5 0 0 0 2 4 a3 3 0 0 0 3 3 a3 3 0 0 0 3 -3 V7 a3 3 0 0 0 -3 -3 z"/><path d="M15 4 a3 3 0 0 1 3 3 a2.5 2.5 0 0 1 2 4 a2.5 2.5 0 0 1 -2 4 a3 3 0 0 1 -3 3 a3 3 0 0 1 -3 -3 V7 a3 3 0 0 1 3 -3 z"/></>,
    sparkle: <><path d="M12 3 L13.5 9 L19 10.5 L13.5 12 L12 18 L10.5 12 L5 10.5 L10.5 9 Z"/><path d="M19 3 L19.8 5.5 L22 6 L19.8 6.5 L19 9 L18.2 6.5 L16 6 L18.2 5.5 Z"/></>,
    menu: <><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></>,
    refresh: <><polyline points="21 4 21 10 15 10"/><polyline points="3 20 3 14 9 14"/><path d="M20 14 a8 8 0 0 1 -14 4 L3 14"/><path d="M4 10 a8 8 0 0 1 14 -4 L21 10"/></>,
    wand: <><path d="M3 21 L15 9"/><path d="M17 7 L18.5 5.5"/><path d="M18 3 L19 4"/><path d="M21 6 L22 7"/><path d="M14 4 L15 5"/><path d="M19 10 L20 11"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 16 14"/></>,
    folder: <><path d="M3 5 a2 2 0 0 1 2 -2 h4 l2 3 h8 a2 2 0 0 1 2 2 v10 a2 2 0 0 1 -2 2 H5 a2 2 0 0 1 -2 -2 z"/></>,
    download: <><path d="M12 3 V15"/><polyline points="6 10 12 16 18 10"/><line x1="4" y1="20" x2="20" y2="20"/></>,
    sun: <><circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="22"/><line x1="4" y1="12" x2="2" y2="12"/><line x1="22" y1="12" x2="20" y2="12"/><line x1="5" y1="5" x2="6.5" y2="6.5"/><line x1="17.5" y1="17.5" x2="19" y2="19"/><line x1="5" y1="19" x2="6.5" y2="17.5"/><line x1="17.5" y1="6.5" x2="19" y2="5"/></>,
    moon: <><path d="M20 14 a8 8 0 1 1 -10 -10 a6 6 0 0 0 10 10 z"/></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      {paths[name] || null}
    </svg>
  );
}

function Sparkline({ data, color = 'var(--up)', fill = true, width = 80, height = 22, strokeWidth = 1.25 }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const stepX = width / (data.length - 1);
  const pts = data.map((v, i) => [i * stepX, height - ((v - min) / range) * height * 0.9 - height * 0.05]);
  const d = pts.map((p, i) => (i === 0 ? 'M' : 'L') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  const areaD = d + ` L${width},${height} L0,${height} Z`;
  return (
    <svg width={width} height={height} style={{ display: 'block', overflow: 'visible' }}>
      {fill && <path d={areaD} fill={color} opacity="0.12"/>}
      <path d={d} fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinejoin="round" strokeLinecap="round"/>
    </svg>
  );
}

// A simple seeded random for deterministic sparklines
function seedRand(seed) {
  let s = seed;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

function genSpark(seed, n = 40, drift = 0, vol = 1) {
  const r = seedRand(seed);
  const out = [];
  let v = 50;
  for (let i = 0; i < n; i++) {
    v += (r() - 0.5) * 4 * vol + drift;
    out.push(v);
  }
  return out;
}

function fmt(n, d = 2) {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
}

function pct(n, d = 2) {
  const s = n >= 0 ? '+' : '';
  return s + n.toFixed(d) + '%';
}

// --- Logo ---
function Logo({ size = 22 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
      <rect x="1" y="1" width="30" height="30" rx="6" fill="oklch(0.18 0.012 260)" stroke="var(--brand)" strokeWidth="1.2"/>
      <path d="M10 22 L14 12 L17 18 L22 8" stroke="var(--brand)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
      <circle cx="22" cy="8" r="1.8" fill="var(--up)"/>
      <line x1="10" y1="25" x2="22" y2="25" stroke="var(--brand)" strokeWidth="1" opacity="0.4"/>
    </svg>
  );
}

Object.assign(window, { Icon, Sparkline, seedRand, genSpark, fmt, pct, Logo });
