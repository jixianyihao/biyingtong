/**
 * PositionsPanel — displays current holdings.
 *
 * Phase 2 (current): wired to GET /api/positions.
 *   - live mode: renders real TDX holdings; "暂无持仓" when empty.
 *   - dry_run mode: server returns positions=[] (no real orders), so we fall
 *     back to demo stub rows with a "DEMO DATA" chip so the operator
 *     understands these aren't real fills.
 *   - loading / error: render stub rows with a subtle indicator chip so the
 *     table is never blank.
 */

import { usePositions } from '../api/hooks';
import type { Position } from '../api/types';

type StubPosition = {
  code: string;
  name: string;
  shares: number;
  cost: number;
  price: number;
};

const STUB_POSITIONS: StubPosition[] = [
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

function stubPnlPct(p: StubPosition): number | null {
  if (p.shares <= 0 || p.cost <= 0) return null;
  return ((p.price - p.cost) / p.cost) * 100;
}

function pnlCls(v: number): string {
  if (v > 0) return 'up mono';
  if (v < 0) return 'down mono';
  return 'mono';
}

function StubRows() {
  return (
    <>
      {STUB_POSITIONS.map((p, i) => {
        const pct = stubPnlPct(p);
        const isEmpty = p.shares <= 0;
        return (
          <tr key={`stub-${p.code}-${i}`}>
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
    </>
  );
}

function LiveRows({ positions }: { positions: Position[] }) {
  return (
    <>
      {positions.map((p, i) => (
        <tr key={`live-${p.code}-${i}`}>
          <td className="mono text-xs text-text-hi">{p.code}</td>
          <td className="text-xs text-text">{p.name}</td>
          <td className="num mono text-xs">{p.shares.toLocaleString()}</td>
          <td className="num mono text-xs">{`¥${fmtNum(p.avg_price, 2)}`}</td>
          <td className="num mono text-xs">{`¥${fmtNum(p.last_price, 2)}`}</td>
          <td className="num">
            <span className={`${pnlCls(p.pnl_pct)} text-xs`}>
              {p.pnl_pct > 0 ? '+' : ''}
              {p.pnl_pct.toFixed(2)}%
            </span>
          </td>
        </tr>
      ))}
    </>
  );
}

function Chip({
  tone,
  title,
  children,
}: {
  tone: 'demo' | 'loading' | 'error';
  title?: string;
  children: React.ReactNode;
}) {
  const cls =
    tone === 'error'
      ? 'bg-red-500/20 text-red-400 border-red-500/50'
      : tone === 'loading'
      ? 'bg-bg-2 text-text-dim border-panel-border-soft'
      : 'bg-amber-500/15 text-amber-400 border-amber-500/40';
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] mono font-medium tracking-wider uppercase border ${cls}`}
      title={title}
    >
      {children}
    </span>
  );
}

export function PositionsPanel() {
  const { data, isLoading, error } = usePositions();

  const mode = data?.mode;
  const isLive = mode === 'live';
  const isDryRun = mode === 'dry_run';
  const livePositions = data?.positions ?? [];

  // Decide what to render in <tbody>.
  //   live + non-empty  → real rows
  //   live + empty      → "暂无持仓" message
  //   dry_run           → stub rows (DEMO)
  //   loading / error / unknown mode → stub rows (fallback)
  const showRealRows = isLive && livePositions.length > 0;
  const showEmptyState = isLive && livePositions.length === 0;
  const showStub = !showRealRows && !showEmptyState;

  // Count chip in header — only meaningful in live mode with real data.
  const headerCount = isLive
    ? livePositions.length
    : STUB_POSITIONS.filter((p) => p.shares > 0).length;

  // Footer text reflects new state.
  const footerText = isLive
    ? '数据源：通达信实时持仓'
    : isDryRun
    ? '数据源：演示桩数据 (BIYINGTONG_EXECUTION_MODE=dry_run)'
    : '数据源：v1 TDX 原型（迁移到 Phase 2 实盘后接入实时持仓）';

  const errorMsg =
    error instanceof Error ? error.message : error ? String(error) : null;

  return (
    <div className="panel p-5 flex flex-col min-h-0">
      <div className="flex items-baseline gap-2 mb-3 flex-wrap">
        <h2 className="text-text-hi text-base font-semibold">当前持仓</h2>
        <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
          Positions · vnpy / TDX
        </span>
        {isDryRun && (
          <Chip tone="demo" title="dry_run 模式下展示演示桩数据，并非真实持仓">
            DEMO DATA
          </Chip>
        )}
        {isLoading && !data && (
          <Chip tone="loading" title="正在加载实时持仓…">
            loading…
          </Chip>
        )}
        {errorMsg && (
          <Chip
            tone="error"
            title={errorMsg}
          >
            error
          </Chip>
        )}
        <span style={{ flex: 1 }} />
        <span className="pill" style={{ fontSize: 10 }}>
          {headerCount} 只
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
            {showRealRows && <LiveRows positions={livePositions} />}
            {showEmptyState && (
              <tr>
                <td
                  colSpan={6}
                  className="text-xs text-text-faint"
                  style={{ textAlign: 'center', padding: '24px 0' }}
                >
                  暂无持仓
                </td>
              </tr>
            )}
            {showStub && <StubRows />}
          </tbody>
        </table>
      </div>

      <div
        className="mono text-[10px] text-text-faint mt-3"
        style={{ lineHeight: 1.5 }}
      >
        {footerText}
      </div>
    </div>
  );
}
