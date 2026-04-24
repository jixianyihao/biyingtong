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

  if (isLoading) {
    return (
      <span className="mono text-[10px] text-text-faint">
        loading redlines…
      </span>
    );
  }
  if (error || !data) {
    return null; // silently hide on error — TopBar should never break
  }

  // Order keys for stable display: known LABELS first, others after
  const knownKeys = Object.keys(LABELS).filter((k) => k in data);
  const unknownKeys = Object.keys(data).filter((k) => !(k in LABELS));
  const orderedKeys = [...knownKeys, ...unknownKeys];

  return (
    <div
      className="flex items-center gap-1.5 mono"
      style={{ fontSize: 10 }}
      title="当前 RedLine 风控配置 (实时用量待 LiveTrading 接入)"
    >
      <span
        className="text-text-ghost uppercase"
        style={{ letterSpacing: '0.08em', marginRight: 2 }}
      >
        Redline
      </span>
      {orderedKeys.map((k) => {
        const v = data[k];
        const label = LABELS[k] ?? k;
        const valStr = formatLimit(k, v);
        const isOff = isBool(v) && !v;
        return (
          <span
            key={k}
            style={{
              padding: '1px 7px',
              borderRadius: 2,
              background: isOff ? 'transparent' : 'var(--bg-2)',
              border: '1px solid var(--panel-border-soft)',
              color: isOff ? 'var(--text-faint)' : 'var(--text-dim)',
              display: 'inline-flex',
              gap: 4,
              alignItems: 'baseline',
            }}
          >
            <span>{label}</span>
            <span style={{ color: 'var(--brand)' }}>{valStr}</span>
          </span>
        );
      })}
    </div>
  );
}
