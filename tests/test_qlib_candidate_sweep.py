from __future__ import annotations

import subprocess
import sys

from scripts.research.t0_qlib_candidate_sweep import run_candidate_sweep


def test_candidate_sweep_scans_candidates_then_runs_profile_sweep():
    seen = {}

    def scan_candidates(**kwargs):
        seen['scan_kwargs'] = kwargs
        return [
            {'code': '301233.SZ', 'stable_t_score': 90.0},
            {'code': '001230.SZ', 'stable_t_score': 89.0},
            {'code': '600724.SH', 'stable_t_score': 88.0},
        ]

    def sweep(**kwargs):
        seen['sweep_kwargs'] = kwargs
        return {
            'count': 2,
            'rows': [
                {'code': '600724.SH', 'best_validation_cost_reduction_pct': 0.8},
                {'code': '001230.SZ', 'best_validation_cost_reduction_pct': 0.0},
            ],
        }

    result = run_candidate_sweep(
        start='2026-01-01',
        end='2026-04-01',
        strategy_profile='adaptive_vwap_cost',
        candidate_top_n=3,
        sweep_top_n=2,
        optimizer_batch_size=96,
        optimizer_max_evaluations=576,
        scan_candidates=scan_candidates,
        sweep=sweep,
    )

    assert seen['scan_kwargs']['top_n'] == 3
    assert seen['scan_kwargs']['score_profile'] == 'stable_t'
    assert seen['sweep_kwargs']['codes'] == ['301233.SZ', '001230.SZ']
    assert seen['sweep_kwargs']['strategy_profile'] == 'adaptive_vwap_cost'
    assert result['candidate_count'] == 3
    assert result['swept_codes'] == ['301233.SZ', '001230.SZ']
    assert result['sweep']['rows'][0]['code'] == '600724.SH'


def test_candidate_sweep_can_compare_multiple_strategy_profiles():
    seen_profiles = []

    def scan_candidates(**kwargs):
        return [
            {'code': '600724.SH', 'stable_t_score': 91.0},
            {'code': '300951.SZ', 'stable_t_score': 90.0},
        ]

    def sweep(**kwargs):
        profile = kwargs['strategy_profile']
        seen_profiles.append(profile)
        if profile == 'risk_balanced_adaptive_vwap_cost':
            return {
                'count': 1,
                'rows': [{
                    'code': '600724.SH',
                    'strategy_profile': profile,
                    'best_validation_cost_reduction_pct': 1.2,
                    'best_fold_pass_rate_pct': 100.0,
                    'best_worst_fold_cost_reduction_pct': 0.3,
                }],
            }
        return {
            'count': 1,
            'rows': [{
                'code': '300951.SZ',
                'strategy_profile': profile,
                'best_validation_cost_reduction_pct': 0.7,
                'best_fold_pass_rate_pct': 100.0,
                'best_worst_fold_cost_reduction_pct': 0.2,
            }],
        }

    result = run_candidate_sweep(
        start='2026-01-01',
        end='2026-04-01',
        strategy_profiles=[
            'trend_pullback_t0_cost',
            'risk_balanced_adaptive_vwap_cost',
        ],
        candidate_top_n=2,
        sweep_top_n=2,
        optimizer_batch_size=96,
        optimizer_max_evaluations=96,
        scan_candidates=scan_candidates,
        sweep=sweep,
    )

    assert seen_profiles == [
        'trend_pullback_t0_cost',
        'risk_balanced_adaptive_vwap_cost',
    ]
    assert sorted(result['profile_sweeps']) == [
        'risk_balanced_adaptive_vwap_cost',
        'trend_pullback_t0_cost',
    ]
    assert [row['strategy_profile'] for row in result['leaderboard']] == [
        'risk_balanced_adaptive_vwap_cost',
        'trend_pullback_t0_cost',
    ]
    assert result['leaderboard'][0]['code'] == '600724.SH'


def test_candidate_sweep_can_rerun_explicit_codes_without_scanning():
    seen = {}

    def scan_candidates(**kwargs):
        raise AssertionError('explicit codes should bypass candidate scan')

    def sweep(**kwargs):
        seen['sweep_kwargs'] = kwargs
        return {
            'count': 1,
            'rows': [{
                'code': '600724.SH',
                'strategy_profile': kwargs['strategy_profile'],
                'best_validation_cost_reduction_pct': 1.0,
                'best_fold_pass_rate_pct': 100.0,
                'best_worst_fold_cost_reduction_pct': 0.2,
            }],
        }

    result = run_candidate_sweep(
        start='2026-01-01',
        end='2026-04-01',
        codes=['600724.SH', '300951.SZ'],
        strategy_profile='risk_balanced_adaptive_vwap_cost',
        optimizer_batch_size=96,
        optimizer_max_evaluations=96,
        scan_candidates=scan_candidates,
        sweep=sweep,
    )

    assert result['candidate_count'] == 2
    assert result['candidates'] == [
        {'code': '600724.SH'},
        {'code': '300951.SZ'},
    ]
    assert result['swept_codes'] == ['600724.SH', '300951.SZ']
    assert seen['sweep_kwargs']['codes'] == ['600724.SH', '300951.SZ']
    assert result['leaderboard'][0]['code'] == '600724.SH'


def test_candidate_sweep_script_help_runs_when_executed_by_path():
    proc = subprocess.run(
        [
            sys.executable,
            'scripts/research/t0_qlib_candidate_sweep.py',
            '--help',
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    assert '--candidate-top-n' in proc.stdout
