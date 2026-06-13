from pathlib import Path
import subprocess
import sys

from scripts.research.t0_qlib_spike import (
    _filter_bars_by_date,
    run_spike,
    run_sweep,
)


def test_run_spike_exports_features_optimizes_and_records(tmp_path: Path):
    bars = [
        {
            'ts': '2026-01-05 09:31:00',
            'date': '2026-01-05',
            'open': 10,
            'high': 10.2,
            'low': 9.9,
            'close': 10.1,
            'vol': 1000,
        },
        {
            'ts': '2026-01-05 14:56:00',
            'date': '2026-01-05',
            'open': 10.1,
            'high': 10.5,
            'low': 9.8,
            'close': 10.4,
            'vol': 1200,
        },
        {
            'ts': '2026-01-06 09:31:00',
            'date': '2026-01-06',
            'open': 10.5,
            'high': 10.7,
            'low': 10.2,
            'close': 10.3,
            'vol': 900,
        },
        {
            'ts': '2026-01-06 14:56:00',
            'date': '2026-01-06',
            'open': 10.3,
            'high': 10.9,
            'low': 10.1,
            'close': 10.8,
            'vol': 1300,
        },
    ]

    def load_bars(code, start=None, end=None):
        assert code == '300951.SZ'
        assert start == '2026-01-01'
        assert end == '2026-04-01'
        return bars

    def optimize(code, loaded_bars, offset, limit):
        assert code == '300951.SZ'
        assert loaded_bars == bars
        assert offset == 0
        assert limit == 12
        return {
            'rows': [{
                'score': 3.0,
                'params': {'signal_mode': 'hybrid'},
                'validation': {'cost_reduction_pct': 1.25},
                'fold_pass_rate_pct': 66.6667,
                'worst_fold_cost_reduction_pct': -0.3,
            }],
        }

    result = run_spike(
        codes=['300951.SZ'],
        start='2026-01-01',
        end='2026-04-01',
        optimizer_offset=0,
        optimizer_limit=12,
        out_root=tmp_path,
        load_bars=load_bars,
        optimize=optimize,
    )

    assert result['count'] == 1
    row = result['rows'][0]
    assert row['code'] == '300951.SZ'
    assert row['best_validation_cost_reduction_pct'] == 1.25
    assert Path(row['csv_path']).exists()
    assert row['record_backend'] == 'jsonl'


def test_run_spike_passes_optimizer_offset(tmp_path: Path):
    bars = [
        {
            'ts': '2026-01-05 09:31:00',
            'date': '2026-01-05',
            'open': 10.0,
            'high': 10.2,
            'low': 9.9,
            'close': 10.1,
            'vol': 1000,
        },
    ]
    seen = {}

    def load_bars(code, start=None, end=None):
        return bars

    def optimize(code, loaded_bars, offset, limit):
        seen['offset'] = offset
        seen['limit'] = limit
        return {
            'rows': [{
                'score': 1.0,
                'params': {'signal_mode': 'band'},
                'validation': {'cost_reduction_pct': 0.1},
            }],
        }

    run_spike(
        codes=['300951.SZ'],
        start='2026-01-01',
        end='2026-04-01',
        optimizer_offset=96,
        optimizer_limit=12,
        out_root=tmp_path,
        load_bars=load_bars,
        optimize=optimize,
    )

    assert seen == {'offset': 96, 'limit': 12}


def test_run_spike_reports_optimizer_progress_metadata(tmp_path: Path):
    bars = [{
        'ts': '2026-01-05 09:31:00',
        'date': '2026-01-05',
        'open': 10.0,
        'high': 10.4,
        'low': 9.8,
        'close': 10.1,
        'vol': 1000,
    }]

    def load_bars(code, start=None, end=None):
        return bars

    def optimize(code, loaded_bars, offset, limit):
        return {
            'total_grid': 30,
            'evaluated': 12,
            'next_offset': 12,
            'rejected_full': 2,
            'rejected_validation': 3,
            'rejected_fold': 4,
            'rejected_risk': 5,
            'rows': [{
                'score': 1.0,
                'params': {'take_profit_pct': 0.55},
                'validation': {'cost_reduction_pct': 0.3},
            }],
        }

    result = run_spike(
        codes=['300951.SZ'],
        start='2026-01-01',
        end='2026-04-01',
        optimizer_offset=0,
        optimizer_limit=12,
        out_root=tmp_path,
        load_bars=load_bars,
        optimize=optimize,
    )

    row = result['rows'][0]
    assert row['optimizer_total_grid'] == 30
    assert row['optimizer_evaluated'] == 12
    assert row['optimizer_next_offset'] == 12
    assert row['optimizer_rejected_risk'] == 5


def test_run_spike_reports_selected_strategy_profile(tmp_path: Path):
    bars = [{
        'ts': '2026-01-05 09:31:00',
        'date': '2026-01-05',
        'open': 10.0,
        'high': 10.4,
        'low': 9.8,
        'close': 10.1,
        'vol': 1000,
    }]

    def load_bars(code, start=None, end=None):
        return bars

    def optimize(code, loaded_bars, offset, limit):
        return {
            'next_offset': None,
            'evaluated': limit,
            'total_grid': 1,
            'rows': [{
                'score': 1.0,
                'params': {'take_profit_pct': 0.55},
                'validation': {'cost_reduction_pct': 0.3},
                'fold_pass_rate_pct': 100.0,
                'worst_fold_cost_reduction_pct': 0.1,
            }],
        }

    result = run_spike(
        codes=['300951.SZ'],
        start='2026-01-01',
        end='2026-04-01',
        strategy_profile='adaptive_vwap_cost',
        optimizer_offset=0,
        optimizer_limit=12,
        out_root=tmp_path,
        load_bars=load_bars,
        optimize=optimize,
    )

    assert result['rows'][0]['strategy_profile'] == 'adaptive_vwap_cost'


def test_run_sweep_aggregates_best_row_across_optimizer_offsets(tmp_path: Path):
    bars = [
        {
            'ts': '2026-01-05 09:31:00',
            'date': '2026-01-05',
            'open': 10.0,
            'high': 10.4,
            'low': 9.8,
            'close': 10.1,
            'vol': 1000,
        },
    ]
    offsets = []

    def load_bars(code, start=None, end=None):
        return bars

    def optimize(code, loaded_bars, offset, limit):
        offsets.append(offset)
        validation_cost = {0: 0.2, 10: 1.4, 20: 0.8}[offset]
        return {
            'next_offset': None if offset == 20 else offset + limit,
            'evaluated': limit,
            'total_grid': 30,
            'rows': [{
                'score': validation_cost,
                'params': {'offset': offset},
                'validation': {'cost_reduction_pct': validation_cost},
                'fold_pass_rate_pct': 66.6667,
                'worst_fold_cost_reduction_pct': -0.1,
            }],
        }

    result = run_sweep(
        codes=['300951.SZ'],
        start='2026-01-01',
        end='2026-04-01',
        optimizer_batch_size=10,
        optimizer_max_evaluations=30,
        out_root=tmp_path,
        load_bars=load_bars,
        optimize=optimize,
    )

    assert offsets == [0, 10, 20]
    assert result['count'] == 1
    assert result['rows'][0]['code'] == '300951.SZ'
    assert result['rows'][0]['best_validation_cost_reduction_pct'] == 1.4
    assert result['rows'][0]['best_optimizer_offset'] == 10
    assert result['rows'][0]['sweep_batches'] == 3
    assert result['rows'][0]['sweep_evaluated'] == 30
    assert result['rows'][0]['sweep_next_offset'] is None


def test_run_sweep_can_resume_from_optimizer_start_offset(tmp_path: Path):
    bars = [
        {
            'ts': '2026-01-05 09:31:00',
            'date': '2026-01-05',
            'open': 10.0,
            'high': 10.4,
            'low': 9.8,
            'close': 10.1,
            'vol': 1000,
        },
    ]
    offsets = []

    def load_bars(code, start=None, end=None):
        return bars

    def optimize(code, loaded_bars, offset, limit):
        offsets.append(offset)
        return {
            'next_offset': offset + limit,
            'evaluated': limit,
            'total_grid': 100,
            'rows': [{
                'score': float(offset),
                'params': {'offset': offset},
                'validation': {'cost_reduction_pct': float(offset)},
                'fold_pass_rate_pct': 66.6667,
                'worst_fold_cost_reduction_pct': -0.1,
            }],
        }

    result = run_sweep(
        codes=['300951.SZ'],
        start='2026-01-01',
        end='2026-04-01',
        optimizer_start_offset=50,
        optimizer_batch_size=10,
        optimizer_max_evaluations=20,
        out_root=tmp_path,
        load_bars=load_bars,
        optimize=optimize,
    )

    assert offsets == [50, 60]
    assert result['rows'][0]['best_optimizer_offset'] == 60
    assert result['rows'][0]['sweep_evaluated'] == 20
    assert result['rows'][0]['sweep_next_offset'] == 70


def test_run_sweep_stops_when_optimizer_reports_grid_exhausted(tmp_path: Path):
    bars = [{
        'ts': '2026-01-05 09:31:00',
        'date': '2026-01-05',
        'open': 10.0,
        'high': 10.4,
        'low': 9.8,
        'close': 10.1,
        'vol': 1000,
    }]
    offsets = []

    def load_bars(code, start=None, end=None):
        return bars

    def optimize(code, loaded_bars, offset, limit):
        offsets.append(offset)
        return {
            'next_offset': None if offset == 10 else offset + limit,
            'evaluated': limit,
            'total_grid': 20,
            'rows': [{
                'score': float(offset),
                'params': {'offset': offset},
                'validation': {'cost_reduction_pct': float(offset)},
                'fold_pass_rate_pct': 100.0,
                'worst_fold_cost_reduction_pct': 0.1,
            }],
        }

    result = run_sweep(
        codes=['300951.SZ'],
        start='2026-01-01',
        end='2026-04-01',
        optimizer_batch_size=10,
        optimizer_max_evaluations=50,
        out_root=tmp_path,
        load_bars=load_bars,
        optimize=optimize,
    )

    assert offsets == [0, 10]
    assert result['rows'][0]['sweep_batches'] == 2
    assert result['rows'][0]['sweep_evaluated'] == 20
    assert result['rows'][0]['sweep_next_offset'] is None


def test_spike_script_help_runs_when_executed_by_path():
    proc = subprocess.run(
        [
            sys.executable,
            'scripts/research/t0_qlib_spike.py',
            '--help',
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    assert '--codes' in proc.stdout


def test_filter_bars_by_date_uses_inclusive_window():
    bars = [
        {'date': '2025-12-31 14:56:00', 'close': 9.9},
        {'date': '2026-01-01 09:31:00', 'close': 10.0},
        {'date': '2026-04-01 14:56:00', 'close': 10.5},
        {'date': '2026-04-02 09:31:00', 'close': 10.6},
    ]

    filtered = _filter_bars_by_date(
        bars,
        start='2026-01-01',
        end='2026-04-01',
    )

    assert [row['date'] for row in filtered] == [
        '2026-01-01 09:31:00',
        '2026-04-01 14:56:00',
    ]
