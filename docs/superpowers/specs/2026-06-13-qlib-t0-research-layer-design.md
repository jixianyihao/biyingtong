# Qlib T0 Research Layer Design

Date: 2026-06-13
Branch: `codex-a-share-t0`
Goal: keep reducing A-share intraday T0 base cost as much as possible, while using Qlib as the research layer.

## Decision

Use Qlib as a research, feature, and experiment-management layer. Do not replace the existing BiYingTong T0 execution simulator with Qlib backtesting.

This boundary is deliberate:

- `t0/portfolio.py::run_t0_portfolio_backtest` already models the project-specific truth: A-share T+1 sellability, old-share-only sell-first legs, same-day buy restrictions, base position cost, T cash, fees, sell tax, slippage, and multi-round intraday T.
- Qlib's strongest fit here is data preparation, feature retrieval, workflow management, recorder/MLflow experiment tracking, and optional model/meta-selector research.
- Qlib's own high-frequency framework is useful as a reference for nested decisions, but the current project has a stricter domain rule: the metric that matters is gradual base-cost reduction under A-share T+1 constraints.

## External Basis

The Qlib docs support this split:

- Data layer: Qlib can convert user-provided CSV/Parquet into Qlib format with `scripts/dump_bin.py`, and documents 1min data preparation examples.
- Recorder: Qlib Recorder manages experiments, recorders, parameters, metrics, artifacts, and can use MLflow for visualization.
- High-frequency framework: Qlib documents nested decision execution for combining daily and intraday decision levels, but that is a framework shape rather than a drop-in replacement for this repo's A-share T0 cost simulator.

References checked:

- <https://qlib.readthedocs.io/en/latest/component/data.html>
- <https://qlib.readthedocs.io/en/latest/component/recorder.html>
- <https://qlib.readthedocs.io/en/latest/component/highfreq.html>
- <https://github.com/microsoft/qlib>

Context7 was attempted first for current docs, but the MCP server returned `-32601: tools/call`; official Qlib docs and GitHub were used as fallback sources.

## Architecture

```text
TDX / local .lc1 1min data
  -> qlib_research exporter
       - normalize minute bars
       - write Qlib-compatible CSV/parquet inputs
       - optional dump_bin integration when qlib is installed
  -> qlib_research feature builder
       - amplitude / range regime
       - VWAP deviation / adaptive z-score
       - volume and turnover proxies
       - opening gap / opening range
       - intraday trend and reversal features
  -> qlib_research experiment recorder
       - records stock universe, window, params, result metrics, artifacts
       - uses Qlib Recorder if installed
       - falls back to local JSONL/SQLite if Qlib is not installed
  -> existing t0 optimizer
       - consumes candidate parameter ranges / selected symbols
       - still runs run_t0_portfolio_backtest as execution truth
  -> existing API/UI
       - candidate scan
       - optimizer results
       - cost path and validation evidence
```

## Components

### 1. `qlib_research/exporter.py`

Purpose: convert local TDX `.lc1` minute bars into a stable research dataset format.

Inputs:

- stock code list, e.g. `300951.SZ`
- date window
- local bars from `t0/local_lc1.py`

Outputs:

- CSV files under `data/qlib_research/source/1min/`
- one file per instrument or one combined file with symbol column
- fields: `symbol`, `date`, `open`, `high`, `low`, `close`, `volume`, `money`, `factor`

Rules:

- Preserve original minute timestamps.
- `factor=1.0` until adjusted-price handling is explicitly added.
- Do not silently synthesize missing bars.
- Report data coverage and missing-day count.

### 2. `qlib_research/features.py`

Purpose: compute research features that help decide which names and parameter regions are worth sending into the expensive T0 optimizer.

Initial feature set:

- `avg_amplitude_pct`
- `avg_intraday_range_pct`
- `vwap_deviation_mean_pct`
- `vwap_deviation_std_pct`
- `vwap_zscore_tail_count`
- `opening_range_pct`
- `opening_gap_pct`
- `volume_cv`
- `trend_slope`
- `reversal_score`

Output:

- pandas DataFrame or list of dicts keyed by symbol/date.
- feature summary JSON artifact for UI/debug review.

### 3. `qlib_research/recorder.py`

Purpose: record every optimizer experiment so iteration does not become anecdotal.

Primary path:

- If `qlib` is installed, use `qlib.workflow.R` and Qlib Recorder APIs to log params, metrics, and artifacts.

Fallback path:

- If Qlib is not installed, write local JSONL under `data/qlib_research/records/`.
- The fallback keeps the API usable on a clean machine and prevents Qlib installation issues from blocking T0 work.

Recorded fields:

- experiment name
- symbol / universe
- data window and bar count
- feature snapshot hash
- optimizer grid id / offset / limit
- best params
- full cost reduction
- validation cost reduction
- fold pass rate
- worst fold cost reduction
- min cost path
- runtime seconds

### 4. `scripts/research/t0_qlib_spike.py`

Purpose: one repeatable command for the first spike.

Example target:

```powershell
python scripts/research/t0_qlib_spike.py `
  --codes 300951.SZ,600724.SH,002468.SZ `
  --start 2026-01-01 `
  --end 2026-04-01 `
  --optimizer-limit 96
```

Behavior:

1. Load local `.lc1` bars.
2. Export Qlib-compatible research CSV.
3. Build features.
4. Run existing T0 optimizer.
5. Record metrics through Qlib Recorder if available; otherwise JSONL fallback.
6. Print a compact ranking by validation cost reduction, fold stability, and worst-fold cost.

## API/UI Integration

Phase 1 should not add a complex UI. It should add one backend-visible artifact and one small UI indicator:

- `/api/t0/candidates` can later expose `research_record_id` and `research_feature_summary`.
- T0Lab can show a small `QLIB REC` / `JSONL REC` badge beside optimizer preview rows.

Do not block candidate scan if Qlib is missing.

## Testing

Unit tests:

- exporter writes required Qlib columns and preserves minute timestamps.
- feature builder produces deterministic values for a small synthetic minute dataset.
- recorder falls back to JSONL when Qlib import fails.
- recorder calls Qlib path through dependency injection when a fake `R` object is supplied.

Integration tests:

- spike command runs on a tiny local fixture and produces:
  - source CSV
  - feature summary
  - optimizer result
  - recorder artifact

Real-data smoke:

- Run one symbol from the current stable candidate set (`300951.SZ` or successor from scan).
- Verify the existing T0 optimizer still returns cost-reduction metrics and the recorder captures them.

## Success Criteria

The first Qlib research-layer milestone is complete only when:

1. One command exports local TDX 1min data to a Qlib-compatible research dataset.
2. Feature summaries are generated from real local 1min data.
3. Existing BiYingTong T0 optimizer results are recorded through Qlib Recorder when available.
4. The same command still works without Qlib installed by using local JSONL fallback.
5. Tests cover exporter, feature builder, recorder fallback, and command smoke.
6. No code path replaces `run_t0_portfolio_backtest` as the source of truth for A-share T0 execution.

## Non-Goals

- Do not replace the current T0 backtester with Qlib's portfolio backtest.
- Do not train RL or deep learning models in the first milestone.
- Do not add live trading behavior.
- Do not add a large UI workflow before the research artifacts prove useful.
- Do not treat Qlib as proof of profitability. It is an experiment-management and research layer.

## Open Implementation Notes

- Qlib may be heavy or fail to install on Windows. The fallback recorder is mandatory.
- If Qlib's official `dump_bin.py` is not installed locally, the exporter still writes valid CSV and records the command needed to convert later.
- The first implementation should prefer deterministic feature engineering over ML. Model training can come after enough real experiments are recorded.
