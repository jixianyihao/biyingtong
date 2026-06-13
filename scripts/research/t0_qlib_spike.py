from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from qlib_research.exporter import write_qlib_csv
from qlib_research.features import summarize_intraday_features
from qlib_research.recorder import ResearchRun, record_research_run


def _default_load_bars(
    code: str,
    start: str | None = None,
    end: str | None = None,
):
    from t0.local_lc1 import load_lc1_bars_for_code
    return load_lc1_bars_for_code(code, start=start, end=end)


def _default_optimize(
    code: str,
    bars: list[dict[str, Any]],
    limit: int,
):
    from api.t0 import DEFAULT_T0_OPTIMIZER_GRID
    from t0.optimizer import T0OptimizerConstraints, optimize_t0_parameters
    from t0.portfolio import run_t0_portfolio_backtest

    base_params = {
        'initial_capital': 1_000_000.0,
        'base_position_pct': 0.75,
        't_shares_pct': 0.20,
        'min_amplitude_pct': 1.0,
        'high_band': 0.82,
        'low_band': 0.25,
        'take_profit_pct': 0.75,
        'stop_loss_pct': 1.0,
        'allow_sell_first': True,
        'allow_buy_first': True,
        'stop_after_daily_loss': True,
    }

    def run_strategy(
        run_code: str,
        run_bars: list[dict[str, Any]],
        params: dict[str, Any],
    ):
        return run_t0_portfolio_backtest(run_code, run_bars, **params)

    return optimize_t0_parameters(
        code,
        bars,
        base_params=base_params,
        grid=DEFAULT_T0_OPTIMIZER_GRID,
        run_strategy=run_strategy,
        limit=limit,
        include_base_candidate=True,
        constraints=T0OptimizerConstraints(
            min_full_cost_reduction_pct=0.0,
            min_validation_cost_reduction_pct=0.0,
            min_full_round_trips=1,
            min_validation_round_trips=1,
            min_fold_cost_reduction_pct=-2.0,
            min_fold_min_cost_reduction_pct=-2.0,
        ),
    )


def run_spike(
    *,
    codes: list[str],
    start: str,
    end: str,
    optimizer_limit: int,
    out_root: str | Path = 'data/qlib_research',
    load_bars: Callable[..., list[dict[str, Any]]] = _default_load_bars,
    optimize: Callable[
        [str, list[dict[str, Any]], int], dict[str, Any]
    ] = _default_optimize,
) -> dict[str, Any]:
    root = Path(out_root)
    rows: list[dict[str, Any]] = []
    for code in codes:
        bars = load_bars(code, start=start, end=end)
        csv_path = write_qlib_csv(code, bars, root / 'source' / '1min')
        features = summarize_intraday_features(code, bars)
        opt = optimize(code, bars, optimizer_limit)
        best = (opt.get('rows') or [{}])[0]
        validation = best.get('validation') or {}
        metrics = {
            'best_score': float(best.get('score') or 0.0),
            'best_validation_cost_reduction_pct': float(
                validation.get('cost_reduction_pct') or 0.0,
            ),
            'best_fold_pass_rate_pct': float(
                best.get('fold_pass_rate_pct') or 0.0,
            ),
            'best_worst_fold_cost_reduction_pct': float(
                best.get('worst_fold_cost_reduction_pct') or 0.0,
            ),
        }
        record = record_research_run(
            ResearchRun(
                experiment='t0-qlib-spike',
                recorder=code,
                params={
                    'code': code,
                    'start': start,
                    'end': end,
                    'optimizer_limit': optimizer_limit,
                },
                metrics=metrics,
                artifacts={
                    'feature_summary': features,
                    'best_params': best.get('params') or {},
                },
            ),
            root=root,
        )
        rows.append({
            'code': code,
            'csv_path': str(csv_path),
            'features': features,
            'best_params': best.get('params') or {},
            'record_backend': record['backend'],
            **metrics,
        })
    rows.sort(
        key=lambda row: (
            row['best_validation_cost_reduction_pct'],
            row['best_fold_pass_rate_pct'],
            row['best_worst_fold_cost_reduction_pct'],
        ),
        reverse=True,
    )
    return {'count': len(rows), 'rows': rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--codes', required=True)
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--optimizer-limit', type=int, default=96)
    parser.add_argument('--out-root', default='data/qlib_research')
    args = parser.parse_args()
    result = run_spike(
        codes=[code.strip() for code in args.codes.split(',') if code.strip()],
        start=args.start,
        end=args.end,
        optimizer_limit=args.optimizer_limit,
        out_root=args.out_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
