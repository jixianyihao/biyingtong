import { useMemo, useState } from 'react';
import type { LedgerEntry, LedgerOutcome } from '../api/types';
import { useBacktestLedger } from '../api/hooks';

type OutcomeFilter = 'all' | LedgerOutcome;
type ActionFilter = 'all' | LedgerEntry['action'];

const OUTCOME_LABELS: Record<LedgerOutcome, string> = {
  ok: '执行',
  approved: '执行',  // legacy alias — same UX as 'ok'
  modified: '调整',
  rejected: '拦截',
  cached: '缓存',
  hold: '持仓',
};

function OutcomeChip({ row }: { row: LedgerEntry }) {
  const label = OUTCOME_LABELS[row.outcome] ?? row.outcome;
  // Color mapping deliberately uses semantic tokens, NOT the CN red/green
  // palette — outcome is "did the validator let it through?", which is
  // independent of buy/sell direction.
  let bg = 'transparent';
  let color = 'var(--text)';
  let border = '1px solid var(--panel-border-soft)';
  let prefix: string | null = null;
  let title: string | undefined;

  if (row.outcome === 'ok' || row.outcome === 'approved') {
    color = 'var(--down)'; // green = success in CN palette
    border = '1px solid var(--down-border)';
    bg = 'var(--down-bg)';
    prefix = '✓';
    title = '通过校验并执行';
  } else if (row.outcome === 'modified') {
    color = 'var(--warn)';
    border = '1px solid var(--warn)';
    bg = 'rgba(234,179,8,0.10)';
    prefix = '~';
    if (row.requested_shares != null && row.executed_shares !== row.requested_shares) {
      title = `${row.requested_shares} → ${row.executed_shares} shares`;
    } else {
      title = '校验时被规则修改';
    }
  } else if (row.outcome === 'rejected') {
    color = 'var(--up)'; // red = failure in CN palette
    border = '1px solid var(--up-border)';
    bg = 'var(--up-bg)';
    prefix = '✗';
    title = row.rejection_reasons.length
      ? row.rejection_reasons.join('; ')
      : '被红线/校验拦截';
  } else if (row.outcome === 'cached') {
    color = 'var(--text-faint)';
    title = '复用缓存决策（未走 LLM）';
  } else if (row.outcome === 'hold') {
    color = 'var(--text-ghost)';
    title = '当日无可执行决策';
  }

  return (
    <span
      className="pill mono"
      title={title}
      style={{
        fontSize: 10,
        padding: '1px 6px',
        background: bg,
        color,
        border,
        borderRadius: 4,
        whiteSpace: 'nowrap',
      }}
    >
      {prefix ? `${prefix} ` : ''}
      {label}
    </span>
  );
}

function ActionCell({ action }: { action: LedgerEntry['action'] }) {
  if (action === 'hold') {
    return (
      <span
        className="pill mono"
        style={{ fontSize: 10, padding: '1px 6px', color: 'var(--text-faint)' }}
      >
        持
      </span>
    );
  }
  // CN convention: buy = red (up), sell = green (down)
  return (
    <span
      className={`pill ${action === 'buy' ? 'up' : 'down'} mono`}
      style={{ fontSize: 10, padding: '1px 6px' }}
    >
      {action === 'buy' ? '买' : '卖'}
    </span>
  );
}

function fmtShares(n: number | null | undefined): string {
  if (n == null) return '—';
  return n.toLocaleString();
}

function fmtPrice(p: number | null | undefined): string {
  if (p == null) return '—';
  return `¥${p.toFixed(2)}`;
}

export function DecisionLedger({ resultId }: { resultId: string | undefined }) {
  const { data, isLoading, error } = useBacktestLedger(resultId);
  const [outcomeFilter, setOutcomeFilter] = useState<OutcomeFilter>('all');
  const [actionFilter, setActionFilter] = useState<ActionFilter>('all');

  const allRows = data?.ledger ?? [];
  const filtered = useMemo(() => {
    return allRows.filter((r) => {
      if (outcomeFilter !== 'all') {
        // 'ok' filter accepts the legacy 'approved' synonym so old backtests
        // (pre-P3-D) still flow through this view.
        const matches =
          r.outcome === outcomeFilter ||
          (outcomeFilter === 'ok' && r.outcome === 'approved');
        if (!matches) return false;
      }
      if (actionFilter !== 'all' && r.action !== actionFilter) return false;
      return true;
    });
  }, [allRows, outcomeFilter, actionFilter]);

  if (isLoading) {
    return (
      <div className="text-text-faint text-xs italic">加载决策日志…</div>
    );
  }
  if (error) {
    return (
      <div className="text-xs" style={{ color: 'var(--down)' }}>
        {String((error as Error)?.message || error)}
      </div>
    );
  }
  if (allRows.length === 0) {
    return <div className="text-text-faint text-xs italic">暂无决策记录</div>;
  }

  // Quick aggregate counters in the toolbar. Merge legacy 'approved' into
  // 'ok' so the chip count matches the dropdown filter.
  const counts = allRows.reduce(
    (acc, r) => {
      const key = r.outcome === 'approved' ? 'ok' : r.outcome;
      acc[key] = (acc[key] ?? 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  return (
    <div>
      <div className="flex gap-2 mb-2 flex-wrap items-center">
        <select
          className="bg-bg-2 border border-panel-border-soft rounded px-2 py-1 text-xs text-text-hi"
          value={outcomeFilter}
          onChange={(e) => setOutcomeFilter(e.target.value as OutcomeFilter)}
        >
          <option value="all">全部状态</option>
          <option value="ok">执行</option>
          <option value="modified">调整</option>
          <option value="rejected">拦截</option>
          <option value="cached">缓存</option>
          <option value="hold">持仓</option>
        </select>
        <select
          className="bg-bg-2 border border-panel-border-soft rounded px-2 py-1 text-xs text-text-hi"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value as ActionFilter)}
        >
          <option value="all">全部方向</option>
          <option value="buy">买入</option>
          <option value="sell">卖出</option>
          <option value="hold">持仓</option>
        </select>
        <span className="text-text-faint text-xs self-center">
          {filtered.length} / {allRows.length} 条
        </span>
        <span style={{ flex: 1 }} />
        <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
          ok {counts.ok ?? 0} · rej {counts.rejected ?? 0} · mod {counts.modified ?? 0} · hold {counts.hold ?? 0} · cached {counts.cached ?? 0}
        </span>
      </div>

      <div
        style={{
          border: '1px solid var(--panel-border-soft)',
          borderRadius: 4,
          overflow: 'auto',
          maxHeight: 480,
        }}
      >
        <table className="tbl" style={{ margin: 0 }}>
          <thead>
            <tr>
              <th>日期</th>
              <th>操作</th>
              <th>代码</th>
              <th className="num">LLM 想做</th>
              <th className="num">实际成交</th>
              <th>状态</th>
              <th className="num">工具</th>
              <th>原因</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, i) => {
              const requestedTxt =
                r.requested_shares != null
                  ? `${fmtShares(r.requested_shares)} @ ${fmtPrice(r.requested_price)}`
                  : '—';
              const executedTxt =
                r.executed_shares > 0
                  ? `${fmtShares(r.executed_shares)} @ ${fmtPrice(r.executed_price)}`
                  : '—';
              return (
                <tr
                  key={`${r.date}-${r.code ?? 'none'}-${r.action}-${i}`}
                  style={{
                    opacity: r.outcome === 'hold' ? 0.55 : 1,
                  }}
                >
                  <td className="mono text-xs">{r.date}</td>
                  <td>
                    <ActionCell action={r.action} />
                  </td>
                  <td className="mono text-xs">{r.code ?? '—'}</td>
                  <td className="num mono text-xs">{requestedTxt}</td>
                  <td className="num mono text-xs">
                    {executedTxt}
                    {r.executed_fee != null && r.executed_shares > 0 && (
                      <div
                        className="mono text-[10px]"
                        style={{ color: 'var(--text-ghost)' }}
                      >
                        费用 ¥{r.executed_fee.toFixed(2)}
                      </div>
                    )}
                  </td>
                  <td>
                    <OutcomeChip row={r} />
                  </td>
                  <td className="num mono text-xs text-text-faint">
                    {r.tool_calls_count}
                  </td>
                  <td
                    className="text-xs"
                    style={{
                      maxWidth: 280,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      color: 'var(--text-dim)',
                    }}
                    title={r.reasoning || undefined}
                  >
                    {r.reasoning || (
                      <span style={{ color: 'var(--text-ghost)' }}>—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
