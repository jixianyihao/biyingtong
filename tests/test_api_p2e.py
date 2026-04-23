"""E2E: exercise every /api/* P2e endpoint via Flask test client."""
from __future__ import annotations

import pytest


def _fresh_app():
    """Build a Flask app with only the P2e blueprint (skip socketio / TDX wiring)."""
    from flask import Flask
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def wired(tmp_path):
    """Set up all stores + seed personas + models + one agent + one backtest."""
    import storage
    from storage.sqlite_redline import SQLiteRedLineStore
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.sqlite_audit import SQLiteAuditStore
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    from storage.sqlite_personas import SQLitePersonaStore
    from storage.sqlite_agents import SQLiteAgentStore
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    from storage.sqlite_models import SQLiteModelStore
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    from storage.sqlite_baselines import SQLiteBaselineResultStore

    for cls, setter in [
        (SQLiteRedLineStore, 'set_redline'),
        (SQLiteStockStatusStore, 'set_stock_status'),
        (SQLiteAuditStore, 'set_audit'),
        (SQLiteLLMDecisionCache, 'set_llm_cache'),
        (SQLitePersonaStore, 'set_personas'),
        (SQLiteAgentStore, 'set_agents'),
        (SQLitePromptVersionStore, 'set_prompt_versions'),
        (SQLiteModelStore, 'set_models'),
        (SQLiteBacktestResultStore, 'set_backtests'),
        (SQLiteBaselineResultStore, 'set_baselines'),
    ]:
        inst = cls(tmp_path=tmp_path); inst.init_schema()
        getattr(storage, setter)(inst)
    storage.models().seed()

    from personas import seed as seed_personas
    seed_personas()
    return storage


@pytest.fixture
def client(wired):
    return _fresh_app().test_client()


@pytest.fixture
def agent(wired):
    a = wired.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='API-Test',
    )
    return a


def test_get_personas_list(client):
    resp = client.get('/api/personas')
    assert resp.status_code == 200
    data = resp.get_json()
    ids = {p['id'] for p in data}
    assert {'linyuan', 'buffet', 'fuyou', 'soros', 'quant_neutral',
            'intraday_t0'} <= ids


def test_get_persona_detail(client):
    resp = client.get('/api/personas/linyuan')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['id'] == 'linyuan'
    assert 'system_prompt' in data
    assert data['is_builtin'] is True


def test_get_persona_not_found(client):
    resp = client.get('/api/personas/nope')
    assert resp.status_code == 404


def test_get_models_list(client):
    resp = client.get('/api/models')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert any('claude' in m['id'] or 'gpt' in m['id'] for m in data)


def test_get_model_detail(client):
    resp = client.get('/api/models/claude-opus-4-7')
    assert resp.status_code == 200
    assert resp.get_json()['id'] == 'claude-opus-4-7'


def test_get_agents_list_empty(client):
    resp = client.get('/api/agents')
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_get_agents_list_after_create(client, agent):
    resp = client.get('/api/agents')
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['id'] == agent.id
    assert data[0]['persona_id'] == 'linyuan'


def test_get_agent_detail(client, agent):
    resp = client.get(f'/api/agents/{agent.id}')
    assert resp.status_code == 200
    assert resp.get_json()['display_name'] == 'API-Test'


def test_agent_health_recomputes(client, agent):
    resp = client.get(f'/api/agents/{agent.id}/health')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['agent_id'] == agent.id
    # No audit rows → health = 100 → A+
    assert data['health_score'] == 100
    assert data['trust_rating'] == 'A+'


def test_backtests_require_agent_id(client):
    resp = client.get('/api/backtests')
    assert resp.status_code == 400


def test_backtests_list_by_agent(client, agent, wired):
    from backtest.baselines.base import BaselineResult
    from backtest.base import BacktestStats, BacktestResult

    stats = BacktestStats(
        sharpe=1.0, max_drawdown_pct=-5.0, trade_count=3,
        win_rate=66.7, max_daily_loss_pct=-1.2,
        total_return_pct=2.5, final_equity=1_025_000,
    )
    wired.backtests().create_session('s1', '2025-11-17', '2025-11-28',
                                     [agent.id])
    wired.backtests().insert(BacktestResult(
        id='r1', session_id='s1', agent_id=agent.id,
        persona_id='linyuan', model_id='claude-opus-4-7',
        start_date='2025-11-17', end_date='2025-11-28',
        initial_capital=1_000_000, stats=stats, zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
        final_equity=1_025_000,
    ))

    resp = client.get(f'/api/backtests?agent_id={agent.id}')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['id'] == 'r1'
    assert data[0]['quality_gate_label'] == 'pass'


def test_backtest_detail(client, agent, wired):
    from backtest.base import BacktestStats, BacktestResult

    stats = BacktestStats(
        sharpe=1.0, max_drawdown_pct=-5.0, trade_count=3,
        win_rate=66.7, max_daily_loss_pct=-1.2,
        total_return_pct=2.5, final_equity=1_025_000,
    )
    wired.backtests().create_session('s1', '2025-11-17', '2025-11-28',
                                     [agent.id])
    wired.backtests().insert(BacktestResult(
        id='r1', session_id='s1', agent_id=agent.id,
        persona_id='linyuan', model_id='claude-opus-4-7',
        start_date='2025-11-17', end_date='2025-11-28',
        initial_capital=1_000_000, stats=stats, zone_stats=[],
        quality_gate_label='pass', quality_gate_criteria={},
        final_equity=1_025_000,
    ))

    resp = client.get('/api/backtests/r1')
    assert resp.status_code == 200
    assert resp.get_json()['stats']['sharpe'] == 1.0


def test_backtest_detail_not_found(client):
    resp = client.get('/api/backtests/nope')
    assert resp.status_code == 404


def test_session_composite_view(client, agent, wired):
    """Session endpoint joins agents + baselines in one response."""
    from backtest.base import BacktestStats, BacktestResult
    from backtest.baselines.base import BaselineResult

    stats = BacktestStats(
        sharpe=0.8, max_drawdown_pct=-6.0, trade_count=2,
        win_rate=50.0, max_daily_loss_pct=-1.5,
        total_return_pct=1.5, final_equity=1_015_000,
    )
    wired.backtests().create_session('s1', '2025-11-17', '2025-11-28',
                                     [agent.id])
    wired.backtests().insert(BacktestResult(
        id='r1', session_id='s1', agent_id=agent.id,
        persona_id='linyuan', model_id='claude-opus-4-7',
        start_date='2025-11-17', end_date='2025-11-28',
        initial_capital=1_000_000, stats=stats, zone_stats=[],
        quality_gate_label='warn', quality_gate_criteria={},
        final_equity=1_015_000,
    ))
    wired.baselines().insert(BaselineResult(
        id='b1', session_id='s1', name='buy_and_hold',
        start_date='2025-11-17', end_date='2025-11-28',
        initial_capital=1_000_000,
        stats=BacktestStats(
            sharpe=0.2, max_drawdown_pct=-8.0, trade_count=3,
            win_rate=100.0, max_daily_loss_pct=-2.0,
            total_return_pct=-1.5, final_equity=985_000,
        ),
        final_equity=985_000,
    ))

    resp = client.get('/api/backtests/session/s1')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['session_id'] == 's1'
    assert len(data['agents']) == 1
    assert len(data['baselines']) == 1
    assert data['baselines'][0]['name'] == 'buy_and_hold'


def test_baselines_list_by_session(client, wired):
    from backtest.base import BacktestStats
    from backtest.baselines.base import BaselineResult

    wired.baselines().insert(BaselineResult(
        id='b1', session_id='s1', name='csi300',
        start_date='2025-11-17', end_date='2025-11-28',
        initial_capital=1_000_000,
        stats=BacktestStats(
            sharpe=0.3, max_drawdown_pct=-7.0, trade_count=0,
            win_rate=0.0, max_daily_loss_pct=-2.0,
            total_return_pct=-1.55, final_equity=984_500,
        ),
        final_equity=984_500,
    ))

    resp = client.get('/api/baselines?session_id=s1')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['name'] == 'csi300'


def test_baselines_require_session_id(client):
    resp = client.get('/api/baselines')
    assert resp.status_code == 400


def test_redlines_returns_defaults(client):
    resp = client.get('/api/redlines')
    assert resp.status_code == 200
    data = resp.get_json()
    # DEFAULT_REDLINES keys
    assert 'position_max_pct' in data
    assert 'ban_st' in data


def test_audit_by_agent(client, agent, wired):
    from validation.base import AuditEntry
    wired.audit().log(AuditEntry(
        kind='validation', agent_id=agent.id,
        details={'outcome': 'approved'},
    ))
    resp = client.get(f'/api/audit?agent_id={agent.id}')
    assert resp.status_code == 200
    rows = resp.get_json()
    assert len(rows) == 1
    assert rows[0]['kind'] == 'validation'


def test_audit_by_kind(client, agent, wired):
    from validation.base import AuditEntry
    wired.audit().log(AuditEntry(
        kind='warning', agent_id=agent.id,
        details={'kind': 'unknown_model'},
    ))
    resp = client.get('/api/audit?kind=warning')
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1


def test_audit_requires_filter(client):
    resp = client.get('/api/audit')
    assert resp.status_code == 400
