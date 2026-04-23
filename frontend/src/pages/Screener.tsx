import { useMemo, useState } from 'react';
import { Icon } from '../components/Icon';

// ─── types ─────────────────────────────────────────────────────────────────
type FactorOp = '<' | '>' | '=';
type FactorCat = '估值' | '财务' | '成长' | '规模' | '量价' | '技术';

type Factor = {
  id: string;
  name: string;
  op: FactorOp;
  val: number;
  enabled: boolean;
  cat: FactorCat;
  field?: keyof StockRow;
};

type StockRow = {
  code: string;
  name: string;
  sector: string;
  price: number;
  pct: number;
  pe: number;
  pb: number;
  roe: number;
  mc: number;
  rev: number;
  vol5: number;
  maCross: 0 | 1;
  rsi: number;
  score: number;
};

type SortKey = 'score' | 'pct' | 'mc';

// ─── sample data ────────────────────────────────────────────────────────────
// NOTE: Phase 3 will replace this with a real /api/screener endpoint that hits
// TDX + fundamentals. For now we hard-code a representative HS300 slice so the
// UI is interactive and the filter pipeline can be validated end-to-end.
const SAMPLE_STOCKS: StockRow[] = [
  { code: '600519', name: '贵州茅台', sector: '食品饮料', price: 1682.30, pct: 1.24, pe: 28.4, pb: 8.6, roe: 31.2, mc: 21130, rev: 16.5, vol5: 3200, maCross: 1, rsi: 58, score: 92 },
  { code: '601318', name: '中国平安', sector: '银行保险', price: 48.21, pct: 0.82, pe: 8.2, pb: 1.1, roe: 12.4, mc: 8782, rev: 4.8, vol5: 12800, maCross: 1, rsi: 52, score: 78 },
  { code: '000858', name: '五粮液', sector: '食品饮料', price: 152.40, pct: 2.15, pe: 21.7, pb: 5.4, roe: 24.1, mc: 5916, rev: 14.2, vol5: 8200, maCross: 1, rsi: 62, score: 86 },
  { code: '601398', name: '工商银行', sector: '银行保险', price: 5.62, pct: -0.35, pe: 4.8, pb: 0.58, roe: 11.8, mc: 20014, rev: 2.1, vol5: 62000, maCross: 0, rsi: 48, score: 64 },
  { code: '000333', name: '美的集团', sector: '家用电器', price: 72.18, pct: 1.05, pe: 14.2, pb: 2.8, roe: 22.6, mc: 5032, rev: 8.4, vol5: 15800, maCross: 1, rsi: 55, score: 81 },
  { code: '600036', name: '招商银行', sector: '银行保险', price: 34.85, pct: 0.46, pe: 6.4, pb: 0.98, roe: 15.2, mc: 8780, rev: 3.2, vol5: 24000, maCross: 1, rsi: 50, score: 73 },
  { code: '300750', name: '宁德时代', sector: '电池', price: 208.50, pct: 3.42, pe: 18.8, pb: 3.9, roe: 18.4, mc: 9161, rev: 22.4, vol5: 18500, maCross: 1, rsi: 68, score: 83 },
  { code: '601888', name: '中国中免', sector: '商业贸易', price: 65.12, pct: -1.24, pe: 22.1, pb: 3.2, roe: 14.8, mc: 1348, rev: -4.2, vol5: 9600, maCross: 0, rsi: 38, score: 58 },
  { code: '600276', name: '恒瑞医药', sector: '医药生物', price: 48.60, pct: 0.92, pe: 52.4, pb: 7.1, roe: 12.2, mc: 3099, rev: 19.3, vol5: 11200, maCross: 1, rsi: 61, score: 68 },
  { code: '000651', name: '格力电器', sector: '家用电器', price: 42.15, pct: 0.68, pe: 8.1, pb: 1.9, roe: 25.8, mc: 2364, rev: 6.8, vol5: 14500, maCross: 1, rsi: 54, score: 79 },
  { code: '600900', name: '长江电力', sector: '公用事业', price: 28.80, pct: 0.18, pe: 19.2, pb: 2.9, roe: 15.6, mc: 7046, rev: 9.1, vol5: 8200, maCross: 1, rsi: 52, score: 72 },
  { code: '601012', name: '隆基绿能', sector: '电子', price: 22.15, pct: -2.08, pe: 12.4, pb: 2.1, roe: 17.2, mc: 1680, rev: 28.6, vol5: 21000, maCross: 0, rsi: 35, score: 61 },
  { code: '002594', name: '比亚迪', sector: '汽车', price: 248.30, pct: 4.12, pe: 24.8, pb: 4.6, roe: 20.8, mc: 7224, rev: 34.2, vol5: 8800, maCross: 1, rsi: 72, score: 85 },
  { code: '600030', name: '中信证券', sector: '银行保险', price: 21.42, pct: 1.58, pe: 12.8, pb: 1.2, roe: 9.6, mc: 3171, rev: 1.4, vol5: 32000, maCross: 1, rsi: 56, score: 66 },
  { code: '000568', name: '泸州老窖', sector: '食品饮料', price: 168.40, pct: 1.82, pe: 19.8, pb: 6.2, roe: 28.4, mc: 2477, rev: 18.6, vol5: 4800, maCross: 1, rsi: 64, score: 88 },
  { code: '300059', name: '东方财富', sector: '银行保险', price: 12.85, pct: 2.48, pe: 24.2, pb: 2.4, roe: 10.8, mc: 2033, rev: 5.2, vol5: 68000, maCross: 1, rsi: 66, score: 69 },
  { code: '601166', name: '兴业银行', sector: '银行保险', price: 15.82, pct: 0.12, pe: 4.2, pb: 0.48, roe: 13.2, mc: 3286, rev: 1.8, vol5: 36000, maCross: 0, rsi: 49, score: 62 },
  { code: '002415', name: '海康威视', sector: '电子', price: 32.56, pct: 1.14, pe: 18.6, pb: 3.4, roe: 16.8, mc: 3012, rev: 12.4, vol5: 15600, maCross: 1, rsi: 58, score: 76 },
  { code: '600887', name: '伊利股份', sector: '食品饮料', price: 27.85, pct: -0.42, pe: 16.8, pb: 3.1, roe: 19.6, mc: 1773, rev: 5.8, vol5: 18200, maCross: 0, rsi: 45, score: 71 },
  { code: '601888', name: '中国石油', sector: '公用事业', price: 8.92, pct: 0.68, pe: 7.8, pb: 1.02, roe: 11.2, mc: 16320, rev: 3.4, vol5: 48000, maCross: 1, rsi: 53, score: 67 },
];

// map factor id -> stock row field + comparator
const FACTOR_FIELD: Record<string, keyof StockRow> = {
  pe: 'pe',
  pb: 'pb',
  roe: 'roe',
  mktcap: 'mc',
  rev_g: 'rev',
  vol5: 'vol5',
  ma_cross: 'maCross',
  rsi: 'rsi',
};

function passes(s: StockRow, f: Factor): boolean {
  const key = FACTOR_FIELD[f.id];
  if (!key) return true;
  const v = s[key] as number;
  if (v == null) return true;
  if (f.op === '<') return v < f.val;
  if (f.op === '>') return v > f.val;
  return v === f.val;
}

// ─── styling helpers ───────────────────────────────────────────────────────
const CAT_COLOR: Record<FactorCat, string> = {
  估值: 'var(--info)',
  财务: 'var(--brand)',
  规模: 'var(--text-dim)',
  成长: 'var(--purple)',
  量价: 'var(--up)',
  技术: 'var(--down)',
};

const CATS: FactorCat[] = ['估值', '财务', '成长', '规模', '量价', '技术'];

function pctCls(v: number) {
  if (v > 0) return 'up';
  if (v < 0) return 'down';
  return '';
}

function fmtPct(v: number, digits = 2) {
  const sign = v > 0 ? '+' : '';
  return `${sign}${v.toFixed(digits)}%`;
}

// ─── page ──────────────────────────────────────────────────────────────────
export function Screener() {
  const [factors, setFactors] = useState<Factor[]>([
    { id: 'pe', name: '市盈率 PE-TTM', op: '<', val: 25, enabled: true, cat: '估值' },
    { id: 'pb', name: '市净率 PB', op: '<', val: 3.0, enabled: true, cat: '估值' },
    { id: 'roe', name: 'ROE (近4季)', op: '>', val: 15, enabled: true, cat: '财务' },
    { id: 'mktcap', name: '总市值 (亿)', op: '>', val: 100, enabled: true, cat: '规模' },
    { id: 'rev_g', name: '营收增速 YoY', op: '>', val: 5, enabled: true, cat: '成长' },
    { id: 'vol5', name: '5日均量', op: '>', val: 5000, enabled: false, cat: '量价' },
    { id: 'ma_cross', name: 'MA5上穿MA20', op: '=', val: 1, enabled: false, cat: '技术' },
    { id: 'rsi', name: 'RSI(14)', op: '<', val: 70, enabled: false, cat: '技术' },
  ]);
  const [sort, setSort] = useState<SortKey>('score');

  const toggle = (id: string) =>
    setFactors((fs) => fs.map((f) => (f.id === id ? { ...f, enabled: !f.enabled } : f)));
  const updateVal = (id: string, val: number) =>
    setFactors((fs) => fs.map((f) => (f.id === id ? { ...f, val } : f)));
  const updateOp = (id: string, op: FactorOp) =>
    setFactors((fs) => fs.map((f) => (f.id === id ? { ...f, op } : f)));

  // filter + sort client-side against the sample stocks
  const filtered = useMemo(() => {
    const active = factors.filter((f) => f.enabled);
    const rows = SAMPLE_STOCKS.filter((s) => active.every((f) => passes(s, f)));
    rows.sort((a, b) => {
      if (sort === 'score') return b.score - a.score;
      if (sort === 'pct') return b.pct - a.pct;
      return b.mc - a.mc;
    });
    return rows;
  }, [factors, sort]);

  const enabledN = factors.filter((f) => f.enabled).length;

  // sector distribution from filtered results
  const sectorDist = useMemo(() => {
    const counts = new Map<string, number>();
    filtered.forEach((s) => counts.set(s.sector, (counts.get(s.sector) ?? 0) + 1));
    const total = filtered.length || 1;
    return Array.from(counts.entries())
      .map(([sec, n]) => ({ sec, n, pct: Math.round((n / total) * 100) }))
      .sort((a, b) => b.n - a.n);
  }, [filtered]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Phase-3 banner */}
      <div
        className="text-xs"
        style={{
          padding: '8px 16px',
          background: 'var(--brand-soft)',
          borderBottom: '1px solid var(--brand-border)',
          color: 'var(--brand)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <Icon name="filter" size={12} />
        <span>筛选器接入实时数据在 Phase 3 · Real-time screener backend arrives in Phase 3</span>
      </div>

      {/* Header */}
      <div className="px-6 pt-5 pb-3">
        <h1 className="text-2xl text-text-hi font-semibold">选股器</h1>
        <div className="text-text-faint text-xs mt-1 tracking-wide uppercase">
          Screener · Multi-factor Stock Filter
        </div>
      </div>

      <div
        className="flex-1 min-h-0 grid gap-3 px-3 pb-3"
        style={{ gridTemplateColumns: '260px minmax(360px,1fr) 240px' }}
      >
        {/* LEFT: factors */}
        <div className="panel flex flex-col min-h-0">
          <div className="panel-head">
            <span className="panel-title">因子筛选条件</span>
            <span className="pill brand">{enabledN} 启用</span>
            <span className="flex-1" />
            <button className="btn ghost" style={{ padding: '2px 6px', fontSize: 11 }}>
              +
            </button>
          </div>

          <div className="flex-1 overflow-auto py-1">
            {CATS.map((cat) => {
              const items = factors.filter((f) => f.cat === cat);
              if (items.length === 0) return null;
              return (
                <div key={cat}>
                  <div
                    className="flex items-center gap-1.5 uppercase"
                    style={{
                      padding: '8px 12px 4px',
                      fontSize: 10,
                      color: 'var(--text-faint)',
                      letterSpacing: '0.12em',
                    }}
                  >
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: 1,
                        background: CAT_COLOR[cat],
                      }}
                    />
                    {cat}
                  </div>
                  {items.map((f) => (
                    <div
                      key={f.id}
                      className="flex items-center gap-2"
                      style={{
                        padding: '7px 12px',
                        opacity: f.enabled ? 1 : 0.45,
                        borderBottom: '1px solid var(--panel-border-soft)',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={f.enabled}
                        onChange={() => toggle(f.id)}
                        style={{ accentColor: 'var(--brand)' }}
                      />
                      <div className="flex-1 min-w-0">
                        <div style={{ fontSize: 11.5, color: 'var(--text)' }}>{f.name}</div>
                        <div className="flex items-center gap-1 mt-1">
                          {(['<', '>', '='] as FactorOp[]).map((op) => (
                            <span
                              key={op}
                              onClick={() => updateOp(f.id, op)}
                              className="mono cursor-pointer"
                              style={{
                                padding: '1px 6px',
                                fontSize: 10,
                                background: f.op === op ? 'var(--bg-3)' : 'transparent',
                                color:
                                  f.op === op ? 'var(--text-hi)' : 'var(--text-faint)',
                                border:
                                  '1px solid ' +
                                  (f.op === op ? 'var(--panel-border)' : 'transparent'),
                                borderRadius: 3,
                              }}
                            >
                              {op}
                            </span>
                          ))}
                          <input
                            type="number"
                            value={f.val}
                            onChange={(e) => updateVal(f.id, Number(e.target.value))}
                            className="mono"
                            style={{
                              flex: 1,
                              marginLeft: 4,
                              background: 'var(--bg-2)',
                              border: '1px solid var(--panel-border-soft)',
                              color: 'var(--text-hi)',
                              borderRadius: 3,
                              padding: '2px 6px',
                              fontSize: 11,
                              outline: 'none',
                              width: 0,
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>

          <div
            className="flex gap-1.5"
            style={{ padding: 10, borderTop: '1px solid var(--panel-border-soft)' }}
          >
            <button className="btn ghost flex-1">保存方案</button>
            <button className="btn ghost flex-1">载入</button>
          </div>
        </div>

        {/* CENTER: results */}
        <div className="panel flex flex-col min-h-0">
          <div className="panel-head">
            <span className="panel-title">筛选结果</span>
            <span
              className="mono"
              style={{
                fontSize: 16,
                color: 'var(--brand)',
                fontWeight: 600,
                letterSpacing: '-0.01em',
              }}
            >
              {filtered.length.toLocaleString()}
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>
              只股票符合条件
            </span>
            <span className="flex-1" />
            <span style={{ fontSize: 10.5, color: 'var(--text-faint)' }}>排序</span>
            {(
              [
                ['score', '综合评分'],
                ['pct', '涨幅'],
                ['mc', '市值'],
              ] as Array<[SortKey, string]>
            ).map(([k, l]) => (
              <span
                key={k}
                onClick={() => setSort(k)}
                className="cursor-pointer"
                style={{
                  padding: '2px 7px',
                  fontSize: 10.5,
                  background: sort === k ? 'var(--bg-3)' : 'transparent',
                  color: sort === k ? 'var(--text-hi)' : 'var(--text-faint)',
                  border:
                    '1px solid ' +
                    (sort === k ? 'var(--panel-border)' : 'transparent'),
                  borderRadius: 3,
                }}
              >
                {l}
              </span>
            ))}
            <button className="btn primary" style={{ padding: '4px 10px' }}>
              <Icon name="backtest" size={12} /> 用此池回测
            </button>
          </div>

          <div className="flex-1 overflow-auto">
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
                  <th />
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td
                      colSpan={12}
                      style={{
                        padding: 24,
                        textAlign: 'center',
                        color: 'var(--text-faint)',
                        fontSize: 12,
                      }}
                    >
                      没有股票符合当前筛选条件 — 尝试放宽因子阈值
                    </td>
                  </tr>
                ) : (
                  filtered.map((s, i) => (
                    <tr key={s.code}>
                      <td style={{ color: 'var(--text-ghost)' }}>{i + 1}</td>
                      <td className="mono" style={{ color: 'var(--text-faint)' }}>
                        {s.code}
                      </td>
                      <td style={{ color: 'var(--text-hi)', fontWeight: 500 }}>
                        {s.name}
                      </td>
                      <td className={`num ${pctCls(s.pct)}`}>{s.price.toFixed(2)}</td>
                      <td className={`num ${pctCls(s.pct)}`}>{fmtPct(s.pct)}</td>
                      <td className="num">{s.pe.toFixed(1)}</td>
                      <td className="num">{s.pb.toFixed(2)}</td>
                      <td className="num">{s.roe.toFixed(1)}</td>
                      <td className="num" style={{ color: 'var(--text-dim)' }}>
                        {s.mc.toLocaleString()}
                      </td>
                      <td className={`num ${s.rev >= 0 ? 'up' : 'down'}`}>
                        {fmtPct(s.rev, 1)}
                      </td>
                      <td>
                        <div className="flex items-center gap-1.5">
                          <div
                            style={{
                              width: 40,
                              height: 4,
                              background: 'var(--bg-3)',
                              borderRadius: 2,
                              overflow: 'hidden',
                            }}
                          >
                            <div
                              style={{
                                width: `${s.score}%`,
                                height: '100%',
                                background: 'var(--brand)',
                              }}
                            />
                          </div>
                          <span
                            className="mono"
                            style={{
                              fontSize: 11,
                              color: 'var(--brand)',
                              fontWeight: 600,
                            }}
                          >
                            {s.score}
                          </span>
                        </div>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button
                          className="btn ghost"
                          style={{ padding: '2px 6px', fontSize: 10 }}
                        >
                          +
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* RIGHT: distribution & saved schemes */}
        <div className="flex flex-col gap-3 min-h-0">
          <div className="panel" style={{ padding: 12 }}>
            <div
              className="uppercase"
              style={{
                fontSize: 10.5,
                color: 'var(--text-faint)',
                letterSpacing: '0.12em',
                marginBottom: 8,
              }}
            >
              行业分布 · Sector Distribution
            </div>
            {sectorDist.length === 0 ? (
              <div style={{ fontSize: 11, color: 'var(--text-ghost)' }}>—</div>
            ) : (
              sectorDist.map((r) => (
                <div key={r.sec} style={{ marginBottom: 8 }}>
                  <div
                    className="flex justify-between"
                    style={{ fontSize: 11, marginBottom: 2 }}
                  >
                    <span style={{ color: 'var(--text)' }}>{r.sec}</span>
                    <span className="mono" style={{ color: 'var(--text-faint)' }}>
                      {r.n} · {r.pct}%
                    </span>
                  </div>
                  <div
                    style={{
                      width: '100%',
                      height: 3,
                      background: 'var(--bg-3)',
                      borderRadius: 2,
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.min(100, r.pct * 2.5)}%`,
                        height: '100%',
                        background: 'var(--brand)',
                        opacity: 0.8,
                      }}
                    />
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="panel" style={{ padding: 12 }}>
            <div
              className="uppercase"
              style={{
                fontSize: 10.5,
                color: 'var(--text-faint)',
                letterSpacing: '0.12em',
                marginBottom: 10,
              }}
            >
              市值分布 (亿) · MarketCap
            </div>
            <svg viewBox="0 0 240 80" style={{ width: '100%', height: 80 }}>
              {[15, 28, 48, 62, 45, 32, 20, 12, 8, 5].map((h, i) => (
                <rect
                  key={i}
                  x={i * 24 + 2}
                  y={80 - h}
                  width={20}
                  height={h}
                  fill={i === 3 ? 'var(--brand)' : 'var(--info)'}
                  opacity={i === 3 ? 1 : 0.6}
                />
              ))}
              <line x1="0" y1="80" x2="240" y2="80" stroke="var(--panel-border)" />
            </svg>
            <div
              className="mono flex justify-between"
              style={{ fontSize: 9, color: 'var(--text-ghost)', marginTop: 3 }}
            >
              <span>50</span>
              <span>500</span>
              <span>5000</span>
            </div>
          </div>

          <div className="panel" style={{ padding: 12 }}>
            <div
              className="uppercase"
              style={{
                fontSize: 10.5,
                color: 'var(--text-faint)',
                letterSpacing: '0.12em',
                marginBottom: 8,
              }}
            >
              最近保存方案 · Saved Schemes
            </div>
            {(
              [
                ['低估值高ROE', '8个因子', 23],
                ['成长龙头', '6个因子', 47],
                ['MACD金叉反弹', '4个因子', 184],
                ['红利稳健', '5个因子', 62],
              ] as Array<[string, string, number]>
            ).map(([n, f, c]) => (
              <div
                key={n}
                className="flex items-center justify-between cursor-pointer"
                style={{
                  padding: '7px 0',
                  borderBottom: '1px solid var(--panel-border-soft)',
                }}
              >
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
    </div>
  );
}
