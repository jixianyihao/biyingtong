// Screener — multi-factor stock filter backed by POST /api/screener.
//
// 财务因子 (PE / PB / ROE / 营收增速 / 净利润增速 / 毛利率) are wired to the
// real backend (financial_cache.db, ~314 stocks). 量价 / 技术 / 规模 factors
// are visible but disabled — those need k-line data the screener cache
// doesn't have yet.
import { useMemo, useState } from 'react';
import { Icon } from '../components/Icon';
import { useScreener } from '../api/hooks';
import type {
  ScreenerFactor,
  ScreenerFilter,
  ScreenerStock,
} from '../api/types';

// ─── types ─────────────────────────────────────────────────────────────────
type FactorOp = '<' | '>' | '=';
type FactorCat = '估值' | '财务' | '成长' | '规模' | '量价' | '技术';

type UIFactor = {
  id: string;
  name: string;
  op: FactorOp;
  val: number;
  enabled: boolean;
  cat: FactorCat;
  /** Backend factor name. null = not yet supported (UI-only / disabled row). */
  backend: ScreenerFactor | null;
  /** Tooltip explaining why a row is locked. */
  lockedReason?: string;
};

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

const fmtNum = (n: number | null | undefined, digits = 2): string => {
  if (n === null || n === undefined) return '—';
  return n.toFixed(digits);
};
const fmtPct = (n: number | null | undefined): string => {
  if (n === null || n === undefined) return '—';
  return `${n.toFixed(2)}%`;
};

// ─── page ──────────────────────────────────────────────────────────────────
export function Screener() {
  const [factors, setFactors] = useState<UIFactor[]>([
    { id: 'pe',         name: '市盈率 PE-TTM', op: '<', val: 25, enabled: true, cat: '估值', backend: 'pe' },
    { id: 'pb',         name: '市净率 PB',     op: '<', val: 3.0, enabled: true, cat: '估值', backend: 'pb' },
    { id: 'roe',        name: 'ROE (近4季)',   op: '>', val: 15, enabled: true, cat: '财务', backend: 'roe' },
    { id: 'gross',      name: '毛利率',         op: '>', val: 30, enabled: false, cat: '财务', backend: 'gross_margin' },
    { id: 'rev_g',      name: '营收增速 YoY',   op: '>', val: 5,  enabled: true, cat: '成长', backend: 'revenue_growth' },
    { id: 'profit_g',   name: '净利润增速 YoY', op: '>', val: 5,  enabled: false, cat: '成长', backend: 'net_profit_growth' },
    { id: 'mktcap',     name: '总市值 (亿)',    op: '>', val: 100, enabled: false, cat: '规模', backend: null,
      lockedReason: '需市值数据，下批接入' },
    { id: 'vol5',       name: '5日均量',        op: '>', val: 5000, enabled: false, cat: '量价', backend: null,
      lockedReason: '需量价数据，下批接入' },
    { id: 'ma_cross',   name: 'MA5上穿MA20',   op: '=', val: 1, enabled: false, cat: '技术', backend: null,
      lockedReason: '需量价数据，下批接入' },
    { id: 'rsi',        name: 'RSI(14)',       op: '<', val: 70, enabled: false, cat: '技术', backend: null,
      lockedReason: '需量价数据，下批接入' },
  ]);

  const screener = useScreener();
  const data = screener.data;
  const hasSubmitted = screener.isSuccess || screener.isError;

  const toggle = (id: string) =>
    setFactors((fs) => fs.map((f) => {
      if (f.id !== id) return f;
      if (f.backend === null) return f;  // locked rows can't be toggled
      return { ...f, enabled: !f.enabled };
    }));
  const updateVal = (id: string, val: number) =>
    setFactors((fs) => fs.map((f) => (f.id === id ? { ...f, val } : f)));
  const updateOp = (id: string, op: FactorOp) =>
    setFactors((fs) => fs.map((f) => (f.id === id ? { ...f, op } : f)));

  const enabledN = factors.filter((f) => f.enabled && f.backend !== null).length;

  const handleRun = () => {
    const payload: ScreenerFilter[] = factors
      .filter((f) => f.backend !== null)
      .map((f) => ({
        factor: f.backend as ScreenerFactor,
        op: f.op,
        value: f.val,
        enabled: f.enabled,
      }));
    screener.mutate(payload);
  };

  const stocks: ScreenerStock[] = useMemo(() => data?.stocks ?? [], [data]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
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
                  {items.map((f) => {
                    const locked = f.backend === null;
                    return (
                      <div
                        key={f.id}
                        className="flex items-center gap-2"
                        title={locked ? f.lockedReason : undefined}
                        style={{
                          padding: '7px 12px',
                          opacity: locked ? 0.4 : (f.enabled ? 1 : 0.55),
                          borderBottom: '1px solid var(--panel-border-soft)',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={f.enabled && !locked}
                          disabled={locked}
                          onChange={() => toggle(f.id)}
                          style={{ accentColor: 'var(--brand)' }}
                        />
                        <div className="flex-1 min-w-0">
                          <div
                            style={{
                              fontSize: 11.5,
                              color: 'var(--text)',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 4,
                            }}
                          >
                            <span style={{ flex: 1 }}>{f.name}</span>
                            {locked && (
                              <span
                                className="mono"
                                style={{
                                  fontSize: 9,
                                  color: 'var(--text-faint)',
                                  letterSpacing: '0.08em',
                                }}
                              >
                                LOCKED
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-1 mt-1">
                            {(['<', '>', '='] as FactorOp[]).map((op) => (
                              <span
                                key={op}
                                onClick={() => !locked && updateOp(f.id, op)}
                                className="mono"
                                style={{
                                  padding: '1px 6px',
                                  fontSize: 10,
                                  cursor: locked ? 'not-allowed' : 'pointer',
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
                              disabled={locked}
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
                    );
                  })}
                </div>
              );
            })}
          </div>

          <div
            className="flex gap-1.5"
            style={{ padding: 10, borderTop: '1px solid var(--panel-border-soft)' }}
          >
            <button
              className="btn primary flex-1"
              onClick={handleRun}
              disabled={screener.isPending}
            >
              <Icon name="filter" size={12} />
              {screener.isPending ? '筛选中…' : '运行筛选'}
            </button>
          </div>
        </div>

        {/* CENTER: results — wired to /api/screener */}
        <div className="panel flex flex-col min-h-0">
          <div className="panel-head">
            <span className="panel-title">筛选结果</span>
            {data && (
              <>
                <span
                  className="mono"
                  style={{ fontSize: 11, color: 'var(--text-faint)', marginLeft: 8 }}
                >
                  {data.total_universe} 总样本
                </span>
                <span
                  className="mono pill brand"
                  style={{ fontSize: 11 }}
                >
                  {data.matched} 命中
                </span>
              </>
            )}
            <span className="flex-1" />
            <button
              className="btn primary"
              style={{ padding: '4px 10px' }}
              disabled
              title="待接入 — 需要 PoolMode='custom_codes' 后端"
            >
              <Icon name="backtest" size={12} /> 用此池回测
            </button>
          </div>

          {/* States: idle / loading / error / empty / table */}
          {!hasSubmitted && !screener.isPending && (
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
                  调整左侧因子，然后点击 "运行筛选"
                </div>
                <div
                  className="uppercase"
                  style={{
                    fontSize: 10.5,
                    color: 'var(--text-faint)',
                    letterSpacing: '0.1em',
                  }}
                >
                  Adjust factors then run screener
                </div>
              </div>
            </div>
          )}

          {screener.isPending && (
            <div
              className="flex-1 flex items-center justify-center"
              style={{ padding: 24 }}
            >
              <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>筛选中…</div>
            </div>
          )}

          {screener.isError && (
            <div style={{ padding: 16 }}>
              <div
                style={{
                  border: '1px solid var(--down)',
                  background: 'var(--down-soft, rgba(190,40,40,0.10))',
                  color: 'var(--down)',
                  padding: '10px 12px',
                  borderRadius: 4,
                  fontSize: 12,
                }}
              >
                筛选失败:{' '}
                {screener.error instanceof Error
                  ? screener.error.message
                  : String(screener.error)}
              </div>
            </div>
          )}

          {screener.isSuccess && data && (
            <>
              {data.note && (
                <div
                  style={{
                    margin: 12,
                    padding: '8px 12px',
                    fontSize: 11.5,
                    color: 'var(--text-dim)',
                    background: 'var(--bg-2)',
                    border: '1px solid var(--panel-border-soft)',
                    borderRadius: 4,
                  }}
                >
                  {data.note}
                </div>
              )}
              {stocks.length === 0 && !data.note && (
                <div
                  className="flex-1 flex items-center justify-center"
                  style={{ padding: 24 }}
                >
                  <div style={{ textAlign: 'center', maxWidth: 360 }}>
                    <div
                      style={{ fontSize: 13, color: 'var(--text)', marginBottom: 6 }}
                    >
                      无股票符合当前筛选条件，尝试放宽阈值
                    </div>
                    <div
                      className="uppercase"
                      style={{
                        fontSize: 10.5,
                        color: 'var(--text-faint)',
                        letterSpacing: '0.1em',
                      }}
                    >
                      No matches — relax thresholds
                    </div>
                  </div>
                </div>
              )}
              {stocks.length > 0 && (
                <div className="flex-1 overflow-auto" style={{ padding: 0 }}>
                  <table
                    className="mono"
                    style={{
                      width: '100%',
                      borderCollapse: 'collapse',
                      fontSize: 11.5,
                    }}
                  >
                    <thead>
                      <tr
                        style={{
                          position: 'sticky',
                          top: 0,
                          background: 'var(--bg-2)',
                          color: 'var(--text-faint)',
                          textAlign: 'right',
                          borderBottom: '1px solid var(--panel-border)',
                        }}
                      >
                        <th style={{ padding: '6px 10px', textAlign: 'left' }}>代码</th>
                        <th style={{ padding: '6px 10px' }}>PE</th>
                        <th style={{ padding: '6px 10px' }}>PB</th>
                        <th style={{ padding: '6px 10px' }}>ROE</th>
                        <th style={{ padding: '6px 10px' }}>毛利率</th>
                        <th style={{ padding: '6px 10px' }}>营收增速</th>
                        <th style={{ padding: '6px 10px' }}>净利润增速</th>
                        <th style={{ padding: '6px 10px', textAlign: 'right' }}>
                          数据日期
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {stocks.map((s) => (
                        <tr
                          key={s.code}
                          style={{
                            borderBottom: '1px solid var(--panel-border-soft)',
                            color: 'var(--text)',
                            textAlign: 'right',
                          }}
                        >
                          <td
                            style={{
                              padding: '5px 10px',
                              textAlign: 'left',
                              color: 'var(--text-hi)',
                            }}
                          >
                            {s.code}
                          </td>
                          <td style={{ padding: '5px 10px' }}>{fmtNum(s.pe)}</td>
                          <td style={{ padding: '5px 10px' }}>{fmtNum(s.pb)}</td>
                          <td style={{ padding: '5px 10px' }}>{fmtPct(s.roe)}</td>
                          <td style={{ padding: '5px 10px' }}>{fmtPct(s.gross_margin)}</td>
                          <td style={{ padding: '5px 10px' }}>{fmtPct(s.revenue_growth)}</td>
                          <td style={{ padding: '5px 10px' }}>{fmtPct(s.net_profit_growth)}</td>
                          <td
                            style={{
                              padding: '5px 10px',
                              color: 'var(--text-faint)',
                            }}
                          >
                            {s.as_of_date}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {data.matched > stocks.length && (
                    <div
                      style={{
                        padding: '8px 12px',
                        fontSize: 11,
                        color: 'var(--text-faint)',
                        textAlign: 'center',
                      }}
                    >
                      仅显示前 {stocks.length} / {data.matched} 条 — 收紧筛选条件可获取完整列表
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* RIGHT: distribution & saved schemes — honest empty states */}
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
              等待数据
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
              等待数据
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
