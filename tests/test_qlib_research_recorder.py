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
