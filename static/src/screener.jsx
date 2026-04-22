// Screener — 选股器
function Screener() {
  const [factors, setFactors] = useState([
    { id: 'pe', name: '市盈率 PE-TTM', op: '<', val: 25, enabled: true, cat: '估值' },
    { id: 'pb', name: '市净率 PB', op: '<', val: 3.0, enabled: true, cat: '估值' },
    { id: 'roe', name: 'ROE (近4季)', op: '>', val: 15, enabled: true, cat: '财务' },
    { id: 'mktcap', name: '总市值 (亿)', op: '>', val: 100, enabled: true, cat: '规模' },
    { id: 'rev_g', name: '营收增速 YoY', op: '>', val: 20, enabled: true, cat: '成长' },
    { id: 'vol5', name: '5日均量', op: '>', val: 5000, enabled: false, cat: '量价' },
    { id: 'ma_cross', name: 'MA5上穿MA20', op: '=', val: 1, enabled: true, cat: '技术' },
    { id: 'rsi', name: 'RSI(14)', op: '<', val: 70, enabled: false, cat: '技术' },
  ]);
  const [sort, setSort] = useState('score');
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(false);

  // Load stock list on mount
  useEffect(() => {
    async function loadStocks() {
      setLoading(true);
      try {
        const codes = await BYT.getStockList('5');
        if (!codes || codes.length === 0) { setLoading(false); return; }
        const sampleCodes = codes.slice(0, 50);
        const snapshots = await BYT.getSnapshots(sampleCodes);
        const stockData = snapshots.map(s => ({
          code: s.code.replace(/\.(SH|SZ|BJ)/, ''),
          name: s.name || s.code,
          price: s.price,
          pct: s.pct,
          pe: null, pb: null, roe: null, mc: null, rev: null, score: null,
        }));
        setStocks(stockData);
      } catch (e) {
        console.error('Screener load error:', e);
      }
      setLoading(false);
    }
    loadStocks();
  }, []);

  const enabledN = factors.filter(f => f.enabled).length;
  const resultCount = stocks.length;

  const catColor = {
    '估值': 'var(--info)', '财务': 'var(--brand)', '规模': 'var(--text-dim)',
    '成长': 'var(--purple)', '量价': 'var(--up)', '技术': 'var(--down)'
  };

  const toggle = (id) => setFactors(fs => fs.map(f => f.id === id ? { ...f, enabled: !f.enabled } : f));
  const updateVal = (id, val) => setFactors(fs => fs.map(f => f.id === id ? { ...f, val } : f));
  const updateOp = (id, op) => setFactors(fs => fs.map(f => f.id === id ? { ...f, op } : f));

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '320px minmax(0,1fr) 280px',
      gap: 12, padding: 12, height: '100%', overflow: 'hidden'
    }}>
      {/* LEFT: factors */}
      <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <div className="panel-head">
          <span className="panel-title">因子筛选条件</span>
          <span className="pill brand">{enabledN} 启用</span>
          <span style={{ flex: 1 }}/>
          <button className="btn ghost" style={{ padding: '2px 6px', fontSize: 11 }}>
            <Icon name="plus" size={11}/>
          </button>
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: '4px 0' }}>
          {['估值', '财务', '成长', '规模', '量价', '技术'].map(cat => {
            const items = factors.filter(f => f.cat === cat);
            return (
              <div key={cat}>
                <div style={{
                  padding: '8px 12px 4px', fontSize: 10, color: 'var(--text-faint)',
                  letterSpacing: '0.12em', textTransform: 'uppercase',
                  display: 'flex', alignItems: 'center', gap: 6
                }}>
                  <span style={{ width: 6, height: 6, borderRadius: 1, background: catColor[cat] }}/>
                  {cat}
                </div>
                {items.map(f => (
                  <div key={f.id} style={{
                    padding: '7px 12px', display: 'flex', alignItems: 'center', gap: 8,
                    opacity: f.enabled ? 1 : 0.45,
                    borderBottom: '1px solid var(--panel-border-soft)'
                  }}>
                    <input type="checkbox" checked={f.enabled} onChange={() => toggle(f.id)}
                      style={{ accentColor: 'var(--brand)' }}/>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 11.5, color: 'var(--text)' }}>{f.name}</div>
                      <div style={{ display: 'flex', gap: 3, marginTop: 4, alignItems: 'center' }}>
                        {['<', '>', '='].map(op => (
                          <span key={op} onClick={() => updateOp(f.id, op)}
                            style={{
                              padding: '1px 6px', fontSize: 10,
                              background: f.op === op ? 'var(--bg-3)' : 'transparent',
                              color: f.op === op ? 'var(--text-hi)' : 'var(--text-faint)',
                              border: '1px solid ' + (f.op === op ? 'var(--panel-border)' : 'transparent'),
                              borderRadius: 3, cursor: 'pointer', fontFamily: 'var(--f-mono)'
                            }}>{op}</span>
                        ))}
                        <input type="number" value={f.val}
                          onChange={e => updateVal(f.id, Number(e.target.value))}
                          style={{
                            flex: 1, marginLeft: 4,
                            background: 'var(--bg-2)',
                            border: '1px solid var(--panel-border-soft)',
                            color: 'var(--text-hi)',
                            borderRadius: 3, padding: '2px 6px',
                            fontFamily: 'var(--f-mono)', fontSize: 11,
                            outline: 'none', width: 0
                          }}/>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>

        <div style={{ padding: 10, borderTop: '1px solid var(--panel-border-soft)', display: 'flex', gap: 6 }}>
          <button className="btn ghost" style={{ flex: 1 }}><Icon name="save" size={12}/> 保存方案</button>
          <button className="btn ghost" style={{ flex: 1 }}><Icon name="folder" size={12}/> 载入</button>
        </div>
      </div>

      {/* CENTER: results */}
      <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <div className="panel-head">
          <span className="panel-title">筛选结果</span>
          <span className="mono" style={{ fontSize: 16, color: 'var(--brand)', fontWeight: 600, letterSpacing: '-0.01em' }}>
            {loading ? '...' : resultCount.toLocaleString()}
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>只股票{loading ? '加载中' : '符合条件'}</span>
          <span style={{ flex: 1 }}/>
          <span style={{ fontSize: 10.5, color: 'var(--text-faint)' }}>排序</span>
          {[['score', '综合评分'], ['pct', '涨幅'], ['mc', '市值']].map(([k, l]) => (
            <span key={k} onClick={() => setSort(k)} style={{
              padding: '2px 7px', fontSize: 10.5,
              background: sort === k ? 'var(--bg-3)' : 'transparent',
              color: sort === k ? 'var(--text-hi)' : 'var(--text-faint)',
              border: '1px solid ' + (sort === k ? 'var(--panel-border)' : 'transparent'),
              borderRadius: 3, cursor: 'pointer'
            }}>{l}</span>
          ))}
          <button className="btn primary" style={{ padding: '4px 10px' }}>
            <Icon name="backtest" size={12}/> 用此池回测
          </button>
        </div>

        <div style={{ flex: 1, overflow: 'auto' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>#</th>
                <th>代码</th>
                <th>名称</th>
                <th className="num">现价</th>
                <th className="num">涨幅</th>
                <th className="num">PE</th>
                <th className="num">PB</th>
                <th className="num">ROE%</th>
                <th className="num">市值亿</th>
                <th className="num">营收增速</th>
                <th>评分</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={12} style={{ padding: 24, textAlign: 'center', color: 'var(--text-faint)', fontSize: 12 }}>加载中...</td></tr>
              ) : stocks.length > 0 ? stocks.map((s, i) => (
                <tr key={s.code}>
                  <td style={{ color: 'var(--text-ghost)' }}>{i + 1}</td>
                  <td className="mono" style={{ color: 'var(--text-faint)' }}>{s.code}</td>
                  <td style={{ color: 'var(--text-hi)', fontWeight: 500 }}>{s.name}</td>
                  <td className={`num ${s.pct >= 0 ? 'up' : 'down'}`}>{fmt(s.price)}</td>
                  <td className={`num ${s.pct >= 0 ? 'up' : 'down'}`}>{pct(s.pct)}</td>
                  <td className="num" style={{ color: s.pe !== null ? undefined : 'var(--text-ghost)' }}>{s.pe !== null ? s.pe.toFixed(1) : '—'}</td>
                  <td className="num" style={{ color: s.pb !== null ? undefined : 'var(--text-ghost)' }}>{s.pb !== null ? s.pb.toFixed(2) : '—'}</td>
                  <td className="num" style={{ color: s.roe !== null ? undefined : 'var(--text-ghost)' }}>{s.roe !== null ? s.roe.toFixed(1) : '—'}</td>
                  <td className="num" style={{ color: s.mc !== null ? 'var(--text-dim)' : 'var(--text-ghost)' }}>{s.mc !== null ? s.mc.toLocaleString() : '—'}</td>
                  <td className="num" style={{ color: s.rev !== null ? undefined : 'var(--text-ghost)' }}>{s.rev !== null ? '+' + s.rev.toFixed(1) + '%' : '—'}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {s.score !== null ? (
                        <>
                          <div style={{ width: 40, height: 4, background: 'var(--bg-3)', borderRadius: 2, overflow: 'hidden' }}>
                            <div style={{ width: `${s.score}%`, height: '100%', background: 'var(--brand)' }}/>
                          </div>
                          <span className="mono" style={{ fontSize: 11, color: 'var(--brand)', fontWeight: 600 }}>{s.score}</span>
                        </>
                      ) : <span style={{ color: 'var(--text-ghost)', fontSize: 11 }}>—</span>}
                    </div>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn ghost" style={{ padding: '2px 6px', fontSize: 10 }}><Icon name="plus" size={10}/></button>
                  </td>
                </tr>
              )) : (
                <tr><td colSpan={12} style={{ padding: 24, textAlign: 'center', color: 'var(--text-faint)', fontSize: 12 }}>无法加载股票数据</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* RIGHT: distribution */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0 }}>
        <div className="panel" style={{ padding: 12 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 8 }}>
            行业分布
          </div>
          {[
            { sec: '食品饮料', n: 8, pct: 22 },
            { sec: '银行', n: 6, pct: 18 },
            { sec: '电子', n: 5, pct: 14 },
            { sec: '医药生物', n: 4, pct: 12 },
            { sec: '家用电器', n: 3, pct: 9 },
            { sec: '其他', n: 8, pct: 25 },
          ].map(r => (
            <div key={r.sec} style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 2 }}>
                <span style={{ color: 'var(--text)' }}>{r.sec}</span>
                <span className="mono" style={{ color: 'var(--text-faint)' }}>{r.n} · {r.pct}%</span>
              </div>
              <div style={{ width: '100%', height: 3, background: 'var(--bg-3)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{ width: `${r.pct * 3.5}%`, height: '100%', background: 'var(--brand)', opacity: 0.8 }}/>
              </div>
            </div>
          ))}
        </div>

        <div className="panel" style={{ padding: 12 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}>
            市值分布 (亿)
          </div>
          <svg viewBox="0 0 240 80" style={{ width: '100%', height: 80 }}>
            {[15, 28, 48, 62, 45, 32, 20, 12, 8, 5].map((h, i) => (
              <rect key={i} x={i * 24 + 2} y={80 - h} width={20} height={h}
                fill={i === 3 ? 'var(--brand)' : 'var(--info)'} opacity={i === 3 ? 1 : 0.6}/>
            ))}
            <line x1="0" y1="80" x2="240" y2="80" stroke="var(--panel-border)"/>
          </svg>
          <div className="mono" style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: 'var(--text-ghost)', marginTop: 3 }}>
            <span>50</span><span>500</span><span>5000</span>
          </div>
        </div>

        <div className="panel" style={{ padding: 12 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 8 }}>
            最近保存方案
          </div>
          {[
            ['低估值高ROE', '8个因子', 23],
            ['成长龙头', '6个因子', 47],
            ['MACD金叉反弹', '4个因子', 184],
            ['红利稳健', '5个因子', 62],
          ].map(([n, f, c]) => (
            <div key={n} style={{
              padding: '7px 0', borderBottom: '1px solid var(--panel-border-soft)',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer'
            }}>
              <div>
                <div style={{ color: 'var(--text)', fontSize: 12 }}>{n}</div>
                <div style={{ color: 'var(--text-ghost)', fontSize: 10 }}>{f}</div>
              </div>
              <span className="mono pill">{c}只</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Screener });
