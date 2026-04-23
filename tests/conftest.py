"""Shared fixtures. TDX-dependent tests are skipped if the TDX client is offline."""
import pytest


@pytest.fixture(scope='session')
def tdx_ready():
    """Returns the live tdx singleton; skips the test if TDX is unreachable."""
    try:
        from tdx_service import tdx
    except ImportError as e:
        pytest.skip(f'tqcenter SDK not importable: {e}')
        return  # unreachable; silence linters
    if not tdx.initialize():
        pytest.skip('TDX failed to initialize — start 通达信 and press F12')
    if not tdx.is_connected():
        pytest.skip('TDX not connected')
    return tdx


@pytest.fixture(scope='session')
def vnpy_configured():
    """Point vnpy at data/vnpy_data.db once per session."""
    from scripts.setup.vnpy_config import configure
    return configure()


@pytest.fixture(autouse=True)
def _close_peewee_db_between_tests():
    """vnpy_sqlite's peewee SqliteDatabase is a module-level singleton. Tests
    that instantiate ``Database()`` without closing leak the connection, which
    makes subsequent ``Database()`` calls raise ``peewee.OperationalError:
    Connection already opened``. Close after every test as a safety net.
    """
    yield
    try:
        from vnpy_sqlite.sqlite_database import db as _peewee_db
    except Exception:  # vnpy_sqlite not imported / not configured yet
        return
    if not _peewee_db.is_closed():
        _peewee_db.close()


@pytest.fixture(autouse=True)
def _reset_storage_between_tests():
    """Ensure every test starts with clean storage singletons."""
    import storage
    storage.reset()
    yield
    storage.reset()


@pytest.fixture
def observability_storage(tmp_path):
    """Full wire-up for end-to-end BacktestRunner + storage tests.

    Seeds every store the runner touches (personas, agents, prompt_versions,
    models, backtests, audit, redline, stock_status, llm_cache, calendar),
    registers the 4 validation handlers, and sets a 15% position cap so
    100-share lots at ~¥100 fit under the default budget.

    Kline is NOT seeded — runner tests monkeypatch `backtest.runner._load_daily_closes`
    and `backtest.runner._trading_days` at module level, same pattern as
    tests/test_backtest_runner.py::wired_full.

    Yields tmp_path for test-local file paths. Storage is reset at teardown
    (redundant with _reset_storage_between_tests but explicit).
    """
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
    from storage.sqlite_calendar import SQLiteCalendarStore
    from validation.base import DEFAULT_REDLINES

    storage.reset()
    for cls, setter in [
        (SQLiteRedLineStore,        'set_redline'),
        (SQLiteStockStatusStore,    'set_stock_status'),
        (SQLiteAuditStore,          'set_audit'),
        (SQLiteLLMDecisionCache,    'set_llm_cache'),
        (SQLitePersonaStore,        'set_personas'),
        (SQLiteAgentStore,          'set_agents'),
        (SQLitePromptVersionStore,  'set_prompt_versions'),
        (SQLiteModelStore,          'set_models'),
        (SQLiteBacktestResultStore, 'set_backtests'),
        (SQLiteCalendarStore,       'set_calendar'),
    ]:
        inst = cls(tmp_path=tmp_path)
        inst.init_schema()
        getattr(storage, setter)(inst)
    storage.models().seed()

    from validation import rules as _rules
    _rules.reset()
    from validation.handlers.position_max_pct import Handler as H1
    from validation.handlers.ban_st import Handler as H2
    from validation.handlers.max_holdings import Handler as H3
    from validation.handlers.daily_loss_limit_pct import Handler as H4
    _rules.register(H1())
    _rules.register(H2())
    _rules.register(H3())
    _rules.register(H4())

    storage.redline().set({**DEFAULT_REDLINES, 'position_max_pct': 15.0})
    from personas import seed as seed_personas
    seed_personas()

    yield tmp_path
    storage.reset()
