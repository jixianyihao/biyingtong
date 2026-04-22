"""P0 follow-up: load_financial uses tq.get_financial_data (FN fields) via storage.financial()."""


def test_load_financial_populates_growth_columns(tdx_ready, tmp_path, monkeypatch):
    import storage
    from storage.sqlite_financial import SQLiteFinancialStore
    store = SQLiteFinancialStore(tmp_path=tmp_path)
    store.init_schema()
    storage.set_financial(store)

    from scripts.setup import load_financial as lf
    symbols = ['600519', '000858', '600036']
    written = lf.load_financial(symbols)
    assert written >= 2, f'expected ≥2/3 stocks written, got {written}'

    import sqlite3
    con = sqlite3.connect(tmp_path / 'financial_cache.db')
    try:
        rows = con.execute(
            'SELECT stock_code, pe, pb, roe, revenue_growth, net_profit_growth '
            'FROM financial_data WHERE revenue_growth IS NOT NULL'
        ).fetchall()
    finally:
        con.close()

    assert len(rows) >= 2, (
        'expected ≥2 rows with non-null revenue_growth. '
        'Ensure TDX client has 专业财务 data downloaded.'
    )
    for code, pe, pb, roe, rg, npg in rows:
        assert rg is None or -200 <= rg <= 1000
        assert npg is None or -500 <= npg <= 2000


def test_load_financial_does_not_import_sqlite_directly():
    """Structural: must use storage.financial()."""
    from pathlib import Path
    source = Path('scripts/setup/load_financial.py').read_text(encoding='utf-8')
    assert 'import sqlite3' not in source, (
        'load_financial.py must not import sqlite3 directly; use storage.financial()'
    )
    assert 'from storage import' in source or 'import storage' in source
