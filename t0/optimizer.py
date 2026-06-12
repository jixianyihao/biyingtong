from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from itertools import product
from typing import Any, Callable, Iterable


RunStrategy = Callable[[str, list[dict], dict], dict]


@dataclass(frozen=True)
class T0OptimizerConstraints:
    min_full_cost_reduction_pct: float = 0.5
    min_validation_cost_reduction_pct: float = 0.5
    min_full_round_trips: int = 20
    min_validation_round_trips: int = 8
    min_fold_cost_reduction_pct: float = -1.2
    min_fold_min_cost_reduction_pct: float = -1.2


def _bar_day(bar: dict) -> date | None:
    raw = str(bar.get('date') or '').strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def _ordered_days(bars: list[dict]) -> list[date]:
    days: list[date] = []
    seen: set[date] = set()
    for bar in bars:
        day = _bar_day(bar)
        if day is None or day in seen:
            continue
        seen.add(day)
        days.append(day)
    return days


def _split_train_validation(
    bars: list[dict],
    validation_ratio: float,
) -> tuple[list[dict], list[dict]]:
    days = _ordered_days(bars)
    if len(days) < 2:
        return bars, []
    ratio = max(0.0, min(0.8, float(validation_ratio or 0.0)))
    if ratio <= 0:
        return bars, []
    validation_days = max(1, round(len(days) * ratio))
    validation_days = min(validation_days, len(days) - 1)
    validation_set = set(days[-validation_days:])
    train = [bar for bar in bars if _bar_day(bar) not in validation_set]
    validation = [bar for bar in bars if _bar_day(bar) in validation_set]
    return (train, validation) if train and validation else (bars, [])


def _split_folds(bars: list[dict], fold_count: int) -> list[list[dict]]:
    days = _ordered_days(bars)
    if not days:
        return []
    count = max(1, min(int(fold_count or 1), len(days)))
    folds: list[list[dict]] = []
    for idx in range(count):
        start = idx * len(days) // count
        end = (idx + 1) * len(days) // count
        day_set = set(days[start:end])
        fold = [bar for bar in bars if _bar_day(bar) in day_set]
        if fold:
            folds.append(fold)
    return folds


def iter_parameter_grid(
    grid: dict[str, Iterable[Any]],
    *,
    offset: int = 0,
    limit: int | None = None,
) -> Iterable[dict[str, Any]]:
    keys = list(grid.keys())
    values = [list(grid[key]) for key in keys]
    start = max(0, int(offset or 0))
    stop = None if limit is None else start + max(0, int(limit))
    for idx, combo in enumerate(product(*values)):
        if idx < start:
            continue
        if stop is not None and idx >= stop:
            break
        yield dict(zip(keys, combo))


def _grid_size(grid: dict[str, Iterable[Any]]) -> int:
    total = 1
    for values in grid.values():
        total *= len(list(values))
    return total


def _passes_common(
    result: dict,
    *,
    min_cost: float,
    min_trips: int,
) -> bool:
    return (
        float(result.get('cost_reduction_pct') or 0.0) >= min_cost and
        int(result.get('round_trips') or 0) >= min_trips
    )


def _score(full: dict, validation: dict, fold_results: list[dict]) -> float:
    worst_cost = min(
        (float(row.get('cost_reduction_pct') or 0.0) for row in fold_results),
        default=0.0,
    )
    worst_min = min(
        (float(row.get('min_cost_reduction_pct') or 0.0) for row in fold_results),
        default=0.0,
    )
    return round(
        float(full.get('cost_reduction_pct') or 0.0) * 5.0 +
        float(validation.get('cost_reduction_pct') or 0.0) * 4.0 +
        float(full.get('min_cost_reduction_pct') or 0.0) +
        float(validation.get('min_cost_reduction_pct') or 0.0) +
        worst_cost + worst_min,
        6,
    )


def _fold_summary(fold_results: list[dict]) -> dict[str, float | int]:
    if not fold_results:
        return {
            'fold_count': 0,
            'fold_pass_count': 0,
            'fold_pass_rate_pct': 0.0,
            'worst_fold_cost_reduction_pct': 0.0,
            'worst_fold_min_cost_reduction_pct': 0.0,
            'avg_fold_cost_reduction_pct': 0.0,
        }
    costs = [float(row.get('cost_reduction_pct') or 0.0) for row in fold_results]
    min_costs = [
        float(row.get('min_cost_reduction_pct') or 0.0)
        for row in fold_results
    ]
    pass_count = sum(1 for cost in costs if cost >= 0.0)
    return {
        'fold_count': len(fold_results),
        'fold_pass_count': pass_count,
        'fold_pass_rate_pct': round(pass_count / len(fold_results) * 100.0, 4),
        'worst_fold_cost_reduction_pct': round(min(costs), 4),
        'worst_fold_min_cost_reduction_pct': round(min(min_costs), 4),
        'avg_fold_cost_reduction_pct': round(sum(costs) / len(costs), 4),
    }


def optimize_t0_parameters(
    code: str,
    bars: list[dict],
    *,
    base_params: dict[str, Any],
    grid: dict[str, Iterable[Any]],
    run_strategy: RunStrategy,
    offset: int = 0,
    limit: int | None = None,
    validation_ratio: float = 0.35,
    fold_count: int = 3,
    constraints: T0OptimizerConstraints | None = None,
    include_base_candidate: bool = False,
) -> dict[str, Any]:
    constraints = constraints or T0OptimizerConstraints()
    total_grid = _grid_size(grid) + (1 if include_base_candidate else 0)
    train, validation = _split_train_validation(bars, validation_ratio)
    validation_bars = validation or train
    folds = _split_folds(validation_bars, fold_count)
    rows: list[dict[str, Any]] = []
    rejected_full = 0
    rejected_validation = 0
    rejected_fold = 0
    evaluated = 0

    candidate_overrides: Iterable[dict[str, Any]]
    if include_base_candidate:
        start = max(0, int(offset or 0))
        stop = None if limit is None else start + max(0, int(limit))

        def _candidates() -> Iterable[dict[str, Any]]:
            if start == 0:
                yield {}
            grid_offset = max(0, start - 1)
            grid_limit = None if stop is None else max(0, stop - 1 - grid_offset)
            if grid_limit == 0:
                return
            yield from iter_parameter_grid(
                grid,
                offset=grid_offset,
                limit=grid_limit,
            )

        candidate_overrides = _candidates()
    else:
        candidate_overrides = iter_parameter_grid(
            grid, offset=offset, limit=limit,
        )

    for overrides in candidate_overrides:
        evaluated += 1
        params = {**base_params, **overrides}
        full = run_strategy(code, bars, params)
        if not _passes_common(
            full,
            min_cost=constraints.min_full_cost_reduction_pct,
            min_trips=constraints.min_full_round_trips,
        ):
            rejected_full += 1
            continue
        validation_result = run_strategy(code, validation_bars, params)
        if not _passes_common(
            validation_result,
            min_cost=constraints.min_validation_cost_reduction_pct,
            min_trips=constraints.min_validation_round_trips,
        ):
            rejected_validation += 1
            continue

        fold_results = [run_strategy(code, fold, params) for fold in folds]
        fold_ok = all(
            float(row.get('cost_reduction_pct') or 0.0) >=
            constraints.min_fold_cost_reduction_pct and
            float(row.get('min_cost_reduction_pct') or 0.0) >=
            constraints.min_fold_min_cost_reduction_pct
            for row in fold_results
        )
        if not fold_ok:
            rejected_fold += 1
            continue

        rows.append({
            'score': _score(full, validation_result, fold_results),
            'params': params,
            'full': full,
            'validation': validation_result,
            'folds': fold_results,
            **_fold_summary(fold_results),
        })

    rows.sort(key=lambda row: row['score'], reverse=True)
    start = max(0, int(offset or 0))
    next_offset = start + evaluated
    return {
        'total_grid': total_grid,
        'offset': start,
        'limit': limit,
        'evaluated': evaluated,
        'next_offset': next_offset if next_offset < total_grid else None,
        'rows': rows,
        'rejected_full': rejected_full,
        'rejected_validation': rejected_validation,
        'rejected_fold': rejected_fold,
    }
