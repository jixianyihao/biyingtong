from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qlib_research.exporter import write_qlib_csv
from qlib_research.features import summarize_intraday_features
from qlib_research.recorder import ResearchRun, record_research_run


def _filter_bars_by_date(
    bars: list[dict[str, Any]],
    *,
    start: str | None,
    end: str | None,
) -> list[dict[str, Any]]:
    if not start and not end:
        return bars
    rows: list[dict[str, Any]] = []
    for bar in bars:
        day = str(bar.get('date') or bar.get('ts') or '')[:10]
        if start and day < start:
            continue
        if end and day > end:
            continue
        rows.append(bar)
    return rows


def _default_load_bars(
    code: str,
    start: str | None = None,
    end: str | None = None,
):
    from t0.local_lc1 import load_lc1_bars_for_code
    return _filter_bars_by_date(
        load_lc1_bars_for_code(code),
        start=start,
        end=end,
    )


def _default_optimize(
    code: str,
    bars: list[dict[str, Any]],
    offset: int,
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
        offset=offset,
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
    optimizer_offset: int = 0,
    optimizer_limit: int,
    out_root: str | Path = 'data/qlib_research',
    load_bars: Callable[..., list[dict[str, Any]]] = _default_load_bars,
    optimize: Callable[
        [str, list[dict[str, Any]], int, int], dict[str, Any]
    ] = _default_optimize,
) -> dict[str, Any]:
    root = Path(out_root)
    rows: list[dict[str, Any]] = []
    for code in codes:
        bars = load_bars(code, start=start, end=end)
        csv_path = write_qlib_csv(code, bars, root / 'source' / '1min')
        features = summarize_intraday_features(code, bars)
        opt = optimize(code, bars, optimizer_offset, optimizer_limit)
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
                    'optimizer_offset': optimizer_offset,
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


def _row_sort_key(row: dict[str, Any]) -> tuple[float, float, float]:
    return (
        float(row.get('best_validation_cost_reduction_pct') or 0.0),
        float(row.get('best_fold_pass_rate_pct') or 0.0),
        float(row.get('best_worst_fold_cost_reduction_pct') or 0.0),
    )


def run_sweep(
    *,
    codes: list[str],
    start: str,
    end: str,
    optimizer_batch_size: int,
    optimizer_max_evaluations: int,
    out_root: str | Path = 'data/qlib_research',
    load_bars: Callable[..., list[dict[str, Any]]] = _default_load_bars,
    optimize: Callable[
        [str, list[dict[str, Any]], int, int], dict[str, Any]
    ] = _default_optimize,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    batch_size = max(1, int(optimizer_batch_size or 1))
    max_evaluations = max(batch_size, int(optimizer_max_evaluations or batch_size))

    for code in codes:
        best_row: dict[str, Any] | None = None
        offset = 0
        evaluated_total = 0
        batches = 0

        while evaluated_total < max_evaluations:
            limit = min(batch_size, max_evaluations - evaluated_total)
            result = run_spike(
                codes=[code],
                start=start,
                end=end,
                optimizer_offset=offset,
                optimizer_limit=limit,
                out_root=out_root,
                load_bars=load_bars,
                optimize=optimize,
            )
            batch_rows = result.get('rows') or []
            if batch_rows:
                candidate = dict(batch_rows[0])
                candidate['best_optimizer_offset'] = offset
                if best_row is None or _row_sort_key(candidate) > _row_sort_key(best_row):
                    best_row = candidate
            batches += 1
            evaluated_total += limit

            # The optimize result is not exposed by run_spike, so we advance by
            # the requested limit. This keeps the sweep deterministic and lets
            # callers choose how much of the grid to cover.
            offset += limit

        if best_row is not None:
            best_row['sweep_batches'] = batches
            best_row['sweep_evaluated'] = evaluated_total
            rows.append(best_row)

    rows.sort(key=_row_sort_key, reverse=True)
    return {'count': len(rows), 'rows': rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--codes', required=True)
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--sweep', action='store_true')
    parser.add_argument('--optimizer-batch-size', type=int, default=96)
    parser.add_argument('--optimizer-max-evaluations', type=int, default=384)
    parser.add_argument('--optimizer-offset', type=int, default=0)
    parser.add_argument('--optimizer-limit', type=int, default=96)
    parser.add_argument('--out-root', default='data/qlib_research')
    args = parser.parse_args()
    codes = [code.strip() for code in args.codes.split(',') if code.strip()]
    if args.sweep:
        result = run_sweep(
            codes=codes,
            start=args.start,
            end=args.end,
            optimizer_batch_size=args.optimizer_batch_size,
            optimizer_max_evaluations=args.optimizer_max_evaluations,
            out_root=args.out_root,
        )
    else:
        result = run_spike(
            codes=codes,
            start=args.start,
            end=args.end,
            optimizer_offset=args.optimizer_offset,
            optimizer_limit=args.optimizer_limit,
            out_root=args.out_root,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
