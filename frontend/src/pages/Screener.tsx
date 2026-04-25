// NOTE: This page is awaiting Phase 3 backend.
// All previously-hardcoded sample stock data, fake screening results, fake
// saved-scheme counts, fake sector distribution and the placeholder market-cap
// chart have been removed. The factor-filter UI shell is retained so the user
// can see what the screener WILL do once /api/screener is wired up.
import { useState } from 'react';
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
};

type SortKey = 'score' | 'pct' | 'mc';

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

  const enabledN = factors.filter((f) => f.enabled).length;

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

        {/* CENTER: results — empty until Phase 3 backend exists */}
        <div className="panel flex flex-col min-h-0">
          <div className="panel-head">
            <span className="panel-title">筛选结果</span>
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
            <button className="btn primary" style={{ padding: '4px 10px' }} disabled>
              <Icon name="backtest" size={12} /> 用此池回测
            </button>
          </div>

          <div
            className="flex-1 flex items-center justify-center"
            style={{ padding: 24 }}
          >
            <div style={{ textAlign: 'center', maxWidth: 360 }}>
              <div
                style={{
                  fontSize: 13,
                  color: 'var(--text)',
                  marginBottom: 6,
                }}
              >
                筛选器尚未接入真实数据
              </div>
              <div
                className="uppercase"
                style={{
                  fontSize: 10.5,
                  color: 'var(--text-faint)',
                  letterSpacing: '0.1em',
                }}
              >
                Phase 3 backend pending
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT: distribution & saved schemes — placeholders until backend lands */}
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
            <div
              style={{
                fontSize: 11,
                color: 'var(--text-ghost)',
                padding: '12px 0',
                textAlign: 'center',
              }}
            >
              等待后端数据
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
              市值分布 (亿) · MarketCap
            </div>
            <div
              style={{
                fontSize: 11,
                color: 'var(--text-ghost)',
                padding: '12px 0',
                textAlign: 'center',
              }}
            >
              等待后端数据
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
            <div
              style={{
                fontSize: 11,
                color: 'var(--text-ghost)',
                padding: '12px 0',
                textAlign: 'center',
              }}
            >
              尚无保存方案
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
