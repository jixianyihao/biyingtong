// Backtest — 回测结果 with animated run
function Backtest() {
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(1); // 0..1
  const [selected, setSelected] = useState('ma_v3');
  const rafRef = useRef(null);

  const strategies = {
    ma_v3:   { name: '均线突破 V3.2',  tag: '技术', color: 'var(--brand)', ret: 47.8, bench: 12.4, sharpe: 1.52, mdd: -8.4, win: 64.2, trades: 182 },
    grid:    { name: '网格套利 · 大盘股', tag: '套利', color: 'var(--info)', ret: 18.2, bench: 12.4, sharpe: 2.14, mdd: -3.1, win: 78.4, trades: 846 },
    factor:  { name: '多因子选股', tag: '因子', color: 'var(--purple)', ret: 31.4, bench: 12.4, sharpe: 1.28, mdd: -11.2, win: 58.4, trades: 48 },
  };

  const cur = strategies[selected];

  const runBacktest = () => {
    if (running) {
      // pause / cancel
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      setRunning(false);
      return;
    }
    setRunning(true);
    setProgress(0);
    const t0 = performance.now();
    const dur = 2800;
    const tick = (now) => {
      const p = Math.min(1, (now - t0) / dur);
      setProgress(p);
      if (p < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        rafRef.current = null;
        setRunning(false);
      }
    };
    rafRef.current = requestAnimationFrame(tick);
  };

  useEffect(() => () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); }, []);

  // equity curve data — strategy vs benchmark
  const N = 240;
  const equity = useMemo(() => {
    const r = seedRand(selected === 'ma_v3' ? 5 : selected === 'grid' ? 12 : 33);
    const arr = []; let v = 100;
    const drift = cur.ret / N * 1.0;
    for (let i = 0; i < N; i++) {
      v += drift + (r() - 0.48) * (cur.mdd < -8 ? 1.3 : 0.6);
      arr.push(v);
    }
    return arr;
  }, [selected]);

  const benchmark = useMemo(() => {
    const r = seedRand(777);
    const arr = []; let v = 100;
    for (let i = 0; i < N; i++) { v += cur.bench/N + (r() - 0.5) * 0.9; arr.push(v); }
    return arr;
  }, [selected]);

  const showN = Math.round(N * progress);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr', gridTemplateRows: 'auto minmax(0,1fr)',
      gap: 12, padding: 12, height: '100%', overflow: 'hidden' }}>
      {/* top config */}
      <div className="panel" style={{ padding: 12, display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>策略</div>
          <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
            {Object.entries(strategies).map(([k, s]) => (
              <span key={k} onClick={() => setSelected(k)} style={{
                padding: '4px 10px', fontSize: 11.5, cursor: 'pointer',
                background: selected === k ? 'var(--bg-3)' : 'transparent',
                color: selected === k ? 'var(--text-hi)' : 'var(--text-dim)',
                border: '1px solid ' + (selected === k ? s.color : 'var(--panel-border)'),
                borderRadius: 4
              }}>{s.name}</span>
            ))}
          </div>
        </div>
        <div style={{ width: 1, height: 36, background: 'var(--panel-border)' }}/>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>区间</div>
          <div className="mono" style={{ fontSize: 13, color: 'var(--text-hi)', marginTop: 4 }}>2023-04-20 → 2026-04-20</div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>股票池</div>
          <div style={{ marginTop: 4 }}><span className="pill info">沪深300</span> <span className="pill">382只</span></div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>初始资金</div>
          <div className="mono" style={{ fontSize: 13, color: 'var(--text-hi)', marginTop: 4 }}>¥1,000,000</div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>手续费</div>
          <div className="mono" style={{ fontSize: 13, color: 'var(--text-hi)', marginTop: 4 }}>0.025% · 印花税 0.1%</div>
        </div>
        <div style={{ flex: 1 }}/>
        <button className="btn ghost"><Icon name="settings" size={12}/> 高级设置</button>
        <button className="btn primary" onClick={runBacktest} style={{ padding: '6px 14px' }}>
          {running ? <><Icon name="pause" size={12}/> 回测中 {Math.round(progress*100)}% · 点击暂停</> : <><Icon name="play" size={12}/> {progress < 1 ? '继续回测' : '重新回测'}</>}
        </button>
      </div>

      {/* results grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 340px', gap: 12, minHeight: 0, overflow: 'hidden' }}>
        {/* CENTER: equity + metrics */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0 }}>
          {/* metric row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 8 }}>
            {[
              ['累计收益', pct(cur.ret * progress), cur.ret >= 0 ? 'up' : 'down', '对比基准 ' + pct(cur.bench)],
              ['年化收益', pct(cur.ret * progress / 3), 'up', ''],
              ['夏普比率', (cur.sharpe * progress).toFixed(2), 'up', 'Calmar ' + (cur.sharpe * 0.9).toFixed(2)],
              ['最大回撤', pct(cur.mdd * progress), 'down', '持续 24天'],
              ['胜率', (cur.win * progress).toFixed(1) + '%', 'up', `${Math.round(cur.trades * progress)}笔交易`],
              ['盈亏比', (2.1 * progress).toFixed(2), 'up', '平均持仓 12天']
            ].map(([l, v, c, sub]) => (
              <div key={l} className="panel" style={{ padding: '10px 12px' }}>
                <div style={{ fontSize: 10, color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>{l}</div>
                <div className={`num ${c}`} style={{ fontSize: 20, fontWeight: 600, marginTop: 4, letterSpacing: '-0.01em' }}>{v}</div>
                {sub && <div style={{ fontSize: 10, color: 'var(--text-ghost)', marginTop: 2 }}>{sub}</div>}
              </div>
            ))}
          </div>

          {/* equity curve */}
          <div className="panel" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            <div className="panel-head">
              <span className="panel-title">净值曲线</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10.5 }}>
                <span style={{ width: 8, height: 2, background: cur.color }}/> <span>{cur.name}</span>
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10.5 }}>
                <span style={{ width: 8, height: 2, background: 'var(--text-ghost)' }}/> <span>沪深300</span>
              </span>
              <span style={{ flex: 1 }}/>
              {running && <span className="pill brand"><span className="live-dot"/> 计算中 · {Math.round(progress*100)}%</span>}
              {['3M', '6M', 'YTD', '1Y', '全部'].map((t, i) => (
                <span key={t} style={{
                  padding: '2px 7px', fontSize: 10.5, cursor: 'pointer',
                  color: i === 4 ? 'var(--text-hi)' : 'var(--text-faint)',
                  background: i === 4 ? 'var(--bg-3)' : 'transparent',
                  border: '1px solid ' + (i === 4 ? 'var(--panel-border)' : 'transparent'),
                  borderRadius: 3
                }}>{t}</span>
              ))}
            </div>
            <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
              <EquityChart equity={equity} bench={benchmark} showN={showN} color={cur.color}/>
            </div>
          </div>

          {/* monthly returns heatmap */}
          <div className="panel" style={{ padding: 12, flexShrink: 0 }}>
            <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}>
              月度收益热力图
            </div>
            <MonthlyHeatmap/>
          </div>
        </div>

        {/* RIGHT: trades + rating */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0 }}>
          <div className="panel" style={{ padding: 14 }}>
            <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>策略评分</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 4 }}>
              <div className="serif" style={{ fontSize: 44, color: 'var(--brand)', fontWeight: 600, letterSpacing: '-0.03em', lineHeight: 1 }}>A+</div>
              <div style={{ color: 'var(--text-faint)', fontSize: 11 }}>超越 92% 同类策略</div>
            </div>
            <div style={{ marginTop: 12 }}>
              {[
                ['收益能力', 94], ['风险控制', 76], ['稳定性', 82], ['交易效率', 88], ['过拟合风险', 42]
              ].map(([n, v]) => (
                <div key={n} style={{ marginBottom: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5, marginBottom: 2 }}>
                    <span style={{ color: 'var(--text)' }}>{n}</span>
                    <span className="mono" style={{ color: v > 70 ? 'var(--up)' : v > 50 ? 'var(--brand)' : 'var(--down)', fontWeight: 600 }}>{v}</span>
                  </div>
                  <div style={{ width: '100%', height: 3, background: 'var(--bg-3)', borderRadius: 2 }}>
                    <div style={{ width: v + '%', height: '100%', background: v > 70 ? 'var(--up)' : v > 50 ? 'var(--brand)' : 'var(--down)', borderRadius: 2 }}/>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="panel" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            <div className="panel-head">
              <span className="panel-title">成交记录</span>
              <span className="pill">{Math.round(cur.trades * progress)} 笔</span>
            </div>
            <div style={{ flex: 1, overflow: 'auto' }}>
              <table className="tbl">
                <thead>
                  <tr><th>日期</th><th>方向</th><th>标的</th><th className="num">价格</th><th className="num">盈亏</th></tr>
                </thead>
                <tbody>
                  {[
                    ['25-11-02', 'buy', '茅台', 1584.20, null],
                    ['25-11-24', 'sell', '茅台', 1698.40, 7.2],
                    ['25-12-08', 'buy', '宁德', 198.40, null],
                    ['25-12-21', 'sell', '宁德', 224.80, 13.3],
                    ['26-01-14', 'buy', '平安', 48.20, null],
                    ['26-01-28', 'sell', '平安', 46.80, -2.9],
                    ['26-02-12', 'buy', '招行', 40.10, null],
                    ['26-03-04', 'sell', '招行', 43.40, 8.2],
                    ['26-03-22', 'buy', '格力', 42.10, null],
                    ['26-04-05', 'sell', '格力', 45.80, 8.8],
                  ].map((t, i) => (
                    <tr key={i}>
                      <td className="mono" style={{ color: 'var(--text-ghost)', fontSize: 10.5 }}>{t[0]}</td>
                      <td><span className={`pill ${t[1] === 'buy' ? 'up' : 'down'}`} style={{ fontSize: 9.5 }}>{t[1] === 'buy' ? '买' : '卖'}</span></td>
                      <td style={{ color: 'var(--text)' }}>{t[2]}</td>
                      <td className="num">{fmt(t[3])}</td>
                      <td className={`num ${t[4] === null ? '' : t[4] > 0 ? 'up' : 'down'}`}>{t[4] === null ? '—' : pct(t[4])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function EquityChart({ equity, bench, showN, color }) {
  const ref = useRef(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = ref.current?.parentElement;
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

    const padL = 10, padR = 54, padT = 14, padB = 26;
    const W = size.w, H = size.h;
    const all = [...equity, ...bench];
    const mn = Math.min(...all), mx = Math.max(...all);
    const pad = (mx - mn) * 0.05;
    const lo = mn - pad, hi = mx + pad;
    const x = i => padL + (i / (equity.length - 1)) * (W - padL - padR);
    const y = v => padT + ((hi - v) / (hi - lo)) * (H - padT - padB);

    ctx.fillStyle = 'oklch(0.14 0.010 260)'; ctx.fillRect(0, 0, W, H);
    // grid
    ctx.strokeStyle = 'oklch(0.22 0.010 260 / 0.5)'; ctx.lineWidth = 0.5;
    for (let i = 0; i <= 5; i++) {
      const yy = padT + (H - padT - padB) / 5 * i;
      ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(W - padR, yy); ctx.stroke();
      const v = hi - (hi - lo) / 5 * i;
      ctx.fillStyle = 'oklch(0.52 0.012 260)'; ctx.font = '10px JetBrains Mono';
      ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      ctx.fillText(v.toFixed(0), W - padR + 4, yy);
    }
    // baseline 100
    ctx.strokeStyle = 'oklch(0.52 0.012 260 / 0.4)'; ctx.setLineDash([3, 3]);
    ctx.beginPath(); ctx.moveTo(padL, y(100)); ctx.lineTo(W - padR, y(100)); ctx.stroke();
    ctx.setLineDash([]);

    // benchmark
    ctx.strokeStyle = 'oklch(0.52 0.012 260 / 0.7)'; ctx.lineWidth = 1.2;
    ctx.beginPath();
    for (let i = 0; i < Math.min(showN, bench.length); i++) {
      if (i === 0) ctx.moveTo(x(i), y(bench[i])); else ctx.lineTo(x(i), y(bench[i]));
    }
    ctx.stroke();

    // strategy area
    if (showN > 1) {
      ctx.fillStyle = color === 'var(--brand)' ? 'oklch(0.82 0.18 75 / 0.15)' :
                      color === 'var(--info)' ? 'oklch(0.74 0.15 235 / 0.15)' : 'oklch(0.72 0.18 305 / 0.15)';
      ctx.beginPath();
      ctx.moveTo(x(0), y(equity[0]));
      for (let i = 0; i < showN; i++) ctx.lineTo(x(i), y(equity[i]));
      ctx.lineTo(x(showN - 1), H - padB); ctx.lineTo(x(0), H - padB); ctx.closePath(); ctx.fill();
      // line
      ctx.strokeStyle = color === 'var(--brand)' ? 'oklch(0.82 0.18 75)' :
                        color === 'var(--info)' ? 'oklch(0.74 0.15 235)' : 'oklch(0.72 0.18 305)';
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      for (let i = 0; i < showN; i++) {
        if (i === 0) ctx.moveTo(x(i), y(equity[i])); else ctx.lineTo(x(i), y(equity[i]));
      }
      ctx.stroke();
      // cursor dot
      if (showN < equity.length) {
        const cx = x(showN - 1), cy = y(equity[showN - 1]);
        ctx.fillStyle = 'oklch(0.82 0.18 75)';
        ctx.beginPath(); ctx.arc(cx, cy, 4, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = 'oklch(0.82 0.18 75 / 0.35)';
        ctx.beginPath(); ctx.arc(cx, cy, 10, 0, Math.PI * 2); ctx.stroke();
      }
    }

    // x labels
    ctx.fillStyle = 'oklch(0.52 0.012 260)'; ctx.font = '10px JetBrains Mono'; ctx.textAlign = 'center';
    const xl = ['2023/04', '2023/10', '2024/04', '2024/10', '2025/04', '2025/10', '2026/04'];
    xl.forEach((l, i) => ctx.fillText(l, padL + (W - padL - padR) / (xl.length - 1) * i, H - padB + 14));
  }, [size, equity, bench, showN, color]);
  return <canvas ref={ref} style={{ display: 'block' }}/>;
}

function MonthlyHeatmap() {
  const years = [2024, 2025, 2026];
  const months = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];
  const data = useMemo(() => {
    const r = seedRand(4); const out = {};
    years.forEach(y => { out[y] = months.map((_, i) => {
      if (y === 2026 && i > 3) return null;
      return (r() - 0.35) * 12;
    }); });
    return out;
  }, []);
  const cellColor = v => {
    if (v === null) return 'var(--bg-2)';
    if (v > 0) return `oklch(0.70 0.24 25 / ${Math.min(0.9, 0.15 + v / 15)})`;
    return `oklch(0.78 0.22 148 / ${Math.min(0.9, 0.15 + Math.abs(v) / 15)})`;
  };
  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '40px repeat(12, 1fr) 60px', gap: 3, alignItems: 'center' }}>
        <div/>
        {months.map(m => (
          <div key={m} className="mono" style={{ fontSize: 9, color: 'var(--text-ghost)', textAlign: 'center' }}>{m}</div>
        ))}
        <div className="mono" style={{ fontSize: 9, color: 'var(--text-ghost)', textAlign: 'right' }}>YTD</div>
        {years.map(y => {
          const ytd = data[y].filter(v => v !== null).reduce((a, b) => a + b, 0);
          return (
            <React.Fragment key={y}>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-dim)' }}>{y}</div>
              {data[y].map((v, i) => (
                <div key={i} style={{
                  height: 28, borderRadius: 3,
                  background: cellColor(v),
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 10, fontFamily: 'var(--f-mono)',
                  color: v === null ? 'var(--text-ghost)' : 'var(--text-hi)',
                }}>{v === null ? '—' : v.toFixed(1)}</div>
              ))}
              <div className={`num ${ytd >= 0 ? 'up' : 'down'}`} style={{ fontSize: 11, fontWeight: 600, textAlign: 'right' }}>{pct(ytd)}</div>
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

Object.assign(window, { Backtest });
