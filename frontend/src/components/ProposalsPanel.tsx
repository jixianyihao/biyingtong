import { useEffect, useState } from 'react';
import {
  useApproveProposal,
  useExecutionMode,
  useProposals,
  useRejectProposal,
} from '../api/hooks';
import type { TradeProposal } from '../api/types';
import { LiveApproveModal } from './LiveApproveModal';

const RESULT_BANNER_MS = 6000;

function ExecutionResultBanner({ p, onDismiss }: { p: TradeProposal; onDismiss: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDismiss, RESULT_BANNER_MS);
    return () => clearTimeout(t);
  }, [p.id, onDismiss]);

  const isLive = p.execution_mode === 'live';
  const isError = !!p.execution_error;
  const tag = isError ? '❌ ERROR' : isLive ? '✓ LIVE' : '✓ DRY-RUN';
  const tagColor = isError ? 'var(--down)' : isLive ? '#ef4444' : 'var(--text-dim)';
  const code = p.code ?? '';
  const action = p.action ?? '';
  const filled = p.filled_qty ?? p.shares ?? 0;
  const price = p.filled_price ?? p.price ?? 0;
  const orderId = p.execution_order_id ?? '—';

  return (
    <div
      style={{
        padding: '8px 10px',
        background: 'var(--bg-2)',
        border: `1px solid ${isError ? 'var(--down-border)' : 'var(--panel-border-soft)'}`,
        borderRadius: 4,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        flexWrap: 'wrap',
      }}
    >
      <span className="mono text-[10px] uppercase tracking-wider" style={{ color: tagColor }}>
        {tag}
      </span>
      <span className="mono text-xs text-text-hi">
        {action} {code} {filled.toLocaleString()}@¥{price.toFixed(2)}
      </span>
      <span className="mono text-[10px] text-text-faint">order: {orderId}</span>
      {isError && (
        <span className="text-xs" style={{ color: 'var(--down)' }}>
          {p.execution_error}
        </span>
      )}
      <span style={{ flex: 1 }} />
      <button
        className="btn"
        onClick={onDismiss}
        style={{ padding: '1px 6px', fontSize: 10, background: 'transparent' }}
      >
        ×
      </button>
    </div>
  );
}

function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '—';
  return v.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function ProposalRow({
  p,
  isLive,
  onRequestLiveApprove,
  onApproved,
}: {
  p: TradeProposal;
  isLive: boolean;
  onRequestLiveApprove: (p: TradeProposal) => void;
  onApproved: (result: TradeProposal) => void;
}) {
  const approve = useApproveProposal();
  const reject = useRejectProposal();
  const pending = approve.isPending || reject.isPending;
  const actionPillCls =
    p.action === 'buy' ? 'pill up'
    : p.action === 'sell' ? 'pill down'
    : 'pill';

  // Dry-run: click fires mutation directly (Phase-1 behaviour).
  // Live: click opens the LiveApproveModal — the parent owns the modal
  // state and, on confirm, triggers the mutation there.
  const handleApproveClick = () => {
    if (isLive) {
      onRequestLiveApprove(p);
    } else {
      approve.mutate(p.id, {
        onSuccess: (data) => onApproved(data),
      });
    }
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
          onClick={handleApproveClick}
          disabled={pending}
          style={{ padding: '3px 12px', fontSize: 11 }}
          title={
            isLive
              ? '⚠ LIVE: 点击后需在弹窗输入“确认下单”方能提交真实订单'
              : 'DRY-RUN: 批准仅改数据库状态，不会真实下单'
          }
        >
          {approve.isPending ? '批准中…' : isLive ? '批准 (LIVE)' : '批准'}
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
 * Phase-2 behaviour:
 *   - DRY-RUN mode (default, BIYINGTONG_EXECUTION_MODE unset/dry_run):
 *     approve fires directly, adapter returns mock fill, no TDX call.
 *   - LIVE mode (BIYINGTONG_EXECUTION_MODE=live): approve opens
 *     <LiveApproveModal/> which requires typed "确认下单" confirmation
 *     BEFORE dispatching the mutation. Backdrop/cancel dismisses.
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
  const executionMode = useExecutionMode();
  const approve = useApproveProposal();
  const isLive = executionMode.data?.mode === 'live';

  // Modal state lives here (not in ProposalRow) so only one modal exists
  // at a time regardless of how many proposal rows are on screen.
  const [modalFor, setModalFor] = useState<TradeProposal | null>(null);
  // Last approve result — surfaced as a transient banner so the user gets
  // feedback even after the row disappears from the pending list on refetch.
  const [lastResult, setLastResult] = useState<TradeProposal | null>(null);

  const closeModal = () => setModalFor(null);
  const confirmLiveApprove = () => {
    if (!modalFor) return;
    approve.mutate(modalFor.id, {
      onSuccess: (data) => {
        setLastResult(data);
        closeModal();
      },
      onError: () => closeModal(),
    });
  };

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
    <>
      <div className="grid gap-2">
        <div className="text-[10px] text-text-ghost uppercase tracking-wider">
          {isLive
            ? '⚠ LIVE：批准将向通达信提交真实订单（需二次确认）。'
            : '⚠ DRY-RUN：批准仅改数据库状态，不会真实下单到 TDX。'}
        </div>
        {lastResult && (
          <ExecutionResultBanner
            p={lastResult}
            onDismiss={() => setLastResult(null)}
          />
        )}
        {rows.map((p) => (
          <ProposalRow
            key={p.id}
            p={p}
            isLive={isLive}
            onRequestLiveApprove={setModalFor}
            onApproved={setLastResult}
          />
        ))}
      </div>
      {modalFor && (
        <LiveApproveModal
          proposal={modalFor}
          onConfirm={confirmLiveApprove}
          onCancel={closeModal}
          isSubmitting={approve.isPending}
        />
      )}
    </>
  );
}
