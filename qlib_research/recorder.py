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
    safe = ''.join(
        ch if ch.isalnum() or ch in {'-', '_'} else '_'
        for ch in experiment
    )
    return root / 'records' / f'{safe}.jsonl'


def _record_jsonl(run: ResearchRun, root: Path) -> dict[str, Any]:
    path = _jsonl_path(root, run.experiment)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(run)
    payload['created_at'] = datetime.now(
        timezone.utc,
    ).isoformat(timespec='seconds')
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
    workflow = (
        qlib_workflow
        if qlib_workflow is not None
        else _load_default_qlib_workflow()
    )
    if workflow is None:
        return _record_jsonl(run, target_root)
    with workflow.start(
        experiment_name=run.experiment,
        recorder_name=run.recorder,
    ):
        workflow.log_params(**run.params)
        workflow.log_metrics(**run.metrics)
    return {'backend': 'qlib', 'path': None}
