// Shell: sidebar + topbar + statusbar

function Sidebar({ active, onNav, collapsed, onToggleCollapse }) {
  const items = [
    { id: 'dashboard', icon: 'dashboard', label: '我的盈亏', sub: 'My P&L' },
    { id: 'agent', icon: 'agent', label: '我的 AI 操盘手', sub: 'My Traders', badge: '核心' },
    { id: 'live', icon: 'live', label: '实盘交易', sub: 'Trade' },
    { id: 'risk', icon: 'risk', label: '安全管控', sub: 'Safety' },
    { id: '__sep', label: '研究工具', sub: 'RESEARCH' },
    { id: 'screener', icon: 'filter', label: '选股器', sub: 'Screener' },
    { id: 'editor', icon: 'code', label: '策略研发', sub: 'Strategy' },
    { id: 'backtest', icon: 'backtest', label: '回测', sub: 'Backtest' },
  ];

  return (
    <aside style={{
      width: collapsed ? 56 : 208,
      background: 'var(--bg-1)',
      borderRight: '1px solid var(--panel-border)',
      display: 'flex',
      flexDirection: 'column',
      transition: 'width 0.2s ease',
      flexShrink: 0,
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '14px 14px 12px', borderBottom: '1px solid var(--panel-border-soft)'
      }}>
        <Logo size={24}/>
        {!collapsed && (
          <div style={{ lineHeight: 1.1 }}>
            <div style={{ fontWeight: 700, color: 'var(--text-hi)', letterSpacing: '0.02em' }}>必赢通</div>
            <div style={{ fontSize: 9.5, color: 'var(--text-faint)', letterSpacing: '0.18em', textTransform: 'uppercase', marginTop: 2 }}>BiYingTong · v4.2</div>
          </div>
        )}
      </div>

      <nav style={{ padding: 8, flex: 1, overflowY: 'auto' }}>
        {items.map(it => {
          if (it.id === '__sep') {
            if (collapsed) return <div key="sep" style={{ height: 1, background: 'var(--panel-border-soft)', margin: '10px 8px' }}/>;
            return (
              <div key="sep" style={{ padding: '12px 10px 4px', fontSize: 9.5, color: 'var(--text-ghost)', letterSpacing: '0.16em', textTransform: 'uppercase', borderTop: '1px solid var(--panel-border-soft)', marginTop: 8 }}>
                {it.label}
              </div>
            );
          }
          const isActive = active === it.id;
          return (
            <button key={it.id} onClick={() => onNav(it.id)}
              title={collapsed ? it.label : ''}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: collapsed ? '9px 0' : '9px 10px',
                justifyContent: collapsed ? 'center' : 'flex-start',
                margin: '2px 0',
                background: isActive ? 'var(--bg-3)' : 'transparent',
                border: '1px solid ' + (isActive ? 'var(--panel-border)' : 'transparent'),
                borderRadius: 6,
                color: isActive ? 'var(--text-hi)' : 'var(--text-dim)',
                cursor: 'pointer',
                position: 'relative',
                fontFamily: 'var(--f-ui)',
                fontSize: 12.5,
                textAlign: 'left',
                transition: 'all 0.12s ease',
              }}
              onMouseEnter={e => { if (!isActive) e.currentTarget.style.color = 'var(--text)'; }}
              onMouseLeave={e => { if (!isActive) e.currentTarget.style.color = 'var(--text-dim)'; }}>
              {isActive && <div style={{ position: 'absolute', left: -9, top: 6, bottom: 6, width: 2, background: 'var(--brand)', borderRadius: 2 }}/>}
              <Icon name={it.icon} size={15}/>
              {!collapsed && (
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                  <div>
                    <div style={{ fontWeight: isActive ? 600 : 500 }}>{it.label}</div>
                    <div className="mono" style={{ fontSize: 9.5, color: 'var(--text-ghost)', letterSpacing: '0.08em', textTransform: 'uppercase', marginTop: 1 }}>{it.sub}</div>
                  </div>
                  {it.badge && <span className="pill brand" style={{ fontSize: 8.5, padding: '1px 5px' }}>{it.badge}</span>}
                </div>
              )}
            </button>
          );
        })}
      </nav>

      {!collapsed && (
        <div style={{ padding: 10, borderTop: '1px solid var(--panel-border-soft)' }}>
          <div style={{
            padding: '10px 10px 9px', background: 'var(--bg-2)', borderRadius: 6,
            border: '1px solid var(--panel-border-soft)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
              <span className="live-dot" style={{ color: 'var(--up)' }}/>
              <span style={{ fontSize: 10.5, color: 'var(--text-dim)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>市场状态</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
              <span style={{ color: 'var(--text)' }}>沪深A股</span>
              <span className="mono up">+0.84%</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginTop: 3 }}>
              <span style={{ color: 'var(--text)' }}>收盘倒计时</span>
              <span className="mono" style={{ color: 'var(--text-hi)' }}>01:24:17</span>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}

function TopBar({ active, onTweakOpen }) {
  const [tdxOpen, setTdxOpen] = useState(false);
  const [account, setAccount] = useState(null);
  const titles = {
    dashboard: ['我的盈亏工作台', 'My P&L Dashboard'],
    screener: ['选股器', 'Factor Screener'],
    editor: ['策略研发', 'Strategy Editor'],
    backtest: ['回测引擎', 'Backtest Engine'],
    agent: ['我的 AI 操盘手', 'My AI Traders'],
    live: ['实盘交易', 'Live Trading'],
    risk: ['安全管控', 'Safety & Guardrails'],
  };
  const [t1, t2] = titles[active] || titles.dashboard;

  useEffect(() => {
    function load() {
      BYT.getAsset().then(r => { if (r && !r.error) setAccount(r); }).catch(() => {});
    }
    load();
    var iv = setInterval(load, 15000);
    return function() { clearInterval(iv); };
  }, []);

  var totalAsset = account ? (parseFloat(account.Asset || account.TotalAsset || account.total_asset || 0)) : null;
  var todayPnl = account ? (parseFloat(account.ProfitLoss || account.TodayIncome || account.today_income || account.TodayProfit || 0)) : null;
  var pnlPct = totalAsset > 0 && todayPnl !== null ? (todayPnl / totalAsset * 100) : null;

  return (
    <header style={{
      height: 44,
      background: 'var(--bg-1)',
      borderBottom: '1px solid var(--panel-border)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 14px',
      gap: 14,
      flexShrink: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-hi)' }}>{t1}</div>
        <div className="mono" style={{ fontSize: 10, color: 'var(--text-ghost)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>{t2}</div>
      </div>

      {/* TDX Python API connection badge */}
      <TDXBadge onClick={() => setTdxOpen(true)}/>
      <TDXPanel open={tdxOpen} onClose={() => setTdxOpen(false)}/>

      {/* command search */}
      <div style={{
        flex: 1, maxWidth: 440, marginLeft: 16,
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '5px 10px',
        background: 'var(--bg-2)',
        border: '1px solid var(--panel-border-soft)',
        borderRadius: 5,
        color: 'var(--text-faint)',
      }}>
        <Icon name="search" size={12}/>
        <span style={{ fontSize: 11.5 }}>搜索股票 / 策略 / 因子…</span>
        <span style={{ flex: 1 }}/>
        <span className="kbd">⌘K</span>
      </div>

      <div style={{ flex: 1 }}/>

      {/* account + P/L */}
      <div className="mono" style={{ display: 'flex', gap: 14, alignItems: 'center', fontSize: 11.5 }}>
        {totalAsset !== null ? (
          <>
            <div>
              <span style={{ color: 'var(--text-faint)', fontSize: 10 }}>总资产 </span>
              <span style={{ color: 'var(--text-hi)', fontWeight: 600 }}>¥{totalAsset.toLocaleString()}</span>
            </div>
            <div>
              <span style={{ color: 'var(--text-faint)', fontSize: 10 }}>今日盈亏 </span>
              <span className={todayPnl >= 0 ? 'up' : 'down'} style={{ fontWeight: 600 }}>{todayPnl >= 0 ? '+' : ''}¥{Math.abs(todayPnl).toLocaleString()}</span>
              {pnlPct !== null && <span className={pnlPct >= 0 ? 'up' : 'down'} style={{ marginLeft: 4, fontSize: 10.5 }}>{pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%</span>}
            </div>
          </>
        ) : (
          <div>
            <span style={{ color: 'var(--text-faint)', fontSize: 10 }}>账户未连接</span>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 6 }}>
        <button className="btn ghost" title="通知">
          <Icon name="bell" size={14}/>
          <span style={{
            position: 'relative', top: -6, marginLeft: -8,
            width: 6, height: 6, background: 'var(--up)', borderRadius: '50%'
          }}/>
        </button>
        <button className="btn ghost" onClick={onTweakOpen} title="设置"><Icon name="settings" size={14}/></button>
        <div style={{
          width: 28, height: 28, borderRadius: '50%',
          background: 'linear-gradient(135deg, var(--brand), var(--up))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontWeight: 600, color: 'oklch(0.15 0.02 40)'
        }}>老</div>
      </div>
    </header>
  );
}

function TDXBadge({ onClick }) {
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    BYT.getStatus().then(r => setConnected(r.connected)).catch(() => setConnected(false));
    const iv = setInterval(() => {
      BYT.getStatus().then(r => setConnected(r.connected)).catch(() => setConnected(false));
    }, 15000);
    return () => clearInterval(iv);
  }, []);
  return (
    <div onClick={onClick} title="点击查看通达信接口详情" style={{
      display: 'flex', alignItems: 'center', gap: 7,
      padding: '4px 9px 4px 8px',
      background: 'var(--bg-2)',
      border: '1px solid ' + (connected ? 'var(--up-border)' : 'var(--panel-border)'),
      borderRadius: 4,
      marginLeft: 6,
      cursor: 'pointer',
      transition: 'all 0.15s',
    }}
    onMouseEnter={e => { e.currentTarget.style.borderColor = connected ? 'var(--up)' : 'var(--warn)'; }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = connected ? 'var(--up-border)' : 'var(--panel-border)'; }}>
      <span className="live-dot" style={{ color: connected ? 'var(--up)' : 'var(--text-faint)' }}/>
      <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-hi)', letterSpacing: '0.04em' }}>TDX · tqcenter</span>
      <span style={{ width: 1, height: 10, background: 'var(--panel-border)' }}/>
      <span className="mono" style={{ fontSize: 10, color: connected ? 'var(--up)' : 'var(--text-faint)' }}>{connected ? '已连接' : '未连接'}</span>
    </div>
  );
}

function StatusBar() {
  return (
    <footer style={{
      height: 22,
      background: 'var(--bg-1)',
      borderTop: '1px solid var(--panel-border)',
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      padding: '0 12px',
      fontSize: 10.5,
      color: 'var(--text-faint)',
      fontFamily: 'var(--f-mono)',
      letterSpacing: '0.04em',
      flexShrink: 0,
    }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        <span className="live-dot" style={{ color: 'var(--up)' }}/> tqcenter 1.0.6 · 通达信SDK
      </span>
      <span>本地 Python Flask 服务</span>
      <span style={{ flex: 1 }}/>
      <span>Py · pandas</span>
      <span>127.0.0.1:5000</span>
      <span>{new Date().toLocaleDateString('zh-CN')} {new Date().toLocaleTimeString('zh-CN', {hour:'2-digit',minute:'2-digit'})}</span>
    </footer>
  );
}

Object.assign(window, { Sidebar, TopBar, StatusBar, RedLineBar, RedLineConfigModal, TDXPanel, TDXBadge });

// ═════════════════════════════════════════════════════════════════════════
// 通达信 (TDX) 接口面板 · pytdx · 实时数据源管理
// ═════════════════════════════════════════════════════════════════════════
function TDXPanel({ open, onClose }) {
  if (!open) return null;

  const servers = [
    { name: '行情主站#03', host: '119.147.212.81:7709', ping: 12, load: 34, role: '实时行情', active: true },
    { name: '扩展行情',    host: '112.95.140.74:7727',  ping: 18, load: 52, role: 'Level-2 / 期货 / 港股', active: true },
    { name: '财务数据站',  host: '60.28.29.69:7709',    ping: 24, load: 18, role: '财务 / 公告 / 分红', active: true },
    { name: '备用节点',    host: '114.80.80.222:7709',  ping: 38, load: 10, role: '主站故障自动切换', active: false },
  ];

  const apis = [
    { fn: 'get_security_quotes',    desc: '获取实时五档行情',      calls: 8432, cached: 72, users: ['Agent×5', 'Dashboard', 'Live'] },
    { fn: 'get_security_bars',      desc: 'K线数据 (分钟/日/周/月)', calls: 1847, cached: 91, users: ['Screener', 'Backtest'] },
    { fn: 'get_minute_time_data',   desc: '分时成交明细',          calls: 642,  cached: 45, users: ['Agent×2'] },
    { fn: 'get_history_minute_time', desc: '历史分时',             calls: 214,  cached: 98, users: ['Backtest'] },
    { fn: 'get_transaction_data',   desc: '逐笔成交 Tick',        calls: 3128, cached: 12, users: ['Agent 浮游', 'Live'] },
    { fn: 'get_company_info_category', desc: '公司信息分类',       calls: 42,   cached: 99, users: ['Screener'] },
    { fn: 'get_finance_info',       desc: '财务指标 (ROE/PE/PB)',  calls: 184,  cached: 99, users: ['Agent 林园', 'Agent 巴菲特'] },
    { fn: 'get_xdxr_info',          desc: '除权除息信息',          calls: 18,   cached: 100, users: ['Backtest'] },
    { fn: 'get_block_infos_meta',   desc: '板块/概念列表',         calls: 124,  cached: 99, users: ['Screener', 'Dashboard'] },
    { fn: 'get_security_list',      desc: '证券列表 (全A 5200只)', calls: 6,    cached: 100, users: ['全局'] },
  ];

  const recentCalls = [
    { t: '14:35:42.384', fn: 'get_security_quotes', args: '[000001.SZ, 600519.SH, 300750.SZ]', by: 'Agent 林园', ms: 11, ok: true },
    { t: '14:35:42.201', fn: 'get_transaction_data', args: '000858.SZ · last 500', by: 'Agent 浮游', ms: 18, ok: true },
    { t: '14:35:41.952', fn: 'get_security_bars', args: '601899.SH · 1min · 240根', by: 'Screener', ms: 24, ok: true },
    { t: '14:35:41.803', fn: 'get_finance_info', args: '000858.SZ', by: 'Agent 巴菲特', ms: 8, ok: true, cache: true },
    { t: '14:35:41.512', fn: 'get_security_quotes', args: '[寒武纪, 中际旭创, ...× 28]', by: 'Agent 浮游', ms: 42, ok: true },
    { t: '14:35:41.204', fn: 'get_block_infos_meta', args: '"白酒"', by: 'Dashboard', ms: 6, ok: true, cache: true },
    { t: '14:35:40.884', fn: 'get_security_quotes', args: '[600036.SH]', by: 'Live Trading', ms: 10, ok: true },
    { t: '14:35:40.521', fn: 'get_transaction_data', args: '300750.SZ · Tick流', by: 'Agent 浮游', ms: 14, ok: true },
  ];

  const dataFlow = [
    { from: '通达信服务器', to: 'pytdx 客户端',    rate: '1,842 tick/s', pct: 94 },
    { from: 'pytdx 客户端', to: '本地 SQLite',     rate: '428 条/s',    pct: 72 },
    { from: '本地 SQLite',  to: 'Agent × 5',      rate: '94 查询/s',   pct: 48 },
    { from: 'Agent × 5',   to: '实盘交易引擎',    rate: '0.3 单/min',  pct: 8 },
  ];

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
      backdropFilter: 'blur(6px)',
    }}>
      <div onClick={e => e.stopPropagation()} className="panel" style={{
        width: 980, maxHeight: '90vh', overflow: 'hidden',
        display: 'flex', flexDirection: 'column', background: 'var(--bg-1)',
      }}>
        {/* header */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--panel-border)',
          display: 'flex', alignItems: 'center', gap: 12,
          background: 'linear-gradient(90deg, var(--up-bg), transparent)' }}>
          <div style={{
            width: 36, height: 36, borderRadius: 6, background: 'var(--up-bg)',
            border: '1px solid var(--up)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'var(--f-mono)', fontWeight: 700, color: 'var(--up)', fontSize: 12, letterSpacing: '0.05em',
          }}>TDX</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15, color: 'var(--text-hi)', fontWeight: 600, display: 'flex', gap: 8, alignItems: 'baseline' }}>
              通达信数据接口
              <span className="pill up" style={{ fontSize: 10 }}><span className="live-dot" style={{ color: 'var(--up)' }}/> 已连接 4 个服务器</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 3 }}>
              pytdx v1.72 · 本软件所有行情/财务/Tick 数据均通过通达信协议实时获取，无需额外付费 API
            </div>
          </div>
          <button onClick={onClose} className="btn ghost" style={{ padding: '4px 10px' }}>关闭</button>
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
          {/* stat strip */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8, marginBottom: 16 }}>
            {[
              ['今日调用', '14,637', 'var(--text-hi)', '次'],
              ['缓存命中率', '84.2', 'var(--up)', '%'],
              ['平均延迟', '12', 'var(--up)', 'ms'],
              ['Tick 入库', '1,842', 'var(--brand)', '/s'],
              ['失败率', '0.02', 'var(--up)', '%'],
            ].map(([k, v, c, u]) => (
              <div key={k} style={{ padding: '10px 12px', background: 'var(--bg-2)', borderRadius: 3, border: '1px solid var(--panel-border-soft)' }}>
                <div style={{ fontSize: 10, color: 'var(--text-faint)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>{k}</div>
                <div style={{ marginTop: 3, display: 'flex', alignItems: 'baseline', gap: 3 }}>
                  <span className="mono" style={{ fontSize: 22, fontWeight: 600, color: c, letterSpacing: '-0.01em' }}>{v}</span>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--text-ghost)' }}>{u}</span>
                </div>
              </div>
            ))}
          </div>

          {/* data flow */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 8 }}>
              ▸ 数据流向 · TDX → 本地 → Agent → 交易
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 0, position: 'relative',
              padding: 12, background: 'var(--bg-2)', borderRadius: 4, border: '1px solid var(--panel-border-soft)' }}>
              {dataFlow.map((f, i) => (
                <div key={i} style={{ textAlign: 'center', position: 'relative' }}>
                  <div style={{ fontSize: 10.5, color: 'var(--text-faint)' }}>{f.from}</div>
                  <div style={{ margin: '4px 6px 3px', height: 4, background: 'var(--bg-3)', borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{ width: f.pct + '%', height: '100%', background: 'var(--up)' }}/>
                  </div>
                  <div className="mono" style={{ fontSize: 10, color: 'var(--up)', fontWeight: 600 }}>{f.rate}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-hi)', fontWeight: 500, marginTop: 2 }}>→ {f.to}</div>
                </div>
              ))}
            </div>
          </div>

          {/* 2 column: servers + APIs */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: 12, marginBottom: 16 }}>
            {/* servers */}
            <div>
              <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 8 }}>
                ▸ 通达信服务器 · 多点智能路由
              </div>
              {servers.map(s => (
                <div key={s.name} style={{ padding: '9px 11px', background: 'var(--bg-2)',
                  border: '1px solid ' + (s.active ? 'var(--up-border)' : 'var(--panel-border-soft)'),
                  borderRadius: 3, marginBottom: 5, opacity: s.active ? 1 : 0.55,
                  display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span className="live-dot" style={{ color: s.active ? 'var(--up)' : 'var(--text-ghost)' }}/>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                      <span style={{ fontSize: 12, color: 'var(--text-hi)', fontWeight: 500 }}>{s.name}</span>
                      <span className="mono" style={{ fontSize: 10, color: 'var(--text-faint)' }}>{s.host}</span>
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-ghost)', marginTop: 2 }}>{s.role}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div className="mono" style={{ fontSize: 11, color: s.ping < 20 ? 'var(--up)' : s.ping < 40 ? 'var(--warn)' : 'var(--down)', fontWeight: 600 }}>{s.ping}ms</div>
                    <div className="mono" style={{ fontSize: 9, color: 'var(--text-ghost)' }}>负载 {s.load}%</div>
                  </div>
                </div>
              ))}
            </div>

            {/* APIs */}
            <div>
              <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 8 }}>
                ▸ pytdx 调用 · 今日 API 使用情况
              </div>
              <div style={{ maxHeight: 270, overflowY: 'auto', border: '1px solid var(--panel-border-soft)', borderRadius: 3 }}>
                <table className="tbl" style={{ margin: 0 }}>
                  <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-2)' }}>
                    <tr>
                      <th>接口</th><th className="num">调用</th><th className="num">缓存率</th><th>使用者</th>
                    </tr>
                  </thead>
                  <tbody>
                    {apis.map(a => (
                      <tr key={a.fn}>
                        <td>
                          <div className="mono" style={{ fontSize: 11, color: 'var(--info)' }}>{a.fn}()</div>
                          <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 1 }}>{a.desc}</div>
                        </td>
                        <td className="num mono" style={{ fontSize: 11 }}>{a.calls.toLocaleString()}</td>
                        <td className="num">
                          <span className="mono" style={{ fontSize: 11, color: a.cached > 80 ? 'var(--up)' : a.cached > 40 ? 'var(--warn)' : 'var(--down)' }}>{a.cached}%</span>
                        </td>
                        <td style={{ fontSize: 10, color: 'var(--text-dim)' }}>{a.users.join(' · ')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* recent calls */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>▸ 实时调用日志</span>
              <span className="pill" style={{ fontSize: 9 }}><span className="live-dot" style={{ color: 'var(--up)' }}/> 流式</span>
              <span style={{ flex: 1 }}/>
              <span style={{ fontSize: 10, color: 'var(--text-ghost)' }}>最近 8 条</span>
            </div>
            <div style={{ background: 'var(--bg-2)', border: '1px solid var(--panel-border-soft)', borderRadius: 3,
              fontFamily: 'var(--f-mono)', fontSize: 10.5, overflow: 'hidden' }}>
              {recentCalls.map((c, i) => (
                <div key={i} style={{
                  padding: '5px 10px', display: 'flex', gap: 10, alignItems: 'baseline',
                  borderBottom: i < recentCalls.length - 1 ? '1px solid var(--panel-border-soft)' : 'none',
                }}>
                  <span style={{ color: 'var(--text-ghost)', fontSize: 10, flexShrink: 0 }}>{c.t}</span>
                  <span style={{ color: 'var(--info)', fontWeight: 500 }}>{c.fn}</span>
                  <span style={{ color: 'var(--text-faint)', fontSize: 10, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    ({c.args})
                  </span>
                  <span style={{ color: 'var(--text-dim)', fontSize: 10, flexShrink: 0 }}>← {c.by}</span>
                  <span style={{ color: c.cache ? 'var(--warn)' : 'var(--up)', fontSize: 10, flexShrink: 0, minWidth: 40, textAlign: 'right' }}>
                    {c.cache ? 'cache' : c.ms + 'ms'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* footer */}
        <div style={{ padding: '10px 20px', borderTop: '1px solid var(--panel-border)',
          display: 'flex', alignItems: 'center', gap: 12,
          background: 'var(--bg-2)', fontSize: 10.5 }}>
          <Icon name="check" size={11} style={{ color: 'var(--up)' }}/>
          <span style={{ color: 'var(--text-faint)', flex: 1 }}>
            本地 pytdx 客户端 · 无需 API Key · 所有数据来自通达信免费行情服务器
          </span>
          <button className="btn ghost" style={{ fontSize: 10.5, padding: '3px 8px' }}>重连</button>
          <button className="btn ghost" style={{ fontSize: 10.5, padding: '3px 8px' }}>清缓存</button>
          <button className="btn ghost" style={{ fontSize: 10.5, padding: '3px 8px' }}>服务器设置</button>
        </div>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// 全局红线策略 · 持久化于 localStorage · 所有 Agent/策略/下单必须通过
// ═════════════════════════════════════════════════════════════════════════
const DEFAULT_REDLINES = {
  dailyLoss: 3,       // 日最大亏损 %
  positionMax: 15,    // 单笔最大仓位 %
  stockMax: 30,       // 单股集中度 %
  cashMin: 5,         // 最低现金比例 %
  orderMax: 200000,   // 单笔金额上限 ¥
  turnoverMax: 300,   // 日内最大换手 %
  banLimitUp: true,   // 禁止追涨停
  banST: true,        // 禁止 ST/*ST
  coolDown: 5,        // 同票冷却分钟
  requireReason: true,// 决策必须附理由
  promptInjectCheck: true, // Prompt 注入检测
  autoHaltVaR: true,  // 超 2σ 自动熔断
};

function useRedLines() {
  const [rl, setRl] = useState(() => {
    try {
      const saved = localStorage.getItem('biying_redlines');
      return saved ? { ...DEFAULT_REDLINES, ...JSON.parse(saved) } : DEFAULT_REDLINES;
    } catch { return DEFAULT_REDLINES; }
  });
  const update = (patch) => {
    setRl(prev => {
      const next = { ...prev, ...patch };
      try { localStorage.setItem('biying_redlines', JSON.stringify(next)); } catch {}
      return next;
    });
  };
  return [rl, update];
}

function RedLineBar({ onOpen }) {
  const [rl] = useRedLines();

  // Current usage vs limits (mock but realistic)
  const usage = [
    { key: 'dailyLoss', label: '日亏损', cur: 0.42, limit: rl.dailyLoss, unit: '%', fmt: v => `-${v.toFixed(2)}%` },
    { key: 'stockMax',  label: '最大集中度', cur: 22, limit: rl.stockMax, unit: '%', fmt: v => `${v}%`, who: '茅台' },
    { key: 'cashMin',   label: '现金比例', cur: 8.4, limit: rl.cashMin, unit: '%', inverse: true, fmt: v => `${v}%` },
    { key: 'turnoverMax', label: '日换手', cur: 87, limit: rl.turnoverMax, unit: '%', fmt: v => `${v}%` },
  ];

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 0,
      height: 32, padding: '0 14px',
      background: 'var(--bg-1)',
      borderBottom: '1px solid var(--panel-border)',
      flexShrink: 0,
      fontFamily: 'var(--f-mono)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, paddingRight: 14, borderRight: '1px solid var(--panel-border-soft)' }}>
        <Icon name="risk" size={12} style={{ color: 'var(--down)' }}/>
        <span style={{ fontSize: 10.5, color: 'var(--down)', letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 600 }}>全局红线</span>
        <span className="pill" style={{ fontSize: 9.5, background: 'var(--down-bg)', border: '1px solid var(--down-border)', color: 'var(--down)' }}>
          <span className="live-dot" style={{ color: 'var(--down)' }}/> 12 条生效中
        </span>
      </div>

      {/* 4 key usage bars */}
      <div style={{ flex: 1, display: 'flex', gap: 18, paddingLeft: 14, alignItems: 'center' }}>
        {usage.map(u => {
          const ratio = u.inverse ? (u.limit / Math.max(u.cur, 0.01)) : (u.cur / u.limit);
          const pct = Math.min(ratio * 100, 100);
          const danger = ratio > 0.8;
          const warn = ratio > 0.6;
          const color = danger ? 'var(--down)' : warn ? 'var(--warn)' : 'var(--up)';
          return (
            <div key={u.key} style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 150 }}>
              <span style={{ fontSize: 10, color: 'var(--text-faint)', fontFamily: 'var(--f-ui)', whiteSpace: 'nowrap' }}>{u.label}</span>
              <div style={{ flex: 1, height: 5, background: 'var(--bg-3)', borderRadius: 2, overflow: 'hidden', position: 'relative', minWidth: 40 }}>
                <div style={{ width: pct + '%', height: '100%', background: color, transition: 'width 0.3s' }}/>
                {/* 80% warning mark */}
                <div style={{ position: 'absolute', left: '80%', top: 0, bottom: 0, width: 1, background: 'var(--panel-border)' }}/>
              </div>
              <span style={{ fontSize: 10, color: color, fontWeight: 600, whiteSpace: 'nowrap' }}>
                {u.fmt(u.cur)}<span style={{ color: 'var(--text-ghost)', fontWeight: 400 }}> / {u.inverse ? '≥' : '≤'}{u.fmt(u.limit).replace('-','')}</span>
              </span>
            </div>
          );
        })}
      </div>

      <div style={{ display: 'flex', gap: 6, paddingLeft: 14, borderLeft: '1px solid var(--panel-border-soft)' }}>
        <button onClick={onOpen} style={{
          padding: '3px 10px', background: 'transparent',
          border: '1px solid var(--panel-border)', borderRadius: 3,
          color: 'var(--text-dim)', fontSize: 10.5, fontFamily: 'var(--f-ui)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 5,
        }} onMouseEnter={e => { e.currentTarget.style.color = 'var(--text-hi)'; e.currentTarget.style.borderColor = 'var(--brand)'; }}
           onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-dim)'; e.currentTarget.style.borderColor = 'var(--panel-border)'; }}>
          <Icon name="settings" size={10}/> 调整红线
        </button>
        <button style={{
          padding: '3px 10px', background: 'var(--down-bg)',
          border: '1px solid var(--down)', borderRadius: 3,
          color: 'var(--down)', fontSize: 10.5, fontFamily: 'var(--f-ui)', cursor: 'pointer',
          fontWeight: 600,
          display: 'flex', alignItems: 'center', gap: 5,
        }} title="一键熔断 — 所有 Agent 停止交易">
          🛑 熔断
        </button>
      </div>
    </div>
  );
}

function RedLineConfigModal({ open, onClose }) {
  const [rl, setRl] = useRedLines();
  if (!open) return null;

  const groups = [
    { title: '资金防护 · 保护本金', icon: '💰', color: 'var(--down)', items: [
      { key: 'dailyLoss',    label: '日最大亏损',   unit: '%',  min: 1, max: 10, step: 0.5, help: '触及则自动熔断所有 Agent，锁仓至次日' },
      { key: 'positionMax',  label: '单笔最大仓位', unit: '%',  min: 5, max: 50, step: 5,   help: '单次买入不超过总资金的百分比' },
      { key: 'stockMax',     label: '单股集中度',   unit: '%',  min: 10, max: 80, step: 5,  help: '单只股票占总资产的上限' },
      { key: 'cashMin',      label: '最低现金比例', unit: '%',  min: 0, max: 30, step: 1,   help: '随时保留的现金比例，应对黑天鹅' },
      { key: 'orderMax',     label: '单笔金额上限', unit: '¥',  min: 10000, max: 2000000, step: 10000, help: '单张委托单金额硬上限' },
    ]},
    { title: '交易防护 · 控制频率', icon: '⚡', color: 'var(--warn)', items: [
      { key: 'turnoverMax',  label: '日内最大换手', unit: '%',  min: 50, max: 1000, step: 50, help: '防止过度交易消耗手续费' },
      { key: 'coolDown',     label: '同票冷却',     unit: '分钟', min: 1, max: 60, step: 1,    help: '同一只股票交易后的等待时间' },
    ]},
  ];

  const toggles = [
    { key: 'banLimitUp',       label: '禁止追涨停',      desc: '涨停板不买入，避免接最后一棒' },
    { key: 'banST',            label: '禁止 ST/*ST',    desc: '排除退市风险股' },
    { key: 'requireReason',    label: '决策必须附理由',  desc: 'Agent 每笔交易必须解释依据' },
    { key: 'promptInjectCheck', label: 'Prompt 注入检测', desc: '过滤新闻/公告中的恶意诱导' },
    { key: 'autoHaltVaR',      label: '异常波动自动熔断', desc: '超 2σ 波动立即暂停 Agent' },
  ];

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
      backdropFilter: 'blur(6px)',
    }}>
      <div onClick={e => e.stopPropagation()} className="panel" style={{
        width: 760, maxHeight: '88vh', overflow: 'hidden',
        display: 'flex', flexDirection: 'column',
        background: 'var(--bg-1)',
      }}>
        {/* header */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--panel-border)',
          display: 'flex', alignItems: 'center', gap: 12,
          background: 'linear-gradient(90deg, var(--down-bg), transparent)' }}>
          <Icon name="risk" size={18} style={{ color: 'var(--down)' }}/>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15, color: 'var(--text-hi)', fontWeight: 600 }}>全局红线策略</div>
            <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 2 }}>
              所有 Agent、所有策略、每一笔下单都必须先通过这些规则 · 本地保存
            </div>
          </div>
          <button onClick={onClose} className="btn ghost" style={{ padding: '4px 10px' }}>完成</button>
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: 20 }}>
          {groups.map(g => (
            <div key={g.title} style={{ marginBottom: 22 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, paddingBottom: 6,
                borderBottom: '1px solid var(--panel-border-soft)' }}>
                <div style={{ width: 3, height: 14, background: g.color }}/>
                <span style={{ fontSize: 12.5, color: 'var(--text-hi)', fontWeight: 600 }}>{g.icon} {g.title}</span>
              </div>
              {g.items.map(it => (
                <div key={it.key} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '10px 0',
                  borderBottom: '1px solid var(--panel-border-soft)' }}>
                  <div style={{ width: 200, flexShrink: 0 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-hi)', fontWeight: 500 }}>{it.label}</div>
                    <div style={{ fontSize: 10.5, color: 'var(--text-faint)', marginTop: 2, lineHeight: 1.35 }}>{it.help}</div>
                  </div>
                  <input type="range" min={it.min} max={it.max} step={it.step} value={rl[it.key]}
                    onChange={e => setRl({ [it.key]: parseFloat(e.target.value) })}
                    style={{ flex: 1, accentColor: 'var(--down)' }}/>
                  <div style={{ width: 110, textAlign: 'right' }}>
                    <span className="mono" style={{ fontSize: 15, color: 'var(--down)', fontWeight: 600 }}>
                      {it.unit === '¥' ? '¥' + rl[it.key].toLocaleString() :
                       it.unit === '%' ? (rl[it.key] + '%') :
                       (rl[it.key] + ' ' + it.unit)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ))}

          <div style={{ marginTop: 18 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, paddingBottom: 6,
              borderBottom: '1px solid var(--panel-border-soft)' }}>
              <div style={{ width: 3, height: 14, background: 'var(--brand)' }}/>
              <span style={{ fontSize: 12.5, color: 'var(--text-hi)', fontWeight: 600 }}>🛡️ 行为防护 · 硬性开关</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {toggles.map(t => (
                <label key={t.key} style={{ display: 'flex', alignItems: 'flex-start', gap: 10,
                  padding: 10, background: 'var(--bg-2)',
                  border: '1px solid ' + (rl[t.key] ? 'var(--up-border)' : 'var(--panel-border-soft)'),
                  borderRadius: 4, cursor: 'pointer' }}>
                  <div onClick={() => setRl({ [t.key]: !rl[t.key] })} style={{
                    width: 32, height: 18, borderRadius: 9, padding: 2, flexShrink: 0,
                    background: rl[t.key] ? 'var(--up)' : 'var(--bg-3)',
                    transition: 'all 0.2s', marginTop: 1,
                  }}>
                    <div style={{
                      width: 12, height: 12, borderRadius: '50%', background: 'white',
                      transform: rl[t.key] ? 'translateX(14px)' : 'translateX(0)',
                      transition: 'transform 0.2s',
                    }}/>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-hi)', fontWeight: 500 }}>{t.label}</div>
                    <div style={{ fontSize: 10.5, color: 'var(--text-faint)', marginTop: 2, lineHeight: 1.35 }}>{t.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* footer */}
        <div style={{ padding: '12px 20px', borderTop: '1px solid var(--panel-border)',
          display: 'flex', alignItems: 'center', gap: 10,
          background: 'var(--bg-2)' }}>
          <Icon name="check" size={11} style={{ color: 'var(--up)' }}/>
          <span style={{ fontSize: 10.5, color: 'var(--text-faint)', flex: 1 }}>
            修改立即全局生效 · 所有 Agent 下一笔决策前重新加载 · 保存至本地 localStorage
          </span>
          <button onClick={() => setRl(DEFAULT_REDLINES)} className="btn ghost" style={{ fontSize: 11, padding: '4px 10px' }}>恢复默认</button>
          <button onClick={onClose} className="btn primary" style={{ fontSize: 11, padding: '4px 14px' }}>完成</button>
        </div>
      </div>
    </div>
  );
}
