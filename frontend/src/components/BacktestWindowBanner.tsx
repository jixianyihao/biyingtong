/**
 * Compact banner showing the backtest window: start → end, trading-day count,
 * and an explicit "all agents + baselines aligned" confirmation. Renders once
 * at the top of the result panel so an analyst can verify at a glance that
 * every comparison row covers the same time range.
 */
export function BacktestWindowBanner({
  startDate,
  endDate,
  tradingDays,
  agentCount,
  baselineCount,
}: {
  startDate: string;
  endDate: string;
  tradingDays: number;
  agentCount: number;
  baselineCount: number;
}) {
  return (
    <div
      className="panel panel-border-soft mb-3 flex items-center gap-3 mono text-[11px]"
      style={{ padding: '8px 12px' }}
    >
      <span
        className="uppercase tracking-wider"
        style={{ color: 'var(--text-ghost)' }}
      >
        Window
      </span>
      <span style={{ color: 'var(--text-hi)' }}>{startDate}</span>
      <span style={{ color: 'var(--text-faint)' }}>→</span>
      <span style={{ color: 'var(--text-hi)' }}>{endDate}</span>
      <span style={{ color: 'var(--text-dim)' }}>· {tradingDays} 个交易日</span>
      <span style={{ flex: 1 }} />
      <span
        style={{ color: 'var(--down)' }}
        title="所有 agent + baseline 使用同一时间窗，可直接横向对比"
      >
        ✓ {agentCount} agents + {baselineCount} baselines aligned
      </span>
    </div>
  );
}
