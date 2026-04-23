"""Factory + set_* + reset coverage for P2c stores."""


def test_backtests_factory_singleton():
    import storage
    storage.reset()
    a = storage.backtests()
    assert storage.backtests() is a


def test_llm_cache_factory_singleton():
    import storage
    storage.reset()
    a = storage.llm_cache()
    assert storage.llm_cache() is a


def test_set_backtests_overrides(tmp_path):
    import storage
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    s = SQLiteBacktestResultStore(tmp_path=tmp_path)
    storage.set_backtests(s)
    assert storage.backtests() is s


def test_set_llm_cache_overrides(tmp_path):
    import storage
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    s = SQLiteLLMDecisionCache(tmp_path=tmp_path)
    storage.set_llm_cache(s)
    assert storage.llm_cache() is s


def test_reset_clears_p2c_stores(tmp_path):
    import storage
    from storage.sqlite_backtests import SQLiteBacktestResultStore
    storage.set_backtests(SQLiteBacktestResultStore(tmp_path=tmp_path))
    storage.reset()
    import storage as s2
    assert isinstance(s2.backtests(), SQLiteBacktestResultStore)
