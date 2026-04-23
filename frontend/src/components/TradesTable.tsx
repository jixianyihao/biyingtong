import { useMemo, useState } from 'react';
import type { TradeRow } from '../api/types';

type SortKey = 'date' | 'code' | 'action' | 'shares' | 'price' | 'fee';

export function TradesTable({
  trades,
  onRowClick,
}: {
  trades: TradeRow[];
  onRowClick?: (t: TradeRow) => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>('date');
  const [sortDesc, setSortDesc] = useState(false);
  const [filterCode, setFilterCode] = useState('');
  const [filterAction, setFilterAction] = useState<'all' | 'buy' | 'sell'>('all');

  const filtered = useMemo(() => {
    let rows = trades;
    if (filterCode.trim()) {
      const q = filterCode.trim().toLowerCase();
      rows = rows.filter((t) => t.code.toLowerCase().includes(q));
    }
    if (filterAction !== 'all') {
      rows = rows.filter((t) => t.action === filterAction);
    }
    return [...rows].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av === bv) return 0;
      const cmp = av < bv ? -1 : 1;
      return sortDesc ? -cmp : cmp;
    });
  }, [trades, sortKey, sortDesc, filterCode, filterAction]);

  if (trades.length === 0) {
    return (
      <div className="text-text-faint text-sm italic">
        本次回测没有成交记录。
      </div>
    );
  }

  const toggleSort = (k: SortKey) => {
    if (k === sortKey) setSortDesc((d) => !d);
    else {
      setSortKey(k);
      setSortDesc(false);
    }
  };
  const headerCls = 'cursor-pointer select-none';

  return (
    <div>
      <div className="flex gap-2 mb-2 flex-wrap">
        <input
          className="bg-bg-2 border border-panel-border-soft rounded px-2 py-1 text-xs text-text-hi"
          placeholder="过滤股票代码…"
          value={filterCode}
          onChange={(e) => setFilterCode(e.target.value)}
        />
        <select
          className="bg-bg-2 border border-panel-border-soft rounded px-2 py-1 text-xs text-text-hi"
          value={filterAction}
          onChange={(e) =>
            setFilterAction(e.target.value as typeof filterAction)
          }
        >
          <option value="all">全部方向</option>
          <option value="buy">买入</option>
          <option value="sell">卖出</option>
        </select>
        <span className="text-text-faint text-xs self-center">
          {filtered.length} / {trades.length} 笔
        </span>
      </div>

      <div
        style={{
          border: '1px solid var(--panel-border-soft)',
          borderRadius: 4,
          overflow: 'auto',
          maxHeight: 400,
        }}
      >
        <table className="tbl" style={{ margin: 0 }}>
          <thead>
            <tr>
              <th className={headerCls} onClick={() => toggleSort('date')}>
                日期 {sortKey === 'date' ? (sortDesc ? '▼' : '▲') : ''}
              </th>
              <th className={headerCls} onClick={() => toggleSort('code')}>
                代码 {sortKey === 'code' ? (sortDesc ? '▼' : '▲') : ''}
              </th>
              <th className={headerCls} onClick={() => toggleSort('action')}>
                方向 {sortKey === 'action' ? (sortDesc ? '▼' : '▲') : ''}
              </th>
              <th className={`num ${headerCls}`} onClick={() => toggleSort('shares')}>
                股数 {sortKey === 'shares' ? (sortDesc ? '▼' : '▲') : ''}
              </th>
              <th className={`num ${headerCls}`} onClick={() => toggleSort('price')}>
                成交价 {sortKey === 'price' ? (sortDesc ? '▼' : '▲') : ''}
              </th>
              <th className={`num ${headerCls}`} onClick={() => toggleSort('fee')}>
                费用 {sortKey === 'fee' ? (sortDesc ? '▼' : '▲') : ''}
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t, i) => (
              <tr
                key={`${t.date}-${t.code}-${i}`}
                onClick={() => onRowClick?.(t)}
                style={{ cursor: onRowClick ? 'pointer' : 'default' }}
              >
                <td className="mono text-xs">{t.date}</td>
                <td className="mono text-xs">{t.code}</td>
                <td>
                  <span
                    className={`pill ${t.action === 'buy' ? 'up' : 'down'}`}
                    style={{ fontSize: 10 }}
                  >
                    {t.action === 'buy' ? '买' : '卖'}
                  </span>
                </td>
                <td className="num mono text-xs">{t.shares.toLocaleString()}</td>
                <td className="num mono text-xs">¥{t.price.toFixed(2)}</td>
                <td className="num mono text-xs">¥{t.fee.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
