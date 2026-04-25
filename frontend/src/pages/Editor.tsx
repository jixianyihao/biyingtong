// NOTE: This page is awaiting Phase 3 backend.
// All previously-baked iteration trajectory data, the deterministic seedable
// PRNG that faked equity curves, the placeholder VNPy CtaTemplate strategy
// code, the sample agent-step timeline and token/cost metrics have been
// removed. The page chrome (banner, header, brief panel, tabs, agent
// timeline shell) is retained so the layout remains visible until
// /api/strategy-iterations and the code-gen endpoint are wired up.
import { useState } from 'react';
import { Icon } from '../components/Icon';

// ─── types ─────────────────────────────────────────────────────────────────
type Tab = 'iter' | 'code' | 'report';

// ─── page ──────────────────────────────────────────────────────────────────
export function Editor() {
  const [tab, setTab] = useState<Tab>('iter');

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Phase-3 banner */}
      <div
        className="text-xs flex items-center gap-2"
        style={{
          padding: '8px 16px',
          background: 'var(--brand-soft)',
          borderBottom: '1px solid var(--brand-border)',
          color: 'var(--brand)',
        }}
      >
        <Icon name="code" size={12} />
        <span>代码自动生成接入在 Phase 3 · AI code-gen backend arrives in Phase 3</span>
      </div>

      <div className="px-6 pt-5 pb-3">
        <h1 className="text-2xl text-text-hi font-semibold">策略研发</h1>
        <div className="text-text-faint text-xs mt-1 tracking-wide uppercase">
          Strategy Editor · AI-driven Iterative R&amp;D
        </div>
      </div>

      <div
        className="flex-1 min-h-0 grid gap-3 px-3 pb-3"
        style={{ gridTemplateColumns: 'minmax(0,1fr) 420px' }}
      >
        {/* LEFT: main working area */}
        <div className="flex flex-col gap-3 min-w-0">
          {/* Brief */}
          <div className="panel" style={{ padding: 14 }}>
            <div className="flex items-center gap-2.5 mb-2">
              <Icon name="filter" size={13} className="text-brand" />
              <span
                className="uppercase"
                style={{
                  fontSize: 11,
                  color: 'var(--text-faint)',
                  letterSpacing: '0.12em',
                }}
              >
                策略需求 · Brief
              </span>
              <span className="flex-1" />
              <button className="btn ghost" style={{ padding: '3px 8px' }} disabled>
                运行
              </button>
            </div>
            <div
              style={{
                fontSize: 12,
                color: 'var(--text-ghost)',
                padding: '8px 0 0 8px',
                borderLeft: '2px solid var(--panel-border-soft)',
              }}
            >
              代码生成接入 Phase 3 · 输入框尚未启用
            </div>
          </div>

          {/* Tabs */}
          <div className="panel flex-1 min-h-0 flex flex-col">
            <div className="panel-head">
              <span className="flex gap-0.5">
                {(
                  [
                    ['iter', '迭代过程'],
                    ['code', '最终稳定代码'],
                    ['report', '自动化报告'],
                  ] as Array<[Tab, string]>
                ).map(([k, l]) => (
                  <span
                    key={k}
                    onClick={() => setTab(k)}
                    className="flex items-center gap-1.5 cursor-pointer"
                    style={{
                      padding: '6px 14px',
                      fontSize: 12,
                      color: tab === k ? 'var(--text-hi)' : 'var(--text-faint)',
                      borderBottom:
                        '2px solid ' +
                        (tab === k ? 'var(--brand)' : 'transparent'),
                      marginBottom: -9,
                      fontWeight: tab === k ? 600 : 400,
                    }}
                  >
                    {l}
                  </span>
                ))}
              </span>
              <span className="flex-1" />
            </div>

            <EmptyTab />
          </div>
        </div>

        {/* RIGHT: agent timeline shell */}
        <AgentTimelineEmpty />
      </div>
    </div>
  );
}

// ─── shared empty state for iter / code / report tabs ──────────────────────
function EmptyTab() {
  return (
    <div
      className="flex-1 flex items-center justify-center"
      style={{ padding: 24 }}
    >
      <div style={{ textAlign: 'center', maxWidth: 380 }}>
        <div
          style={{
            fontSize: 13,
            color: 'var(--text)',
            marginBottom: 6,
          }}
        >
          尚无迭代数据 · 等待后端
        </div>
        <div
          className="uppercase"
          style={{
            fontSize: 10.5,
            color: 'var(--text-faint)',
            letterSpacing: '0.1em',
          }}
        >
          Phase 3 code-gen backend pending
        </div>
      </div>
    </div>
  );
}

// ─── Right-side Agent activity timeline (empty) ────────────────────────────
function AgentTimelineEmpty() {
  return (
    <div className="panel flex flex-col min-h-0">
      <div className="panel-head">
        <Icon name="filter" size={11} className="text-brand" />
        <span className="panel-title">Agent 工作流</span>
        <span className="flex-1" />
      </div>
      <div
        className="flex-1 flex items-center justify-center"
        style={{ padding: 24 }}
      >
        <div style={{ textAlign: 'center', maxWidth: 280 }}>
          <div style={{ fontSize: 12, color: 'var(--text)', marginBottom: 6 }}>
            尚无 Agent 活动
          </div>
          <div
            className="uppercase"
            style={{
              fontSize: 10.5,
              color: 'var(--text-faint)',
              letterSpacing: '0.1em',
            }}
          >
            Awaiting backend
          </div>
        </div>
      </div>
    </div>
  );
}
