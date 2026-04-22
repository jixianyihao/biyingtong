"""SQLiteFinancialStore — financial_cache.db wrapper."""
from datetime import date


def test_sqlite_financial_satisfies_protocol(tmp_path):
    from storage.base import FinancialStore
    from storage.sqlite_financial import SQLiteFinancialStore
    assert isinstance(SQLiteFinancialStore(tmp_path=tmp_path), FinancialStore)


def test_init_schema_creates_table(tmp_path):
    from storage.sqlite_financial import SQLiteFinancialStore
    store = SQLiteFinancialStore(tmp_path=tmp_path)
    store.init_schema()

    import sqlite3
    con = sqlite3.connect(tmp_path / 'financial_cache.db')
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='financial_data'"
        ).fetchall()
    finally:
        con.close()
    assert len(rows) == 1


def test_upsert_and_get_latest(tmp_path):
    from storage.sqlite_financial import SQLiteFinancialStore
    store = SQLiteFinancialStore(tmp_path=tmp_path)
    store.init_schema()

    rows = [
        {'stock_code': '600519', 'date': '2025-03-31', 'pe': 23.1, 'pb': 9.0,
         'roe': 36.0, 'gross_margin': 91.5, 'revenue_growth': 12.3,
         'net_profit_growth': 15.4},
        {'stock_code': '600519', 'date': '2025-06-30', 'pe': 21.0, 'pb': 8.5,
         'roe': 36.5, 'gross_margin': 91.2, 'revenue_growth': 11.1,
         'net_profit_growth': 13.8},
    ]
    assert store.upsert(rows) == 2

    latest = store.get_latest('600519')
    assert latest is not None
    assert latest['date'] == '2025-06-30'
    assert latest['pe'] == 21.0
    assert latest['revenue_growth'] == 11.1


def test_upsert_idempotent(tmp_path):
    from storage.sqlite_financial import SQLiteFinancialStore
    store = SQLiteFinancialStore(tmp_path=tmp_path)
    store.init_schema()

    row = {'stock_code': '600519', 'date': '2025-03-31', 'pe': 23.1, 'pb': 9.0,
           'roe': 36.0, 'gross_margin': 91.5, 'revenue_growth': 12.3,
           'net_profit_growth': 15.4}
    store.upsert([row])
    row2 = dict(row, pe=25.0)
    store.upsert([row2])

    latest = store.get_latest('600519')
    assert latest['pe'] == 25.0


def test_get_latest_missing_returns_none(tmp_path):
    from storage.sqlite_financial import SQLiteFinancialStore
    store = SQLiteFinancialStore(tmp_path=tmp_path)
    store.init_schema()
    assert store.get_latest('000000') is None
