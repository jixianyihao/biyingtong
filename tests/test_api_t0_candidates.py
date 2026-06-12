from __future__ import annotations

import struct
from pathlib import Path

from flask import Flask

from api.t0 import (
    _T0_PORTFOLIO_PREVIEW_CACHE,
    _fold_min_trips,
    _preview_cost_path_allowed,
    _preview_drawdown_allowed,
    _preview_fold_result_passes,
    _preview_sort_key,
    _preview_win_rate_allowed,
)


def _fresh_flask_app():
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


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
            close,
            close * 1.02,
            close * 0.98,
            close,
            close * 100_000,
            100_000,
            0,
        ))
    file_path = target / f'{market}{raw}.lc1'
    file_path.write_bytes(b''.join(rows))
    return target


def test_t0_candidates_endpoint_scans_local_lc1_files(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [10 + i * 0.05 for i in range(80)])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 10,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['count'] == 1
    assert body['rows'][0]['code'] == '688981.SH'
    assert body['rows'][0]['bar_count'] == 80


def test_t0_candidates_endpoint_can_attach_portfolio_preview(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [
        100.0, 98.0, 101.0, 101.0,
        102.0, 100.0, 103.0, 103.0,
    ])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 2,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
        'with_backtest': True,
        'preview_pool': 5,
        'min_preview_trips': 0,
    })

    assert resp.status_code == 200
    row = resp.get_json()['rows'][0]
    assert row['code'] == '688981.SH'
    assert row['preview_total_return_pct'] is not None
    assert row['preview_alpha_vs_all_in'] is not None
    assert row['preview_round_trips'] >= 0
    assert row['preview_cost_reduction_pct'] is not None
    assert row['preview_cost_reduction_per_share'] is not None
    assert row['preview_min_cost_reduction_pct'] is not None
    assert row['preview_cost_reduction_positive_days_pct'] is not None


def test_run_t0_portfolio_with_strategy_reuses_same_preview(monkeypatch):
    import api.t0 as t0_api
    _T0_PORTFOLIO_PREVIEW_CACHE.clear()
    calls = 0

    def fake_backtest(*args, **kwargs):
        nonlocal calls
        calls += 1
        return {
            'total_return_pct': 1.23,
            'final_equity': 1_012_300.0,
            'alpha_vs_all_in_hold': 100.0,
            'alpha_vs_base_hold': 100.0,
            'round_trips': 3,
            'win_rate': 66.7,
            'max_drawdown_pct': -0.5,
            'cost_reduction_pct': 0.8,
            'cost_reduction_per_share': 0.1,
            'min_cost_reduction_pct': -0.2,
            'cost_reduction_positive_days_pct': 80.0,
        }

    monkeypatch.setattr(t0_api, 'run_t0_portfolio_backtest', fake_backtest)
    bars = [
        {'date': '2026-05-01 09:31', 'open': 10, 'high': 11, 'low': 9, 'close': 10, 'vol': 100},
        {'date': '2026-05-01 09:32', 'open': 10, 'high': 11, 'low': 9, 'close': 10.5, 'vol': 110},
    ]
    kwargs = {
        'allocation': {'base_position_pct': 80.0, 't_shares_pct': 20.0},
        'initial_capital': 1_000_000.0,
        'strategy_params': {
            'selected_variant': 'default',
            'signal_mode': 'band',
            'execution_style': 'next_bar',
        },
    }

    first = t0_api._run_t0_portfolio_with_strategy('688981.SH', bars, **kwargs)
    first['total_return_pct'] = -99.0
    second = t0_api._run_t0_portfolio_with_strategy('688981.SH', bars, **kwargs)

    assert calls == 1
    assert second['total_return_pct'] == 1.23
    assert second['selected_variant'] == 'default'


def test_t0_candidates_endpoint_can_attach_next_bar_stress_preview(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [
        100.0, 98.0, 101.0, 101.0,
        102.0, 100.0, 103.0, 103.0,
    ])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 2,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
        'with_backtest': True,
        'with_next_bar_stress': True,
        'preview_pool': 5,
        'min_preview_trips': 0,
    })

    assert resp.status_code == 200
    row = resp.get_json()['rows'][0]
    assert row['preview_next_bar_total_return_pct'] is not None
    assert row['preview_next_bar_cost_reduction_pct'] is not None
    assert row['preview_next_bar_min_cost_reduction_pct'] is not None
    assert row['preview_next_bar_round_trips'] >= 0
    assert row['preview_next_bar_selected_variant'] == (
        f"{row['preview_selected_variant']}_next_bar_stress"
    )


def test_t0_candidates_endpoint_filters_by_next_bar_stress_cost(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [
        100.0, 98.0, 101.0, 101.0,
        102.0, 100.0, 103.0, 103.0,
    ])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 2,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
        'with_backtest': True,
        'with_next_bar_stress': True,
        'preview_pool': 5,
        'min_preview_trips': 0,
        'min_preview_next_bar_cost_reduction_pct': 999.0,
    })

    assert resp.status_code == 200
    assert resp.get_json()['rows'] == []


def test_t0_candidates_endpoint_skips_next_bar_stress_when_preview_fails(
    monkeypatch,
):
    import api.t0 as t0_api
    next_bar_calls = []

    monkeypatch.setattr(t0_api, 'scan_lc1_candidates', lambda *a, **k: [{
        'code': '688981.SH',
        'bar_count': 8,
        'days': 2,
    }])
    monkeypatch.setattr(t0_api, 'load_lc1_bars_for_code', lambda *a, **k: [
        {'date': '2026-05-01 09:31', 'close': 100.0},
        {'date': '2026-05-01 09:32', 'close': 99.0},
        {'date': '2026-05-02 09:31', 'close': 98.0},
        {'date': '2026-05-02 09:32', 'close': 97.0},
    ])
    monkeypatch.setattr(t0_api, 'choose_t0_allocation', lambda *a, **k: {
        'base_position_pct': 80.0,
        't_shares_pct': 20.0,
    })
    monkeypatch.setattr(
        t0_api,
        't0_strategy_variants',
        lambda allocation: [{'selected_variant': 'default'}],
    )
    monkeypatch.setattr(
        t0_api,
        'choose_best_t0_result',
        lambda results: {
            'selected_variant': 'default',
            'total_return_pct': 1.0,
            'alpha_vs_all_in_hold': 1_000.0,
            'cost_reduction_pct': 1.0,
            'min_cost_reduction_pct': 1.0,
            'cost_reduction_positive_days_pct': 100.0,
        },
    )

    def fake_run(*args, **kwargs):
        params = kwargs['strategy_params']
        if params.get('execution_style') == 'next_bar':
            next_bar_calls.append(params)
        return {
            'selected_variant': params.get('selected_variant', 'default'),
            'total_return_pct': -9.0,
            'final_equity': 910_000.0,
            'alpha_vs_all_in_hold': -10_000.0,
            'alpha_vs_base_hold': -10_000.0,
            'round_trips': 1,
            'win_rate': 0.0,
            'max_drawdown_pct': -9.0,
            'cost_reduction_pct': -1.0,
            'cost_reduction_per_share': -0.1,
            'min_cost_reduction_pct': -1.0,
            'cost_reduction_positive_days_pct': 0.0,
        }

    monkeypatch.setattr(t0_api, '_run_t0_portfolio_with_strategy', fake_run)
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'top': 5,
        'with_backtest': True,
        'with_next_bar_stress': True,
        'preview_pool': 5,
        'min_preview_return_pct': 0.0,
    })

    assert resp.status_code == 200
    assert resp.get_json()['rows'] == []
    assert next_bar_calls == []


def test_t0_candidates_endpoint_uses_validation_aware_variant(monkeypatch):
    import api.t0 as t0_api

    bars = [
        {'date': '2026-05-01 09:31', 'close': 100.0},
        {'date': '2026-05-02 09:31', 'close': 101.0},
        {'date': '2026-05-03 09:31', 'close': 102.0},
        {'date': '2026-05-04 09:31', 'close': 103.0},
    ]
    monkeypatch.setattr(t0_api, 'scan_lc1_candidates', lambda *a, **k: [{
        'code': '688981.SH',
        'bar_count': len(bars),
        'days': 4,
    }])
    monkeypatch.setattr(t0_api, 'load_lc1_bars_for_code', lambda *a, **k: bars)
    monkeypatch.setattr(t0_api, 'choose_t0_allocation', lambda *a, **k: {
        'base_position_pct': 80.0,
        't_shares_pct': 20.0,
    })
    monkeypatch.setattr(
        t0_api,
        't0_strategy_variants',
        lambda allocation: [
            {'selected_variant': 'train_only_trap'},
            {'selected_variant': 'validation_stable'},
        ],
    )

    def fake_run(code, run_bars, **kwargs):
        days = t0_api._count_bar_days(run_bars)
        first_day = min(t0_api._bar_day(b) for b in run_bars if t0_api._bar_day(b))
        variant = kwargs['strategy_params']['selected_variant']
        segment = (
            'full' if days == 4
            else 'validation' if first_day.isoformat() >= '2026-05-03'
            else 'train'
        )
        cost = {
            ('train', 'train_only_trap'): 2.0,
            ('train', 'validation_stable'): 1.0,
            ('validation', 'train_only_trap'): -1.0,
            ('validation', 'validation_stable'): 0.5,
            ('full', 'train_only_trap'): 2.5,
            ('full', 'validation_stable'): 1.2,
        }[(segment, variant)]
        return {
            'selected_variant': variant,
            'total_return_pct': cost,
            'final_equity': 1_000_000.0 + cost * 1_000.0,
            'alpha_vs_all_in_hold': 1_000.0,
            'alpha_vs_base_hold': 1_000.0,
            'round_trips': 4,
            'win_rate': 75.0,
            'max_drawdown_pct': -0.1,
            'cost_reduction_pct': cost,
            'cost_reduction_per_share': 0.1,
            'min_cost_reduction_pct': min(cost, -0.2),
            'cost_reduction_positive_days_pct': 80.0 if cost >= 0 else 20.0,
        }

    monkeypatch.setattr(t0_api, '_run_t0_portfolio_with_strategy', fake_run)
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'top': 5,
        'with_backtest': True,
        'preview_pool': 5,
        'preview_validation_ratio': 0.5,
        'min_preview_trips': 0,
        'min_preview_validation_trips': 0,
        'min_preview_cost_reduction_pct': 0.0,
        'min_preview_validation_cost_reduction_pct': 0.0,
    })

    assert resp.status_code == 200
    row = resp.get_json()['rows'][0]
    assert row['preview_selected_variant'] == 'validation_stable'
    assert row['preview_validation_cost_reduction_pct'] == 0.5


def test_t0_candidates_endpoint_can_attach_optimizer_preview(monkeypatch):
    import api.t0 as t0_api
    captured = {}

    bars = [
        {'date': '2026-05-01 09:31', 'close': 100.0},
        {'date': '2026-05-02 09:31', 'close': 101.0},
        {'date': '2026-05-03 09:31', 'close': 102.0},
        {'date': '2026-05-04 09:31', 'close': 103.0},
    ]
    monkeypatch.setattr(t0_api, 'scan_lc1_candidates', lambda *a, **k: [{
        'code': '688981.SH',
        'bar_count': len(bars),
        'days': 4,
    }])
    monkeypatch.setattr(t0_api, 'load_lc1_bars_for_code', lambda *a, **k: bars)
    monkeypatch.setattr(t0_api, 'choose_t0_allocation', lambda *a, **k: {
        'base_position_pct': 80.0,
        't_shares_pct': 20.0,
    })
    monkeypatch.setattr(
        t0_api,
        't0_strategy_variants',
        lambda allocation: [{'selected_variant': 'default'}],
    )

    def fake_run(code, run_bars, **kwargs):
        return {
            'selected_variant': kwargs['strategy_params'].get(
                'selected_variant', 'default',
            ),
            'total_return_pct': 1.0,
            'final_equity': 1_010_000.0,
            'alpha_vs_all_in_hold': 1_000.0,
            'alpha_vs_base_hold': 1_000.0,
            'round_trips': 4,
            'win_rate': 75.0,
            'max_drawdown_pct': -0.1,
            'cost_reduction_pct': 1.0,
            'cost_reduction_per_share': 0.1,
            'min_cost_reduction_pct': -0.2,
            'cost_reduction_positive_days_pct': 80.0,
        }

    def fake_optimize(code, opt_bars, **kwargs):
        captured['code'] = code
        captured.update(kwargs)
        return {
            'total_grid': 2,
            'offset': 0,
            'limit': kwargs['limit'],
            'evaluated': 2,
            'next_offset': None,
            'rejected_full': 0,
            'rejected_validation': 0,
            'rejected_fold': 0,
            'rows': [{
                'score': 12.34,
                'params': {'take_profit_pct': 0.55},
                'full': {'cost_reduction_pct': 2.2},
                'validation': {'cost_reduction_pct': 1.1},
                'folds': [],
                'fold_count': 3,
                'fold_pass_count': 3,
                'fold_pass_rate_pct': 100.0,
                'worst_fold_cost_reduction_pct': 0.2,
                'worst_fold_min_cost_reduction_pct': -0.1,
                'avg_fold_cost_reduction_pct': 0.5,
            }],
        }

    monkeypatch.setattr(t0_api, '_run_t0_portfolio_with_strategy', fake_run)
    monkeypatch.setattr(t0_api, 'optimize_t0_parameters', fake_optimize)
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'top': 5,
        'with_backtest': True,
        'with_optimizer': True,
        'optimizer_limit': 2,
        'preview_pool': 5,
        'min_preview_trips': 0,
        'min_preview_validation_trips': 0,
    })

    assert resp.status_code == 200
    row = resp.get_json()['rows'][0]
    assert captured['code'] == '688981.SH'
    assert captured['include_base_candidate'] is True
    assert row['optimizer_evaluated'] == 2
    assert row['optimizer_best_score'] == 12.34
    assert row['optimizer_best_cost_reduction_pct'] == 2.2
    assert row['optimizer_best_validation_cost_reduction_pct'] == 1.1
    assert row['optimizer_best_fold_pass_rate_pct'] == 100.0
    assert row['optimizer_best_worst_fold_cost_reduction_pct'] == 0.2
    assert row['optimizer_best_params'] == {'take_profit_pct': 0.55}


def test_t0_candidates_endpoint_can_attach_walk_forward_preview(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [
        100.0, 98.0, 101.0, 101.0,
        102.0, 100.0, 103.0, 103.0,
        104.0, 102.0, 105.0, 105.0,
        106.0, 104.0, 107.0, 107.0,
    ])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 4,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
        'with_backtest': True,
        'preview_pool': 5,
        'preview_validation_ratio': 0.5,
        'min_preview_trips': 0,
    })

    assert resp.status_code == 200
    row = resp.get_json()['rows'][0]
    assert row['preview_train_total_return_pct'] is not None
    assert row['preview_train_alpha_vs_all_in'] is not None
    assert row['preview_train_cost_reduction_pct'] is not None
    assert row['preview_train_min_cost_reduction_pct'] is not None
    assert row['preview_train_cost_reduction_positive_days_pct'] is not None
    assert row['preview_validation_total_return_pct'] is not None
    assert row['preview_validation_alpha_vs_all_in'] is not None
    assert row['preview_validation_cost_reduction_pct'] is not None
    assert row['preview_validation_cost_reduction_per_share'] is not None
    assert row['preview_validation_min_cost_reduction_pct'] is not None
    assert row['preview_validation_cost_reduction_positive_days_pct'] is not None


def test_t0_candidates_endpoint_reports_validation_fold_stability(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [
        100.0, 98.0, 101.0, 101.0,
        102.0, 100.0, 103.0, 103.0,
        104.0, 102.0, 105.0, 105.0,
        106.0, 104.0, 107.0, 107.0,
        108.0, 106.0, 109.0, 109.0,
        110.0, 108.0, 111.0, 111.0,
        112.0, 110.0, 113.0, 113.0,
        114.0, 112.0, 115.0, 115.0,
    ])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 8,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
        'with_backtest': True,
        'preview_pool': 5,
        'preview_validation_ratio': 0.75,
        'preview_validation_folds': 3,
        'min_preview_trips': 0,
        'min_preview_validation_pass_rate_pct': 0.0,
    })

    assert resp.status_code == 200
    row = resp.get_json()['rows'][0]
    assert row['preview_validation_fold_count'] == 3
    assert row['preview_validation_pass_count'] == 3
    assert row['preview_validation_pass_rate_pct'] == 100.0
    assert row['preview_validation_worst_cost_reduction_pct'] is not None
    assert row['preview_validation_worst_min_cost_reduction_pct'] is not None
    assert row['preview_validation_avg_cost_reduction_pct'] is not None


def test_t0_candidates_endpoint_reports_validation_next_bar_fold_stress(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [
        100.0, 98.0, 101.0, 101.0,
        102.0, 100.0, 103.0, 103.0,
        104.0, 102.0, 105.0, 105.0,
        106.0, 104.0, 107.0, 107.0,
        108.0, 106.0, 109.0, 109.0,
        110.0, 108.0, 111.0, 111.0,
        112.0, 110.0, 113.0, 113.0,
        114.0, 112.0, 115.0, 115.0,
    ])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 8,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
        'with_backtest': True,
        'with_next_bar_stress': True,
        'preview_pool': 5,
        'preview_validation_ratio': 0.75,
        'preview_validation_folds': 3,
        'min_preview_trips': 0,
        'min_preview_validation_pass_rate_pct': 0.0,
    })

    assert resp.status_code == 200
    row = resp.get_json()['rows'][0]
    assert row['preview_validation_next_bar_fold_count'] == 3
    assert row['preview_validation_next_bar_pass_count'] == 3
    assert row['preview_validation_next_bar_pass_rate_pct'] == 100.0
    assert row['preview_validation_next_bar_worst_cost_reduction_pct'] is not None
    assert row['preview_validation_next_bar_worst_min_cost_reduction_pct'] is not None
    assert row['preview_validation_next_bar_avg_cost_reduction_pct'] is not None


def test_t0_candidates_endpoint_filters_by_validation_fold_pass_rate(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [
        100.0, 98.0, 101.0, 101.0,
        102.0, 100.0, 103.0, 103.0,
        104.0, 102.0, 105.0, 105.0,
        106.0, 104.0, 107.0, 107.0,
    ])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 4,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
        'with_backtest': True,
        'preview_pool': 5,
        'preview_validation_ratio': 0.5,
        'preview_validation_folds': 2,
        'min_preview_trips': 0,
        'min_preview_validation_pass_rate_pct': 101.0,
    })

    assert resp.status_code == 200
    assert resp.get_json()['rows'] == []


def test_t0_candidates_endpoint_allows_looser_fold_cost_than_validation_total(
    monkeypatch,
):
    import api.t0 as t0_api

    bars = [
        {'date': '2026-05-01 09:31', 'close': 100.0},
        {'date': '2026-05-02 09:31', 'close': 101.0},
        {'date': '2026-05-03 09:31', 'close': 102.0},
        {'date': '2026-05-04 09:31', 'close': 103.0},
    ]
    monkeypatch.setattr(t0_api, 'scan_lc1_candidates', lambda *a, **k: [{
        'code': '688981.SH',
        'bar_count': len(bars),
        'days': 4,
    }])
    monkeypatch.setattr(t0_api, 'load_lc1_bars_for_code', lambda *a, **k: bars)
    monkeypatch.setattr(t0_api, 'choose_t0_allocation', lambda *a, **k: {
        'base_position_pct': 80.0,
        't_shares_pct': 20.0,
    })
    monkeypatch.setattr(
        t0_api,
        't0_strategy_variants',
        lambda allocation: [{'selected_variant': 'default'}],
    )
    monkeypatch.setattr(
        t0_api,
        'choose_best_t0_result',
        lambda results: {
            'selected_variant': 'default',
            'total_return_pct': 1.0,
            'alpha_vs_all_in_hold': 1_000.0,
            'cost_reduction_pct': 1.0,
            'min_cost_reduction_pct': 1.0,
            'cost_reduction_positive_days_pct': 100.0,
        },
    )

    def fake_run(code, run_bars, **kwargs):
        cost = -0.5 if len(run_bars) == 1 else 1.0
        return {
            'selected_variant': kwargs['strategy_params'].get(
                'selected_variant', 'default',
            ),
            'total_return_pct': 1.0,
            'final_equity': 1_010_000.0,
            'alpha_vs_all_in_hold': 1_000.0,
            'alpha_vs_base_hold': 1_000.0,
            'round_trips': max(1, len(run_bars)),
            'win_rate': 100.0,
            'max_drawdown_pct': -0.1,
            'cost_reduction_pct': cost,
            'cost_reduction_per_share': 0.1,
            'min_cost_reduction_pct': cost,
            'cost_reduction_positive_days_pct': 100.0,
        }

    monkeypatch.setattr(t0_api, '_run_t0_portfolio_with_strategy', fake_run)
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'top': 5,
        'with_backtest': True,
        'preview_pool': 5,
        'preview_validation_ratio': 0.5,
        'preview_validation_folds': 2,
        'min_preview_trips': 0,
        'min_preview_validation_trips': 2,
        'min_preview_validation_cost_reduction_pct': 0.0,
        'min_preview_validation_fold_cost_reduction_pct': -1.0,
        'min_preview_validation_pass_rate_pct': 100.0,
    })

    assert resp.status_code == 200
    row = resp.get_json()['rows'][0]
    assert row['preview_validation_cost_reduction_pct'] == 1.0
    assert row['preview_validation_worst_cost_reduction_pct'] == -0.5
    assert row['preview_validation_pass_rate_pct'] == 100.0


def test_t0_candidates_endpoint_filters_by_validation_next_bar_fold_pass_rate(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [
        100.0, 98.0, 101.0, 101.0,
        102.0, 100.0, 103.0, 103.0,
        104.0, 102.0, 105.0, 105.0,
        106.0, 104.0, 107.0, 107.0,
    ])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 4,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
        'with_backtest': True,
        'with_next_bar_stress': True,
        'preview_pool': 5,
        'preview_validation_ratio': 0.5,
        'preview_validation_folds': 2,
        'min_preview_trips': 0,
        'min_preview_validation_pass_rate_pct': 0.0,
        'min_preview_validation_next_bar_pass_rate_pct': 101.0,
    })

    assert resp.status_code == 200
    assert resp.get_json()['rows'] == []


def test_t0_candidates_endpoint_can_filter_negative_preview_returns(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [
        100.0, 98.0, 97.0, 96.0,
        95.0, 94.0, 93.0, 92.0,
    ])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 2,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
        'with_backtest': True,
        'preview_pool': 5,
        'min_preview_trips': 0,
        'min_preview_return_pct': 0,
    })

    assert resp.status_code == 200
    assert resp.get_json()['rows'] == []


def test_t0_candidates_endpoint_can_filter_insufficient_preview_cost_reduction(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [
        100.0, 98.0, 97.0, 96.0,
        95.0, 94.0, 93.0, 92.0,
    ])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 2,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
        'with_backtest': True,
        'preview_pool': 5,
        'min_preview_trips': 0,
        'min_preview_return_pct': -999.0,
        'min_preview_alpha_vs_all_in': -999_000.0,
        'min_preview_cost_reduction_pct': 0.1,
    })

    assert resp.status_code == 200
    assert resp.get_json()['rows'] == []


def test_t0_candidates_endpoint_can_filter_negative_preview_alpha(tmp_path):
    root = _write_lc1(tmp_path, '688981.SH', [
        100.0, 98.0, 101.0, 101.0,
        102.0, 100.0, 103.0, 103.0,
    ])
    app = _fresh_flask_app()

    resp = app.test_client().post('/api/t0/candidates', json={
        'roots': [str(root)],
        'top': 5,
        'min_days': 2,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
        'with_backtest': True,
        'preview_pool': 5,
        'min_preview_trips': 0,
        'min_preview_alpha_vs_all_in': 1_000_000,
    })

    assert resp.status_code == 200
    assert resp.get_json()['rows'] == []


def test_previewed_candidates_sort_by_return_after_alpha_filter():
    rows = [
        {
            'code': 'low-return-high-alpha',
            'preview_total_return_pct': 1.1,
            'preview_alpha_vs_all_in': 31_000.0,
            'preview_round_trips': 70,
        },
        {
            'code': 'high-return-positive-alpha',
            'preview_total_return_pct': 13.1,
            'preview_alpha_vs_all_in': 4_000.0,
            'preview_round_trips': 49,
        },
    ]

    rows.sort(key=_preview_sort_key, reverse=True)

    assert [r['code'] for r in rows] == [
        'high-return-positive-alpha',
        'low-return-high-alpha',
    ]


def test_previewed_candidates_sort_by_validation_return_when_available():
    rows = [
        {
            'code': 'high-full-return-bad-validation',
            'preview_total_return_pct': 20.0,
            'preview_alpha_vs_all_in': 50_000.0,
            'preview_validation_total_return_pct': -1.0,
            'preview_validation_alpha_vs_all_in': -3_000.0,
            'preview_round_trips': 80,
        },
        {
            'code': 'lower-full-return-good-validation',
            'preview_total_return_pct': 8.0,
            'preview_alpha_vs_all_in': 12_000.0,
            'preview_validation_total_return_pct': 2.0,
            'preview_validation_alpha_vs_all_in': 2_000.0,
            'preview_round_trips': 30,
        },
    ]

    rows.sort(key=_preview_sort_key, reverse=True)

    assert rows[0]['code'] == 'lower-full-return-good-validation'


def test_previewed_candidates_sort_by_validation_cost_reduction_first():
    rows = [
        {
            'code': 'higher-validation-return-lower-cost-cut',
            'preview_total_return_pct': 20.0,
            'preview_alpha_vs_all_in': 50_000.0,
            'preview_cost_reduction_pct': 1.0,
            'preview_validation_total_return_pct': 5.0,
            'preview_validation_alpha_vs_all_in': 5_000.0,
            'preview_validation_cost_reduction_pct': 0.6,
            'preview_round_trips': 80,
        },
        {
            'code': 'lower-validation-return-better-cost-cut',
            'preview_total_return_pct': 8.0,
            'preview_alpha_vs_all_in': 12_000.0,
            'preview_cost_reduction_pct': 3.0,
            'preview_validation_total_return_pct': 2.0,
            'preview_validation_alpha_vs_all_in': 2_000.0,
            'preview_validation_cost_reduction_pct': 2.1,
            'preview_round_trips': 30,
        },
    ]

    rows.sort(key=_preview_sort_key, reverse=True)

    assert rows[0]['code'] == 'lower-validation-return-better-cost-cut'


def test_previewed_candidates_sort_by_validation_cost_path_on_tie():
    rows = [
        {
            'code': 'choppy-cost-cut',
            'preview_total_return_pct': 10.0,
            'preview_alpha_vs_all_in': 10_000.0,
            'preview_cost_reduction_pct': 2.0,
            'preview_validation_total_return_pct': 5.0,
            'preview_validation_alpha_vs_all_in': 5_000.0,
            'preview_validation_cost_reduction_pct': 1.5,
            'preview_validation_min_cost_reduction_pct': -2.0,
            'preview_validation_cost_reduction_positive_days_pct': 55.0,
            'preview_round_trips': 80,
        },
        {
            'code': 'smooth-cost-cut',
            'preview_total_return_pct': 7.0,
            'preview_alpha_vs_all_in': 8_000.0,
            'preview_cost_reduction_pct': 2.0,
            'preview_validation_total_return_pct': 3.0,
            'preview_validation_alpha_vs_all_in': 4_000.0,
            'preview_validation_cost_reduction_pct': 1.5,
            'preview_validation_min_cost_reduction_pct': -0.2,
            'preview_validation_cost_reduction_positive_days_pct': 90.0,
            'preview_round_trips': 50,
        },
    ]

    rows.sort(key=_preview_sort_key, reverse=True)

    assert rows[0]['code'] == 'smooth-cost-cut'


def test_previewed_candidates_sort_by_validation_fold_stability_first():
    rows = [
        {
            'code': 'strong-tail-unstable-folds',
            'preview_total_return_pct': 10.0,
            'preview_alpha_vs_all_in': 10_000.0,
            'preview_cost_reduction_pct': 2.0,
            'preview_validation_total_return_pct': 6.0,
            'preview_validation_alpha_vs_all_in': 6_000.0,
            'preview_validation_cost_reduction_pct': 3.0,
            'preview_validation_min_cost_reduction_pct': 0.2,
            'preview_validation_cost_reduction_positive_days_pct': 80.0,
            'preview_validation_fold_count': 3,
            'preview_validation_pass_rate_pct': 33.3333,
            'preview_validation_worst_cost_reduction_pct': -1.2,
            'preview_validation_worst_min_cost_reduction_pct': -2.0,
            'preview_round_trips': 80,
        },
        {
            'code': 'lower-tail-stable-folds',
            'preview_total_return_pct': 7.0,
            'preview_alpha_vs_all_in': 8_000.0,
            'preview_cost_reduction_pct': 1.5,
            'preview_validation_total_return_pct': 3.0,
            'preview_validation_alpha_vs_all_in': 3_000.0,
            'preview_validation_cost_reduction_pct': 1.4,
            'preview_validation_min_cost_reduction_pct': 0.1,
            'preview_validation_cost_reduction_positive_days_pct': 75.0,
            'preview_validation_fold_count': 3,
            'preview_validation_pass_rate_pct': 100.0,
            'preview_validation_worst_cost_reduction_pct': 0.3,
            'preview_validation_worst_min_cost_reduction_pct': -0.4,
            'preview_round_trips': 50,
        },
    ]

    rows.sort(key=_preview_sort_key, reverse=True)

    assert rows[0]['code'] == 'lower-tail-stable-folds'


def test_previewed_candidates_sort_by_optimizer_preview_when_available():
    rows = [
        {
            'code': 'preview-good-optimizer-weak',
            'preview_validation_cost_reduction_pct': 5.0,
            'preview_validation_pass_rate_pct': 100.0,
            'preview_validation_worst_cost_reduction_pct': 2.0,
            'preview_validation_min_cost_reduction_pct': -0.1,
            'preview_validation_total_return_pct': 4.0,
            'preview_validation_alpha_vs_all_in': 20_000.0,
            'preview_round_trips': 80,
            'optimizer_best_cost_reduction_pct': 0.4,
            'optimizer_best_validation_cost_reduction_pct': 0.2,
            'optimizer_best_fold_pass_rate_pct': 66.0,
            'optimizer_best_worst_fold_cost_reduction_pct': -0.5,
        },
        {
            'code': 'preview-ok-optimizer-strong',
            'preview_validation_cost_reduction_pct': 1.0,
            'preview_validation_pass_rate_pct': 66.0,
            'preview_validation_worst_cost_reduction_pct': 0.2,
            'preview_validation_min_cost_reduction_pct': -0.3,
            'preview_validation_total_return_pct': 1.0,
            'preview_validation_alpha_vs_all_in': 5_000.0,
            'preview_round_trips': 40,
            'optimizer_best_cost_reduction_pct': 2.0,
            'optimizer_best_validation_cost_reduction_pct': 1.4,
            'optimizer_best_fold_pass_rate_pct': 100.0,
            'optimizer_best_worst_fold_cost_reduction_pct': 0.3,
        },
    ]

    rows.sort(key=_preview_sort_key, reverse=True)

    assert rows[0]['code'] == 'preview-ok-optimizer-strong'


def test_previewed_candidates_sort_by_next_bar_stress_cost_first():
    rows = [
        {
            'code': 'market-good-next-bar-bad',
            'preview_total_return_pct': 10.0,
            'preview_alpha_vs_all_in': 10_000.0,
            'preview_cost_reduction_pct': 3.0,
            'preview_validation_cost_reduction_pct': 2.0,
            'preview_validation_pass_rate_pct': 100.0,
            'preview_validation_worst_cost_reduction_pct': 1.0,
            'preview_validation_worst_min_cost_reduction_pct': 0.0,
            'preview_validation_avg_cost_reduction_pct': 1.5,
            'preview_next_bar_cost_reduction_pct': -1.0,
            'preview_next_bar_min_cost_reduction_pct': -1.2,
            'preview_round_trips': 80,
        },
        {
            'code': 'market-lower-next-bar-good',
            'preview_total_return_pct': 7.0,
            'preview_alpha_vs_all_in': 8_000.0,
            'preview_cost_reduction_pct': 1.5,
            'preview_validation_cost_reduction_pct': 1.2,
            'preview_validation_pass_rate_pct': 100.0,
            'preview_validation_worst_cost_reduction_pct': 0.8,
            'preview_validation_worst_min_cost_reduction_pct': -0.1,
            'preview_validation_avg_cost_reduction_pct': 1.1,
            'preview_next_bar_cost_reduction_pct': 0.8,
            'preview_next_bar_min_cost_reduction_pct': -0.3,
            'preview_round_trips': 40,
        },
    ]

    rows.sort(key=_preview_sort_key, reverse=True)

    assert rows[0]['code'] == 'market-lower-next-bar-good'


def test_preview_drawdown_filter_uses_absolute_drawdown_limit():
    assert _preview_drawdown_allowed(-7.5, 8.0)
    assert _preview_drawdown_allowed(0.0, 8.0)
    assert not _preview_drawdown_allowed(-8.1, 8.0)
    assert _preview_drawdown_allowed(-99.0, float('inf'))


def test_preview_cost_path_filter_requires_floor_and_positive_days():
    assert _preview_cost_path_allowed(
        min_cost_reduction_pct=-0.8,
        positive_days_pct=70.0,
        min_floor_pct=-1.0,
        min_positive_days_pct=60.0,
    )
    assert not _preview_cost_path_allowed(
        min_cost_reduction_pct=-1.1,
        positive_days_pct=70.0,
        min_floor_pct=-1.0,
        min_positive_days_pct=60.0,
    )
    assert not _preview_cost_path_allowed(
        min_cost_reduction_pct=-0.8,
        positive_days_pct=59.9,
        min_floor_pct=-1.0,
        min_positive_days_pct=60.0,
    )


def test_fold_min_trips_scales_total_validation_requirement_per_fold():
    assert _fold_min_trips(0, 3) == 0
    assert _fold_min_trips(1, 3) == 1
    assert _fold_min_trips(8, 4) == 2
    assert _fold_min_trips(8, 3) == 3


def test_preview_fold_result_passes_focuses_on_cost_path_not_tiny_fold_alpha():
    fold_result = {
        'round_trips': 3,
        'total_return_pct': -5.0,
        'alpha_vs_all_in_hold': -20_000.0,
        'win_rate': 25.0,
        'cost_reduction_pct': -0.6,
        'min_cost_reduction_pct': -0.8,
        'cost_reduction_positive_days_pct': 10.0,
        'max_drawdown_pct': -2.0,
    }

    assert _preview_fold_result_passes(
        fold_result,
        min_trips=2,
        min_cost_reduction_pct=-1.2,
        min_min_cost_reduction_pct=-1.2,
        max_drawdown_pct=12.0,
    )


def test_preview_win_rate_filter_uses_minimum_percent_threshold():
    assert _preview_win_rate_allowed(55.0, 50.0)
    assert _preview_win_rate_allowed(50.0, 50.0)
    assert not _preview_win_rate_allowed(49.9, 50.0)
    assert _preview_win_rate_allowed(0.0, 0.0)
