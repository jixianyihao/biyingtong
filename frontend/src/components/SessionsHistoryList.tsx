// Compact list of past backtest results. Lives in BacktestLab so the user
// retains context even after navigating away and coming back, and so they can
// jump back into any prior session with a single click.
import { useBacktestList } from '../api/hooks';

export function SessionsHistoryList({
  onSelect,
  selectedSessionId,
  limit = 12,
}: {
  onSelect: (sessionId: string, kind: 'agent' | 'rule') => void;
  selectedSessionId?: string | null;
  limit?: number;
}) {
  const { data, isLoading, error } = useBacktestList(limit);

  if (isLoading) {
    return <div className="text-text-faint text-xs italic">加载历史…</div>;
  }
  if (error) {
    return (
      <div className="text-xs" style={{ color: 'var(--down)' }}>
        历史加载失败：{String((error as Error).message ?? error)}
      </div>
    );
  }
  const rows = data ?? [];
  if (rows.length === 0) {
    return <div className="text-text-faint text-xs italic">暂无历史回测</div>;
  }

  return (
    <div className="grid gap-1">
      {rows.map((r) => {
        const sel = r.session_id === selectedSessionId;
        const ret = r.stats?.total_return_pct ?? 0;
        const retColor =
          ret > 0 ? 'var(--up)' : ret < 0 ? 'var(--down)' : 'var(--text-dim)';
        const kindLabel = r.kind === 'rule' ? 'RULE' : 'AGENT';
        const gateColor =
          r.quality_gate_label === 'pass'
            ? 'var(--up)'
            : r.quality_gate_label === 'fail'
              ? 'var(--down)'
              : 'var(--text-faint)';
        // Friendly title: prefer user-given display_name, then persona+model
        // pair, then last-resort agent_id / session_id slice.
        const primary =
          r.agent_display_name?.trim() ||
          (r.persona_id && r.model_id
            ? `${r.persona_id} · ${r.model_id}`
            : r.persona_id || r.agent_id || r.session_id.slice(0, 18));
        const subtitle =
          r.agent_display_name && (r.persona_id || r.model_id)
            ? [r.persona_id, r.model_id].filter(Boolean).join(' · ')
            : null;
        return (
          <button
            key={r.id}
            onClick={() =>
              onSelect(r.session_id, r.kind === 'rule' ? 'rule' : 'agent')
            }
            className="text-left px-2 py-1.5 rounded text-xs transition-colors"
            style={{
              border: `1px solid ${sel ? 'var(--brand)' : 'var(--panel-border-soft)'}`,
              background: sel ? 'var(--bg-3)' : 'var(--bg-2)',
            }}
          >
            <div className="flex items-baseline gap-2">
              <span
                className="mono text-[9.5px] uppercase tracking-wider"
                style={{ color: 'var(--text-ghost)' }}
              >
                {kindLabel}
              </span>
              <span
                className="text-[12px] font-semibold flex-1 truncate"
                style={{ color: 'var(--text-hi)' }}
              >
                {primary}
              </span>
              <span
                className="num mono text-[11px]"
                style={{ color: retColor, fontVariantNumeric: 'tabular-nums' }}
              >
                {ret >= 0 ? '+' : ''}
                {ret.toFixed(2)}%
              </span>
            </div>
            {subtitle && (
              <div
                className="mono text-[10px] mt-0.5 truncate"
                style={{ color: 'var(--text-dim)' }}
              >
                {subtitle}
              </div>
            )}
            <div
              className="mono text-[10px] mt-0.5"
              style={{ color: 'var(--text-faint)' }}
            >
              {r.start_date} → {r.end_date}
              {r.quality_gate_label && (
                <span className="ml-2" style={{ color: gateColor }}>
                  · {r.quality_gate_label.toUpperCase()}
                </span>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
