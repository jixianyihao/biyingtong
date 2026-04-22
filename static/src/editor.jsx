// Strategy Editor — AI Agent 自动化策略编写 + 自动回测 + 迭代报告
function StrategyEditor() {
  const [tab, setTab] = useState('iter'); // iter | code | report
  const [curIter, setCurIter] = useState(6); // 展示第几次迭代

  const brief = `为我生成一个"MA 均线突破 + 放量过滤"的选股策略，适用于 A 股日线。
目标：夏普 > 1.5，回撤 < 8%，胜率 > 60%。股票池：沪深300。`;

  const iterations = [
    { n: 1, label: '初版 · 朴素 MA 金叉',           sharpe: 0.82, mdd: -14.2, win: 51, ret: 8.4,  trades: 48, issue: '假突破严重，换手过高',   status: 'bad' },
    { n: 2, label: '+ 成交量过滤 ≥ 1.5x',           sharpe: 1.08, mdd: -11.6, win: 56, ret: 12.1, trades: 32, issue: '熊市仍有较大回撤',       status: 'bad' },
    { n: 3, label: '+ ATR(14) 动态止损',            sharpe: 1.24, mdd: -9.8,  win: 59, ret: 14.8, trades: 34, issue: '止损过紧导致部分被震出', status: 'warn' },
    { n: 4, label: '调整 ATR 倍数 2.0→2.2',          sharpe: 1.31, mdd: -9.2,  win: 61, ret: 15.6, trades: 30, issue: '涨跌停日误入场',         status: 'warn' },
    { n: 5, label: '+ 涨跌停 / 停牌过滤',            sharpe: 1.42, mdd: -8.4,  win: 64, ret: 16.8, trades: 28, issue: '横盘震荡期交易过多',      status: 'warn' },
    { n: 6, label: '+ MA60 趋势过滤 · 仓位风控',      sharpe: 1.58, mdd: -7.6,  win: 68, ret: 18.4, trades: 22, issue: '—',                     status: 'good' },
  ];
  const cur = iterations[curIter - 1];

  const finalCode = `# ============================================================
# 策略：MA 均线突破 V6 (最终稳定版)
# 生成：AI Agent · Claude Opus 4.5 · 经 6 轮自动迭代收敛
# 回测：夏普 1.58  回撤 -7.6%  胜率 68%  年化 18.4%
# ============================================================
from quantlib import Strategy, indicators as ind
from quantlib.tdx import get_security_bars  # pytdx 接口

class MABreakoutV6(Strategy):
    """
    AI 生成策略 · 经 6 轮迭代
    新增：MA60 趋势过滤 + 动态仓位风控
    """
    params = dict(
        fast = 5, slow = 20, trend = 60,
        vol_ratio = 1.8,
        stop_atr  = 2.2,
        max_pos   = 0.15,
    )

    def init(self):
        self.ma_f = ind.MA(self.close, self.p.fast)
        self.ma_s = ind.MA(self.close, self.p.slow)
        self.ma_t = ind.MA(self.close, self.p.trend)  # ← v6 新增
        self.atr  = ind.ATR(14)
        self.volm = ind.MA(self.volume, 5)

    def next(self):
        if self.is_limit_up() or self.is_suspended():
            return                             # ← v5 新增

        # v6：只在上升趋势中做多
        if self.close < self.ma_t:
            return

        # 入场：金叉 + 放量
        if cross_up(self.ma_f, self.ma_s) \\
           and self.volume > self.volm * self.p.vol_ratio:
            size = self.size_by_risk(
                stop = self.atr * self.p.stop_atr)   # v3/v4 ATR 止损
            self.buy(size=size, reason="MA金叉放量")

        elif self.position and (
            cross_down(self.ma_f, self.ma_s) or
            self.drawdown > self.p.stop_atr * self.atr
        ):
            self.close(reason="信号反转/止损")`.split('\n');

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 420px',
      gap: 12, padding: 12, height: '100%', overflow: 'hidden' }}>

      {/* LEFT: main working area */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
        {/* Brief */}
        <div className="panel" style={{ padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <Icon name="sparkle" size={13} style={{ color: 'var(--brand)' }}/>
            <span style={{ fontSize: 11, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>策略需求 · Brief</span>
            <span className="pill brand"><Icon name="agent" size={9}/> Agent: Claude Opus 4.5</span>
            <span style={{ flex: 1 }}/>
            <span className="pill up"><span className="live-dot"/> 迭代已收敛</span>
            <button className="btn ghost" style={{ padding: '3px 8px' }}><Icon name="refresh" size={11}/> 重新运行</button>
          </div>
          <div className="serif" style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.7, fontStyle: 'italic', paddingLeft: 8, borderLeft: '2px solid var(--brand)' }}>
            "{brief}"
          </div>
        </div>

        {/* Tabs */}
        <div className="panel" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <div className="panel-head">
            <span style={{ display: 'flex', gap: 2 }}>
              {[['iter', '🔁 迭代过程', 6], ['code', '📄 最终稳定代码', 'v6'], ['report', '📊 自动化报告', null]].map(([k, l, badge]) => (
                <span key={k} onClick={() => setTab(k)} style={{
                  padding: '6px 14px', fontSize: 12, cursor: 'pointer',
                  color: tab === k ? 'var(--text-hi)' : 'var(--text-faint)',
                  borderBottom: '2px solid ' + (tab === k ? 'var(--brand)' : 'transparent'),
                  marginBottom: -9, fontWeight: tab === k ? 600 : 400,
                  display: 'flex', alignItems: 'center', gap: 6,
                }}>
                  {l}
                  {badge && <span className="pill mono" style={{ fontSize: 9, padding: '1px 5px' }}>{badge}</span>}
                </span>
              ))}
            </span>
            <span style={{ flex: 1 }}/>
            <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-faint)' }}>总耗时 4m 12s · $0.84</span>
          </div>

          {tab === 'iter' && <IterationView iterations={iterations} curIter={curIter} setCurIter={setCurIter} cur={cur}/>}
          {tab === 'code' && <CodeView code={finalCode}/>}
          {tab === 'report' && <ReportView iterations={iterations} final={cur}/>}
        </div>
      </div>

      {/* RIGHT: agent timeline */}
      <AgentTimeline/>
    </div>
  );
}

// ─── Iteration timeline view ─────────────────────────────
function IterationView({ iterations, curIter, setCurIter, cur }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' }}>
      {/* horizontal iteration rail */}
      <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--panel-border-soft)' }}>
        <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 10 }}>
          迭代轨迹 · {iterations.length} 轮 · 夏普 0.82 → <span className="up" style={{ fontWeight: 600 }}>1.58</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', position: 'relative' }}>
          <div style={{ position: 'absolute', left: 14, right: 14, top: 11, height: 2, background: 'var(--panel-border)' }}/>
          <div style={{ position: 'absolute', left: 14, top: 11, height: 2, width: `calc(${(curIter - 1) / (iterations.length - 1) * 100}% - 28px * ${(curIter - 1) / (iterations.length - 1)})`, background: 'var(--brand)' }}/>
          {iterations.map(it => {
            const isCur = it.n === curIter;
            const color = it.status === 'good' ? 'var(--up)' : it.status === 'warn' ? 'var(--warn)' : 'var(--down)';
            return (
              <div key={it.n} onClick={() => setCurIter(it.n)} style={{
                flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', cursor: 'pointer', position: 'relative', zIndex: 1,
              }}>
                <div style={{
                  width: 24, height: 24, borderRadius: '50%',
                  background: isCur ? color : 'var(--bg-1)',
                  border: '2px solid ' + color,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: 'var(--f-mono)', fontSize: 11, fontWeight: 600,
                  color: isCur ? 'oklch(0.15 0.02 40)' : color,
                }}>{it.n}</div>
                <div style={{ marginTop: 6, fontSize: 10, color: isCur ? 'var(--text-hi)' : 'var(--text-faint)', fontWeight: isCur ? 600 : 400 }}>v{it.n}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* iteration detail */}
      <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10 }}>
          <span className="pill" style={{ fontSize: 10, background: 'var(--bg-3)' }}>v{cur.n}</span>
          <span style={{ color: 'var(--text-hi)', fontWeight: 600, fontSize: 15 }}>{cur.label}</span>
          <span style={{ flex: 1 }}/>
          <span className={`pill ${cur.status === 'good' ? 'up' : cur.status === 'warn' ? '' : 'down'}`} style={{ fontSize: 10 }}>
            {cur.status === 'good' ? '✓ 达标' : cur.status === 'warn' ? '接近达标' : '未达标'}
          </span>
        </div>

        {/* metrics grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8, marginBottom: 14 }}>
          <MetricCell label="年化收益" v={pct(cur.ret,1)} color={cur.ret > 0 ? 'var(--up)' : 'var(--down)'}/>
          <MetricCell label="夏普比率" v={cur.sharpe.toFixed(2)} color={cur.sharpe >= 1.5 ? 'var(--up)' : 'var(--text-hi)'} target=">1.5"/>
          <MetricCell label="最大回撤" v={pct(cur.mdd,1)} color="var(--down)" target="<8%"/>
          <MetricCell label="胜率" v={cur.win + '%'} color={cur.win >= 60 ? 'var(--up)' : 'var(--text-hi)'} target=">60%"/>
          <MetricCell label="交易次数" v={cur.trades} color="var(--text-hi)"/>
        </div>

        {/* equity chart */}
        <div style={{ height: 160, background: 'oklch(0.13 0.009 260)', border: '1px solid var(--panel-border-soft)', borderRadius: 4, position: 'relative', marginBottom: 12 }}>
          <IterEquity seed={cur.n} ret={cur.ret} mdd={cur.mdd}/>
        </div>

        {/* agent commentary */}
        <div style={{ padding: 12, background: 'var(--brand-soft)', border: '1px solid var(--brand-border)', borderRadius: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <Icon name="sparkle" size={11} style={{ color: 'var(--brand)' }}/>
            <span style={{ fontSize: 10.5, color: 'var(--brand)', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase' }}>Agent 评注 & 下一步</span>
          </div>
          <div className="serif" style={{ fontSize: 12.5, color: 'var(--text)', lineHeight: 1.65 }}>
            {cur.status === 'good'
              ? `"v${cur.n} 已满足所有目标指标。夏普 ${cur.sharpe} 超越目标 1.5，回撤控制在 ${Math.abs(cur.mdd)}% 以内。策略已收敛，可以作为最终稳定版本部署。"`
              : `"v${cur.n} 当前的主要问题：${cur.issue}。准备在下一轮 v${cur.n + 1} 中加入修正..."`}
          </div>
          {cur.status !== 'good' && (
            <div className="mono" style={{ marginTop: 8, padding: 8, background: 'var(--bg-1)', borderRadius: 3, fontSize: 10.5, color: 'var(--text-dim)' }}>
              <span style={{ color: 'var(--up)' }}>+</span> self.ma_trend = ind.MA(self.close, 60)<br/>
              <span style={{ color: 'var(--up)' }}>+</span> if self.close {'<'} self.ma_trend: return
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MetricCell({ label, v, color, target }) {
  return (
    <div style={{ padding: '8px 10px', background: 'var(--bg-2)', border: '1px solid var(--panel-border-soft)', borderRadius: 3 }}>
      <div style={{ fontSize: 9.5, color: 'var(--text-faint)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>{label}</div>
      <div className="num mono" style={{ fontSize: 17, color, fontWeight: 600, marginTop: 2 }}>{v}</div>
      {target && <div className="mono" style={{ fontSize: 9, color: 'var(--text-ghost)' }}>目标 {target}</div>}
    </div>
  );
}

function IterEquity({ seed, ret, mdd }) {
  const ref = useRef(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = ref.current?.parentElement;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el); setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);
  useEffect(() => {
    if (!size.w) return;
    const cvs = ref.current; const dpr = window.devicePixelRatio || 1;
    cvs.width = size.w * dpr; cvs.height = size.h * dpr;
    cvs.style.width = size.w + 'px'; cvs.style.height = size.h + 'px';
    const ctx = cvs.getContext('2d'); ctx.scale(dpr, dpr);
    const N = 120; const r = seedRand(seed * 17);
    const arr = []; let v = 100;
    for (let i = 0; i < N; i++) { v += ret / N + (r() - 0.5) * (Math.abs(mdd) / 8); arr.push(v); }
    const mn = Math.min(...arr), mx = Math.max(...arr);
    const pad = 10;
    const y = vv => pad + ((mx - vv)/(mx - mn)) * (size.h - 2*pad);
    const x = i => pad + (i/(N-1)) * (size.w - 2*pad);
    ctx.strokeStyle = 'oklch(0.22 0.010 260 / 0.3)'; ctx.setLineDash([2,3]);
    ctx.beginPath(); ctx.moveTo(pad, y(100)); ctx.lineTo(size.w - pad, y(100)); ctx.stroke(); ctx.setLineDash([]);
    const clr = ret >= 15 ? 'oklch(0.70 0.24 25)' : 'oklch(0.82 0.18 75)';
    ctx.strokeStyle = clr; ctx.lineWidth = 1.6;
    ctx.beginPath();
    arr.forEach((vv,i)=>{ if (i===0) ctx.moveTo(x(i), y(vv)); else ctx.lineTo(x(i), y(vv)); });
    ctx.stroke();
  }, [size, seed, ret, mdd]);
  return <canvas ref={ref} style={{ display: 'block', width: '100%', height: '100%' }}/>;
}

// ─── Code view ─────────────────────────────
function CodeView({ code }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <div style={{ padding: '10px 16px', background: 'var(--up-bg)', borderBottom: '1px solid var(--up-border)', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Icon name="check" size={12} style={{ color: 'var(--up)' }}/>
        <span style={{ fontSize: 12, color: 'var(--text-hi)', fontWeight: 600 }}>v6 · 最终稳定版 · 已通过所有目标指标</span>
        <span style={{ flex: 1 }}/>
        <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-faint)' }}>SHA256: a3f07...c4e2</span>
        <button className="btn ghost" style={{ padding: '3px 8px' }}><Icon name="copy" size={11}/> 复制</button>
        <button className="btn primary" style={{ padding: '3px 10px' }}><Icon name="agent" size={11}/> 分派给 Agent</button>
      </div>
      <div style={{ flex: 1, display: 'flex', overflow: 'auto', background: 'oklch(0.13 0.009 260)' }}>
        <div style={{ padding: '10px 10px 10px 14px', color: 'var(--text-ghost)', fontFamily: 'var(--f-mono)', fontSize: 11.5, lineHeight: 1.62, textAlign: 'right', userSelect: 'none', borderRight: '1px solid var(--panel-border-soft)' }}>
          {code.map((_, i) => <div key={i}>{i + 1}</div>)}
        </div>
        <pre style={{ margin: 0, padding: '10px 14px', fontFamily: 'var(--f-mono)', fontSize: 11.5, lineHeight: 1.62, color: 'var(--text)', flex: 1 }}>
          {code.map((ln, i) => <CodeLine key={i} line={ln}/>)}
        </pre>
      </div>
    </div>
  );
}

// ─── Report view ─────────────────────────────
function ReportView({ iterations, final }) {
  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 20 }}>
      <div className="serif" style={{ fontSize: 22, color: 'var(--text-hi)', fontWeight: 600, marginBottom: 4 }}>
        MA 均线突破策略 · 自动化研发报告
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-faint)', marginBottom: 20 }}>
        AI Agent · Claude Opus 4.5 · 生成时间 2026-04-20 14:35 · 总耗时 4m 12s · 6 轮迭代
      </div>

      <ReportSection title="概要">
        <p style={{ fontSize: 12.5, color: 'var(--text)', lineHeight: 1.8 }}>
          接到"MA 均线突破 + 放量过滤"任务后，Agent 从朴素金叉方案起步，通过 <span className="up">6 轮</span>自动迭代，
          最终收敛到 v6 稳定版。夏普从 <span className="mono">0.82</span> 提升至 <span className="mono up">1.58</span>，
          回撤从 <span className="mono down">-14.2%</span> 降至 <span className="mono down">-7.6%</span>，
          胜率由 <span className="mono">51%</span> 提升至 <span className="mono up">68%</span>。
          所有目标指标已达标，策略可进入实盘阶段。
        </p>
      </ReportSection>

      <ReportSection title="迭代演进明细">
        <table className="tbl">
          <thead>
            <tr>
              <th>版本</th><th>关键改动</th>
              <th className="num">年化</th><th className="num">夏普</th><th className="num">回撤</th><th className="num">胜率</th>
              <th>Agent 评注</th>
            </tr>
          </thead>
          <tbody>
            {iterations.map(it => {
              const color = it.status === 'good' ? 'var(--up)' : it.status === 'warn' ? 'var(--warn)' : 'var(--down)';
              return (
                <tr key={it.n}>
                  <td><span className="mono pill" style={{ fontSize: 10, color }}>v{it.n}</span></td>
                  <td style={{ color: 'var(--text-hi)' }}>{it.label}</td>
                  <td className={`num ${it.ret > 0 ? 'up' : 'down'}`}>{pct(it.ret,1)}</td>
                  <td className="num" style={{ color: it.sharpe >= 1.5 ? 'var(--up)' : 'var(--text-hi)' }}>{it.sharpe.toFixed(2)}</td>
                  <td className="num down">{pct(it.mdd,1)}</td>
                  <td className="num" style={{ color: it.win >= 60 ? 'var(--up)' : 'var(--text-hi)' }}>{it.win}%</td>
                  <td style={{ fontSize: 11, color: 'var(--text-dim)' }}>{it.issue}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </ReportSection>

      <ReportSection title="关键洞察">
        <ul style={{ fontSize: 12, color: 'var(--text)', lineHeight: 1.9, paddingLeft: 18 }}>
          <li><span style={{ color: 'var(--brand)' }}>放量过滤 (v2)</span> 是信噪比提升的关键 — 夏普 +0.26</li>
          <li><span style={{ color: 'var(--brand)' }}>ATR 动态止损 (v3-v4)</span> 大幅降低回撤 — 回撤 -2.4%</li>
          <li><span style={{ color: 'var(--brand)' }}>MA60 趋势过滤 (v6)</span> 避免熊市逆势 — 胜率 +4%</li>
          <li>剔除涨跌停日进场可有效避免尾部风险</li>
        </ul>
      </ReportSection>

      <ReportSection title="结论 & 建议">
        <p style={{ fontSize: 12.5, color: 'var(--text)', lineHeight: 1.8 }}>
          v6 稳定版已满足所有目标指标，建议：
          <br/>① 以 <span className="mono up">15%</span> 单股仓位上限部署，分散到 20-30 只股票；
          <br/>② 前 3 个月以 <span className="mono">¥100k</span> 小资金试跑，观察实盘与回测偏差；
          <br/>③ 每季度由 Agent 重新评估，若夏普退化超过 20% 触发新一轮迭代。
        </p>
      </ReportSection>

      <div style={{ display: 'flex', gap: 8, marginTop: 20 }}>
        <button className="btn ghost"><Icon name="copy" size={11}/> 导出 PDF 报告</button>
        <button className="btn ghost"><Icon name="save" size={11}/> 归档到策略库</button>
        <span style={{ flex: 1 }}/>
        <button className="btn primary"><Icon name="agent" size={12}/> 分派给 AI Agent 运行</button>
      </div>
    </div>
  );
}

function ReportSection({ title, children }) {
  return (
    <div style={{ marginBottom: 22 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, paddingBottom: 6, borderBottom: '1px solid var(--panel-border-soft)' }}>
        <div style={{ width: 3, height: 14, background: 'var(--brand)' }}/>
        <div style={{ fontSize: 13, color: 'var(--text-hi)', fontWeight: 600, letterSpacing: '0.02em' }}>{title}</div>
      </div>
      {children}
    </div>
  );
}

// ─── Right-side Agent activity timeline ─────────────────────────────
function AgentTimeline() {
  const steps = [
    { t: '14:31:02', kind: 'start', msg: '接收任务 · 解析需求' },
    { t: '14:31:04', kind: 'think', msg: '查询 pytdx 接口可用数据范围' },
    { t: '14:31:08', kind: 'code',  msg: '编写 v1 · 朴素 MA 金叉' },
    { t: '14:31:22', kind: 'test',  msg: '运行 v1 回测 · 3 年沪深300' },
    { t: '14:32:01', kind: 'fail',  msg: 'v1 夏普 0.82 未达标 · 分析失败原因' },
    { t: '14:32:10', kind: 'code',  msg: '编写 v2 · 加入成交量过滤' },
    { t: '14:32:28', kind: 'test',  msg: '运行 v2 回测' },
    { t: '14:32:58', kind: 'fail',  msg: 'v2 回撤 -11.6% 仍偏大' },
    { t: '14:33:05', kind: 'code',  msg: '编写 v3 · ATR 动态止损' },
    { t: '14:33:22', kind: 'test',  msg: '运行 v3 回测' },
    { t: '14:33:47', kind: 'tune',  msg: 'v4 · 参数微调 ATR 2.0→2.2' },
    { t: '14:34:05', kind: 'code',  msg: 'v5 · 加入涨跌停/停牌过滤' },
    { t: '14:34:28', kind: 'code',  msg: 'v6 · 加入 MA60 趋势过滤' },
    { t: '14:34:52', kind: 'test',  msg: '运行 v6 回测' },
    { t: '14:35:14', kind: 'done',  msg: 'v6 所有目标达标 · 迭代收敛' },
    { t: '14:35:14', kind: 'report', msg: '生成自动化研发报告' },
  ];

  const tokMetrics = [
    ['模型', 'Claude Opus 4.5'],
    ['输入 Token', '184K'],
    ['输出 Token', '42K'],
    ['代码版本数', '6'],
    ['回测调用数', '6'],
    ['累计成本', '¥0.84'],
    ['耗时', '4m 12s'],
  ];

  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <div className="panel-head">
        <Icon name="sparkle" size={11} style={{ color: 'var(--brand)' }}/>
        <span className="panel-title">Agent 工作流 · 实时</span>
        <span style={{ flex: 1 }}/>
        <span className="pill up"><span className="live-dot"/> 已完成</span>
      </div>

      {/* token / cost meta */}
      <div style={{ padding: '10px 14px', background: 'var(--bg-2)', borderBottom: '1px solid var(--panel-border-soft)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3px 14px' }}>
          {tokMetrics.map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5 }}>
              <span style={{ color: 'var(--text-faint)' }}>{k}</span>
              <span className="mono" style={{ color: 'var(--text-hi)', fontWeight: 500 }}>{v}</span>
            </div>
          ))}
        </div>
      </div>

      {/* timeline */}
      <div style={{ flex: 1, overflow: 'auto', padding: '10px 0' }}>
        {steps.map((s, i) => {
          const colorMap = {
            start: 'var(--info)', think: 'var(--text-faint)',
            code: 'var(--brand)', test: 'var(--info)',
            fail: 'var(--down)', tune: 'var(--warn)',
            done: 'var(--up)', report: 'var(--up)',
          };
          const iconMap = {
            start: '▶', think: '◇', code: '❯', test: '▢',
            fail: '✕', tune: '◈', done: '✓', report: '📄',
          };
          const clr = colorMap[s.kind];
          return (
            <div key={i} style={{ display: 'flex', gap: 10, padding: '5px 14px', alignItems: 'flex-start' }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 2 }}>
                <div style={{
                  width: 16, height: 16, borderRadius: '50%',
                  background: clr + '20', border: '1px solid ' + clr,
                  color: clr, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 9, fontFamily: 'var(--f-mono)',
                }}>{iconMap[s.kind]}</div>
                {i < steps.length - 1 && <div style={{ width: 1, flex: 1, background: 'var(--panel-border-soft)', minHeight: 12, marginTop: 2 }}/>}
              </div>
              <div style={{ flex: 1, paddingBottom: 6 }}>
                <div style={{ fontSize: 11.5, color: 'var(--text)', lineHeight: 1.4 }}>{s.msg}</div>
                <div className="mono" style={{ fontSize: 9.5, color: 'var(--text-ghost)', marginTop: 1 }}>{s.t}</div>
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ padding: 10, borderTop: '1px solid var(--panel-border-soft)', display: 'flex', gap: 6 }}>
        <button className="btn ghost" style={{ flex: 1 }}><Icon name="refresh" size={11}/> 新任务</button>
        <button className="btn primary" style={{ flex: 1 }}><Icon name="agent" size={11}/> 分派给 Agent</button>
      </div>
    </div>
  );
}

function CodeLine({ line }) {
  const kw  = /\b(from|import|class|def|self|return|if|elif|else|and|or|not|None|True|False|in|is|for|while|dict|lambda)\b/g;
  const str = /("[^"]*"|'[^']*')/g;
  const num = /\b(\d+\.?\d*)\b/g;
  const cmt = /(#.*)$/g;
  const bi  = /\b(MA|ATR|cross_up|cross_down|ind|Strategy|size_by_risk|buy|close|is_limit_up|is_suspended|drawdown|position|volume|high|low|open|get_security_bars)\b/g;
  let html = line.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  html = html.replace(cmt, '<span style="color:var(--text-ghost)">$1</span>');
  html = html.replace(str, '<span style="color:oklch(0.82 0.16 140)">$1</span>');
  html = html.replace(kw,  '<span style="color:oklch(0.74 0.18 305)">$1</span>');
  html = html.replace(bi,  '<span style="color:var(--info)">$1</span>');
  html = html.replace(num, '<span style="color:var(--brand)">$1</span>');
  return <div dangerouslySetInnerHTML={{ __html: html || '&nbsp;' }}/>;
}

Object.assign(window, { StrategyEditor });
