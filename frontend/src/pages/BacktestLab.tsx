import { useEffect, useState } from 'react';
import {
  useCreateAgent,
  useJobStatus,
  useModels,
  usePersonas,
  useSession,
  useStartBacktest,
} from '../api/hooks';
import type {
  BacktestResult,
  BaselineResult,
  JobStatus,
  SessionComposite,
  ZoneStats,
} from '../api/types';

// ─── form defaults ─────────────────────────────────────────────────────────
const DEFAULT_UNIVERSE = '600519.SH, 601318.SH, 000858.SZ';
const DEFAULT_START = '2025-11-17';
const DEFAULT_END = '2025-11-28';
const DEFAULT_CAPITAL = 1_000_000;

type FormState = {
  persona_id: string;
  model_id: string;
  display_name: string;
  universe: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  include_baselines: boolean;
};

function parseUniverse(raw: string): string[] {
  return raw
    .split(/[,;\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

// ─── styling helpers ───────────────────────────────────────────────────────
const fieldLabelCls = 'block text-[11px] uppercase tracking-wider text-text-faint mb-1';
const inputCls =
  'w-full bg-bg-2 border border-panel-border-soft rounded px-3 py-2 text-sm text-text-hi focus:outline-none focus:border-brand transition-colors';

function StateChip({ state }: { state: JobStatus['state'] }) {
  const cls =
    state === 'complete'
      ? 'pill brand'
      : state === 'failed'
        ? 'pill down'
        : 'pill';
  const label =
    state === 'queued'
      ? '排队中'
      : state === 'running'
        ? '运行中'
        : state === 'complete'
          ? '已完成'
          : '失败';
  return <span className={cls}>{label}</span>;
}

function GateChip({ label }: { label: 'pass' | 'warn' | 'fail' }) {
  const cls =
    label === 'pass' ? 'pill brand' : label === 'warn' ? 'pill' : 'pill down';
  const txt = label === 'pass' ? '达标' : label === 'warn' ? '观察' : '不通过';
  return <span className={cls}>{txt}</span>;
}

function pctCls(v: number) {
  if (v > 0) return 'up mono';
  if (v < 0) return 'down mono';
  return 'mono';
}

function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '—';
  return v.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

// ─── subcomponents ─────────────────────────────────────────────────────────
function BacktestForm({
  state,
  setState,
  personas,
  models,
  busy,
  onSubmit,
}: {
  state: FormState;
  setState: (patch: Partial<FormState>) => void;
  personas: ReturnType<typeof usePersonas>;
  models: ReturnType<typeof useModels>;
  busy: boolean;
  onSubmit: () => void;
}) {
  const personaList = personas.data ?? [];
  const modelList = models.data ?? [];

  return (
    <div className="panel p-5">
      <div className="flex items-baseline gap-2 mb-4">
        <h2 className="text-text-hi text-base font-semibold">新建回测</h2>
        <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
          New Backtest
        </span>
      </div>

      <div className="grid gap-4">
        <div>
          <label className={fieldLabelCls}>Persona · 风格</label>
          <select
            className={inputCls}
            value={state.persona_id}
            onChange={(e) => setState({ persona_id: e.target.value })}
            disabled={personas.isLoading}
          >
            <option value="">
              {personas.isLoading ? '加载中…' : '请选择'}
            </option>
            {personaList.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} — {p.style_desc}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className={fieldLabelCls}>Model · 大模型</label>
          <select
            className={inputCls}
            value={state.model_id}
            onChange={(e) => setState({ model_id: e.target.value })}
            disabled={models.isLoading}
          >
            <option value="">
              {models.isLoading ? '加载中…' : '请选择'}
            </option>
            {modelList
              .filter((m) => m.enabled)
              .map((m) => (
                <option key={m.id} value={m.id}>
                  {m.display_name} · {m.provider}
                </option>
              ))}
          </select>
        </div>

        <div>
          <label className={fieldLabelCls}>Agent 名称 · Display Name</label>
          <input
            className={inputCls}
            type="text"
            placeholder="例如：林园-Claude-0422"
            value={state.display_name}
            onChange={(e) => setState({ display_name: e.target.value })}
          />
        </div>

        <div>
          <label className={fieldLabelCls}>股票池 · Universe</label>
          <input
            className={`${inputCls} mono`}
            type="text"
            value={state.universe}
            onChange={(e) => setState({ universe: e.target.value })}
            placeholder="600519.SH, 601318.SH, 000858.SZ"
          />
          <div className="text-[10px] text-text-ghost mt-1">
            逗号/空格分隔 · 至少 1 只
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={fieldLabelCls}>开始日期</label>
            <input
              className={`${inputCls} mono`}
              type="date"
              value={state.start_date}
              onChange={(e) => setState({ start_date: e.target.value })}
            />
          </div>
          <div>
            <label className={fieldLabelCls}>结束日期</label>
            <input
              className={`${inputCls} mono`}
              type="date"
              value={state.end_date}
              onChange={(e) => setState({ end_date: e.target.value })}
            />
          </div>
        </div>

        <div>
          <label className={fieldLabelCls}>初始资金 · Capital (¥)</label>
          <input
            className={`${inputCls} mono`}
            type="number"
            min={10000}
            step={10000}
            value={state.initial_capital}
            onChange={(e) =>
              setState({ initial_capital: Number(e.target.value) || 0 })
            }
          />
        </div>

        <label className="flex items-center gap-2 cursor-pointer select-none text-sm text-text">
          <input
            type="checkbox"
            checked={state.include_baselines}
            onChange={(e) => setState({ include_baselines: e.target.checked })}
            className="accent-brand"
          />
          <span>同时运行 Baseline 对照组</span>
          <span className="text-[10px] text-text-faint">(Buy-and-Hold 等)</span>
        </label>

        <button
          onClick={onSubmit}
          disabled={busy}
          className="btn primary mt-1"
          style={{ justifyContent: 'center', padding: '10px 16px', fontSize: 13 }}
        >
          {busy ? '运行中…' : '创建并运行'}
        </button>
      </div>
    </div>
  );
}

function JobPanel({
  sessionId,
  job,
  session,
  error,
  startedAt,
}: {
  sessionId: string | null;
  job: JobStatus | undefined;
  session: SessionComposite | undefined;
  error: string | null;
  startedAt: number | null;
}) {
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!startedAt) return;
    if (job?.state === 'complete' || job?.state === 'failed') return;
    const iv = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(iv);
  }, [startedAt, job?.state]);

  if (!sessionId) {
    return (
      <div className="panel p-5">
        <div className="flex items-baseline gap-2 mb-4">
          <h2 className="text-text-hi text-base font-semibold">运行状态</h2>
          <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
            Run Status
          </span>
        </div>
        <div className="text-text-faint text-sm">
          填写左侧表单并点击「创建并运行」开始一次回测。
        </div>
      </div>
    );
  }

  const elapsed =
    startedAt != null
      ? Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
      : null;

  return (
    <div className="panel p-5">
      <div className="flex items-baseline gap-2 mb-4 flex-wrap">
        <h2 className="text-text-hi text-base font-semibold">运行状态</h2>
        <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
          Run Status
        </span>
        <span style={{ flex: 1 }} />
        {job && <StateChip state={job.state} />}
      </div>

      <div className="mono text-[11px] text-text-faint mb-3 break-all">
        session_id: <span className="text-text">{sessionId}</span>
      </div>

      {job && (
        <div className="grid grid-cols-3 gap-3 mb-4">
          <StatCell label="进度" value={job.progress || '—'} />
          <StatCell label="已用时" value={elapsed != null ? `${elapsed}s` : '—'} />
          <StatCell label="Agents" value={String(job.agent_ids.length)} />
        </div>
      )}

      {error && (
        <div
          className="text-sm"
          style={{
            padding: 10,
            marginBottom: 12,
            borderRadius: 4,
            background: 'var(--down-bg)',
            border: '1px solid var(--down-border)',
            color: 'var(--down)',
          }}
        >
          {error}
        </div>
      )}

      {job?.state === 'failed' && job.error && (
        <div
          className="text-sm"
          style={{
            padding: 10,
            marginBottom: 12,
            borderRadius: 4,
            background: 'var(--down-bg)',
            border: '1px solid var(--down-border)',
            color: 'var(--down)',
          }}
        >
          {job.error}
        </div>
      )}

      {job?.state === 'complete' && session && (
        <>
          <ResultsTable session={session} />
          <ZoneMetricsPanel session={session} />
        </>
      )}

      {(!job || job.state === 'queued' || job.state === 'running') && !error && (
        <div className="text-text-faint text-sm italic">
          正在轮询状态（每 1.5 秒）…
        </div>
      )}
    </div>
  );
}

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        padding: '8px 10px',
        background: 'var(--bg-2)',
        borderRadius: 4,
        border: '1px solid var(--panel-border-soft)',
      }}
    >
      <div className="text-[10px] text-text-faint uppercase tracking-wider">
        {label}
      </div>
      <div className="mono text-text-hi text-base font-semibold mt-1">{value}</div>
    </div>
  );
}

function ResultsTable({ session }: { session: SessionComposite }) {
  type Row = {
    key: string;
    name: string;
    kind: 'agent' | 'baseline';
    persona?: string | null;
    totalReturn: number;
    trades: number;
    sharpe: number;
    maxDD: number;
    finalEquity: number | null;
    gate?: 'pass' | 'warn' | 'fail';
  };

  const agentRows: Row[] = session.agents.map((a: BacktestResult) => ({
    key: `a:${a.id}`,
    name: a.agent_id,
    kind: 'agent',
    persona: a.persona_id,
    totalReturn: a.stats.total_return_pct,
    trades: a.stats.trade_count,
    sharpe: a.stats.sharpe,
    maxDD: a.stats.max_drawdown_pct,
    finalEquity: a.final_equity,
    gate: a.quality_gate_label,
  }));

  const baselineRows: Row[] = session.baselines.map((b: BaselineResult) => ({
    key: `b:${b.id}`,
    name: b.name,
    kind: 'baseline',
    totalReturn: b.stats.total_return_pct,
    trades: b.stats.trade_count,
    sharpe: b.stats.sharpe,
    maxDD: b.stats.max_drawdown_pct,
    finalEquity: b.final_equity,
  }));

  const rows = [...agentRows, ...baselineRows];

  if (rows.length === 0) {
    return <div className="text-text-faint text-sm">本次运行暂无结果。</div>;
  }

  return (
    <div style={{ border: '1px solid var(--panel-border-soft)', borderRadius: 4, overflow: 'hidden' }}>
      <table className="tbl" style={{ margin: 0 }}>
        <thead>
          <tr>
            <th>名称 · Name</th>
            <th>类型</th>
            <th className="num">收益%</th>
            <th className="num">交易数</th>
            <th className="num">Sharpe</th>
            <th className="num">最大回撤%</th>
            <th className="num">最终资产</th>
            <th>质量门</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <td>
                <div className="text-text-hi">{r.name}</div>
                {r.persona && (
                  <div className="mono text-[10px] text-text-faint mt-0.5">
                    {r.persona}
                  </div>
                )}
              </td>
              <td>
                {r.kind === 'agent' ? (
                  <span className="pill brand" style={{ fontSize: 10 }}>
                    Agent
                  </span>
                ) : (
                  <span className="pill" style={{ fontSize: 10 }}>
                    Baseline
                  </span>
                )}
              </td>
              <td className={`num ${pctCls(r.totalReturn)}`}>
                {r.totalReturn > 0 ? '+' : ''}
                {fmtNum(r.totalReturn, 2)}%
              </td>
              <td className="num">{r.trades}</td>
              <td className="num">{fmtNum(r.sharpe, 2)}</td>
              <td className="num down">{fmtNum(r.maxDD, 2)}%</td>
              <td className="num">
                {r.finalEquity != null ? `¥${fmtNum(r.finalEquity, 0)}` : '—'}
              </td>
              <td>{r.gate ? <GateChip label={r.gate} /> : <span className="text-text-faint">—</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── zone metrics (spec §11.3) ─────────────────────────────────────────────
type ZoneKey = 'pollution' | 'buffer' | 'clean';

type ZoneMeta = {
  key: ZoneKey;
  cn: string;
  en: string;
  /** accent bar color on left edge of each zone column */
  accent: string;
};

const ZONE_ORDER: ZoneMeta[] = [
  { key: 'pollution', cn: '污染区', en: 'Pollution', accent: 'oklch(0.58 0.14 25)' }, // muted red
  { key: 'buffer',    cn: '缓冲区', en: 'Buffer',    accent: 'var(--warn)' },          // amber
  { key: 'clean',     cn: '干净区', en: 'Clean',     accent: 'var(--down)' },          // brand green (Chinese-market "down" hue is green)
];

const ZONE_METRIC_ROWS: Array<{
  key: string;
  label: string;
  sub: string;
  /** true = higher is better (red/green by up/down sign); 'dd' = always shown as red-ish loss */
  kind: 'plain' | 'pct' | 'dd' | 'daily_loss';
  digits: number;
}> = [
  { key: 'sharpe',             label: 'Sharpe',     sub: '',           kind: 'plain',      digits: 2 },
  { key: 'total_return_pct',   label: '总收益',     sub: 'Return',     kind: 'pct',        digits: 2 },
  { key: 'max_drawdown_pct',   label: '最大回撤',   sub: 'Max DD',     kind: 'dd',         digits: 2 },
  { key: 'win_rate',           label: '胜率',       sub: 'Win Rate',   kind: 'pct',        digits: 2 },
  { key: 'trade_count',        label: '交易数',     sub: 'Trades',     kind: 'plain',      digits: 0 },
  { key: 'max_daily_loss_pct', label: '最大日亏损', sub: 'Daily Loss', kind: 'daily_loss', digits: 2 },
];

function getZone(zones: ZoneStats[], key: ZoneKey): ZoneStats | undefined {
  return zones.find((z) => z.zone === key);
}

function fmtZoneMetric(
  v: number | undefined | null,
  kind: (typeof ZONE_METRIC_ROWS)[number]['kind'],
  digits: number,
): { text: string; cls: string } {
  if (v == null || Number.isNaN(v)) return { text: '—', cls: 'mono text-text-faint' };

  if (kind === 'pct') {
    const cls = `num ${pctCls(v)}`;
    const sign = v > 0 ? '+' : '';
    return { text: `${sign}${fmtNum(v, digits)}%`, cls };
  }
  if (kind === 'dd' || kind === 'daily_loss') {
    // max_drawdown_pct is typically reported as a negative number (loss) or
    // positive magnitude — show in 'down' (green in CN market = loss) either way.
    return { text: `${fmtNum(v, digits)}%`, cls: 'num down' };
  }
  // plain
  return { text: fmtNum(v, digits), cls: 'num text-text-hi' };
}

function ZoneColumn({ meta, zone }: { meta: ZoneMeta; zone: ZoneStats | undefined }) {
  const hasStats = !!zone && zone.days >= 2;
  return (
    <div
      style={{
        background: 'var(--bg-3)',
        border: '1px solid var(--panel-border-soft)',
        borderRadius: 'var(--r-sm)',
        borderLeft: `4px solid ${meta.accent}`,
        padding: '10px 12px',
      }}
    >
      <div className="flex items-baseline gap-2 mb-2 flex-wrap">
        <span className="text-text-hi text-sm font-semibold" style={{ color: meta.accent }}>
          {meta.cn}
        </span>
        <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
          {meta.en}
        </span>
        <span style={{ flex: 1 }} />
        <span className="pill" style={{ fontSize: 10 }}>
          {zone ? `${zone.days}d` : '0d'}
        </span>
      </div>
      {hasStats ? (
        <div className="grid gap-1.5">
          {ZONE_METRIC_ROWS.map((row) => {
            const v = zone!.stats[row.key];
            const { text, cls } = fmtZoneMetric(v, row.kind, row.digits);
            return (
              <div
                key={row.key}
                className="flex items-baseline justify-between gap-2"
                style={{
                  padding: '3px 0',
                  borderBottom: '1px dashed var(--panel-border-soft)',
                }}
              >
                <div>
                  <span className="text-text text-xs">{row.label}</span>
                  {row.sub && (
                    <span className="mono text-[9.5px] text-text-ghost uppercase ml-1.5 tracking-wider">
                      {row.sub}
                    </span>
                  )}
                </div>
                <span className={`${cls} text-sm`} style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {text}
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-text-faint text-xs italic py-2">
          —  数据不足（需 ≥ 2 天）
        </div>
      )}
    </div>
  );
}

function DivergenceBanner({ zones }: { zones: ZoneStats[] }) {
  const pollution = getZone(zones, 'pollution');
  const clean = getZone(zones, 'clean');
  const p_sharpe = pollution?.stats.sharpe;
  const c_sharpe = clean?.stats.sharpe;

  const bothPresent =
    p_sharpe != null && !Number.isNaN(p_sharpe) &&
    c_sharpe != null && !Number.isNaN(c_sharpe);
  const sufficient =
    bothPresent && (pollution?.days ?? 0) >= 10 && (clean?.days ?? 0) >= 10;

  if (!sufficient) {
    return (
      <div
        className="text-xs mt-3"
        style={{
          padding: '8px 12px',
          borderRadius: 'var(--r-sm)',
          background: 'var(--bg-3)',
          border: '1px solid var(--panel-border-soft)',
          color: 'var(--text-faint)',
        }}
      >
        需要至少 10 天污染区 + 10 天干净区数据才能评估泄漏风险
      </div>
    );
  }

  const delta = Math.abs((p_sharpe as number) - (c_sharpe as number));
  const leaky = delta > 0.5;

  if (leaky) {
    return (
      <div
        className="text-xs mt-3"
        style={{
          padding: '10px 12px',
          borderRadius: 'var(--r-sm)',
          background: 'var(--up-bg)',
          border: '1px solid var(--up-border)',
          color: 'var(--up)',
          borderLeft: '4px solid var(--warn)',
        }}
      >
        <span style={{ fontWeight: 600 }}>⚠ </span>
        污染区 Sharpe ({fmtNum(p_sharpe, 2)}) 明显高于干净区 ({fmtNum(c_sharpe, 2)}) —
        考虑是否有知识泄漏，干净区数据才能反映泛化能力
      </div>
    );
  }

  return (
    <div
      className="text-xs mt-3"
      style={{
        padding: '10px 12px',
        borderRadius: 'var(--r-sm)',
        background: 'var(--down-bg)',
        border: '1px solid var(--down-border)',
        color: 'var(--down)',
      }}
    >
      <span style={{ fontWeight: 600 }}>✓ </span>
      污染区与干净区 Sharpe 差距可忽略 (|Δ{fmtNum(delta, 2)}|)，无明显知识泄漏信号
    </div>
  );
}

function ZoneMetricsPanel({ session }: { session: SessionComposite }) {
  // Design choice: render ONE zone grid per agent in the session, each labeled
  // with the agent's display name/id. In single-agent sessions this collapses
  // to a single grid; multi-agent sessions stack them vertically so the user
  // can audit knowledge-leakage per agent independently.
  const agents = session.agents;
  if (agents.length === 0) return null;

  return (
    <div className="panel p-5 mt-4">
      <div className="flex items-baseline gap-2 mb-1 flex-wrap">
        <h2 className="text-text-hi text-base font-semibold">跨截止区分区指标</h2>
        <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
          Zone-Bifurcated Metrics
        </span>
      </div>
      <div className="text-text-faint text-[11px] mb-2">
        污染区 / 缓冲区 / 干净区 分别统计
      </div>
      <div
        className="text-text-dim text-[11px] mb-4"
        style={{ lineHeight: 1.6 }}
      >
        把回测窗口按模型 training_cutoff 切成三段分别计算，干净区的 Sharpe
        才是"真实代"，污染区若远高于干净区说明模型在吃训练数据。
      </div>

      <div className="grid gap-5">
        {agents.map((agent, idx) => {
          const zones = agent.zone_stats ?? [];
          return (
            <div key={agent.id}>
              {agents.length > 1 && (
                <div className="flex items-baseline gap-2 mb-2 flex-wrap">
                  <span
                    className="pill brand"
                    style={{ fontSize: 10 }}
                  >
                    Agent #{idx + 1}
                  </span>
                  <span className="text-text-hi text-sm font-semibold">
                    {agent.agent_id}
                  </span>
                  {agent.persona_id && (
                    <span className="mono text-[10px] text-text-faint">
                      {agent.persona_id}
                    </span>
                  )}
                </div>
              )}

              {zones.length === 0 ? (
                <div
                  className="text-xs"
                  style={{
                    padding: '14px 12px',
                    borderRadius: 'var(--r-sm)',
                    background: 'var(--bg-3)',
                    border: '1px dashed var(--panel-border-soft)',
                    color: 'var(--text-faint)',
                    fontStyle: 'italic',
                  }}
                >
                  (本次回测未生成分区统计 · Zone stats unavailable)
                </div>
              ) : (
                <>
                  <div
                    className="grid gap-3"
                    style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}
                  >
                    {ZONE_ORDER.map((meta) => (
                      <ZoneColumn
                        key={meta.key}
                        meta={meta}
                        zone={getZone(zones, meta.key)}
                      />
                    ))}
                  </div>
                  <DivergenceBanner zones={zones} />
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── page ──────────────────────────────────────────────────────────────────
export function BacktestLab() {
  const personas = usePersonas();
  const models = useModels();

  const [form, setForm] = useState<FormState>(() => ({
    persona_id: '',
    model_id: '',
    display_name: '',
    universe: DEFAULT_UNIVERSE,
    start_date: DEFAULT_START,
    end_date: DEFAULT_END,
    initial_capital: DEFAULT_CAPITAL,
    include_baselines: true,
  }));
  const patch = (p: Partial<FormState>) => setForm((prev) => ({ ...prev, ...p }));

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [uiError, setUiError] = useState<string | null>(null);

  const createAgent = useCreateAgent();
  const startBacktest = useStartBacktest();

  const job = useJobStatus(sessionId ?? undefined);
  const sessionEnabled = job.data?.state === 'complete';
  const session = useSession(sessionId ?? undefined, sessionEnabled);

  const busy =
    createAgent.isPending ||
    startBacktest.isPending ||
    (!!sessionId && (job.data?.state === 'queued' || job.data?.state === 'running'));

  async function onSubmit() {
    setUiError(null);

    // basic validation
    if (!form.persona_id) {
      setUiError('请选择 Persona。');
      return;
    }
    if (!form.model_id) {
      setUiError('请选择 Model。');
      return;
    }
    if (!form.display_name.trim()) {
      setUiError('请填写 Agent 名称。');
      return;
    }
    const tickers = parseUniverse(form.universe);
    if (tickers.length === 0) {
      setUiError('股票池不能为空。');
      return;
    }
    if (!form.start_date || !form.end_date) {
      setUiError('请填写开始/结束日期。');
      return;
    }
    if (form.initial_capital <= 0) {
      setUiError('初始资金必须大于 0。');
      return;
    }

    try {
      const agent = await createAgent.mutateAsync({
        persona_id: form.persona_id,
        model_id: form.model_id,
        display_name: form.display_name.trim(),
        initial_capital: form.initial_capital,
      });
      const res = await startBacktest.mutateAsync({
        agent_ids: [agent.id],
        start_date: form.start_date,
        end_date: form.end_date,
        initial_capital: form.initial_capital,
        universe: tickers,
        include_baselines: form.include_baselines,
      });
      setSessionId(res.session_id);
      setStartedAt(Date.now());
    } catch (e) {
      setUiError(e instanceof Error ? e.message : String(e));
    }
  }

  const pageError = uiError;

  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-2xl text-text-hi font-semibold">回测实验室</h1>
        <div className="text-text-faint text-xs mt-1 tracking-wide uppercase">
          Backtest Lab · Agent vs Baseline
        </div>
      </div>

      <div className="grid gap-5" style={{ gridTemplateColumns: 'minmax(340px, 400px) 1fr' }}>
        <BacktestForm
          state={form}
          setState={patch}
          personas={personas}
          models={models}
          busy={busy}
          onSubmit={onSubmit}
        />
        <JobPanel
          sessionId={sessionId}
          job={job.data}
          session={session.data}
          error={pageError}
          startedAt={startedAt}
        />
      </div>
    </div>
  );
}
