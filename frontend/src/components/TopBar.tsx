import { useLocation } from 'react-router-dom';
import { ExecutionModeBadge } from './ExecutionModeBadge';
import { RedLineBar } from './RedLineBar';

const TITLES: Record<string, [string, string]> = {
  '/': ['做T研究', 'A-share T0 Lab'],
  '/agent': ['我的 AI 操盘手', 'My AI Traders'],
  '/live': ['实盘交易', 'Live Trading'],
  '/risk': ['安全管控', 'Safety & Guardrails'],
  '/screener': ['选股器', 'Factor Screener'],
  '/t0': ['做T研究', 'A-share T0 Lab'],
  '/editor': ['策略研发', 'Strategy Editor'],
  '/backtest': ['回测引擎', 'Backtest Engine'],
};

export function TopBar() {
  const { pathname } = useLocation();
  const [t1, t2] = TITLES[pathname] ?? TITLES['/'];

  return (
    <header
      style={{
        height: 44,
        background: 'var(--bg-1)',
        borderBottom: '1px solid var(--panel-border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 14px',
        gap: 14,
        flexShrink: 0,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-hi)' }}>{t1}</div>
        <div
          className="mono"
          style={{
            fontSize: 10,
            color: 'var(--text-ghost)',
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
          }}
        >
          {t2}
        </div>
      </div>

      <span
        className="pill brand"
        style={{ fontSize: 9.5, marginLeft: 6 }}
        title="Phase 2 · Vite + React 19"
      >
        v5.0 · dev
      </span>

      <div style={{ flex: 1 }} />

      <RedLineBar />

      <ExecutionModeBadge />
    </header>
  );
}
