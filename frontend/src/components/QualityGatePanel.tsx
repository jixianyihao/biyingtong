import type { BacktestResult, QualityGateCriterion } from '../api/types';

type Row = {
  key: string;
  label: string;
  actual: number | string | boolean | null;
  threshold: number | string | boolean;
  ok: boolean;
  reason?: string;
};

function buildRows(r: BacktestResult): Row[] {
  const raw = r.quality_gate_criteria as Record<string, unknown>;
  const out: Row[] = [];
  for (const [k, v] of Object.entries(raw)) {
    if (!v || typeof v !== 'object') continue;
    const entry = v as Partial<QualityGateCriterion>;
    if (typeof entry.ok !== 'boolean') continue;
    out.push({
      key: k,
      label: k.replace(/_/g, ' '),
      actual: (entry.actual ?? '—') as Row['actual'],
      threshold: (entry.threshold ?? '') as Row['threshold'],
      ok: entry.ok,
      reason: entry.reason,
    });
  }
  return out;
}

function fmt(v: number | string | boolean | null): string {
  if (v === null) return '—';
  if (typeof v === 'number') {
    return Number.isInteger(v) ? v.toString() : v.toFixed(2);
  }
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  return v;
}

export function QualityGatePanel({ result }: { result: BacktestResult | undefined }) {
  if (!result) return null;
  const rows = buildRows(result);
  if (rows.length === 0) {
    return (
      <div className="panel p-5">
        <div className="flex items-baseline gap-2 mb-3 flex-wrap">
          <h2 className="text-text-hi text-base font-semibold">质量门</h2>
          <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
            Quality Gate
          </span>
        </div>
        <div className="text-text-faint text-sm italic">
          (本次回测无质量门数据)
        </div>
      </div>
    );
  }

  const passCount = rows.filter((r) => r.ok).length;
  const label = result.quality_gate_label;
  const chipCls =
    label === 'pass' ? 'pill brand' : label === 'warn' ? 'pill' : 'pill down';
  const chipTxt =
    label === 'pass' ? '达标' : label === 'warn' ? '观察' : '不通过';

  return (
    <div className="panel p-5">
      <div className="flex items-baseline gap-2 mb-3 flex-wrap">
        <h2 className="text-text-hi text-base font-semibold">质量门</h2>
        <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
          Quality Gate
        </span>
        <span style={{ flex: 1 }} />
        <span className={chipCls}>
          {chipTxt} · {passCount}/{rows.length}
        </span>
      </div>
      <div className="grid gap-2">
        {rows.map((row) => (
          <div
            key={row.key}
            className="flex items-center gap-2 flex-wrap"
            style={{
              padding: '6px 10px',
              background: 'var(--bg-3)',
              border: `1px solid ${row.ok ? 'var(--brand)' : 'var(--down-border)'}`,
              borderRadius: 4,
            }}
            title={row.reason || undefined}
          >
            <span
              style={{
                width: 18,
                height: 18,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: 999,
                background: row.ok ? 'var(--brand)' : 'var(--down)',
                color: 'var(--bg)',
                fontSize: 11,
                fontWeight: 'bold',
                flexShrink: 0,
              }}
            >
              {row.ok ? '✓' : '✗'}
            </span>
            <span className="text-xs text-text-hi capitalize">{row.label}</span>
            <span style={{ flex: 1 }} />
            <span className="mono text-xs text-text-faint">
              {fmt(row.actual)} / {fmt(row.threshold)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
