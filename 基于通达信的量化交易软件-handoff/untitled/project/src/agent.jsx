// AI Agent Lab — LLM 多模型对比 · 模仿操盘手风格
function AgentLab() {
  const [selected, setSelected] = useState('linyuan');
  const [showPromptEditor, setShowPromptEditor] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [customAgents, setCustomAgents] = useState([]);

  const baseAgents = [
    {
      id: 'linyuan', name: '林园风格', model: 'Claude Opus 4.5',
      desc: '价值投资 · 重仓白酒医药消费 · 长期持有',
      ret: 32.4, sharpe: 1.84, mdd: -6.2, win: 71, trades: 14, cost: 2.14,
      color: 'var(--brand)', rank: 1,
      positions: ['贵州茅台 32%', '五粮液 18%', '片仔癀 12%', '恒瑞医药 10%'],
      thinking: '当前市场情绪偏乐观，但白酒板块估值仍在合理区间。茅台PE 23x 处于近5年35%分位，适合继续持有。片仔癀创新高，考虑部分减仓锁定利润。',
    },
    {
      id: 'fuyou', name: '浮游风格', model: 'GPT-5',
      desc: '短线游资 · 题材热点 · 快进快出',
      ret: 58.7, sharpe: 1.62, mdd: -14.2, win: 58, trades: 147, cost: 8.42,
      color: 'var(--up)', rank: 2,
      positions: ['寒武纪 20%', '中际旭创 15%', '工业富联 12%', '现金 40%'],
      thinking: 'AI算力板块出现涨停潮，寒武纪连续3日放量突破，跟进首板。但需警惕周五情绪降温，设置-4%止损。',
    },
    {
      id: 'buffet', name: '巴菲特风格', model: 'Gemini 2.0 Pro',
      desc: '护城河 · 安全边际 · ROE > 15%',
      ret: 18.2, sharpe: 2.14, mdd: -3.8, win: 82, trades: 8, cost: 1.42,
      color: 'var(--info)', rank: 3,
      positions: ['招商银行 25%', '长江电力 20%', '美的集团 15%', '伊利股份 12%'],
      thinking: '银行板块整体估值处于历史底部 PB 0.8x，招行作为零售银行龙头，ROE连续10年>15%，长期持有不变。',
    },
    {
      id: 'soros', name: '索罗斯反身性', model: 'Claude Sonnet 4.5',
      desc: '宏观对冲 · 反身性 · 追逐趋势',
      ret: 24.8, sharpe: 1.28, mdd: -18.4, win: 52, trades: 32, cost: 3.81,
      color: 'var(--purple)', rank: 4,
      positions: ['沪深300 ETF -20% (做空)', '黄金 ETF 25%', '现金 55%'],
      thinking: '市场情绪已至极端乐观，融资余额创3年新高。建仓空头对冲，同时加仓避险资产黄金。',
    },
    {
      id: 'quant', name: '量化中性', model: 'DeepSeek V4',
      desc: '多因子 · 市值中性 · 低回撤',
      ret: 14.2, sharpe: 3.12, mdd: -2.1, win: 88, trades: 482, cost: 0.82,
      color: 'var(--down)', rank: 5,
      positions: ['多头 182只 · 空头 沪深300期货', '市值暴露 ≈0', '行业中性'],
      thinking: '模型Alpha信号稳定，动量+反转+质量三因子贡献度均衡。维持当前持仓，按月度调仓。',
    },
  ];

  const agents = [...baseAgents, ...customAgents];
  const cur = agents.find(a => a.id === selected) || agents[0];

  const addAgent = (a) => {
    const id = 'custom_' + Date.now();
    setCustomAgents(prev => [...prev, { ...a, id, rank: agents.length + 1 }]);
    setSelected(id);
    setShowCreate(false);
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr', gridTemplateRows: 'auto auto minmax(0,1fr)',
      gap: 12, padding: 12, height: '100%', overflow: 'hidden' }}>

      {/* Autonomous scheduler — 24/7 event-driven operation */}
      <AutonomousScheduler/>

      {/* Hero: my AI traders */}
      <div className="panel" style={{ padding: '14px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <Icon name="brain" size={16} style={{ color: 'var(--brand)' }}/>
          <span style={{ fontSize: 11, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>为你 7×24 工作的 AI 操盘手</span>
          <span style={{ flex: 1 }}/>
          <span className="pill brand"><span className="live-dot"/> 5 个 Agent 同时盯盘 · 已为你赚 ¥42,180</span>
          <button className="btn ghost" onClick={() => setShowPromptEditor(true)}><Icon name="wand" size={12}/> 编辑操盘理念</button>
          <button className="btn primary" onClick={() => setShowCreate(true)}><Icon name="plus" size={12}/> 新增操盘手</button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.max(5, agents.length)}, 1fr)`, gap: 8 }}>
          {agents.map(a => {
            const isSel = a.id === selected;
            // 为你赚的钱 (mock: based on ret)
            const earned = Math.round(a.ret * 135);
            return (
              <div key={a.id} onClick={() => setSelected(a.id)} style={{
                padding: 10, cursor: 'pointer',
                background: isSel ? 'var(--bg-3)' : 'var(--bg-2)',
                border: '1px solid ' + (isSel ? a.color : 'var(--panel-border-soft)'),
                borderRadius: 5, position: 'relative'
              }}>
                <div style={{
                  position: 'absolute', top: 8, right: 10,
                  fontFamily: 'var(--f-mono)', fontSize: 11, fontWeight: 500,
                  color: earned >= 0 ? 'var(--up)' : 'var(--down)',
                  lineHeight: 1, letterSpacing: '-0.01em', textAlign: 'right'
                }}>
                  <div style={{ fontSize: 9, color: 'var(--text-ghost)', fontWeight: 400, marginBottom: 2 }}>为你赚</div>
                  {earned >= 0 ? '+' : ''}¥{Math.abs(earned).toLocaleString()}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 7, height: 7, borderRadius: 2, background: a.color }}/>
                  <div style={{ color: 'var(--text-hi)', fontWeight: 600, fontSize: 13 }}>{a.name}</div>
                </div>
                <div className="mono" style={{ fontSize: 9.5, color: 'var(--text-ghost)', marginTop: 3, letterSpacing: '0.04em' }}>{a.model}</div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 8 }}>
                  <div className={`num ${a.ret >= 0 ? 'up' : 'down'}`} style={{ fontSize: 20, fontWeight: 600, letterSpacing: '-0.01em' }}>{pct(a.ret, 1)}</div>
                  <div className="mono" style={{ fontSize: 9.5, color: 'var(--text-faint)' }}>90日</div>
                </div>
                <div style={{ display: 'flex', gap: 12, marginTop: 4, fontSize: 10, color: 'var(--text-faint)' }}>
                  <span>夏普 <span className="mono up">{a.sharpe}</span></span>
                  <span>回撤 <span className="mono down">{pct(a.mdd, 1)}</span></span>
                  <span>胜率 <span className="mono up">{a.win}%</span></span>
                </div>
                <div style={{ marginTop: 6 }}>
                  <Sparkline data={genSpark(a.id.length * 13, 40, a.ret > 0 ? a.ret / 80 : -0.1, a.mdd < -10 ? 1.3 : 0.7)}
                    color={a.color} width={200} height={22}/>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* main area */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 380px', gap: 12, minHeight: 0, overflow: 'hidden' }}>
        {/* COL 1: thinking / decision log */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div className="panel-head">
            <span style={{ width: 7, height: 7, borderRadius: 2, background: cur.color }}/>
            <span className="panel-title">{cur.name} · 思考日志</span>
            <span className="pill brand"><Icon name="sparkle" size={9}/> {cur.model}</span>
            <span style={{ flex: 1 }}/>
            <span className="pill"><span className="live-dot" style={{ color: 'var(--up)' }}/> 实时</span>
          </div>
          <div style={{ flex: 1, overflow: 'auto', padding: 14 }}>
            {[
              { t: '14:32:18', kind: 'decision', title: '买入决策 · 宁德时代 300750', content: '宁德时代刚公告Q1业绩超预期，营收增速42%。技术面突破60日新高，成交量放大至均量2.1倍，符合我"业绩+技术共振"的选股范式。按15%仓位买入。', act: { type: 'buy', code: '300750', qty: 200, price: 247.80 } },
              { t: '14:18:42', kind: 'thinking', title: '市场情绪分析', content: '今日沪深300放量上涨0.84%，北向资金净流入62亿。白酒板块领涨，我重仓的茅台涨幅2.3%。整体市场情绪偏乐观，但需警惕创业板分化，继续持仓观察。' },
              { t: '13:48:02', kind: 'decision', title: '减仓决策 · 片仔癀 600436', content: '片仔癀创历史新高，估值PE达到48x，超出我的安全边际。锁定50%仓位利润，剩余继续持有等待业绩披露。', act: { type: 'sell', code: '600436', qty: 100, price: 262.40 } },
              { t: '11:24:18', kind: 'thinking', title: '行业配置复盘', content: '近一周白酒板块涨幅8.2%，领先沪深300 5个百分点。回想2020年白酒大牛市，当时核心逻辑是消费升级+龙头集中度提升。当前周期类似，继续保持超配。' },
              { t: '10:02:44', kind: 'decision', title: '加仓决策 · 五粮液 000858', content: '五粮液回调至145元附近，对应PE 18x，已进入我的"低估可买入"区间。分批加仓至18%仓位。', act: { type: 'buy', code: '000858', qty: 300, price: 146.20 } },
              { t: '09:32:01', kind: 'thinking', title: '开盘策略', content: '昨晚美股纳指收涨1.2%，A股预期高开。我的持仓主要是大消费，对外围波动敏感度较低。开盘不急于操作，观察30分钟再决定。' },
            ].map((e, i) => (
              <div key={i} style={{
                marginBottom: 14, paddingBottom: 14,
                borderBottom: i < 5 ? '1px solid var(--panel-border-soft)' : 'none',
              }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
                  <span className={`pill ${e.kind === 'decision' ? (e.act?.type === 'buy' ? 'up' : 'down') : 'info'}`} style={{ fontSize: 9.5 }}>
                    {e.kind === 'decision' ? <><Icon name="zap" size={9}/> 决策</> : <><Icon name="brain" size={9}/> 思考</>}
                  </span>
                  <span style={{ color: 'var(--text-hi)', fontSize: 12, fontWeight: 500 }}>{e.title}</span>
                  <span style={{ flex: 1 }}/>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--text-ghost)' }}>{e.t}</span>
                </div>
                <div className="serif" style={{ fontSize: 12.5, color: 'var(--text)', lineHeight: 1.6, paddingLeft: 2 }}>
                  "{e.content}"
                </div>
                {e.act && (
                  <div style={{
                    marginTop: 6,
                    padding: '6px 10px',
                    background: e.act.type === 'buy' ? 'var(--up-bg)' : 'var(--down-bg)',
                    border: '1px solid ' + (e.act.type === 'buy' ? 'var(--up-border)' : 'var(--down-border)'),
                    borderRadius: 4,
                    display: 'flex', gap: 10, alignItems: 'center'
                  }}>
                    <span className={`pill ${e.act.type === 'buy' ? 'up' : 'down'}`} style={{ fontSize: 10 }}>
                      {e.act.type === 'buy' ? '买入' : '卖出'}
                    </span>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--text-hi)' }}>{e.act.code}</span>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--text-faint)' }}>@ ¥{fmt(e.act.price)}</span>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--text-faint)' }}>× {e.act.qty}股</span>
                    <span style={{ flex: 1 }}/>
                    <span className="mono pill">已执行</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* COL 2: positions + performance */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0 }}>
          <div className="panel" style={{ padding: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>{cur.name} · 当前持仓</div>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-faint)' }}>¥1,000,000 初始</div>
            </div>
            <div className="serif" style={{ fontSize: 16, color: 'var(--text)', marginTop: 6, lineHeight: 1.5, fontStyle: 'italic' }}>
              "{cur.desc}"
            </div>
            <div style={{ marginTop: 12 }}>
              {cur.positions.map((p, i) => {
                const [name, w] = p.split(' ');
                const width = parseInt(w) || 5;
                return (
                  <div key={i} style={{ marginBottom: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, marginBottom: 2 }}>
                      <span style={{ color: 'var(--text)' }}>{name}</span>
                      <span className="mono" style={{ color: 'var(--text-hi)', fontWeight: 600 }}>{w}</span>
                    </div>
                    <div style={{ width: '100%', height: 4, background: 'var(--bg-3)', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ width: Math.abs(width) + '%', height: '100%', background: width < 0 ? 'var(--down)' : cur.color }}/>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="panel" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            <div className="panel-head">
              <span className="panel-title">净值对比 · 5 Agent</span>
              <span style={{ flex: 1 }}/>
              <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>90天</span>
            </div>
            <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
              <AgentCompareChart agents={agents} selected={selected}/>
            </div>
          </div>

          <div className="panel" style={{ padding: 14 }}>
            <div style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 8 }}>成本统计</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 11 }}>
              <div><span style={{ color: 'var(--text-faint)' }}>Token 消耗</span><div className="num" style={{ color: 'var(--text-hi)', fontSize: 14, fontWeight: 600, marginTop: 2 }}>847K</div></div>
              <div><span style={{ color: 'var(--text-faint)' }}>累计成本</span><div className="num" style={{ color: 'var(--brand)', fontSize: 14, fontWeight: 600, marginTop: 2 }}>¥{cur.cost * 100}</div></div>
              <div><span style={{ color: 'var(--text-faint)' }}>决策次数</span><div className="num" style={{ color: 'var(--text-hi)', fontSize: 14, fontWeight: 600, marginTop: 2 }}>{cur.trades}</div></div>
              <div><span style={{ color: 'var(--text-faint)' }}>ROI/¥</span><div className="num up" style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>{(cur.ret / cur.cost).toFixed(0)}x</div></div>
            </div>
          </div>
        </div>

        {/* COL 3: prompt / persona */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div className="panel-head">
            <span className="panel-title">人格 Prompt · 可版本化</span>
            <span style={{ flex: 1 }}/>
            <span className="pill">v7</span>
            <button className="btn ghost" style={{ padding: '2px 6px' }}><Icon name="copy" size={11}/></button>
          </div>
          <div style={{ flex: 1, overflow: 'auto', padding: 14, fontSize: 11.5, lineHeight: 1.65 }}>
            <div style={{ color: 'var(--text-faint)', fontSize: 10, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 6 }}>
              SYSTEM PROMPT
            </div>
            <div className="mono" style={{ color: 'var(--text)', fontSize: 11.5 }}>
              你是 <span style={{ color: 'var(--brand)' }}>林园</span>，一位坚守<span style={{ color: 'var(--up)' }}>价值投资</span>理念的基金经理。<br/><br/>
              你的投资原则：<br/>
              1. 只买看得懂的行业：<span style={{ color: 'var(--up)' }}>白酒、医药、消费</span><br/>
              2. 寻找"印钞机"式企业：ROE {'>'}  15%，毛利率 {'>'} 30%<br/>
              3. 安全边际至上：PE 低于行业均值 20%<br/>
              4. 长期持有：平均持仓周期 {'>'} 6个月<br/>
              5. 重仓龙头：单只股票 ≤ 30%，前5重仓 ≥ 70%<br/><br/>
              你应避免：<br/>
              • 追涨杀跌、短线交易<br/>
              • 科技股、周期股、新概念<br/>
              • 超过总仓位 5% 的仓位调整<br/><br/>
              决策格式：<br/>
              <span style={{ color: 'var(--info)' }}>{'<thinking>'}</span> 详细分析 <span style={{ color: 'var(--info)' }}>{'</thinking>'}</span><br/>
              <span style={{ color: 'var(--info)' }}>{'<action>'}</span> buy/sell/hold, 股票代码, 数量 <span style={{ color: 'var(--info)' }}>{'</action>'}</span>
            </div>

            <div style={{ marginTop: 18, color: 'var(--text-faint)', fontSize: 10, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8 }}>
              TOOLS 可用工具
            </div>
            {[
              ['get_quote(code)', '实时行情'],
              ['get_kline(code, period)', 'K线数据'],
              ['get_financials(code)', '财务指标'],
              ['get_news(code)', '新闻舆情'],
              ['place_order(code, side, qty)', '下单交易'],
              ['get_positions()', '查询持仓'],
            ].map(([fn, desc]) => (
              <div key={fn} style={{ display: 'flex', gap: 8, padding: '4px 0', fontSize: 11 }}>
                <span className="mono" style={{ color: 'var(--info)' }}>{fn}</span>
                <span style={{ color: 'var(--text-faint)' }}>· {desc}</span>
              </div>
            ))}

            <div style={{ marginTop: 18, padding: 10, background: 'var(--brand-soft)', border: '1px solid var(--brand-border)', borderRadius: 4 }}>
              <div style={{ fontSize: 10.5, color: 'var(--brand)', fontWeight: 600, marginBottom: 4 }}>
                <Icon name="sparkle" size={10}/> Prompt 演化历史
              </div>
              <div style={{ fontSize: 10.5, color: 'var(--text-faint)', lineHeight: 1.6 }}>
                v1 → v7 历经 12 次优化，夏普从 1.12 提升至 1.84。
              </div>
            </div>
          </div>
          <div style={{ padding: 10, borderTop: '1px solid var(--panel-border-soft)', display: 'flex', gap: 6 }}>
            <button className="btn ghost" style={{ flex: 1 }}><Icon name="refresh" size={12}/> 重跑回测</button>
            <button className="btn primary" style={{ flex: 1 }}><Icon name="live" size={12}/> 部署实盘</button>
          </div>
        </div>
      </div>

      {showPromptEditor && <PromptModal onClose={() => setShowPromptEditor(false)}/>}
      {showCreate && <CreateAgentModal onClose={() => setShowCreate(false)} onCreate={addAgent}/>}
    </div>
  );
}

function CreateAgentModal({ onClose, onCreate }) {
  const prototypes = [
    { id: 'duan',    name: '段永平', desc: '本分 · 长期持有 · 消费科技', color: 'oklch(0.82 0.18 75)',
      prompt: '你是段永平，价值投资者。核心理念：\n• 本分：只做看得懂的生意\n• 平常心：不追涨杀跌\n• 敢为天下后：等待最好入场点\n• 长期持有龙头' },
    { id: 'zhaodanyang', name: '赵丹阳', desc: '深度价值 · 逆向投资', color: 'oklch(0.74 0.15 235)',
      prompt: '你是赵丹阳，深度价值投资者。\n• 买入标准：PB<1.2，ROE>15%\n• 重仓低估资产，耐心等待价值回归\n• 逆向思维，熊市建仓牛市减仓' },
    { id: 'fengliu',  name: '冯柳风格', desc: '弱者体系 · 困境反转', color: 'oklch(0.78 0.22 148)',
      prompt: '你是冯柳风格投资者，采用"弱者体系"。\n• 寻找市场错杀的困境反转机会\n• 逆向布局被情绪打压的优质公司\n• 不预测，只应对' },
    { id: 'custom',   name: '空白自定义', desc: '从零开始自己写 Prompt', color: 'oklch(0.52 0.012 260)',
      prompt: '你是一位...\n\n投资原则：\n1. \n2. \n\n可用工具：\n• get_quote(code)\n• get_kline(code, period)\n• place_order(code, side, qty)' },
  ];
  const [proto, setProto] = useState('duan');
  const [name, setName] = useState('段永平风格');
  const [model, setModel] = useState('Claude Opus 4.5');
  const [capital, setCapital] = useState(1000000);
  const [freq, setFreq] = useState('每日收盘后');
  const [stopLoss, setStopLoss] = useState(8);
  const [maxPos, setMaxPos] = useState(30);
  const [tools, setTools] = useState({
    get_quote: true, get_kline: true, get_financials: true,
    get_news: true, place_order: true, get_positions: true, get_screener_result: false,
  });
  const cur = prototypes.find(p => p.id === proto);
  const [prompt, setPrompt] = useState(cur.prompt);

  const choose = (p) => {
    setProto(p.id);
    setName(p.name);
    setPrompt(p.prompt);
  };

  const submit = () => {
    onCreate({
      name, model,
      desc: cur.desc,
      ret: 0, sharpe: 0, mdd: 0, win: 0, trades: 0, cost: 0,
      color: cur.color,
      positions: ['现金 100%'],
      thinking: `Agent 已创建，初始资金 ¥${capital.toLocaleString()}，等待首次决策...`,
    });
  };

  return (
    <div onClick={onClose} style={{
      position: 'absolute', inset: 0, background: 'oklch(0 0 0 / 0.65)', zIndex: 100,
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 40
    }}>
      <div onClick={e => e.stopPropagation()} className="panel" style={{
        width: 820, maxHeight: '86vh', display: 'flex', flexDirection: 'column',
        boxShadow: '0 20px 60px oklch(0 0 0 / 0.7)'
      }}>
        <div className="panel-head" style={{ background: 'var(--brand-soft)' }}>
          <Icon name="sparkle" size={12} style={{ color: 'var(--brand)' }}/>
          <span className="panel-title">新增 AI Agent</span>
          <span className="mono" style={{ fontSize: 10, color: 'var(--text-ghost)', marginLeft: 4 }}>从操盘手原型或空白模板创建</span>
          <span style={{ flex: 1 }}/>
          <button className="btn ghost" onClick={onClose} style={{ padding: '2px 6px' }}><Icon name="close" size={12}/></button>
        </div>

        <div style={{ padding: 16, overflow: 'auto', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {/* LEFT: persona + prompt */}
          <div>
            <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6 }}>① 选择操盘手原型</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 14 }}>
              {prototypes.map(p => (
                <div key={p.id} onClick={() => choose(p)} style={{
                  padding: '8px 10px', cursor: 'pointer',
                  background: proto === p.id ? 'var(--bg-3)' : 'var(--bg-2)',
                  border: '1px solid ' + (proto === p.id ? p.color : 'var(--panel-border-soft)'),
                  borderRadius: 4,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 6, height: 6, borderRadius: 2, background: p.color }}/>
                    <div style={{ color: 'var(--text-hi)', fontWeight: 600, fontSize: 12 }}>{p.name}</div>
                  </div>
                  <div style={{ fontSize: 10.5, color: 'var(--text-faint)', marginTop: 2 }}>{p.desc}</div>
                </div>
              ))}
            </div>

            <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>② Persona Prompt</div>
            <textarea value={prompt} onChange={e => setPrompt(e.target.value)} style={{
              width: '100%', height: 196, padding: 10,
              background: 'var(--bg-2)', border: '1px solid var(--panel-border)',
              color: 'var(--text)', borderRadius: 4, fontFamily: 'var(--f-mono)', fontSize: 11, resize: 'vertical',
              lineHeight: 1.6,
            }}/>
          </div>

          {/* RIGHT: config */}
          <div>
            <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>③ Agent 名称</div>
            <input value={name} onChange={e => setName(e.target.value)} style={{
              width: '100%', padding: 8, background: 'var(--bg-2)', border: '1px solid var(--panel-border)',
              color: 'var(--text-hi)', borderRadius: 4, fontFamily: 'var(--f-ui)', fontSize: 12, marginBottom: 12,
            }}/>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
              <div>
                <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>④ 底层模型</div>
                <select value={model} onChange={e => setModel(e.target.value)} style={{ width: '100%', padding: 8, background: 'var(--bg-2)', border: '1px solid var(--panel-border)', color: 'var(--text-hi)', borderRadius: 4, fontSize: 12 }}>
                  <option>Claude Opus 4.5</option><option>Claude Sonnet 4.5</option>
                  <option>GPT-5</option><option>Gemini 2.0 Pro</option><option>DeepSeek V4</option>
                </select>
              </div>
              <div>
                <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>决策频率</div>
                <select value={freq} onChange={e => setFreq(e.target.value)} style={{ width: '100%', padding: 8, background: 'var(--bg-2)', border: '1px solid var(--panel-border)', color: 'var(--text-hi)', borderRadius: 4, fontSize: 12 }}>
                  <option>每 30 分钟</option><option>每小时</option><option>每日收盘后</option><option>仅信号触发</option>
                </select>
              </div>
            </div>

            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>⑤ 初始资金</div>
              <div style={{ display: 'flex', gap: 6 }}>
                {[100000, 500000, 1000000, 5000000].map(v => (
                  <div key={v} onClick={() => setCapital(v)} style={{
                    flex: 1, padding: '6px 0', textAlign: 'center', cursor: 'pointer',
                    background: capital === v ? 'var(--bg-3)' : 'var(--bg-2)',
                    border: '1px solid ' + (capital === v ? 'var(--brand)' : 'var(--panel-border-soft)'),
                    borderRadius: 3, fontSize: 11, color: capital === v ? 'var(--text-hi)' : 'var(--text-dim)',
                    fontFamily: 'var(--f-mono)',
                  }}>¥{(v/10000).toFixed(0)}万</div>
                ))}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
              <div>
                <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>⑥ 止损阈值</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="range" min={2} max={20} value={stopLoss} onChange={e => setStopLoss(+e.target.value)} style={{ flex: 1, accentColor: 'var(--down)' }}/>
                  <span className="mono down" style={{ fontSize: 12, width: 40, textAlign: 'right', fontWeight: 600 }}>-{stopLoss}%</span>
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>单票上限</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="range" min={5} max={50} value={maxPos} onChange={e => setMaxPos(+e.target.value)} style={{ flex: 1, accentColor: 'var(--brand)' }}/>
                  <span className="mono" style={{ fontSize: 12, width: 40, textAlign: 'right', color: 'var(--brand)', fontWeight: 600 }}>{maxPos}%</span>
                </div>
              </div>
            </div>

            <div>
              <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>⑦ 授予工具 · 通达信 Python 接口</div>
              <div style={{ padding: 8, background: 'var(--bg-2)', border: '1px solid var(--panel-border-soft)', borderRadius: 4 }}>
                {[
                  ['get_quote', '实时行情', true],
                  ['get_kline', 'K线数据', true],
                  ['get_financials', '财务指标', false],
                  ['get_news', '新闻舆情', false],
                  ['get_screener_result', '调用选股器', false],
                  ['place_order', '下单交易', true],
                  ['get_positions', '查询持仓', false],
                ].map(([k, desc, danger]) => (
                  <label key={k} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 2px', fontSize: 11, cursor: 'pointer' }}>
                    <input type="checkbox" checked={tools[k]} onChange={e => setTools(t => ({...t, [k]: e.target.checked}))} style={{ accentColor: 'var(--brand)' }}/>
                    <span className="mono" style={{ color: 'var(--info)', minWidth: 140 }}>{k}()</span>
                    <span style={{ color: 'var(--text-faint)', flex: 1 }}>{desc}</span>
                    {danger && <span className="pill" style={{ fontSize: 9, color: 'var(--warn)', border: '1px solid var(--warn)' }}>高权限</span>}
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div style={{ padding: 12, borderTop: '1px solid var(--panel-border-soft)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-faint)' }}>
            <Icon name="sparkle" size={10} style={{ color: 'var(--brand)' }}/> 创建后将自动运行 90 天历史回测，约需 2-4 分钟
          </div>
          <span style={{ flex: 1 }}/>
          <button className="btn ghost" onClick={onClose}>取消</button>
          <button className="btn primary" onClick={submit}><Icon name="play" size={12}/> 创建 Agent 并开始回测</button>
        </div>
      </div>
    </div>
  );
}

function AgentCompareChart({ agents, selected }) {
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

    const padL = 6, padR = 40, padT = 10, padB = 16;
    const W = size.w, H = size.h;
    ctx.fillStyle = 'oklch(0.14 0.010 260)'; ctx.fillRect(0, 0, W, H);
    const N = 90;
    const curves = agents.map(a => {
      const r = seedRand(a.id.length * 31);
      const arr = []; let v = 100;
      for (let i = 0; i < N; i++) { v += a.ret / N + (r() - 0.5) * (a.mdd < -10 ? 2 : 0.8); arr.push(v); }
      return { ...a, arr };
    });
    const all = curves.flatMap(c => c.arr);
    const mn = Math.min(...all), mx = Math.max(...all);
    const pad = (mx - mn) * 0.05; const lo = mn - pad, hi = mx + pad;
    const x = i => padL + (i / (N - 1)) * (W - padL - padR);
    const y = v => padT + ((hi - v) / (hi - lo)) * (H - padT - padB);

    ctx.strokeStyle = 'oklch(0.22 0.010 260 / 0.4)'; ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const yy = padT + (H - padT - padB) / 4 * i;
      ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(W - padR, yy); ctx.stroke();
      ctx.fillStyle = 'oklch(0.52 0.012 260)'; ctx.font = '9px JetBrains Mono';
      ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      ctx.fillText((hi - (hi - lo) / 4 * i).toFixed(0), W - padR + 3, yy);
    }
    ctx.strokeStyle = 'oklch(0.52 0.012 260 / 0.5)'; ctx.setLineDash([3, 3]);
    ctx.beginPath(); ctx.moveTo(padL, y(100)); ctx.lineTo(W - padR, y(100)); ctx.stroke(); ctx.setLineDash([]);

    curves.forEach(c => {
      const sel = c.id === selected;
      const clr = c.id === 'linyuan' ? 'oklch(0.82 0.18 75)' :
        c.id === 'fuyou' ? 'oklch(0.70 0.24 25)' :
        c.id === 'buffet' ? 'oklch(0.74 0.15 235)' :
        c.id === 'soros' ? 'oklch(0.72 0.18 305)' : 'oklch(0.78 0.22 148)';
      ctx.strokeStyle = sel ? clr : clr.replace(')', ' / 0.35)');
      ctx.lineWidth = sel ? 2 : 1;
      ctx.beginPath();
      c.arr.forEach((v, i) => { if (i === 0) ctx.moveTo(x(i), y(v)); else ctx.lineTo(x(i), y(v)); });
      ctx.stroke();
    });
  }, [size, agents, selected]);
  return <canvas ref={ref} style={{ display: 'block' }}/>;
}

function PromptModal({ onClose }) {
  return (
    <div onClick={onClose} style={{
      position: 'absolute', inset: 0, background: 'oklch(0 0 0 / 0.6)', zIndex: 100,
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 40
    }}>
      <div onClick={e => e.stopPropagation()} className="panel" style={{
        width: 720, maxHeight: '80vh', display: 'flex', flexDirection: 'column',
        boxShadow: '0 12px 40px oklch(0 0 0 / 0.6)'
      }}>
        <div className="panel-head">
          <span className="panel-title">创建自定义 AI Agent</span>
          <span style={{ flex: 1 }}/>
          <button className="btn ghost" onClick={onClose} style={{ padding: '2px 6px' }}><Icon name="close" size={12}/></button>
        </div>
        <div style={{ padding: 16, overflow: 'auto' }}>
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>操盘手名称</div>
            <input type="text" defaultValue="我的Agent · 段永平风格" style={{
              width: '100%', padding: 8, background: 'var(--bg-2)', border: '1px solid var(--panel-border)',
              color: 'var(--text-hi)', borderRadius: 4, fontFamily: 'var(--f-ui)', fontSize: 12
            }}/>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            <div>
              <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>底层模型</div>
              <select style={{ width: '100%', padding: 8, background: 'var(--bg-2)', border: '1px solid var(--panel-border)', color: 'var(--text-hi)', borderRadius: 4 }}>
                <option>Claude Opus 4.5</option><option>GPT-5</option><option>Gemini 2.0 Pro</option><option>DeepSeek V4</option>
              </select>
            </div>
            <div>
              <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>决策频率</div>
              <select style={{ width: '100%', padding: 8, background: 'var(--bg-2)', border: '1px solid var(--panel-border)', color: 'var(--text-hi)', borderRadius: 4 }}>
                <option>每 30 分钟</option><option>每小时</option><option>每日收盘后</option>
              </select>
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10.5, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>Persona Prompt</div>
            <textarea style={{
              width: '100%', height: 180, padding: 10,
              background: 'var(--bg-2)', border: '1px solid var(--panel-border)',
              color: 'var(--text)', borderRadius: 4, fontFamily: 'var(--f-mono)', fontSize: 11.5, resize: 'vertical'
            }} defaultValue={`你是段永平，价值投资者。你的核心理念：\n• 本分：只做看得懂的生意\n• 平常心：不追逐热点\n• 敢为天下后：等待最好的入场点\n• 长期持有龙头企业\n\n可用工具：get_quote, get_financials, place_order...`}/>
          </div>
        </div>
        <div style={{ padding: 12, borderTop: '1px solid var(--panel-border-soft)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button className="btn ghost" onClick={onClose}>取消</button>
          <button className="btn primary"><Icon name="play" size={12}/> 创建并开始回测</button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { AgentLab, CreateAgentModal, AutonomousScheduler });

// ═══════════════════════════════════════════════════════════════════════
// 24/7 Autonomous Scheduler — Agent 持续工作，事件驱动，无需人工触发
// ═══════════════════════════════════════════════════════════════════════
function AutonomousScheduler() {
  const [autonomous, setAutonomous] = useState(true);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // Market clock — 24/7 across sessions
  const hour = now.getHours();
  const minute = now.getMinutes();
  const day = now.getDay(); // 0=Sun, 6=Sat
  const isWeekend = day === 0 || day === 6;
  const isMorning = hour >= 9 && (hour < 11 || (hour === 11 && minute < 30));
  const isAfternoon = hour >= 13 && hour < 15;
  const isTrading = !isWeekend && (isMorning || isAfternoon);
  const isPreMarket = !isWeekend && ((hour === 9 && minute < 30) || hour === 8);
  const isAfterHours = !isWeekend && hour >= 15 && hour < 18;
  const isOvernight = hour >= 18 || hour < 8 || isWeekend;

  // Phase for the current moment
  const phase =
    isTrading ? { label: '盘中交易', color: 'var(--up)', icon: 'play' } :
    isPreMarket ? { label: '盘前准备', color: 'var(--warn)', icon: 'sparkle' } :
    isAfterHours ? { label: '盘后复盘', color: 'var(--info)', icon: 'brain' } :
    { label: '夜间研究', color: 'var(--purple)', icon: 'sparkle' };

  // Schedule grid — shows Agent's 24h activities
  const schedule = [
    { start: 0,  end: 6,  phase: '夜间', task: '回测新策略 · 参数优化 · 扫描海外市场',                count: 3 },
    { start: 6,  end: 8,  phase: '早间', task: '抓取隔夜新闻 · 分析美股/港股 · 生成今日情报简报',     count: 2 },
    { start: 8,  end: 9.5, phase: '盘前', task: '筛选盘前异动 · 预测开盘方向 · 更新持仓风险敞口',    count: 5 },
    { start: 9.5, end: 11.5, phase: '早盘', task: '监控 5200 只股票 · Tick 级决策 · 执行买卖信号',  count: 5, live: true },
    { start: 11.5, end: 13, phase: '午间', task: '午盘快报 · 调仓评估 · 基本面更新',                count: 4 },
    { start: 13, end: 15,  phase: '午盘', task: '持续盯盘 · 止损止盈触发 · 尾盘撮合',               count: 5, live: true },
    { start: 15, end: 18,  phase: '盘后', task: '日报生成 · 绩效归因 · 明日策略草稿',                count: 5 },
    { start: 18, end: 24,  phase: '夜间', task: '大模型调用研究 · 公告挖掘 · 跨市场联动',            count: 3 },
  ];

  const curHour = hour + minute / 60;

  // Triggers — event-driven, replaces human clicks
  const triggers = [
    { icon: 'clock',  name: '定时器',     desc: '每 15 秒评估一次持仓', n: '∞/日' },
    { icon: 'bolt',   name: '价格事件',   desc: '±2% 波动立即触发决策', n: '47 次' },
    { icon: 'news',   name: '新闻/公告',  desc: 'RSS · Wind · 雪球实时订阅', n: '312 条' },
    { icon: 'chart',  name: '技术信号',   desc: 'MA / MACD / 量能 形态触发', n: '28 次' },
    { icon: 'bell',   name: '异常告警',   desc: '回撤 · 黑天鹅 · 流动性', n: '0 次' },
    { icon: 'link',   name: '其它 Agent', desc: '多 Agent 协作 · 共享信号', n: '84 次' },
  ];

  // Currently running — live tasks
  const running = [
    { agent: '林园风格',   task: '监控白酒板块 tick',    progress: 74, eta: '持续' },
    { agent: '浮游短线',   task: '扫描涨停板异动',       progress: 42, eta: '持续' },
    { agent: '巴菲特风格', task: 'ROE 季度更新 (第 82/500)', progress: 16, eta: '3h' },
    { agent: '索罗斯反身性', task: '宏观情绪指数计算', progress: 90, eta: '持续' },
    { agent: '量化中性',   task: '182 只多头信号刷新',   progress: 65, eta: '持续' },
  ];

  const fmt = (d) => d.toTimeString().slice(0, 8);

  return (
    <div className="panel" style={{ padding: 14, background:
      'linear-gradient(135deg, oklch(0.16 0.02 160) 0%, oklch(0.13 0.01 260) 60%)',
      border: '1px solid ' + phase.color + '44' }}>

      {/* top strip: status + clock + master switch */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 12 }}>
        <div style={{
          width: 42, height: 42, borderRadius: '50%',
          background: autonomous ? phase.color + '22' : 'var(--bg-3)',
          border: '2px solid ' + (autonomous ? phase.color : 'var(--panel-border)'),
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          position: 'relative',
        }}>
          <Icon name={phase.icon} size={16} style={{ color: autonomous ? phase.color : 'var(--text-ghost)' }}/>
          {autonomous && (
            <div style={{
              position: 'absolute', inset: -4, borderRadius: '50%',
              border: '2px solid ' + phase.color, opacity: 0.4,
              animation: 'pulse-ring 2s ease-out infinite',
            }}/>
          )}
        </div>

        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <span style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Autonomous Mode · 24/7 无人值守</span>
            {autonomous && <span className="pill" style={{ background: phase.color + '22', border: '1px solid ' + phase.color, color: phase.color, fontSize: 10 }}>
              <span className="live-dot" style={{ color: phase.color }}/> {phase.label}
            </span>}
          </div>
          <div style={{ marginTop: 3, display: 'flex', alignItems: 'baseline', gap: 14 }}>
            <span className="serif" style={{ fontSize: 22, color: 'var(--text-hi)', fontWeight: 600, letterSpacing: '-0.01em' }}>
              {autonomous ? '5 个 Agent 正在持续工作' : '已暂停 · 等待手动触发'}
            </span>
            <span className="mono" style={{ fontSize: 12, color: 'var(--text-faint)' }}>
              今日已决策 <span style={{ color: 'var(--up)', fontWeight: 600 }}>847</span> 次 · 
              执行 <span style={{ color: 'var(--brand)', fontWeight: 600 }}>23</span> 笔 · 
              拦截 <span style={{ color: 'var(--down)', fontWeight: 600 }}>14</span> 次
            </span>
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          <div className="mono" style={{ fontSize: 20, color: 'var(--text-hi)', fontWeight: 500, letterSpacing: '0.02em' }}>{fmt(now)}</div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 1 }}>
            {['周日','周一','周二','周三','周四','周五','周六'][day]} · 运行 47 天 16h
          </div>
        </div>

        {/* master switch */}
        <div onClick={() => setAutonomous(!autonomous)} style={{
          width: 54, height: 30, borderRadius: 15, padding: 3, cursor: 'pointer',
          background: autonomous ? 'var(--up)' : 'var(--bg-3)',
          border: '1px solid ' + (autonomous ? 'var(--up)' : 'var(--panel-border)'),
          position: 'relative', transition: 'all 0.2s',
        }}>
          <div style={{
            width: 22, height: 22, borderRadius: '50%', background: 'white',
            transform: autonomous ? 'translateX(24px)' : 'translateX(0)',
            transition: 'transform 0.2s', boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
          }}/>
        </div>
      </div>

      {/* Body: 3-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1.1fr', gap: 14 }}>

        {/* 24h timeline */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <span style={{ fontSize: 10, color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>24h 自动任务日历</span>
            <span style={{ flex: 1 }}/>
            <span className="mono" style={{ fontSize: 9.5, color: 'var(--text-ghost)' }}>当前 {curHour.toFixed(1)}h</span>
          </div>
          <div style={{ position: 'relative', height: 56, background: 'var(--bg-2)', borderRadius: 4, overflow: 'hidden', border: '1px solid var(--panel-border-soft)' }}>
            {/* hour gridlines */}
            {[0,3,6,9,12,15,18,21].map(h => (
              <div key={h} style={{ position: 'absolute', left: (h/24)*100 + '%', top: 0, bottom: 0, width: 1, background: 'var(--panel-border-soft)' }}/>
            ))}
            {/* task blocks */}
            {schedule.map((s, i) => {
              const isPast = s.end <= curHour;
              const isActive = s.start <= curHour && s.end > curHour;
              const color =
                s.phase === '夜间' ? 'var(--purple)' :
                s.phase === '早间' || s.phase === '盘前' ? 'var(--warn)' :
                s.phase === '早盘' || s.phase === '午盘' ? 'var(--up)' :
                s.phase === '午间' ? 'var(--info)' :
                'var(--info)';
              return (
                <div key={i} title={`${s.phase} ${s.start}:00-${s.end}:00 · ${s.task}`} style={{
                  position: 'absolute',
                  left: (s.start/24)*100 + '%',
                  width: ((s.end - s.start)/24)*100 + '%',
                  top: 8, bottom: 8,
                  background: isActive ? color : color + '44',
                  borderLeft: '2px solid ' + color,
                  opacity: isPast && !isActive ? 0.35 : 1,
                  display: 'flex', alignItems: 'center', padding: '0 5px',
                  overflow: 'hidden', gap: 4,
                }}>
                  {isActive && <span className="live-dot" style={{ color: 'white', flexShrink: 0 }}/>}
                  <span style={{ fontSize: 9, color: isActive ? 'white' : color, fontWeight: 600, whiteSpace: 'nowrap' }}>{s.phase}</span>
                </div>
              );
            })}
            {/* NOW marker */}
            <div style={{
              position: 'absolute', left: (curHour/24)*100 + '%',
              top: -2, bottom: -2, width: 2,
              background: 'var(--text-hi)',
              boxShadow: '0 0 6px var(--text-hi)',
            }}>
              <div style={{ position: 'absolute', top: -6, left: -4, width: 10, height: 10, borderRadius: '50%', background: 'var(--text-hi)' }}/>
            </div>
          </div>
          {/* hour labels */}
          <div style={{ display: 'flex', fontSize: 9, color: 'var(--text-ghost)', marginTop: 3, fontFamily: 'var(--f-mono)' }}>
            {[0,3,6,9,12,15,18,21,24].map(h => (
              <span key={h} style={{ flex: h === 24 ? 0 : 1 }}>{String(h).padStart(2,'0')}:00</span>
            ))}
          </div>

          {/* current phase description */}
          <div style={{ marginTop: 8, padding: 8, background: 'var(--bg-2)', borderRadius: 3, border: '1px solid ' + phase.color + '33' }}>
            <div style={{ fontSize: 10, color: phase.color, letterSpacing: '0.06em', textTransform: 'uppercase', fontWeight: 600 }}>
              ▸ 当前正在执行
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--text-hi)', marginTop: 3, lineHeight: 1.4 }}>
              {schedule.find(s => s.start <= curHour && s.end > curHour)?.task || '待机中'}
            </div>
          </div>
        </div>

        {/* Event triggers */}
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8 }}>触发方式 · 事件驱动</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            {triggers.map(t => (
              <div key={t.name} style={{
                padding: '7px 9px', background: 'var(--bg-2)',
                border: '1px solid var(--panel-border-soft)', borderRadius: 3,
                display: 'flex', alignItems: 'center', gap: 8,
              }}>
                <Icon name={t.icon} size={12} style={{ color: 'var(--brand)', flexShrink: 0 }}/>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-hi)', fontWeight: 500, display: 'flex', gap: 4, alignItems: 'baseline' }}>
                    <span>{t.name}</span>
                    <span style={{ flex: 1 }}/>
                    <span className="mono" style={{ fontSize: 9, color: 'var(--up)' }}>{t.n}</span>
                  </div>
                  <div style={{ fontSize: 9.5, color: 'var(--text-faint)', marginTop: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.desc}</div>
                </div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 8, padding: '6px 9px', background: 'var(--up-bg)', borderRadius: 3, border: '1px solid var(--up)' }}>
            <div style={{ fontSize: 10.5, color: 'var(--up)', display: 'flex', alignItems: 'center', gap: 5 }}>
              <Icon name="check" size={10}/>
              <span style={{ fontWeight: 600 }}>无需人工触发</span>
              <span style={{ color: 'var(--text-faint)' }}>· Agent 自主响应所有事件</span>
            </div>
          </div>
        </div>

        {/* Running agents */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontSize: 10, color: 'var(--text-faint)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>Agent 实时运行</span>
            <span style={{ flex: 1 }}/>
            <span className="pill up" style={{ fontSize: 9.5 }}><span className="live-dot" style={{ color: 'var(--up)' }}/> 5/5 在线</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            {running.map((r, i) => (
              <div key={i} style={{ padding: '6px 9px', background: 'var(--bg-2)', border: '1px solid var(--panel-border-soft)', borderRadius: 3 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, fontSize: 10.5 }}>
                  <Icon name="sparkle" size={9} style={{ color: 'var(--brand)' }}/>
                  <span style={{ color: 'var(--text-hi)', fontWeight: 500 }}>{r.agent}</span>
                  <span style={{ flex: 1 }}/>
                  <span className="mono" style={{ fontSize: 9, color: 'var(--text-ghost)' }}>{r.eta}</span>
                </div>
                <div style={{ fontSize: 9.5, color: 'var(--text-faint)', marginTop: 2, marginBottom: 3 }}>▸ {r.task}</div>
                <div style={{ height: 3, background: 'var(--bg-3)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ width: r.progress + '%', height: '100%', background: 'var(--up)' }}/>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// pulse animation for the status indicator
if (typeof document !== 'undefined' && !document.getElementById('autonomous-styles')) {
  const s = document.createElement('style');
  s.id = 'autonomous-styles';
  s.textContent = `@keyframes pulse-ring { 0% { transform: scale(0.9); opacity: 0.6; } 100% { transform: scale(1.3); opacity: 0; } }`;
  document.head.appendChild(s);
}
