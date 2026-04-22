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
