"""LLMPortfolioStrategy bar→decision→order translation."""
from datetime import datetime


class _StubBar:
    def __init__(self, symbol, close, exchange='SSE',
                 dt=datetime(2024, 3, 15)):
        self.symbol = symbol
        self.close_price = close
        self.datetime = dt
        class _Exch:
            value = exchange
        self.exchange = _Exch()


def test_process_bars_calls_runner_with_mark_prices():
    from backtest.strategy import LLMPortfolioStrategy

    class FakeRunner:
        def __init__(self):
            self.calls = []

        def run_day(self, **kwargs):
            self.calls.append(kwargs)
            return []

    runner = FakeRunner()
    s = LLMPortfolioStrategy.__new__(LLMPortfolioStrategy)
    s._runner = runner
    s._agent_id = 'a1'
    s._cash = 1_000_000.0
    s._positions = {}
    s.vt_symbols = ['600519.SSE']

    bars = {'600519.SSE': _StubBar('600519', 1600.0)}
    decisions = s._process_bars(bars)
    assert decisions == []
    assert len(runner.calls) == 1
    call = runner.calls[0]
    assert call['date'] == '2024-03-15'
    assert call['mark_prices']['600519.SH'] == 1600.0


def test_process_bars_converts_decisions_to_orders():
    from backtest.strategy import LLMPortfolioStrategy

    class FakeRunner:
        def run_day(self, **kwargs):
            return [{'action': 'buy', 'code': '600519.SH',
                     'shares': 100, 'price': 1600.0,
                     'reason': 'solid fundamentals and good value',
                     'thinking': 'analysis'}]

    s = LLMPortfolioStrategy.__new__(LLMPortfolioStrategy)
    s._runner = FakeRunner()
    s._agent_id = 'a1'
    s._cash = 1_000_000.0
    s._positions = {}
    s.vt_symbols = ['600519.SSE']

    bars = {'600519.SSE': _StubBar('600519', 1600.0)}
    decisions = s._process_bars(bars)
    assert len(decisions) == 1
    assert decisions[0]['action'] == 'buy'


def test_vt_to_biyingtong_code_mapping():
    from backtest.strategy import vt_to_biyingtong
    assert vt_to_biyingtong('600519', 'SSE') == '600519.SH'
    assert vt_to_biyingtong('000858', 'SZSE') == '000858.SZ'
