from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.t0_qlib_spike import run_sweep


def _row_sort_key(row: dict[str, Any]) -> tuple[float, float, float]:
    return (
        float(row.get('best_validation_cost_reduction_pct') or 0.0),
        float(row.get('best_fold_pass_rate_pct') or 0.0),
        float(row.get('best_worst_fold_cost_reduction_pct') or 0.0),
    )


def _default_scan_candidates(**kwargs):
    from t0.local_lc1 import scan_lc1_candidates

    return scan_lc1_candidates(**kwargs)


def run_candidate_sweep(
    *,
    start: str,
    end: str,
    codes: list[str] | None = None,
    strategy_profile: str = 'adaptive_vwap_cost',
    strategy_profiles: list[str] | None = None,
    candidate_top_n: int = 20,
    sweep_top_n: int = 5,
    optimizer_batch_size: int = 96,
    optimizer_max_evaluations: int = 576,
    out_root: str | Path = 'data/qlib_research',
    scan_candidates: Callable[..., list[dict[str, Any]]] = _default_scan_candidates,
    sweep: Callable[..., dict[str, Any]] = run_sweep,
) -> dict[str, Any]:
    explicit_codes = [code.strip().upper() for code in (codes or []) if code.strip()]
    if explicit_codes:
        candidates = [{'code': code} for code in explicit_codes]
        swept_codes = explicit_codes
    else:
        candidates = scan_candidates(
            top_n=max(1, int(candidate_top_n)),
            max_files=20_000,
            score_profile='stable_t',
            min_days=30,
            min_avg_amp_pct=2.5,
            max_avg_amp_pct=8.0,
            min_price=2.0,
            max_price=80.0,
            min_return_pct=-35.0,
            max_return_pct=80.0,
        )
        swept_codes = [
            str(row['code'])
            for row in candidates[:max(1, int(sweep_top_n))]
            if row.get('code')
        ]
    profiles = strategy_profiles or [strategy_profile]
    profile_sweeps: dict[str, dict[str, Any]] = {}
    leaderboard: list[dict[str, Any]] = []
    for profile in profiles:
        profile_result = (
            sweep(
                codes=swept_codes,
                start=start,
                end=end,
                strategy_profile=profile,
                optimizer_batch_size=optimizer_batch_size,
                optimizer_max_evaluations=optimizer_max_evaluations,
                out_root=out_root,
            )
            if swept_codes else {'count': 0, 'rows': []}
        )
        profile_sweeps[profile] = profile_result
        leaderboard.extend([
            {**row, 'strategy_profile': row.get('strategy_profile') or profile}
            for row in (profile_result.get('rows') or [])
        ])
    leaderboard.sort(key=_row_sort_key, reverse=True)

    sweep_result = (
        profile_sweeps[profiles[0]]
        if len(profiles) == 1
        else {'count': len(leaderboard), 'rows': leaderboard}
    )
    return {
        'candidate_count': len(candidates),
        'candidates': candidates,
        'swept_codes': swept_codes,
        'strategy_profiles': profiles,
        'profile_sweeps': profile_sweeps,
        'leaderboard': leaderboard,
        'sweep': sweep_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument(
        '--codes',
        default='',
        help='Comma-separated stock codes; skips candidate scan when set.',
    )
    parser.add_argument('--strategy-profile', default='adaptive_vwap_cost')
    parser.add_argument(
        '--strategy-profiles',
        default='',
        help='Comma-separated profile names; overrides --strategy-profile.',
    )
    parser.add_argument('--candidate-top-n', type=int, default=20)
    parser.add_argument('--sweep-top-n', type=int, default=5)
    parser.add_argument('--optimizer-batch-size', type=int, default=96)
    parser.add_argument('--optimizer-max-evaluations', type=int, default=576)
    parser.add_argument('--out-root', default='data/qlib_research')
    args = parser.parse_args()
    result = run_candidate_sweep(
        start=args.start,
        end=args.end,
        codes=[code.strip() for code in args.codes.split(',') if code.strip()],
        strategy_profile=args.strategy_profile,
        strategy_profiles=(
            [p.strip() for p in args.strategy_profiles.split(',') if p.strip()]
            or None
        ),
        candidate_top_n=args.candidate_top_n,
        sweep_top_n=args.sweep_top_n,
        optimizer_batch_size=args.optimizer_batch_size,
        optimizer_max_evaluations=args.optimizer_max_evaluations,
        out_root=args.out_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
