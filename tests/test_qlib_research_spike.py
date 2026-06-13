from pathlib import Path

from scripts.research.t0_qlib_spike import run_spike


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

    def optimize(code, loaded_bars, limit):
        assert code == '300951.SZ'
        assert loaded_bars == bars
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
