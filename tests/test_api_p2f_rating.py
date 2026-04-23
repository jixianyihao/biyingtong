"""GET /api/backtests/<id>/rating — 5-sub-score strategy rating."""
from __future__ import annotations

import pytest


def _fresh_app():
    from flask import Flask
    from api import api_bp
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def wired(tmp_path):
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


def test_rating_unknown_result_id_is_404(client):
    resp = client.get('/api/backtests/does-not-exist/rating')
    assert resp.status_code == 404


def test_rating_returns_all_sub_scores_and_letter(client, wired):
    """Insert a BacktestResult and GET /rating returns all expected keys."""
    from backtest.base import BacktestResult, BacktestStats, ZoneStats
    stats = BacktestStats(
        sharpe=1.2, max_drawdown_pct=-8.0, trade_count=25,
        win_rate=58.0, max_daily_loss_pct=-2.5,
        total_return_pct=18.0, final_equity=1_180_000.0,
    )
    zones = [
        ZoneStats(zone='pollution', days=20,
                  stats={'sharpe': 1.1, 'max_drawdown_pct': -5.0,
                         'trade_count': 10, 'win_rate': 55.0,
                         'max_daily_loss_pct': -2.0,
                         'total_return_pct': 7.0,
                         'final_equity': 1_070_000.0}),
        ZoneStats(zone='buffer', days=5, stats={}),
        ZoneStats(zone='clean', days=30,
                  stats={'sharpe': 1.3, 'max_drawdown_pct': -6.0,
                         'trade_count': 15, 'win_rate': 60.0,
                         'max_daily_loss_pct': -2.5,
                         'total_return_pct': 11.0,
                         'final_equity': 1_110_000.0}),
    ]
    r = BacktestResult(
        id='r-api-test', session_id='s-api-test', agent_id='a-api-test',
        persona_id='linyuan', model_id='claude-opus-4-7',
        start_date='2025-01-01', end_date='2025-02-01',
        initial_capital=1_000_000.0, final_equity=1_180_000.0,
        stats=stats, zone_stats=zones,
        quality_gate_label='pass', quality_gate_criteria={},
    )
    # Session row required for FK-like consistency — insert both
    wired.backtests().create_session(
        's-api-test', '2025-01-01', '2025-02-01', ['a-api-test'],
    )
    wired.backtests().insert(r)

    resp = client.get('/api/backtests/r-api-test/rating')
    assert resp.status_code == 200
    body = resp.get_json()
    # All 5 sub-scores + overall + letter + notes
    for key in ('return_power', 'risk_control', 'stability',
                'trading_efficiency', 'overfitting_risk',
                'overall', 'letter', 'notes'):
        assert key in body, f'missing {key}'
    assert body['letter'] in ('A+', 'A', 'B', 'C', 'D')
    assert isinstance(body['notes'], list)
    # Overall must be weighted sum (rough sanity: between min and max subscore)
    subs = [body['return_power'], body['risk_control'], body['stability'],
            body['trading_efficiency'], body['overfitting_risk']]
    assert min(subs) - 0.1 <= body['overall'] <= max(subs) + 0.1
