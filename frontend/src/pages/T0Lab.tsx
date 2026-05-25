import { useMemo, useState } from 'react';
import { Icon } from '../components/Icon';
import { useT0Candidates, useT0Grid, useT0Portfolio } from '../api/hooks';
import type { T0CandidateRow, T0GridRow } from '../api/types';

const todayIso = () => new Date().toISOString().slice(0, 10);

const fmtMoney = (n: number) =>
  n.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

const fmtPct = (n: number) => `${n.toFixed(1)}%`;

const fmtNum = (n: number, digits = 2) => n.toFixed(digits);

function paramText(row: T0GridRow) {
  const p = row.params;
  const mode = row.mode === 'sell_first_only' ? '先卖后买' : '双向';
  return [
    mode,
    `振幅>${p.min_amplitude_pct}%`,
    `高位>${p.high_band}`,
    `低位<${p.low_band}`,
    `止盈${p.take_profit_pct}%`,
    `止损${p.stop_loss_pct}%`,
    `最晚${p.latest_entry_time}`,
  ].join(' · ');
}

function ResultTable({ rows }: { rows: T0GridRow[] }) {
  if (rows.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 text-text-faint text-sm">
        没有可排名的参数组合。先确认 1 分钟 K 线数据已下载。
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto">
      <table
        className="mono"
        style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11.5 }}
      >
        <thead>
          <tr
            style={{
              position: 'sticky',
              top: 0,
              background: 'var(--bg-2)',
              color: 'var(--text-faint)',
              borderBottom: '1px solid var(--panel-border)',
              textAlign: 'right',
            }}
          >
            <th style={{ padding: '7px 10px', textAlign: 'left' }}>排名</th>
            <th style={{ padding: '7px 10px' }}>总PnL</th>
            <th style={{ padding: '7px 10px' }}>样本外</th>
            <th style={{ padding: '7px 10px' }}>回撤</th>
            <th style={{ padding: '7px 10px' }}>胜率</th>
            <th style={{ padding: '7px 10px' }}>次数</th>
            <th style={{ padding: '7px 10px' }}>PF</th>
            <th style={{ padding: '7px 10px', textAlign: 'left' }}>参数</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, idx) => {
            const good = r.total_pnl >= 0;
            const oosGood = r.test_total_pnl >= 0 && r.test_round_trips > 0;
            return (
              <tr
                key={`${r.rank_score}-${idx}`}
                style={{ borderBottom: '1px solid var(--panel-border-soft)' }}
              >
                <td style={{ padding: '7px 10px', color: 'var(--text-hi)', textAlign: 'left' }}>
                  #{idx + 1}
                </td>
                <td style={{ padding: '7px 10px', color: good ? 'var(--up)' : 'var(--down)' }}>
                  {fmtMoney(r.total_pnl)}
                </td>
                <td style={{ padding: '7px 10px', color: oosGood ? 'var(--up)' : 'var(--down)' }}>
                  {fmtMoney(r.test_total_pnl)}
                  <span style={{ color: 'var(--text-ghost)', marginLeft: 4 }}>
                    / {r.test_round_trips}
                  </span>
                </td>
                <td style={{ padding: '7px 10px', color: 'var(--down)' }}>
                  {fmtMoney(r.max_drawdown)}
                </td>
                <td style={{ padding: '7px 10px', color: 'var(--text-dim)' }}>
                  {fmtPct(r.win_rate)}
                </td>
                <td style={{ padding: '7px 10px', color: 'var(--text-dim)' }}>
                  {r.round_trips}
                </td>
                <td style={{ padding: '7px 10px', color: 'var(--text-dim)' }}>
                  {fmtNum(r.profit_factor, 2)}
                </td>
                <td
                  style={{
                    padding: '7px 10px',
                    color: 'var(--text)',
                    textAlign: 'left',
                    whiteSpace: 'normal',
                    lineHeight: 1.45,
                  }}
                >
                  {r.robust && (
                    <span className="pill brand" style={{ fontSize: 9, marginRight: 6 }}>
                      OOS+
                    </span>
                  )}
                  {paramText(r)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CandidateList({
  rows,
  onPick,
}: {
  rows: T0CandidateRow[];
  onPick: (code: string) => void;
}) {
  if (rows.length === 0) return null;
  return (
    <div className="grid gap-1" style={{ maxHeight: 210, overflowY: 'auto' }}>
      {rows.slice(0, 12).map((r) => (
        <button
          key={r.code}
          onClick={() => onPick(r.code)}
          className="mono"
          style={{
            textAlign: 'left',
            padding: '6px 7px',
            borderRadius: 4,
            border: '1px solid var(--panel-border-soft)',
            background: 'var(--bg-2)',
            color: 'var(--text-dim)',
            cursor: 'pointer',
          }}
        >
          <div className="flex items-center gap-2">
            <span style={{ color: 'var(--text-hi)', fontWeight: 700 }}>{r.code}</span>
            <span style={{ color: (r.preview_total_return_pct ?? r.period_return_pct) >= 0 ? 'var(--up)' : 'var(--down)' }}>
              {fmtPct(r.preview_total_return_pct ?? r.period_return_pct)}
            </span>
            <span style={{ marginLeft: 'auto', color: 'var(--text-faint)' }}>
              振幅 {fmtPct(r.avg_intraday_amp_pct)}
            </span>
          </div>
          <div style={{ marginTop: 2, fontSize: 10, color: 'var(--text-ghost)' }}>
            {r.first_date} → {r.last_date} · {r.days} 天 · T {r.preview_round_trips ?? 0} 次
            {r.preview_alpha_vs_all_in != null && (
              <> · 跑赢全仓¥{fmtMoney(r.preview_alpha_vs_all_in)}</>
            )}
          </div>
        </button>
      ))}
    </div>
  );
}

export function T0Lab() {
  const [code, setCode] = useState('688981.SH');
  const [minLastDate, setMinLastDate] = useState(todayIso());
  const [top, setTop] = useState(20);
  const grid = useT0Grid();
  const portfolio = useT0Portfolio();
  const candidates = useT0Candidates();
  const data = grid.data;

  const best = data?.rows?.[0];
  const coverageText = useMemo(() => {
    if (!data) return '等待运行';
    const c = data.coverage;
    if (!c.first || !c.last) return '无 1m K 线';
    return `${c.first} → ${c.last} · ${c.bar_count.toLocaleString('zh-CN')} bars`;
  }, [data]);

  function run() {
    const cleanCode = code.trim().toUpperCase();
    if (!cleanCode) return;
    grid.mutate({
      code: cleanCode,
      top,
      count: -1,
      min_last_date: minLastDate || undefined,
    });
  }

  function runPortfolio() {
    portfolio.mutate({
      code: code.trim().toUpperCase(),
      initial_capital: 1_000_000,
      allocation_mode: 'auto',
    });
  }

  function scanCandidates() {
    candidates.mutate({
      top: 30,
      max_files: 2_000,
      with_backtest: true,
      preview_pool: 80,
      min_preview_trips: 1,
      min_days: 50,
      min_avg_amp_pct: 3.0,
      max_avg_amp_pct: 15.0,
      min_return_pct: -30.0,
      max_return_pct: 120.0,
    });
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-6 pt-5 pb-3">
        <h1 className="text-2xl text-text-hi font-semibold">做T研究</h1>
        <div className="text-text-faint text-xs mt-1 tracking-wide uppercase">
          A-share T0 Lab · 1m K-line Grid Backtest
        </div>
      </div>

      <div
        className="flex-1 min-h-0 grid gap-3 px-3 pb-3"
        style={{ gridTemplateColumns: '280px minmax(0, 1fr)' }}
      >
        <div className="panel flex flex-col min-h-0">
          <div className="panel-head">
            <span className="panel-title">回测输入</span>
            <span className="flex-1" />
          </div>

          <div className="grid gap-3" style={{ padding: 12 }}>
            <label className="grid gap-1">
              <span className="text-[11px] text-text-faint">标的代码</span>
              <input
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                className="mono"
                style={{
                  background: 'var(--bg-2)',
                  border: '1px solid var(--panel-border-soft)',
                  color: 'var(--text-hi)',
                  borderRadius: 4,
                  padding: '7px 8px',
                  fontSize: 12,
                  outline: 'none',
                }}
              />
            </label>

            <label className="grid gap-1">
              <span className="text-[11px] text-text-faint">最新数据至少到</span>
              <input
                type="date"
                value={minLastDate}
                onChange={(e) => setMinLastDate(e.target.value)}
                className="mono"
                style={{
                  background: 'var(--bg-2)',
                  border: '1px solid var(--panel-border-soft)',
                  color: 'var(--text-hi)',
                  borderRadius: 4,
                  padding: '7px 8px',
                  fontSize: 12,
                  outline: 'none',
                }}
              />
            </label>

            <label className="grid gap-1">
              <span className="text-[11px] text-text-faint">返回前 N 组参数</span>
              <input
                type="number"
                min={1}
                max={100}
                value={top}
                onChange={(e) => setTop(Number(e.target.value))}
                className="mono"
                style={{
                  background: 'var(--bg-2)',
                  border: '1px solid var(--panel-border-soft)',
                  color: 'var(--text-hi)',
                  borderRadius: 4,
                  padding: '7px 8px',
                  fontSize: 12,
                  outline: 'none',
                }}
              />
            </label>

            <button
              className="btn primary"
              onClick={run}
              disabled={grid.isPending}
              style={{ height: 34, fontWeight: 600 }}
            >
              <Icon name="backtest" size={13} />
              {grid.isPending ? '正在回测…' : '运行参数网格'}
            </button>
          </div>

          <div
            className="grid gap-2"
            style={{ padding: 12, borderTop: '1px solid var(--panel-border-soft)' }}
          >
            <div className="text-[11px] text-text-faint">数据覆盖</div>
            <div className="mono text-xs text-text-hi">{coverageText}</div>
            {data?.coverage.is_stale && (
              <div
                style={{
                  padding: '8px 9px',
                  border: '1px solid var(--down-border)',
                  background: 'rgba(190,40,40,0.08)',
                  color: 'var(--down)',
                  borderRadius: 4,
                  fontSize: 11.5,
                  lineHeight: 1.5,
                }}
              >
                数据不是最新：{data.coverage.stale_reason}
              </div>
            )}
            {!data?.coverage.is_stale && data && (
              <div
                style={{
                  padding: '8px 9px',
                  border: '1px solid var(--panel-border-soft)',
                  background: 'var(--bg-2)',
                  color: 'var(--text-dim)',
                  borderRadius: 4,
                  fontSize: 11.5,
                  lineHeight: 1.5,
                }}
              >
                这里只是历史回测研究，不直接生成实盘订单。
              </div>
            )}
          </div>

          {best && (
            <div
              className="grid gap-1"
              style={{ padding: 12, borderTop: '1px solid var(--panel-border-soft)' }}
            >
              <div className="text-[11px] text-text-faint">当前最优</div>
              <div
                className="mono"
                style={{
                  color: best.total_pnl >= 0 ? 'var(--up)' : 'var(--down)',
                  fontSize: 18,
                  fontWeight: 700,
                }}
              >
                {fmtMoney(best.total_pnl)}
              </div>
              <div className="mono text-[11px] text-text-faint">
                全样本 {best.round_trips} 次 · 样本外 {best.test_round_trips} 次 ·
                OOS {fmtMoney(best.test_total_pnl)}
              </div>
            </div>
          )}

          <div
            className="grid gap-2"
            style={{ padding: 12, borderTop: '1px solid var(--panel-border-soft)' }}
          >
            <div className="text-[11px] text-text-faint">候选标的扫描</div>
            <button
              className="btn"
              onClick={scanCandidates}
              disabled={candidates.isPending}
              style={{ justifyContent: 'center', height: 32 }}
            >
              {candidates.isPending ? '扫描本地1m数据…' : '扫描做T候选'}
            </button>
            {candidates.data && (
              <CandidateList
                rows={candidates.data.rows}
                onPick={(nextCode) => {
                  setCode(nextCode);
                  portfolio.reset();
                }}
              />
            )}
            {candidates.isError && (
              <div style={{ color: 'var(--down)', fontSize: 11 }}>
                候选扫描失败：{candidates.error instanceof Error ? candidates.error.message : String(candidates.error)}
              </div>
            )}
          </div>

          <div
            className="grid gap-2"
            style={{ padding: 12, borderTop: '1px solid var(--panel-border-soft)' }}
          >
            <div className="text-[11px] text-text-faint">100万组合回测</div>
            <button
              className="btn"
              onClick={runPortfolio}
              disabled={portfolio.isPending}
              style={{ justifyContent: 'center', height: 32 }}
            >
              {portfolio.isPending ? '计算中…' : '跑推荐做T组合'}
            </button>
            {portfolio.data && (
              <div className="grid gap-1 mono text-[11px]" style={{ color: 'var(--text-dim)' }}>
                <div>
                  仓位模式{' '}
                  <span style={{ color: portfolio.data.allocation.mode === 'bull_high_base' ? 'var(--up)' : 'var(--text-hi)' }}>
                    {portfolio.data.allocation.mode === 'bull_high_base'
                      ? '牛市高底仓'
                      : portfolio.data.allocation.mode === 'defensive_low_base'
                        ? '防守低底仓'
                        : '震荡均衡'}
                  </span>
                  {' '}· 底仓 {(Number(portfolio.data.params.base_position_pct) * 100).toFixed(0)}%
                  {' '}· T额 {(Number(portfolio.data.params.t_shares_pct) * 100).toFixed(0)}%
                </div>
                <div>
                  期末权益{' '}
                  <span style={{ color: 'var(--text-hi)' }}>
                    {fmtMoney(portfolio.data.final_equity)}
                  </span>
                  {' '}({fmtPct(portfolio.data.total_return_pct)})
                </div>
                <div>
                  跑赢全仓{' '}
                  <span style={{ color: portfolio.data.alpha_vs_all_in_hold >= 0 ? 'var(--up)' : 'var(--down)' }}>
                    {fmtMoney(portfolio.data.alpha_vs_all_in_hold)}
                  </span>
                </div>
                <div>
                  跑赢同底仓{' '}
                  <span style={{ color: portfolio.data.alpha_vs_base_hold >= 0 ? 'var(--up)' : 'var(--down)' }}>
                    {fmtMoney(portfolio.data.alpha_vs_base_hold)}
                  </span>
                </div>
                <div>
                  底仓 {portfolio.data.base_shares} · T额 {portfolio.data.t_shares} ·
                  {portfolio.data.round_trips} 次 · 胜率 {fmtPct(portfolio.data.win_rate)}
                </div>
                <div>
                  基准持有 {fmtMoney(portfolio.data.base_hold_equity)} ·
                  全仓持有 {fmtMoney(portfolio.data.all_in_hold_equity)}
                </div>
                <div style={{ color: 'var(--text-ghost)', whiteSpace: 'normal', lineHeight: 1.45 }}>
                  {portfolio.data.allocation.reason}
                </div>
              </div>
            )}
            {portfolio.isError && (
              <div style={{ color: 'var(--down)', fontSize: 11 }}>
                组合回测失败：{portfolio.error instanceof Error ? portfolio.error.message : String(portfolio.error)}
              </div>
            )}
          </div>
        </div>

        <div className="panel flex flex-col min-h-0">
          <div className="panel-head">
            <span className="panel-title">做T参数排名</span>
            {data && (
              <span className="mono pill brand" style={{ fontSize: 10.5 }}>
                {data.code}
              </span>
            )}
            <span className="flex-1" />
          </div>

          {!data && !grid.isPending && !grid.isError && (
            <div className="flex-1 flex items-center justify-center p-6">
              <div style={{ textAlign: 'center', maxWidth: 420 }}>
                <div style={{ color: 'var(--text)', fontSize: 13, marginBottom: 6 }}>
                  先用当前 TDX 1 分钟 K 线缓存做参数回测。
                </div>
                <div
                  className="uppercase"
                  style={{ color: 'var(--text-faint)', fontSize: 10.5, letterSpacing: '0.1em' }}
                >
                  Download minute bars in TDX first, then run the grid
                </div>
              </div>
            </div>
          )}

          {grid.isPending && (
            <div className="flex-1 flex items-center justify-center p-6 text-text-dim text-sm">
              正在跑 1m 做T参数网格…
            </div>
          )}

          {grid.isError && (
            <div style={{ padding: 14 }}>
              <div
                style={{
                  padding: '10px 12px',
                  border: '1px solid var(--down-border)',
                  background: 'rgba(190,40,40,0.08)',
                  color: 'var(--down)',
                  borderRadius: 4,
                  fontSize: 12,
                }}
              >
                回测失败：{grid.error instanceof Error ? grid.error.message : String(grid.error)}
              </div>
            </div>
          )}

          {data && !grid.isPending && <ResultTable rows={data.rows} />}
        </div>
      </div>
    </div>
  );
}
