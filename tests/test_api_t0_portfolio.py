from __future__ import annotations

import struct
from pathlib import Path

from flask import Flask


def _fresh_flask_app():
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


class _FakeTDX:
    def get_kline(self, code, period='1d', count=80, dividend_type='front'):
        assert code == '688981.SH'
        assert period == '1m'
        return [
            {'date': '2026-01-26 09:31:00', 'open': 100, 'high': 100, 'low': 100, 'close': 100, 'vol': 100000},
            {'date': '2026-01-26 09:35:00', 'open': 98, 'high': 100, 'low': 97.8, 'close': 98, 'vol': 100000},
            {'date': '2026-01-26 10:05:00', 'open': 101, 'high': 101.2, 'low': 97.8, 'close': 101, 'vol': 100000},
            {'date': '2026-01-26 15:00:00', 'open': 101, 'high': 101, 'low': 101, 'close': 101, 'vol': 100000},
        ]

    def get_snapshot(self, code):  # pragma: no cover
        return {}


class _BullishFakeTDX:
    def get_kline(self, code, period='1d', count=80, dividend_type='front'):
        assert code == '688981.SH'
        assert period == '1m'
        return [
            {'date': '2026-01-26 09:31:00', 'open': 100, 'high': 100, 'low': 100, 'close': 100, 'vol': 100000},
            {'date': '2026-02-10 15:00:00', 'open': 102, 'high': 102, 'low': 102, 'close': 102, 'vol': 100000},
            {'date': '2026-03-02 15:00:00', 'open': 104, 'high': 104, 'low': 104, 'close': 104, 'vol': 100000},
            {'date': '2026-04-01 15:00:00', 'open': 107, 'high': 107, 'low': 107, 'close': 107, 'vol': 100000},
        ]

    def get_snapshot(self, code):  # pragma: no cover
        return {}


class _LateBullishFakeTDX:
    def get_kline(self, code, period='1d', count=80, dividend_type='front'):
        assert code == '688981.SH'
        assert period == '1m'
        return [
            {'date': '2026-01-26 09:31:00', 'open': 100, 'high': 100, 'low': 100, 'close': 100, 'vol': 100000},
            {'date': '2026-01-26 09:35:00', 'open': 98, 'high': 100, 'low': 97.8, 'close': 98, 'vol': 100000},
            {'date': '2026-01-26 10:05:00', 'open': 101, 'high': 101.2, 'low': 97.8, 'close': 101, 'vol': 100000},
            {'date': '2026-01-27 15:00:00', 'open': 102, 'high': 102, 'low': 102, 'close': 102, 'vol': 100000},
            {'date': '2026-01-28 15:00:00', 'open': 108, 'high': 108, 'low': 108, 'close': 108, 'vol': 100000},
            {'date': '2026-01-29 15:00:00', 'open': 116, 'high': 116, 'low': 116, 'close': 116, 'vol': 100000},
        ]

    def get_snapshot(self, code):  # pragma: no cover
        return {}


class _EmptyTDX:
    def get_kline(self, code, period='1d', count=80, dividend_type='front'):
        return []

    def get_snapshot(self, code):  # pragma: no cover
        return {}


def _date_code(year: int, month: int, day: int) -> int:
    return (year - 2004) * 2048 + month * 100 + day


def _write_lc1(path: Path, code: str, closes: list[float]) -> Path:
    market = code[-2:].lower()
    raw = code[:6]
    target = path / market / 'minline'
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    day = 1
    for i, close in enumerate(closes):
        if i and i % 4 == 0:
            day += 1
        rows.append(struct.pack(
            '<HHfffffii',
            _date_code(2026, 5, day),
            9 * 60 + 31 + (i % 4),
            close, close * 1.02, close * 0.98, close,
            close * 100_000, 100_000, 0,
        ))
    (target / f'{market}{raw}.lc1').write_bytes(b''.join(rows))
    return target


def test_t0_portfolio_endpoint_returns_account_level_result(monkeypatch):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _FakeTDX())
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/portfolio', json={
        'code': '688981.SH',
        'initial_capital': 1_000_000,
        'base_position_pct': 0.75,
        't_shares_pct': 0.20,
        'fee_bps': 0,
        'sell_tax_bps': 0,
        'slippage_bps': 0,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['code'] == '688981.SH'
    assert body['base_shares'] == 7500
    assert body['round_trips'] == 1
    assert body['t_pnl'] == 4500
    assert body['alpha_vs_base_hold'] == 4500
    assert body['min_cost_reduction_pct'] is not None
    assert body['cost_reduction_positive_days_pct'] is not None


def test_t0_portfolio_endpoint_auto_allocation_uses_bull_mode(monkeypatch):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _BullishFakeTDX())
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/portfolio', json={
        'code': '688981.SH',
        'initial_capital': 1_000_000,
        'strategy_selection_ratio': 0.0,
        'fee_bps': 0,
        'sell_tax_bps': 0,
        'slippage_bps': 0,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['allocation']['mode'] == 'bull_high_base'
    assert body['params']['base_position_pct'] == 0.90
    assert body['params']['t_shares_pct'] == 0.15
    assert body['params']['allow_sell_first'] is False
    assert body['params']['allow_buy_first'] is True
    assert body['params']['high_band'] == 0.82
    assert body['params']['low_band'] == 0.25
    assert body['params']['stop_loss_pct'] == 1.0
    assert body['base_shares'] == 9000


def test_t0_portfolio_endpoint_defaults_to_train_slice_selection(monkeypatch):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _LateBullishFakeTDX())
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/portfolio', json={
        'code': '688981.SH',
        'initial_capital': 1_000_000,
        'fee_bps': 0,
        'sell_tax_bps': 0,
        'slippage_bps': 0,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['strategy_selection_ratio'] == 0.35
    assert body['strategy_selection_days'] == 3


def test_t0_portfolio_endpoint_can_select_strategy_on_train_slice(monkeypatch):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _LateBullishFakeTDX())
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/portfolio', json={
        'code': '688981.SH',
        'initial_capital': 1_000_000,
        'strategy_selection_ratio': 0.5,
        'fee_bps': 0,
        'sell_tax_bps': 0,
        'slippage_bps': 0,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['allocation']['mode'] == 'balanced_range'
    assert body['params']['base_position_pct'] == 0.70
    assert body['strategy_selection_ratio'] == 0.5
    assert body['strategy_selection_days'] == 2


def test_t0_portfolio_endpoint_selects_variant_on_train_slice(monkeypatch):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _LateBullishFakeTDX())
    monkeypatch.setattr(t0_api, 'choose_t0_allocation', lambda bars, requested_mode='auto': {
        'mode': 'strong_bull_sell_rebalance',
        'base_position_pct': 0.85,
        't_shares_pct': 0.15,
        'strategy_params': {},
    })
    variants = [
        {'selected_variant': 'train_cost_cut'},
        {'selected_variant': 'full_sample_trap'},
    ]
    monkeypatch.setattr(t0_api, 't0_strategy_variants', lambda allocation: variants)

    def fake_run(code, bars, *, allocation, initial_capital, strategy_params,
                 base_position_pct=None, t_shares_pct=None):
        days = t0_api._count_bar_days(bars)
        first_day = min(t0_api._bar_day(b) for b in bars if t0_api._bar_day(b))
        variant = strategy_params['selected_variant']
        # Training slice says train_cost_cut lowers cost better. Full sample
        # would pick full_sample_trap if the endpoint still selected variants
        # with future data.
        segment = (
            'full' if days == 4
            else 'validation' if first_day.isoformat() >= '2026-01-28'
            else 'train'
        )
        cost = {
            ('train', 'train_cost_cut'): 2.0,
            ('train', 'full_sample_trap'): 0.5,
            ('validation', 'train_cost_cut'): 1.0,
            ('validation', 'full_sample_trap'): 0.5,
            ('full', 'train_cost_cut'): 1.0,
            ('full', 'full_sample_trap'): 3.0,
        }[(segment, variant)]
        return {
            'code': code,
            'selected_variant': variant,
            'total_return_pct': cost,
            'alpha_vs_all_in_hold': 10_000.0,
            'cost_reduction_pct': cost,
            'win_rate': 60.0,
            'max_drawdown_pct': -5.0,
            'params': {'selected_variant': variant},
        }

    monkeypatch.setattr(t0_api, '_run_t0_portfolio_with_strategy', fake_run)
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/portfolio', json={
        'code': '688981.SH',
        'initial_capital': 1_000_000,
        'strategy_selection_ratio': 0.5,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['selected_variant'] == 'train_cost_cut'
    assert body['cost_reduction_pct'] == 1.0


def test_t0_portfolio_endpoint_validation_slice_rejects_train_only_variant(
    monkeypatch,
):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _LateBullishFakeTDX())
    monkeypatch.setattr(t0_api, 'choose_t0_allocation', lambda bars, requested_mode='auto': {
        'mode': 'balanced_range',
        'base_position_pct': 0.70,
        't_shares_pct': 0.20,
        'strategy_params': {},
    })
    variants = [
        {'selected_variant': 'train_only_trap'},
        {'selected_variant': 'validation_stable'},
    ]
    monkeypatch.setattr(t0_api, 't0_strategy_variants', lambda allocation: variants)

    def fake_run(code, bars, *, allocation, initial_capital, strategy_params,
                 base_position_pct=None, t_shares_pct=None):
        days = t0_api._count_bar_days(bars)
        first_day = min(t0_api._bar_day(b) for b in bars if t0_api._bar_day(b))
        variant = strategy_params['selected_variant']
        segment = (
            'full' if days == 4
            else 'validation' if first_day.isoformat() >= '2026-01-28'
            else 'train'
        )
        cost = {
            ('train', 'train_only_trap'): 2.2,
            ('train', 'validation_stable'): 1.4,
            ('validation', 'train_only_trap'): -1.3,
            ('validation', 'validation_stable'): 0.8,
            ('full', 'train_only_trap'): 2.8,
            ('full', 'validation_stable'): 1.0,
        }[(segment, variant)]
        return {
            'code': code,
            'selected_variant': variant,
            'total_return_pct': cost,
            'alpha_vs_all_in_hold': 10_000.0,
            'cost_reduction_pct': cost,
            'min_cost_reduction_pct': min(cost, -0.2),
            'cost_reduction_positive_days_pct': 70.0 if cost >= 0 else 20.0,
            'win_rate': 60.0,
            'max_drawdown_pct': -5.0,
            'params': {'selected_variant': variant},
        }

    monkeypatch.setattr(t0_api, '_run_t0_portfolio_with_strategy', fake_run)
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/portfolio', json={
        'code': '688981.SH',
        'initial_capital': 1_000_000,
        'strategy_selection_ratio': 0.5,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['selected_variant'] == 'validation_stable'
    assert body['cost_reduction_pct'] == 1.0


def test_t0_portfolio_endpoint_accepts_cost_floor_stop_param(monkeypatch):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _FakeTDX())
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/portfolio', json={
        'code': '688981.SH',
        'initial_capital': 1_000_000,
        'stop_after_cost_floor_pct': -0.2,
        'fee_bps': 0,
        'sell_tax_bps': 0,
        'slippage_bps': 0,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['params']['stop_after_cost_floor_pct'] == -0.2
    assert body['cost_floor_stop_triggered'] is False


def test_t0_portfolio_endpoint_accepts_vwap_signal_params(monkeypatch):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _FakeTDX())
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/portfolio', json={
        'code': '688981.SH',
        'initial_capital': 1_000_000,
        'signal_mode': 'vwap_deviation',
        'vwap_deviation_pct': 0.9,
        'fee_bps': 0,
        'sell_tax_bps': 0,
        'slippage_bps': 0,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['params']['signal_mode'] == 'vwap_deviation'
    assert body['params']['vwap_deviation_pct'] == 0.9


def test_t0_portfolio_endpoint_accepts_execution_style_param(monkeypatch):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _FakeTDX())
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/portfolio', json={
        'code': '688981.SH',
        'initial_capital': 1_000_000,
        'execution_style': 'next_bar',
        'fee_bps': 0,
        'sell_tax_bps': 0,
        'slippage_bps': 0,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['params']['execution_style'] == 'next_bar'


def test_t0_optimize_endpoint_runs_bounded_parameter_batch(monkeypatch):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _FakeTDX())
    captured = {}

    def fake_optimize(code, bars, **kwargs):
        captured['code'] = code
        captured['bar_count'] = len(bars)
        captured.update(kwargs)
        return {
            'total_grid': 2,
            'offset': kwargs['offset'],
            'limit': kwargs['limit'],
            'evaluated': 1,
            'next_offset': 1,
            'rows': [{
                'score': 9.5,
                'params': {'take_profit_pct': 0.55},
                'full': {'cost_reduction_pct': 1.2},
                'validation': {'cost_reduction_pct': 1.0},
                'folds': [],
            }],
            'rejected_full': 0,
            'rejected_validation': 0,
            'rejected_fold': 0,
        }

    monkeypatch.setattr(t0_api, 'optimize_t0_parameters', fake_optimize)
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/optimize', json={
        'code': '688981.SH',
        'offset': 3,
        'limit': 1,
        'grid': {'take_profit_pct': [0.55, 0.65]},
        'fee_bps': 0,
        'sell_tax_bps': 0,
        'slippage_bps': 0,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['code'] == '688981.SH'
    assert body['data_source'] == 'tdx_sdk'
    assert body['optimizer']['next_offset'] == 1
    assert captured['code'] == '688981.SH'
    assert captured['bar_count'] == 4
    assert captured['offset'] == 3
    assert captured['limit'] == 1
    assert captured['grid'] == {'take_profit_pct': [0.55, 0.65]}
    assert captured['include_base_candidate'] is True
    assert captured['base_params']['signal_mode'] == 'band'
    assert captured['base_params']['execution_style'] == 'market'


def test_t0_optimize_endpoint_uses_validation_aware_base_variant(monkeypatch):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _LateBullishFakeTDX())
    monkeypatch.setattr(t0_api, 'choose_t0_allocation', lambda bars, requested_mode='auto': {
        'mode': 'balanced_range',
        'base_position_pct': 0.70,
        't_shares_pct': 0.20,
        'strategy_params': {},
    })
    variants = [
        {'selected_variant': 'train_only_trap'},
        {'selected_variant': 'validation_stable'},
    ]
    monkeypatch.setattr(t0_api, 't0_strategy_variants', lambda allocation: variants)

    def fake_run(code, bars, *, allocation, initial_capital, strategy_params,
                 base_position_pct=None, t_shares_pct=None):
        days = t0_api._count_bar_days(bars)
        first_day = min(t0_api._bar_day(b) for b in bars if t0_api._bar_day(b))
        variant = strategy_params['selected_variant']
        segment = (
            'full' if days == 4
            else 'validation' if first_day.isoformat() >= '2026-01-28'
            else 'train'
        )
        cost = {
            ('train', 'train_only_trap'): 2.2,
            ('train', 'validation_stable'): 1.4,
            ('validation', 'train_only_trap'): -1.3,
            ('validation', 'validation_stable'): 0.8,
            ('full', 'train_only_trap'): 2.8,
            ('full', 'validation_stable'): 1.0,
        }[(segment, variant)]
        return {
            'code': code,
            'selected_variant': variant,
            'total_return_pct': cost,
            'alpha_vs_all_in_hold': 10_000.0,
            'cost_reduction_pct': cost,
            'min_cost_reduction_pct': min(cost, -0.2),
            'cost_reduction_positive_days_pct': 70.0 if cost >= 0 else 20.0,
            'win_rate': 60.0,
            'max_drawdown_pct': -5.0,
            'params': {'selected_variant': variant},
        }

    monkeypatch.setattr(t0_api, '_run_t0_portfolio_with_strategy', fake_run)
    monkeypatch.setattr(t0_api, 'optimize_t0_parameters', lambda *args, **kwargs: {
        'total_grid': 1,
        'offset': 0,
        'limit': 1,
        'evaluated': 1,
        'next_offset': None,
        'rows': [],
        'rejected_full': 0,
        'rejected_validation': 0,
        'rejected_fold': 0,
    })
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/optimize', json={
        'code': '688981.SH',
        'strategy_selection_ratio': 0.5,
        'grid': {'take_profit_pct': [0.55]},
        'limit': 1,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['base_variant'] == 'validation_stable'


def test_t0_optimize_endpoint_preserves_selected_base_signal_and_execution(
    monkeypatch,
):
    import api.t0 as t0_api
    monkeypatch.setattr(t0_api, 'tdx', _FakeTDX())
    monkeypatch.setattr(t0_api, 'choose_t0_allocation', lambda bars, requested_mode='auto': {
        'mode': 'balanced_range',
        'base_position_pct': 0.70,
        't_shares_pct': 0.20,
        'strategy_params': {},
    })
    monkeypatch.setattr(
        t0_api,
        't0_strategy_variants',
        lambda allocation: [{
            'selected_variant': 'default',
            'signal_mode': 'band',
            'execution_style': 'market',
        }],
    )
    captured = {}

    def fake_optimize(code, bars, **kwargs):
        captured.update(kwargs)
        return {
            'total_grid': 1,
            'offset': 0,
            'limit': 1,
            'evaluated': 1,
            'next_offset': None,
            'rows': [],
            'rejected_full': 0,
            'rejected_validation': 0,
            'rejected_fold': 0,
        }

    monkeypatch.setattr(t0_api, 'optimize_t0_parameters', fake_optimize)
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/optimize', json={
        'code': '688981.SH',
        'grid': {'take_profit_pct': [0.55]},
        'limit': 1,
    })

    assert resp.status_code == 200
    assert captured['base_params']['signal_mode'] == 'band'
    assert captured['base_params']['execution_style'] == 'market'


def test_t0_optimize_endpoint_uses_named_strategy_profile_grid(monkeypatch):
    import api.t0 as t0_api
    from t0.strategy_profiles import get_t0_strategy_profile
    monkeypatch.setattr(t0_api, 'tdx', _FakeTDX())
    monkeypatch.setattr(t0_api, 'choose_t0_allocation', lambda bars, requested_mode='auto': {
        'mode': 'balanced_range',
        'base_position_pct': 0.70,
        't_shares_pct': 0.20,
        'strategy_params': {},
    })
    monkeypatch.setattr(
        t0_api,
        't0_strategy_variants',
        lambda allocation: [{
            'selected_variant': 'default',
            'signal_mode': 'band',
            'execution_style': 'market',
        }],
    )
    captured = {}

    def fake_optimize(code, bars, **kwargs):
        captured.update(kwargs)
        return {
            'total_grid': 1,
            'offset': 0,
            'limit': 1,
            'evaluated': 1,
            'next_offset': None,
            'rows': [],
            'rejected_full': 0,
            'rejected_validation': 0,
            'rejected_fold': 0,
        }

    monkeypatch.setattr(t0_api, 'optimize_t0_parameters', fake_optimize)
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/optimize', json={
        'code': '688981.SH',
        'strategy_profile': 'adaptive_vwap_cost',
        'limit': 1,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['strategy_profile'] == 'adaptive_vwap_cost'
    assert captured['grid'] == get_t0_strategy_profile(
        'adaptive_vwap_cost',
    ).optimizer_grid


def test_run_t0_portfolio_with_strategy_lets_profile_params_override_allocation(
    monkeypatch,
):
    import api.t0 as t0_api
    captured = {}

    def fake_backtest(code, bars, **kwargs):
        captured.update(kwargs)
        return {'params': kwargs, 'selected_variant': 'profile_override'}

    monkeypatch.setattr(t0_api, 'run_t0_portfolio_backtest', fake_backtest)

    t0_api._run_t0_portfolio_with_strategy(
        '688981.SH',
        [{'date': '2026-01-01 09:31:00', 'close': 10.0}],
        allocation={'base_position_pct': 0.70, 't_shares_pct': 0.20},
        initial_capital=1_000_000.0,
        base_position_pct=0.75,
        t_shares_pct=0.25,
        strategy_params={
            'selected_variant': 'profile_override',
            'base_position_pct': 0.55,
            't_shares_pct': 0.15,
        },
    )

    assert captured['base_position_pct'] == 0.55
    assert captured['t_shares_pct'] == 0.15


def test_default_t0_optimizer_grid_sweeps_signal_and_execution_layers():
    import api.t0 as t0_api

    assert t0_api.DEFAULT_T0_OPTIMIZER_GRID['signal_mode'] == [
        'band',
        'hybrid',
        'adaptive_vwap',
        'hybrid_adaptive',
    ]
    assert t0_api.DEFAULT_T0_OPTIMIZER_GRID['vwap_zscore_threshold'] == [
        1.2,
        1.5,
        1.8,
    ]
    assert t0_api.DEFAULT_T0_OPTIMIZER_GRID['execution_style'] == [
        'market',
        'next_bar',
    ]


def test_default_t0_optimizer_grid_interleaves_signal_zscore_and_execution_early():
    import api.t0 as t0_api
    from t0.optimizer import iter_parameter_grid

    first_signal_block = list(iter_parameter_grid(
        t0_api.DEFAULT_T0_OPTIMIZER_GRID,
        limit=24,
    ))
    signal_execution_pairs = {
        (row['signal_mode'], row['execution_style'])
        for row in first_signal_block
    }
    adaptive_zscores = {
        row['vwap_zscore_threshold']
        for row in first_signal_block
        if row['signal_mode'] == 'adaptive_vwap'
    }

    assert signal_execution_pairs == {
        ('band', 'market'),
        ('band', 'next_bar'),
        ('hybrid', 'market'),
        ('hybrid', 'next_bar'),
        ('adaptive_vwap', 'market'),
        ('adaptive_vwap', 'next_bar'),
        ('hybrid_adaptive', 'market'),
        ('hybrid_adaptive', 'next_bar'),
    }
    assert adaptive_zscores == {1.2, 1.5, 1.8}


def test_t0_portfolio_endpoint_falls_back_to_local_lc1_when_tdx_has_no_bars(
    monkeypatch,
    tmp_path,
):
    import api.t0 as t0_api
    root = _write_lc1(tmp_path, '688981.SH', [
        100.0, 98.0, 101.0, 101.0,
        102.0, 100.0, 103.0, 103.0,
    ])
    monkeypatch.setattr(t0_api, 'tdx', _EmptyTDX())
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/portfolio', json={
        'code': '688981.SH',
        'roots': [str(root)],
        'initial_capital': 1_000_000,
        'fee_bps': 0,
        'sell_tax_bps': 0,
        'slippage_bps': 0,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['code'] == '688981.SH'
    assert body['bar_count'] == 8
    assert body['data_source'] == 'local_lc1'
