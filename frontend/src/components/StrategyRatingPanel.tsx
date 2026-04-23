import type { StrategyRating } from '../api/types';

const SUB_ROWS: Array<{
  key: keyof Pick<StrategyRating, 'returns' | 'sharpe' | 'drawdown' | 'win_rate' | 'consistency'>;
  label: string;
  weight: number;
}> = [
  { key: 'returns', label: '收益 Returns', weight: 30 },
  { key: 'sharpe', label: '风险调整 Sharpe', weight: 30 },
  { key: 'drawdown', label: '最大回撤 Drawdown', weight: 15 },
  { key: 'win_rate', label: '胜率 Win Rate', weight: 15 },
  { key: 'consistency', label: '一致性 Consistency', weight: 10 },
];

function letterColor(letter: StrategyRating['letter']): string {
  switch (letter) {
    case 'A+':
    case 'A':
      return 'var(--brand)';
    case 'B':
      return 'var(--text-hi)';
    case 'C':
      return 'var(--warn)';
    case 'D':
    default:
      return 'var(--down)';
  }
}

export function StrategyRatingPanel({ rating }: { rating: StrategyRating | undefined }) {
  if (!rating) {
    return (
      <div className="panel p-5">
        <div className="flex items-baseline gap-2 mb-3 flex-wrap">
          <h2 className="text-text-hi text-base font-semibold">策略评级</h2>
          <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
            Strategy Rating
          </span>
        </div>
        <div className="text-text-faint text-sm">评级加载中…</div>
      </div>
    );
  }

  return (
    <div className="panel p-5">
      <div className="flex items-baseline gap-2 mb-3 flex-wrap">
        <h2 className="text-text-hi text-base font-semibold">策略评级</h2>
        <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
          Strategy Rating
        </span>
        <span style={{ flex: 1 }} />
        <span
          className="text-3xl font-bold"
          style={{ color: letterColor(rating.letter) }}
        >
          {rating.letter}
        </span>
        <span className="mono text-xs text-text-faint">
          {rating.overall.toFixed(1)} / 100
        </span>
      </div>

      <div className="grid gap-2 mb-3">
        {SUB_ROWS.map((row) => {
          const v = rating[row.key];
          const pct = Math.max(0, Math.min(100, v));
          return (
            <div key={row.key}>
              <div className="flex items-baseline justify-between text-xs mb-0.5">
                <span className="text-text">
                  {row.label}
                  <span className="text-text-faint ml-1">({row.weight}%)</span>
                </span>
                <span className="mono text-text-hi">{v.toFixed(1)}</span>
              </div>
              <div
                style={{
                  height: 4,
                  background: 'var(--bg-2)',
                  borderRadius: 2,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    width: `${pct}%`,
                    height: '100%',
                    background: 'var(--brand)',
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {rating.notes.length > 0 && (
        <div
          className="text-text-faint text-[11px]"
          style={{ lineHeight: 1.5 }}
        >
          <div className="text-[10px] uppercase tracking-wider mb-1">Notes</div>
          {rating.notes.map((n, i) => (
            <div key={i}>· {n}</div>
          ))}
        </div>
      )}
    </div>
  );
}
