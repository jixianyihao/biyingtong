import { useState } from 'react';
import type { ThinkingDecision, ThinkingEntry } from '../api/types';

export function ThinkingDrawer({ thinking }: { thinking: ThinkingEntry[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (thinking.length === 0) {
    return (
      <div className="text-text-faint text-sm italic">
        本次回测没有 LLM 决策日志。
      </div>
    );
  }

  return (
    <div className="grid gap-2" style={{ maxHeight: 500, overflowY: 'auto' }}>
      {thinking.map((entry) => {
        const isOpen = expanded === entry.date;
        const hasContent =
          !!entry.reasoning ||
          entry.tool_calls.length > 0 ||
          entry.decisions.length > 0;
        return (
          <div
            key={entry.date}
            style={{
              background: 'var(--bg-3)',
              border: '1px solid var(--panel-border-soft)',
              borderRadius: 4,
              overflow: 'hidden',
            }}
          >
            <button
              onClick={() => setExpanded(isOpen ? null : entry.date)}
              className="w-full text-left px-3 py-2 flex items-center gap-2"
              style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
            >
              <span className="mono text-xs text-text-hi">{entry.date}</span>
              <span className="text-text-faint text-xs">
                {entry.decisions.length} 决策 · {entry.tool_calls.length} 工具
              </span>
              <span style={{ flex: 1 }} />
              <span className="text-text-faint text-xs">{isOpen ? '▲' : '▼'}</span>
            </button>
            {isOpen && hasContent && (
              <div
                className="px-3 py-2"
                style={{ borderTop: '1px solid var(--panel-border-soft)' }}
              >
                {entry.reasoning && (
                  <ReasoningBlock text={entry.reasoning} />
                )}
                {entry.tool_calls.length > 0 && (
                  <ToolCallsBlock calls={entry.tool_calls} />
                )}
                {entry.decisions.length > 0 && (
                  <DecisionsBlock decisions={entry.decisions} />
                )}
              </div>
            )}
            {isOpen && !hasContent && (
              <div
                className="px-3 py-2 text-text-faint text-xs italic"
                style={{ borderTop: '1px solid var(--panel-border-soft)' }}
              >
                (该日无决策 / 工具调用 / 推理记录)
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ReasoningBlock({ text }: { text: string }) {
  return (
    <div className="mb-3">
      <div className="text-[10px] text-text-ghost uppercase tracking-wider mb-1">
        Reasoning
      </div>
      <div
        className="text-xs text-text"
        style={{ whiteSpace: 'pre-wrap', lineHeight: 1.5 }}
      >
        {text}
      </div>
    </div>
  );
}

function ToolCallsBlock({
  calls,
}: {
  calls: Array<{ name: string; input: Record<string, unknown> }>;
}) {
  return (
    <div className="mb-3">
      <div className="text-[10px] text-text-ghost uppercase tracking-wider mb-1">
        Tool Calls
      </div>
      <div className="grid gap-1">
        {calls.map((tc, i) => (
          <div
            key={i}
            className="mono text-[11px]"
            style={{
              padding: '4px 8px',
              background: 'var(--bg-2)',
              borderRadius: 3,
              wordBreak: 'break-all',
            }}
          >
            <span className="text-brand">{tc.name}</span>
            <span className="text-text-faint">
              {' '}
              ({JSON.stringify(tc.input)})
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function DecisionsBlock({ decisions }: { decisions: ThinkingDecision[] }) {
  return (
    <div>
      <div className="text-[10px] text-text-ghost uppercase tracking-wider mb-1">
        Decisions
      </div>
      <div className="grid gap-1">
        {decisions.map((d, i) => (
          <DecisionRow key={i} decision={d} />
        ))}
      </div>
    </div>
  );
}

function DecisionRow({ decision: d }: { decision: ThinkingDecision }) {
  const actionPillCls =
    d.action === 'buy' ? 'pill up' : d.action === 'sell' ? 'pill down' : 'pill';
  const outcomeStyle: React.CSSProperties =
    d.outcome === 'rejected'
      ? { background: 'var(--down-bg)', color: 'var(--down)' }
      : d.outcome === 'cached'
        ? { background: 'var(--bg-2)', color: 'var(--text-faint)', opacity: 0.6 }
        : { background: 'var(--bg-2)', color: 'var(--text-faint)' };

  return (
    <div
      className="text-xs flex items-center gap-2 flex-wrap"
      style={{
        padding: '4px 8px',
        background: 'var(--bg-2)',
        borderRadius: 3,
      }}
    >
      <span className={actionPillCls} style={{ fontSize: 9 }}>
        {d.action}
      </span>
      {d.code && <span className="mono">{d.code}</span>}
      {d.shares != null && <span className="num mono">{d.shares}股</span>}
      {d.price != null && <span className="num mono">¥{d.price.toFixed(2)}</span>}
      {d.outcome && (
        <span className="pill" style={{ fontSize: 9, ...outcomeStyle }}>
          {d.outcome}
        </span>
      )}
      {d.reasoning && (
        <span
          className="text-text-faint italic"
          style={{ minWidth: 0, flex: 1 }}
        >
          {d.reasoning}
        </span>
      )}
    </div>
  );
}
