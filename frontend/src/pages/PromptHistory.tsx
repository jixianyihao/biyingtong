import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  useAgent,
  useAgentPromptVersions,
  useModels,
  usePersonas,
} from '../api/hooks';
import type { PromptVersion } from '../api/types';

// ─── helpers ───────────────────────────────────────────────────────────────
function formatRelative(ts: string | null): string {
  if (!ts) return '—';
  const d = new Date(ts.replace(' ', 'T'));
  if (Number.isNaN(d.getTime())) return ts;
  const diffSec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  const days = Math.floor(diffSec / 86400);
  if (days < 30) return `${days}d ago`;
  return d.toISOString().slice(0, 10);
}

function formatFull(ts: string | null): string {
  if (!ts) return '—';
  return ts.replace('T', ' ').replace(/\..*$/, '').replace(/Z$/, '');
}

function truncate(s: string | null, n = 40): string {
  if (!s) return '';
  if (s.length <= n) return s;
  return s.slice(0, n - 1) + '…';
}

// Primitive line diff: classify each line in the new text as
// 'added' | 'same' compared to the previous version's lines (set-based).
type DiffLine = { kind: 'same' | 'added' | 'removed'; text: string };

function diffLines(prev: string, curr: string): {
  left: DiffLine[];
  right: DiffLine[];
} {
  const prevLines = prev.split('\n');
  const currLines = curr.split('\n');
  const prevSet = new Set(prevLines);
  const currSet = new Set(currLines);
  const left: DiffLine[] = prevLines.map((t) => ({
    kind: currSet.has(t) ? 'same' : 'removed',
    text: t,
  }));
  const right: DiffLine[] = currLines.map((t) => ({
    kind: prevSet.has(t) ? 'same' : 'added',
    text: t,
  }));
  return { left, right };
}

// ─── sub-components ────────────────────────────────────────────────────────
function VersionListItem({
  v,
  selected,
  isCurrent,
  onClick,
}: {
  v: PromptVersion;
  selected: boolean;
  isCurrent: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left px-3 py-2.5 border-b transition-colors"
      style={{
        borderColor: 'var(--panel-border-soft)',
        background: selected ? 'var(--bg-hover)' : 'transparent',
        borderLeft: selected
          ? '2px solid var(--brand)'
          : '2px solid transparent',
      }}
    >
      <div className="flex items-center gap-2 mb-1">
        <span
          className="mono text-[12px] font-semibold"
          style={{ color: selected ? 'var(--brand)' : 'var(--text-hi)' }}
        >
          v{v.version_number}
        </span>
        {isCurrent && (
          <>
            <span
              className="inline-block rounded-full"
              style={{
                width: 6,
                height: 6,
                background: 'var(--brand)',
              }}
            />
            <span
              className="mono text-[10px] uppercase tracking-wider"
              style={{ color: 'var(--brand)' }}
            >
              当前 · Current
            </span>
          </>
        )}
        <span style={{ flex: 1 }} />
        <span className="mono text-[10px] text-text-faint">
          {formatRelative(v.created_at)}
        </span>
      </div>
      <div className="text-[11.5px] text-text-faint leading-snug">
        {v.note ? truncate(v.note, 60) : (
          <span className="italic text-text-ghost">（无备注）</span>
        )}
      </div>
    </button>
  );
}

function DiffColumn({
  title,
  lines,
}: {
  title: string;
  lines: DiffLine[];
}) {
  return (
    <div className="flex-1 min-w-0">
      <div className="text-[10px] text-text-faint uppercase tracking-[0.1em] mb-1">
        {title}
      </div>
      <pre
        className="mono bg-bg-2 border border-panel-border-soft rounded p-2 text-[11px] whitespace-pre-wrap overflow-auto"
        style={{ margin: 0, maxHeight: '64vh', lineHeight: 1.65 }}
      >
        {lines.map((ln, i) => {
          let bg = 'transparent';
          let color = 'var(--text)';
          if (ln.kind === 'added') {
            bg = 'var(--up-bg)';
            color = 'var(--up)';
          } else if (ln.kind === 'removed') {
            bg = 'var(--down-bg)';
            color = 'var(--down)';
          }
          return (
            <div
              key={i}
              style={{
                background: bg,
                color,
                padding: '0 4px',
                minHeight: '1.4em',
              }}
            >
              {ln.text || ' '}
            </div>
          );
        })}
      </pre>
    </div>
  );
}

// ─── main page ─────────────────────────────────────────────────────────────
export function PromptHistory() {
  const { agentId } = useParams<{ agentId: string }>();
  const agentQ = useAgent(agentId);
  const versionsQ = useAgentPromptVersions(agentId);
  const personasQ = usePersonas();
  const modelsQ = useModels();

  const versions = useMemo(
    () => (versionsQ.data ?? []).slice().sort((a, b) => a.version_number - b.version_number),
    [versionsQ.data],
  );

  // Default to latest version (last item)
  const [selectedVN, setSelectedVN] = useState<number | null>(null);
  const [showDiff, setShowDiff] = useState(false);

  const effectiveSelectedVN = selectedVN ?? (versions.length > 0 ? versions[versions.length - 1].version_number : null);
  const selected = versions.find((v) => v.version_number === effectiveSelectedVN) ?? null;
  const previous = selected
    ? versions.find((v) => v.version_number === selected.version_number - 1) ?? null
    : null;

  const agent = agentQ.data;
  const persona = personasQ.data?.find((p) => p.id === agent?.persona_id);
  const model = modelsQ.data?.find((m) => m.id === agent?.model_id);

  // Match the current prompt_version_id
  const currentPromptVersionId = agent ? agent.current_prompt_version_id : null;

  const isLoading = agentQ.isLoading || versionsQ.isLoading;
  const error = agentQ.error || versionsQ.error;

  return (
    <div className="p-5 flex flex-col gap-4 min-h-full">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-text-hi font-semibold" style={{ fontSize: 18, margin: 0 }}>
          Prompt 版本历史
        </h1>
        <span className="mono text-[11px] text-text-faint uppercase tracking-[0.12em]">
          Prompt Version History
        </span>
        <span style={{ flex: 1 }} />
        <Link
          to="/agent"
          className="btn ghost"
          style={{ padding: '4px 12px', fontSize: 12, textDecoration: 'none' }}
        >
          ← 返回 Agent · Back
        </Link>
      </div>

      {/* Error / loading states */}
      {error && (
        <div
          className="text-sm p-3 rounded"
          style={{
            background: 'var(--down-bg)',
            border: '1px solid var(--down-border)',
            color: 'var(--down)',
          }}
        >
          加载失败 · {error instanceof Error ? error.message : String(error)}
        </div>
      )}
      {isLoading && !error && (
        <div className="text-text-faint text-sm">加载中 · Loading…</div>
      )}

      {/* Agent summary */}
      {agent && (
        <div className="panel p-4">
          <div className="flex flex-wrap items-baseline gap-3">
            <div className="text-text-hi text-base font-semibold">
              {agent.display_name}
            </div>
            <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
              {agent.id}
            </span>
            <span style={{ flex: 1 }} />
            <div className="flex flex-wrap gap-3 text-[12px] text-text-faint">
              <span>
                Persona ·{' '}
                <span className="text-text-hi">
                  {persona?.name ?? agent.persona_id}
                </span>
              </span>
              <span>
                Model ·{' '}
                <span className="text-text-hi">
                  {model?.display_name ?? agent.model_id}
                </span>
              </span>
              <span>
                Versions ·{' '}
                <span className="text-text-hi mono">{versions.length}</span>
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Main 2-pane area */}
      {agent && versions.length > 0 && selected && (
        <div
          className="panel flex overflow-hidden"
          style={{ minHeight: '68vh' }}
        >
          {/* Left pane: list */}
          <div
            className="flex flex-col overflow-auto"
            style={{
              width: '30%',
              minWidth: 220,
              borderRight: '1px solid var(--panel-border-soft)',
            }}
          >
            <div className="panel-head" style={{ position: 'sticky', top: 0 }}>
              <span className="panel-title">版本列表 · Versions</span>
              <span style={{ flex: 1 }} />
              <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
                {versions.length}
              </span>
            </div>
            {versions.map((v) => {
              const isCurrent =
                currentPromptVersionId != null &&
                String(v.id) === String(currentPromptVersionId);
              return (
                <VersionListItem
                  key={v.id}
                  v={v}
                  selected={v.version_number === effectiveSelectedVN}
                  isCurrent={isCurrent}
                  onClick={() => {
                    setSelectedVN(v.version_number);
                    setShowDiff(false);
                  }}
                />
              );
            })}
          </div>

          {/* Right pane: detail */}
          <div className="flex-1 flex flex-col min-w-0 overflow-auto">
            <div className="panel-head">
              <span className="panel-title">
                v{selected.version_number} · System Prompt
              </span>
              <span style={{ flex: 1 }} />
              {previous && (
                <button
                  onClick={() => setShowDiff((x) => !x)}
                  className={`btn${showDiff ? ' primary' : ' ghost'}`}
                  style={{ padding: '2px 10px', fontSize: 12 }}
                >
                  {showDiff
                    ? '隐藏对比 · Hide Diff'
                    : '与上一版对比 · vs Previous'}
                </button>
              )}
            </div>
            <div className="p-4 flex flex-col gap-3">
              {/* Meta row */}
              <div className="flex flex-wrap gap-4 text-[12px]">
                <div>
                  <div className="text-[10px] text-text-faint uppercase tracking-[0.1em] mb-0.5">
                    版本号 · Version
                  </div>
                  <div className="mono text-text-hi">
                    v{selected.version_number}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-text-faint uppercase tracking-[0.1em] mb-0.5">
                    创建时间 · Created
                  </div>
                  <div className="mono text-text-hi">
                    {formatFull(selected.created_at)}
                  </div>
                </div>
                <div className="flex-1 min-w-[200px]">
                  <div className="text-[10px] text-text-faint uppercase tracking-[0.1em] mb-0.5">
                    备注 · Note
                  </div>
                  <div className="text-text">
                    {selected.note || (
                      <span className="italic text-text-ghost">（无）</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Content or diff */}
              {showDiff && previous ? (
                <div className="flex gap-3 min-w-0">
                  <DiffColumn
                    title={`v${previous.version_number} · Previous`}
                    lines={diffLines(previous.system_prompt, selected.system_prompt).left}
                  />
                  <DiffColumn
                    title={`v${selected.version_number} · Selected`}
                    lines={diffLines(previous.system_prompt, selected.system_prompt).right}
                  />
                </div>
              ) : (
                <pre
                  className="mono border border-panel-border-soft rounded p-3 text-[11.5px] text-text whitespace-pre-wrap overflow-auto"
                  style={{
                    background: 'var(--bg-2)',
                    margin: 0,
                    maxHeight: '64vh',
                    lineHeight: 1.65,
                  }}
                >
                  {selected.system_prompt}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {agent && versions.length === 0 && !isLoading && (
        <div className="panel p-5 text-text-faint text-sm">
          暂无 Prompt 版本 · No prompt versions recorded
        </div>
      )}
    </div>
  );
}
