import { useMemo, useState } from 'react';
import { useAgents, useAuditQuery } from '../api/hooks';
import type { AuditRow } from '../api/types';

// ─── constants ─────────────────────────────────────────────────────────────
const KIND_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'validation', label: 'validation · 决策校验' },
  { value: 'warning', label: 'warning · 告警' },
  { value: 'trade_executed', label: 'trade_executed · 成交' },
  { value: 'trade_blocked', label: 'trade_blocked · 阻断' },
  { value: 'error', label: 'error · 错误' },
  { value: 'redline_changed', label: 'redline_changed · 红线变更' },
  { value: 'agent_deployed', label: 'agent_deployed · 部署' },
  { value: 'parse_failure', label: 'parse_failure · 解析失败' },
];

type KindTone = 'brand' | 'up' | 'down' | 'info' | 'warn' | 'ghost';

const KIND_TONE: Record<string, KindTone> = {
  validation: 'info',
  warning: 'warn',
  trade_executed: 'up',
  trade_blocked: 'down',
  error: 'down',
  redline_changed: 'brand',
  agent_deployed: 'info',
  parse_failure: 'warn',
};

// ─── helpers ───────────────────────────────────────────────────────────────
function fmtTimestamp(ts: string): string {
  return ts.replace('T', ' ').replace(/\..*$/, '').replace(/Z$/, '');
}

function kindChipClass(kind: string): string {
  const tone = KIND_TONE[kind] ?? 'ghost';
  if (tone === 'up') return 'pill up';
  if (tone === 'down') return 'pill down';
  if (tone === 'brand') return 'pill brand';
  if (tone === 'info') return 'pill info';
  if (tone === 'warn') {
    return 'pill';
  }
  return 'pill';
}

function summarize(row: AuditRow): string {
  const d = row.details ?? {};
  // Best-effort one-line summary across common audit-kind shapes
  if (row.kind === 'validation') {
    const rule = (d.rule_id as string) ?? '';
    const reason = (d.reason as string) ?? '';
    const outcome = (d.outcome as string) ?? '';
    return `[${outcome || '—'}] ${rule}${reason ? ' · ' + reason : ''}`;
  }
  if (row.kind === 'redline_changed') {
    const before = d.before as Record<string, unknown> | undefined;
    const after = d.after as Record<string, unknown> | undefined;
    if (before && after) {
      const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
      const diffs: string[] = [];
      keys.forEach((k) => {
        if (before[k] !== after[k]) {
          diffs.push(`${k}: ${String(before[k])}→${String(after[k])}`);
        }
      });
      return diffs.length === 0 ? '（无字段变化）' : diffs.slice(0, 3).join(' · ') + (diffs.length > 3 ? ` (+${diffs.length - 3})` : '');
    }
  }
  if (row.kind === 'trade_executed' || row.kind === 'trade_blocked') {
    const sym = (d.symbol as string) ?? (d.ticker as string) ?? '';
    const qty = d.qty ?? d.shares ?? '';
    const price = d.price ?? '';
    const side = (d.side as string) ?? '';
    if (sym) return `${side || ''} ${sym} ${qty ? '× ' + qty : ''} ${price ? '@ ' + price : ''}`.trim();
  }
  if (row.kind === 'agent_deployed') {
    return `persona=${row.persona_id ?? '?'} · model=${row.model_id ?? '?'}`;
  }
  if (row.kind === 'error' || row.kind === 'parse_failure' || row.kind === 'warning') {
    const msg = (d.message as string) ?? (d.reason as string) ?? (d.error as string) ?? '';
    return msg || '—';
  }
  // fallback: show up to 3 keys
  const keys = Object.keys(d).slice(0, 3);
  if (keys.length === 0) return '—';
  return keys.map((k) => `${k}=${JSON.stringify(d[k])}`).join(' · ').slice(0, 160);
}

// ─── sub-components ────────────────────────────────────────────────────────
function FilterBar({
  agentId,
  kind,
  limit,
  onApply,
  agents,
  pending,
}: {
  agentId: string;
  kind: string;
  limit: number;
  onApply: (next: { agentId: string; kind: string; limit: number }) => void;
  agents: ReturnType<typeof useAgents>;
  pending: boolean;
}) {
  const [draftAgent, setDraftAgent] = useState(agentId);
  const [draftKind, setDraftKind] = useState(kind);
  const [draftLimit, setDraftLimit] = useState(limit);

  const agentList = agents.data ?? [];

  const inputCls =
    'bg-bg-2 border border-panel-border-soft rounded px-3 py-2 text-sm text-text-hi focus:outline-none focus:border-brand transition-colors';

  return (
    <div className="panel p-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col">
          <label className="block text-[11px] uppercase tracking-wider text-text-faint mb-1">
            Agent · 操盘手
          </label>
          <select
            className={`${inputCls} min-w-[220px]`}
            value={draftAgent}
            onChange={(e) => setDraftAgent(e.target.value)}
            disabled={agents.isLoading}
          >
            <option value="">（全部 Agent）</option>
            {agentList.map((a) => (
              <option key={a.id} value={a.id}>
                {a.display_name} — {a.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col">
          <label className="block text-[11px] uppercase tracking-wider text-text-faint mb-1">
            Kind · 事件类型
          </label>
          <select
            className={`${inputCls} min-w-[220px]`}
            value={draftKind}
            onChange={(e) => setDraftKind(e.target.value)}
          >
            <option value="">（全部 Kind）</option>
            {KIND_OPTIONS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col">
          <label className="block text-[11px] uppercase tracking-wider text-text-faint mb-1">
            Limit
          </label>
          <input
            type="number"
            min={10}
            max={500}
            step={10}
            className={`${inputCls} mono w-[90px]`}
            value={draftLimit}
            onChange={(e) => setDraftLimit(Number(e.target.value) || 100)}
          />
        </div>

        <div className="flex items-center gap-2 ml-auto">
          {pending && (
            <span className="text-[10px] text-text-faint italic">
              <span className="live-dot" style={{ color: 'var(--info)' }} /> 刷新中
            </span>
          )}
          <button
            className="btn primary"
            onClick={() => {
              if (!draftAgent && !draftKind) {
                // Backend requires at least one of agent_id/kind; default to validation.
                onApply({ agentId: draftAgent, kind: 'validation', limit: draftLimit });
                setDraftKind('validation');
                return;
              }
              onApply({ agentId: draftAgent, kind: draftKind, limit: draftLimit });
            }}
          >
            Apply · 应用
          </button>
        </div>
      </div>
      <div className="text-[10px] text-text-ghost mt-2">
        自动每 10 秒刷新 · 后端需要 agent_id 或 kind 之一，默认使用 kind=validation。
      </div>
    </div>
  );
}

function AuditRowCard({ row }: { row: AuditRow }) {
  const [open, setOpen] = useState(false);
  const chip = kindChipClass(row.kind);
  return (
    <div
      className="border border-panel-border-soft rounded bg-bg-1 hover:bg-bg-2 transition-colors"
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 px-3 py-2 text-left"
        style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
      >
        <span className="mono text-[10px] text-text-ghost w-[140px] flex-shrink-0">
          {fmtTimestamp(row.timestamp)}
        </span>
        <span className={chip} style={{ fontSize: 10, minWidth: 110, justifyContent: 'center' }}>
          {row.kind}
        </span>
        <span className="mono text-[11px] text-text-dim w-[90px] flex-shrink-0 truncate">
          {row.agent_id ? row.agent_id.slice(0, 8) : '—'}
        </span>
        <span className="text-xs text-text flex-1 truncate">{summarize(row)}</span>
        <span className="mono text-[10px] text-text-faint">
          {open ? '▼' : '▶'}
        </span>
      </button>
      {open && (
        <div className="px-4 pb-3 pt-1 border-t border-panel-border-soft">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3 text-[11px]">
            <div>
              <div className="text-text-faint uppercase tracking-wider text-[9px] mb-1">
                audit id
              </div>
              <div className="mono text-text">{row.id}</div>
            </div>
            <div>
              <div className="text-text-faint uppercase tracking-wider text-[9px] mb-1">
                agent_id
              </div>
              <div className="mono text-text break-all">{row.agent_id ?? '—'}</div>
            </div>
            <div>
              <div className="text-text-faint uppercase tracking-wider text-[9px] mb-1">
                persona_id
              </div>
              <div className="mono text-text">{row.persona_id ?? '—'}</div>
            </div>
            <div>
              <div className="text-text-faint uppercase tracking-wider text-[9px] mb-1">
                model_id
              </div>
              <div className="mono text-text">{row.model_id ?? '—'}</div>
            </div>
          </div>
          <div className="text-[9px] text-text-faint uppercase tracking-wider mb-1">
            details
          </div>
          <pre
            className="mono text-[11px] text-text bg-bg-2 p-3 rounded border border-panel-border-soft overflow-auto max-h-[320px]"
            style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
          >
            {JSON.stringify(row.details ?? {}, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

// ─── page ──────────────────────────────────────────────────────────────────
export function Audit() {
  // Backend requires either agent_id or kind. Start with kind=validation.
  const [filters, setFilters] = useState<{ agentId: string; kind: string; limit: number }>({
    agentId: '',
    kind: 'validation',
    limit: 100,
  });

  const agents = useAgents();
  const audit = useAuditQuery(
    {
      agent_id: filters.agentId || undefined,
      kind: filters.kind || undefined,
      limit: filters.limit,
    },
    { refetchInterval: 10000 },
  );

  const rows = useMemo(() => {
    const r = audit.data ?? [];
    // Sort newest first by timestamp (backend likely already does, but guarantee)
    return [...r].sort((a, b) => (a.timestamp < b.timestamp ? 1 : a.timestamp > b.timestamp ? -1 : b.id - a.id));
  }, [audit.data]);

  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-2xl text-text-hi font-semibold">审计日志</h1>
        <div className="text-text-faint text-xs mt-1 tracking-wide uppercase">
          Audit Log · 100% 留痕 · 可追溯
        </div>
      </div>

      <div className="grid gap-5">
        <FilterBar
          agentId={filters.agentId}
          kind={filters.kind}
          limit={filters.limit}
          agents={agents}
          pending={audit.isFetching}
          onApply={(next) =>
            setFilters({ agentId: next.agentId, kind: next.kind, limit: next.limit })
          }
        />

        <div className="panel p-4">
          <div className="flex items-baseline gap-2 mb-3 flex-wrap">
            <h2 className="text-text-hi text-base font-semibold">时间线</h2>
            <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
              Timeline · newest first
            </span>
            <span className="ml-auto mono text-[10px] text-text-faint">
              {rows.length} 条
            </span>
          </div>

          {audit.isLoading && (
            <div className="text-text-faint text-sm italic py-6 text-center">
              加载中…
            </div>
          )}

          {audit.isError && (
            <div
              className="text-sm"
              style={{
                padding: 10,
                borderRadius: 4,
                background: 'var(--down-bg)',
                border: '1px solid var(--down-border)',
                color: 'var(--down)',
              }}
            >
              加载失败：{audit.error instanceof Error ? audit.error.message : String(audit.error)}
            </div>
          )}

          {!audit.isLoading && !audit.isError && rows.length === 0 && (
            <div className="text-text-faint text-sm italic py-6 text-center">
              未找到匹配的审计记录。
            </div>
          )}

          {rows.length > 0 && (
            <div className="flex flex-col gap-2">
              {rows.map((row) => (
                <AuditRowCard key={row.id} row={row} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
