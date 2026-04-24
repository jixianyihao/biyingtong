import type React from 'react';
import { useState } from 'react';
import type { TradeProposal } from '../api/types';

/**
 * The exact confirmation phrase the user must type. SAFETY CRITICAL —
 * changing this constant is a review-gate change because this string is the
 * last line of defence against accidental LIVE orders. Keep the comparison
 * strict equality (no trim / no lowercase); we WANT typos to fail.
 */
const REQUIRED_PHRASE = '确认下单';

/**
 * LiveApproveModal — 2-step confirmation gate for LIVE-mode proposal
 * approval.
 *
 * Flow:
 *   1. Modal appears with a red warning banner + proposal summary.
 *   2. User must type `确认下单` EXACTLY into the input. Only then does
 *      the submit button enable.
 *   3. On submit, onConfirm() fires the real approve mutation.
 *   4. onCancel() fires on backdrop click, Cancel button, or Escape.
 *
 * Caller contract: the modal does NOT know about mutations. ProposalsPanel
 * owns the mutation state and decides when to mount/unmount this component.
 */
export function LiveApproveModal({
  proposal,
  onConfirm,
  onCancel,
  isSubmitting = false,
}: {
  proposal: TradeProposal;
  onConfirm: () => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}) {
  const [typed, setTyped] = useState('');
  // STRICT equality — typos must block submission. Do not .trim() here.
  const canSubmit = typed === REQUIRED_PHRASE && !isSubmitting;
  const estAmount = (proposal.shares ?? 0) * (proposal.price ?? 0);

  return (
    <div style={overlayStyle} onClick={onCancel}>
      <div
        className="panel"
        style={dialogStyle}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-text-hi text-base font-semibold mb-1">
          提交真实订单
        </h2>
        <div className="mono text-[10px] text-text-faint uppercase tracking-wider mb-3">
          LIVE TRADING · 通达信 place_order
        </div>

        <div
          className="mb-4 text-sm"
          style={{
            padding: '10px 12px',
            borderRadius: 4,
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            color: '#fca5a5',
          }}
        >
          ⚠ 此操作会向通达信提交真实订单，<b>不可撤销</b>。
        </div>

        <table className="w-full text-sm mb-4">
          <tbody>
            <tr>
              <td className="py-1 text-text-dim" style={{ width: 72 }}>
                代码
              </td>
              <td className="mono text-text-hi">{proposal.code ?? '—'}</td>
            </tr>
            <tr>
              <td className="py-1 text-text-dim">方向</td>
              <td
                className="mono"
                style={{
                  color:
                    proposal.action === 'buy'
                      ? 'var(--up)'
                      : proposal.action === 'sell'
                      ? 'var(--down)'
                      : 'var(--text-dim)',
                }}
              >
                {proposal.action === 'buy'
                  ? '买入'
                  : proposal.action === 'sell'
                  ? '卖出'
                  : proposal.action}
              </td>
            </tr>
            <tr>
              <td className="py-1 text-text-dim">数量</td>
              <td className="mono num text-text-hi">
                {proposal.shares?.toLocaleString() ?? '—'} 股
              </td>
            </tr>
            <tr>
              <td className="py-1 text-text-dim">价格</td>
              <td className="mono num text-text-hi">
                ¥ {proposal.price?.toFixed(2) ?? '—'}
              </td>
            </tr>
            <tr>
              <td className="py-1 text-text-dim">预估金额</td>
              <td className="mono num text-text-hi font-semibold">
                ¥ {estAmount.toFixed(2)}
              </td>
            </tr>
          </tbody>
        </table>

        <label className="block text-xs text-text-dim mb-2">
          请输入{' '}
          <code
            className="mono px-1"
            style={{
              color: '#fca5a5',
              background: 'rgba(239, 68, 68, 0.12)',
              borderRadius: 2,
            }}
          >
            {REQUIRED_PHRASE}
          </code>{' '}
          以继续：
        </label>
        <input
          type="text"
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          placeholder={REQUIRED_PHRASE}
          autoFocus
          disabled={isSubmitting}
          className="w-full bg-bg-2 border border-panel-border-soft rounded px-3 py-2 text-sm text-text-hi mono mb-4"
        />

        <div className="flex gap-2 justify-end">
          <button
            className="btn"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            disabled={!canSubmit}
            className="btn"
            style={{
              padding: '4px 14px',
              fontSize: 12,
              background: canSubmit
                ? 'rgba(239, 68, 68, 0.8)'
                : 'var(--bg-2)',
              color: canSubmit ? '#fff' : 'var(--text-faint)',
              borderColor: canSubmit
                ? 'rgba(239, 68, 68, 1)'
                : 'var(--panel-border-soft)',
              cursor: canSubmit ? 'pointer' : 'not-allowed',
            }}
            title={
              canSubmit
                ? '提交真实订单'
                : `请先输入 "${REQUIRED_PHRASE}"`
            }
          >
            {isSubmitting ? '提交中…' : '确认提交'}
          </button>
        </div>
      </div>
    </div>
  );
}

const overlayStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.6)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000,
};

const dialogStyle: React.CSSProperties = {
  width: 'min(520px, 92vw)',
  maxHeight: '90vh',
  overflowY: 'auto',
  padding: '20px 24px',
};
