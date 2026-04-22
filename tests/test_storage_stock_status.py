"""SQLiteStockStatusStore — per-code tradability flags."""


def test_missing_code_is_st_returns_false(tmp_path):
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    s = SQLiteStockStatusStore(tmp_path=tmp_path)
    s.init_schema()
    assert s.is_st('600519.SH') is False
    assert s.is_suspended('600519.SH') is False
    assert s.get('600519.SH') is None


def test_upsert_then_get(tmp_path):
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.base import StockStatusRow
    s = SQLiteStockStatusStore(tmp_path=tmp_path)
    s.init_schema()
    s.upsert(StockStatusRow(
        code='000001.SZ', name='平安银行',
        is_st=False, is_suspended=False, is_delisted=False,
        listing_date='1991-04-03',
    ))
    row = s.get('000001.SZ')
    assert row is not None
    assert row.name == '平安银行'
    assert row.is_st is False


def test_upsert_replaces_existing(tmp_path):
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.base import StockStatusRow
    s = SQLiteStockStatusStore(tmp_path=tmp_path)
    s.init_schema()
    s.upsert(StockStatusRow(code='X.SH', name='X', is_st=False,
                            is_suspended=False, is_delisted=False))
    s.upsert(StockStatusRow(code='X.SH', name='*ST X', is_st=True,
                            is_suspended=False, is_delisted=False))
    assert s.is_st('X.SH') is True
    assert s.get('X.SH').name == '*ST X'


def test_bulk_upsert_returns_count(tmp_path):
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.base import StockStatusRow
    s = SQLiteStockStatusStore(tmp_path=tmp_path)
    s.init_schema()
    n = s.bulk_upsert([
        StockStatusRow(code=f'{i:06d}.SH', name=f'n{i}', is_st=False,
                       is_suspended=False, is_delisted=False)
        for i in range(10)
    ])
    assert n == 10


def test_suspended_flag(tmp_path):
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.base import StockStatusRow
    s = SQLiteStockStatusStore(tmp_path=tmp_path)
    s.init_schema()
    s.upsert(StockStatusRow(code='Y.SZ', name='Y', is_st=False,
                            is_suspended=True, is_delisted=False))
    assert s.is_suspended('Y.SZ') is True
    assert s.is_st('Y.SZ') is False
