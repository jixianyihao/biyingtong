// Live Trading + Marketplace + Risk
function LiveTrading() {
  const [side, setSide] = useState('buy');
  const [showConfirm, setShowConfirm] = useState(false);
  const [price, setPrice] = useState(null);
  const [qty, setQty] = useState(100);
  const [code, setCode] = useState('600519');
  const [rawPositions, setRawPositions] = useState(null);
  const [rawOrders, setRawOrders] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [orderResult, setOrderResult] = useState(null);
  const [loadingData, setLoadingData] = useState(true);
  const [tradeLoggedIn, setTradeLoggedIn] = useState(null); // null = unknown, true/false

  useEffect(() => {
    async function loadData() {
      try {
        const [statusRes, pos, ord] = await Promise.allSettled([
          BYT.getAccountStatus(),
          BYT.getPositions(),
          BYT.getOrders(),
        ]);
        if (statusRes.status === 'fulfilled') {
          setTradeLoggedIn(statusRes.value.logged_in);
        }
        if (pos.status === 'fulfilled') setRawPositions(pos.value || []);
        if (ord.status === 'fulfilled') setRawOrders(ord.value || []);
      } catch (e) {
        console.error('LiveTrading load error:', e);
      }
      setLoadingData(false);
    }
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!code) return;
    let active = true;
    const fullCode = code.length === 6 ? code + (code.startsWith('6') || code.startsWith('9') ? '.SH' : '.SZ') : code;
    BYT.getSnapshot(fullCode).then(snap => {
      if (active && snap) {
        setSnapshot(snap);
        if (snap.price > 0) setPrice(snap.price);
      }
    }).catch(() => {});
    return () => { active = false; };
  }, [code]);

  // Build depth from snapshot
  const bids = [];
  const asks = [];
  if (snapshot) {
    for (let i = 1; i <= 5; i++) {
      const bp = snapshot['bid' + i] || 0;
      const bv = snapshot['bidVol' + i] || 0;
      const ap = snapshot['ask' + i] || 0;
      const av = snapshot['askVol' + i] || 0;
      if (bp > 0) bids.push({ p: bp, v: bv, cum: (bids.length > 0 ? bids[bids.length-1].cum : 0) + bv });
      if (ap > 0) asks.push({ p: ap, v: av, cum: (asks.length > 0 ? asks[asks.length-1].cum : 0) + av });
    }
  }

  // Map TDX positions to UI format
  const positions = (rawPositions || []).map(p => {
    const pCode = (p.Code || p.StockCode || p.code || '').replace(/\.(SH|SZ|BJ)$/, '');
    const pName = p.Name || p.name || pCode;
    const pQty = parseInt(p.Volume || p.CanUseVolume || p.volume || p.qty || 0);
    const pCost = parseFloat(p.CostPrice || p.BuyAvgPrice || p.cost || p.costPrice || 0);
    const pCur = parseFloat(p.MarketPrice || p.NowPrice || p.cur || p.marketPrice || 0);
    return { code: pCode, name: pName, qty: pQty, cost: pCost, cur: pCur, from: '—' };
  });

  // Map TDX orders to UI format
  const orders = (rawOrders || []).map(o => {
    const oCode = (o.Code || o.StockCode || o.code || '').replace(/\.(SH|SZ|BJ)$/, '');
    const oSide = parseInt(o.OrderType || o.orderType || 0) === 0 ? 'buy' : 'sell';
    const oQty = parseInt(o.OrderVolume || o.orderVolume || o.qty || 0);
    const oPrice = parseFloat(o.OrderPrice || o.orderPrice || o.price || 0);
    const oTime = (o.EntrustTime || o.OrderTime || o.time || '').toString().substring(0, 8);
    const oStatus = parseInt(o.OrderStatus || o.orderStatus || 0);
    let status = 'pending';
    if (oStatus === 6 || oStatus === 56) status = 'filled';
    else if (oStatus === 5 || oStatus === 55) status = 'partial';
    else if (oStatus === 7 || oStatus === 57) status = 'cancelled';
    return { t: oTime, code: oCode, side: oSide, qty: oQty, price: oPrice, status, from: '手动' };
  });

  const stockDisplay = snapshot ? `${snapshot.name || code} · ${code.startsWith('6') || code.startsWith('9') ? code + '.SH' : code + '.SZ'}` : (code || '—');
  const stockPrice = snapshot ? snapshot.price : null;
  const stockPct = snapshot ? snapshot.pct : null;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '320px minmax(0,1fr) 340px',
      gap: 12, padding: 12, height: '100%', overflow: 'hidden' }}>
      {tradeLoggedIn === false && (
        <div style={{ gridColumn: '1 / span 3', padding: '10px 16px',
          background: 'var(--brand-soft)', border: '1px solid var(--brand-border)',
          borderRadius: 6, display: 'flex', alignItems: 'center', gap: 10, fontSize: 12 }}>
          <Icon name="warn" size={14} style={{ color: 'var(--brand)' }}/>
          <span style={{ color: 'var(--text)', fontWeight: 500 }}>交易账户未登录</span>
          <span style={{ color: 'var(--text-dim)' }}>— 请在通达信客户端中按 <span className="mono" style={{ color: 'var(--text-hi)' }}>F12</span> 登录模拟交易账户，登录后可正常下单查询</span>
        </div>
      )}
      {/* LEFT: order entry + depth */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0 }}>
        <div className="panel" style={{ padding: 14 }}>
          <div style={{ display: 'flex', gap: 4, marginBottom: 12 }}>
            {[['buy', '买入'], ['sell', '卖出']].map(([k, l]) => (
              <button key={k} onClick={() => setSide(k)} style={{
                flex: 1, padding: '7px 0', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                background: side === k ? (k === 'buy' ? 'var(--up)' : 'var(--down)') : 'var(--bg-2)',
                color: side === k ? 'white' : 'var(--text-dim)',
                border: '1px solid ' + (side === k ? 'transparent' : 'var(--panel-border)'),
                borderRadius: 4
              }}>{l}</button>
            ))}
          </div>
          <div style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>证券代码</div>
            <input value={code} onChange={e => setCode(e.target.value)} className="mono" style={{
              width: '100%', padding: '7px 10px', background: 'var(--bg-2)', border: '1px solid var(--panel-border)',
              color: 'var(--text-hi)', borderRadius: 4, fontSize: 14, letterSpacing: '0.08em'
            }}/>
            <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 3 }}>
              {stockDisplay}
              {stockPrice !== null ? (
                <> · <span className={`${stockPct >= 0 ? 'up' : 'down'} mono`}>¥{fmt(stockPrice)}</span> <span className={stockPct >= 0 ? 'up' : 'down'}>{pct(stockPct)}</span></>
              ) : ' · 加载中...'}
            </div>
          </div>
          <div style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>委托价格</div>
            <div style={{ display: 'flex', gap: 4 }}>
              <button onClick={() => setPrice(p => +(p - 0.1).toFixed(2))} className="btn" style={{ padding: '4px 10px' }}>−</button>
              <input type="number" value={price === null ? '' : price} onChange={e => setPrice(+e.target.value)} placeholder="—" className="mono" style={{
                flex: 1, padding: '6px 10px', background: 'var(--bg-2)', border: '1px solid var(--panel-border)',
                color: 'var(--text-hi)', borderRadius: 4, textAlign: 'center', fontSize: 14
              }}/>
              <button onClick={() => setPrice(p => +(p + 0.1).toFixed(2))} className="btn" style={{ padding: '4px 10px' }}>+</button>
            </div>
            <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
              {[['市价', snapshot ? snapshot.price : null], ['买一', snapshot ? snapshot.bid1 : null], ['卖一', snapshot ? snapshot.ask1 : null]].map(([l, v]) => (
                <span key={l} onClick={() => v !== null && setPrice(v)} style={{
                  flex: 1, textAlign: 'center', padding: '3px 0', fontSize: 10.5,
                  cursor: v !== null ? 'pointer' : 'default',
                  background: 'var(--bg-3)', color: v !== null ? 'var(--text-faint)' : 'var(--text-ghost)', borderRadius: 3
                }}>{l}{v !== null ? ' ¥' + v.toFixed(2) : ''}</span>
              ))}
            </div>
          </div>
          <div style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>委托数量 (股)</div>
            <input type="number" value={qty} onChange={e => setQty(+e.target.value)} step={100} className="mono" style={{
              width: '100%', padding: '7px 10px', background: 'var(--bg-2)', border: '1px solid var(--panel-border)',
              color: 'var(--text-hi)', borderRadius: 4, fontSize: 14, textAlign: 'right'
            }}/>
            <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
              {['1/4', '1/3', '1/2', '全仓'].map(l => (
                <span key={l} onClick={() => setQty(100 * (l === '1/4' ? 1 : l === '1/3' ? 2 : l === '1/2' ? 3 : 4))} style={{
                  flex: 1, textAlign: 'center', padding: '3px 0', fontSize: 10.5, cursor: 'pointer',
                  background: 'var(--bg-3)', color: 'var(--text-faint)', borderRadius: 3
                }}>{l}</span>
              ))}
            </div>
          </div>
          <div style={{ padding: 10, background: 'var(--bg-2)', borderRadius: 4, marginBottom: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
              <span style={{ color: 'var(--text-faint)' }}>成交金额</span>
              <span className="mono" style={{ color: price ? 'var(--text-hi)' : 'var(--text-faint)' }}>{price ? '¥' + fmt(price * qty) : '—'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
              <span style={{ color: 'var(--text-faint)' }}>手续费 (0.025%)</span>
              <span className="mono" style={{ color: price ? 'var(--text-dim)' : 'var(--text-faint)' }}>{price ? '¥' + fmt(price * qty * 0.00025) : '—'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
              <span style={{ color: 'var(--text-faint)' }}>可用 / 需要</span>
              <span className="mono" style={{ color: 'var(--text-faint)' }}>— / {price ? '¥' + fmt(price * qty) : '—'}</span>
            </div>
          </div>
          <button onClick={() => setShowConfirm(true)} className="btn" style={{
            width: '100%', padding: '9px 0', fontSize: 14, fontWeight: 600,
            background: side === 'buy' ? 'var(--up)' : 'var(--down)', color: 'white', borderColor: 'transparent'
          }}>
            <Icon name="zap" size={13}/> {side === 'buy' ? '确认买入' : '确认卖出'}
          </button>
        </div>

        <div className="panel" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <div className="panel-head">
            <span className="panel-title">五档行情</span>
            <span style={{ flex: 1 }}/>
            <span className="mono" style={{ fontSize: 10, color: 'var(--text-faint)' }}>· 刷新 100ms</span>
          </div>
          <div style={{ padding: '4px 0', flex: 1, overflow: 'auto' }}>
            {asks.length > 0 ? asks.slice().reverse().map((o, i) => (
              <DepthRow key={'a'+i} o={o} side="down" level={asks.length - i} maxCum={asks.length > 0 ? asks[asks.length-1].cum : 1}/>
            )) : <div style={{ padding: 12, color: 'var(--text-faint)', fontSize: 11 }}>输入代码加载行情</div>}
            <div style={{ padding: '8px 12px', display: 'flex', justifyContent: 'space-between',
              background: 'var(--bg-2)', borderTop: '1px solid var(--panel-border-soft)', borderBottom: '1px solid var(--panel-border-soft)' }}>
              <span className={`mono ${stockPct !== null ? (stockPct >= 0 ? 'up' : 'down') : ''}`} style={{ fontSize: 16, fontWeight: 600 }}>
                {stockPrice !== null ? fmt(stockPrice) : '—'}
              </span>
              <span className={stockPct !== null ? (stockPct >= 0 ? 'up' : 'down') : ''} style={{ fontSize: 11 }}>
                {stockPct !== null ? (stockPct >= 0 ? '+' : '') + fmt(snapshot?.chg || 0) + ' ' + pct(stockPct) : '—'}
              </span>
            </div>
            {bids.map((o, i) => (
              <DepthRow key={'b'+i} o={o} side="up" level={i + 1} maxCum={bids.length > 0 ? bids[bids.length-1].cum : 1}/>
            ))}
          </div>
        </div>
      </div>

      {/* CENTER: positions */}
      <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <div className="panel-head">
          <span className="panel-title">持仓</span>
          <span className="pill">{positions.length}</span>
          <span style={{ flex: 1 }}/>
          <span className="mono" style={{ fontSize: 11, color: 'var(--text-faint)' }}>市值 </span>
          <span className="mono" style={{ fontSize: 12, color: positions.length > 0 ? 'var(--text-hi)' : 'var(--text-faint)', fontWeight: 600 }}>
            {positions.length > 0 ? '¥' + positions.reduce((s, p) => s + p.cur * p.qty, 0).toLocaleString() : '—'}
          </span>
        </div>
        <div style={{ flex: 1, overflow: 'auto' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>代码</th><th>名称</th>
                <th className="num">持仓</th><th className="num">成本</th><th className="num">现价</th>
                <th className="num">盈亏</th><th className="num">盈亏%</th>
                <th>来源</th><th></th>
              </tr>
            </thead>
            <tbody>
              {loadingData ? (
                <tr><td colSpan={9} style={{ padding: 24, textAlign: 'center', color: 'var(--text-faint)', fontSize: 12 }}>加载中...</td></tr>
              ) : positions.length > 0 ? positions.map(p => {
                const pl = (p.cur - p.cost) * p.qty;
                const plPct = (p.cur - p.cost) / p.cost * 100;
                return (
                  <tr key={p.code}>
                    <td className="mono" style={{ color: 'var(--text-faint)' }}>{p.code}</td>
                    <td style={{ color: 'var(--text-hi)', fontWeight: 500 }}>{p.name}</td>
                    <td className="num">{p.qty.toLocaleString()}</td>
                    <td className="num">{fmt(p.cost)}</td>
                    <td className={`num ${p.cur >= p.cost ? 'up' : 'down'}`}>{fmt(p.cur)}</td>
                    <td className={`num ${pl >= 0 ? 'up' : 'down'}`}>{pl >= 0 ? '+' : ''}¥{fmt(pl, 0)}</td>
                    <td className={`num ${pl >= 0 ? 'up' : 'down'}`}>{pct(plPct)}</td>
                    <td>
                      <span className={`pill ${p.from.startsWith('AI') ? 'brand' : ''}`} style={{ fontSize: 10 }}>
                        {p.from.startsWith('AI') && <Icon name="sparkle" size={9}/>}
                        {p.from}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <button className="btn" style={{ padding: '2px 6px', fontSize: 10, marginRight: 3 }}>加仓</button>
                      <button className="btn down" style={{ padding: '2px 6px', fontSize: 10 }}>平仓</button>
                    </td>
                  </tr>
                );
              }) : (
                <tr><td colSpan={9} style={{ padding: 24, textAlign: 'center', color: 'var(--text-faint)', fontSize: 12 }}>暂无持仓</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* RIGHT: orders + risk */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0 }}>
        <div className="panel" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <div className="panel-head">
            <span className="panel-title">今日委托</span>
            <span className="pill">{orders.length}</span>
            <span style={{ flex: 1 }}/>
            <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>仅显示今日</span>
          </div>
          <div style={{ flex: 1, overflow: 'auto' }}>
            {loadingData ? (
              <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-faint)', fontSize: 12 }}>加载中...</div>
            ) : orders.length > 0 ? orders.map((o, i) => {
              const statMap = {
                filled: ['已成交', 'var(--up)'],
                partial: ['部分成交', 'var(--warn)'],
                cancelled: ['已撤单', 'var(--text-faint)'],
                pending: ['待成交', 'var(--info)'],
              };
              const [sl, sc] = statMap[o.status];
              return (
                <div key={i} style={{ padding: '8px 12px', borderBottom: '1px solid var(--panel-border-soft)' }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                    <span className={`pill ${o.side === 'buy' ? 'up' : 'down'}`} style={{ fontSize: 9 }}>{o.side === 'buy' ? '买' : '卖'}</span>
                    <span className="mono" style={{ color: 'var(--text-hi)', fontSize: 11 }}>{o.code}</span>
                    <span style={{ flex: 1 }}/>
                    <span className="mono" style={{ fontSize: 10, color: sc }}>{sl}</span>
                  </div>
                  <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-dim)', marginTop: 3 }}>
                    {o.qty}股 × ¥{fmt(o.price)} {o.status === 'partial' && ` (成交${o.filled}/${o.qty})`}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3 }}>
                    <span className="mono" style={{ fontSize: 9.5, color: 'var(--text-ghost)' }}>{o.t}</span>
                    <span className={`pill ${o.from.startsWith('AI') ? 'brand' : ''}`} style={{ fontSize: 9 }}>{o.from}</span>
                  </div>
                </div>
              );
            }) : (
              <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-faint)', fontSize: 12 }}>今日暂无委托</div>
            )}
          </div>
        </div>

        <div className="panel" style={{ padding: 12 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 8 }}>
            风险指标
          </div>
          {positions.length > 0 ? [
            ['仓位率', 76, 90, 'up'],
            ['单股集中度', 32, 40, 'warn'],
            ['行业集中度', 48, 50, 'warn'],
            ['Beta', 0.84, 1.2, 'up'],
            ['VaR (95%)', -2.1, -3.5, 'up'],
          ].map(([n, v, max, c]) => (
            <div key={n} style={{ marginBottom: 7 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 2 }}>
                <span style={{ color: 'var(--text)' }}>{n}</span>
                <span className="mono" style={{ color: c === 'warn' ? 'var(--warn)' : 'var(--up)', fontWeight: 600 }}>
                  {typeof v === 'number' && v > 2 ? v + '%' : v}
                </span>
              </div>
              <div style={{ height: 3, background: 'var(--bg-3)', borderRadius: 2 }}>
                <div style={{ width: Math.abs(v)/Math.abs(max)*100 + '%', height: '100%', background: c === 'warn' ? 'var(--warn)' : 'var(--up)', borderRadius: 2 }}/>
              </div>
            </div>
          )) : (
            <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-faint)', fontSize: 11 }}>
              {loadingData ? '加载中...' : '暂无持仓数据'}
            </div>
          )}
        </div>
      </div>

      {showConfirm && <OrderConfirm code={code} price={price} qty={qty} side={side} onClose={() => setShowConfirm(false)}/>}
    </div>
  );
}

function DepthRow({ o, side, level, maxCum }) {
  const clr = side === 'up' ? 'var(--up)' : 'var(--down)';
  const bgPct = (o.cum / maxCum) * 100;
  return (
    <div style={{
      display: 'flex', alignItems: 'center', padding: '4px 12px', fontSize: 11,
      position: 'relative', fontFamily: 'var(--f-mono)'
    }}>
      <div style={{
        position: 'absolute',
        right: side === 'up' ? 'auto' : 0,
        left: side === 'up' ? 0 : 'auto',
        top: 0, bottom: 0, width: bgPct + '%',
        background: side === 'up' ? 'var(--up-bg)' : 'var(--down-bg)',
        opacity: 0.5
      }}/>
      <span style={{ position: 'relative', width: 30, color: 'var(--text-faint)', fontSize: 10 }}>{side === 'up' ? '买' : '卖'}{level}</span>
      <span style={{ position: 'relative', flex: 1, color: clr, fontWeight: 500 }}>{o.p.toFixed(2)}</span>
      <span style={{ position: 'relative', color: 'var(--text-dim)' }}>{o.v}</span>
    </div>
  );
}

function OrderConfirm({ code, price, qty, side, onClose }) {
  const [stage, setStage] = useState('confirm'); // confirm | sending | done | error
  const [result, setResult] = useState(null);
  const handle = async () => {
    setStage('sending');
    try {
      const fullCode = code.includes('.') ? code : code + (code.startsWith('6') || code.startsWith('9') ? '.SH' : '.SZ');
      const res = await BYT.placeOrder({
        stock_code: fullCode,
        side: side,
        qty: qty,
        price: price,
        price_type: 0,
      });
      if (res.error) {
        setResult(res.error);
        setStage('error');
      } else {
        setResult(res);
        setStage('done');
      }
    } catch (e) {
      setResult(e.message);
      setStage('error');
    }
  };
  return (
    <div onClick={onClose} style={{
      position: 'absolute', inset: 0, background: 'oklch(0 0 0 / 0.6)', zIndex: 100,
      display: 'flex', alignItems: 'center', justifyContent: 'center'
    }}>
      <div onClick={e => e.stopPropagation()} className="panel" style={{
        width: 380, boxShadow: '0 12px 40px oklch(0 0 0 / 0.6)'
      }}>
        <div className="panel-head">
          <span className={`pill ${side === 'buy' ? 'up' : 'down'}`}>{side === 'buy' ? '买入确认' : '卖出确认'}</span>
          <span style={{ flex: 1 }}/>
          <button className="btn ghost" onClick={onClose} style={{ padding: '2px 6px' }}><Icon name="close" size={12}/></button>
        </div>
        {stage === 'confirm' && (
          <>
            <div style={{ padding: 20 }}>
              <div style={{ textAlign: 'center' }}>
                <div className="serif" style={{ fontSize: 18, color: 'var(--text-hi)' }}>{code}</div>
                <div className="mono" style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 2 }}>{code.includes('.') ? code : code + '.SH'}</div>
              </div>
              <div style={{ marginTop: 18, padding: '14px 16px', background: 'var(--bg-2)', borderRadius: 4 }}>
                {[['方向', side === 'buy' ? '买入' : '卖出'], ['委托价', '¥' + fmt(price)], ['数量', qty.toLocaleString() + ' 股'],
                  ['成交金额', '¥' + fmt(price * qty)], ['预计手续费', '¥' + fmt(price * qty * 0.00025)]].map(([k, v]) => (
                  <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 12 }}>
                    <span style={{ color: 'var(--text-faint)' }}>{k}</span>
                    <span className="mono" style={{ color: 'var(--text-hi)' }}>{v}</span>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 14, padding: 10, background: 'var(--brand-soft)', border: '1px solid var(--brand-border)', borderRadius: 4, fontSize: 11, color: 'var(--text)', lineHeight: 1.5 }}>
                <Icon name="sparkle" size={11} style={{ color: 'var(--brand)' }}/> <span style={{ color: 'var(--brand)' }}>AI 风控提示</span>：此笔交易后仓位将达 82%，超过预设阈值 80%，建议减少数量至 80 股。
              </div>
            </div>
            <div style={{ padding: 12, borderTop: '1px solid var(--panel-border-soft)', display: 'flex', gap: 8 }}>
              <button onClick={onClose} className="btn ghost" style={{ flex: 1 }}>取消</button>
              <button onClick={handle} className="btn" style={{
                flex: 1.5, background: side === 'buy' ? 'var(--up)' : 'var(--down)',
                color: 'white', borderColor: 'transparent', fontWeight: 600
              }}>确认{side === 'buy' ? '买入' : '卖出'}</button>
            </div>
          </>
        )}
        {stage === 'sending' && (
          <div style={{ padding: 44, textAlign: 'center' }}>
            <div style={{ width: 44, height: 44, borderRadius: '50%', border: '3px solid var(--panel-border)',
              borderTopColor: 'var(--brand)', margin: '0 auto',
              animation: 'spin 0.8s linear infinite' }}/>
            <style>{'@keyframes spin { to { transform: rotate(360deg) } }'}</style>
            <div style={{ color: 'var(--text-dim)', marginTop: 14, fontSize: 12 }}>正在提交委托…</div>
          </div>
        )}
        {stage === 'done' && (
          <div style={{ padding: 44, textAlign: 'center' }}>
            <div style={{
              width: 44, height: 44, borderRadius: '50%', background: 'var(--up-bg)', border: '1px solid var(--up)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto',
              color: 'var(--up)'
            }}><Icon name="check" size={22}/></div>
            <div className="serif" style={{ color: 'var(--text-hi)', marginTop: 14, fontSize: 16 }}>委托提交成功</div>
            <button onClick={onClose} className="btn primary" style={{ marginTop: 18 }}>好的</button>
          </div>
        )}
        {stage === 'error' && (
          <div style={{ padding: 44, textAlign: 'center' }}>
            <div style={{
              width: 44, height: 44, borderRadius: '50%', background: 'var(--down-bg)', border: '1px solid var(--down)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto',
              color: 'var(--down)'
            }}>✕</div>
            <div className="serif" style={{ color: 'var(--text-hi)', marginTop: 14, fontSize: 16 }}>委托失败</div>
            <div className="mono" style={{ color: 'var(--down)', marginTop: 4, fontSize: 11 }}>{result || '未知错误'}</div>
            <button onClick={onClose} className="btn primary" style={{ marginTop: 18 }}>关闭</button>
          </div>
        )}
      </div>
    </div>
  );
}

// --- Strategy Marketplace ---
function Marketplace() {
  const strats = [
    { name: 'AI-林园价值投资', author: '量化老炮', type: 'LLM', ret: 32.4, sub: 12847, price: '¥299/月', stars: 4.9, tag: 'brand' },
    { name: '茅台趋势跟踪', author: '白酒大师', type: '技术', ret: 48.2, sub: 8421, price: '免费', stars: 4.7, tag: '' },
    { name: 'AI-段永平本分投资', author: 'Claude工作室', type: 'LLM', ret: 24.8, sub: 5842, price: '¥199/月', stars: 4.8, tag: 'brand' },
    { name: '中证500网格套利', author: '套利专家', type: '套利', ret: 18.2, sub: 12084, price: '¥99/月', stars: 4.6, tag: '' },
    { name: '低PEG成长股', author: '巴菲特门徒', type: '基本面', ret: 28.7, sub: 6482, price: '免费', stars: 4.5, tag: '' },
    { name: 'AI-浮游短线游资', author: '打板之神', type: 'LLM', ret: 58.7, sub: 3842, price: '¥499/月', stars: 4.4, tag: 'brand' },
    { name: 'RSI极端背离反转', author: '技术派', type: '技术', ret: 22.4, sub: 4821, price: '¥49/月', stars: 4.3, tag: '' },
    { name: 'AI-索罗斯反身性', author: '宏观对冲', type: 'LLM', ret: 41.2, sub: 2841, price: '¥799/月', stars: 4.6, tag: 'brand' },
    { name: '红利低波高股息', author: '稳健派', type: '基本面', ret: 14.2, sub: 18942, price: '免费', stars: 4.8, tag: '' },
  ];

  return (
    <div style={{ padding: 12, height: '100%', overflow: 'auto' }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }}>
        {['全部', '🔥 LLM Agent', '技术指标', '因子选股', '套利', '免费'].map((t, i) => (
          <span key={t} style={{
            padding: '5px 12px', fontSize: 11.5, cursor: 'pointer',
            background: i === 0 ? 'var(--bg-3)' : 'transparent',
            color: i === 0 ? 'var(--text-hi)' : 'var(--text-faint)',
            border: '1px solid ' + (i === 0 ? 'var(--panel-border)' : 'var(--panel-border-soft)'),
            borderRadius: 999
          }}>{t}</span>
        ))}
        <span style={{ flex: 1 }}/>
        <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>热度排序</span>
      </div>

      {/* Hero: featured LLM Agent */}
      <div className="panel" style={{ padding: 20, marginBottom: 12, background:
        'linear-gradient(135deg, oklch(0.20 0.04 75) 0%, oklch(0.15 0.01 260) 55%)',
        border: '1px solid var(--brand-border)', position: 'relative', overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 20 }}>
          <div style={{ flex: 1 }}>
            <span className="pill brand"><Icon name="sparkle" size={10}/> NEW · 本周力荐</span>
            <div className="serif" style={{ fontSize: 28, color: 'var(--text-hi)', fontWeight: 600, letterSpacing: '-0.01em', marginTop: 10, lineHeight: 1.2 }}>
              让 5 位传奇操盘手<br/>同时为你操盘
            </div>
            <div style={{ color: 'var(--text-dim)', marginTop: 8, fontSize: 13, maxWidth: 520, lineHeight: 1.6 }}>
              林园、段永平、索罗斯、巴菲特、西蒙斯……大模型 Agent 实时模仿，5个风格并行回测，择优部署实盘。
            </div>
            <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
              <button className="btn primary" style={{ padding: '7px 16px', fontSize: 13 }}>立即体验</button>
              <button className="btn ghost" style={{ padding: '7px 16px', fontSize: 13 }}>查看样本回测 →</button>
            </div>
          </div>
          <div style={{ width: 200, height: 100, display: 'flex', alignItems: 'center', justifyContent: 'center',
            position: 'relative' }}>
            <Sparkline data={genSpark(99, 60, 0.6, 1.1)} color="oklch(0.82 0.18 75)" width={200} height={100} strokeWidth={2}/>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 10 }}>
        {strats.map(s => (
          <div key={s.name} className="panel" style={{ padding: 14, cursor: 'pointer', transition: 'all 0.15s' }}
            onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--brand)'}
            onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--panel-border)'}>
            <div style={{ display: 'flex', alignItems: 'start', gap: 8 }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <span className={`pill ${s.tag === 'brand' ? 'brand' : ''}`} style={{ fontSize: 9 }}>
                    {s.tag === 'brand' && <Icon name="sparkle" size={9}/>}
                    {s.type}
                  </span>
                  <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>★ {s.stars}</span>
                </div>
                <div style={{ color: 'var(--text-hi)', fontSize: 14, fontWeight: 600, marginTop: 5 }}>{s.name}</div>
                <div style={{ color: 'var(--text-ghost)', fontSize: 10.5, marginTop: 2 }}>by {s.author}</div>
              </div>
              <div className={`num ${s.ret >= 0 ? 'up' : 'down'}`} style={{ fontSize: 18, fontWeight: 600, letterSpacing: '-0.01em' }}>
                {pct(s.ret, 1)}
              </div>
            </div>
            <div style={{ marginTop: 10 }}>
              <Sparkline data={genSpark(s.name.length * 13, 40, s.ret / 80, 0.8)} color={s.ret >= 0 ? 'var(--up)' : 'var(--down)'} width={268} height={36}/>
            </div>
            <div style={{ marginTop: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11 }}>
              <span style={{ color: 'var(--text-faint)' }}>订阅 {s.sub.toLocaleString()}</span>
              <span style={{ color: s.price === '免费' ? 'var(--up)' : 'var(--brand)', fontWeight: 600 }}>{s.price}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Agent Safety & Guardrails Center ---
function RiskMonitor() {
  const [emergencyOn, setEmergencyOn] = React.useState(false);
  const [approvalMode, setApprovalMode] = React.useState('auto');

  const agents = [
    { name: '林园风格',   model: 'Claude Opus 4.5', health: 98, mode: '自动', capital: 1000000, used: 76, alerts: 0,  trust: 'A+' },
    { name: '浮游短线',   model: 'GPT-5',           health: 72, mode: '半自动', capital: 500000,  used: 60, alerts: 3, trust: 'B' },
    { name: '巴菲特风格', model: 'Gemini 2.0 Pro',  health: 96, mode: '自动', capital: 1500000, used: 82, alerts: 0, trust: 'A+' },
    { name: '索罗斯反身性', model: 'Claude Sonnet', health: 54, mode: '仅观察', capital: 800000, used: 0, alerts: 7, trust: 'C' },
    { name: '量化中性',   model: 'DeepSeek V4',     health: 99, mode: '自动', capital: 2000000, used: 100, alerts: 0, trust: 'A+' },
  ];

  const guardrails = [
    { cat: '资金防护', items: [
      ['单日最大亏损', '≤ 3%', 'hard', true],
      ['单笔最大仓位', '≤ 15% 总资金', 'hard', true],
      ['单股集中度', '≤ 30%', 'soft', true],
      ['最低现金比例', '≥ 5%', 'hard', true],
      ['资金隔离', '独立子账户 · 不跨池', 'hard', true],
    ]},
    { cat: '交易防护', items: [
      ['日内最大换手', '≤ 300%', 'soft', true],
      ['单笔下单金额', '≤ ¥200,000', 'hard', true],
      ['禁用涨跌停追入', 'strict', 'hard', true],
      ['冷却期', '同票 5min 内仅 1 单', 'soft', true],
      ['黑名单股票', 'ST · *ST · 退市风险', 'hard', true],
    ]},
    { cat: 'Agent 行为', items: [
      ['Prompt 注入检测', '启用 · 过滤可疑输入', 'hard', true],
      ['决策前必填理由', '≥ 80 字 · 含依据', 'soft', true],
      ['工具调用白名单', '仅授权 API 可用', 'hard', true],
      ['模型输出审计', '100% 留痕 · 可追溯', 'hard', true],
      ['异常波动熔断', 'VaR 超 2σ 自动暂停', 'hard', true],
    ]},
  ];

  const auditLog = [
    { t: '14:32:18', agent: '浮游短线', act: 'place_order', tgt: '寒武纪 × 300', status: 'blocked', reason: '单笔金额超限 ¥258,000 > ¥200,000' },
    { t: '14:28:04', agent: '林园风格', act: 'place_order', tgt: '贵州茅台 × 200', status: 'ok', reason: '通过全部 15 项检查' },
    { t: '14:24:55', agent: '索罗斯反身性', act: 'get_news',  tgt: '宏观数据',      status: 'flagged', reason: '检测到可能的 Prompt 注入（新闻标题含"忽略以上指令"）' },
    { t: '14:21:33', agent: '浮游短线', act: 'place_order', tgt: '*ST 凯迪',       status: 'blocked', reason: '股票在黑名单（退市风险）' },
    { t: '14:18:02', agent: '林园风格', act: 'place_order', tgt: '五粮液 × 800',  status: 'ok',      reason: '通过全部 15 项检查' },
    { t: '14:12:47', agent: '量化中性', act: 'place_order', tgt: '多笔委托 × 18',  status: 'ok',      reason: '批量通过' },
    { t: '14:08:21', agent: '浮游短线', act: 'place_order', tgt: '宁德时代 × 500', status: 'needs_approval', reason: '单股集中度将达 32% > 30%，转人工' },
    { t: '13:58:14', agent: '索罗斯反身性', act: 'place_order', tgt: '沪深300 空单', status: 'blocked', reason: 'Agent 健康分过低 (54)，已降级为"仅观察"' },
  ];

  return (
    <div style={{ padding: 12, display: 'grid',
      gridTemplateColumns: '1fr 1fr 1fr', gridTemplateRows: 'auto auto auto 1fr',
      gap: 12, height: '100%', overflow: 'auto' }}>

      {/* ═══ Emergency kill switch ═══ */}
      <div className="panel" style={{ gridColumn: '1 / span 3', padding: 14,
        background: emergencyOn ? 'var(--down-bg)' : 'var(--bg-1)',
        border: '1px solid ' + (emergencyOn ? 'var(--down)' : 'var(--panel-border)'),
        display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{
          width: 44, height: 44, borderRadius: '50%',
          background: emergencyOn ? 'var(--down)' : 'var(--up-bg)',
          border: '2px solid ' + (emergencyOn ? 'var(--down)' : 'var(--up)'),
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: emergencyOn ? 'white' : 'var(--up)',
        }}>
          <Icon name={emergencyOn ? 'warn' : 'check'} size={20}/>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, color: 'var(--text-hi)', fontWeight: 600 }}>
            {emergencyOn ? '🛑 全局熔断已触发 · 所有 Agent 已暂停交易' : '✅ 系统状态正常 · 5 个 Agent 运行中'}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 3 }}>
            {emergencyOn ? '所有 place_order 调用已阻断，仅保留行情读取' : '最近 24h 阻断 14 次可疑调用 · 触发 3 次人工审批'}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>审批模式</span>
          <div style={{ display: 'flex', gap: 2, padding: 2, background: 'var(--bg-2)', borderRadius: 4 }}>
            {[['auto', '全自动'], ['review', '超限审批'], ['manual', '全人工']].map(([k, l]) => (
              <span key={k} onClick={() => setApprovalMode(k)} style={{
                padding: '4px 10px', fontSize: 11, cursor: 'pointer',
                background: approvalMode === k ? 'var(--bg-3)' : 'transparent',
                color: approvalMode === k ? 'var(--text-hi)' : 'var(--text-faint)',
                borderRadius: 3,
              }}>{l}</span>
            ))}
          </div>
        </div>

        <button onClick={() => setEmergencyOn(!emergencyOn)} className="btn" style={{
          background: emergencyOn ? 'var(--bg-3)' : 'var(--down)',
          color: emergencyOn ? 'var(--text-hi)' : 'white',
          borderColor: emergencyOn ? 'var(--panel-border)' : 'transparent',
          padding: '8px 16px', fontWeight: 600,
        }}>
          {emergencyOn ? '解除熔断' : '🛑 一键熔断 · Kill Switch'}
        </button>
      </div>

      {/* ═══ Agent health grid ═══ */}
      <div className="panel" style={{ gridColumn: '1 / span 3' }}>
        <div className="panel-head">
          <span className="panel-title">Agent 健康度 & 信任评级</span>
          <span style={{ flex: 1 }}/>
          <span className="mono" style={{ fontSize: 10, color: 'var(--text-faint)' }}>依据：回测偏差 · 违规次数 · 模型稳定性</span>
        </div>
        <table className="tbl">
          <thead>
            <tr>
              <th>Agent</th><th>模型</th>
              <th className="num">健康分</th><th>运行模式</th>
              <th className="num">授权资金</th><th className="num">使用率</th>
              <th className="num">告警</th><th>信任评级</th><th></th>
            </tr>
          </thead>
          <tbody>
            {agents.map(a => {
              const hColor = a.health >= 90 ? 'var(--up)' : a.health >= 70 ? 'var(--warn)' : 'var(--down)';
              const tColor = a.trust === 'A+' ? 'var(--up)' : a.trust === 'B' ? 'var(--warn)' : 'var(--down)';
              return (
                <tr key={a.name}>
                  <td style={{ color: 'var(--text-hi)', fontWeight: 500 }}><Icon name="sparkle" size={10} style={{ color: 'var(--brand)' }}/> {a.name}</td>
                  <td className="mono" style={{ fontSize: 10, color: 'var(--text-dim)' }}>{a.model}</td>
                  <td className="num" style={{ color: hColor, fontWeight: 600 }}>{a.health}</td>
                  <td>
                    <span className={`pill ${a.mode === '仅观察' ? 'down' : a.mode === '半自动' ? '' : 'up'}`} style={{ fontSize: 10 }}>{a.mode}</span>
                  </td>
                  <td className="num">¥{(a.capital/10000).toFixed(0)}万</td>
                  <td className="num"><span style={{ color: a.used >= 90 ? 'var(--warn)' : 'var(--text-hi)' }}>{a.used}%</span></td>
                  <td className="num">
                    {a.alerts > 0 ? <span className="down" style={{ fontWeight: 600 }}>{a.alerts}</span> : <span style={{ color: 'var(--text-ghost)' }}>0</span>}
                  </td>
                  <td><span className="pill" style={{ fontSize: 11, color: tColor, border: '1px solid ' + tColor, fontWeight: 600 }}>{a.trust}</span></td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn" style={{ padding: '2px 7px', fontSize: 10 }}>调整权限</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* ═══ Three-layer guardrails ═══ */}
      <div className="panel" style={{ gridColumn: '1 / span 3', padding: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <Icon name="risk" size={14} style={{ color: 'var(--brand)' }}/>
          <span style={{ fontSize: 11, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>三层防护规则 · 15 项检查</span>
          <span style={{ flex: 1 }}/>
          <span className="pill up">15/15 已启用</span>
          <button className="btn ghost" style={{ padding: '3px 8px' }}><Icon name="settings" size={11}/> 自定义规则</button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
          {guardrails.map(g => (
            <div key={g.cat} style={{ padding: 12, background: 'var(--bg-2)', border: '1px solid var(--panel-border-soft)', borderRadius: 4 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, paddingBottom: 6, borderBottom: '1px solid var(--panel-border-soft)' }}>
                <div style={{ width: 4, height: 14, background: 'var(--brand)' }}/>
                <span style={{ fontSize: 12, color: 'var(--text-hi)', fontWeight: 600 }}>{g.cat}</span>
              </div>
              {g.items.map(([n, v, kind, on]) => (
                <div key={n} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0', fontSize: 11 }}>
                  <span style={{
                    width: 14, height: 14, borderRadius: 3, flexShrink: 0,
                    background: on ? 'var(--up-bg)' : 'var(--bg-3)',
                    border: '1px solid ' + (on ? 'var(--up)' : 'var(--panel-border)'),
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'var(--up)', fontSize: 9,
                  }}>{on ? '✓' : ''}</span>
                  <span style={{ color: 'var(--text)', flex: 1 }}>{n}</span>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--text-faint)' }}>{v}</span>
                  <span style={{
                    fontSize: 8.5, padding: '1px 4px', borderRadius: 2,
                    color: kind === 'hard' ? 'var(--down)' : 'var(--warn)',
                    border: '1px solid ' + (kind === 'hard' ? 'var(--down)' : 'var(--warn)'),
                    textTransform: 'uppercase', letterSpacing: '0.05em',
                  }}>{kind}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* ═══ Audit log ═══ */}
      <div className="panel" style={{ gridColumn: '1 / span 2', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <div className="panel-head">
          <span className="panel-title">决策审计日志 · 可追溯</span>
          <span className="pill"><span className="live-dot" style={{ color: 'var(--up)' }}/> 实时</span>
          <span style={{ flex: 1 }}/>
          <span style={{ fontSize: 10.5, color: 'var(--text-faint)' }}>100% 留痕 · 不可篡改</span>
        </div>
        <div style={{ overflow: 'auto' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>时间</th><th>Agent</th><th>动作</th><th>目标</th><th>状态</th><th>原因</th>
              </tr>
            </thead>
            <tbody>
              {auditLog.map((l, i) => {
                const sMap = {
                  ok: ['✓ 通过', 'var(--up)'],
                  blocked: ['✕ 已阻断', 'var(--down)'],
                  flagged: ['⚠ 标记', 'var(--warn)'],
                  needs_approval: ['⏸ 待审批', 'var(--info)'],
                };
                const [sl, sc] = sMap[l.status];
                return (
                  <tr key={i}>
                    <td className="mono" style={{ fontSize: 10, color: 'var(--text-ghost)' }}>{l.t}</td>
                    <td><Icon name="sparkle" size={9} style={{ color: 'var(--brand)' }}/> {l.agent}</td>
                    <td className="mono" style={{ fontSize: 10.5, color: 'var(--info)' }}>{l.act}()</td>
                    <td style={{ color: 'var(--text-hi)' }}>{l.tgt}</td>
                    <td><span style={{ color: sc, fontSize: 11, fontWeight: 500 }}>{sl}</span></td>
                    <td style={{ fontSize: 11, color: 'var(--text-dim)' }}>{l.reason}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ═══ Pending approvals + stats ═══ */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0 }}>
        <div className="panel" style={{ padding: 14 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}>24h 防护统计</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            {[
              ['总决策', '847', 'var(--text-hi)'],
              ['自动通过', '798', 'var(--up)'],
              ['已阻断', '14', 'var(--down)'],
              ['人工审批', '3', 'var(--info)'],
              ['注入拦截', '2', 'var(--warn)'],
              ['熔断触发', '0', 'var(--up)'],
            ].map(([k, v, c]) => (
              <div key={k} style={{ padding: '8px 10px', background: 'var(--bg-2)', borderRadius: 3 }}>
                <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>{k}</div>
                <div className="num mono" style={{ fontSize: 18, color: c, fontWeight: 600, marginTop: 2 }}>{v}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="panel" style={{ flex: 1, padding: 14, minHeight: 0, overflow: 'auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>待人工审批</span>
            <span className="pill down">2</span>
          </div>
          {[
            { agent: '浮游短线', act: '买入 宁德时代 × 500', reason: '单股集中度将达 32% > 30% 上限', ago: '2分钟前' },
            { agent: '索罗斯反身性', act: '开空 沪深300 期货 × 10 手', reason: 'Agent 健康分 54 < 70 触发复核', ago: '8分钟前' },
          ].map((p, i) => (
            <div key={i} style={{ padding: 10, background: 'var(--warn-bg, oklch(0.82 0.16 85 / 0.1))', border: '1px solid var(--warn)', borderRadius: 4, marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                <Icon name="sparkle" size={10} style={{ color: 'var(--brand)' }}/>
                <span style={{ fontSize: 12, color: 'var(--text-hi)', fontWeight: 600 }}>{p.agent}</span>
                <span style={{ flex: 1 }}/>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text-ghost)' }}>{p.ago}</span>
              </div>
              <div className="mono" style={{ fontSize: 11, color: 'var(--text)', marginTop: 4 }}>{p.act}</div>
              <div style={{ fontSize: 10.5, color: 'var(--text-faint)', marginTop: 3, lineHeight: 1.4 }}>⚠ {p.reason}</div>
              <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                <button className="btn ghost" style={{ flex: 1, padding: '4px 0', fontSize: 11 }}>拒绝</button>
                <button className="btn primary" style={{ flex: 1, padding: '4px 0', fontSize: 11 }}>批准执行</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { LiveTrading, Marketplace, RiskMonitor });

// --- dead code below (kept as no-op for legacy import, will never execute) ---
const _unused = () => {
  return (
    <div style={{ padding: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, height: '100%', overflow: 'auto' }}>
      <div className="panel" style={{ padding: 16 }}>
        <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8 }}>组合风险仪表</div>
        <div style={{ display: 'flex', justifyContent: 'center', padding: 20 }}>
          <svg width="240" height="140" viewBox="0 0 240 140">
            <path d="M30 130 A 90 90 0 0 1 210 130" stroke="var(--bg-3)" strokeWidth="14" fill="none"/>
            <path d="M30 130 A 90 90 0 0 1 180 58" stroke="var(--up)" strokeWidth="14" fill="none" strokeLinecap="round"/>
            <text x="120" y="100" textAnchor="middle" fontSize="36" fill="var(--text-hi)" fontFamily="JetBrains Mono" fontWeight="600">A-</text>
            <text x="120" y="122" textAnchor="middle" fontSize="11" fill="var(--text-faint)">综合风险评级</text>
          </svg>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginTop: 4 }}>
          {[['夏普比率', '1.84', 'up'], ['最大回撤', '-6.2%', 'down'], ['Beta', '0.84', 'up'],
            ['VaR 95%', '-2.1%', 'up'], ['下行偏差', '8.4%', 'warn'], ['Calmar', '5.23', 'up']].map(([l, v, c]) => (
            <div key={l} style={{ padding: 8, background: 'var(--bg-2)', borderRadius: 4, textAlign: 'center' }}>
              <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>{l}</div>
              <div className={`num ${c}`} style={{ fontSize: 15, fontWeight: 600, marginTop: 2 }}>{v}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="panel" style={{ padding: 16 }}>
        <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 12 }}>持仓行业暴露</div>
        {[['食品饮料', 32], ['金融', 18], ['新能源', 15], ['医药', 12], ['科技', 10], ['有色', 8], ['现金', 5]].map(([n, v]) => (
          <div key={n} style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, marginBottom: 3 }}>
              <span style={{ color: 'var(--text)' }}>{n}</span>
              <span className="mono" style={{ color: v > 25 ? 'var(--warn)' : 'var(--text-hi)' }}>{v}%</span>
            </div>
            <div style={{ height: 6, background: 'var(--bg-3)', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ width: v*2.5 + '%', height: '100%', background: v > 25 ? 'var(--warn)' : 'var(--brand)' }}/>
            </div>
          </div>
        ))}
      </div>

      <div className="panel" style={{ padding: 16, gridColumn: '1 / span 2' }}>
        <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10 }}>风险告警</div>
        {[
          { lvl: 'high', t: '14:28', msg: '贵州茅台 单日回撤 -2.1% 接近止损阈值 -2.5%', rec: '建议部分减仓' },
          { lvl: 'med', t: '13:42', msg: '食品饮料行业暴露 32%，超过预设阈值 30%', rec: '可适度分散至医药/金融' },
          { lvl: 'low', t: '11:08', msg: 'AI-浮游策略 本周胜率降至 44%，低于均值', rec: '观察 3-5 交易日' },
          { lvl: 'low', t: '09:35', msg: '5G相关个股早盘异动，未在任何策略覆盖范围内', rec: '可加入观察池' },
        ].map((a, i) => {
          const colors = { high: 'var(--up)', med: 'var(--warn)', low: 'var(--info)' };
          return (
            <div key={i} style={{
              display: 'flex', gap: 10, padding: '10px 0', alignItems: 'flex-start',
              borderBottom: i < 3 ? '1px solid var(--panel-border-soft)' : 'none'
            }}>
              <span style={{ width: 4, height: 28, background: colors[a.lvl], borderRadius: 2, flexShrink: 0, marginTop: 2 }}/>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                  <span style={{ color: 'var(--text-hi)', fontSize: 12 }}>{a.msg}</span>
                  <span style={{ flex: 1 }}/>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--text-ghost)' }}>{a.t}</span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 2 }}>建议：{a.rec}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
