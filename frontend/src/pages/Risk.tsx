import { useMemo, useState } from 'react';
import { useAuditQuery, useRedlines, useUpdateRedlines } from '../api/hooks';
import type { AuditRow } from '../api/types';

// ─── key groupings of the RedLine dict ─────────────────────────────────────
type NumericKey =
  | 'daily_loss_max_pct'
  | 'position_max_pct'
  | 'stock_concentration'
  | 'order_max_value'
  | 'turnover_max_daily'
  | 'same_stock_cooldown_min'
  | 'cash_min_pct';

type BoolKey =
  | 'ban_limit_up'
  | 'ban_st'
  | 'ban_limit_down'
  | 'ban_ipo_30d'
  | 'require_reason'
  | 'prompt_injection_check'
  | 'auto_halt_var_2sigma';

type RuleKind = 'hard' | 'soft';

type NumericRow = {
  key: NumericKey;
  label: string;
  unit: string;
  kind: RuleKind;
  direction: 'upper' | 'lower';
};

type BoolRow = {
  key: BoolKey;
  label: string;
  hint: string;
  kind: RuleKind;
};

const CAPITAL_RULES: NumericRow[] = [
  { key: 'daily_loss_max_pct', label: '单日最大亏损', unit: '%', kind: 'hard', direction: 'upper' },
  { key: 'position_max_pct', label: '单笔最大仓位', unit: '% 总资金', kind: 'hard', direction: 'upper' },
  { key: 'stock_concentration', label: '单股集中度', unit: '%', kind: 'soft', direction: 'upper' },
  { key: 'cash_min_pct', label: '最低现金比例', unit: '%', kind: 'hard', direction: 'lower' },
];

const TRADE_RULES: NumericRow[] = [
  { key: 'order_max_value', label: '单笔下单金额', unit: '¥', kind: 'hard', direction: 'upper' },
  { key: 'turnover_max_daily', label: '日内最大换手', unit: '%', kind: 'soft', direction: 'upper' },
  { key: 'same_stock_cooldown_min', label: '同票冷却期', unit: '分钟', kind: 'soft', direction: 'lower' },
];

const BEHAVIOR_RULES: BoolRow[] = [
  { key: 'ban_limit_up', label: '禁止涨停追入', hint: '避免追高', kind: 'hard' },
  { key: 'ban_limit_down', label: '禁止跌停买入', hint: '避免接飞刀', kind: 'hard' },
  { key: 'ban_st', label: '黑名单 ST / *ST', hint: '退市风险', kind: 'hard' },
  { key: 'ban_ipo_30d', label: '禁止新股 (30天)', hint: '次新股波动', kind: 'hard' },
  { key: 'require_reason', label: '决策必填理由', hint: '可审计', kind: 'soft' },
  { key: 'prompt_injection_check', label: 'Prompt 注入检测', hint: '过滤可疑输入', kind: 'hard' },
  { key: 'auto_halt_var_2sigma', label: '异常波动熔断', hint: 'VaR 超 2σ 自动暂停', kind: 'hard' },
];

// ─── helpers ───────────────────────────────────────────────────────────────
function fmtNumeric(key: NumericKey, v: unknown): string {
  if (v == null) return '—';
  if (typeof v !== 'number') return String(v);
  if (key === 'order_max_value') return `¥${v.toLocaleString('en-US')}`;
  if (key === 'same_stock_cooldown_min') return `${v} min`;
  return `${v}%`;
}

function fmtTimestamp(ts: string): string {
  // ISO-ish string → keep the "YYYY-MM-DD HH:MM:SS" slice if present, else full.
  return ts.replace('T', ' ').replace(/\..*$/, '').replace(/Z$/, '');
}

function outcomeChip(outcome: string | undefined): { cls: string; label: string } {
  if (outcome === 'rejected') return { cls: 'pill down', label: '✕ 已阻断' };
  if (outcome === 'modified') return { cls: 'pill', label: '⚠ 已修改' };
  if (outcome === 'approved') return { cls: 'pill up', label: '✓ 通过' };
  return { cls: 'pill', label: outcome || '—' };
}

// ─── sub-panels ────────────────────────────────────────────────────────────
function SectionHeader({ zh, en, extra }: { zh: string; en: string; extra?: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-2 mb-3 flex-wrap">
      <h2 className="text-text-hi text-base font-semibold">{zh}</h2>
      <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">{en}</span>
      {extra ? <span className="ml-auto">{extra}</span> : null}
    </div>
  );
}

function LayeredProtection() {
  const layers: Array<{
    tag: string;
    name: string;
    zh: string;
    en: string;
    desc: string;
    scope: string;
    tone: 'brand' | 'info' | 'warn';
  }> = [
    {
      tag: 'L1',
      name: 'RedLine',
      zh: '全局红线',
      en: 'Global Redlines',
      desc: '系统级不可跨越上限，单例配置',
      scope: 'Global · Immutable ceiling',
      tone: 'brand',
    },
    {
      tag: 'L2',
      name: 'rules_override',
      zh: 'Agent 覆写',
      en: 'Per-agent Override',
      desc: '单个 Agent 可将红线收紧（仅 stricter）',
      scope: 'Per-agent · Stricter only',
      tone: 'info',
    },
    {
      tag: 'L3',
      name: 'Validation',
      zh: '决策前校验',
      en: 'Per-decision Check',
      desc: '每一笔下单经过处理器链逐项判定',
      scope: 'Per-decision · 15 rules',
      tone: 'warn',
    },
  ];

  const toneVars: Record<'brand' | 'info' | 'warn', { bar: string; txt: string }> = {
    brand: { bar: 'bg-brand', txt: 'text-brand' },
    info: { bar: 'bg-[var(--info)]', txt: 'text-[var(--info)]' },
    warn: { bar: 'bg-[var(--warn)]', txt: 'text-[var(--warn)]' },
  };

  return (
    <div className="panel p-5">
      <SectionHeader zh="三层防护架构" en="Layered Protection" extra={<span className="pill brand">RedLine → override → validation</span>} />
      <div className="grid grid-cols-3 gap-3">
        {layers.map((l, i) => {
          const tone = toneVars[l.tone];
          return (
            <div
              key={l.tag}
              className="relative p-4 bg-bg-2 border border-panel-border-soft rounded"
            >
              <div className={`absolute left-0 top-2 bottom-2 w-1 ${tone.bar} rounded-r`} />
              <div className="pl-2">
                <div className="flex items-baseline gap-2 mb-1">
                  <span className={`mono text-[10px] ${tone.txt} uppercase tracking-wider`}>
                    {l.tag}
                  </span>
                  <span className="text-text-hi text-sm font-semibold">{l.zh}</span>
                </div>
                <div className="mono text-[10px] text-text-ghost uppercase tracking-wider mb-2">
                  {l.en}
                </div>
                <div className="text-xs text-text leading-relaxed mb-2">{l.desc}</div>
                <div className="mono text-[10px] text-text-faint">{l.scope}</div>
              </div>
              {i < layers.length - 1 && (
                <div className="hidden md:flex absolute -right-3 top-1/2 -translate-y-1/2 w-5 h-5 items-center justify-center bg-bg-3 border border-panel-border-soft rounded-full text-text-faint text-[10px] z-10">
                  →
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function KindBadge({ kind }: { kind: RuleKind }) {
  const cls =
    kind === 'hard'
      ? 'text-[var(--up)] border-[var(--up)]'
      : 'text-[var(--warn)] border-[var(--warn)]';
  return (
    <span
      className={`mono text-[9px] px-1 py-[1px] border rounded uppercase tracking-wider ${cls}`}
    >
      {kind}
    </span>
  );
}

function RedlineConfigPanel({
  data,
  loading,
  onEdit,
}: {
  data: Record<string, unknown> | undefined;
  loading: boolean;
  onEdit: () => void;
}) {
  if (loading) {
    return (
      <div className="panel p-5">
        <SectionHeader zh="全局红线" en="RedLine Config" />
        <div className="text-text-faint text-sm italic">加载中…</div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="panel p-5">
        <SectionHeader zh="全局红线" en="RedLine Config" />
        <div className="text-text-faint text-sm">无红线配置。</div>
      </div>
    );
  }

  return (
    <div className="panel p-5">
      <SectionHeader
        zh="全局红线"
        en="RedLine Config"
        extra={
          <div className="flex gap-2 items-center">
            <span className="pill up">15/15 已启用</span>
            <button
              className="btn ghost text-xs"
              onClick={onEdit}
              title="修改全局红线（PUT /api/redlines）"
            >
              编辑
            </button>
          </div>
        }
      />
      <div className="grid md:grid-cols-3 gap-3">
        {/* 资金防护 */}
        <div className="p-3 bg-bg-2 border border-panel-border-soft rounded">
          <div className="flex items-center gap-2 pb-2 mb-2 border-b border-panel-border-soft">
            <div className="w-1 h-3.5 bg-brand" />
            <span className="text-text-hi text-sm font-semibold">资金防护</span>
            <span className="mono text-[10px] text-text-ghost uppercase tracking-wider ml-auto">
              Capital
            </span>
          </div>
          {CAPITAL_RULES.map((r) => (
            <div key={r.key} className="flex items-center gap-2 py-1 text-xs">
              <span className="text-[var(--up)] text-[10px]">✓</span>
              <span className="text-text flex-1 truncate">{r.label}</span>
              <span className="mono text-text-faint text-[11px]">
                {r.direction === 'upper' ? '≤ ' : '≥ '}
                {fmtNumeric(r.key, data[r.key])}
              </span>
              <KindBadge kind={r.kind} />
            </div>
          ))}
        </div>

        {/* 交易防护 */}
        <div className="p-3 bg-bg-2 border border-panel-border-soft rounded">
          <div className="flex items-center gap-2 pb-2 mb-2 border-b border-panel-border-soft">
            <div className="w-1 h-3.5 bg-brand" />
            <span className="text-text-hi text-sm font-semibold">交易防护</span>
            <span className="mono text-[10px] text-text-ghost uppercase tracking-wider ml-auto">
              Trading
            </span>
          </div>
          {TRADE_RULES.map((r) => (
            <div key={r.key} className="flex items-center gap-2 py-1 text-xs">
              <span className="text-[var(--up)] text-[10px]">✓</span>
              <span className="text-text flex-1 truncate">{r.label}</span>
              <span className="mono text-text-faint text-[11px]">
                {r.direction === 'upper' ? '≤ ' : '≥ '}
                {fmtNumeric(r.key, data[r.key])}
              </span>
              <KindBadge kind={r.kind} />
            </div>
          ))}
        </div>

        {/* Agent 行为 */}
        <div className="p-3 bg-bg-2 border border-panel-border-soft rounded">
          <div className="flex items-center gap-2 pb-2 mb-2 border-b border-panel-border-soft">
            <div className="w-1 h-3.5 bg-brand" />
            <span className="text-text-hi text-sm font-semibold">Agent 行为</span>
            <span className="mono text-[10px] text-text-ghost uppercase tracking-wider ml-auto">
              Behavior
            </span>
          </div>
          {BEHAVIOR_RULES.map((r) => {
            const on = Boolean(data[r.key]);
            return (
              <div key={r.key} className="flex items-center gap-2 py-1 text-xs">
                <span
                  className={`w-3.5 h-3.5 rounded-sm flex items-center justify-center text-[9px] flex-shrink-0 ${
                    on
                      ? 'bg-[var(--up-bg)] border border-[var(--up)] text-[var(--up)]'
                      : 'bg-bg-3 border border-panel-border text-text-ghost'
                  }`}
                >
                  {on ? '✓' : ''}
                </span>
                <span className="text-text flex-1 truncate">{r.label}</span>
                <span className="mono text-[10px] text-text-faint truncate max-w-[90px]">
                  {r.hint}
                </span>
                <KindBadge kind={r.kind} />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// Shape of validation-audit details as emitted by backend handlers.
type ValidationDetails = {
  outcome?: string;
  rule_id?: string;
  reason?: string;
  severity?: string;
};

function ViolationsPanel({ rows, loading }: { rows: AuditRow[] | undefined; loading: boolean }) {
  const filtered = useMemo(() => {
    const r = rows ?? [];
    return r
      .filter((row) => {
        const d = row.details as ValidationDetails;
        return d?.outcome === 'rejected' || d?.outcome === 'modified';
      })
      .slice(0, 20);
  }, [rows]);

  return (
    <div className="panel p-5">
      <SectionHeader
        zh="近期违规拦截"
        en="Recent Violations"
        extra={
          <span className="pill down">
            <span className="live-dot" /> {filtered.length} 条
          </span>
        }
      />
      {loading && <div className="text-text-faint text-sm italic">加载中…</div>}
      {!loading && filtered.length === 0 && (
        <div className="text-text-faint text-sm italic">暂无违规记录。</div>
      )}
      {!loading && filtered.length > 0 && (
        <div className="border border-panel-border-soft rounded overflow-hidden">
          <table className="tbl">
            <thead>
              <tr>
                <th>时间</th>
                <th>Agent</th>
                <th>规则</th>
                <th>结果</th>
                <th>原因</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => {
                const d = (row.details ?? {}) as ValidationDetails;
                const chip = outcomeChip(d.outcome);
                return (
                  <tr key={row.id}>
                    <td className="mono text-[10px] text-text-ghost">
                      {fmtTimestamp(row.timestamp)}
                    </td>
                    <td className="mono text-[11px] text-text-hi">
                      {row.agent_id ? row.agent_id.slice(0, 8) : '—'}
                    </td>
                    <td className="mono text-[11px] text-[var(--info)]">
                      {d.rule_id ?? '—'}
                    </td>
                    <td>
                      <span className={chip.cls} style={{ fontSize: 10 }}>
                        {chip.label}
                      </span>
                    </td>
                    <td className="text-xs text-text-dim">{d.reason ?? '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

type RedlineChangedDetails = {
  before?: Record<string, unknown>;
  after?: Record<string, unknown>;
};

function diffKeys(
  before: Record<string, unknown> | undefined,
  after: Record<string, unknown> | undefined,
): Array<{ key: string; from: unknown; to: unknown }> {
  if (!before || !after) return [];
  const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
  const out: Array<{ key: string; from: unknown; to: unknown }> = [];
  keys.forEach((k) => {
    if (before[k] !== after[k]) out.push({ key: k, from: before[k], to: after[k] });
  });
  return out;
}

function RedlineHistoryPanel({ rows, loading }: { rows: AuditRow[] | undefined; loading: boolean }) {
  return (
    <div className="panel p-5">
      <SectionHeader
        zh="红线变更历史"
        en="RedLine Changes"
        extra={
          <span className="pill">
            <span className="live-dot" style={{ color: 'var(--info)' }} /> audit trail
          </span>
        }
      />
      {loading && <div className="text-text-faint text-sm italic">加载中…</div>}
      {!loading && (!rows || rows.length === 0) && (
        <div className="text-text-faint text-sm italic">未曾修改红线。</div>
      )}
      {!loading && rows && rows.length > 0 && (
        <div className="flex flex-col gap-2 max-h-[380px] overflow-auto pr-1">
          {rows.slice(0, 25).map((row) => {
            const d = (row.details ?? {}) as RedlineChangedDetails;
            const diffs = diffKeys(d.before, d.after);
            return (
              <div
                key={row.id}
                className="p-3 bg-bg-2 border border-panel-border-soft rounded"
              >
                <div className="flex items-baseline gap-2 mb-2">
                  <span className="mono text-[10px] text-text-ghost">
                    {fmtTimestamp(row.timestamp)}
                  </span>
                  <span className="pill info" style={{ fontSize: 9.5 }}>
                    redline_changed
                  </span>
                  <span className="ml-auto text-[10px] text-text-faint">
                    {diffs.length} 项变更
                  </span>
                </div>
                {diffs.length === 0 && (
                  <div className="text-xs text-text-faint">（无字段变化）</div>
                )}
                {diffs.length > 0 && (
                  <div className="grid gap-1">
                    {diffs.map((d2) => (
                      <div key={d2.key} className="flex items-center gap-2 text-xs">
                        <span className="mono text-text-dim truncate max-w-[160px]">{d2.key}</span>
                        <span className="mono text-text-ghost">
                          {String(d2.from)}
                        </span>
                        <span className="text-text-faint">→</span>
                        <span className="mono text-text-hi">{String(d2.to)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── edit modal ────────────────────────────────────────────────────────────
type FormVal = number | boolean;
type FormState = Record<string, FormVal>;

function numericStep(key: NumericKey): number {
  if (key === 'order_max_value') return 1000;
  if (key === 'same_stock_cooldown_min') return 1;
  // daily_loss_max_pct / position_max_pct / stock_concentration /
  // turnover_max_daily / cash_min_pct — all percentages
  return 0.1;
}

function numericSuffix(key: NumericKey, unit: string): string {
  // unit column in NumericRow already holds "%", "¥", "% 总资金", "分钟" — keep consistent
  if (key === 'order_max_value') return '¥';
  if (key === 'same_stock_cooldown_min') return 'min';
  return unit.includes('%') ? '%' : unit;
}

function validateNumeric(key: NumericKey, raw: number): string | null {
  if (!Number.isFinite(raw)) return '必须是数字';
  if (raw < 0) return '不可为负';
  if (key === 'cash_min_pct' && raw >= 100) return '必须 < 100';
  // percentages sanity: reject > 100 for pct bounds except turnover_max_daily which is intentionally unbounded
  if (
    (key === 'daily_loss_max_pct' ||
      key === 'position_max_pct' ||
      key === 'stock_concentration') &&
    raw > 100
  ) {
    return '百分比不可 > 100';
  }
  return null;
}

function fmtDiffValue(key: string, v: unknown): string {
  if (typeof v === 'boolean') return v ? 'ON' : 'OFF';
  if (typeof v === 'number') {
    if (key === 'order_max_value') return `¥${v.toLocaleString('en-US')}`;
    if (key === 'same_stock_cooldown_min') return `${v} min`;
    return `${v}%`;
  }
  return String(v);
}

function RedlineEditModal({
  current,
  onClose,
}: {
  current: Record<string, unknown>;
  onClose: () => void;
}) {
  const mut = useUpdateRedlines();

  // Build initial form state from current config (cast to numeric/bool per DEFAULT).
  const initial = useMemo<FormState>(() => {
    const s: FormState = {};
    [...CAPITAL_RULES, ...TRADE_RULES].forEach((r) => {
      const v = current[r.key];
      s[r.key] = typeof v === 'number' ? v : 0;
    });
    BEHAVIOR_RULES.forEach((r) => {
      s[r.key] = Boolean(current[r.key]);
    });
    return s;
  }, [current]);

  const [form, setForm] = useState<FormState>(initial);
  const [submitErr, setSubmitErr] = useState<string | null>(null);

  // Per-field validation errors (numeric only).
  const errors = useMemo<Record<string, string>>(() => {
    const out: Record<string, string> = {};
    [...CAPITAL_RULES, ...TRADE_RULES].forEach((r) => {
      const v = form[r.key];
      if (typeof v !== 'number') {
        out[r.key] = '必须是数字';
        return;
      }
      const err = validateNumeric(r.key, v);
      if (err) out[r.key] = err;
    });
    return out;
  }, [form]);

  // Compute diff vs current config for preview + partial PUT body.
  const diffs = useMemo(() => {
    const out: Array<{ key: string; from: unknown; to: FormVal }> = [];
    Object.entries(form).forEach(([k, v]) => {
      const cur = current[k];
      // Compare: numeric uses strict equality, bool too.
      if (typeof v === 'number' && typeof cur === 'number') {
        if (v !== cur) out.push({ key: k, from: cur, to: v });
      } else if (typeof v === 'boolean') {
        if (v !== Boolean(cur)) out.push({ key: k, from: Boolean(cur), to: v });
      }
    });
    return out;
  }, [form, current]);

  const hasErrors = Object.keys(errors).length > 0;
  const canSave = diffs.length > 0 && !hasErrors && !mut.isPending;

  async function handleSave() {
    if (!canSave) return;
    setSubmitErr(null);
    const body: Record<string, FormVal> = {};
    diffs.forEach((d) => {
      body[d.key] = d.to;
    });
    try {
      await mut.mutateAsync(body);
      // Hook's onSuccess invalidates ['redlines'] + ['audit'] — closes modal.
      onClose();
    } catch (e) {
      setSubmitErr(e instanceof Error ? e.message : String(e));
    }
  }

  function setNum(key: NumericKey, raw: string) {
    const n = raw === '' ? NaN : Number(raw);
    setForm((s) => ({ ...s, [key]: n }));
  }

  function setBool(key: BoolKey, v: boolean) {
    setForm((s) => ({ ...s, [key]: v }));
  }

  const sectionHeadCls =
    'flex items-center gap-2 pb-2 mb-3 border-b border-panel-border-soft';

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center p-10"
      style={{ background: 'oklch(0 0 0 / 0.65)' }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="panel flex flex-col"
        style={{
          width: 720,
          maxHeight: '86vh',
          boxShadow: '0 16px 48px oklch(0 0 0 / 0.7)',
        }}
      >
        {/* Header */}
        <div className="panel-head">
          <span className="panel-title">编辑全局红线</span>
          <span className="mono text-[10px] text-text-ghost tracking-wider uppercase ml-1">
            Edit RedLines · PUT /api/redlines
          </span>
          <span style={{ flex: 1 }} />
          <button
            className="btn ghost"
            onClick={onClose}
            style={{ padding: '2px 10px', fontSize: 14, lineHeight: 1 }}
            aria-label="关闭"
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div className="p-4 overflow-auto flex flex-col gap-4">
          {/* 资金防护 */}
          <div>
            <div className={sectionHeadCls}>
              <div className="w-1 h-3.5 bg-brand" />
              <span className="text-text-hi text-sm font-semibold">资金防护</span>
              <span className="mono text-[10px] text-text-ghost uppercase tracking-wider ml-auto">
                Capital
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {CAPITAL_RULES.map((r) => {
                const val = form[r.key];
                const err = errors[r.key];
                return (
                  <div key={r.key} className="flex flex-col gap-1">
                    <label className="flex items-baseline gap-2 text-xs">
                      <span className="text-text flex-1 truncate">{r.label}</span>
                      <KindBadge kind={r.kind} />
                      <span className="mono text-[10px] text-text-ghost">
                        {r.direction === 'upper' ? '≤' : '≥'}
                      </span>
                    </label>
                    <div className="flex items-center gap-1.5">
                      <input
                        type="number"
                        step={numericStep(r.key)}
                        min={0}
                        value={typeof val === 'number' && !Number.isNaN(val) ? val : ''}
                        onChange={(e) => setNum(r.key, e.target.value)}
                        className={`flex-1 bg-bg-2 border rounded px-2 py-1.5 text-sm mono text-text-hi focus:outline-none focus:border-brand transition-colors ${
                          err ? 'border-[var(--down)]' : 'border-panel-border-soft'
                        }`}
                      />
                      <span className="mono text-[10px] text-text-ghost w-10 text-right">
                        {numericSuffix(r.key, r.unit)}
                      </span>
                    </div>
                    {err && (
                      <div className="text-[10px] text-[var(--down)] mono">{err}</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* 交易防护 */}
          <div>
            <div className={sectionHeadCls}>
              <div className="w-1 h-3.5 bg-brand" />
              <span className="text-text-hi text-sm font-semibold">交易防护</span>
              <span className="mono text-[10px] text-text-ghost uppercase tracking-wider ml-auto">
                Trading
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {TRADE_RULES.map((r) => {
                const val = form[r.key];
                const err = errors[r.key];
                return (
                  <div key={r.key} className="flex flex-col gap-1">
                    <label className="flex items-baseline gap-2 text-xs">
                      <span className="text-text flex-1 truncate">{r.label}</span>
                      <KindBadge kind={r.kind} />
                      <span className="mono text-[10px] text-text-ghost">
                        {r.direction === 'upper' ? '≤' : '≥'}
                      </span>
                    </label>
                    <div className="flex items-center gap-1.5">
                      <input
                        type="number"
                        step={numericStep(r.key)}
                        min={0}
                        value={typeof val === 'number' && !Number.isNaN(val) ? val : ''}
                        onChange={(e) => setNum(r.key, e.target.value)}
                        className={`flex-1 bg-bg-2 border rounded px-2 py-1.5 text-sm mono text-text-hi focus:outline-none focus:border-brand transition-colors ${
                          err ? 'border-[var(--down)]' : 'border-panel-border-soft'
                        }`}
                      />
                      <span className="mono text-[10px] text-text-ghost w-10 text-right">
                        {numericSuffix(r.key, r.unit)}
                      </span>
                    </div>
                    {err && (
                      <div className="text-[10px] text-[var(--down)] mono">{err}</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Agent 行为 */}
          <div>
            <div className={sectionHeadCls}>
              <div className="w-1 h-3.5 bg-brand" />
              <span className="text-text-hi text-sm font-semibold">Agent 行为</span>
              <span className="mono text-[10px] text-text-ghost uppercase tracking-wider ml-auto">
                Behavior
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {BEHAVIOR_RULES.map((r) => {
                const on = Boolean(form[r.key]);
                return (
                  <label
                    key={r.key}
                    className="flex items-center gap-2 p-2 bg-bg-2 border border-panel-border-soft rounded cursor-pointer text-xs"
                  >
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={(e) => setBool(r.key, e.target.checked)}
                      className="flex-shrink-0"
                    />
                    <span className="text-text flex-1 truncate">{r.label}</span>
                    <span className="mono text-[10px] text-text-faint truncate max-w-[90px]">
                      {r.hint}
                    </span>
                    <KindBadge kind={r.kind} />
                  </label>
                );
              })}
            </div>
          </div>

          {/* 变更预览 */}
          <div>
            <div className={sectionHeadCls}>
              <div className="w-1 h-3.5 bg-[var(--info)]" />
              <span className="text-text-hi text-sm font-semibold">变更预览</span>
              <span className="mono text-[10px] text-text-ghost uppercase tracking-wider ml-auto">
                Change Preview · {diffs.length} 项
              </span>
            </div>
            {diffs.length === 0 ? (
              <div className="text-text-faint text-xs italic px-1">
                暂无改动 —— 修改字段后将在此处预览。
              </div>
            ) : (
              <div className="grid gap-1 p-2 bg-bg-2 border border-panel-border-soft rounded">
                {diffs.map((d) => (
                  <div key={d.key} className="flex items-center gap-2 text-xs">
                    <span className="mono text-text-dim truncate w-[190px]">{d.key}</span>
                    <span className="mono text-text-ghost">
                      {fmtDiffValue(d.key, d.from)}
                    </span>
                    <span className="text-text-faint">→</span>
                    <span className="mono text-text-hi">
                      {fmtDiffValue(d.key, d.to)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Error banner */}
          {submitErr && (
            <div
              className="text-sm text-down p-3 rounded"
              style={{
                background: 'var(--down-bg)',
                border: '1px solid var(--down-border)',
                color: 'var(--down)',
              }}
            >
              保存失败：{submitErr}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="flex items-center gap-2 px-4 py-3 border-t"
          style={{ borderColor: 'var(--panel-border-soft)' }}
        >
          <span className="mono text-[10px] text-text-faint">
            {hasErrors
              ? '请先修复校验错误'
              : diffs.length === 0
                ? '无改动'
                : `${diffs.length} 项变更待保存`}
          </span>
          <span style={{ flex: 1 }} />
          <button
            className="btn ghost"
            onClick={onClose}
            disabled={mut.isPending}
            style={{ fontSize: 12 }}
          >
            取消
          </button>
          <button
            className="btn primary"
            onClick={handleSave}
            disabled={!canSave}
            style={{
              fontSize: 12,
              opacity: canSave ? 1 : 0.5,
              cursor: canSave ? 'pointer' : 'not-allowed',
            }}
          >
            {mut.isPending ? '保存中…' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── page ──────────────────────────────────────────────────────────────────
export function Risk() {
  const redlines = useRedlines();
  const validationAudit = useAuditQuery(
    { kind: 'validation', limit: 200 },
    { refetchInterval: 10000 },
  );
  const redlineChangedAudit = useAuditQuery(
    { kind: 'redline_changed', limit: 50 },
    { refetchInterval: 10000 },
  );

  const [editing, setEditing] = useState(false);

  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-2xl text-text-hi font-semibold">安全管控</h1>
        <div className="text-text-faint text-xs mt-1 tracking-wide uppercase">
          Safety · RedLine · Audit
        </div>
      </div>

      <div className="grid gap-5">
        <LayeredProtection />

        <RedlineConfigPanel
          data={redlines.data}
          loading={redlines.isLoading}
          onEdit={() => setEditing(true)}
        />

        <div className="grid gap-5" style={{ gridTemplateColumns: '2fr 1fr' }}>
          <ViolationsPanel rows={validationAudit.data} loading={validationAudit.isLoading} />
          <RedlineHistoryPanel
            rows={redlineChangedAudit.data}
            loading={redlineChangedAudit.isLoading}
          />
        </div>
      </div>

      {editing && redlines.data && (
        <RedlineEditModal
          current={redlines.data}
          onClose={() => setEditing(false)}
        />
      )}
    </div>
  );
}
