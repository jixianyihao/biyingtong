// Wraps multiple KLineCharts in a responsive grid for the backtest universe.
import { KLineChart } from './KLineChart';

export function UniverseKLineGrid({
  codes,
  start,
  end,
}: {
  codes: string[];
  start: string;
  end: string;
}) {
  if (!codes.length) return null;
  return (
    <div
      className="grid gap-3"
      style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}
    >
      {codes.map((c) => (
        <div
          key={c}
          className="p-3"
          style={{
            border: '1px solid var(--panel-border-soft)',
            borderRadius: 'var(--r-sm)',
            background: 'var(--bg-2)',
          }}
        >
          <KLineChart code={c} start={start} end={end} height={200} />
        </div>
      ))}
    </div>
  );
}
