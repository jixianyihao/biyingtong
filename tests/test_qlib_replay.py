from pathlib import Path
from argparse import Namespace

from scripts.research.t0_qlib_replay import (
    _load_params_from_args,
    run_replay,
    summarize_replay_result,
)


def _bar(ts: str, price: float, high: float | None = None, low: float | None = None):
    return {
        'date': ts,
        'open': price,
        'high': price if high is None else high,
        'low': price if low is None else low,
        'close': price,
        'vol': 100_000,
    }


def test_summarize_replay_result_keeps_cost_and_risk_metrics():
    summary = summarize_replay_result({
        'final_equity': 1_002_000.0,
        'total_return_pct': 0.2,
        'cost_reduction_pct': 0.8,
        'min_cost_reduction_pct': -0.3,
        'cost_reduction_positive_days_pct': 75.0,
        'alpha_vs_all_in_hold': 1_200.0,
        'max_drawdown_pct': -2.5,
        'round_trips': 12,
        'win_rate': 58.3,
    })

    assert summary == {
        'final_equity': 1_002_000.0,
        'total_return_pct': 0.2,
        'cost_reduction_pct': 0.8,
        'min_cost_reduction_pct': -0.3,
        'cost_reduction_positive_days_pct': 75.0,
        'alpha_vs_all_in_hold': 1_200.0,
        'max_drawdown_pct': -2.5,
        'round_trips': 12,
        'win_rate': 58.3,
    }


def test_run_replay_merges_profile_params_and_records_research(tmp_path: Path):
    bars = [
        _bar('2026-01-05 09:31:00', 100.0),
        _bar('2026-01-05 09:40:00', 98.0, high=100.0, low=98.0),
        _bar('2026-01-05 10:10:00', 101.0, high=101.0, low=98.0),
        _bar('2026-01-05 15:00:00', 101.0),
    ]

    def load_bars(code, start=None, end=None):
        assert code == '600724.SH'
        assert start == '2026-01-01'
        assert end == '2026-04-01'
        return bars

    result = run_replay(
        code='600724.SH',
        start='2026-01-01',
        end='2026-04-01',
        strategy_profile='risk_balanced_adaptive_vwap_cost',
        params={
            'base_position_pct': 0.45,
            't_shares_pct': 0.12,
            'take_profit_pct': 0.5,
            'stop_loss_pct': 0.7,
            'signal_mode': 'adaptive_vwap',
            'execution_style': 'market',
        },
        out_root=tmp_path,
        load_bars=load_bars,
    )

    assert result['code'] == '600724.SH'
    assert result['strategy_profile'] == 'risk_balanced_adaptive_vwap_cost'
    assert result['params']['base_position_pct'] == 0.45
    assert result['params']['t_shares_pct'] == 0.12
    assert result['metrics']['round_trips'] >= 0
    assert result['record_backend'] == 'jsonl'
    assert Path(result['record_path']).exists()


def test_params_file_accepts_windows_utf8_bom(tmp_path: Path):
    path = tmp_path / 'params.json'
    path.write_text('{"base_position_pct": 0.45}', encoding='utf-8-sig')

    params = _load_params_from_args(Namespace(
        params_file=str(path),
        params_json=None,
    ))

    assert params == {'base_position_pct': 0.45}
