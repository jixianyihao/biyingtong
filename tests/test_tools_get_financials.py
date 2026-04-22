def test_spec_shape():
    from tools.get_financials import SPEC
    assert SPEC.name == 'get_financials'


def test_reads_from_storage(tmp_path):
    """Uses storage.financial() — inject a test-specific store."""
    import storage
    from storage.sqlite_financial import SQLiteFinancialStore
    store = SQLiteFinancialStore(tmp_path=tmp_path)
    store.init_schema()
    store.upsert([
        {'stock_code': '600519', 'date': '2025-06-30', 'pe': 21.0, 'pb': 8.5,
         'roe': 36.5, 'gross_margin': 91.2, 'revenue_growth': 11.1,
         'net_profit_growth': 13.8},
    ])
    storage.set_financial(store)

    from tools.get_financials import call
    r = call({'code': '600519.SH'})
    assert r['pe'] == 21.0
    assert r['revenue_growth'] == 11.1


def test_missing_stock_returns_error(tmp_path):
    import storage
    from storage.sqlite_financial import SQLiteFinancialStore
    store = SQLiteFinancialStore(tmp_path=tmp_path)
    store.init_schema()
    storage.set_financial(store)

    from tools.get_financials import call
    r = call({'code': '000000.SH'})
    assert 'error' in r


def test_does_not_import_sqlite_directly():
    from pathlib import Path
    source = Path('tools/get_financials.py').read_text(encoding='utf-8')
    assert 'import sqlite3' not in source
