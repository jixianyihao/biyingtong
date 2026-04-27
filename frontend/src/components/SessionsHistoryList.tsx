// Compact list of past backtest results. Lives in BacktestLab so the user
// retains context even after navigating away and coming back, and so they can
// jump back into any prior session with a single click.
import { useState } from 'react';
import { useBacktestList } from '../api/hooks';

function formatRelative(iso: string | null | undefined): string {
  if (!iso) return '';
  const ms = Date.now() - new Date(iso.replace(' ', 'T') + 'Z').getTime();
  if (Number.isNaN(ms)) return '';
  const m = Math.floor(ms / 60_000);
  if (m < 1) return '刚才';
  if (m < 60) return `${m} 分钟前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} 小时前`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d} 天前`;
  return iso.slice(0, 10);
}

export function SessionsHistoryList({
  onSelect,
  selectedSessionId,
  limit = 30,  // bumped from 12 — show more, hide empties by default
}: {
  onSelect: (sessionId: string, kind: 'agent' | 'rule') => void;
  selectedSessionId?: string | null;
  limit?: number;
}) {
  const { data, isLoading, error } = useBacktestList(limit);
  // 默认隐藏 0-trade / 0-equity-change runs (window-out-of-data 等失败回测)
  const [showEmpty, setShowEmpty] = useState(false);

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
  const allRows = data ?? [];
  // Filter empties: 0 trades AND zero P&L delta = nothing happened.
  const isEmpty = (r: typeof allRows[0]) =>
    (r.stats?.trade_count ?? 0) === 0 &&
    Math.abs((r.final_equity ?? 0) - (r.initial_capital ?? 0)) < 0.01;
  const visibleRows = showEmpty ? allRows : allRows.filter((r) => !isEmpty(r));
  const hiddenCount = allRows.length - visibleRows.length;
  if (allRows.length === 0) {
    return <div className="text-text-faint text-xs italic">暂无历史回测</div>;
  }

  return (
    <div className="grid gap-1">
      {hiddenCount > 0 && (
        <button
          onClick={() => setShowEmpty((v) => !v)}
          className="mono text-[10px] text-left px-2 py-1 rounded"
          style={{
            color: 'var(--text-faint)',
            background: 'var(--bg-2)',
            border: '1px dashed var(--panel-border-soft)',
            cursor: 'pointer',
          }}
          title="0 交易 + 净值未变 = 失败/空回测"
        >
          {showEmpty
            ? `▾ 隐藏空回测 (${hiddenCount})`
            : `▸ 显示 ${hiddenCount} 条空回测`}
        </button>
      )}
      {visibleRows.map((r) => {
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
              className="mono text-[10px] mt-0.5 flex items-baseline gap-2"
              style={{ color: 'var(--text-faint)' }}
            >
              <span>
                {r.start_date} → {r.end_date}
              </span>
              {r.created_at && (
                <span style={{ color: 'var(--text-ghost)' }}>
                  · {formatRelative(r.created_at)}
                </span>
              )}
              {r.quality_gate_label && (
                <span style={{ color: gateColor, marginLeft: 'auto' }}>
                  {r.quality_gate_label.toUpperCase()}
                </span>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
