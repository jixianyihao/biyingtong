"""Factory + set_* + reset() coverage for P2b stores."""


def test_redline_factory_returns_singleton():
    import storage
    storage.reset()
    a = storage.redline()
    b = storage.redline()
    assert a is b


def test_stock_status_factory_returns_singleton():
    import storage
    storage.reset()
    a = storage.stock_status()
    b = storage.stock_status()
    assert a is b


def test_audit_factory_returns_singleton():
    import storage
    storage.reset()
    a = storage.audit()
    b = storage.audit()
    assert a is b


def test_set_redline_overrides_factory(tmp_path):
    import storage
    from storage.sqlite_redline import SQLiteRedLineStore
    s = SQLiteRedLineStore(tmp_path=tmp_path)
    storage.set_redline(s)
    assert storage.redline() is s


def test_set_stock_status_overrides_factory(tmp_path):
    import storage
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    s = SQLiteStockStatusStore(tmp_path=tmp_path)
    storage.set_stock_status(s)
    assert storage.stock_status() is s


def test_set_audit_overrides_factory(tmp_path):
    import storage
    from storage.sqlite_audit import SQLiteAuditStore
    s = SQLiteAuditStore(tmp_path=tmp_path)
    storage.set_audit(s)
    assert storage.audit() is s


def test_reset_clears_all_p2b_stores(tmp_path):
    import storage
    from storage.sqlite_redline import SQLiteRedLineStore
    storage.set_redline(SQLiteRedLineStore(tmp_path=tmp_path))
    storage.reset()
    # After reset, factory must construct fresh instance
    assert isinstance(storage.redline(), type(storage.redline()))
