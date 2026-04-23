"""Factory + set + reset for BaselineResultStore."""


def test_baselines_factory_singleton():
    import storage
    storage.reset()
    assert storage.baselines() is storage.baselines()


def test_set_baselines_overrides(tmp_path):
    import storage
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    s = SQLiteBaselineResultStore(tmp_path=tmp_path)
    storage.set_baselines(s)
    assert storage.baselines() is s


def test_reset_clears_baselines(tmp_path):
    import storage
    from storage.sqlite_baselines import SQLiteBaselineResultStore
    storage.set_baselines(SQLiteBaselineResultStore(tmp_path=tmp_path))
    storage.reset()
    assert isinstance(storage.baselines(), SQLiteBaselineResultStore)
