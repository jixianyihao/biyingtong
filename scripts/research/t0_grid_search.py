from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from t0.grid import run_grid_search  # noqa: E402
from tdx_service import tdx  # noqa: E402


def _bar_day(bar: dict) -> str | None:
    raw = str(bar.get('date') or '')
    return raw[:10] if len(raw) >= 10 else None


def _date(raw: str | None):
    if not raw:
        return None
    return datetime.strptime(raw, '%Y-%m-%d').date()


def _coverage(bars: list[dict]):
    days = [_bar_day(b) for b in bars]
    days = [d for d in days if d]
    if not days:
        return None, None
    return min(days), max(days)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Run concentrated intraday T grid search on TDX 1m bars.',
    )
    parser.add_argument('--code', default='688981.SH')
    parser.add_argument('--count', type=int, default=-1)
    parser.add_argument('--top', type=int, default=20)
    parser.add_argument('--base-shares', type=int, default=1000)
    parser.add_argument('--t-shares', type=int, default=500)
    parser.add_argument('--min-last-date',
                        help='Fail if latest 1m bar date is older than this YYYY-MM-DD.')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    bars = tdx.get_kline(args.code, period='1m', count=args.count,
                         dividend_type='front')
    first, last = _coverage(bars)
    if not bars:
        print(f'ERROR: no 1m bars for {args.code}', file=sys.stderr)
        return 2
    print(
        f'coverage: {args.code} 1m bars={len(bars)} first={first} last={last}',
        file=sys.stderr,
    )

    if args.min_last_date and last:
        if _date(last) < _date(args.min_last_date):
            print(
                f'ERROR: stale 1m data: latest={last} < required={args.min_last_date}',
                file=sys.stderr,
            )
            return 3

    rows = run_grid_search(
        args.code,
        bars,
        top_n=args.top,
        base_shares=args.base_shares,
        t_shares=args.t_shares,
    )
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    print('rank score      pnl   testPnL       dd   trips  win%   pf    mode params')
    for i, row in enumerate(rows, start=1):
        p = row['params']
        param_text = (
            f"amp={p['min_amplitude_pct']} hi={p['high_band']} "
            f"lo={p['low_band']} tp={p['take_profit_pct']} "
            f"sl={p['stop_loss_pct']} max={p['max_round_trips_per_day']} "
            f"late={p.get('latest_entry_time', '')}"
        )
        print(
            f"{i:>4} {row['rank_score']:>8.1f} "
            f"{row['total_pnl']:>8.1f} {row['test_total_pnl']:>8.1f} "
            f"{row['max_drawdown']:>8.1f} "
            f"{row['round_trips']:>5} {row['win_rate']:>5.1f} "
            f"{row['profit_factor']:>5.2f} {row['mode']:<16} {param_text}"
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
