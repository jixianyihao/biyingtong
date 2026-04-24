import { useEffect, useMemo, useRef, useState } from 'react';
import { useQueries } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  useAgents,
  useBacktestNav,
  useSession,
  useSessions,
} from '../api/hooks';
import { api } from '../api/client';
import {
  ColorType,
  LineStyle,
  createChart,
  type UTCTimestamp,
} from 'lightweight-charts';
import type {
  Agent,
  BacktestResult,
  NavResponse,
  SessionSummary,
} from '../api/types';

// ─── helpers ──────────────────────────────────────────────────────────────
function fmt(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '—';
  return v.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—';
  const sign = v > 0 ? '+' : '';
  return `${sign}${v.toFixed(2)}%`;
}

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  // SQLite CURRENT_TIMESTAMP returns "YYYY-MM-DD HH:MM:SS" in UTC.
  // Normalize to ISO so the browser parses correctly.
  const raw = iso.includes('T') ? iso : iso.replace(' ', 'T') + 'Z';
  const t = new Date(raw).getTime();
  if (Number.isNaN(t)) return iso;
  const diffSec = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (diffSec < 60) return '刚刚';
  const mins = Math.floor(diffSec / 60);
  if (mins < 60) return `${mins} 分钟前`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} 小时前`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return '昨天';
  if (days < 7) return `${days} 天前`;
  if (days < 30) return `${Math.floor(days / 7)} 周前`;
  return `${Math.floor(days / 30)} 个月前`;
}

function trustColor(rating: string): string {
  const r = (rating || '').toUpperCase();
  if (r === 'A+') return 'var(--brand)';
  if (r === 'A') return 'var(--warn)';
  if (r === 'B') return 'var(--info)';
  if (r === 'C') return 'var(--down)';
  return 'var(--text-faint)';
}

function qualityPillCls(label: string): string {
  if (label === 'pass') return 'pill up';
  if (label === 'fail') return 'pill down';
  return 'pill';
}

function qualityPillLabel(label: string): string {
  if (label === 'pass') return '达标';
  if (label === 'warn') return '留意';
  if (label === 'fail') return '不达标';
  return label || '—';
}

// ─── Stat card ────────────────────────────────────────────────────────────
function StatCard({
  icon,
  label,
  subLabel,
  value,
  valueAccent,
  footer,
}: {
  icon: string;
  label: string;
  subLabel?: string;
  value: string;
  valueAccent?: string;
  footer?: React.ReactNode;
}) {
  return (
    <div className="panel p-4 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <div
          className="flex items-center justify-center rounded"
          style={{
            width: 32,
            height: 32,
            background: 'var(--bg-2)',
            border: '1px solid var(--panel-border-soft)',
            fontSize: 16,
          }}
        >
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[10.5px] text-text-faint uppercase tracking-[0.1em]">
            {label}
          </div>
          {subLabel && (
            <div className="mono text-[9.5px] text-text-ghost tracking-wider uppercase">
              {subLabel}
            </div>
          )}
        </div>
      </div>
      <div
        className="mono text-2xl font-semibold"
        style={{ color: valueAccent ?? 'var(--text-hi)', letterSpacing: '-0.01em' }}
      >
        {value}
      </div>
      {footer && (
        <div className="text-[11px] text-text-faint">{footer}</div>
      )}
    </div>
  );
}

// ─── Row 2 Left: Recent sessions table ────────────────────────────────────
function RecentSessions({
  sessions,
  loading,
  error,
}: {
  sessions: SessionSummary[];
  loading: boolean;
  error: string | null;
}) {
  const navigate = useNavigate();
  const list = sessions.slice(0, 10);
  return (
    <div className="panel flex flex-col min-h-0">
      <div className="panel-head">
        <span className="panel-title">最近回测会话</span>
        <span className="mono text-[10px] text-text-ghost tracking-wider uppercase">
          Recent Sessions
        </span>
        <span style={{ flex: 1 }} />
        <span className="mono text-[10px] text-text-faint">
          {sessions.length} 条
        </span>
      </div>
      <div className="overflow-auto" style={{ maxHeight: 360 }}>
        {loading && (
          <div className="p-6 text-text-faint text-sm">加载中…</div>
        )}
        {error && (
          <div className="p-5 text-down text-sm">加载失败：{error}</div>
        )}
        {!loading && !error && list.length === 0 && (
          <div className="p-6 text-text-faint text-sm leading-relaxed">
            还没有回测会话 · 前往
            <span className="mono text-brand"> 回测实验室 </span>
            发起第一次回测。
          </div>
        )}
        {!loading && !error && list.length > 0 && (
          <table className="tbl">
            <thead>
              <tr>
                <th>会话</th>
                <th>区间</th>
                <th className="num">A / B</th>
                <th>创建</th>
              </tr>
            </thead>
            <tbody>
              {list.map((s) => {
                const short = s.session_id.length > 14
                  ? s.session_id.slice(0, 14) + '…'
                  : s.session_id;
                return (
                  <tr
                    key={s.session_id}
                    onClick={() =>
                      navigate(
                        `/backtest?session=${encodeURIComponent(s.session_id)}`,
                      )
                    }
                    style={{ cursor: 'pointer' }}
                  >
                    <td className="mono text-[11.5px] text-text-hi">
                      {short}
                      {s.notes && (
                        <div className="text-[10px] text-text-faint mt-0.5">
                          {s.notes}
                        </div>
                      )}
                    </td>
                    <td className="mono text-[11px] text-text">
                      {s.start_date}
                      <div className="text-[10px] text-text-faint">
                        → {s.end_date}
                      </div>
                    </td>
                    <td className="num">
                      <span className="mono text-[11.5px] text-text-hi">
                        {s.agent_count}
                      </span>
                      <span className="mono text-[11.5px] text-text-faint">
                        {' / '}{s.baseline_count}
                      </span>
                    </td>
                    <td className="text-[11px] text-text">
                      {relativeTime(s.created_at)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ─── Row 2 Right: Trust distribution ──────────────────────────────────────
function TrustDistribution({ agents }: { agents: Agent[] }) {
  const buckets = useMemo(() => {
    const counts: Record<string, number> = { 'A+': 0, A: 0, B: 0, C: 0 };
    let other = 0;
    for (const a of agents) {
      const r = (a.trust_rating || '').toUpperCase();
      if (r in counts) counts[r] += 1;
      else other += 1;
    }
    return { counts, other };
  }, [agents]);

  const ratings = ['A+', 'A', 'B', 'C'] as const;
  const max = Math.max(
    1,
    ...ratings.map((r) => buckets.counts[r]),
    buckets.other,
  );

  return (
    <div className="panel flex flex-col min-h-0">
      <div className="panel-head">
        <span className="panel-title">信任评分分布</span>
        <span className="mono text-[10px] text-text-ghost tracking-wider uppercase">
          Trust Rating Distribution
        </span>
      </div>
      <div className="p-4 flex flex-col gap-3">
        {ratings.map((r) => {
          const n = buckets.counts[r];
          const pct = (n / max) * 100;
          const color = trustColor(r);
          return (
            <div key={r} className="flex items-center gap-3">
              <div
                className="mono text-sm font-semibold"
                style={{ width: 24, color }}
              >
                {r}
              </div>
              <div
                className="flex-1 rounded overflow-hidden"
                style={{
                  height: 16,
                  background: 'var(--bg-2)',
                  border: '1px solid var(--panel-border-soft)',
                }}
              >
                <div
                  style={{
                    width: `${pct}%`,
                    height: '100%',
                    background: color,
                    transition: 'width 0.3s ease',
                  }}
                />
              </div>
              <div
                className="mono text-sm font-semibold"
                style={{ width: 36, textAlign: 'right', color }}
              >
                {n}
              </div>
            </div>
          );
        })}
        {buckets.other > 0 && (
          <div className="text-[10.5px] text-text-faint mt-1">
            + {buckets.other} 未分级
          </div>
        )}
        {agents.length === 0 && (
          <div className="text-[11px] text-text-faint leading-relaxed">
            尚无 Agent · 创建 Agent 后将基于 audit_log 自动评估健康分与评级。
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Row 3: Top Performers ────────────────────────────────────────────────
type PerformerRow = {
  agent: Agent;
  result: BacktestResult | null;
};

function TopPerformers({ agents }: { agents: Agent[] }) {
  // Fetch latest backtest per agent in parallel
  const queries = useQueries({
    queries: agents.map((a) => ({
      queryKey: ['agent-backtests', a.id, 1],
      queryFn: () => api.backtestsForAgent(a.id, 1),
      staleTime: 30_000,
    })),
  });

  const rows: PerformerRow[] = agents.map((agent, i) => ({
    agent,
    result: queries[i]?.data?.[0] ?? null,
  }));

  const anyLoading = queries.some((q) => q.isLoading);
  const anyError = queries.find((q) => q.isError);

  // Sort by most recent backtest total_return_pct, descending. Agents without
  // a backtest drop to the bottom.
  const sorted = [...rows]
    .filter((r) => r.result != null)
    .sort((a, b) => {
      const ra = a.result?.stats.total_return_pct ?? -Infinity;
      const rb = b.result?.stats.total_return_pct ?? -Infinity;
      return rb - ra;
    })
    .slice(0, 5);

  return (
    <div className="panel flex flex-col">
      <div className="panel-head">
        <span className="panel-title">近期最佳表现</span>
        <span className="mono text-[10px] text-text-ghost tracking-wider uppercase">
          Top Performers · by latest backtest return
        </span>
        <span style={{ flex: 1 }} />
        {anyLoading && (
          <span className="mono text-[10px] text-text-faint">加载中…</span>
        )}
      </div>
      <div className="overflow-auto">
        {anyError && (
          <div className="p-4 text-down text-sm">
            部分回测拉取失败 ·
            {anyError.error instanceof Error ? ' ' + anyError.error.message : ''}
          </div>
        )}
        {!anyLoading && agents.length === 0 && (
          <div className="p-6 text-text-faint text-sm leading-relaxed">
            尚无 Agent · 创建 Agent 并运行一次回测后，此处将展示胜率 Top 5。
          </div>
        )}
        {!anyLoading && agents.length > 0 && sorted.length === 0 && (
          <div className="p-6 text-text-faint text-sm leading-relaxed">
            所有 Agent 都还没有回测记录 · 前往
            <span className="mono text-brand"> 回测实验室 </span>
            发起回测以解锁排行。
          </div>
        )}
        {sorted.length > 0 && (
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: 28 }}>#</th>
                <th>Agent</th>
                <th>Persona · Model</th>
                <th className="num">收益率</th>
                <th className="num">Sharpe</th>
                <th>质量</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r, i) => {
                const ret = r.result?.stats.total_return_pct ?? 0;
                const retColor =
                  ret > 0 ? 'var(--up)' : ret < 0 ? 'var(--down)' : 'var(--text)';
                return (
                  <tr key={r.agent.id}>
                    <td
                      className="mono text-[11px] font-semibold"
                      style={{ color: i === 0 ? 'var(--brand)' : 'var(--text-faint)' }}
                    >
                      {i + 1}
                    </td>
                    <td className="text-text-hi text-[12.5px] font-semibold">
                      {r.agent.display_name}
                    </td>
                    <td className="mono text-[11px] text-text-dim">
                      {r.agent.persona_id}
                      <span className="text-text-ghost"> · </span>
                      {r.agent.model_id}
                    </td>
                    <td
                      className="num mono text-[12.5px] font-semibold"
                      style={{ color: retColor }}
                    >
                      {fmtPct(ret)}
                    </td>
                    <td className="num mono text-[11.5px] text-text">
                      {r.result ? fmt(r.result.stats.sharpe, 2) : '—'}
                    </td>
                    <td>
                      <span
                        className={qualityPillCls(r.result?.quality_gate_label ?? '')}
                        style={{ fontSize: 10 }}
                      >
                        {qualityPillLabel(r.result?.quality_gate_label ?? '')}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ─── Compare Sessions ─────────────────────────────────────────────────────
const COMPARE_COLORS = ['#c9a227', '#3b82f6']; // gold + blue

function toTs(dateStr: string): UTCTimestamp {
  return Math.floor(new Date(dateStr + 'T00:00:00Z').getTime() / 1000) as UTCTimestamp;
}

function CompareNavChart({
  navA,
  navB,
  labelA,
  labelB,
}: {
  navA: NavResponse | undefined;
  navB: NavResponse | undefined;
  labelA: string;
  labelB: string;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    const chart = createChart(container, {
      width: container.clientWidth || 600,
      height: 280,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#8a8a8a',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(120,120,120,0.15)', style: LineStyle.Dotted },
        horzLines: { color: 'rgba(120,120,120,0.15)', style: LineStyle.Dotted },
      },
      timeScale: { borderColor: 'rgba(120,120,120,0.3)', timeVisible: false },
      rightPriceScale: { borderColor: 'rgba(120,120,120,0.3)' },
      crosshair: { mode: 1 },
    });

    if (navA && navA.agent.length > 0) {
      const s = chart.addLineSeries({
        color: COMPARE_COLORS[0],
        lineWidth: 2,
        title: labelA,
      });
      s.setData(navA.agent.map((p) => ({ time: toTs(p.date), value: p.equity })));
    }
    if (navB && navB.agent.length > 0) {
      const s = chart.addLineSeries({
        color: COMPARE_COLORS[1],
        lineWidth: 2,
        title: labelB,
      });
      s.setData(navB.agent.map((p) => ({ time: toTs(p.date), value: p.equity })));
    }

    chart.timeScale().fitContent();

    const ro = new ResizeObserver((entries) => {
      for (const e of entries) chart.applyOptions({ width: e.contentRect.width });
    });
    ro.observe(container);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [navA, navB, labelA, labelB]);

  return (
    <div>
      <div ref={containerRef} style={{ width: '100%', height: 280 }} />
      <div className="flex flex-wrap gap-3 mt-2 text-[11px]">
        <span className="inline-flex items-center gap-1.5">
          <span
            style={{
              width: 14,
              height: 3,
              background: COMPARE_COLORS[0],
              borderRadius: 1,
              display: 'inline-block',
            }}
          />
          <span className="text-text-dim">{labelA || 'Session A'}</span>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span
            style={{
              width: 14,
              height: 3,
              background: COMPARE_COLORS[1],
              borderRadius: 1,
              display: 'inline-block',
            }}
          />
          <span className="text-text-dim">{labelB || 'Session B'}</span>
        </span>
      </div>
    </div>
  );
}

function CompareSessionsPanel() {
  const sessions = useSessions(20);
  const list = sessions.data ?? [];
  const [sidA, setSidA] = useState<string>('');
  const [sidB, setSidB] = useState<string>('');

  const sessionA = useSession(sidA || undefined, !!sidA);
  const sessionB = useSession(sidB || undefined, !!sidB);

  const ridA = sessionA.data?.agents?.[0]?.id;
  const ridB = sessionB.data?.agents?.[0]?.id;

  const navA = useBacktestNav(ridA);
  const navB = useBacktestNav(ridB);

  return (
    <div className="panel p-5">
      <div className="flex items-baseline gap-2 mb-3 flex-wrap">
        <h2 className="text-text-hi text-base font-semibold">Session 对比</h2>
        <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
          Compare Sessions
        </span>
      </div>

      <div
        className="grid gap-3 mb-4"
        style={{ gridTemplateColumns: '1fr 1fr' }}
      >
        <div>
          <label className="text-[10px] text-text-faint uppercase tracking-wider mb-1 block">
            Session A
          </label>
          <select
            className="w-full bg-bg-2 border border-panel-border-soft rounded px-3 py-2 text-sm text-text-hi"
            value={sidA}
            onChange={(e) => setSidA(e.target.value)}
            disabled={sessions.isLoading}
          >
            <option value="">{sessions.isLoading ? '加载中…' : '请选择'}</option>
            {list.map((s) => (
              <option key={s.session_id} value={s.session_id}>
                {s.session_id.slice(0, 18)} · {s.start_date} → {s.end_date}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-[10px] text-text-faint uppercase tracking-wider mb-1 block">
            Session B
          </label>
          <select
            className="w-full bg-bg-2 border border-panel-border-soft rounded px-3 py-2 text-sm text-text-hi"
            value={sidB}
            onChange={(e) => setSidB(e.target.value)}
            disabled={sessions.isLoading}
          >
            <option value="">{sessions.isLoading ? '加载中…' : '请选择'}</option>
            {list.map((s) => (
              <option key={s.session_id} value={s.session_id}>
                {s.session_id.slice(0, 18)} · {s.start_date} → {s.end_date}
              </option>
            ))}
          </select>
        </div>
      </div>

      {!sidA && !sidB ? (
        <div className="text-text-faint text-sm italic">
          选择两个 session 进行 NAV 曲线叠加对比。
        </div>
      ) : (
        <CompareNavChart
          navA={navA.data}
          navB={navB.data}
          labelA={sidA.slice(0, 12) || 'A'}
          labelB={sidB.slice(0, 12) || 'B'}
        />
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────
export function Dashboard() {
  const agentsQ = useAgents();
  const sessionsQ = useSessions();

  const agents = agentsQ.data ?? [];
  const sessions = sessionsQ.data ?? [];

  const totalCapital = agents.reduce(
    (s, a) => s + (a.initial_capital || 0),
    0,
  );
  const activeAgents = agents.filter((a) =>
    ['active', 'running', 'live'].includes((a.status || '').toLowerCase()),
  ).length;
  const avgHealth = agents.length
    ? agents.reduce((s, a) => s + (a.health_score || 0), 0) / agents.length
    : 0;

  const sessionsLoading = sessionsQ.isLoading;
  const sessionsError =
    sessionsQ.isError
      ? sessionsQ.error instanceof Error
        ? sessionsQ.error.message
        : '未知错误'
      : null;

  return (
    <div className="p-5 flex flex-col gap-4 min-h-full">
      {/* page heading */}
      <div className="flex items-baseline gap-2 flex-wrap">
        <h1 className="text-2xl text-text-hi font-semibold">我的盈亏</h1>
        <div className="mono text-[11px] text-text-ghost uppercase tracking-wider">
          Dashboard · Portfolio Overview
        </div>
        <span style={{ flex: 1 }} />
        <span className="pill brand">
          <span className="live-dot" />
          {agents.length} Agents · {sessions.length} Sessions
        </span>
      </div>

      {/* Row 1 — Stat cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          icon="🤖"
          label="Agent 总数"
          subLabel="Agents"
          value={String(agents.length)}
          valueAccent="var(--brand)"
          footer={
            <span>
              运行中{' '}
              <span className="mono text-text-hi">{activeAgents}</span>
              {' / '}
              待机{' '}
              <span className="mono text-text">
                {agents.length - activeAgents}
              </span>
            </span>
          }
        />
        <StatCard
          icon="📊"
          label="回测会话"
          subLabel="Sessions"
          value={String(sessions.length)}
          valueAccent="var(--info)"
          footer={
            sessions[0]
              ? (
                <span>
                  最近 <span className="mono text-text">
                    {relativeTime(sessions[0].created_at)}
                  </span>
                </span>
              )
              : <span>暂无记录</span>
          }
        />
        <StatCard
          icon="💰"
          label="总初始资金"
          subLabel="Total Capital"
          value={`¥${fmt(totalCapital, 0)}`}
          valueAccent="var(--text-hi)"
          footer={
            agents.length > 0
              ? (
                <span>
                  均值{' '}
                  <span className="mono text-text">
                    ¥{fmt(totalCapital / agents.length, 0)}
                  </span>
                </span>
              )
              : <span>尚未分配</span>
          }
        />
        <StatCard
          icon="💎"
          label="平均健康"
          subLabel="Avg Health Score"
          value={agents.length ? String(Math.round(avgHealth)) : '—'}
          valueAccent={
            avgHealth >= 70
              ? 'var(--brand)'
              : avgHealth >= 40
                ? 'var(--info)'
                : 'var(--down)'
          }
          footer={
            <div
              className="rounded overflow-hidden"
              style={{
                height: 4,
                background: 'var(--bg-2)',
                border: '1px solid var(--panel-border-soft)',
              }}
            >
              <div
                style={{
                  width: `${Math.max(0, Math.min(100, avgHealth))}%`,
                  height: '100%',
                  background:
                    avgHealth >= 70
                      ? 'var(--brand)'
                      : avgHealth >= 40
                        ? 'var(--info)'
                        : 'var(--down)',
                }}
              />
            </div>
          }
        />
      </div>

      {/* Row 2 — Sessions (60%) + Trust distribution (40%) */}
      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: 'minmax(0, 3fr) minmax(0, 2fr)' }}
      >
        <RecentSessions
          sessions={sessions}
          loading={sessionsLoading}
          error={sessionsError}
        />
        <TrustDistribution agents={agents} />
      </div>

      {/* Row 3 — Top performers */}
      <TopPerformers agents={agents} />

      {/* Row 4 — Compare Sessions (NAV overlay) */}
      <CompareSessionsPanel />
    </div>
  );
}
