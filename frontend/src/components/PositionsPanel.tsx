/**
 * PositionsPanel — displays current holdings.
 *
 * Phase 1 (current): static stub data. The v1 TDX prototype kept positions in
 * TDXService, but those aren't wired to this React frontend yet. When Phase 2
 * (real trading) is gated on, this component will subscribe to a live
 * positions feed (vnpy state or TDX account snapshot).
 */

type Position = {
  code: string;
  name: string;
  shares: number;
  cost: number;
  price: number;
};

const STUB_POSITIONS: Position[] = [
  { code: '600519.SH', name: '贵州茅台', shares: 100, cost: 1685.30, price: 1742.50 },
  { code: '000858.SZ', name: '五粮液',   shares: 200, cost: 158.40,  price: 152.80  },
  { code: '—',         name: '（空仓位）', shares: 0,   cost: 0,       price: 0       },
];

function fmtNum(v: number, digits = 2): string {
  if (v === 0) return '—';
  return v.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function pnlPct(p: Position): number | null {
  if (p.shares <= 0 || p.cost <= 0) return null;
  return ((p.price - p.cost) / p.cost) * 100;
}

function pnlCls(v: number): string {
  if (v > 0) return 'up mono';
  if (v < 0) return 'down mono';
  return 'mono';
}

export function PositionsPanel() {
  return (
    <div className="panel p-5 flex flex-col min-h-0">
      <div className="flex items-baseline gap-2 mb-3 flex-wrap">
        <h2 className="text-text-hi text-base font-semibold">当前持仓</h2>
        <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
          Positions · vnpy / TDX
        </span>
        <span style={{ flex: 1 }} />
        <span className="pill" style={{ fontSize: 10 }}>
          {STUB_POSITIONS.filter((p) => p.shares > 0).length} 只
        </span>
      </div>

      <div
        style={{
          border: '1px solid var(--panel-border-soft)',
          borderRadius: 4,
          overflow: 'auto',
        }}
      >
        <table className="tbl" style={{ margin: 0 }}>
          <thead>
            <tr>
              <th>代码</th>
              <th>名称</th>
              <th className="num">持仓</th>
              <th className="num">成本</th>
              <th className="num">市价</th>
              <th className="num">盈亏%</th>
            </tr>
          </thead>
          <tbody>
            {STUB_POSITIONS.map((p, i) => {
              const pct = pnlPct(p);
              const isEmpty = p.shares <= 0;
              return (
                <tr key={`${p.code}-${i}`}>
                  <td className="mono text-xs text-text-hi">{p.code}</td>
                  <td className="text-xs text-text">{p.name}</td>
                  <td className="num mono text-xs">
                    {isEmpty ? '—' : p.shares.toLocaleString()}
                  </td>
                  <td className="num mono text-xs">
                    {isEmpty ? '—' : `¥${fmtNum(p.cost, 2)}`}
                  </td>
                  <td className="num mono text-xs">
                    {isEmpty ? '—' : `¥${fmtNum(p.price, 2)}`}
                  </td>
                  <td className="num">
                    {pct == null ? (
                      <span className="mono text-xs text-text-faint">—</span>
                    ) : (
                      <span className={`${pnlCls(pct)} text-xs`}>
                        {pct > 0 ? '+' : ''}
                        {pct.toFixed(2)}%
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div
        className="mono text-[10px] text-text-faint mt-3"
        style={{ lineHeight: 1.5 }}
      >
        数据源：v1 TDX 原型（迁移到 Phase 2 实盘后接入实时持仓）
      </div>
    </div>
  );
}
