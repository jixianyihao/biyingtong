// Dashboard — 主工作台
function Dashboard() {
  const indices = [
    { name: '上证指数', code: '000001.SH', price: 3284.47, chg: 27.52, pct: 0.84 },
    { name: '深证成指', code: '399001.SZ', price: 10847.23, chg: 112.08, pct: 1.04 },
    { name: '创业板指', code: '399006.SZ', price: 2174.88, chg: -8.14, pct: -0.37 },
    { name: '沪深300', code: '000300.SH', price: 3924.12, chg: 34.55, pct: 0.89 },
    { name: '科创50', code: '000688.SH', price: 982.44, chg: 6.72, pct: 0.69 },
  ];

  const watchlist = [
    { code: '600519', name: '贵州茅台', price: 1684.50, pct: 2.34, vol: '2.47亿', strat: '均线突破' },
    { code: '300750', name: '宁德时代', price: 247.80, pct: 3.12, vol: '18.2亿', strat: 'AI-浮游' },
    { code: '000858', name: '五粮液', price: 158.42, pct: 1.87, vol: '8.4亿', strat: '均线突破' },
    { code: '002594', name: '比亚迪', price: 278.90, pct: -0.84, vol: '12.1亿', strat: '网格套利' },
    { code: '601899', name: '紫金矿业', price: 18.24, pct: 4.52, vol: '24.8亿', strat: 'AI-操盘手林园' },
    { code: '600036', name: '招商银行', price: 42.18, pct: 0.24, vol: '6.7亿', strat: '红利低波' },
    { code: '688981', name: '中芯国际', price: 112.33, pct: -1.24, vol: '5.1亿', strat: '量价共振' },
    { code: '300059', name: '东方财富', price: 18.74, pct: 2.92, vol: '32.4亿', strat: '—' },
    { code: '002415', name: '海康威视', price: 34.55, pct: 0.87, vol: '4.2亿', strat: 'AI-林园' },
  ];

  const signals = [
    { time: '14:32:18', type: 'buy', code: '300750', name: '宁德时代', strat: 'AI-浮游', price: 247.8, qty: 200, reason: '突破60日新高 + 成交量放大至均量2.1倍' },
    { time: '14:28:04', type: 'sell', code: '600030', name: '中信证券', strat: '均线突破', price: 22.14, qty: 800, reason: 'MA5下穿MA20，趋势反转信号' },
    { time: '14:21:55', type: 'buy', code: '601899', name: '紫金矿业', strat: 'AI-林园', price: 17.89, qty: 1000, reason: '有色板块龙头 · 估值处于历史30%分位' },
    { time: '14:18:33', type: 'alert', code: '002594', name: '比亚迪', strat: '风险监控', price: 278.9, qty: 0, reason: '单日回撤触及-2%止损阈值' },
    { time: '14:12:47', type: 'buy', code: '300059', name: '东方财富', strat: 'AI-浮游', price: 18.21, qty: 500, reason: '券商板块情绪反转，RSI低位背离' },
  ];

  return (
    <div style={{
      padding: 12,
      display: 'grid',
      gridTemplateColumns: 'minmax(0, 1fr) 360px',
      gridTemplateRows: 'auto auto minmax(0, 1fr)',
      gap: 12,
      height: '100%',
      overflow: 'hidden'
    }}>
      {/* RETAIL P&L HERO — 最重要的事：我今天赚了多少？AI 帮了我什么？下一步做什么？ */}
      <div style={{ gridColumn: '1 / span 2', display: 'grid', gridTemplateColumns: '1.1fr 1fr 1fr 1fr', gap: 10 }}>
        {/* 今日盈亏 */}
        <div className="panel" style={{ padding: '14px 16px', background:
          'linear-gradient(135deg, oklch(0.20 0.08 150) 0%, oklch(0.14 0.02 260) 60%)',
          border: '1px solid var(--up)' }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>今日盈亏 · 实盘</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginTop: 6 }}>
            <span className="num up serif" style={{ fontSize: 34, fontWeight: 600, letterSpacing: '-0.02em' }}>+¥4,287</span>
            <span className="num up mono" style={{ fontSize: 13 }}>+1.82%</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 6, display: 'flex', gap: 14 }}>
            <span>总资产 <span className="mono" style={{ color: 'var(--text-hi)' }}>¥239,840</span></span>
            <span>本周 <span className="mono up">+¥12,460</span></span>
            <span>本月 <span className="mono up">+¥31,204</span></span>
          </div>
        </div>

        {/* AI 今日为你做了什么 */}
        <div className="panel" style={{ padding: '14px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Icon name="sparkle" size={11} style={{ color: 'var(--brand)' }}/>
            <span style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>AI 操盘手今日贡献</span>
          </div>
          <div style={{ fontSize: 22, color: 'var(--up)', fontWeight: 600, letterSpacing: '-0.01em', marginTop: 2 }}>
            +¥3,142 <span style={{ fontSize: 11, color: 'var(--text-faint)', fontWeight: 400 }}>· 占比 73%</span>
          </div>
          <div style={{ fontSize: 10.5, color: 'var(--text-dim)', marginTop: 6, lineHeight: 1.5 }}>
            <div>✓ 林园风格 买入紫金矿业 <span className="up mono">+¥1,840</span></div>
            <div>✓ 浮游短线 抓到宁德时代 <span className="up mono">+¥1,560</span></div>
            <div>✓ 巴菲特风格 长持茅台贡献 <span className="up mono">+¥742</span></div>
          </div>
        </div>

        {/* AI 帮你避开的坑 */}
        <div className="panel" style={{ padding: '14px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Icon name="risk" size={11} style={{ color: 'var(--warn)' }}/>
            <span style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>今日避免的损失</span>
          </div>
          <div style={{ fontSize: 22, color: 'var(--warn)', fontWeight: 600, letterSpacing: '-0.01em', marginTop: 2 }}>
            -¥2,840 <span style={{ fontSize: 11, color: 'var(--text-faint)', fontWeight: 400 }}>若未拦截</span>
          </div>
          <div style={{ fontSize: 10.5, color: 'var(--text-dim)', marginTop: 6, lineHeight: 1.5 }}>
            <div>⊘ 拦截追高 *ST 凯迪 <span className="mono" style={{ color: 'var(--text-faint)' }}>已退市风险</span></div>
            <div>⊘ 阻止全仓一只票 <span className="mono" style={{ color: 'var(--text-faint)' }}>超集中度</span></div>
            <div>⊘ 提前止损 2 只下跌股 <span className="mono" style={{ color: 'var(--text-faint)' }}>-2.5% 阈值</span></div>
          </div>
        </div>

        {/* 下一步建议 */}
        <div className="panel" style={{ padding: '14px 16px', background: 'var(--bg-1)', border: '1px solid var(--brand)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Icon name="bolt" size={11} style={{ color: 'var(--brand)' }}/>
            <span style={{ fontSize: 10.5, color: 'var(--brand)', letterSpacing: '0.12em', textTransform: 'uppercase', fontWeight: 600 }}>下一步建议 · 待你确认</span>
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--text-hi)', marginTop: 5, lineHeight: 1.45 }}>
            <span style={{ fontWeight: 600 }}>减仓 片仔癀</span> <span className="down mono" style={{ fontSize: 11 }}>-50%</span>
          </div>
          <div style={{ fontSize: 10.5, color: 'var(--text-faint)', marginTop: 2, lineHeight: 1.45 }}>
            创新高后 PE 48x 超安全边际，林园 Agent 建议锁利
          </div>
          <div style={{ display: 'flex', gap: 5, marginTop: 9 }}>
            <button className="btn ghost" style={{ flex: 1, padding: '4px 0', fontSize: 11 }}>忽略</button>
            <button className="btn primary" style={{ flex: 1, padding: '4px 0', fontSize: 11 }}>一键执行</button>
          </div>
        </div>
      </div>

      {/* index strip — spans both columns */}
      <div style={{ gridColumn: '1 / span 2', display: 'flex', gap: 10, overflowX: 'auto' }}>
        {indices.map(i => (
          <div key={i.code} className="panel" style={{ padding: '10px 14px', minWidth: 196, flexShrink: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <div style={{ color: 'var(--text-hi)', fontWeight: 600 }}>{i.name}</div>
              <div className="mono" style={{ fontSize: 9.5, color: 'var(--text-ghost)', letterSpacing: '0.08em' }}>{i.code}</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 4 }}>
              <div className={`num ${i.pct >= 0 ? 'up' : 'down'}`} style={{ fontSize: 20, fontWeight: 600, letterSpacing: '-0.01em' }}>{fmt(i.price)}</div>
              <div className="mono" style={{ fontSize: 11 }}>
                <span className={i.pct >= 0 ? 'up' : 'down'}>{pct(i.pct)}</span>
              </div>
            </div>
            <div style={{ marginTop: 4 }}>
              <Sparkline data={genSpark(i.code.length * 17, 32, i.pct > 0 ? 0.15 : -0.15, 0.9)}
                color={i.pct >= 0 ? 'var(--up)' : 'var(--down)'} width={168} height={26}/>
            </div>
          </div>
        ))}
      </div>

      {/* LEFT column: watchlist + chart */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0, minHeight: 0 }}>
        {/* chart */}
        <div className="panel" style={{ flex: '1 1 0', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <div className="panel-head">
            <span className="panel-title">贵州茅台 · 600519.SH</span>
            <span className="pill up">¥1,684.50</span>
            <span className="mono up" style={{ fontSize: 11 }}>+38.40 +2.34%</span>
            <span style={{ flex: 1 }}/>
            {['1分', '5分', '15分', '日线', '周线', '月线'].map((t, i) => (
              <span key={t} style={{
                padding: '2px 7px', fontSize: 10.5, fontWeight: 500,
                color: i === 3 ? 'var(--text-hi)' : 'var(--text-faint)',
                background: i === 3 ? 'var(--bg-3)' : 'transparent',
                border: '1px solid ' + (i === 3 ? 'var(--panel-border)' : 'transparent'),
                borderRadius: 3, cursor: 'pointer'
              }}>{t}</span>
            ))}
            <span style={{ marginLeft: 8, color: 'var(--text-ghost)' }}>|</span>
            <span className="kbd" style={{ cursor: 'pointer' }}>MA</span>
            <span className="kbd" style={{ cursor: 'pointer' }}>BOLL</span>
            <span className="kbd" style={{ cursor: 'pointer' }}>MACD</span>
          </div>
          <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
            <CandleChart/>
          </div>
        </div>

        {/* watchlist */}
        <div className="panel" style={{ flex: '1 1 0', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <div className="panel-head">
            <span className="panel-title">自选 · 策略信号</span>
            <span className="pill">{watchlist.length}只</span>
            <span style={{ flex: 1 }}/>
            <span style={{ fontSize: 10.5, color: 'var(--text-faint)' }}>按涨幅排序</span>
          </div>
          <div style={{ overflow: 'auto', flex: 1 }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th className="num">现价</th>
                  <th className="num">涨幅</th>
                  <th className="num">成交</th>
                  <th>归属策略</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {watchlist.map(s => (
                  <tr key={s.code}>
                    <td className="mono" style={{ color: 'var(--text-faint)' }}>{s.code}</td>
                    <td style={{ color: 'var(--text-hi)', fontWeight: 500 }}>{s.name}</td>
                    <td className={`num ${s.pct >= 0 ? 'up' : 'down'}`}>{fmt(s.price)}</td>
                    <td className={`num ${s.pct >= 0 ? 'up' : 'down'}`}>{pct(s.pct)}</td>
                    <td className="num" style={{ color: 'var(--text-dim)' }}>{s.vol}</td>
                    <td>
                      {s.strat !== '—' ? (
                        <span className={`pill ${s.strat.startsWith('AI') ? 'brand' : ''}`}
                          style={{ fontSize: 10 }}>
                          {s.strat.startsWith('AI') && <Icon name="sparkle" size={9}/>}
                          {s.strat}
                        </span>
                      ) : <span style={{ color: 'var(--text-ghost)' }}>—</span>}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <Sparkline data={genSpark(s.code.length * 11, 22, s.pct > 0 ? 0.1 : -0.1)}
                        color={s.pct >= 0 ? 'var(--up)' : 'var(--down)'} width={60} height={18}/>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* RIGHT column: strategy perf + signals + account */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0 }}>
        {/* account */}
        <div className="panel" style={{ padding: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>账户净值</span>
            <span className="pill up"><Icon name="arrowUp" size={9}/> 历史新高</span>
          </div>
          <div className="num" style={{ fontSize: 28, fontWeight: 600, color: 'var(--text-hi)', marginTop: 6, letterSpacing: '-0.02em' }}>
            ¥2,847,213<span style={{ fontSize: 16, color: 'var(--text-dim)' }}>.55</span>
          </div>
          <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 11 }}>
            <span><span style={{ color: 'var(--text-faint)' }}>今日 </span><span className="up mono">+0.83%</span></span>
            <span><span style={{ color: 'var(--text-faint)' }}>本月 </span><span className="up mono">+5.47%</span></span>
            <span><span style={{ color: 'var(--text-faint)' }}>年内 </span><span className="up mono">+34.18%</span></span>
          </div>
          <div style={{ marginTop: 10 }}>
            <Sparkline data={genSpark(42, 80, 0.4, 0.6)} color="var(--brand)" width={332} height={48}/>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--panel-border-soft)' }}>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>可用资金</div>
              <div className="num" style={{ fontSize: 13, color: 'var(--text-hi)', marginTop: 2 }}>¥684,201</div>
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>持仓市值</div>
              <div className="num" style={{ fontSize: 13, color: 'var(--text-hi)', marginTop: 2 }}>¥2,163,012</div>
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>仓位</div>
              <div className="num" style={{ fontSize: 13, color: 'var(--brand)', marginTop: 2 }}>76.0%</div>
            </div>
          </div>
        </div>

        {/* strategy perf */}
        <div className="panel" style={{ flexShrink: 0 }}>
          <div className="panel-head">
            <span className="panel-title">我的策略 · 运行中</span>
            <span className="pill up"><span className="live-dot"/> 7个</span>
          </div>
          <div style={{ padding: '4px 0' }}>
            {[
              { name: 'AI-林园风格', tag: 'LLM', pct: 12.4, spark: genSpark(1, 30, 0.3), mdd: -3.2 },
              { name: 'AI-浮游短线', tag: 'LLM', pct: 28.7, spark: genSpark(2, 30, 0.5, 1.2), mdd: -6.1 },
              { name: '均线突破v3', tag: '技术', pct: 8.2, spark: genSpark(3, 30, 0.2), mdd: -2.8 },
              { name: '红利低波', tag: '基本面', pct: 4.7, spark: genSpark(4, 30, 0.1, 0.5), mdd: -1.4 },
              { name: '网格套利', tag: '套利', pct: -1.2, spark: genSpark(5, 30, -0.05), mdd: -4.2 },
            ].map(s => (
              <div key={s.name} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 12px', borderBottom: '1px solid var(--panel-border-soft)',
              }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <span style={{ color: 'var(--text-hi)', fontSize: 12, fontWeight: 500 }}>{s.name}</span>
                    <span className={`pill ${s.tag === 'LLM' ? 'brand' : ''}`} style={{ fontSize: 9 }}>{s.tag}</span>
                  </div>
                  <div className="mono" style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 2 }}>
                    本月 <span className={s.pct >= 0 ? 'up' : 'down'}>{pct(s.pct)}</span> · 回撤 <span className="down">{pct(s.mdd)}</span>
                  </div>
                </div>
                <Sparkline data={s.spark} color={s.pct >= 0 ? 'var(--up)' : 'var(--down)'} width={60} height={22}/>
              </div>
            ))}
          </div>
        </div>

        {/* Python API panel */}
        <PyApiPanel/>

        {/* signals */}
        <div className="panel" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <div className="panel-head">
            <span className="panel-title">今日信号</span>
            <span className="pill">{signals.length}</span>
            <span style={{ flex: 1 }}/>
            <span style={{ fontSize: 10.5, color: 'var(--text-faint)' }}>实时</span>
          </div>
          <div style={{ overflow: 'auto', flex: 1 }}>
            {signals.map((s, i) => {
              const clr = s.type === 'buy' ? 'var(--up)' : s.type === 'sell' ? 'var(--down)' : 'var(--warn)';
              const label = s.type === 'buy' ? '买' : s.type === 'sell' ? '卖' : '警';
              return (
                <div key={i} style={{
                  padding: '9px 12px',
                  borderBottom: '1px solid var(--panel-border-soft)',
                  display: 'flex', gap: 10,
                }}>
                  <div style={{
                    width: 22, height: 22, borderRadius: 3, flexShrink: 0,
                    background: clr + '20',
                    color: clr,
                    border: '1px solid ' + clr + '60',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 11, fontWeight: 600,
                  }}>{label}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'baseline' }}>
                      <span style={{ color: 'var(--text-hi)', fontWeight: 500 }}>{s.name}</span>
                      <span className="mono" style={{ fontSize: 10, color: 'var(--text-ghost)' }}>{s.code}</span>
                      <span style={{ flex: 1 }}/>
                      <span className="mono" style={{ fontSize: 10, color: 'var(--text-faint)' }}>{s.time}</span>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2, lineHeight: 1.4 }}>
                      {s.reason}
                    </div>
                    {s.qty > 0 && (
                      <div className="mono" style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 3 }}>
                        @¥{fmt(s.price)} × {s.qty}股 · 来自 <span style={{ color: 'var(--brand)' }}>{s.strat}</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Candle chart (the real centerpiece) ---
function CandleChart() {
  const canvasRef = useRef(null);
  const [size, setSize] = useState({ w: 0, h: 0 });

  useEffect(() => {
    const el = canvasRef.current?.parentElement;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setSize({ w: el.clientWidth, h: el.clientHeight });
    });
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!size.w || !size.h) return;
    const cvs = canvasRef.current;
    const dpr = window.devicePixelRatio || 1;
    cvs.width = size.w * dpr;
    cvs.height = size.h * dpr;
    cvs.style.width = size.w + 'px';
    cvs.style.height = size.h + 'px';
    const ctx = cvs.getContext('2d');
    ctx.scale(dpr, dpr);

    // generate candles
    const N = 80;
    const r = seedRand(42);
    const bars = [];
    let price = 1580;
    for (let i = 0; i < N; i++) {
      const open = price;
      const drift = (Math.sin(i / 12) + 0.3) * 3;
      const vol = 8 + r() * 16;
      const close = open + drift + (r() - 0.5) * vol;
      const high = Math.max(open, close) + r() * vol * 0.6;
      const low = Math.min(open, close) - r() * vol * 0.6;
      bars.push({ open, close, high, low, vol: 20 + r() * 80 });
      price = close;
    }

    // layout
    const padL = 10, padR = 58, padT = 14, padB = 92;
    const chartH = size.h - padT - padB;
    const volH = 70;
    const W = size.w;
    const innerW = W - padL - padR;
    const barW = innerW / N;

    // Find min/max
    const allHi = Math.max(...bars.map(b => b.high));
    const allLo = Math.min(...bars.map(b => b.low));
    const pad = (allHi - allLo) * 0.08;
    const hi = allHi + pad, lo = allLo - pad;
    const yOf = p => padT + ((hi - p) / (hi - lo)) * chartH;

    // bg
    ctx.fillStyle = 'oklch(0.14 0.010 260)';
    ctx.fillRect(0, 0, W, size.h);

    // horizontal grid + price labels
    ctx.strokeStyle = 'oklch(0.22 0.010 260 / 0.5)';
    ctx.lineWidth = 0.5;
    ctx.font = '10px JetBrains Mono, monospace';
    ctx.fillStyle = 'oklch(0.52 0.012 260)';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    for (let i = 0; i <= 6; i++) {
      const y = padT + (chartH / 6) * i;
      const p = hi - ((hi - lo) / 6) * i;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(W - padR, y);
      ctx.stroke();
      ctx.fillText(p.toFixed(2), W - padR + 4, y);
    }

    // MA20 line
    const ma = [];
    for (let i = 0; i < N; i++) {
      if (i < 19) { ma.push(null); continue; }
      let s = 0;
      for (let j = i - 19; j <= i; j++) s += bars[j].close;
      ma.push(s / 20);
    }
    ctx.strokeStyle = 'oklch(0.82 0.18 75 / 0.7)';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    let started = false;
    ma.forEach((v, i) => {
      if (v === null) return;
      const x = padL + i * barW + barW / 2;
      const y = yOf(v);
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // candles
    bars.forEach((b, i) => {
      const x = padL + i * barW + barW / 2;
      const up = b.close >= b.open;
      const clr = up ? 'oklch(0.70 0.24 25)' : 'oklch(0.78 0.22 148)';
      ctx.strokeStyle = clr;
      ctx.fillStyle = clr;
      // wick
      ctx.beginPath();
      ctx.lineWidth = 1;
      ctx.moveTo(x, yOf(b.high));
      ctx.lineTo(x, yOf(b.low));
      ctx.stroke();
      // body
      const y1 = yOf(b.open), y2 = yOf(b.close);
      const top = Math.min(y1, y2);
      const h = Math.max(1, Math.abs(y2 - y1));
      const bw = Math.max(2, barW * 0.68);
      if (up) {
        ctx.fillRect(x - bw / 2, top, bw, h);
      } else {
        ctx.strokeRect(x - bw / 2, top, bw, h);
      }
    });

    // Volume
    const volY0 = size.h - padB + 18;
    const maxVol = Math.max(...bars.map(b => b.vol));
    ctx.fillStyle = 'oklch(0.52 0.012 260)';
    ctx.font = '9.5px JetBrains Mono, monospace';
    ctx.fillText('VOL', padL + 2, volY0 - 8);
    bars.forEach((b, i) => {
      const x = padL + i * barW + barW / 2;
      const up = b.close >= b.open;
      ctx.fillStyle = up ? 'oklch(0.70 0.24 25 / 0.7)' : 'oklch(0.78 0.22 148 / 0.7)';
      const h = (b.vol / maxVol) * volH;
      const bw = Math.max(2, barW * 0.68);
      ctx.fillRect(x - bw / 2, volY0 + (volH - h), bw, h);
    });

    // current price line
    const cur = bars[N - 1].close;
    ctx.strokeStyle = 'oklch(0.70 0.24 25 / 0.5)';
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(padL, yOf(cur));
    ctx.lineTo(W - padR, yOf(cur));
    ctx.stroke();
    ctx.setLineDash([]);
    // price tag
    ctx.fillStyle = 'oklch(0.70 0.24 25)';
    ctx.fillRect(W - padR, yOf(cur) - 9, padR - 2, 18);
    ctx.fillStyle = 'white';
    ctx.font = '10.5px JetBrains Mono, monospace';
    ctx.textAlign = 'center';
    ctx.fillText(cur.toFixed(2), W - padR / 2 - 1, yOf(cur));

    // x-axis dates
    ctx.fillStyle = 'oklch(0.52 0.012 260)';
    ctx.textAlign = 'center';
    ctx.font = '9.5px JetBrains Mono, monospace';
    const xLabels = ['03/01', '03/15', '03/29', '04/12', '今日'];
    xLabels.forEach((l, i) => {
      const x = padL + (innerW / (xLabels.length - 1)) * i;
      ctx.fillText(l, x, size.h - padB + volH + 28);
    });

    // crosshair hint badge top-left
    ctx.fillStyle = 'oklch(0.88 0.008 260)';
    ctx.textAlign = 'left';
    ctx.font = '10.5px JetBrains Mono, monospace';
    ctx.fillText('O 1646.10  H 1692.80  L 1644.20  C 1684.50  +2.34%', padL + 4, padT + 10);
  }, [size]);

  return <canvas ref={canvasRef} style={{ display: 'block' }}/>;
}

// --- Python API panel: shows pytdx interface calls ---
function PyApiPanel() {
  const endpoints = [
    { fn: 'get_security_bars',   desc: 'K线数据',      calls: 4821, rate: 142, ok: 100 },
    { fn: 'get_security_quotes', desc: '实时行情快照',   calls: 8204, rate: 318, ok: 99.8 },
    { fn: 'get_transaction_data',desc: '逐笔成交',       calls: 2140, rate: 88,  ok: 100 },
    { fn: 'get_finance_info',    desc: '财务数据',       calls: 612,  rate: 4,   ok: 100 },
    { fn: 'get_xdxr_info',       desc: '除权除息',       calls: 204,  rate: 1,   ok: 100 },
    { fn: 'get_k_data',          desc: '历史日K (TDX缓存)', calls: 1847, rate: 22,  ok: 99.2 },
  ];

  const seedLogs = [
    { t: '14:35:43.218', fn: 'get_security_quotes',  arg: '([0,1],"600519","300750",...)', ms: 8,  ok: true },
    { t: '14:35:43.201', fn: 'get_security_bars',    arg: '(9,0,"000001",0,120)',           ms: 14, ok: true },
    { t: '14:35:43.189', fn: 'get_transaction_data', arg: '(1,"601899",0,30)',              ms: 11, ok: true },
    { t: '14:35:43.174', fn: 'get_security_quotes',  arg: '([0,1],"600036","002594",...)', ms: 9,  ok: true },
    { t: '14:35:43.152', fn: 'get_security_bars',    arg: '(4,1,"300750",0,240)',           ms: 22, ok: true },
    { t: '14:35:43.131', fn: 'get_finance_info',     arg: '(1,"600519")',                    ms: 34, ok: true },
    { t: '14:35:43.118', fn: 'get_security_quotes',  arg: '([1],"688981","300059",...)',    ms: 7,  ok: true },
    { t: '14:35:43.094', fn: 'get_security_bars',    arg: '(9,1,"002415",0,120)',           ms: 13, ok: true },
    { t: '14:35:43.076', fn: 'get_k_data',           arg: '("601899","D",-60)',              ms: 41, ok: true },
    { t: '14:35:43.055', fn: 'get_security_quotes',  arg: '([0],"600519",...)',              ms: 6,  ok: true },
  ];
  const [logs, setLogs] = React.useState(seedLogs);

  // live append
  React.useEffect(() => {
    const quickFns = [
      ['get_security_quotes', () => `([0,1],"${pickCode()}","${pickCode()}",...)`, [6, 14]],
      ['get_security_bars',   () => `(9,${Math.random() > 0.5 ? 0 : 1},"${pickCode()}",0,120)`, [10, 28]],
      ['get_transaction_data',() => `(1,"${pickCode()}",0,30)`, [9, 18]],
      ['get_security_quotes', () => `([1],"${pickCode()}",...)`, [5, 11]],
    ];
    const pickCode = () => ['600519','300750','000858','002594','601899','600036','688981','300059','002415'][Math.floor(Math.random()*9)];
    let i = 0;
    const id = setInterval(() => {
      i++;
      const [fn, argFn, [lo, hi]] = quickFns[Math.floor(Math.random() * quickFns.length)];
      const now = new Date();
      const t = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}.${String(now.getMilliseconds()).padStart(3,'0')}`;
      const ok = Math.random() > 0.03;
      const entry = { t, fn, arg: argFn(), ms: lo + Math.floor(Math.random()*(hi-lo)), ok };
      setLogs(prev => [entry, ...prev].slice(0, 12));
    }, 1400);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="panel" style={{ flexShrink: 0 }}>
      <div className="panel-head">
        <Icon name="sparkle" size={11} style={{ color: 'var(--brand)' }}/>
        <span className="panel-title">数据接口 · 通达信 Python</span>
        <span className="pill up"><span className="live-dot"/> 已连接</span>
        <span style={{ flex: 1 }}/>
        <span className="mono" style={{ fontSize: 10, color: 'var(--text-ghost)' }}>pytdx 1.72</span>
      </div>

      {/* meta row */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr 1fr',
        padding: '8px 12px',
        background: 'var(--bg-2)',
        borderBottom: '1px solid var(--panel-border-soft)',
        gap: 10,
      }}>
        <div>
          <div style={{ fontSize: 9.5, color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>调用总量</div>
          <div className="num mono" style={{ fontSize: 14, color: 'var(--text-hi)', marginTop: 1 }}>17,828</div>
        </div>
        <div>
          <div style={{ fontSize: 9.5, color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>tick / 秒</div>
          <div className="num mono" style={{ fontSize: 14, color: 'var(--up)', marginTop: 1 }}>1,842</div>
        </div>
        <div>
          <div style={{ fontSize: 9.5, color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>P95 延迟</div>
          <div className="num mono" style={{ fontSize: 14, color: 'var(--text-hi)', marginTop: 1 }}>24<span style={{ fontSize: 10, color: 'var(--text-faint)', marginLeft: 2 }}>ms</span></div>
        </div>
      </div>

      {/* endpoint table */}
      <div style={{ padding: '4px 0' }}>
        {endpoints.map(ep => (
          <div key={ep.fn} style={{
            display: 'grid', gridTemplateColumns: '1fr 58px 50px',
            alignItems: 'center', gap: 10,
            padding: '6px 12px',
            borderBottom: '1px solid var(--panel-border-soft)',
          }}>
            <div style={{ minWidth: 0 }}>
              <div className="mono" style={{ fontSize: 11, color: 'var(--brand)' }}>{ep.fn}<span style={{ color: 'var(--text-ghost)' }}>()</span></div>
              <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 1 }}>{ep.desc}</div>
            </div>
            <div className="num mono" style={{ fontSize: 11, color: 'var(--text-dim)', textAlign: 'right' }}>{ep.calls.toLocaleString()}</div>
            <div style={{ textAlign: 'right' }}>
              <div className="num mono" style={{ fontSize: 11, color: 'var(--text-hi)' }}>{ep.rate}<span style={{ fontSize: 9, color: 'var(--text-faint)' }}>/s</span></div>
              <div className="mono" style={{ fontSize: 9, color: ep.ok >= 99.5 ? 'var(--up)' : 'var(--warn)' }}>{ep.ok.toFixed(1)}%</div>
            </div>
          </div>
        ))}
      </div>

      {/* live log stream */}
      <div style={{
        borderTop: '1px solid var(--panel-border)',
        background: 'oklch(0.10 0.008 260)',
        padding: '6px 10px 8px',
        maxHeight: 132,
        overflow: 'hidden',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          <span style={{ fontSize: 9.5, color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>调用流</span>
          <span className="live-dot" style={{ color: 'var(--brand)' }}/>
          <span style={{ flex: 1 }}/>
          <span className="mono" style={{ fontSize: 9, color: 'var(--text-ghost)' }}>stdout › tdx_bridge.py</span>
        </div>
        {logs.map((l, i) => (
          <div key={l.t + i} className="mono" style={{
            fontSize: 10,
            lineHeight: 1.45,
            display: 'flex', gap: 8,
            opacity: 1 - i * 0.06,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            <span style={{ color: 'var(--text-ghost)' }}>{l.t}</span>
            <span style={{ color: l.ok ? 'var(--up)' : 'var(--down)' }}>{l.ok ? '›' : '✕'}</span>
            <span style={{ color: 'var(--brand)' }}>{l.fn}</span>
            <span style={{ color: 'var(--text-dim)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{l.arg}</span>
            <span style={{ flex: 1 }}/>
            <span style={{ color: l.ms < 15 ? 'var(--up)' : l.ms < 30 ? 'var(--text-faint)' : 'var(--warn)' }}>{l.ms}ms</span>
          </div>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { Dashboard, CandleChart, PyApiPanel });
