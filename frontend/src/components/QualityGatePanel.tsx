import type { BacktestResult } from '../api/types';

type Criterion = {
  key: string;
  label: string;
  value: number | string | boolean;
  passed: boolean;
  threshold?: string;
};

function buildCriteria(r: BacktestResult): Criterion[] {
  const raw = r.quality_gate_criteria as Record<
    string,
    { passed?: boolean; value?: unknown; threshold?: string } | unknown
  >;
  const out: Criterion[] = [];
  for (const [k, v] of Object.entries(raw)) {
    if (v && typeof v === 'object' && 'passed' in (v as object)) {
      const entry = v as { passed: boolean; value?: unknown; threshold?: string };
      out.push({
        key: k,
        label: k.replace(/_/g, ' '),
        value: (entry.value as number | string | boolean) ?? '—',
        passed: !!entry.passed,
        threshold: entry.threshold,
      });
    }
  }
  return out;
}

export function QualityGatePanel({ result }: { result: BacktestResult | undefined }) {
  if (!result) return null;
  const items = buildCriteria(result);
  if (items.length === 0) {
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

  const passCount = items.filter((i) => i.passed).length;
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
          {chipTxt} · {passCount}/{items.length}
        </span>
      </div>
      <div className="grid gap-2">
        {items.map((c) => (
          <div
            key={c.key}
            className="flex items-center gap-2"
            style={{
              padding: '6px 10px',
              background: 'var(--bg-3)',
              border: `1px solid ${c.passed ? 'var(--brand)' : 'var(--down-border)'}`,
              borderRadius: 4,
            }}
          >
            <span
              style={{
                width: 18,
                height: 18,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: 999,
                background: c.passed ? 'var(--brand)' : 'var(--down)',
                color: 'var(--bg)',
                fontSize: 11,
                fontWeight: 'bold',
                flexShrink: 0,
              }}
            >
              {c.passed ? '✓' : '✗'}
            </span>
            <span className="text-xs text-text-hi capitalize">{c.label}</span>
            <span style={{ flex: 1 }} />
            <span className="mono text-xs text-text-faint">
              {String(c.value)}
              {c.threshold ? ` / ${c.threshold}` : ''}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
