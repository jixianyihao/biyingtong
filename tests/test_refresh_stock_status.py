"""Daily stock_status refresh pulls from TDX snapshot and upserts."""


def test_parse_st_from_name():
    from scripts.setup.refresh_stock_status import _is_st_name
    assert _is_st_name('*ST 经纬') is True
    assert _is_st_name('ST 金贵') is True
    assert _is_st_name('S*ST 金泰') is True
    assert _is_st_name('贵州茅台') is False
    assert _is_st_name('') is False
    assert _is_st_name(None) is False


def test_refresh_upserts_via_store(tmp_path, monkeypatch):
    """Verify the end-to-end flow with a mocked TDX snapshot."""
    import storage
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    s = SQLiteStockStatusStore(tmp_path=tmp_path)
    s.init_schema()
    storage.set_stock_status(s)

    fake_codes = ['600519.SH', '000666.SZ', '000001.SZ']
    fake_snapshot = {
        '600519.SH': {'name': '贵州茅台', 'suspended': False},
        '000666.SZ': {'name': '*ST 经纬', 'suspended': False},
        '000001.SZ': {'name': '平安银行', 'suspended': True},
    }

    from scripts.setup import refresh_stock_status as mod
    monkeypatch.setattr(mod, '_load_pool_codes', lambda: fake_codes)
    monkeypatch.setattr(mod, '_fetch_snapshot', lambda codes: fake_snapshot)

    n = mod.run()
    assert n == 3
    assert s.is_st('600519.SH') is False
    assert s.is_st('000666.SZ') is True
    assert s.is_suspended('000001.SZ') is True
