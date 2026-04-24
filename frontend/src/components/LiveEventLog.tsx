import type { BacktestEvent } from '../api/types';

const MAX_ROWS = 200;

function formatTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString('en-US', { hour12: false });
}

function shortId(s: string | undefined, n = 12): string {
  if (!s) return '';
  return s.length <= n ? s : s.slice(0, n) + '…';
}

function renderSummary(e: BacktestEvent): { badge: string; text: string; color: string } {
  switch (e.kind) {
    case 'phase':
      return { badge: 'phase', text: e.phase, color: 'var(--brand)' };
    case 'progress':
      return {
        badge: 'progress',
        text: `${shortId(e.agent_id)} · ${e.date} · equity ${(e.equity ?? 0).toFixed(0)} · ${(e.pnl_pct ?? 0).toFixed(2)}%`,
        color: 'var(--text-dim)',
      };
    case 'tool_call':
      return {
        badge: 'tool',
        text: `${shortId(e.agent_id)} · ${e.date} · ${e.tool_name}`,
        color: 'var(--text-hi)',
      };
    case 'decision': {
      const priceStr = e.price != null ? `@ ${e.price.toFixed(2)}` : '';
      return {
        badge: 'decision',
        text: `${shortId(e.agent_id)} · ${e.date} · ${e.action} ${e.code ?? ''} ${e.shares ?? ''} ${priceStr} · ${e.outcome}`,
        color: 'var(--up)',
      };
    }
    case 'blocked':
      return {
        badge: 'blocked',
        text: `${shortId(e.agent_id)} · ${e.date} · blocked: ${e.reason}`,
        color: 'var(--down)',
      };
    case 'baseline_done':
      return {
        badge: 'baseline',
        text: `${e.baseline_name} done`,
        color: 'var(--text-faint)',
      };
    case 'done':
      return { badge: 'done', text: 'session complete', color: 'var(--brand)' };
    default:
      return { badge: 'event', text: JSON.stringify(e), color: 'var(--text-faint)' };
  }
}

export function LiveEventLog({ events }: { events: BacktestEvent[] }) {
  if (events.length === 0) {
    return (
      <div className="text-text-faint text-xs italic">
        正在等待事件…
      </div>
    );
  }
  const trimmed = events.slice(-MAX_ROWS);
  return (
    <div
      className="grid gap-0.5"
      style={{
        maxHeight: 280, overflowY: 'auto',
        border: '1px solid var(--panel-border-soft)',
        borderRadius: 4, padding: '6px 8px',
        background: 'var(--bg-3)',
        fontSize: 11,
      }}
    >
      {trimmed.map((e, i) => {
        const { badge, text, color } = renderSummary(e);
        return (
          <div key={i} className="flex gap-2 items-baseline mono">
            <span className="text-text-ghost" style={{ fontSize: 10 }}>
              {formatTime(e.ts)}
            </span>
            <span
              style={{
                padding: '1px 6px', borderRadius: 2, fontSize: 9,
                background: 'var(--bg-2)', color,
                minWidth: 64, textAlign: 'center',
              }}
            >
              {badge}
            </span>
            <span className="text-text-dim" style={{ wordBreak: 'break-word' }}>
              {text}
            </span>
          </div>
        );
      })}
    </div>
  );
}
