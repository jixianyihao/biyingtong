import { useEffect, useRef, useState } from 'react';
import { useRedlines } from '../api/hooks';

// Display labels for the known redline keys. Unknown keys get a fallback rendering.
// NOTE: For MVP this shows configured *limits* only. Future P3-F LiveTrading work
// will plug in real-time usage values (e.g. "3 / 10 holdings", "-1.2% / -5% daily loss").
const LABELS: Record<string, string> = {
  position_max_pct: '单仓上限',
  max_holdings: '最大持仓数',
  daily_loss_limit_pct: '日内止损',
  ban_st: '禁 ST',
};

function isBool(v: unknown): v is boolean {
  return typeof v === 'boolean';
}

function isNumber(v: unknown): v is number {
  return typeof v === 'number' && !Number.isNaN(v);
}

function formatLimit(key: string, v: unknown): string {
  if (isBool(v)) return v ? 'on' : 'off';
  if (isNumber(v)) {
    if (key.endsWith('_pct')) return `${v.toFixed(0)}%`;
    return String(v);
  }
  return String(v);
}

export function RedLineBar() {
  const { data, isLoading, error } = useRedlines();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open]);

  if (isLoading) {
    return <span className="mono text-[10px] text-text-faint">loading redlines…</span>;
  }
  if (error || !data) {
    return null;
  }

  const knownKeys = Object.keys(LABELS).filter((k) => k in data);
  const unknownKeys = Object.keys(data).filter((k) => !(k in LABELS));
  const orderedKeys = [...knownKeys, ...unknownKeys];
  const count = orderedKeys.length;

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="mono"
        style={{
          fontSize: 10,
          padding: '2px 8px',
          borderRadius: 3,
          background: 'var(--bg-2)',
          border: '1px solid var(--panel-border-soft)',
          color: 'var(--text-dim)',
          cursor: 'pointer',
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          letterSpacing: '0.04em',
        }}
        title="点击查看完整 RedLine 风控配置"
      >
        <span style={{ color: 'var(--text-ghost)', textTransform: 'uppercase' }}>
          Redline
        </span>
        <span style={{ color: 'var(--brand)' }}>{count} 条</span>
        <span style={{ fontSize: 9, color: 'var(--text-faint)' }}>{open ? '▴' : '▾'}</span>
      </button>

      {open && (
        <div
          className="panel panel-border-soft mono"
          style={{
            position: 'absolute',
            right: 0,
            top: 'calc(100% + 6px)',
            zIndex: 50,
            padding: 10,
            minWidth: 240,
            maxHeight: 360,
            overflowY: 'auto',
            fontSize: 10.5,
            display: 'grid',
            gridTemplateColumns: '1fr auto',
            gap: '4px 14px',
          }}
        >
          {orderedKeys.map((k) => {
            const v = data[k];
            const label = LABELS[k] ?? k;
            const valStr = formatLimit(k, v);
            const isOff = isBool(v) && !v;
            return (
              <div key={k} style={{ display: 'contents' }}>
                <span style={{ color: isOff ? 'var(--text-faint)' : 'var(--text-dim)' }}>
                  {label}
                </span>
                <span
                  style={{
                    color: isOff ? 'var(--text-faint)' : 'var(--brand)',
                    textAlign: 'right',
                  }}
                >
                  {valStr}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
