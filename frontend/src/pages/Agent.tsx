import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  useAgent,
  useAgents,
  useCreateAgent,
  useDeletePersona,
  useModels,
  usePersonas,
} from '../api/hooks';
import type { Agent, ModelInfo, Persona } from '../api/types';
import { AgentEditModal } from '../components/AgentEditModal';
import { AgentDeleteDialog } from '../components/AgentDeleteDialog';
import { PersonaFormModal } from '../components/PersonaFormModal';

// ─── styling helpers ───────────────────────────────────────────────────────
const inputCls =
  'w-full bg-bg-2 border border-panel-border-soft rounded px-3 py-2 text-sm text-text-hi focus:outline-none focus:border-brand transition-colors';
const sectionLabelCls =
  'text-[10px] text-text-faint uppercase tracking-[0.1em] mb-2';

function fmt(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '—';
  return v.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function seedRand(seed: number) {
  let s = seed;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

// Map persona_id → accent colour so agent cards stay visually distinct.
function personaColor(id: string | null | undefined): string {
  const table: Record<string, string> = {
    linyuan: 'var(--brand)',
    fuyou: 'var(--up)',
    buffet: 'var(--info)',
    soros: 'var(--purple)',
    quant_neutral: 'var(--down)',
    intraday_t0: 'var(--warn)',
  };
  if (!id) return 'var(--text-dim)';
  return table[id] ?? 'var(--brand)';
}

// ─── subcomponents: tiny building blocks ───────────────────────────────────
function StatCell({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: 'brand' | 'up' | 'down' | 'hi';
}) {
  const color =
    accent === 'brand'
      ? 'var(--brand)'
      : accent === 'up'
        ? 'var(--up)'
        : accent === 'down'
          ? 'var(--down)'
          : 'var(--text-hi)';
  return (
    <div className="bg-bg-2 border border-panel-border-soft rounded px-2.5 py-2">
      <div className="text-[10px] text-text-faint uppercase tracking-wider">
        {label}
      </div>
      <div
        className="mono text-sm font-semibold mt-1"
        style={{ color }}
      >
        {value}
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const s = (status || '').toLowerCase();
  const cls =
    s === 'active' || s === 'running' || s === 'live'
      ? 'pill up'
      : s === 'paused' || s === 'stopped'
        ? 'pill down'
        : s === 'idle' || s === 'created'
          ? 'pill brand'
          : 'pill';
  const label =
    s === 'active'
      ? '运行中'
      : s === 'paused'
        ? '已暂停'
        : s === 'idle'
          ? '待机'
          : s === 'created'
            ? '新建'
            : status || '未知';
  return <span className={cls}>{label}</span>;
}

function TrustPill({ rating }: { rating: string }) {
  const r = (rating || '').toLowerCase();
  const cls =
    r === 'trusted' || r === 'a' || r === 's'
      ? 'pill brand'
      : r === 'probation' || r === 'c'
        ? 'pill down'
        : 'pill';
  return <span className={cls}>{rating || '—'}</span>;
}

// ─── Sparkline — inline SVG, no canvas complexity ──────────────────────────
function Sparkline({
  seed,
  points = 40,
  trend = 0,
  volatility = 1,
  color,
  width = 200,
  height = 24,
}: {
  seed: number;
  points?: number;
  trend?: number;
  volatility?: number;
  color: string;
  width?: number;
  height?: number;
}) {
  const data = useMemo(() => {
    const rand = seedRand(seed);
    const arr: number[] = [];
    let v = 0;
    for (let i = 0; i < points; i++) {
      v += trend + (rand() - 0.5) * volatility;
      arr.push(v);
    }
    return arr;
  }, [seed, points, trend, volatility]);

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const step = width / (points - 1);
  const path = data
    .map((v, i) => {
      const x = i * step;
      const y = height - ((v - min) / range) * height;
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <path d={path} fill="none" stroke={color} strokeWidth={1.2} />
    </svg>
  );
}

// ─── Agent list item — left sidebar ────────────────────────────────────────
function AgentListItem({
  agent,
  persona,
  model,
  selected,
  onClick,
}: {
  agent: Agent;
  persona: Persona | undefined;
  model: ModelInfo | undefined;
  selected: boolean;
  onClick: () => void;
}) {
  const color = personaColor(agent.persona_id);
  return (
    <div
      onClick={onClick}
      className="p-3 cursor-pointer rounded transition-colors"
      style={{
        background: selected ? 'var(--bg-3)' : 'var(--bg-2)',
        border: '1px solid ' + (selected ? color : 'var(--panel-border-soft)'),
      }}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <div
          style={{
            width: 7,
            height: 7,
            borderRadius: 2,
            background: color,
            flexShrink: 0,
          }}
        />
        <div className="text-text-hi font-semibold text-[13px] truncate flex-1">
          {agent.display_name}
        </div>
        <StatusPill status={agent.status} />
      </div>
      <div className="mono text-[10px] text-text-ghost tracking-wider uppercase">
        {persona?.name ?? agent.persona_id}
        {model && <> · {model.display_name}</>}
      </div>
      <div className="mt-2">
        <Sparkline
          seed={(agent.id || 'x').split('').reduce((a, c) => a + c.charCodeAt(0), 0)}
          color={color}
          trend={agent.health_score > 50 ? 0.2 : -0.1}
          volatility={1.2}
        />
      </div>
      <div className="flex gap-3 mt-1 text-[10px] text-text-faint">
        <span>
          健康 <span className="mono text-text-hi">{Math.round(agent.health_score)}</span>
        </span>
        <span>
          评级 <span className="mono text-text-hi">{agent.trust_rating || '—'}</span>
        </span>
      </div>
    </div>
  );
}

// ─── AgentDetail — right panel ─────────────────────────────────────────────
function AgentDetail({
  agentId,
  personas,
  models,
  onShowPrompt,
  onEdit,
  onDelete,
}: {
  agentId: string | null;
  personas: Persona[];
  models: ModelInfo[];
  onShowPrompt: (personaId: string) => void;
  onEdit: (agent: Agent) => void;
  onDelete: (agent: Agent) => void;
}) {
  const q = useAgent(agentId ?? undefined);
  const agent = q.data;

  if (!agentId) {
    return (
      <div className="panel p-8 flex items-center justify-center text-text-faint text-sm">
        请从左侧选择一位 AI 操盘手查看详情。
      </div>
    );
  }
  if (q.isLoading) {
    return (
      <div className="panel p-8 text-text-faint text-sm">
        正在加载 Agent 详情…
      </div>
    );
  }
  if (q.isError || !agent) {
    return (
      <div className="panel p-5">
        <div className="text-down text-sm">
          加载失败：{q.error instanceof Error ? q.error.message : '未知错误'}
        </div>
      </div>
    );
  }

  const persona = personas.find((p) => p.id === agent.persona_id);
  const model = models.find((m) => m.id === agent.model_id);
  const color = personaColor(agent.persona_id);
  const rulesEntries = Object.entries(agent.rules_override || {});

  return (
    <div className="panel p-5 flex flex-col gap-5 min-h-0">
      {/* header */}
      <div className="flex items-start gap-3 flex-wrap">
        <div
          style={{
            width: 10,
            height: 10,
            borderRadius: 3,
            background: color,
            marginTop: 8,
            flexShrink: 0,
          }}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <h2 className="text-text-hi text-lg font-semibold">
              {agent.display_name}
            </h2>
            <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
              Agent Profile
            </span>
          </div>
          <div className="mono text-[11px] text-text-faint mt-1 break-all">
            id: <span className="text-text">{agent.id}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <StatusPill status={agent.status} />
          <button
            className="btn ghost"
            onClick={() => onEdit(agent)}
            style={{ padding: '3px 10px', fontSize: 11 }}
            title="编辑 Agent"
          >
            编辑
          </button>
          <button
            className="btn ghost"
            onClick={() => onDelete(agent)}
            style={{
              padding: '3px 10px',
              fontSize: 11,
              color: 'var(--down)',
              borderColor: 'var(--down-border)',
            }}
            title="删除 Agent"
          >
            删除
          </button>
        </div>
      </div>

      {/* stats grid */}
      <div className="grid grid-cols-4 gap-2.5">
        <StatCell
          label="健康分"
          value={String(Math.round(agent.health_score))}
          accent={agent.health_score >= 70 ? 'brand' : agent.health_score < 40 ? 'down' : 'hi'}
        />
        <StatCell label="信用评级" value={agent.trust_rating || '—'} accent="hi" />
        <StatCell
          label="初始资金"
          value={`¥${fmt(agent.initial_capital, 0)}`}
          accent="hi"
        />
        <StatCell
          label="Prompt 版本"
          value={(() => {
            const pv = agent.current_prompt_version_id;
            return pv ? `v${String(pv).slice(0, 6)}` : '—';
          })()}
          accent="brand"
        />
      </div>
      <div className="flex justify-end -mt-1">
        <Link
          to={`/agent/${agent.id}/prompts`}
          className="mono text-[11px] uppercase tracking-wider"
          style={{
            color: 'var(--brand)',
            textDecoration: 'none',
            padding: '2px 4px',
          }}
          title="查看 Prompt 版本历史"
        >
          查看版本历史 · View History →
        </Link>
      </div>

      {/* persona + model */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className={sectionLabelCls}>Persona · 操盘风格</div>
          <div className="bg-bg-2 border border-panel-border-soft rounded p-3">
            <div className="text-text-hi font-semibold text-sm">
              {persona?.name ?? agent.persona_id}
            </div>
            <div className="mono text-[10px] text-text-ghost uppercase tracking-wider mt-1">
              {agent.persona_id}
            </div>
            <div className="serif text-[12.5px] text-text mt-2 italic leading-relaxed">
              “{persona?.style_desc ?? '—'}”
            </div>
            <button
              className="btn ghost mt-3 text-xs"
              onClick={() => onShowPrompt(agent.persona_id)}
              style={{ padding: '4px 10px' }}
            >
              查看 System Prompt
            </button>
          </div>
        </div>
        <div>
          <div className={sectionLabelCls}>Model · 大模型</div>
          <div className="bg-bg-2 border border-panel-border-soft rounded p-3">
            <div className="text-text-hi font-semibold text-sm">
              {model?.display_name ?? agent.model_id}
            </div>
            <div className="mono text-[10px] text-text-ghost uppercase tracking-wider mt-1">
              {model?.provider ?? '—'} · {model?.api_model_id ?? agent.model_id}
            </div>
            <div className="flex gap-3 mt-2 text-[11px] text-text-faint">
              <span>
                工具 <span className="mono text-text-hi">
                  {model?.supports_tool_use ? '✓' : '—'}
                </span>
              </span>
              <span>
                最大输出 <span className="mono text-text-hi">{model?.max_tokens_out ?? '—'}</span>
              </span>
              <span>
                训练截止 <span className="mono text-text-hi">{model?.training_cutoff ?? '—'}</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* rules override */}
      <div>
        <div className={sectionLabelCls}>Rules Override · 风险参数覆盖</div>
        {rulesEntries.length === 0 ? (
          <div className="bg-bg-2 border border-panel-border-soft rounded px-3 py-3 text-text-faint text-sm">
            未覆盖 — 使用 persona 默认规则。
          </div>
        ) : (
          <div className="bg-bg-2 border border-panel-border-soft rounded overflow-hidden">
            <table className="tbl" style={{ margin: 0 }}>
              <thead>
                <tr>
                  <th>规则</th>
                  <th>覆盖值</th>
                </tr>
              </thead>
              <tbody>
                {rulesEntries.map(([k, v]) => (
                  <tr key={k}>
                    <td className="mono text-text-hi text-[11.5px]">{k}</td>
                    <td className="mono text-text text-[11.5px]">
                      {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* trust rating breakdown */}
      <div>
        <div className={sectionLabelCls}>Trust · 信用档案</div>
        <div className="flex items-center gap-3 flex-wrap">
          <TrustPill rating={agent.trust_rating} />
          <div className="flex-1 h-2 bg-bg-3 rounded overflow-hidden min-w-[120px]">
            <div
              style={{
                width: `${Math.max(0, Math.min(100, agent.health_score))}%`,
                height: '100%',
                background:
                  agent.health_score >= 70
                    ? 'var(--brand)'
                    : agent.health_score >= 40
                      ? 'var(--info)'
                      : 'var(--down)',
              }}
            />
          </div>
          <span className="mono text-[11px] text-text-faint">
            {Math.round(agent.health_score)} / 100
          </span>
        </div>
        <div className="text-[10.5px] text-text-faint mt-2">
          健康分由 audit_log 回放生成，评级每次触发
          <span className="mono text-text"> /api/agents/:id/health </span>
          后刷新。
        </div>
      </div>
    </div>
  );
}

// ─── Agent compare chart — Phase 3 placeholder ─────────────────────────────
function AgentCompareChart({
  agents,
  selected,
}: {
  agents: Agent[];
  selected: string | null;
}) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });

  useEffect(() => {
    const el = ref.current?.parentElement;
    if (!el) return;
    const ro = new ResizeObserver(() =>
      setSize({ w: el.clientWidth, h: el.clientHeight })
    );
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!size.w || !size.h) return;
    const cvs = ref.current;
    if (!cvs) return;
    const dpr = window.devicePixelRatio || 1;
    cvs.width = size.w * dpr;
    cvs.height = size.h * dpr;
    cvs.style.width = size.w + 'px';
    cvs.style.height = size.h + 'px';
    const ctx = cvs.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    const padL = 6;
    const padR = 40;
    const padT = 10;
    const padB = 16;
    const W = size.w;
    const H = size.h;
    ctx.clearRect(0, 0, W, H);

    if (agents.length === 0) {
      ctx.fillStyle = 'oklch(0.52 0.012 260)';
      ctx.font = '11px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('暂无 Agent 数据', W / 2, H / 2);
      return;
    }

    const N = 90;
    const curves = agents.map((a) => {
      const seed =
        (a.id || 'x').split('').reduce((s, c) => s + c.charCodeAt(0), 0) *
        31;
      const rand = seedRand(seed);
      const arr: number[] = [];
      let v = 100;
      const trend = ((a.health_score - 50) / 50) * 0.25;
      for (let i = 0; i < N; i++) {
        v += trend + (rand() - 0.5) * 1.2;
        arr.push(v);
      }
      return { id: a.id, arr, color: personaColor(a.persona_id) };
    });
    const all = curves.flatMap((c) => c.arr);
    const mn = Math.min(...all);
    const mx = Math.max(...all);
    const pad = (mx - mn) * 0.05 || 1;
    const lo = mn - pad;
    const hi = mx + pad;
    const x = (i: number) => padL + (i / (N - 1)) * (W - padL - padR);
    const y = (v: number) => padT + ((hi - v) / (hi - lo)) * (H - padT - padB);

    // gridlines
    ctx.strokeStyle = 'oklch(0.22 0.010 260 / 0.4)';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const yy = padT + ((H - padT - padB) / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padL, yy);
      ctx.lineTo(W - padR, yy);
      ctx.stroke();
      ctx.fillStyle = 'oklch(0.52 0.012 260)';
      ctx.font = '9px JetBrains Mono';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText(
        (hi - ((hi - lo) / 4) * i).toFixed(0),
        W - padR + 3,
        yy
      );
    }
    // baseline 100
    ctx.strokeStyle = 'oklch(0.52 0.012 260 / 0.5)';
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(padL, y(100));
    ctx.lineTo(W - padR, y(100));
    ctx.stroke();
    ctx.setLineDash([]);

    // curves
    curves.forEach((c) => {
      const sel = c.id === selected;
      ctx.strokeStyle = sel
        ? c.color
        : c.color.replace(')', ' / 0.35)').replace('var(', 'var(');
      ctx.lineWidth = sel ? 2 : 1;
      ctx.beginPath();
      c.arr.forEach((v, i) => {
        if (i === 0) ctx.moveTo(x(i), y(v));
        else ctx.lineTo(x(i), y(v));
      });
      ctx.stroke();
    });
  }, [size, agents, selected]);

  return <canvas ref={ref} style={{ display: 'block' }} />;
}

// ─── Autonomous Scheduler — Phase 3 scaffold ───────────────────────────────
function AutonomousScheduler() {
  const [autonomous, setAutonomous] = useState(false);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const hour = now.getHours();
  const minute = now.getMinutes();
  const day = now.getDay();
  const isWeekend = day === 0 || day === 6;
  const isMorning =
    hour >= 9 && (hour < 11 || (hour === 11 && minute < 30));
  const isAfternoon = hour >= 13 && hour < 15;
  const isTrading = !isWeekend && (isMorning || isAfternoon);
  const isPreMarket =
    !isWeekend && ((hour === 9 && minute < 30) || hour === 8);
  const isAfterHours = !isWeekend && hour >= 15 && hour < 18;

  const phase = isTrading
    ? { label: '盘中交易', color: 'var(--up)' }
    : isPreMarket
      ? { label: '盘前准备', color: 'var(--warn)' }
      : isAfterHours
        ? { label: '盘后复盘', color: 'var(--info)' }
        : { label: '夜间研究', color: 'var(--purple)' };

  const schedule = [
    { start: 0, end: 6, phase: '夜间', task: '回测新策略 · 参数优化' },
    { start: 6, end: 8, phase: '早间', task: '抓取隔夜新闻 · 情报简报' },
    { start: 8, end: 9.5, phase: '盘前', task: '异动筛选 · 开盘预测' },
    { start: 9.5, end: 11.5, phase: '早盘', task: '监控盘面 · 执行信号' },
    { start: 11.5, end: 13, phase: '午间', task: '午盘快报 · 调仓评估' },
    { start: 13, end: 15, phase: '午盘', task: '持续盯盘 · 止损止盈' },
    { start: 15, end: 18, phase: '盘后', task: '日报生成 · 绩效归因' },
    { start: 18, end: 24, phase: '夜间', task: '研究 · 公告挖掘' },
  ];
  const curHour = hour + minute / 60;
  const curTask =
    schedule.find((s) => s.start <= curHour && s.end > curHour)?.task ??
    '待机中';
  const fmtT = (d: Date) => d.toTimeString().slice(0, 8);

  return (
    <div
      className="panel p-4"
      style={{
        background:
          'linear-gradient(135deg, oklch(0.16 0.02 160) 0%, oklch(0.13 0.01 260) 60%)',
        border: '1px solid ' + phase.color + '44',
      }}
    >
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <div
          style={{
            width: 38,
            height: 38,
            borderRadius: '50%',
            background: autonomous ? phase.color + '22' : 'var(--bg-3)',
            border:
              '2px solid ' +
              (autonomous ? phase.color : 'var(--panel-border)'),
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: autonomous ? phase.color : 'var(--text-ghost)',
            flexShrink: 0,
            fontSize: 14,
            fontWeight: 700,
          }}
        >
          A
        </div>
        <div className="flex-1 min-w-[220px]">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className="text-[10.5px] text-text-faint tracking-[0.14em] uppercase">
              Autonomous Mode · 24/7 无人值守
            </span>
            <span
              className="pill"
              style={{
                background: 'var(--brand-soft)',
                border: '1px solid var(--brand-border)',
                color: 'var(--brand)',
                fontSize: 10,
              }}
            >
              Phase 3 接入 /api/backtests/jobs
            </span>
            {autonomous && (
              <span
                className="pill"
                style={{
                  background: phase.color + '22',
                  border: '1px solid ' + phase.color,
                  color: phase.color,
                  fontSize: 10,
                }}
              >
                <span
                  className="live-dot"
                  style={{ color: phase.color }}
                />{' '}
                {phase.label}
              </span>
            )}
          </div>
          <div
            className="serif mt-1 text-text-hi text-[18px] font-semibold"
            style={{ letterSpacing: '-0.01em' }}
          >
            {autonomous ? '调度器已启用 · 等待接入' : '调度器未启用'}
          </div>
          <div className="mono text-[11px] text-text-faint mt-0.5">
            ▸ 当前阶段：{phase.label} · {curTask}
          </div>
        </div>
        <div className="text-right">
          <div
            className="mono text-text-hi font-medium"
            style={{ fontSize: 18, letterSpacing: '0.02em' }}
          >
            {fmtT(now)}
          </div>
          <div className="mono text-[10px] text-text-faint mt-0.5">
            {['周日', '周一', '周二', '周三', '周四', '周五', '周六'][day]}
          </div>
        </div>
        <div
          onClick={() => setAutonomous((a) => !a)}
          style={{
            width: 50,
            height: 28,
            borderRadius: 14,
            padding: 3,
            cursor: 'pointer',
            background: autonomous ? 'var(--up)' : 'var(--bg-3)',
            border:
              '1px solid ' +
              (autonomous ? 'var(--up)' : 'var(--panel-border)'),
            transition: 'all 0.2s',
          }}
        >
          <div
            style={{
              width: 20,
              height: 20,
              borderRadius: '50%',
              background: 'white',
              transform: autonomous ? 'translateX(22px)' : 'translateX(0)',
              transition: 'transform 0.2s',
              boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
            }}
          />
        </div>
      </div>

      {/* 24h timeline */}
      <div
        className="relative h-10 bg-bg-2 rounded border border-panel-border-soft overflow-hidden"
      >
        {[0, 3, 6, 9, 12, 15, 18, 21].map((h) => (
          <div
            key={h}
            style={{
              position: 'absolute',
              left: (h / 24) * 100 + '%',
              top: 0,
              bottom: 0,
              width: 1,
              background: 'var(--panel-border-soft)',
            }}
          />
        ))}
        {schedule.map((s, i) => {
          const isPast = s.end <= curHour;
          const isActive = s.start <= curHour && s.end > curHour;
          const color =
            s.phase === '夜间'
              ? 'var(--purple)'
              : s.phase === '早间' || s.phase === '盘前'
                ? 'var(--warn)'
                : s.phase === '早盘' || s.phase === '午盘'
                  ? 'var(--up)'
                  : 'var(--info)';
          return (
            <div
              key={i}
              title={`${s.phase} ${s.start}:00-${s.end}:00 · ${s.task}`}
              style={{
                position: 'absolute',
                left: (s.start / 24) * 100 + '%',
                width: ((s.end - s.start) / 24) * 100 + '%',
                top: 6,
                bottom: 6,
                background: isActive ? color : color + '44',
                borderLeft: '2px solid ' + color,
                opacity: isPast && !isActive ? 0.35 : 1,
                display: 'flex',
                alignItems: 'center',
                padding: '0 5px',
                overflow: 'hidden',
                gap: 4,
              }}
            >
              <span
                style={{
                  fontSize: 9,
                  color: isActive ? 'white' : color,
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                }}
              >
                {s.phase}
              </span>
            </div>
          );
        })}
        {/* NOW marker */}
        <div
          style={{
            position: 'absolute',
            left: (curHour / 24) * 100 + '%',
            top: -2,
            bottom: -2,
            width: 2,
            background: 'var(--text-hi)',
            boxShadow: '0 0 6px var(--text-hi)',
          }}
        />
      </div>
      <div
        className="flex mono text-[9px] text-text-ghost mt-1"
        style={{ letterSpacing: '0.02em' }}
      >
        {[0, 3, 6, 9, 12, 15, 18, 21, 24].map((h) => (
          <span key={h} style={{ flex: h === 24 ? 0 : 1 }}>
            {String(h).padStart(2, '0')}:00
          </span>
        ))}
      </div>
    </div>
  );
}

// ─── Prompt Modal — shows the selected persona's system_prompt ─────────────
type PersonaDetail = Persona & {
  system_prompt: string;
  pool_filter?: Record<string, unknown>;
};

function PromptModal({
  personaId,
  onClose,
}: {
  personaId: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<PersonaDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let aborted = false;
    setData(null);
    setErr(null);
    fetch(`/api/personas/${encodeURIComponent(personaId)}`)
      .then(async (r) => {
        if (!r.ok) {
          throw new Error(`${r.status} ${r.statusText}`);
        }
        return (await r.json()) as PersonaDetail;
      })
      .then((d) => {
        if (!aborted) setData(d);
      })
      .catch((e) => {
        if (!aborted) setErr(e instanceof Error ? e.message : String(e));
      });
    return () => {
      aborted = true;
    };
  }, [personaId]);

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center p-10"
      style={{ background: 'oklch(0 0 0 / 0.6)' }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="panel flex flex-col"
        style={{
          width: 720,
          maxHeight: '82vh',
          boxShadow: '0 12px 40px oklch(0 0 0 / 0.6)',
        }}
      >
        <div className="panel-head">
          <span className="panel-title">Persona System Prompt</span>
          <span className="mono text-[10px] text-text-ghost tracking-wider uppercase">
            /api/personas/{personaId}
          </span>
          <span style={{ flex: 1 }} />
          <button
            className="btn ghost"
            onClick={onClose}
            style={{ padding: '2px 10px', fontSize: 12 }}
          >
            关闭
          </button>
        </div>
        <div className="p-4 overflow-auto min-h-[200px]">
          {err && (
            <div
              className="text-sm text-down p-3 rounded"
              style={{
                background: 'var(--down-bg)',
                border: '1px solid var(--down-border)',
              }}
            >
              加载失败：{err}
            </div>
          )}
          {!err && !data && (
            <div className="text-text-faint text-sm">加载中…</div>
          )}
          {data && (
            <>
              <div className="flex items-baseline gap-2 mb-3 flex-wrap">
                <div className="text-text-hi text-base font-semibold">
                  {data.name}
                </div>
                <div className="mono text-[10px] text-text-ghost uppercase tracking-wider">
                  {data.id}
                </div>
                {data.is_builtin && (
                  <span className="pill brand" style={{ fontSize: 10 }}>
                    内置
                  </span>
                )}
              </div>
              <div className="serif text-[13px] text-text italic mb-4 leading-relaxed">
                “{data.style_desc}”
              </div>

              <div className="text-[10px] text-text-faint uppercase tracking-[0.1em] mb-2">
                SYSTEM PROMPT
              </div>
              <pre
                className="mono bg-bg-2 border border-panel-border-soft rounded p-3 text-[11.5px] text-text whitespace-pre-wrap"
                style={{ lineHeight: 1.65, margin: 0 }}
              >
                {data.system_prompt}
              </pre>

              <div className="text-[10px] text-text-faint uppercase tracking-[0.1em] mb-2 mt-5">
                Allowed Tools
              </div>
              <div className="flex flex-wrap gap-1.5">
                {data.allowed_tools.map((t) => (
                  <span
                    key={t}
                    className="pill"
                    style={{
                      background: 'var(--info-soft)',
                      color: 'var(--info)',
                      fontSize: 10.5,
                    }}
                  >
                    {t}
                  </span>
                ))}
              </div>

              <div className="text-[10px] text-text-faint uppercase tracking-[0.1em] mb-2 mt-5">
                Default Rules
              </div>
              <pre
                className="mono bg-bg-2 border border-panel-border-soft rounded p-3 text-[11px] text-text"
                style={{ margin: 0 }}
              >
                {JSON.stringify(data.default_rules, null, 2)}
              </pre>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Create Agent Modal ────────────────────────────────────────────────────
type CreateForm = {
  persona_id: string;
  model_id: string;
  display_name: string;
  initial_capital: number;
  rules_override_raw: string;
};

const CAPITAL_PRESETS = [100_000, 500_000, 1_000_000, 5_000_000];

function CreateAgentModal({
  personas,
  models,
  onClose,
  onCreated,
}: {
  personas: Persona[];
  models: ModelInfo[];
  onClose: () => void;
  onCreated: (agent: Agent) => void;
}) {
  const createAgent = useCreateAgent();
  const [form, setForm] = useState<CreateForm>(() => ({
    persona_id: '',
    model_id: '',
    display_name: '',
    initial_capital: 1_000_000,
    rules_override_raw: '',
  }));
  const [err, setErr] = useState<string | null>(null);

  const patch = (p: Partial<CreateForm>) =>
    setForm((prev) => ({ ...prev, ...p }));

  const selectPersona = (p: Persona) => {
    patch({
      persona_id: p.id,
      display_name: form.display_name || `${p.name} · Agent`,
    });
  };

  async function submit() {
    setErr(null);
    if (!form.persona_id) {
      setErr('请选择 Persona。');
      return;
    }
    if (!form.model_id) {
      setErr('请选择 Model。');
      return;
    }
    if (!form.display_name.trim()) {
      setErr('请填写 Agent 名称。');
      return;
    }
    if (form.initial_capital <= 0) {
      setErr('初始资金必须大于 0。');
      return;
    }
    let rules_override: Record<string, unknown> | undefined;
    const raw = form.rules_override_raw.trim();
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        if (typeof parsed !== 'object' || Array.isArray(parsed) || parsed === null) {
          throw new Error('must be a JSON object');
        }
        rules_override = parsed as Record<string, unknown>;
      } catch (e) {
        setErr(
          'rules_override 不是合法 JSON 对象：' +
            (e instanceof Error ? e.message : String(e))
        );
        return;
      }
    }

    try {
      const agent = await createAgent.mutateAsync({
        persona_id: form.persona_id,
        model_id: form.model_id,
        display_name: form.display_name.trim(),
        initial_capital: form.initial_capital,
        rules_override,
      });
      onCreated(agent);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

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
          width: 820,
          maxHeight: '86vh',
          boxShadow: '0 20px 60px oklch(0 0 0 / 0.7)',
        }}
      >
        <div
          className="panel-head"
          style={{ background: 'var(--brand-soft)' }}
        >
          <span className="panel-title" style={{ color: 'var(--brand)' }}>
            创建 AI 操盘手
          </span>
          <span className="mono text-[10px] text-text-ghost tracking-wider uppercase ml-1">
            Create Agent · persona + model
          </span>
          <span style={{ flex: 1 }} />
          <button
            className="btn ghost"
            onClick={onClose}
            style={{ padding: '2px 10px', fontSize: 12 }}
          >
            关闭
          </button>
        </div>

        <div className="p-4 overflow-auto grid grid-cols-2 gap-4">
          {/* LEFT: persona picker */}
          <div>
            <div className={sectionLabelCls}>① 选择 Persona · 操盘风格</div>
            <div className="grid grid-cols-2 gap-2 mb-4">
              {personas.length === 0 && (
                <div className="col-span-2 text-text-faint text-sm p-3">
                  暂无 persona — 请先运行 personas.seed()。
                </div>
              )}
              {personas.map((p) => {
                const sel = form.persona_id === p.id;
                const color = personaColor(p.id);
                return (
                  <div
                    key={p.id}
                    onClick={() => selectPersona(p)}
                    className="p-2.5 cursor-pointer rounded"
                    style={{
                      background: sel ? 'var(--bg-3)' : 'var(--bg-2)',
                      border:
                        '1px solid ' +
                        (sel ? color : 'var(--panel-border-soft)'),
                    }}
                  >
                    <div className="flex items-center gap-1.5">
                      <div
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: 2,
                          background: color,
                          flexShrink: 0,
                        }}
                      />
                      <div className="text-text-hi font-semibold text-[12.5px] truncate">
                        {p.name}
                      </div>
                    </div>
                    <div className="text-[10.5px] text-text-faint mt-1 line-clamp-2">
                      {p.style_desc}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className={sectionLabelCls}>② Rules Override · 可选 JSON</div>
            <textarea
              value={form.rules_override_raw}
              onChange={(e) => patch({ rules_override_raw: e.target.value })}
              placeholder={`{ "max_position_pct": 0.15, "stop_loss_pct": -0.08 }`}
              className="w-full p-2.5 rounded mono text-[11px]"
              style={{
                height: 150,
                background: 'var(--bg-2)',
                border: '1px solid var(--panel-border)',
                color: 'var(--text)',
                resize: 'vertical',
                lineHeight: 1.6,
              }}
            />
            <div className="text-[10px] text-text-ghost mt-1">
              留空则使用 persona 默认规则 · 必须是合法 JSON 对象
            </div>
          </div>

          {/* RIGHT: model + config */}
          <div className="flex flex-col gap-3">
            <div>
              <div className={sectionLabelCls}>③ Agent 名称</div>
              <input
                className={inputCls}
                value={form.display_name}
                onChange={(e) => patch({ display_name: e.target.value })}
                placeholder="例如：林园-Claude-0422"
              />
            </div>

            <div>
              <div className={sectionLabelCls}>④ 底层 Model · 大模型</div>
              <select
                className={inputCls}
                value={form.model_id}
                onChange={(e) => patch({ model_id: e.target.value })}
              >
                <option value="">请选择</option>
                {models
                  .filter((m) => m.enabled)
                  .map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.display_name} · {m.provider}
                    </option>
                  ))}
              </select>
            </div>

            <div>
              <div className={sectionLabelCls}>⑤ 初始资金</div>
              <div className="flex gap-1.5 mb-2">
                {CAPITAL_PRESETS.map((v) => (
                  <div
                    key={v}
                    onClick={() => patch({ initial_capital: v })}
                    style={{
                      flex: 1,
                      padding: '6px 0',
                      textAlign: 'center',
                      cursor: 'pointer',
                      background:
                        form.initial_capital === v
                          ? 'var(--bg-3)'
                          : 'var(--bg-2)',
                      border:
                        '1px solid ' +
                        (form.initial_capital === v
                          ? 'var(--brand)'
                          : 'var(--panel-border-soft)'),
                      borderRadius: 3,
                      fontSize: 11,
                      color:
                        form.initial_capital === v
                          ? 'var(--text-hi)'
                          : 'var(--text-dim)',
                      fontFamily: 'var(--f-mono)',
                    }}
                  >
                    ¥{(v / 10_000).toFixed(0)}万
                  </div>
                ))}
              </div>
              <input
                type="number"
                className={`${inputCls} mono`}
                min={10000}
                step={10000}
                value={form.initial_capital}
                onChange={(e) =>
                  patch({ initial_capital: Number(e.target.value) || 0 })
                }
              />
            </div>

            {form.persona_id && (
              <div
                className="rounded p-2.5 mt-1"
                style={{
                  background: 'var(--brand-soft)',
                  border: '1px solid var(--brand-border)',
                }}
              >
                <div
                  className="text-[10.5px] font-semibold mb-1"
                  style={{ color: 'var(--brand)' }}
                >
                  已选 Persona
                </div>
                <div className="text-[11.5px] text-text-hi">
                  {
                    personas.find((p) => p.id === form.persona_id)?.name
                  }
                </div>
                <div className="text-[10.5px] text-text-faint mt-1 leading-relaxed">
                  {
                    personas.find((p) => p.id === form.persona_id)?.style_desc
                  }
                </div>
              </div>
            )}
          </div>
        </div>

        {/* footer */}
        <div className="p-3 border-t border-panel-border-soft flex items-center gap-2 flex-wrap">
          {err && (
            <div
              className="text-[11px] text-down px-2.5 py-1 rounded flex-1 min-w-[200px]"
              style={{
                background: 'var(--down-bg)',
                border: '1px solid var(--down-border)',
              }}
            >
              {err}
            </div>
          )}
          {!err && <span style={{ flex: 1 }} />}
          <button
            className="btn ghost"
            onClick={onClose}
            disabled={createAgent.isPending}
            style={{ fontSize: 12 }}
          >
            取消
          </button>
          <button
            className="btn primary"
            onClick={submit}
            disabled={createAgent.isPending}
            style={{ fontSize: 12 }}
          >
            {createAgent.isPending ? '创建中…' : '创建 Agent'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Persona Row — used in the persona management section ─────────────────
function PersonaRow({
  persona,
  onEdit,
  onDelete,
}: {
  persona: Persona;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const color = personaColor(persona.id);
  return (
    <div
      className="flex items-center gap-3 p-3 rounded"
      style={{
        background: 'var(--bg-2)',
        border: '1px solid var(--panel-border-soft)',
      }}
    >
      <div
        style={{
          width: 7,
          height: 7,
          borderRadius: 2,
          background: color,
          flexShrink: 0,
        }}
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 flex-wrap">
          <div className="text-text-hi font-semibold text-[13px] truncate">
            {persona.name}
          </div>
          <div className="mono text-[10px] text-text-ghost uppercase tracking-wider">
            {persona.id}
          </div>
          {persona.is_builtin && (
            <span className="pill brand" style={{ fontSize: 10 }}>
              内置
            </span>
          )}
        </div>
        <div className="serif text-[11.5px] text-text-faint italic mt-1 line-clamp-1">
          “{persona.style_desc}”
        </div>
      </div>
      {!persona.is_builtin && (
        <div className="flex gap-2 flex-shrink-0">
          <button
            className="btn ghost"
            onClick={() => onEdit(persona.id)}
            style={{ padding: '3px 10px', fontSize: 11 }}
          >
            编辑
          </button>
          <button
            className="btn ghost"
            onClick={() => onDelete(persona.id)}
            style={{
              padding: '3px 10px',
              fontSize: 11,
              color: 'var(--down)',
              borderColor: 'var(--down-border)',
            }}
          >
            删除
          </button>
        </div>
      )}
    </div>
  );
}

type PersonaModalState =
  | null
  | { mode: 'create' }
  | { mode: 'edit'; persona: Persona };

// ─── page ──────────────────────────────────────────────────────────────────
export function Agent() {
  const agents = useAgents();
  const personas = usePersonas();
  const models = useModels();
  const deletePersona = useDeletePersona();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [promptPersonaId, setPromptPersonaId] = useState<string | null>(null);
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);
  const [deletingAgent, setDeletingAgent] = useState<Agent | null>(null);
  const [personaModal, setPersonaModal] = useState<PersonaModalState>(null);

  const agentList = agents.data ?? [];
  const personaList = personas.data ?? [];
  const modelList = models.data ?? [];

  const onEditPersona = async (id: string) => {
    try {
      const r = await fetch(`/api/personas/${encodeURIComponent(id)}`);
      if (!r.ok) {
        alert(`加载 persona 失败: ${r.status} ${r.statusText}`);
        return;
      }
      const full = (await r.json()) as Persona;
      setPersonaModal({ mode: 'edit', persona: full });
    } catch (e) {
      alert(`加载 persona 失败: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const onDeletePersonaClick = (id: string) => {
    if (!confirm(`确认删除 persona "${id}" ? 若有 agent 引用将拒绝。`)) return;
    deletePersona.mutate(id, {
      onError: (e) =>
        alert(`删除失败: ${e instanceof Error ? e.message : String(e)}`),
    });
  };

  // Auto-select first agent once the list loads
  useEffect(() => {
    if (!selectedId && agentList.length > 0) {
      setSelectedId(agentList[0].id);
    }
  }, [selectedId, agentList]);

  const onCreated = (agent: Agent) => {
    setShowCreate(false);
    setSelectedId(agent.id);
  };

  const totalInvested = agentList.reduce(
    (s, a) => s + (a.initial_capital || 0),
    0
  );
  const avgHealth = agentList.length
    ? agentList.reduce((s, a) => s + a.health_score, 0) / agentList.length
    : 0;

  return (
    <div className="p-5 flex flex-col gap-4 min-h-full">
      {/* page heading */}
      <div className="flex items-baseline gap-2 flex-wrap">
        <h1 className="text-2xl text-text-hi font-semibold">我的 AI 操盘手</h1>
        <div className="mono text-[11px] text-text-ghost uppercase tracking-wider">
          My Traders · Persona × Model
        </div>
        <span style={{ flex: 1 }} />
        <span className="pill brand">
          <span className="live-dot" /> {agentList.length} 个 Agent ·
          总投入 ¥{fmt(totalInvested, 0)} · 平均健康{' '}
          {Math.round(avgHealth)}
        </span>
        <button
          className="btn primary"
          onClick={() => setShowCreate(true)}
          style={{ fontSize: 12 }}
        >
          + 创建 AI 操盘手
        </button>
      </div>

      {/* autonomous scheduler — Phase 3 scaffold */}
      <AutonomousScheduler />

      {/* main: list + detail + compare */}
      <div
        className="grid gap-4 flex-1"
        style={{
          gridTemplateColumns: 'minmax(260px, 300px) 1fr',
          minHeight: 0,
        }}
      >
        {/* LEFT: agent list */}
        <div className="panel p-3 flex flex-col gap-2 min-h-0">
          <div className="flex items-baseline gap-2 px-1 pb-2 border-b border-panel-border-soft">
            <h3 className="text-text-hi text-sm font-semibold">Agent 列表</h3>
            <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
              Agents
            </span>
          </div>
          <div className="flex flex-col gap-2 overflow-auto">
            {agents.isLoading && (
              <div className="text-text-faint text-sm p-2">加载中…</div>
            )}
            {agents.isError && (
              <div className="text-down text-sm p-2">
                加载失败：{agents.error instanceof Error ? agents.error.message : '未知错误'}
              </div>
            )}
            {!agents.isLoading && !agents.isError && agentList.length === 0 && (
              <div className="text-text-faint text-sm p-3 leading-relaxed">
                还没有 Agent · 点击右上角「创建 AI 操盘手」开始。
              </div>
            )}
            {agentList.map((a) => (
              <AgentListItem
                key={a.id}
                agent={a}
                persona={personaList.find((p) => p.id === a.persona_id)}
                model={modelList.find((m) => m.id === a.model_id)}
                selected={a.id === selectedId}
                onClick={() => setSelectedId(a.id)}
              />
            ))}
          </div>
        </div>

        {/* RIGHT: detail + compare chart */}
        <div className="flex flex-col gap-4 min-h-0 min-w-0">
          <AgentDetail
            agentId={selectedId}
            personas={personaList}
            models={modelList}
            onShowPrompt={(pid) => setPromptPersonaId(pid)}
            onEdit={(a) => setEditingAgent(a)}
            onDelete={(a) => setDeletingAgent(a)}
          />

          <div className="panel flex flex-col" style={{ minHeight: 240 }}>
            <div className="panel-head">
              <span className="panel-title">净值对比 · Equity Curves</span>
              <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
                placeholder · Phase 3 接入 portfolio_history
              </span>
              <span style={{ flex: 1 }} />
              <span className="text-[10px] text-text-faint">90天</span>
            </div>
            <div className="flex-1 relative min-h-0">
              <AgentCompareChart agents={agentList} selected={selectedId} />
            </div>
          </div>
        </div>
      </div>

      {/* Persona management — create/edit/delete custom personas */}
      <section className="panel p-5">
        <div className="flex items-baseline gap-2 mb-3 flex-wrap">
          <h2 className="text-text-hi text-base font-semibold">
            Persona 管理
          </h2>
          <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
            Personas · 操盘风格库
          </span>
          <span style={{ flex: 1 }} />
          <button
            className="btn primary"
            onClick={() => setPersonaModal({ mode: 'create' })}
            style={{ fontSize: 12 }}
          >
            + 新建 Persona
          </button>
        </div>
        {personas.isLoading && (
          <div className="text-text-faint text-sm p-2">加载中…</div>
        )}
        {personas.isError && (
          <div className="text-down text-sm p-2">
            加载失败：
            {personas.error instanceof Error
              ? personas.error.message
              : '未知错误'}
          </div>
        )}
        {!personas.isLoading && !personas.isError && personaList.length === 0 && (
          <div className="text-text-faint text-sm p-3 leading-relaxed">
            暂无 persona — 点击「+ 新建 Persona」开始。
          </div>
        )}
        {personaList.length > 0 && (
          <div className="grid gap-2">
            {personaList.map((p) => (
              <PersonaRow
                key={p.id}
                persona={p}
                onEdit={onEditPersona}
                onDelete={onDeletePersonaClick}
              />
            ))}
          </div>
        )}
      </section>

      {showCreate && (
        <CreateAgentModal
          personas={personaList}
          models={modelList}
          onClose={() => setShowCreate(false)}
          onCreated={onCreated}
        />
      )}
      {promptPersonaId && (
        <PromptModal
          personaId={promptPersonaId}
          onClose={() => setPromptPersonaId(null)}
        />
      )}
      {editingAgent && (
        <AgentEditModal
          agent={editingAgent}
          onClose={() => setEditingAgent(null)}
        />
      )}
      {deletingAgent && (
        <AgentDeleteDialog
          agent={deletingAgent}
          onClose={() => setDeletingAgent(null)}
          onDeleted={() => {
            // Clear selection if the deleted agent was currently selected
            if (selectedId === deletingAgent.id) {
              setSelectedId(null);
            }
          }}
        />
      )}
      {personaModal?.mode === 'create' && (
        <PersonaFormModal
          mode="create"
          onClose={() => setPersonaModal(null)}
        />
      )}
      {personaModal?.mode === 'edit' && (
        <PersonaFormModal
          mode="edit"
          persona={personaModal.persona}
          onClose={() => setPersonaModal(null)}
        />
      )}
    </div>
  );
}
