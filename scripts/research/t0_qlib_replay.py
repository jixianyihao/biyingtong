from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qlib_research.recorder import ResearchRun, record_research_run
from scripts.research.t0_qlib_spike import _default_load_bars


BarLoader = Callable[..., list[dict[str, Any]]]
T0BacktestRunner = Callable[..., dict[str, Any]]


REPLAY_METRIC_KEYS = (
    'final_equity',
    'total_return_pct',
    'cost_reduction_pct',
    'min_cost_reduction_pct',
    'cost_reduction_positive_days_pct',
    'alpha_vs_all_in_hold',
    'max_drawdown_pct',
    'round_trips',
    'win_rate',
)


def summarize_replay_result(result: dict[str, Any]) -> dict[str, Any]:
    """Keep the compact audit surface for a replayed T0 parameter set."""
    return {key: result.get(key) for key in REPLAY_METRIC_KEYS}


def _default_run_backtest(
    code: str,
    bars: list[dict[str, Any]],
    **params: Any,
) -> dict[str, Any]:
    from t0.portfolio import run_t0_portfolio_backtest

    return run_t0_portfolio_backtest(code, bars, **params)


def run_replay(
    *,
    code: str,
    start: str,
    end: str,
    strategy_profile: str,
    params: dict[str, Any] | None = None,
    out_root: str | Path = 'data/qlib_research',
    load_bars: BarLoader = _default_load_bars,
    run_backtest: T0BacktestRunner = _default_run_backtest,
) -> dict[str, Any]:
    """Replay one optimized T0 parameter set against the full backtest engine.

    This module intentionally stays orchestration-only: strategy defaults live
    in ``t0.strategy_profiles``, execution lives in ``t0.portfolio``, and run
    evidence lives in ``qlib_research.recorder``.
    """
    from t0.strategy_profiles import get_t0_strategy_profile

    profile = get_t0_strategy_profile(strategy_profile)
    merged_params = profile.build_base_params(params)
    bars = load_bars(code, start=start, end=end)
    result = run_backtest(code, bars, **merged_params)
    metrics = summarize_replay_result(result)

    record = record_research_run(
        ResearchRun(
            experiment='t0-qlib-replay',
            recorder=code,
            params={
                'code': code,
                'start': start,
                'end': end,
                'strategy_profile': profile.name,
                'strategy_params': merged_params,
            },
            metrics=metrics,
            artifacts={
                'daily': result.get('daily', []),
                'trades': result.get('trades', []),
            },
        ),
        root=out_root,
    )

    return {
        'code': code,
        'start': start,
        'end': end,
        'strategy_profile': profile.name,
        'params': merged_params,
        'metrics': metrics,
        'record_backend': record['backend'],
        'record_path': record.get('path'),
    }


def _load_params_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.params_file:
        return json.loads(Path(args.params_file).read_text(encoding='utf-8-sig'))
    if args.params_json:
        return json.loads(args.params_json)
    return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--code', required=True)
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument(
        '--strategy-profile',
        default='adaptive_vwap_cost',
        help='T0 strategy profile name from t0.strategy_profiles',
    )
    parser.add_argument('--params-json')
    parser.add_argument('--params-file')
    parser.add_argument('--out-root', default='data/qlib_research')
    args = parser.parse_args()

    result = run_replay(
        code=args.code,
        start=args.start,
        end=args.end,
        strategy_profile=args.strategy_profile,
        params=_load_params_from_args(args),
        out_root=args.out_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
