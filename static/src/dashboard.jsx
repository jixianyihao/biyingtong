// Dashboard — 主工作台 (TDX live data)
function Dashboard() {
  const [indices, setIndices] = useState([]);
  const [watchlist, setWatchlist] = useState([]);
  const [klineData, setKlineData] = useState([]);
  const [klineCode, setKlineCode] = useState('600519.SH');
  const [klineInfo, setKlineInfo] = useState({ name: '—', code: '' });
  const [account, setAccount] = useState(null);
  const [loading, setLoading] = useState(true);

  const WATCHLIST_CODES = ['600519.SH','300750.SZ','000858.SZ','002594.SZ','601899.SH','600036.SH','688981.SH','300059.SZ','002415.SZ'];

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [idx, snaps, bars, acc] = await Promise.allSettled([
          BYT.getIndices(),
          BYT.getSnapshots(WATCHLIST_CODES),
          BYT.getKline(klineCode, '1d', 80),
          BYT.getAsset(),
        ]);
        if (idx.status === 'fulfilled' && idx.value.length > 0) setIndices(idx.value);
        if (snaps.status === 'fulfilled' && snaps.value.length > 0) {
          setWatchlist(snaps.value.map(s => ({
            code: s.code.replace(/\.(SH|SZ|BJ)/, ''),
            name: s.name || s.code,
            price: s.price,
            pct: s.pct,
            vol: BYT.fmtVol(s.vol),
            strat: '—',
          })));
          // Update kline info name from watchlist
          const match = snaps.value.find(s => s.code === klineCode);
          if (match) setKlineInfo({ name: match.name, code: klineCode });
        }
        if (bars.status === 'fulfilled' && bars.value.length > 0) setKlineData(bars.value);
        if (acc.status === 'fulfilled' && acc.value && !acc.value.error) setAccount(acc.value);
      } catch (e) {
        console.error('Dashboard load error:', e);
      }
      setLoading(false);
    }
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [klineCode]);

  // Account data extraction (field names vary by TDX version)
  const hasAccount = account && !account.error;
  const totalAsset = hasAccount ? (parseFloat(account.Asset || account.TotalAsset || account.total_asset || 0)) : null;
  const availableCash = hasAccount ? (parseFloat(account.Cash || account.AvailableFund || account.available || 0)) : null;
  const marketValue = hasAccount ? (parseFloat(account.MarketValue || account.market_value || 0)) : null;
  const todayPnl = hasAccount ? (parseFloat(account.ProfitLoss || account.TodayIncome || account.today_income || account.TodayProfit || 0)) : null;
  const positionPct = totalAsset !== null && marketValue !== null && totalAsset > 0 && marketValue > 0 ? (marketValue / totalAsset * 100).toFixed(1) : '—';

  // Keep mock signals (these come from AI agents, deferred)
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
      {/* RETAIL P&L HERO */}
      <div style={{ gridColumn: '1 / span 2', display: 'grid', gridTemplateColumns: '1.1fr 1fr 1fr 1fr', gap: 10 }}>
        {/* 今日盈亏 */}
        <div className="panel" style={{ padding: '14px 16px', background:
          'linear-gradient(135deg, oklch(0.20 0.08 150) 0%, oklch(0.14 0.02 260) 60%)',
          border: '1px solid ' + (hasAccount ? 'var(--up)' : 'var(--panel-border)') }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>今日盈亏 · 实盘</div>
          {hasAccount ? (
            <>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginTop: 6 }}>
                <span className={`num ${todayPnl >= 0 ? 'up' : 'down'} serif`} style={{ fontSize: 34, fontWeight: 600, letterSpacing: '-0.02em' }}>
                  {todayPnl >= 0 ? '+' : ''}¥{Math.abs(todayPnl).toLocaleString()}
                </span>
                <span className={`num ${todayPnl >= 0 ? 'up' : 'down'} mono`} style={{ fontSize: 13 }}>
                  {totalAsset > 0 ? (todayPnl >= 0 ? '+' : '') + (todayPnl / totalAsset * 100).toFixed(2) + '%' : '—'}
                </span>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 6, display: 'flex', gap: 14 }}>
                <span>总资产 <span className="mono" style={{ color: 'var(--text-hi)' }}>¥{totalAsset.toLocaleString()}</span></span>
                <span>可用 <span className="mono" style={{ color: 'var(--text-hi)' }}>¥{availableCash.toLocaleString()}</span></span>
              </div>
            </>
          ) : (
            <div style={{ marginTop: 6 }}>
              <div style={{ fontSize: 22, color: 'var(--text-faint)', fontWeight: 600 }}>未登录实盘账户</div>
              <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 6 }}>请在通达信客户端登录交易账户后刷新</div>
            </div>
          )}
        </div>

        {/* AI 今日为你做了什么 — requires LLM integration */}
        <div className="panel" style={{ padding: '14px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Icon name="sparkle" size={11} style={{ color: 'var(--brand)' }}/>
            <span style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>AI 操盘手今日贡献</span>
            <span className="pill" style={{ fontSize: 9, color: 'var(--warn)' }}>未接入</span>
          </div>
          <div style={{ fontSize: 16, color: 'var(--text-faint)', fontWeight: 600, letterSpacing: '-0.01em', marginTop: 2 }}>
            —
          </div>
          <div style={{ fontSize: 10.5, color: 'var(--text-faint)', marginTop: 6, lineHeight: 1.5 }}>
            需接入 AI 模型后，此处将展示各 AI 策略的实盘贡献数据
          </div>
        </div>

        {/* AI 帮你避开的坑 — requires LLM integration */}
        <div className="panel" style={{ padding: '14px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Icon name="risk" size={11} style={{ color: 'var(--warn)' }}/>
            <span style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>今日避免的损失</span>
            <span className="pill" style={{ fontSize: 9, color: 'var(--warn)' }}>未接入</span>
          </div>
          <div style={{ fontSize: 16, color: 'var(--text-faint)', fontWeight: 600, letterSpacing: '-0.01em', marginTop: 2 }}>
            —
          </div>
          <div style={{ fontSize: 10.5, color: 'var(--text-faint)', marginTop: 6, lineHeight: 1.5 }}>
            需接入 AI 风控模型后，此处将展示 AI 拦截的危险交易
          </div>
        </div>

        {/* 下一步建议 — requires LLM integration */}
        <div className="panel" style={{ padding: '14px 16px', background: 'var(--bg-1)', border: '1px solid var(--panel-border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Icon name="bolt" size={11} style={{ color: 'var(--brand)' }}/>
            <span style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>下一步建议 · 待你确认</span>
            <span className="pill" style={{ fontSize: 9, color: 'var(--warn)' }}>未接入</span>
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--text-faint)', marginTop: 5, lineHeight: 1.45 }}>
            —
          </div>
          <div style={{ fontSize: 10.5, color: 'var(--text-faint)', marginTop: 2, lineHeight: 1.45 }}>
            需接入 AI 模型后，此处将展示个性化操作建议
          </div>
        </div>
      </div>

      {/* index strip */}
      <div style={{ gridColumn: '1 / span 2', display: 'flex', gap: 10, overflowX: 'auto' }}>
        {indices.length > 0 ? indices.map(i => (
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
        )) : (
          <div className="panel" style={{ padding: '10px 14px', color: 'var(--text-faint)', fontSize: 12 }}>
            {loading ? '加载中...' : '无法获取指数数据，请确认通达信客户端已启动'}
          </div>
        )}
      </div>

      {/* LEFT column: watchlist + chart */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0, minHeight: 0 }}>
        {/* chart */}
        <div className="panel" style={{ flex: '1 1 0', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <div className="panel-head">
            <span className="panel-title">{klineInfo.name} · {klineInfo.code}</span>
            {klineData.length > 0 && (
              <>
                <span className={`pill ${klineData[klineData.length-1].close >= klineData[klineData.length-1].open ? 'up' : 'down'}`}>
                  ¥{fmt(klineData[klineData.length-1].close)}
                </span>
                <span className={`mono ${klineData[klineData.length-1].close >= (klineData.length > 1 ? klineData[klineData.length-2].close : klineData[klineData.length-1].open) ? 'up' : 'down'}`} style={{ fontSize: 11 }}>
                  {(() => {
                    const cur = klineData[klineData.length-1].close;
                    const prev = klineData.length > 1 ? klineData[klineData.length-2].close : klineData[klineData.length-1].open;
                    const diff = cur - prev;
                    const p = prev > 0 ? (diff / prev * 100) : 0;
                    return (diff >= 0 ? '+' : '') + fmt(diff) + ' ' + (p >= 0 ? '+' : '') + p.toFixed(2) + '%';
                  })()}
                </span>
              </>
            )}
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
            <CandleChart data={klineData}/>
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
                {watchlist.length > 0 ? watchlist.map(s => (
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
                )) : (
                  <tr><td colSpan={7} style={{ padding: 24, textAlign: 'center', color: 'var(--text-faint)', fontSize: 12 }}>
                    {loading ? '加载中...' : '无法加载自选股数据'}
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* RIGHT column: account + strategy perf + signals */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0 }}>
        {/* account */}
        <div className="panel" style={{ padding: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>账户净值</span>
            {hasAccount ? (
              <span className="pill up"><Icon name="arrowUp" size={9}/> 实盘</span>
            ) : (
              <span className="pill" style={{ color: 'var(--text-faint)' }}>未连接</span>
            )}
          </div>
          <div className="num" style={{ fontSize: 28, fontWeight: 600, color: hasAccount ? 'var(--text-hi)' : 'var(--text-faint)', marginTop: 6, letterSpacing: '-0.02em' }}>
            {hasAccount ? '¥' + totalAsset.toLocaleString() : '—'}
          </div>
          {hasAccount ? (
            <>
              <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 11 }}>
                <span><span style={{ color: 'var(--text-faint)' }}>今日 </span><span className={`${todayPnl >= 0 ? 'up' : 'down'} mono`}>{todayPnl >= 0 ? '+' : ''}¥{todayPnl.toLocaleString()}</span></span>
              </div>
              <div style={{ marginTop: 10 }}>
                <Sparkline data={genSpark(42, 80, 0.4, 0.6)} color="var(--brand)" width={332} height={48}/>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--panel-border-soft)' }}>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>可用资金</div>
                  <div className="num" style={{ fontSize: 13, color: 'var(--text-hi)', marginTop: 2 }}>¥{availableCash.toLocaleString()}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>持仓市值</div>
                  <div className="num" style={{ fontSize: 13, color: 'var(--text-hi)', marginTop: 2 }}>¥{marketValue.toLocaleString()}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>仓位</div>
                  <div className="num" style={{ fontSize: 13, color: 'var(--brand)', marginTop: 2 }}>{positionPct}%</div>
                </div>
              </div>
            </>
          ) : (
            <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 10, lineHeight: 1.5 }}>
              请在通达信客户端登录交易账户
            </div>
          )}
        </div>

        {/* strategy perf (mock) */}
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

// --- Candle chart — accepts real kline data ---
function CandleChart({ data }) {
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

    if (!data || data.length === 0) {
      ctx.fillStyle = 'oklch(0.14 0.010 260)';
      ctx.fillRect(0, 0, size.w, size.h);
      ctx.fillStyle = 'oklch(0.52 0.012 260)';
      ctx.font = '13px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('加载K线数据中...', size.w / 2, size.h / 2);
      return;
    }

    const bars = data;
    const N = bars.length;

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
      ctx.beginPath();
      ctx.lineWidth = 1;
      ctx.moveTo(x, yOf(b.high));
      ctx.lineTo(x, yOf(b.low));
      ctx.stroke();
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
    ctx.strokeStyle = (cur >= bars[N - 1].open ? 'oklch(0.70 0.24 25 / 0.5)' : 'oklch(0.78 0.22 148 / 0.5)');
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(padL, yOf(cur));
    ctx.lineTo(W - padR, yOf(cur));
    ctx.stroke();
    ctx.setLineDash([]);
    // price tag
    ctx.fillStyle = cur >= bars[N - 1].open ? 'oklch(0.70 0.24 25)' : 'oklch(0.78 0.22 148)';
    ctx.fillRect(W - padR, yOf(cur) - 9, padR - 2, 18);
    ctx.fillStyle = 'white';
    ctx.font = '10.5px JetBrains Mono, monospace';
    ctx.textAlign = 'center';
    ctx.fillText(cur.toFixed(2), W - padR / 2 - 1, yOf(cur));

    // x-axis dates
    ctx.fillStyle = 'oklch(0.52 0.012 260)';
    ctx.textAlign = 'center';
    ctx.font = '9.5px JetBrains Mono, monospace';
    const dateLabels = [];
    const step = Math.max(1, Math.floor(N / 5));
    for (let i = 0; i < N; i += step) {
      const d = bars[i].date || '';
      dateLabels.push({ label: d.substring(5) || '—', idx: i });
    }
    if (dateLabels.length > 0) {
      dateLabels[dateLabels.length - 1] = { label: '今日', idx: N - 1 };
    }
    dateLabels.forEach(dl => {
      const x = padL + dl.idx * barW + barW / 2;
      ctx.fillText(dl.label, x, size.h - padB + volH + 28);
    });

    // crosshair hint badge top-left
    const last = bars[N - 1];
    const prev = N > 1 ? bars[N - 2] : last;
    const diffPct = prev.close > 0 ? ((last.close - prev.close) / prev.close * 100).toFixed(2) : '0.00';
    ctx.fillStyle = 'oklch(0.88 0.008 260)';
    ctx.textAlign = 'left';
    ctx.font = '10.5px JetBrains Mono, monospace';
    ctx.fillText(`O ${last.open.toFixed(2)}  H ${last.high.toFixed(2)}  L ${last.low.toFixed(2)}  C ${last.close.toFixed(2)}  ${diffPct >= 0 ? '+' : ''}${diffPct}%`, padL + 4, padT + 10);
  }, [size, data]);

  return <canvas ref={canvasRef} style={{ display: 'block' }}/>;
}

// --- Python API panel: shows pytdx interface calls ---
function PyApiPanel() {
  const endpoints = [
    { fn: 'get_market_data',     desc: 'K线数据',      calls: 4821, rate: 142, ok: 100 },
    { fn: 'get_market_snapshot', desc: '实时行情快照',   calls: 8204, rate: 318, ok: 99.8 },
    { fn: 'get_stock_list',      desc: '证券列表',       calls: 2140, rate: 88,  ok: 100 },
    { fn: 'get_stock_info',      desc: '财务数据',       calls: 612,  rate: 4,   ok: 100 },
    { fn: 'query_stock_positions',desc: '持仓查询',      calls: 204,  rate: 1,   ok: 100 },
    { fn: 'query_stock_asset',   desc: '账户资产',       calls: 1847, rate: 22,  ok: 99.2 },
  ];

  const seedLogs = [
    { t: '14:35:43.218', fn: 'get_market_snapshot',  arg: '("600519.SH","300750.SZ",...)', ms: 8,  ok: true },
    { t: '14:35:43.201', fn: 'get_market_data',      arg: '("000001.SH",period="1d",80)',  ms: 14, ok: true },
    { t: '14:35:43.189', fn: 'get_stock_list',       arg: '(market="5")',                   ms: 11, ok: true },
    { t: '14:35:43.174', fn: 'get_market_snapshot',  arg: '("600036.SH","002594.SZ",...)', ms: 9,  ok: true },
    { t: '14:35:43.152', fn: 'get_market_data',      arg: '("300750.SZ",period="1d",240)', ms: 22, ok: true },
    { t: '14:35:43.131', fn: 'get_stock_info',       arg: '("600519.SH")',                  ms: 34, ok: true },
    { t: '14:35:43.118', fn: 'get_market_snapshot',  arg: '("688981.SH","300059.SZ",...)', ms: 7,  ok: true },
    { t: '14:35:43.094', fn: 'get_market_data',      arg: '("002415.SZ",period="1d",120)', ms: 13, ok: true },
    { t: '14:35:43.076', fn: 'query_stock_asset',    arg: '(account_id=1)',                  ms: 41, ok: true },
    { t: '14:35:43.055', fn: 'get_market_snapshot',  arg: '("600519.SH",...)',              ms: 6,  ok: true },
  ];
  const [logs, setLogs] = React.useState(seedLogs);

  React.useEffect(() => {
    const quickFns = [
      ['get_market_snapshot', () => `("${pickCode()}","${pickCode()}",...)`, [6, 14]],
      ['get_market_data',    () => `("${pickCode()}",period="1d",120)`, [10, 28]],
      ['get_stock_list',     () => `(market="5")`, [9, 18]],
      ['get_market_snapshot', () => `("${pickCode()}",...)`, [5, 11]],
    ];
    const pickCode = () => ['600519.SH','300750.SZ','000858.SZ','002594.SZ','601899.SH','600036.SH','688981.SH','300059.SZ','002415.SZ'][Math.floor(Math.random()*9)];
    const id = setInterval(() => {
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
        <span className="panel-title">数据接口 · 通达信 Python SDK</span>
        <span className="pill up"><span className="live-dot"/> 已连接</span>
        <span style={{ flex: 1 }}/>
        <span className="mono" style={{ fontSize: 10, color: 'var(--text-ghost)' }}>tqcenter 1.0.6</span>
      </div>

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
          <span className="mono" style={{ fontSize: 9, color: 'var(--text-ghost)' }}>stdout › tdx_service.py</span>
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
