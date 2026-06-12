from __future__ import annotations

from t0.optimizer import (
    T0OptimizerConstraints,
    iter_parameter_grid,
    optimize_t0_parameters,
)


def _bar(day: str, close: float = 100.0) -> dict:
    return {
        'date': f'{day} 09:31:00',
        'open': close,
        'high': close,
        'low': close,
        'close': close,
        'vol': 100_000,
    }


def _result(cost: float, min_cost: float, trips: int, ret: float = 1.0) -> dict:
    return {
        'cost_reduction_pct': cost,
        'min_cost_reduction_pct': min_cost,
        'cost_reduction_positive_days_pct': 80.0,
        'round_trips': trips,
        'total_return_pct': ret,
        'max_drawdown_pct': -5.0,
    }


def test_iter_parameter_grid_supports_stable_offset_and_limit():
    grid = {
        'take_profit_pct': [0.5, 0.7],
        'stop_loss_pct': [0.8, 1.0],
    }

    first = list(iter_parameter_grid(grid, offset=0, limit=2))
    second = list(iter_parameter_grid(grid, offset=2, limit=2))

    assert first == [
        {'take_profit_pct': 0.5, 'stop_loss_pct': 0.8},
        {'take_profit_pct': 0.5, 'stop_loss_pct': 1.0},
    ]
    assert second == [
        {'take_profit_pct': 0.7, 'stop_loss_pct': 0.8},
        {'take_profit_pct': 0.7, 'stop_loss_pct': 1.0},
    ]


def test_optimize_t0_parameters_sorts_by_cost_path_and_reports_next_offset():
    bars = [_bar('2026-01-01'), _bar('2026-01-02'), _bar('2026-01-03'), _bar('2026-01-04')]
    grid = {
        'take_profit_pct': [0.5, 0.7, 0.9],
        'stop_loss_pct': [0.8],
    }

    def run_strategy(code: str, slice_bars: list[dict], params: dict) -> dict:
        assert code == '300951.SZ'
        tp = params['take_profit_pct']
        days = {bar['date'][:10] for bar in slice_bars}
        if len(days) == 4:
            return _result(cost={0.5: 0.8, 0.7: 1.4, 0.9: 1.2}[tp],
                           min_cost={0.5: -0.2, 0.7: -0.4, 0.9: -1.1}[tp],
                           trips=30)
        if len(days) == 1:
            return _result(cost={0.5: 0.4, 0.7: 1.1, 0.9: 0.9}[tp],
                           min_cost={0.5: -0.2, 0.7: -0.1, 0.9: -0.9}[tp],
                           trips=10)
        return _result(cost={0.5: 0.2, 0.7: 0.8, 0.9: 0.7}[tp],
                       min_cost={0.5: -0.2, 0.7: -0.3, 0.9: -0.8}[tp],
                       trips=3)

    out = optimize_t0_parameters(
        '300951.SZ',
        bars,
        base_params={'signal_mode': 'hybrid'},
        grid=grid,
        run_strategy=run_strategy,
        offset=0,
        limit=2,
        validation_ratio=0.25,
        fold_count=1,
        constraints=T0OptimizerConstraints(
            min_full_cost_reduction_pct=0.5,
            min_validation_cost_reduction_pct=0.5,
            min_full_round_trips=20,
            min_validation_round_trips=8,
            min_fold_cost_reduction_pct=-1.2,
            min_fold_min_cost_reduction_pct=-1.2,
        ),
    )

    assert out['total_grid'] == 3
    assert out['evaluated'] == 2
    assert out['next_offset'] == 2
    assert [row['params']['take_profit_pct'] for row in out['rows']] == [0.7]
    assert out['rows'][0]['full']['cost_reduction_pct'] == 1.4
    assert out['rows'][0]['validation']['cost_reduction_pct'] == 1.1


def test_optimize_t0_parameters_can_evaluate_base_params_before_grid():
    bars = [
        _bar('2026-01-01'), _bar('2026-01-02'),
        _bar('2026-01-03'), _bar('2026-01-04'),
    ]
    seen: list[float] = []

    def run_strategy(code: str, slice_bars: list[dict], params: dict) -> dict:
        if len({bar['date'][:10] for bar in slice_bars}) == 4:
            seen.append(params['take_profit_pct'])
        return _result(cost=1.0, min_cost=-0.2, trips=30)

    out = optimize_t0_parameters(
        '300951.SZ',
        bars,
        base_params={'take_profit_pct': 0.9},
        grid={'take_profit_pct': [0.5, 0.7]},
        run_strategy=run_strategy,
        offset=0,
        limit=1,
        validation_ratio=0.25,
        fold_count=1,
        include_base_candidate=True,
        constraints=T0OptimizerConstraints(
            min_full_cost_reduction_pct=0.5,
            min_validation_cost_reduction_pct=0.5,
            min_full_round_trips=20,
            min_validation_round_trips=8,
            min_fold_cost_reduction_pct=-1.2,
            min_fold_min_cost_reduction_pct=-1.2,
        ),
    )

    assert out['total_grid'] == 3
    assert out['evaluated'] == 1
    assert out['next_offset'] == 1
    assert seen == [0.9]
    assert out['rows'][0]['params']['take_profit_pct'] == 0.9


def test_optimize_t0_parameters_rejects_candidates_with_bad_fold_cost_path():
    bars = [_bar('2026-01-01'), _bar('2026-01-02'), _bar('2026-01-03'), _bar('2026-01-04')]
    grid = {'take_profit_pct': [0.7], 'stop_loss_pct': [0.8]}

    def run_strategy(code: str, slice_bars: list[dict], params: dict) -> dict:
        days = sorted({bar['date'][:10] for bar in slice_bars})
        if len(days) == 4:
            return _result(cost=1.5, min_cost=-0.4, trips=30)
        if len(days) == 1 and days[0] == '2026-01-03':
            return _result(cost=-1.6, min_cost=-1.6, trips=2)
        return _result(cost=1.0, min_cost=-0.2, trips=10)

    out = optimize_t0_parameters(
        '300951.SZ',
        bars,
        base_params={},
        grid=grid,
        run_strategy=run_strategy,
        validation_ratio=0.5,
        fold_count=2,
        constraints=T0OptimizerConstraints(
            min_full_cost_reduction_pct=0.5,
            min_validation_cost_reduction_pct=0.5,
            min_full_round_trips=20,
            min_validation_round_trips=2,
            min_fold_cost_reduction_pct=-1.2,
            min_fold_min_cost_reduction_pct=-1.2,
        ),
    )

    assert out['rows'] == []
    assert out['rejected_fold'] == 1


def test_optimize_t0_parameters_reports_fold_stability_summary():
    bars = [
        _bar('2026-01-01'), _bar('2026-01-02'), _bar('2026-01-03'),
        _bar('2026-01-04'), _bar('2026-01-05'), _bar('2026-01-06'),
    ]
    grid = {'take_profit_pct': [0.7]}

    def run_strategy(code: str, slice_bars: list[dict], params: dict) -> dict:
        days = sorted({bar['date'][:10] for bar in slice_bars})
        if len(days) == 6:
            return _result(cost=1.5, min_cost=-0.3, trips=40)
        if len(days) == 3:
            return _result(cost=1.2, min_cost=-0.2, trips=18)
        if days == ['2026-01-04']:
            return _result(cost=0.5, min_cost=-0.1, trips=6)
        if days == ['2026-01-05']:
            return _result(cost=-0.4, min_cost=-0.6, trips=6)
        return _result(cost=0.8, min_cost=-0.2, trips=6)

    out = optimize_t0_parameters(
        '300951.SZ',
        bars,
        base_params={},
        grid=grid,
        run_strategy=run_strategy,
        validation_ratio=0.5,
        fold_count=3,
        constraints=T0OptimizerConstraints(
            min_full_cost_reduction_pct=0.5,
            min_validation_cost_reduction_pct=0.5,
            min_full_round_trips=20,
            min_validation_round_trips=8,
            min_fold_cost_reduction_pct=-1.2,
            min_fold_min_cost_reduction_pct=-1.2,
        ),
    )

    row = out['rows'][0]
    assert row['fold_count'] == 3
    assert row['fold_pass_count'] == 2
    assert row['fold_pass_rate_pct'] == 66.6667
    assert row['worst_fold_cost_reduction_pct'] == -0.4
    assert row['worst_fold_min_cost_reduction_pct'] == -0.6
    assert row['avg_fold_cost_reduction_pct'] == 0.3
