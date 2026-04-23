import { useEffect, useRef, useState } from 'react';
import { Icon } from '../components/Icon';

// ─── types ─────────────────────────────────────────────────────────────────
type IterStatus = 'good' | 'warn' | 'bad';

type Iteration = {
  n: number;
  label: string;
  sharpe: number;
  mdd: number; // negative pct
  win: number; // 0-100
  ret: number; // pct
  trades: number;
  issue: string;
  status: IterStatus;
};

type Tab = 'iter' | 'code' | 'report';

type AgentStep = {
  t: string;
  kind: 'start' | 'think' | 'code' | 'test' | 'fail' | 'tune' | 'done' | 'report';
  msg: string;
};

// ─── shared helpers ────────────────────────────────────────────────────────
function pct(v: number, digits = 1) {
  const sign = v > 0 ? '+' : '';
  return `${sign}${v.toFixed(digits)}%`;
}

// deterministic seedable PRNG for fake equity curves
function seedRand(seed: number) {
  let s = seed || 1;
  return function () {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

// ─── sample data (Phase 3 will pull from /api/strategy-iterations) ─────────
// NOTE: in v1 these were baked into the editor. Real data source in Phase 3
// will be the code-gen endpoint that returns the agent's iteration history.
const SAMPLE_ITERATIONS: Iteration[] = [
  { n: 1, label: '初版 · 朴素 MA 金叉', sharpe: 0.82, mdd: -14.2, win: 51, ret: 8.4, trades: 48, issue: '假突破严重，换手过高', status: 'bad' },
  { n: 2, label: '+ 成交量过滤 ≥ 1.5x', sharpe: 1.08, mdd: -11.6, win: 56, ret: 12.1, trades: 32, issue: '熊市仍有较大回撤', status: 'bad' },
  { n: 3, label: '+ ATR(14) 动态止损', sharpe: 1.24, mdd: -9.8, win: 59, ret: 14.8, trades: 34, issue: '止损过紧导致部分被震出', status: 'warn' },
  { n: 4, label: '调整 ATR 倍数 2.0→2.2', sharpe: 1.31, mdd: -9.2, win: 61, ret: 15.6, trades: 30, issue: '涨跌停日误入场', status: 'warn' },
  { n: 5, label: '+ 涨跌停 / 停牌过滤', sharpe: 1.42, mdd: -8.4, win: 64, ret: 16.8, trades: 28, issue: '横盘震荡期交易过多', status: 'warn' },
  { n: 6, label: '+ MA60 趋势过滤 · 仓位风控', sharpe: 1.58, mdd: -7.6, win: 68, ret: 18.4, trades: 22, issue: '—', status: 'good' },
];

const BRIEF = `为我生成一个"MA 均线突破 + 放量过滤"的选股策略，适用于 A 股日线。
目标：夏普 > 1.5，回撤 < 8%，胜率 > 60%。股票池：沪深300。`;

// Placeholder VNPy CtaTemplate strategy — real code will be generated in Phase 3.
const FINAL_CODE = `# ============================================================
# 策略：MA 均线突破 V6 (最终稳定版)
# 生成：AI Agent · Claude Opus 4.5 · 经 6 轮自动迭代收敛
# 回测：夏普 1.58  回撤 -7.6%  胜率 68%  年化 18.4%
# ============================================================
from vnpy_ctastrategy import CtaTemplate
from vnpy.trader.object import BarData, TickData
from vnpy.trader.utility import ArrayManager

class MABreakoutV6(CtaTemplate):
    """
    AI 生成策略 · 经 6 轮迭代
    新增：MA60 趋势过滤 + 动态仓位风控
    """
    author = "BiYingTong AI Agent"

    # 参数
    fast_window = 5
    slow_window = 20
    trend_window = 60
    vol_ratio = 1.8
    stop_atr = 2.2
    max_pos = 0.15

    parameters = ["fast_window", "slow_window", "trend_window", "vol_ratio", "stop_atr", "max_pos"]
    variables = ["ma_fast", "ma_slow", "ma_trend", "atr_value"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.am = ArrayManager(100)
        self.ma_fast = 0.0
        self.ma_slow = 0.0
        self.ma_trend = 0.0  # v6 新增：长期趋势过滤
        self.atr_value = 0.0

    def on_bar(self, bar: BarData):
        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        self.ma_fast = am.sma(self.fast_window)
        self.ma_slow = am.sma(self.slow_window)
        self.ma_trend = am.sma(self.trend_window)  # v6
        self.atr_value = am.atr(14)

        # v5：涨跌停 / 停牌过滤
        if self.is_limit_or_halt(bar):
            return

        # v6：仅在上升趋势中做多
        if bar.close_price < self.ma_trend:
            if self.pos > 0:
                self.sell(bar.close_price, abs(self.pos))
            return

        # 入场：金叉 + 放量
        vol_ma = am.sma(5, array=False)
        if self.cross_up(self.ma_fast, self.ma_slow) and bar.volume > vol_ma * self.vol_ratio:
            size = self.size_by_risk(bar.close_price, self.atr_value * self.stop_atr)
            self.buy(bar.close_price, size)

        # 出场：反转 或 ATR 止损
        elif self.pos > 0 and (
            self.cross_down(self.ma_fast, self.ma_slow)
            or self.drawdown > self.stop_atr * self.atr_value
        ):
            self.sell(bar.close_price, abs(self.pos))

    def on_tick(self, tick: TickData):
        pass
`.split('\n');

const SAMPLE_STEPS: AgentStep[] = [
  { t: '14:31:02', kind: 'start', msg: '接收任务 · 解析需求' },
  { t: '14:31:04', kind: 'think', msg: '查询 vnpy + TDX 接口可用数据范围' },
  { t: '14:31:08', kind: 'code', msg: '编写 v1 · 朴素 MA 金叉' },
  { t: '14:31:22', kind: 'test', msg: '运行 v1 回测 · 3 年沪深300' },
  { t: '14:32:01', kind: 'fail', msg: 'v1 夏普 0.82 未达标 · 分析失败原因' },
  { t: '14:32:10', kind: 'code', msg: '编写 v2 · 加入成交量过滤' },
  { t: '14:32:28', kind: 'test', msg: '运行 v2 回测' },
  { t: '14:32:58', kind: 'fail', msg: 'v2 回撤 -11.6% 仍偏大' },
  { t: '14:33:05', kind: 'code', msg: '编写 v3 · ATR 动态止损' },
  { t: '14:33:22', kind: 'test', msg: '运行 v3 回测' },
  { t: '14:33:47', kind: 'tune', msg: 'v4 · 参数微调 ATR 2.0→2.2' },
  { t: '14:34:05', kind: 'code', msg: 'v5 · 加入涨跌停/停牌过滤' },
  { t: '14:34:28', kind: 'code', msg: 'v6 · 加入 MA60 趋势过滤' },
  { t: '14:34:52', kind: 'test', msg: '运行 v6 回测' },
  { t: '14:35:14', kind: 'done', msg: 'v6 所有目标达标 · 迭代收敛' },
  { t: '14:35:14', kind: 'report', msg: '生成自动化研发报告' },
];

const TOKEN_METRICS: Array<[string, string]> = [
  ['模型', 'Claude Opus 4.5'],
  ['输入 Token', '184K'],
  ['输出 Token', '42K'],
  ['代码版本数', '6'],
  ['回测调用数', '6'],
  ['累计成本', '¥0.84'],
  ['耗时', '4m 12s'],
];

// ─── page ──────────────────────────────────────────────────────────────────
export function Editor() {
  const [tab, setTab] = useState<Tab>('iter');
  const [curIter, setCurIter] = useState(6);
  const iterations = SAMPLE_ITERATIONS;
  const cur = iterations[curIter - 1];

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
              <span className="pill brand">Agent: Claude Opus 4.5</span>
              <span className="flex-1" />
              <span className="pill up">
                <span className="live-dot" /> 迭代已收敛
              </span>
              <button className="btn ghost" style={{ padding: '3px 8px' }}>
                重新运行
              </button>
            </div>
            <div
              className="serif italic"
              style={{
                fontSize: 13,
                color: 'var(--text)',
                lineHeight: 1.7,
                paddingLeft: 8,
                borderLeft: '2px solid var(--brand)',
              }}
            >
              "{BRIEF}"
            </div>
          </div>

          {/* Tabs */}
          <div className="panel flex-1 min-h-0 flex flex-col">
            <div className="panel-head">
              <span className="flex gap-0.5">
                {(
                  [
                    ['iter', '🔁 迭代过程', '6'],
                    ['code', '📄 最终稳定代码', 'v6'],
                    ['report', '📊 自动化报告', null],
                  ] as Array<[Tab, string, string | null]>
                ).map(([k, l, badge]) => (
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
                    {badge && (
                      <span
                        className="pill mono"
                        style={{ fontSize: 9, padding: '1px 5px' }}
                      >
                        {badge}
                      </span>
                    )}
                  </span>
                ))}
              </span>
              <span className="flex-1" />
              <span
                className="mono"
                style={{ fontSize: 10.5, color: 'var(--text-faint)' }}
              >
                总耗时 4m 12s · $0.84
              </span>
            </div>

            {tab === 'iter' && (
              <IterationView
                iterations={iterations}
                curIter={curIter}
                setCurIter={setCurIter}
                cur={cur}
              />
            )}
            {tab === 'code' && <CodeView code={FINAL_CODE} />}
            {tab === 'report' && <ReportView iterations={iterations} />}
          </div>
        </div>

        {/* RIGHT: agent timeline */}
        <AgentTimeline />
      </div>
    </div>
  );
}

// ─── Iteration timeline view ────────────────────────────────────────────────
function IterationView({
  iterations,
  curIter,
  setCurIter,
  cur,
}: {
  iterations: Iteration[];
  curIter: number;
  setCurIter: (n: number) => void;
  cur: Iteration;
}) {
  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
      {/* horizontal iteration rail */}
      <div
        style={{
          padding: '14px 16px',
          borderBottom: '1px solid var(--panel-border-soft)',
        }}
      >
        <div
          className="uppercase"
          style={{
            fontSize: 10.5,
            color: 'var(--text-faint)',
            letterSpacing: '0.1em',
            marginBottom: 10,
          }}
        >
          迭代轨迹 · {iterations.length} 轮 · 夏普 0.82 →{' '}
          <span className="up" style={{ fontWeight: 600 }}>
            1.58
          </span>
        </div>
        <div className="flex items-center relative">
          <div
            style={{
              position: 'absolute',
              left: 14,
              right: 14,
              top: 11,
              height: 2,
              background: 'var(--panel-border)',
            }}
          />
          <div
            style={{
              position: 'absolute',
              left: 14,
              top: 11,
              height: 2,
              width: `calc(${
                ((curIter - 1) / (iterations.length - 1)) * 100
              }% - 28px * ${(curIter - 1) / (iterations.length - 1)})`,
              background: 'var(--brand)',
            }}
          />
          {iterations.map((it) => {
            const isCur = it.n === curIter;
            const color =
              it.status === 'good'
                ? 'var(--up)'
                : it.status === 'warn'
                  ? 'var(--warn)'
                  : 'var(--down)';
            return (
              <div
                key={it.n}
                onClick={() => setCurIter(it.n)}
                className="flex-1 flex flex-col items-center cursor-pointer relative"
                style={{ zIndex: 1 }}
              >
                <div
                  className="mono flex items-center justify-center"
                  style={{
                    width: 24,
                    height: 24,
                    borderRadius: '50%',
                    background: isCur ? color : 'var(--bg-1)',
                    border: '2px solid ' + color,
                    fontSize: 11,
                    fontWeight: 600,
                    color: isCur ? 'oklch(0.15 0.02 40)' : color,
                  }}
                >
                  {it.n}
                </div>
                <div
                  style={{
                    marginTop: 6,
                    fontSize: 10,
                    color: isCur ? 'var(--text-hi)' : 'var(--text-faint)',
                    fontWeight: isCur ? 600 : 400,
                  }}
                >
                  v{it.n}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* iteration detail */}
      <div className="flex-1 overflow-auto" style={{ padding: 16 }}>
        <div className="flex items-baseline gap-2.5 mb-2.5">
          <span
            className="pill"
            style={{ fontSize: 10, background: 'var(--bg-3)' }}
          >
            v{cur.n}
          </span>
          <span
            style={{ color: 'var(--text-hi)', fontWeight: 600, fontSize: 15 }}
          >
            {cur.label}
          </span>
          <span className="flex-1" />
          <span
            className={`pill ${
              cur.status === 'good' ? 'up' : cur.status === 'warn' ? '' : 'down'
            }`}
            style={{ fontSize: 10 }}
          >
            {cur.status === 'good'
              ? '✓ 达标'
              : cur.status === 'warn'
                ? '接近达标'
                : '未达标'}
          </span>
        </div>

        {/* metrics grid */}
        <div
          className="grid gap-2 mb-3.5"
          style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}
        >
          <MetricCell
            label="年化收益"
            v={pct(cur.ret, 1)}
            color={cur.ret > 0 ? 'var(--up)' : 'var(--down)'}
          />
          <MetricCell
            label="夏普比率"
            v={cur.sharpe.toFixed(2)}
            color={cur.sharpe >= 1.5 ? 'var(--up)' : 'var(--text-hi)'}
            target=">1.5"
          />
          <MetricCell
            label="最大回撤"
            v={pct(cur.mdd, 1)}
            color="var(--down)"
            target="<8%"
          />
          <MetricCell
            label="胜率"
            v={`${cur.win}%`}
            color={cur.win >= 60 ? 'var(--up)' : 'var(--text-hi)'}
            target=">60%"
          />
          <MetricCell
            label="交易次数"
            v={String(cur.trades)}
            color="var(--text-hi)"
          />
        </div>

        {/* equity chart */}
        <div
          style={{
            height: 160,
            background: 'oklch(0.13 0.009 260)',
            border: '1px solid var(--panel-border-soft)',
            borderRadius: 4,
            position: 'relative',
            marginBottom: 12,
          }}
        >
          <IterEquity seed={cur.n} ret={cur.ret} mdd={cur.mdd} />
        </div>

        {/* agent commentary */}
        <div
          style={{
            padding: 12,
            background: 'var(--brand-soft)',
            border: '1px solid var(--brand-border)',
            borderRadius: 4,
          }}
        >
          <div className="flex items-center gap-1.5 mb-1.5">
            <Icon name="filter" size={11} className="text-brand" />
            <span
              className="uppercase"
              style={{
                fontSize: 10.5,
                color: 'var(--brand)',
                fontWeight: 600,
                letterSpacing: '0.08em',
              }}
            >
              Agent 评注 & 下一步
            </span>
          </div>
          <div
            className="serif"
            style={{ fontSize: 12.5, color: 'var(--text)', lineHeight: 1.65 }}
          >
            {cur.status === 'good'
              ? `"v${cur.n} 已满足所有目标指标。夏普 ${cur.sharpe} 超越目标 1.5，回撤控制在 ${Math.abs(
                  cur.mdd
                )}% 以内。策略已收敛，可以作为最终稳定版本部署。"`
              : `"v${cur.n} 当前的主要问题：${cur.issue}。准备在下一轮 v${
                  cur.n + 1
                } 中加入修正..."`}
          </div>
          {cur.status !== 'good' && (
            <div
              className="mono"
              style={{
                marginTop: 8,
                padding: 8,
                background: 'var(--bg-1)',
                borderRadius: 3,
                fontSize: 10.5,
                color: 'var(--text-dim)',
              }}
            >
              <span style={{ color: 'var(--up)' }}>+</span> self.ma_trend =
              ind.MA(self.close, 60)
              <br />
              <span style={{ color: 'var(--up)' }}>+</span> if self.close {'<'}{' '}
              self.ma_trend: return
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MetricCell({
  label,
  v,
  color,
  target,
}: {
  label: string;
  v: string;
  color: string;
  target?: string;
}) {
  return (
    <div
      style={{
        padding: '8px 10px',
        background: 'var(--bg-2)',
        border: '1px solid var(--panel-border-soft)',
        borderRadius: 3,
      }}
    >
      <div
        className="uppercase"
        style={{
          fontSize: 9.5,
          color: 'var(--text-faint)',
          letterSpacing: '0.08em',
        }}
      >
        {label}
      </div>
      <div
        className="num mono"
        style={{ fontSize: 17, color, fontWeight: 600, marginTop: 2 }}
      >
        {v}
      </div>
      {target && (
        <div className="mono" style={{ fontSize: 9, color: 'var(--text-ghost)' }}>
          目标 {target}
        </div>
      )}
    </div>
  );
}

function IterEquity({
  seed,
  ret,
  mdd,
}: {
  seed: number;
  ret: number;
  mdd: number;
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
    if (!size.w) return;
    const cvs = ref.current;
    if (!cvs) return;
    const dpr = window.devicePixelRatio || 1;
    cvs.width = size.w * dpr;
    cvs.height = size.h * dpr;
    cvs.style.width = `${size.w}px`;
    cvs.style.height = `${size.h}px`;
    const ctx = cvs.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    const N = 120;
    const r = seedRand(seed * 17);
    const arr: number[] = [];
    let v = 100;
    for (let i = 0; i < N; i++) {
      v += ret / N + (r() - 0.5) * (Math.abs(mdd) / 8);
      arr.push(v);
    }
    const mn = Math.min(...arr);
    const mx = Math.max(...arr);
    const pad = 10;
    const y = (vv: number) =>
      pad + ((mx - vv) / (mx - mn || 1)) * (size.h - 2 * pad);
    const x = (i: number) => pad + (i / (N - 1)) * (size.w - 2 * pad);

    ctx.strokeStyle = 'oklch(0.22 0.010 260 / 0.3)';
    ctx.setLineDash([2, 3]);
    ctx.beginPath();
    ctx.moveTo(pad, y(100));
    ctx.lineTo(size.w - pad, y(100));
    ctx.stroke();
    ctx.setLineDash([]);

    const clr = ret >= 15 ? 'oklch(0.70 0.24 25)' : 'oklch(0.82 0.18 75)';
    ctx.strokeStyle = clr;
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    arr.forEach((vv, i) => {
      if (i === 0) ctx.moveTo(x(i), y(vv));
      else ctx.lineTo(x(i), y(vv));
    });
    ctx.stroke();
  }, [size, seed, ret, mdd]);

  return (
    <canvas
      ref={ref}
      style={{ display: 'block', width: '100%', height: '100%' }}
    />
  );
}

// ─── Code view ──────────────────────────────────────────────────────────────
function CodeView({ code }: { code: string[] }) {
  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div
        className="flex items-center gap-2.5"
        style={{
          padding: '10px 16px',
          background: 'var(--up-bg)',
          borderBottom: '1px solid var(--up-border)',
        }}
      >
        <Icon name="backtest" size={12} className="text-up" />
        <span
          style={{ fontSize: 12, color: 'var(--text-hi)', fontWeight: 600 }}
        >
          v6 · 最终稳定版 · 已通过所有目标指标
        </span>
        <span className="flex-1" />
        <span
          className="mono"
          style={{ fontSize: 10.5, color: 'var(--text-faint)' }}
        >
          SHA256: a3f07...c4e2
        </span>
        <button className="btn ghost" style={{ padding: '3px 8px' }}>
          复制
        </button>
        <button className="btn primary" style={{ padding: '3px 10px' }}>
          <Icon name="agent" size={11} /> 分派给 Agent
        </button>
      </div>
      <div
        className="flex-1 flex overflow-auto"
        style={{ background: 'oklch(0.13 0.009 260)' }}
      >
        <div
          style={{
            padding: '10px 10px 10px 14px',
            color: 'var(--text-ghost)',
            fontFamily: 'var(--f-mono)',
            fontSize: 11.5,
            lineHeight: 1.62,
            textAlign: 'right',
            userSelect: 'none',
            borderRight: '1px solid var(--panel-border-soft)',
          }}
        >
          {code.map((_, i) => (
            <div key={i}>{i + 1}</div>
          ))}
        </div>
        <pre
          style={{
            margin: 0,
            padding: '10px 14px',
            fontFamily: 'var(--f-mono)',
            fontSize: 11.5,
            lineHeight: 1.62,
            color: 'var(--text)',
            flex: 1,
          }}
        >
          {code.map((ln, i) => (
            <CodeLine key={i} line={ln} />
          ))}
        </pre>
      </div>
    </div>
  );
}

function CodeLine({ line }: { line: string }) {
  const kw =
    /\b(from|import|class|def|self|return|if|elif|else|and|or|not|None|True|False|in|is|for|while|dict|lambda|super)\b/g;
  const str = /("[^"]*"|'[^']*')/g;
  const num = /\b(\d+\.?\d*)\b/g;
  const cmt = /(#.*)$/g;
  const bi =
    /\b(MA|ATR|CtaTemplate|ArrayManager|BarData|TickData|sma|atr|cross_up|cross_down|buy|sell|size_by_risk|is_limit_or_halt|drawdown|pos|volume|close_price|update_bar|on_bar|on_tick)\b/g;

  let html = line
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  html = html.replace(cmt, '<span style="color:var(--text-ghost)">$1</span>');
  html = html.replace(str, '<span style="color:oklch(0.82 0.16 140)">$1</span>');
  html = html.replace(kw, '<span style="color:oklch(0.74 0.18 305)">$1</span>');
  html = html.replace(bi, '<span style="color:var(--info)">$1</span>');
  html = html.replace(num, '<span style="color:var(--brand)">$1</span>');
  return <div dangerouslySetInnerHTML={{ __html: html || '&nbsp;' }} />;
}

// ─── Report view ────────────────────────────────────────────────────────────
function ReportView({ iterations }: { iterations: Iteration[] }) {
  return (
    <div className="flex-1 overflow-auto" style={{ padding: 20 }}>
      <div
        className="serif"
        style={{
          fontSize: 22,
          color: 'var(--text-hi)',
          fontWeight: 600,
          marginBottom: 4,
        }}
      >
        MA 均线突破策略 · 自动化研发报告
      </div>
      <div
        style={{ fontSize: 11, color: 'var(--text-faint)', marginBottom: 20 }}
      >
        AI Agent · Claude Opus 4.5 · 生成时间 2026-04-20 14:35 · 总耗时 4m 12s · 6
        轮迭代
      </div>

      <ReportSection title="概要">
        <p
          style={{ fontSize: 12.5, color: 'var(--text)', lineHeight: 1.8 }}
        >
          接到"MA 均线突破 + 放量过滤"任务后，Agent 从朴素金叉方案起步，通过{' '}
          <span className="up">6 轮</span>自动迭代，最终收敛到 v6 稳定版。夏普从{' '}
          <span className="mono">0.82</span> 提升至{' '}
          <span className="mono up">1.58</span>，回撤从{' '}
          <span className="mono down">-14.2%</span> 降至{' '}
          <span className="mono down">-7.6%</span>，胜率由{' '}
          <span className="mono">51%</span> 提升至{' '}
          <span className="mono up">68%</span>。所有目标指标已达标，策略可进入实盘阶段。
        </p>
      </ReportSection>

      <ReportSection title="迭代演进明细">
        <table className="tbl">
          <thead>
            <tr>
              <th>版本</th>
              <th>关键改动</th>
              <th className="num">年化</th>
              <th className="num">夏普</th>
              <th className="num">回撤</th>
              <th className="num">胜率</th>
              <th>Agent 评注</th>
            </tr>
          </thead>
          <tbody>
            {iterations.map((it) => {
              const color =
                it.status === 'good'
                  ? 'var(--up)'
                  : it.status === 'warn'
                    ? 'var(--warn)'
                    : 'var(--down)';
              return (
                <tr key={it.n}>
                  <td>
                    <span
                      className="mono pill"
                      style={{ fontSize: 10, color }}
                    >
                      v{it.n}
                    </span>
                  </td>
                  <td style={{ color: 'var(--text-hi)' }}>{it.label}</td>
                  <td className={`num ${it.ret > 0 ? 'up' : 'down'}`}>
                    {pct(it.ret, 1)}
                  </td>
                  <td
                    className="num"
                    style={{
                      color:
                        it.sharpe >= 1.5 ? 'var(--up)' : 'var(--text-hi)',
                    }}
                  >
                    {it.sharpe.toFixed(2)}
                  </td>
                  <td className="num down">{pct(it.mdd, 1)}</td>
                  <td
                    className="num"
                    style={{
                      color: it.win >= 60 ? 'var(--up)' : 'var(--text-hi)',
                    }}
                  >
                    {it.win}%
                  </td>
                  <td style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                    {it.issue}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </ReportSection>

      <ReportSection title="关键洞察">
        <ul
          style={{
            fontSize: 12,
            color: 'var(--text)',
            lineHeight: 1.9,
            paddingLeft: 18,
          }}
        >
          <li>
            <span style={{ color: 'var(--brand)' }}>放量过滤 (v2)</span>{' '}
            是信噪比提升的关键 — 夏普 +0.26
          </li>
          <li>
            <span style={{ color: 'var(--brand)' }}>ATR 动态止损 (v3-v4)</span>{' '}
            大幅降低回撤 — 回撤 -2.4%
          </li>
          <li>
            <span style={{ color: 'var(--brand)' }}>MA60 趋势过滤 (v6)</span>{' '}
            避免熊市逆势 — 胜率 +4%
          </li>
          <li>剔除涨跌停日进场可有效避免尾部风险</li>
        </ul>
      </ReportSection>

      <ReportSection title="结论 & 建议">
        <p
          style={{ fontSize: 12.5, color: 'var(--text)', lineHeight: 1.8 }}
        >
          v6 稳定版已满足所有目标指标，建议：
          <br />① 以 <span className="mono up">15%</span>{' '}
          单股仓位上限部署，分散到 20-30 只股票；
          <br />② 前 3 个月以 <span className="mono">¥100k</span>{' '}
          小资金试跑，观察实盘与回测偏差；
          <br />③ 每季度由 Agent 重新评估，若夏普退化超过 20% 触发新一轮迭代。
        </p>
      </ReportSection>

      <div className="flex gap-2 mt-5">
        <button className="btn ghost">导出 PDF 报告</button>
        <button className="btn ghost">归档到策略库</button>
        <span className="flex-1" />
        <button className="btn primary">
          <Icon name="agent" size={12} /> 分派给 AI Agent 运行
        </button>
      </div>
    </div>
  );
}

function ReportSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 22 }}>
      <div
        className="flex items-center gap-2"
        style={{
          marginBottom: 10,
          paddingBottom: 6,
          borderBottom: '1px solid var(--panel-border-soft)',
        }}
      >
        <div style={{ width: 3, height: 14, background: 'var(--brand)' }} />
        <div
          style={{
            fontSize: 13,
            color: 'var(--text-hi)',
            fontWeight: 600,
            letterSpacing: '0.02em',
          }}
        >
          {title}
        </div>
      </div>
      {children}
    </div>
  );
}

// ─── Right-side Agent activity timeline ────────────────────────────────────
function AgentTimeline() {
  // NOTE: Phase 3 can wire this to api.audit({agent_id, kind:'validation'})
  // to render real validation decisions (agent thinks → validates → trades).
  // For now we render the static sample that matches the v1 prototype.
  const steps = SAMPLE_STEPS;

  const colorMap: Record<AgentStep['kind'], string> = {
    start: 'var(--info)',
    think: 'var(--text-faint)',
    code: 'var(--brand)',
    test: 'var(--info)',
    fail: 'var(--down)',
    tune: 'var(--warn)',
    done: 'var(--up)',
    report: 'var(--up)',
  };
  const iconMap: Record<AgentStep['kind'], string> = {
    start: '▶',
    think: '◇',
    code: '❯',
    test: '▢',
    fail: '✕',
    tune: '◈',
    done: '✓',
    report: '📄',
  };

  return (
    <div className="panel flex flex-col min-h-0">
      <div className="panel-head">
        <Icon name="filter" size={11} className="text-brand" />
        <span className="panel-title">Agent 工作流 · 实时</span>
        <span className="flex-1" />
        <span className="pill up">
          <span className="live-dot" /> 已完成
        </span>
      </div>

      {/* token / cost meta */}
      <div
        style={{
          padding: '10px 14px',
          background: 'var(--bg-2)',
          borderBottom: '1px solid var(--panel-border-soft)',
        }}
      >
        <div
          className="grid gap-x-3"
          style={{ gridTemplateColumns: '1fr 1fr', rowGap: 3 }}
        >
          {TOKEN_METRICS.map(([k, v]) => (
            <div key={k} className="flex justify-between" style={{ fontSize: 10.5 }}>
              <span style={{ color: 'var(--text-faint)' }}>{k}</span>
              <span
                className="mono"
                style={{ color: 'var(--text-hi)', fontWeight: 500 }}
              >
                {v}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* timeline */}
      <div className="flex-1 overflow-auto" style={{ padding: '10px 0' }}>
        {steps.map((s, i) => {
          const clr = colorMap[s.kind];
          return (
            <div
              key={i}
              className="flex gap-2.5 items-start"
              style={{ padding: '5px 14px' }}
            >
              <div className="flex flex-col items-center" style={{ paddingTop: 2 }}>
                <div
                  className="mono flex items-center justify-center"
                  style={{
                    width: 16,
                    height: 16,
                    borderRadius: '50%',
                    background: clr + '20',
                    border: '1px solid ' + clr,
                    color: clr,
                    fontSize: 9,
                  }}
                >
                  {iconMap[s.kind]}
                </div>
                {i < steps.length - 1 && (
                  <div
                    style={{
                      width: 1,
                      flex: 1,
                      background: 'var(--panel-border-soft)',
                      minHeight: 12,
                      marginTop: 2,
                    }}
                  />
                )}
              </div>
              <div className="flex-1" style={{ paddingBottom: 6 }}>
                <div
                  style={{ fontSize: 11.5, color: 'var(--text)', lineHeight: 1.4 }}
                >
                  {s.msg}
                </div>
                <div
                  className="mono"
                  style={{
                    fontSize: 9.5,
                    color: 'var(--text-ghost)',
                    marginTop: 1,
                  }}
                >
                  {s.t}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div
        className="flex gap-1.5"
        style={{ padding: 10, borderTop: '1px solid var(--panel-border-soft)' }}
      >
        <button className="btn ghost flex-1">新任务</button>
        <button className="btn primary flex-1">
          <Icon name="agent" size={11} /> 分派给 Agent
        </button>
      </div>
    </div>
  );
}
