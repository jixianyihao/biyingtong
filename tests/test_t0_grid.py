from __future__ import annotations

from t0.grid import run_grid_search


def _bar(ts: str, price: float, high: float | None = None, low: float | None = None):
    return {
        'date': ts,
        'open': price,
        'high': price if high is None else high,
        'low': price if low is None else low,
        'close': price,
        'vol': 100_000,
    }


def test_grid_search_returns_ranked_results():
    bars = [
        _bar('2026-01-26 09:31:00', 100.0),
        _bar('2026-01-26 09:40:00', 103.0, high=103.2, low=100.0),
        _bar('2026-01-26 10:10:00', 101.0, high=103.2, low=100.8),
        _bar('2026-01-27 09:31:00', 100.0),
        _bar('2026-01-27 09:40:00', 103.0, high=103.2, low=100.0),
        _bar('2026-01-27 10:10:00', 101.0, high=103.2, low=100.8),
    ]

    rows = run_grid_search(
        '688981.SH',
        bars,
        param_grid=[
            {'mode': 'sell_first_only', 'min_amplitude_pct': 1.0,
             'high_band': 0.82, 'low_band': 0.25,
             'take_profit_pct': 1.0, 'stop_loss_pct': 2.0,
             'max_round_trips_per_day': 1},
            {'mode': 'sell_first_only', 'min_amplitude_pct': 5.0,
             'high_band': 0.82, 'low_band': 0.25,
             'take_profit_pct': 1.0, 'stop_loss_pct': 2.0,
             'max_round_trips_per_day': 1},
        ],
        top_n=2,
        fee_bps=0.0,
        sell_tax_bps=0.0,
        slippage_bps=0.0,
    )

    assert len(rows) == 2
    assert rows[0]['total_pnl'] > rows[1]['total_pnl']
    assert rows[0]['round_trips'] == 2
    assert rows[0]['params']['mode'] == 'sell_first_only'


def test_grid_search_reports_train_test_split_metrics():
    bars = [
        _bar('2026-01-26 09:31:00', 100.0),
        _bar('2026-01-26 09:40:00', 103.0, high=103.2, low=100.0),
        _bar('2026-01-26 10:10:00', 101.0, high=103.2, low=100.8),
        _bar('2026-01-27 09:31:00', 100.0),
        _bar('2026-01-27 09:40:00', 103.0, high=103.2, low=100.0),
        _bar('2026-01-27 10:10:00', 101.0, high=103.2, low=100.8),
        _bar('2026-01-28 09:31:00', 100.0),
        _bar('2026-01-28 09:40:00', 103.0, high=103.2, low=100.0),
        _bar('2026-01-28 10:10:00', 101.0, high=103.2, low=100.8),
        _bar('2026-01-29 09:31:00', 100.0),
        _bar('2026-01-29 09:40:00', 103.0, high=103.2, low=100.0),
        _bar('2026-01-29 10:10:00', 101.0, high=103.2, low=100.8),
    ]

    rows = run_grid_search(
        '688981.SH',
        bars,
        param_grid=[{'mode': 'sell_first_only', 'min_amplitude_pct': 1.0,
                     'high_band': 0.82, 'low_band': 0.25,
                     'take_profit_pct': 1.0, 'stop_loss_pct': 2.0,
                     'max_round_trips_per_day': 1}],
        top_n=1,
        fee_bps=0.0,
        sell_tax_bps=0.0,
        slippage_bps=0.0,
    )

    row = rows[0]
    assert row['train_days'] == 2
    assert row['test_days'] == 2
    assert row['train_round_trips'] == 2
    assert row['test_round_trips'] == 2
    assert row['train_total_pnl'] > 0
    assert row['test_total_pnl'] > 0
    assert row['robust'] is True
