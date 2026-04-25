/**
 * PositionsPanel — displays current holdings, wired to GET /api/positions.
 *
 *   - live mode: renders real TDX holdings; "暂无持仓" when empty.
 *   - dry_run mode: server returns positions=[] (no real orders placed),
 *     panel shows empty state with hint about engaging live mode.
 *   - loading / error: subtle indicator chip; table stays empty.
 *
 * No stub/demo data — only real values from the API.
 */

import { usePositions } from '../api/hooks';
import type { Position } from '../api/types';

function fmtNum(v: number, digits = 2): string {
  if (v === 0) return '—';
  return v.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function pnlCls(v: number): string {
  if (v > 0) return 'up mono';
  if (v < 0) return 'down mono';
  return 'mono';
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
  tone: 'loading' | 'error';
  title?: string;
  children: React.ReactNode;
}) {
  const cls =
    tone === 'loading'
      ? 'bg-bg-2 text-text-dim border-panel-border-soft'
      : 'bg-red-500/15 text-red-400 border-red-500/40';
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
  const positions = data?.positions ?? [];

  const errorMsg =
    error instanceof Error ? error.message : error ? String(error) : null;

  const emptyMessage = isLive
    ? '暂无持仓'
    : isDryRun
    ? '当前为 dry-run 模式，没有真实持仓。开启 BIYINGTONG_EXECUTION_MODE=live 后会读取实盘账户。'
    : isLoading
    ? '加载中…'
    : errorMsg
    ? `读取持仓失败：${errorMsg}`
    : '暂无持仓数据';

  const footerText = isLive
    ? '数据源：通达信实时持仓'
    : isDryRun
    ? '数据源：—（dry_run）'
    : '数据源：等待后端响应';

  return (
    <div className="panel p-5 flex flex-col min-h-0">
      <div className="flex items-baseline gap-2 mb-3 flex-wrap">
        <h2 className="text-text-hi text-base font-semibold">当前持仓</h2>
        <span className="mono text-[10px] text-text-ghost uppercase tracking-wider">
          Positions · vnpy / TDX
        </span>
        {isLoading && !data && (
          <Chip tone="loading" title="正在加载实时持仓…">
            loading…
          </Chip>
        )}
        {errorMsg && (
          <Chip tone="error" title={errorMsg}>
            error
          </Chip>
        )}
        <span style={{ flex: 1 }} />
        <span className="pill" style={{ fontSize: 10 }}>
          {positions.length} 只
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
            {positions.length > 0 ? (
              <LiveRows positions={positions} />
            ) : (
              <tr>
                <td
                  colSpan={6}
                  className="text-xs text-text-faint"
                  style={{ textAlign: 'center', padding: '24px 0' }}
                >
                  {emptyMessage}
                </td>
              </tr>
            )}
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
