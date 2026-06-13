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


def _default_scan_candidates(**kwargs):
    from t0.local_lc1 import scan_lc1_candidates

    return scan_lc1_candidates(**kwargs)


def run_candidate_sweep(
    *,
    start: str,
    end: str,
    strategy_profile: str = 'adaptive_vwap_cost',
    candidate_top_n: int = 20,
    sweep_top_n: int = 5,
    optimizer_batch_size: int = 96,
    optimizer_max_evaluations: int = 576,
    out_root: str | Path = 'data/qlib_research',
    scan_candidates: Callable[..., list[dict[str, Any]]] = _default_scan_candidates,
    sweep: Callable[..., dict[str, Any]] = run_sweep,
) -> dict[str, Any]:
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
    sweep_result = (
        sweep(
            codes=swept_codes,
            start=start,
            end=end,
            strategy_profile=strategy_profile,
            optimizer_batch_size=optimizer_batch_size,
            optimizer_max_evaluations=optimizer_max_evaluations,
            out_root=out_root,
        )
        if swept_codes else {'count': 0, 'rows': []}
    )
    return {
        'candidate_count': len(candidates),
        'candidates': candidates,
        'swept_codes': swept_codes,
        'sweep': sweep_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--strategy-profile', default='adaptive_vwap_cost')
    parser.add_argument('--candidate-top-n', type=int, default=20)
    parser.add_argument('--sweep-top-n', type=int, default=5)
    parser.add_argument('--optimizer-batch-size', type=int, default=96)
    parser.add_argument('--optimizer-max-evaluations', type=int, default=576)
    parser.add_argument('--out-root', default='data/qlib_research')
    args = parser.parse_args()
    result = run_candidate_sweep(
        start=args.start,
        end=args.end,
        strategy_profile=args.strategy_profile,
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
