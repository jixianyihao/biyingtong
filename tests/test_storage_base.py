"""Protocols + factory singleton pattern for storage/."""
from datetime import date, datetime
from typing import Protocol


def test_model_info_dataclass():
    from storage.base import ModelInfo
    m = ModelInfo(
        id='claude-opus-4-7', provider='anthropic',
        display_name='Claude Opus 4.7', api_model_id='claude-opus-4-7',
        training_cutoff='2026-01-31',
        supports_tool_use=True, max_tokens_out=4096, enabled=True,
    )
    assert m.training_cutoff == '2026-01-31'


def test_protocols_defined():
    from storage.base import KlineStore, FinancialStore, ModelStore, CalendarStore
    assert isinstance(KlineStore, type(Protocol))
    assert isinstance(FinancialStore, type(Protocol))
    assert isinstance(ModelStore, type(Protocol))
    assert isinstance(CalendarStore, type(Protocol))


def test_factories_return_same_singleton():
    import storage
    storage.reset()

    class FakeKline:
        def save_bars(self, bars): return 0
        def get_recent(self, code, period, count): return []
        def load_range(self, code, period, start, end): return []
        def get_closes(self, code, count): return []
        def distinct_dates(self, start, end): return []

    fake = FakeKline()
    storage.set_kline(fake)
    assert storage.kline() is fake
    assert storage.kline() is storage.kline()


def test_reset_clears_all_singletons():
    import storage
    storage.reset()

    class Noop:
        def save_bars(self, bars): return 0
        def get_recent(self, *a, **kw): return []
        def load_range(self, *a, **kw): return []
        def get_closes(self, *a, **kw): return []
        def distinct_dates(self, *a, **kw): return []

    n = Noop()
    storage.set_kline(n)
    storage.reset()

    assert storage.kline() is not n


def test_default_factories_return_sqlite_impls():
    """After reset, calling storage.kline() etc. builds the SQLite default."""
    import storage
    storage.reset()

    from storage.sqlite_kline import SQLiteKlineStore
    assert isinstance(storage.kline(), SQLiteKlineStore)


def test_protocols_are_runtime_checkable():
    from storage.base import KlineStore

    class Compliant:
        def save_bars(self, bars): return 0
        def get_recent(self, code, period, count): return []
        def load_range(self, code, period, start, end): return []
        def get_closes(self, code, count): return []
        def distinct_dates(self, start, end): return []

    assert isinstance(Compliant(), KlineStore)


def test_persona_dataclass():
    from storage.base import Persona
    p = Persona(
        id='x', name='Test', style_desc='desc',
        system_prompt='prompt', default_pool=['600519.SH'],
        pool_filter=None, default_schedule='daily',
        default_rules={'position_max_pct': 30.0},
        allowed_tools=['get_kline'], is_builtin=True,
    )
    assert p.id == 'x'
    assert p.created_at is None


def test_agent_dataclass():
    from storage.base import Agent
    a = Agent(
        id='a1', persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='林园 · Claude Opus 4.7', rules_override={},
        initial_capital=1_000_000, status='created',
        subprocess_pid=None, health_score=100, trust_rating='A',
        current_prompt_version_id=None,
    )
    assert a.persona_id == 'linyuan'


def test_prompt_version_dataclass():
    from storage.base import PromptVersion
    v = PromptVersion(
        id=1, agent_id='a1', version_number=1,
        system_prompt='You are X', created_at='2026-04-22T00:00:00',
    )
    assert v.note is None


def test_persona_store_protocol_runtime_checkable():
    from storage.base import Persona, PersonaStore

    class Compliant:
        def init_schema(self): pass
        def upsert(self, persona): pass
        def get(self, persona_id): return None
        def list_all(self): return []
        def delete(self, persona_id): return False

    assert isinstance(Compliant(), PersonaStore)


def test_agent_store_protocol_runtime_checkable():
    from storage.base import AgentStore

    class Compliant:
        def init_schema(self): pass
        def create_from_persona(self, persona_id, model_id, display_name,
                                 rules_override=None, initial_capital=1_000_000):
            return None  # type: ignore
        def get(self, agent_id): return None
        def list_all(self): return []
        def update_status(self, agent_id, status): pass
        def update_health(self, agent_id, health, rating): pass
        def update(self, agent_id, *, display_name=None, rules_override=None): pass
        def delete(self, agent_id): return False
        def set_current_prompt_version(self, agent_id, version_id): pass

    assert isinstance(Compliant(), AgentStore)


def test_prompt_version_store_protocol_runtime_checkable():
    from storage.base import PromptVersionStore

    class Compliant:
        def init_schema(self): pass
        def insert(self, agent_id, system_prompt, note=None): return None  # type: ignore
        def get_latest(self, agent_id): return None
        def get_by_id(self, version_id): return None
        def list_for_agent(self, agent_id): return []
        def rollback(self, agent_id, version_id): return None  # type: ignore

    assert isinstance(Compliant(), PromptVersionStore)


def test_redline_store_protocol_exists():
    from storage.base import RedLineStore
    assert hasattr(RedLineStore, 'init_schema')
    assert hasattr(RedLineStore, 'get')
    assert hasattr(RedLineStore, 'set')


def test_stock_status_store_protocol_exists():
    from storage.base import StockStatusStore
    for m in ('init_schema', 'upsert', 'get', 'is_st', 'is_suspended', 'bulk_upsert'):
        assert hasattr(StockStatusStore, m), f'missing {m}'


def test_audit_store_protocol_exists():
    from storage.base import AuditStore
    for m in ('init_schema', 'log', 'query_by_agent', 'query_by_kind'):
        assert hasattr(AuditStore, m), f'missing {m}'


def test_backtest_result_store_protocol_exists():
    from storage.base import BacktestResultStore
    for m in ('init_schema', 'insert', 'get', 'list_for_agent',
              'list_for_session', 'create_session'):
        assert hasattr(BacktestResultStore, m), f'missing {m}'


def test_llm_decision_cache_store_protocol_exists():
    from storage.base import LLMDecisionCacheStore
    for m in ('init_schema', 'get', 'put', 'has'):
        assert hasattr(LLMDecisionCacheStore, m), f'missing {m}'
