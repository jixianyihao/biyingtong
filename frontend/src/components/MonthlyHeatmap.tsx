import { useMonthlyReturns } from '../api/hooks';
import type { MonthlyReturn } from '../api/types';

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function colorFor(returnPct: number, maxAbs: number): string {
  if (Math.abs(returnPct) < 0.01) return 'var(--bg-3)';
  // intensity 0..1
  const intensity = Math.min(1, Math.abs(returnPct) / Math.max(maxAbs, 1));
  // CN convention: red=up (positive), green=down (negative)
  const alpha = (0.15 + intensity * 0.55).toFixed(2);
  if (returnPct > 0) {
    // var(--up) is red; we use rgba directly so we can blend with bg
    return `rgba(220, 60, 50, ${alpha})`;
  }
  return `rgba(40, 180, 90, ${alpha})`;
}

function fmtPct(v: number): string {
  const sign = v > 0 ? '+' : '';
  return `${sign}${v.toFixed(1)}%`;
}

function buildGrid(returns: MonthlyReturn[]): { years: number[]; byKey: Map<string, MonthlyReturn>; maxAbs: number } {
  const byKey = new Map<string, MonthlyReturn>();
  const yearSet = new Set<number>();
  let maxAbs = 0;
  for (const r of returns) {
    byKey.set(`${r.year}-${r.month}`, r);
    yearSet.add(r.year);
    maxAbs = Math.max(maxAbs, Math.abs(r.return_pct));
  }
  return {
    years: [...yearSet].sort(),
    byKey,
    maxAbs,
  };
}

export function MonthlyHeatmap({ resultId }: { resultId: string | undefined }) {
  const q = useMonthlyReturns(resultId);

  if (q.isLoading) {
    return <div className="text-text-faint text-sm">加载中…</div>;
  }
  if (q.error || !q.data) {
    return <div className="text-text-faint text-sm italic">无月度数据</div>;
  }
  const returns = q.data.monthly_returns;
  if (returns.length === 0) {
    return (
      <div className="text-text-faint text-sm italic">
        本次回测窗口不足一个月，无月度收益。
      </div>
    );
  }

  const { years, byKey, maxAbs } = buildGrid(returns);

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ borderCollapse: 'separate', borderSpacing: 2, fontSize: 11 }}>
        <thead>
          <tr>
            <th style={{
              padding: '4px 8px', textAlign: 'right',
              color: 'var(--text-faint)', fontWeight: 'normal',
              fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.06em',
            }}>
              YEAR
            </th>
            {MONTH_LABELS.map((m) => (
              <th
                key={m}
                style={{
                  padding: '4px 6px', textAlign: 'center',
                  color: 'var(--text-faint)', fontWeight: 'normal',
                  fontSize: 10, minWidth: 48,
                }}
              >
                {m}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {years.map((y) => (
            <tr key={y}>
              <td className="mono" style={{
                padding: '4px 8px', textAlign: 'right',
                color: 'var(--text-dim)', fontSize: 11,
              }}>
                {y}
              </td>
              {MONTH_LABELS.map((_, mi) => {
                const month = mi + 1;
                const cell = byKey.get(`${y}-${month}`);
                if (!cell) {
                  return (
                    <td
                      key={month}
                      style={{
                        background: 'var(--bg-3)',
                        border: '1px solid var(--panel-border-soft)',
                        height: 32, minWidth: 48,
                      }}
                    />
                  );
                }
                const bg = colorFor(cell.return_pct, maxAbs);
                const positive = cell.return_pct > 0;
                return (
                  <td
                    key={month}
                    style={{
                      background: bg,
                      border: '1px solid var(--panel-border-soft)',
                      height: 32, minWidth: 48,
                      textAlign: 'center', verticalAlign: 'middle',
                      color: 'var(--text-hi)',
                      fontVariantNumeric: 'tabular-nums',
                    }}
                    title={`${y}-${String(month).padStart(2, '0')}: ${fmtPct(cell.return_pct)} over ${cell.days} day${cell.days === 1 ? '' : 's'}`}
                  >
                    <span className={positive ? 'up' : 'down'}>
                      {fmtPct(cell.return_pct)}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
