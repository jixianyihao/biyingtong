"""Protocols + factory singleton pattern for storage/."""
from datetime import date, datetime
from typing import Protocol


def test_model_info_dataclass():
    from storage.base import ModelInfo
    m = ModelInfo(
        id='claude-opus-4-7', provider='anthropic',
        display_name='Claude Opus 4.7', api_model_id='claude-opus-4-7',
        training_cutoff='2026-01-31',
        supports_tool_use=True, max_tokens_out=4096, enabled=True,
    )
    assert m.training_cutoff == '2026-01-31'


def test_protocols_defined():
    from storage.base import KlineStore, FinancialStore, ModelStore, CalendarStore
    assert isinstance(KlineStore, type(Protocol))
    assert isinstance(FinancialStore, type(Protocol))
    assert isinstance(ModelStore, type(Protocol))
    assert isinstance(CalendarStore, type(Protocol))


def test_factories_return_same_singleton():
    import storage
    storage.reset()

    class FakeKline:
        def save_bars(self, bars): return 0
        def get_recent(self, code, period, count): return []
        def load_range(self, code, period, start, end): return []
        def get_closes(self, code, count): return []
        def distinct_dates(self, start, end): return []

    fake = FakeKline()
    storage.set_kline(fake)
    assert storage.kline() is fake
    assert storage.kline() is storage.kline()


def test_reset_clears_all_singletons():
    import storage
    storage.reset()

    class Noop:
        def save_bars(self, bars): return 0
        def get_recent(self, *a, **kw): return []
        def load_range(self, *a, **kw): return []
        def get_closes(self, *a, **kw): return []
        def distinct_dates(self, *a, **kw): return []

    n = Noop()
    storage.set_kline(n)
    storage.reset()

    assert storage.kline() is not n


def test_default_factories_return_sqlite_impls():
    """After reset, calling storage.kline() etc. builds the SQLite default."""
    import storage
    storage.reset()

    from storage.sqlite_kline import SQLiteKlineStore
    assert isinstance(storage.kline(), SQLiteKlineStore)


def test_protocols_are_runtime_checkable():
    from storage.base import KlineStore

    class Compliant:
        def save_bars(self, bars): return 0
        def get_recent(self, code, period, count): return []
        def load_range(self, code, period, start, end): return []
        def get_closes(self, code, count): return []
        def distinct_dates(self, start, end): return []

    assert isinstance(Compliant(), KlineStore)
