import {
  useApprovedProposals,
  useCancelProposal,
  usePollProposalStatus,
} from '../api/hooks';
import type { TradeProposal } from '../api/types';

function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '—';
  return v.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function isCancelled(p: TradeProposal): boolean {
  return !!p.execution_order_id && p.execution_order_id.startsWith('cancelled-');
}

function isFullyFilled(p: TradeProposal): boolean {
  if (p.shares == null) return false;
  const filled = p.filled_qty ?? 0;
  return filled >= p.shares;
}

function ExecutionStatusChip({ p }: { p: TradeProposal }) {
  const baseStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    padding: '2px 8px',
    borderRadius: 3,
    fontSize: 10,
    fontFamily: 'var(--f-mono)',
    letterSpacing: '0.02em',
    whiteSpace: 'nowrap',
  };

  if (isCancelled(p)) {
    return (
      <span
        style={{
          ...baseStyle,
          background: 'var(--bg-2)',
          border: '1px solid var(--panel-border-soft)',
          color: 'var(--text-faint)',
        }}
      >
        已取消
      </span>
    );
  }

  if (p.execution_error) {
    return (
      <span
        title={p.execution_error}
        style={{
          ...baseStyle,
          background: 'var(--down-bg)',
          border: '1px solid var(--down-border)',
          color: 'var(--down)',
        }}
      >
        ✗ 执行失败
      </span>
    );
  }

  const filled = p.filled_qty ?? 0;
  const shares = p.shares ?? 0;
  const price = p.filled_price ?? p.price ?? 0;

  if (shares > 0 && filled < shares) {
    return (
      <span
        style={{
          ...baseStyle,
          background: 'var(--warn-soft, oklch(0.4 0.1 70 / 0.2))',
          border: '1px solid var(--warn)',
          color: 'var(--warn)',
        }}
      >
        部分成交 {filled.toLocaleString()}/{shares.toLocaleString()}
      </span>
    );
  }

  return (
    <span
      style={{
        ...baseStyle,
        background: 'var(--up-soft, oklch(0.4 0.1 25 / 0.2))',
        border: '1px solid var(--up-border, var(--up))',
        color: 'var(--up)',
      }}
    >
      ✓ 已成交 {filled.toLocaleString()}@¥{fmtNum(price, 2)}
    </span>
  );
}

function ApprovedProposalRow({ p }: { p: TradeProposal }) {
  const poll = usePollProposalStatus();
  const cancel = useCancelProposal();
  const pending = poll.isPending || cancel.isPending;

  const cancelled = isCancelled(p);
  const fullyFilled = isFullyFilled(p);
  const cancelDisabled = cancelled || fullyFilled || pending;
  const pollDisabled = cancelled || pending;

  const actionPillCls =
    p.action === 'buy' ? 'pill up'
    : p.action === 'sell' ? 'pill down'
    : 'pill';

  const onCancelClick = () => {
    const codeLabel = p.code ?? p.id;
    if (!confirm(`确认取消订单 ${codeLabel}？`)) return;
    cancel.mutate(p.id);
  };

  return (
    <div
      style={{
        padding: '10px 12px',
        background: 'var(--bg-3)',
        border: '1px solid var(--panel-border-soft)',
        borderRadius: 4,
      }}
    >
      <div className="flex items-baseline gap-2 mb-1 flex-wrap">
        <span className={actionPillCls} style={{ fontSize: 10 }}>
          {p.action}
        </span>
        {p.code && <span className="mono text-sm text-text-hi">{p.code}</span>}
        {p.shares != null && (
          <span className="num mono text-sm text-text-hi">
            {p.shares.toLocaleString()} 股
          </span>
        )}
        {p.price != null && (
          <span className="num mono text-sm text-text-dim">
            @ ¥{fmtNum(p.price, 2)}
          </span>
        )}
        <span style={{ flex: 1 }} />
        <span className="mono text-[10px] text-text-ghost">
          {(p.decision_at ?? '').slice(0, 19).replace('T', ' ')}
        </span>
      </div>

      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <ExecutionStatusChip p={p} />
        {p.execution_order_id && !isCancelled(p) && (
          <span className="mono text-[10px] text-text-faint">
            order: {p.execution_order_id}
          </span>
        )}
        {isCancelled(p) && p.execution_order_id && (
          <span className="mono text-[10px] text-text-faint">
            {p.execution_order_id}
          </span>
        )}
      </div>

      {p.execution_error && (
        <div
          className="text-xs mb-2"
          style={{
            color: 'var(--down)',
            padding: '4px 8px',
            background: 'var(--down-bg)',
            border: '1px solid var(--down-border)',
            borderRadius: 3,
            wordBreak: 'break-all',
          }}
        >
          {p.execution_error}
        </div>
      )}

      <div className="flex gap-2 justify-end mt-2">
        <button
          className="btn ghost"
          onClick={() => poll.mutate(p.id)}
          disabled={pollDisabled}
          style={{ padding: '3px 10px', fontSize: 11 }}
          title={cancelled ? '订单已取消，无法查询' : '从 TDX 重新获取最新成交状态'}
        >
          {poll.isPending ? '查询中…' : '查询状态'}
        </button>
        <button
          className="btn"
          onClick={onCancelClick}
          disabled={cancelDisabled}
          style={{
            padding: '3px 10px',
            fontSize: 11,
            color: cancelDisabled ? undefined : 'var(--down)',
            borderColor: cancelDisabled ? undefined : 'var(--down-border)',
            background: 'transparent',
          }}
          title={
            cancelled
              ? '订单已取消'
              : fullyFilled
                ? '订单已全部成交，无法取消'
                : '撤销 TDX 中尚未成交的部分'
          }
        >
          {cancel.isPending ? '取消中…' : '取消订单'}
        </button>
      </div>

      {(poll.isError || cancel.isError) && (
        <div className="text-xs mt-1" style={{ color: 'var(--down)' }}>
          {String(poll.error ?? cancel.error)}
        </div>
      )}
    </div>
  );
}

/**
 * ApprovedProposalsList — list approved trade proposals for a single agent
 * with poll-status + cancel-order actions.
 *
 * Props:
 *   agentId — REQUIRED; the backend rejects non-pending listings without
 *             agent_id, so this component is only rendered on the agent
 *             detail panel (never on global views like Live/Risk).
 */
export function ApprovedProposalsList({ agentId }: { agentId: string }) {
  const proposals = useApprovedProposals(agentId);

  if (proposals.isLoading) {
    return <div className="text-text-faint text-sm">加载中…</div>;
  }
  if (proposals.error) {
    return (
      <div className="text-xs" style={{ color: 'var(--down)' }}>
        {String(proposals.error)}
      </div>
    );
  }

  const rows = proposals.data ?? [];
  if (rows.length === 0) {
    return (
      <div className="text-text-faint text-sm italic">
        此 agent 暂无已批准订单
      </div>
    );
  }

  return (
    <div className="grid gap-2">
      {rows.map((p) => (
        <ApprovedProposalRow key={p.id} p={p} />
      ))}
    </div>
  );
}
