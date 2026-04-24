import { useProposals, useApproveProposal, useRejectProposal } from '../api/hooks';
import type { TradeProposal } from '../api/types';

function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '—';
  return v.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function ProposalRow({ p }: { p: TradeProposal }) {
  const approve = useApproveProposal();
  const reject = useRejectProposal();
  const pending = approve.isPending || reject.isPending;
  const actionPillCls =
    p.action === 'buy' ? 'pill up'
    : p.action === 'sell' ? 'pill down'
    : 'pill';

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

      <div className="mono text-[10px] text-text-faint mb-2">
        agent: {p.agent_id}
      </div>

      {p.reason && (
        <div className="text-xs text-text-dim mb-2" style={{ lineHeight: 1.5 }}>
          <span className="text-text-ghost mono uppercase mr-1" style={{ fontSize: 9 }}>
            reason
          </span>
          {p.reason}
        </div>
      )}

      {p.thinking && (
        <details className="mb-2">
          <summary
            className="text-[10px] text-text-ghost uppercase tracking-wider cursor-pointer"
            style={{ letterSpacing: '0.08em' }}
          >
            Thinking
          </summary>
          <div
            className="text-xs text-text mt-1"
            style={{
              whiteSpace: 'pre-wrap',
              lineHeight: 1.5,
              padding: '6px 8px',
              background: 'var(--bg-2)',
              borderRadius: 3,
            }}
          >
            {p.thinking}
          </div>
        </details>
      )}

      <div className="flex gap-2 justify-end mt-2">
        <button
          className="btn"
          onClick={() => reject.mutate(p.id)}
          disabled={pending}
          style={{
            padding: '3px 10px',
            fontSize: 11,
            color: 'var(--down)',
            borderColor: 'var(--down-border)',
            background: 'transparent',
          }}
        >
          {reject.isPending ? '拒绝中…' : '拒绝'}
        </button>
        <button
          className="btn primary"
          onClick={() => approve.mutate(p.id)}
          disabled={pending}
          style={{ padding: '3px 12px', fontSize: 11 }}
          title="Phase 1: 批准仅改数据库状态，不会真实下单"
        >
          {approve.isPending ? '批准中…' : '批准'}
        </button>
      </div>

      {(approve.isError || reject.isError) && (
        <div className="text-xs mt-1" style={{ color: 'var(--down)' }}>
          {String(approve.error ?? reject.error)}
        </div>
      )}
    </div>
  );
}

/**
 * ProposalsPanel — list pending trade proposals with approve/reject actions.
 *
 * Phase 1 CRITICAL: approve ONLY flips DB status → 'approved'. No real TDX
 * order is placed. Phase 2 (separate consent) wires the execution path.
 *
 * Props:
 *   agentId (optional) — filter to a specific agent; omit for global inbox.
 */
export function ProposalsPanel({ agentId }: { agentId?: string }) {
  const proposals = useProposals({
    status: 'pending',
    agent_id: agentId,
    limit: 100,
  });

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
        {agentId ? '此 agent 暂无待审批的提议。' : '暂无待审批的交易提议。'}
      </div>
    );
  }

  return (
    <div className="grid gap-2">
      <div className="text-[10px] text-text-ghost uppercase tracking-wider">
        ⚠ Phase 1：批准 / 拒绝仅改数据库状态，不会真实下单到 TDX。
      </div>
      {rows.map((p) => (
        <ProposalRow key={p.id} p={p} />
      ))}
    </div>
  );
}
