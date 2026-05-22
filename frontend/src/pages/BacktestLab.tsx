import { useEffect, useMemo, useState } from 'react';
import {
  useBacktestNav,
  useBacktestRating,
  useBacktestThinking,
  useBacktestTrades,
  useCancelJob,
  useCreateAgent,
  useDataCoverage,
  useDeleteBacktest,
  useJobStatusStream,
  useModels,
  usePersonas,
  useSession,
  useStartBacktest,
  useStartRuleBacktest,
  useStrategies,
} from '../api/hooks';
import { api } from '../api/client';
import type {
  BacktestEvent,
  BacktestResult,
  BaselineResult,
  DataCoverage,
  JobStatus,
  SessionComposite,
  ZoneStats,
} from '../api/types';
import { NavChart } from '../components/NavChart';
import { TradesTable } from '../components/TradesTable';
import { ThinkingDrawer } from '../components/ThinkingDrawer';
import { QualityGatePanel } from '../components/QualityGatePanel';
import { StrategyRatingPanel } from '../components/StrategyRatingPanel';
import { LiveEventLog } from '../components/LiveEventLog';
import { MonthlyHeatmap } from '../components/MonthlyHeatmap';
import { SessionsHistoryList } from '../components/SessionsHistoryList';
import { UniverseKLineGrid } from '../components/UniverseKLineGrid';
import { DecisionLedger } from '../components/DecisionLedger';
import { BacktestWindowBanner } from '../components/BacktestWindowBanner';

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
  engine: 'legacy' | 'vnpy';
};

function parseUniverse(raw: string): string[] {
  return raw
    .split(/[,;\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

// ─── data-coverage validation helpers ──────────────────────────────────────
/**
 * v1: probes coverage for the FIRST ticker in the universe and treats it as a
 * proxy for the whole list. Justified because the local cache today is single-
 * source HS300 (all tickers ingested in the same window). When per-stock
 * windows diverge, upgrade to useQueries() over the full list and intersect
 * the ranges; the rest of the validation logic already accepts a single
 * {first_date,last_date} pair.
 */
function useUniverseCoverage(universeStr: string) {
  const codes = useMemo(() => parseUniverse(universeStr), [universeStr]);
  const firstCode = codes[0];
  const q = useDataCoverage(firstCode);
  return {
    firstCode,
    coverage: q.data,
    isLoading: q.isLoading,
    isError: q.isError,
  };
}

type DateValidation =
  | { kind: 'ok'; coverage: DataCoverage; codeUsed: string }
  | { kind: 'no-data'; codeUsed: string }
  | { kind: 'loading' }
  | { kind: 'inverted' }   // start > end
  | { kind: 'outside'; coverage: DataCoverage; codeUsed: string }   // entirely outside
  | { kind: 'partial'; coverage: DataCoverage; codeUsed: string }   // overlaps but spills
  | { kind: 'covered'; coverage: DataCoverage; codeUsed: string };  // fully inside

function classifyDateRange(
  start: string,
  end: string,
  coverage: DataCoverage | undefined,
  codeUsed: string | undefined,
  isLoading: boolean,
): DateValidation {
  if (!start || !end) return { kind: 'loading' };
  if (start > end) return { kind: 'inverted' };
  if (isLoading) return { kind: 'loading' };
  if (!coverage || !codeUsed) return { kind: 'loading' };
  if (!coverage.first_date || !coverage.last_date || coverage.count === 0) {
    return { kind: 'no-data', codeUsed };
  }
  // Entirely outside coverage in either direction.
  if (start > coverage.last_date || end < coverage.first_date) {
    return { kind: 'outside', coverage, codeUsed };
  }
  // Spills off either edge but at least overlaps.
  if (start < coverage.first_date || end > coverage.last_date) {
    return { kind: 'partial', coverage, codeUsed };
  }
  return { kind: 'covered', coverage, codeUsed };
}

/** Subtract `days` from an ISO YYYY-MM-DD date string and return ISO. */
function subtractDays(iso: string, days: number): string {
  const d = new Date(iso + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

/** Render coverage status under the date-row inputs. */
function CoverageStatus({ v }: { v: DateValidation }) {
  const baseStyle: React.CSSProperties = {
    padding: '6px 10px',
    fontSize: 11,
    borderRadius: 4,
    marginTop: 6,
    lineHeight: 1.5,
  };
  if (v.kind === 'loading') {
    return (
      <div
        style={{
          ...baseStyle,
          color: 'var(--text-faint)',
          background: 'var(--bg-3)',
          border: '1px dashed var(--panel-border-soft)',
        }}
      >
        正在查询数据覆盖范围…
      </div>
    );
  }
  if (v.kind === 'inverted') {
    return (
      <div
        style={{
          ...baseStyle,
          color: 'var(--down)',
          background: 'var(--down-bg)',
          border: '1px solid var(--down-border)',
        }}
      >
        ✗ 开始日期晚于结束日期
      </div>
    );
  }
  if (v.kind === 'no-data') {
    return (
      <div
        style={{
          ...baseStyle,
          color: 'var(--down)',
          background: 'var(--down-bg)',
          border: '1px solid var(--down-border)',
        }}
      >
        ✗ 本地缓存中没有 {v.codeUsed} 的数据，无法进行回测
      </div>
    );
  }
  if (v.kind === 'outside') {
    return (
      <div
        style={{
          ...baseStyle,
          color: 'var(--down)',
          background: 'var(--down-bg)',
          border: '1px solid var(--down-border)',
        }}
      >
        ✗ 整个窗口在数据覆盖之外（{v.coverage.code} 仅有
        {' '}{v.coverage.first_date} → {v.coverage.last_date}）
      </div>
    );
  }
  if (v.kind === 'partial') {
    return (
      <div
        style={{
          ...baseStyle,
          color: 'var(--warn)',
          background: 'var(--warn-bg, rgba(234,179,8,0.08))',
          border: '1px solid var(--warn)',
        }}
      >
        ⚠ 部分窗口缺数据：{v.coverage.code} 仅有
        {' '}{v.coverage.first_date} → {v.coverage.last_date}
        （共 {v.coverage.count} 个交易日）。建议调整起止日期。
      </div>
    );
  }
  // covered
  return (
    <div
      style={{
        ...baseStyle,
        color: 'var(--text-dim)',
        background: 'var(--bg-3)',
        border: '1px solid var(--panel-border-soft)',
      }}
    >
      ✓ 数据覆盖：{v.coverage.code} 有 {v.coverage.count} 个交易日
      （{v.coverage.first_date} → {v.coverage.last_date}）
    </div>
  );
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
  coverageValidation,
}: {
  state: FormState;
  setState: (patch: Partial<FormState>) => void;
  personas: ReturnType<typeof usePersonas>;
  models: ReturnType<typeof useModels>;
  busy: boolean;
  onSubmit: () => void;
  coverageValidation: DateValidation;
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
          <label className={fieldLabelCls}>回测引擎 · Engine</label>
          <select
            className={inputCls}
            value={state.engine}
            onChange={(e) =>
              setState({ engine: e.target.value as 'legacy' | 'vnpy' })
            }
          >
            <option value="legacy">Legacy (默认)</option>
            <option value="vnpy">vnpy (Beta)</option>
          </select>
          {state.engine === 'vnpy' && (
            <div
              className="text-[10px] text-text-faint mt-1"
              style={{ lineHeight: 1.5 }}
            >
              Beta：走 vnpy.BacktestingEngine，使用 engine.calculate_statistics()。
              撮合时间点与 Legacy 有细微差异（next-bar-open vs same-day-close）。
            </div>
          )}
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

        <div>
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
          <CoverageStatus v={coverageValidation} />
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

/**
 * Pulls the first agent's nav curve to learn the actual trading-day count
 * (daily_records.length is the source of truth — calendar diff would
 * over-count weekends). Falls back to 0 while loading; banner still renders
 * with the known dates so the alignment confirmation appears immediately.
 */
function SessionWindowBanner({ session }: { session: SessionComposite }) {
  const firstAgentId = session.agents[0]?.id;
  const nav = useBacktestNav(firstAgentId);
  if (session.agents.length === 0) return null;
  const first = session.agents[0];
  const tradingDays = nav.data?.agent.length ?? 0;
  return (
    <BacktestWindowBanner
      startDate={first.start_date}
      endDate={first.end_date}
      tradingDays={tradingDays}
      agentCount={session.agents.length}
      baselineCount={session.baselines.length}
    />
  );
}

function JobPanel({
  sessionId,
  job,
  events,
  session,
  error,
  startedAt,
}: {
  sessionId: string | null;
  job: JobStatus | undefined;
  events: BacktestEvent[];
  session: SessionComposite | undefined;
  error: string | null;
  startedAt: number | null;
}) {
  const [, setTick] = useState(0);
  const cancel = useCancelJob();
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
          <SessionWindowBanner session={session} />
          <ResultsTable session={session} />
          <ZoneMetricsPanel session={session} />
          {session.agents.map((a) => (
            <ResultDetailPanels key={a.id} result={a} />
          ))}
        </>
      )}

      {(!job || job.state === 'queued' || job.state === 'running') && !error && (
        <div className="mt-3">
          <div className="flex items-baseline gap-2 mb-1">
            <div className="text-[10px] text-text-ghost uppercase tracking-wider">
              实时事件 · Live Events
            </div>
            <span style={{ flex: 1 }} />
            {sessionId && job?.state === 'running' && (
              <button
                className="btn"
                onClick={() => cancel.mutate(sessionId)}
                disabled={cancel.isPending || !!job.cancel_requested}
                style={{
                  padding: '3px 10px',
                  fontSize: 10,
                  background: 'var(--down)',
                  color: 'var(--bg)',
                  borderColor: 'var(--down)',
                }}
              >
                {cancel.isPending || job.cancel_requested ? '取消中…' : '取消运行'}
              </button>
            )}
          </div>
          <LiveEventLog events={events} />
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
    deletableId: string | null;  // backtest_results.id for agent/rule; null for baselines
    name: string;
    kind: 'agent' | 'baseline' | 'rule';
    persona?: string | null;
    totalReturn: number;
    trades: number;
    sharpe: number;
    maxDD: number;
    finalEquity: number | null;
    gate?: 'pass' | 'warn' | 'fail';
  };
  const del = useDeleteBacktest();

  const agentRows: Row[] = session.agents.map((a: BacktestResult) => ({
    key: `a:${a.id}`,
    deletableId: a.id,
    name: a.kind === 'rule' ? '规则策略' : a.agent_id,
    kind: a.kind === 'rule' ? 'rule' : 'agent',
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
    deletableId: null,
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
            <th></th>
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
                ) : r.kind === 'rule' ? (
                  <span
                    className="pill"
                    style={{
                      fontSize: 10,
                      background: 'var(--bg-3)',
                      color: 'var(--text)',
                    }}
                  >
                    Rule
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
              <td>
                {r.deletableId && (
                  <button
                    className="btn"
                    title="删除此回测结果"
                    onClick={() => {
                      if (window.confirm(`删除 ${r.name} 的回测结果？此操作不可撤销。`)) {
                        del.mutate(r.deletableId!);
                      }
                    }}
                    disabled={del.isPending}
                    style={{
                      padding: '2px 8px',
                      fontSize: 11,
                      color: 'var(--down)',
                      borderColor: 'var(--down-border)',
                      background: 'transparent',
                    }}
                  >
                    🗑
                  </button>
                )}
              </td>
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

// Zone accent palette — deliberately DECOUPLED from the CN stock up/down
// palette (which inverts: red=up, green=down). Using --up/--down here would
// read as "clean zone = price down" which is nonsensical. Instead we use a
// neutral severity scale:
//   pollution → warn amber  ("data quality caveat")
//   buffer    → text-faint  ("uncertain zone")
//   clean     → brand gold  ("trusted data")
const ZONE_COLORS: Record<ZoneKey, string> = {
  pollution: 'var(--warn)',
  buffer: 'var(--text-faint)',
  clean: 'var(--brand)',
};

const ZONE_ORDER: ZoneMeta[] = [
  { key: 'pollution', cn: '污染区', en: 'Pollution', accent: ZONE_COLORS.pollution },
  { key: 'buffer',    cn: '缓冲区', en: 'Buffer',    accent: ZONE_COLORS.buffer },
  { key: 'clean',     cn: '干净区', en: 'Clean',     accent: ZONE_COLORS.clean },
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

function DivergenceBanner({ result }: { result: BacktestResult }) {
  const { divergence_flag, divergence_metric, zone_stats } = result;
  const byZone = Object.fromEntries(zone_stats.map((z) => [z.zone, z]));
  const pollution = byZone['pollution'];
  const clean = byZone['clean'];
  const minDays = 10;
  const sufficient =
    pollution && clean && pollution.days >= minDays && clean.days >= minDays &&
    pollution.stats && clean.stats;

  if (!sufficient) {
    return (
      <div style={{ padding: '10px 14px', marginTop: 12, fontSize: 12,
                    color: 'var(--text-dim)', background: 'var(--bg-3)',
                    border: '1px solid var(--panel-border-soft)',
                    borderRadius: 6 }}>
        需要至少 10 天污染区 + 10 天干净区数据才能评估知识泄漏风险
      </div>
    );
  }

  if (divergence_flag) {
    const pretty = divergence_metric !== null ? divergence_metric.toFixed(3) : '—';
    return (
      <div style={{ padding: '10px 14px', marginTop: 12, fontSize: 12,
                    color: 'var(--warn)', background: 'var(--warn-bg, rgba(234,179,8,0.08))',
                    border: '1px solid var(--warn)',
                    borderRadius: 6 }}>
        ⚠ 污染区与干净区收益差距显著（相对距离 {pretty} &gt; 0.5）—
        考虑是否有知识泄漏，以干净区的指标评估泛化能力
      </div>
    );
  }
  const pretty = divergence_metric !== null ? divergence_metric.toFixed(3) : '0.000';
  return (
    <div style={{ padding: '10px 14px', marginTop: 12, fontSize: 12,
                  color: 'var(--text-dim)', background: 'var(--bg-3)',
                  border: '1px solid var(--panel-border-soft)',
                  borderRadius: 6 }}>
      ✓ 污染区与干净区收益相对距离可忽略（{pretty}），无明显知识泄漏信号
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
                  <DivergenceBanner result={agent} />
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ResultDetailPanels({ result }: { result: BacktestResult }) {
  const nav = useBacktestNav(result.id);
  const trades = useBacktestTrades(result.id);
  const thinking = useBacktestThinking(result.id);
  const rating = useBacktestRating(result.id);

  // Universe shown in the K-line grid — prefer the persisted input pool
  // (post 2026-04-26 schema change) so analysts can see ALL stocks the
  // agent had access to, not only the ones it actually traded. Fallback to
  // deriving from trades for pre-fix legacy result rows.
  const universeCodes =
    result.universe && result.universe.length > 0
      ? result.universe
      : Array.from(new Set((trades.data?.trades ?? []).map((t) => t.code)));

  return (
    <div className="grid gap-4 mt-4">
      {/* NAV curve */}
      <div className="panel p-5">
        <div className="flex items-baseline gap-2 mb-3 flex-wrap">
          <h2 className="text-text-hi text-base font-semibold">权益曲线</h2>
          <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
            NAV Curve · {result.agent_id}
          </span>
        </div>
        <NavChart data={nav.data} />
      </div>

      {/* Universe K-lines — one OHLC chart per traded code over the window */}
      {universeCodes.length > 0 && (
        <div className="panel p-5">
          <div className="flex items-baseline gap-2 mb-3 flex-wrap">
            <h2 className="text-text-hi text-base font-semibold">股票池 K 线</h2>
            <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
              Universe K-Lines · {universeCodes.length} stocks
            </span>
          </div>
          <UniverseKLineGrid
            codes={universeCodes}
            start={result.start_date}
            end={result.end_date}
          />
        </div>
      )}

      {/* Two-column: rating+gate | thinking */}
      <div className="grid gap-4" style={{ gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)' }}>
        <div className="grid gap-4">
          <StrategyRatingPanel rating={rating.data} />
          <QualityGatePanel result={result} />
        </div>
        <div className="panel p-5">
          <div className="flex items-baseline gap-2 mb-3 flex-wrap">
            <h2 className="text-text-hi text-base font-semibold">决策日志</h2>
            <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
              LLM Thinking
            </span>
          </div>
          <ThinkingDrawer thinking={thinking.data?.thinking ?? []} />
        </div>
      </div>

      {/* Trade log */}
      <div className="panel p-5">
        <div className="flex items-baseline gap-2 mb-3 flex-wrap">
          <h2 className="text-text-hi text-base font-semibold">成交流水</h2>
          <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
            Trade Log
          </span>
        </div>
        <TradesTable trades={trades.data?.trades ?? []} />
      </div>

      {/* Joined per-decision ledger: thinking → validation → fill */}
      <div className="panel p-5">
        <div className="flex items-baseline gap-2 mb-3 flex-wrap">
          <h2 className="text-text-hi text-base font-semibold">决策日志</h2>
          <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
            Decision Ledger · {result.agent_id}
          </span>
        </div>
        <DecisionLedger resultId={result.id} />
      </div>

      {/* Monthly heatmap */}
      <div className="panel p-5">
        <div className="flex items-baseline gap-2 mb-3 flex-wrap">
          <h2 className="text-text-hi text-base font-semibold">月度收益热力图</h2>
          <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
            Monthly Returns
          </span>
        </div>
        <MonthlyHeatmap resultId={result.id} />
      </div>
    </div>
  );
}

// ─── rule mode (P3-C) ──────────────────────────────────────────────────────
type RuleFormState = {
  strategy_name: string;
  params: Record<string, number>;
  universe: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
};

function coerceParams(raw: Record<string, number | string>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [k, v] of Object.entries(raw)) {
    const n = typeof v === 'string' ? Number(v) : v;
    if (!Number.isNaN(n)) out[k] = n;
  }
  return out;
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className="btn"
      style={{
        padding: '6px 16px',
        background: active ? 'var(--brand)' : 'transparent',
        color: active ? 'var(--bg)' : 'var(--text-hi)',
        borderColor: active ? 'var(--brand)' : 'var(--panel-border-soft)',
      }}
    >
      {children}
    </button>
  );
}

function RuleBacktestForm({
  state,
  setState,
  strategies,
  busy,
  onSubmit,
  coverageValidation,
}: {
  state: RuleFormState;
  setState: (patch: Partial<RuleFormState>) => void;
  strategies: ReturnType<typeof useStrategies>;
  busy: boolean;
  onSubmit: () => void;
  coverageValidation: DateValidation;
}) {
  const list = strategies.data ?? [];
  const selected = list.find((s) => s.name === state.strategy_name);

  return (
    <div className="panel p-5">
      <div className="flex items-baseline gap-2 mb-4">
        <h2 className="text-text-hi text-base font-semibold">规则模式回测</h2>
        <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
          Rule Mode
        </span>
      </div>
      <div className="grid gap-4">
        <div>
          <label className={fieldLabelCls}>策略 · Strategy</label>
          <select
            className={inputCls}
            value={state.strategy_name}
            onChange={(e) => {
              const picked = list.find((s) => s.name === e.target.value);
              setState({
                strategy_name: e.target.value,
                params: picked ? coerceParams(picked.default_params) : {},
              });
            }}
            disabled={strategies.isLoading}
          >
            <option value="">
              {strategies.isLoading ? '加载中…' : '请选择'}
            </option>
            {list.map((s) => (
              <option key={s.name} value={s.name}>
                {s.display_name} · {s.name}
              </option>
            ))}
          </select>
          {selected && (
            <div className="text-[11px] text-text-faint mt-1">
              {selected.description}
            </div>
          )}
        </div>

        {selected && Object.keys(state.params).length > 0 && (
          <div>
            <label className={fieldLabelCls}>参数 · Params</label>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(state.params).map(([k, v]) => (
                <div key={k}>
                  <div className="text-[10px] text-text-ghost uppercase tracking-wider mb-0.5">
                    {k}
                  </div>
                  <input
                    className={`${inputCls} mono text-xs`}
                    type="number"
                    value={v}
                    step={Number.isInteger(v) ? 1 : 0.05}
                    onChange={(e) =>
                      setState({
                        params: { ...state.params, [k]: Number(e.target.value) },
                      })
                    }
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        <div>
          <label className={fieldLabelCls}>股票池 · Universe</label>
          <input
            className={`${inputCls} mono`}
            type="text"
            value={state.universe}
            onChange={(e) => setState({ universe: e.target.value })}
            placeholder="600519.SH, 601318.SH"
          />
        </div>

        <div>
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
          <CoverageStatus v={coverageValidation} />
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

        <button
          onClick={onSubmit}
          disabled={busy || !state.strategy_name}
          className="btn primary mt-1"
          style={{ justifyContent: 'center', padding: '10px 16px', fontSize: 13 }}
        >
          {busy ? '运行中…' : '运行规则回测'}
        </button>
      </div>
    </div>
  );
}

// ─── page ──────────────────────────────────────────────────────────────────
export function BacktestLab() {
  const personas = usePersonas();
  const models = useModels();
  const strategies = useStrategies();

  const [mode, setMode] = useState<'agent' | 'rule'>('agent');

  const [form, setForm] = useState<FormState>(() => ({
    persona_id: '',
    model_id: '',
    display_name: '',
    universe: DEFAULT_UNIVERSE,
    start_date: DEFAULT_START,
    end_date: DEFAULT_END,
    initial_capital: DEFAULT_CAPITAL,
    include_baselines: true,
    engine: 'legacy',
  }));
  const patch = (p: Partial<FormState>) => setForm((prev) => ({ ...prev, ...p }));

  const [ruleForm, setRuleForm] = useState<RuleFormState>(() => ({
    strategy_name: '',
    params: {},
    universe: DEFAULT_UNIVERSE,
    start_date: DEFAULT_START,
    end_date: DEFAULT_END,
    initial_capital: DEFAULT_CAPITAL,
  }));
  const patchRule = (p: Partial<RuleFormState>) =>
    setRuleForm((prev) => ({ ...prev, ...p }));

  // Coverage probes (one per form). Each follows the FIRST ticker — see
  // useUniverseCoverage docstring for the single-source justification.
  const agentCoverage = useUniverseCoverage(form.universe);
  const ruleCoverage = useUniverseCoverage(ruleForm.universe);

  const agentValidation = useMemo(
    () => classifyDateRange(
      form.start_date,
      form.end_date,
      agentCoverage.coverage,
      agentCoverage.firstCode,
      agentCoverage.isLoading,
    ),
    [form.start_date, form.end_date, agentCoverage.coverage,
      agentCoverage.firstCode, agentCoverage.isLoading],
  );
  const ruleValidation = useMemo(
    () => classifyDateRange(
      ruleForm.start_date,
      ruleForm.end_date,
      ruleCoverage.coverage,
      ruleCoverage.firstCode,
      ruleCoverage.isLoading,
    ),
    [ruleForm.start_date, ruleForm.end_date, ruleCoverage.coverage,
      ruleCoverage.firstCode, ruleCoverage.isLoading],
  );

  // Smart defaults: once coverage for the first ticker arrives AND the form
  // dates are still the hardcoded DEFAULT_START/DEFAULT_END, snap the window
  // to (last - 30d, last) clamped to [first, last]. Runs at most once per
  // form because subsequent edits move the dates off the hardcoded sentinels.
  useEffect(() => {
    const cov = agentCoverage.coverage;
    if (!cov || !cov.first_date || !cov.last_date) return;
    if (form.start_date !== DEFAULT_START || form.end_date !== DEFAULT_END) return;
    const desiredStart = subtractDays(cov.last_date, 30);
    const clampedStart = desiredStart < cov.first_date ? cov.first_date : desiredStart;
    patch({ start_date: clampedStart, end_date: cov.last_date });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentCoverage.coverage]);

  useEffect(() => {
    const cov = ruleCoverage.coverage;
    if (!cov || !cov.first_date || !cov.last_date) return;
    if (ruleForm.start_date !== DEFAULT_START || ruleForm.end_date !== DEFAULT_END) return;
    const desiredStart = subtractDays(cov.last_date, 30);
    const clampedStart = desiredStart < cov.first_date ? cov.first_date : desiredStart;
    patchRule({ start_date: clampedStart, end_date: cov.last_date });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ruleCoverage.coverage]);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [uiError, setUiError] = useState<string | null>(null);
  const [showFormModal, setShowFormModal] = useState<boolean>(false);
  // Tracks which mode produced the current sessionId; controls whether we
  // wait for the SSE job stream (agent) or fetch the session composite
  // immediately (rule mode is synchronous).
  const [sessionMode, setSessionMode] = useState<'agent' | 'rule'>('agent');

  const createAgent = useCreateAgent();
  const startBacktest = useStartBacktest();
  const startRule = useStartRuleBacktest();

  // Historic = a session loaded from the history list (no live job to stream).
  // We bypass the SSE entirely and load the session composite straight away.
  const isHistoric = !!sessionId && startedAt === null;

  // Only stream SSE for live agent-mode sessions; rule mode is synchronous,
  // historic sessions have no running job.
  const jobStream = useJobStatusStream(
    sessionMode === 'agent' && !isHistoric ? (sessionId ?? undefined) : undefined,
  );
  const sessionEnabled =
    sessionMode === 'rule' ||
    isHistoric ||
    jobStream.status?.state === 'complete';
  const session = useSession(sessionId ?? undefined, sessionEnabled);

  const busy =
    createAgent.isPending ||
    startBacktest.isPending ||
    startRule.isPending ||
    (!!sessionId &&
      sessionMode === 'agent' &&
      (jobStream.status?.state === 'queued' ||
        jobStream.status?.state === 'running'));

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
        engine: form.engine,
      });
      setSessionMode('agent');
      setSessionId(res.session_id);
      setStartedAt(Date.now());
      setShowFormModal(false);
    } catch (e) {
      setUiError(e instanceof Error ? e.message : String(e));
    }
  }

  async function onSubmitRule() {
    setUiError(null);
    if (!ruleForm.strategy_name) {
      setUiError('请选择策略。');
      return;
    }
    const tickers = parseUniverse(ruleForm.universe);
    if (tickers.length === 0) {
      setUiError('股票池不能为空。');
      return;
    }
    if (!ruleForm.start_date || !ruleForm.end_date) {
      setUiError('请填写开始/结束日期。');
      return;
    }
    if (ruleForm.initial_capital <= 0) {
      setUiError('初始资金必须大于 0。');
      return;
    }
    try {
      const res = await startRule.mutateAsync({
        strategy_name: ruleForm.strategy_name,
        params: ruleForm.params,
        universe: tickers,
        start_date: ruleForm.start_date,
        end_date: ruleForm.end_date,
        initial_capital: ruleForm.initial_capital,
      });
      setSessionMode('rule');
      setSessionId(res.session_id);
      setStartedAt(Date.now());
      setShowFormModal(false);
    } catch (e) {
      setUiError(e instanceof Error ? e.message : String(e));
    }
  }

  const pageError = uiError ?? jobStream.error;

  // For rule mode and historic sessions (no live SSE), synthesize a "complete"
  // job status so JobPanel renders the ResultsTable (which gates on
  // job.state === 'complete'). The session composite is the source of truth;
  // this shim just unlocks the render.
  const syntheticJobStatus: JobStatus | undefined =
    (sessionMode === 'rule' || isHistoric) && sessionId
      ? {
          session_id: sessionId,
          state: 'complete',
          progress: 'done',
          agent_ids: session.data?.agents.map((a) => a.agent_id) ?? [],
          agent_result_ids: session.data?.agents.map((a) => a.id) ?? [],
          baseline_result_ids: session.data?.baselines.map((b) => b.id) ?? [],
          error: null,
          submitted_at: startedAt ?? Date.now(),
          started_at: startedAt,
          finished_at: Date.now(),
        }
      : undefined;

  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-2xl text-text-hi font-semibold">回测实验室</h1>
        <div className="text-text-faint text-xs mt-1 tracking-wide uppercase">
          Backtest Lab · Agent vs Baseline
        </div>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <button
          className="btn primary"
          onClick={() => {
            setUiError(null);
            setShowFormModal(true);
          }}
          style={{ padding: '6px 16px', fontSize: 13, fontWeight: 600 }}
          title="打开新建回测表单"
        >
          + 新建回测
        </button>
        <button
            className="btn"
            onClick={() => {
              if (window.confirm('清空所有回测历史？此操作不可撤销。')) {
                api.purgeBacktests().then(() => {
                  setSessionId(null);
                  setStartedAt(null);
                  setUiError(null);
                  window.location.reload();
                });
              }
            }}
            style={{ padding: '4px 12px', fontSize: 12, color: 'var(--down)', borderColor: 'var(--down-border)' }}
            title="清空所有回测历史记录"
          >
            清空
          </button>
      </div>

      <div
        className="grid gap-5"
        style={{
          // History stays narrow so the result detail panel has breathing room.
          // sticky+max-height keeps history in its own column without bleeding
          // into the result area when scrolling long detail content.
          gridTemplateColumns: 'minmax(180px, 200px) minmax(0, 1fr)',
        }}
      >
        <div
          className="panel p-3"
          style={{
            alignSelf: 'start',
            position: 'sticky',
            top: 16,
            maxHeight: 'calc(100vh - 80px)',
            overflowY: 'auto',
            zIndex: 1,
          }}
        >
          <div className="flex items-baseline gap-2 mb-2">
            <h3 className="text-text-hi text-sm font-semibold">历史回测</h3>
            <span className="mono text-[9.5px] text-text-ghost uppercase tracking-wider">
              History
            </span>
          </div>
          <SessionsHistoryList
            selectedSessionId={sessionId}
            onSelect={(sid, kind) => {
              setUiError(null);
              setSessionMode(kind);
              setSessionId(sid);
              setStartedAt(null);
            }}
          />
        </div>
        <JobPanel
          sessionId={sessionId}
          job={syntheticJobStatus ?? jobStream.status ?? undefined}
          events={jobStream.events}
          session={session.data}
          error={pageError}
          startedAt={startedAt}
        />
      </div>

      {showFormModal && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center"
          style={{ background: 'rgba(0,0,0,0.6)', paddingTop: 60, overflowY: 'auto' }}
          onClick={() => setShowFormModal(false)}
        >
          <div
            className="panel panel-border-soft p-4"
            style={{ minWidth: 460, maxWidth: 600, width: '90%', marginBottom: 60 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-text-hi text-lg font-semibold">新建回测</h2>
              <button
                className="btn"
                onClick={() => setShowFormModal(false)}
                style={{ padding: '2px 10px', fontSize: 14 }}
                title="关闭"
              >
                ×
              </button>
            </div>
            <div className="panel p-2 mb-4 flex gap-1" style={{ width: 'fit-content' }}>
              <TabButton active={mode === 'agent'} onClick={() => setMode('agent')}>
                Agent 模式
              </TabButton>
              <TabButton active={mode === 'rule'} onClick={() => setMode('rule')}>
                规则模式
              </TabButton>
            </div>
            {mode === 'agent' ? (
              <BacktestForm
                state={form}
                setState={patch}
                personas={personas}
                models={models}
                busy={busy}
                onSubmit={onSubmit}
                coverageValidation={agentValidation}
              />
            ) : (
              <RuleBacktestForm
                state={ruleForm}
                setState={patchRule}
                strategies={strategies}
                busy={busy}
                onSubmit={onSubmitRule}
                coverageValidation={ruleValidation}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
