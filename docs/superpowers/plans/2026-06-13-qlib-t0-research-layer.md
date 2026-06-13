# Qlib T0 Research Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Qlib-compatible research layer that exports local TDX 1min data, builds deterministic T0 research features, records optimizer experiments, and keeps `run_t0_portfolio_backtest` as the execution source of truth.

**Architecture:** Create a small `qlib_research/` package beside `t0/`. It reads local `.lc1` bars through existing loaders, writes Qlib-compatible CSV artifacts, computes research features, and records optimizer runs through Qlib Recorder when available or JSONL fallback when Qlib is absent. A single spike command ties the pipeline to the existing T0 optimizer.

**Tech Stack:** Python 3.13, existing `t0/` modules, optional Qlib import, JSONL fallback, pytest.

---

## File Structure

- Create `qlib_research/__init__.py` — package marker and public exports.
- Create `qlib_research/exporter.py` — convert normalized minute bars to Qlib-compatible rows and write CSV files.
- Create `qlib_research/features.py` — compute deterministic intraday feature summaries.
- Create `qlib_research/recorder.py` — log experiment params/metrics/artifacts through optional Qlib or JSONL fallback.
- Create `scripts/research/t0_qlib_spike.py` — repeatable command for local real-data spike.
- Create `tests/test_qlib_research_exporter.py` — exporter tests.
- Create `tests/test_qlib_research_features.py` — feature tests.
- Create `tests/test_qlib_research_recorder.py` — recorder tests.
- Create `tests/test_qlib_research_spike.py` — spike command smoke with monkeypatched local bars/optimizer.

Do not modify `t0/portfolio.py` in this first milestone. The existing T0 simulator remains the truth layer.

---

### Task 1: Export Qlib-Compatible Research CSV

**Files:**
- Create: `qlib_research/__init__.py`
- Create: `qlib_research/exporter.py`
- Test: `tests/test_qlib_research_exporter.py`

- [ ] **Step 1: Write the failing exporter tests**

Add `tests/test_qlib_research_exporter.py`:

```python
from pathlib import Path

from qlib_research.exporter import bars_to_qlib_rows, write_qlib_csv


def _bars():
    return [
        {
            'ts': '2026-01-05 09:31:00',
            'date': '2026-01-05',
            'open': 10.0,
            'high': 10.2,
            'low': 9.9,
            'close': 10.1,
            'vol': 1200,
            'amount': 12120.0,
        },
        {
            'ts': '2026-01-05 09:32:00',
            'date': '2026-01-05',
            'open': 10.1,
            'high': 10.3,
            'low': 10.0,
            'close': 10.25,
            'vol': 1500,
            'amount': 15375.0,
        },
    ]


def test_bars_to_qlib_rows_preserves_minute_timestamp_and_required_columns():
    rows = bars_to_qlib_rows('300951.SZ', _bars())

    assert rows == [
        {
            'symbol': 'SZ300951',
            'date': '2026-01-05 09:31:00',
            'open': 10.0,
            'high': 10.2,
            'low': 9.9,
            'close': 10.1,
            'volume': 1200.0,
            'money': 12120.0,
            'factor': 1.0,
        },
        {
            'symbol': 'SZ300951',
            'date': '2026-01-05 09:32:00',
            'open': 10.1,
            'high': 10.3,
            'low': 10.0,
            'close': 10.25,
            'volume': 1500.0,
            'money': 15375.0,
            'factor': 1.0,
        },
    ]


def test_write_qlib_csv_writes_one_file_per_symbol(tmp_path: Path):
    path = write_qlib_csv('300951.SZ', _bars(), tmp_path)

    assert path == tmp_path / 'SZ300951.csv'
    text = path.read_text(encoding='utf-8')
    assert text.splitlines()[0] == 'symbol,date,open,high,low,close,volume,money,factor'
    assert 'SZ300951,2026-01-05 09:31:00,10.0,10.2,9.9,10.1,1200.0,12120.0,1.0' in text
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_qlib_research_exporter.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'qlib_research'`.

- [ ] **Step 3: Implement exporter**

Create `qlib_research/__init__.py`:

```python
"""Qlib-compatible research helpers for BiYingTong T0 experiments."""
```

Create `qlib_research/exporter.py`:

```python
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


QLIB_COLUMNS = [
    'symbol', 'date', 'open', 'high', 'low', 'close',
    'volume', 'money', 'factor',
]


def qlib_symbol(code: str) -> str:
    token = (code or '').strip().upper()
    if token.endswith('.SZ'):
        return 'SZ' + token[:-3]
    if token.endswith('.SH'):
        return 'SH' + token[:-3]
    return token.replace('.', '')


def _timestamp(row: dict[str, Any]) -> str:
    raw = row.get('ts') or row.get('datetime') or row.get('date')
    return str(raw).replace('T', ' ')[:19]


def bars_to_qlib_rows(code: str, bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    symbol = qlib_symbol(code)
    rows: list[dict[str, Any]] = []
    for bar in bars:
        volume = float(bar.get('vol', bar.get('volume', 0.0)) or 0.0)
        close = float(bar.get('close') or 0.0)
        money = float(bar.get('amount', bar.get('money', close * volume)) or 0.0)
        rows.append({
            'symbol': symbol,
            'date': _timestamp(bar),
            'open': float(bar.get('open') or 0.0),
            'high': float(bar.get('high') or 0.0),
            'low': float(bar.get('low') or 0.0),
            'close': close,
            'volume': volume,
            'money': money,
            'factor': 1.0,
        })
    return rows


def write_qlib_csv(code: str, bars: list[dict[str, Any]], out_dir: str | Path) -> Path:
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f'{qlib_symbol(code)}.csv'
    rows = bars_to_qlib_rows(code, bars)
    with path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=QLIB_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_qlib_research_exporter.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```powershell
git add qlib_research/__init__.py qlib_research/exporter.py tests/test_qlib_research_exporter.py
git -c user.name="ouyan" -c user.email="ouyan@users.noreply.github.com" commit -m "feat(qlib): export TDX minute bars to Qlib CSV"
```

---

### Task 2: Build Deterministic T0 Research Features

**Files:**
- Create: `qlib_research/features.py`
- Test: `tests/test_qlib_research_features.py`

- [ ] **Step 1: Write the failing feature tests**

Add `tests/test_qlib_research_features.py`:

```python
from qlib_research.features import summarize_intraday_features


def test_summarize_intraday_features_reports_range_vwap_and_reversal():
    bars = [
        {'ts': '2026-01-05 09:31:00', 'date': '2026-01-05', 'open': 10.0, 'high': 10.2, 'low': 9.9, 'close': 10.0, 'vol': 1000},
        {'ts': '2026-01-05 09:32:00', 'date': '2026-01-05', 'open': 10.0, 'high': 10.4, 'low': 9.8, 'close': 9.9, 'vol': 2000},
        {'ts': '2026-01-05 14:56:00', 'date': '2026-01-05', 'open': 9.9, 'high': 10.5, 'low': 9.7, 'close': 10.4, 'vol': 2500},
        {'ts': '2026-01-06 09:31:00', 'date': '2026-01-06', 'open': 10.5, 'high': 10.8, 'low': 10.2, 'close': 10.3, 'vol': 1200},
        {'ts': '2026-01-06 14:56:00', 'date': '2026-01-06', 'open': 10.3, 'high': 11.0, 'low': 10.1, 'close': 10.9, 'vol': 2400},
    ]

    summary = summarize_intraday_features('300951.SZ', bars)

    assert summary['code'] == '300951.SZ'
    assert summary['days'] == 2
    assert summary['bar_count'] == 5
    assert summary['avg_intraday_range_pct'] > 5.0
    assert summary['avg_amplitude_pct'] > 5.0
    assert summary['vwap_deviation_std_pct'] > 0.0
    assert summary['vwap_zscore_tail_count'] >= 0
    assert summary['opening_range_pct'] > 0.0
    assert summary['volume_cv'] > 0.0
    assert summary['reversal_score'] > 0.0
```

- [ ] **Step 2: Run test to verify RED**

Run:

```powershell
python -m pytest tests/test_qlib_research_features.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'qlib_research.features'`.

- [ ] **Step 3: Implement features**

Create `qlib_research/features.py`:

```python
from __future__ import annotations

from collections import defaultdict
from math import sqrt
from statistics import mean
from typing import Any


def _float(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _date(row: dict[str, Any]) -> str:
    return str(row.get('date') or row.get('ts') or '')[:10]


def _pct(numerator: float, denominator: float) -> float:
    return numerator / denominator * 100.0 if denominator else 0.0


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    return sqrt(sum((v - avg) ** 2 for v in values) / len(values))


def summarize_intraday_features(code: str, bars: list[dict[str, Any]]) -> dict[str, Any]:
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bar in bars:
        day = _date(bar)
        if day:
            by_day[day].append(bar)

    ranges: list[float] = []
    amplitudes: list[float] = []
    opening_ranges: list[float] = []
    reversals: list[float] = []
    volumes: list[float] = []
    vwap_devs: list[float] = []

    for day_rows in by_day.values():
        if not day_rows:
            continue
        first = day_rows[0]
        last = day_rows[-1]
        day_high = max(_float(row, 'high') for row in day_rows)
        day_low = min(_float(row, 'low') for row in day_rows)
        first_close = _float(first, 'close')
        last_close = _float(last, 'close')
        ranges.append(_pct(day_high - day_low, first_close))
        amplitudes.append(_pct(day_high - day_low, day_low))
        opening_high = max(_float(row, 'high') for row in day_rows[: min(30, len(day_rows))])
        opening_low = min(_float(row, 'low') for row in day_rows[: min(30, len(day_rows))])
        opening_ranges.append(_pct(opening_high - opening_low, first_close))
        reversals.append(abs(last_close - first_close) / max(day_high - day_low, 1e-9))

        cum_money = 0.0
        cum_volume = 0.0
        for row in day_rows:
            close = _float(row, 'close')
            vol = _float(row, 'vol', _float(row, 'volume'))
            volumes.append(vol)
            cum_money += close * vol
            cum_volume += vol
            vwap = cum_money / cum_volume if cum_volume else close
            vwap_devs.append(_pct(close - vwap, vwap))

    dev_std = _std(vwap_devs)
    tail_count = sum(1 for value in vwap_devs if dev_std > 0 and abs(value) / dev_std >= 1.5)
    vol_avg = mean(volumes) if volumes else 0.0
    vol_cv = _std(volumes) / vol_avg if vol_avg else 0.0
    closes = [_float(row, 'close') for row in bars]
    trend = _pct(closes[-1] - closes[0], closes[0]) if len(closes) >= 2 else 0.0

    return {
        'code': code,
        'days': len(by_day),
        'bar_count': len(bars),
        'avg_amplitude_pct': round(mean(amplitudes), 4) if amplitudes else 0.0,
        'avg_intraday_range_pct': round(mean(ranges), 4) if ranges else 0.0,
        'vwap_deviation_mean_pct': round(mean(vwap_devs), 4) if vwap_devs else 0.0,
        'vwap_deviation_std_pct': round(dev_std, 4),
        'vwap_zscore_tail_count': tail_count,
        'opening_range_pct': round(mean(opening_ranges), 4) if opening_ranges else 0.0,
        'opening_gap_pct': 0.0,
        'volume_cv': round(vol_cv, 4),
        'trend_slope': round(trend, 4),
        'reversal_score': round(mean(reversals), 4) if reversals else 0.0,
    }
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_qlib_research_features.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add qlib_research/features.py tests/test_qlib_research_features.py
git -c user.name="ouyan" -c user.email="ouyan@users.noreply.github.com" commit -m "feat(qlib): compute deterministic T0 research features"
```

---

### Task 3: Record Experiments Through Optional Qlib or JSONL Fallback

**Files:**
- Create: `qlib_research/recorder.py`
- Test: `tests/test_qlib_research_recorder.py`

- [ ] **Step 1: Write failing recorder tests**

Add `tests/test_qlib_research_recorder.py`:

```python
import json
from pathlib import Path

from qlib_research.recorder import ResearchRun, record_research_run


def test_record_research_run_writes_jsonl_fallback(tmp_path: Path):
    run = ResearchRun(
        experiment='t0-qlib-spike',
        recorder='300951.SZ',
        params={'code': '300951.SZ', 'limit': 12},
        metrics={'validation_cost_reduction_pct': 1.25},
        artifacts={'feature_summary': {'days': 3}},
    )

    result = record_research_run(run, root=tmp_path, qlib_workflow=None)

    assert result['backend'] == 'jsonl'
    path = Path(result['path'])
    assert path.exists()
    payload = json.loads(path.read_text(encoding='utf-8').splitlines()[0])
    assert payload['experiment'] == 't0-qlib-spike'
    assert payload['metrics']['validation_cost_reduction_pct'] == 1.25


class FakeR:
    def __init__(self):
        self.logged_params = []
        self.logged_metrics = []

    def start(self, experiment_name, recorder_name):
        self.experiment_name = experiment_name
        self.recorder_name = recorder_name
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def log_params(self, **params):
        self.logged_params.append(params)

    def log_metrics(self, **metrics):
        self.logged_metrics.append(metrics)


def test_record_research_run_uses_injected_qlib_workflow(tmp_path: Path):
    fake = FakeR()
    run = ResearchRun(
        experiment='t0-qlib-spike',
        recorder='300951.SZ',
        params={'code': '300951.SZ'},
        metrics={'score': 2.0},
        artifacts={},
    )

    result = record_research_run(run, root=tmp_path, qlib_workflow=fake)

    assert result['backend'] == 'qlib'
    assert fake.experiment_name == 't0-qlib-spike'
    assert fake.recorder_name == '300951.SZ'
    assert fake.logged_params == [{'code': '300951.SZ'}]
    assert fake.logged_metrics == [{'score': 2.0}]
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_qlib_research_recorder.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'qlib_research.recorder'`.

- [ ] **Step 3: Implement recorder**

Create `qlib_research/recorder.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ResearchRun:
    experiment: str
    recorder: str
    params: dict[str, Any]
    metrics: dict[str, float | int]
    artifacts: dict[str, Any]


def _jsonl_path(root: Path, experiment: str) -> Path:
    safe = ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '_' for ch in experiment)
    return root / 'records' / f'{safe}.jsonl'


def _record_jsonl(run: ResearchRun, root: Path) -> dict[str, Any]:
    path = _jsonl_path(root, run.experiment)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(run)
    payload['created_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    with path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, default=str) + '\n')
    return {'backend': 'jsonl', 'path': str(path)}


def _load_default_qlib_workflow():
    try:
        from qlib.workflow import R  # type: ignore
    except Exception:
        return None
    return R


def record_research_run(
    run: ResearchRun,
    *,
    root: str | Path = 'data/qlib_research',
    qlib_workflow: Any = None,
) -> dict[str, Any]:
    target_root = Path(root)
    workflow = qlib_workflow if qlib_workflow is not None else _load_default_qlib_workflow()
    if workflow is None:
        return _record_jsonl(run, target_root)
    with workflow.start(experiment_name=run.experiment, recorder_name=run.recorder):
        workflow.log_params(**run.params)
        workflow.log_metrics(**run.metrics)
    return {'backend': 'qlib', 'path': None}
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_qlib_research_recorder.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```powershell
git add qlib_research/recorder.py tests/test_qlib_research_recorder.py
git -c user.name="ouyan" -c user.email="ouyan@users.noreply.github.com" commit -m "feat(qlib): record T0 research runs with JSONL fallback"
```

---

### Task 4: Add Repeatable T0 Qlib Spike Command

**Files:**
- Create: `scripts/research/t0_qlib_spike.py`
- Test: `tests/test_qlib_research_spike.py`

- [ ] **Step 1: Write failing spike test**

Add `tests/test_qlib_research_spike.py`:

```python
from pathlib import Path

from scripts.research.t0_qlib_spike import run_spike


def test_run_spike_exports_features_optimizes_and_records(tmp_path: Path):
    bars = [
        {'ts': '2026-01-05 09:31:00', 'date': '2026-01-05', 'open': 10, 'high': 10.2, 'low': 9.9, 'close': 10.1, 'vol': 1000},
        {'ts': '2026-01-05 14:56:00', 'date': '2026-01-05', 'open': 10.1, 'high': 10.5, 'low': 9.8, 'close': 10.4, 'vol': 1200},
        {'ts': '2026-01-06 09:31:00', 'date': '2026-01-06', 'open': 10.5, 'high': 10.7, 'low': 10.2, 'close': 10.3, 'vol': 900},
        {'ts': '2026-01-06 14:56:00', 'date': '2026-01-06', 'open': 10.3, 'high': 10.9, 'low': 10.1, 'close': 10.8, 'vol': 1300},
    ]

    def load_bars(code, start=None, end=None):
        assert code == '300951.SZ'
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
            }]
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
```

- [ ] **Step 2: Run test to verify RED**

Run:

```powershell
python -m pytest tests/test_qlib_research_spike.py -q
```

Expected: FAIL with `ModuleNotFoundError` or missing `run_spike`.

- [ ] **Step 3: Implement spike command**

Create `scripts/research/t0_qlib_spike.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from qlib_research.exporter import write_qlib_csv
from qlib_research.features import summarize_intraday_features
from qlib_research.recorder import ResearchRun, record_research_run


def _default_load_bars(code: str, start: str | None = None, end: str | None = None):
    from t0.local_lc1 import load_lc1_bars_for_code
    return load_lc1_bars_for_code(code, start=start, end=end)


def _default_optimize(code: str, bars: list[dict[str, Any]], limit: int):
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

    def run_strategy(run_code: str, run_bars: list[dict[str, Any]], params: dict[str, Any]):
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
    optimize: Callable[[str, list[dict[str, Any]], int], dict[str, Any]] = _default_optimize,
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
            'best_validation_cost_reduction_pct': float(validation.get('cost_reduction_pct') or 0.0),
            'best_fold_pass_rate_pct': float(best.get('fold_pass_rate_pct') or 0.0),
            'best_worst_fold_cost_reduction_pct': float(best.get('worst_fold_cost_reduction_pct') or 0.0),
        }
        record = record_research_run(
            ResearchRun(
                experiment='t0-qlib-spike',
                recorder=code,
                params={'code': code, 'start': start, 'end': end, 'optimizer_limit': optimizer_limit},
                metrics=metrics,
                artifacts={'feature_summary': features, 'best_params': best.get('params') or {}},
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
    rows.sort(key=lambda row: (
        row['best_validation_cost_reduction_pct'],
        row['best_fold_pass_rate_pct'],
        row['best_worst_fold_cost_reduction_pct'],
    ), reverse=True)
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
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_qlib_research_spike.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add scripts/research/t0_qlib_spike.py tests/test_qlib_research_spike.py
git -c user.name="ouyan" -c user.email="ouyan@users.noreply.github.com" commit -m "feat(qlib): add repeatable T0 research spike command"
```

---

### Task 5: Full Verification and Real-Data Smoke

**Files:**
- No new files.

- [ ] **Step 1: Run focused test suite**

Run:

```powershell
python -m pytest tests/test_qlib_research_exporter.py tests/test_qlib_research_features.py tests/test_qlib_research_recorder.py tests/test_qlib_research_spike.py tests -k t0 -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run one real-data spike**

Run:

```powershell
python scripts/research/t0_qlib_spike.py --codes 300951.SZ --start 2026-01-01 --end 2026-04-01 --optimizer-limit 24
```

Expected:

- command exits 0
- output includes `"count": 1`
- output includes `"record_backend": "jsonl"` or `"record_backend": "qlib"`
- output includes `best_validation_cost_reduction_pct`
- a CSV appears under `data/qlib_research/source/1min/`
- a JSONL record appears under `data/qlib_research/records/` if Qlib is absent

- [ ] **Step 3: Check git status**

Run:

```powershell
git status --short -b
```

Expected: only intended tracked files changed; `AGENTS.md` may remain untracked and must not be staged.

- [ ] **Step 4: Commit verification docs if any generated tracked docs changed**

If no tracked docs changed, skip commit. Do not commit generated `data/qlib_research/*` artifacts unless the repo already tracks that directory.

- [ ] **Step 5: Push branch**

```powershell
git push origin codex-a-share-t0
```

Expected: push succeeds.
