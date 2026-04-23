"""LLMPortfolioStrategy — vnpy_portfoliostrategy subclass driven by AgentRunner.

The integration with vnpy's engine (order submission, position tracking) is
delegated to the parent StrategyTemplate; this class only bridges bars →
AgentRunner → decisions → vnpy orders.
"""
from __future__ import annotations


_EXCHANGE_TO_BIYINGTONG = {
    'SSE': 'SH',
    'SZSE': 'SZ',
}


def vt_to_biyingtong(symbol: str, exchange: str) -> str:
    """'600519' + 'SSE' → '600519.SH'."""
    suffix = _EXCHANGE_TO_BIYINGTONG.get(exchange, exchange)
    return f'{symbol}.{suffix}'


try:
    from vnpy_portfoliostrategy import StrategyTemplate as _BaseStrategy
except Exception:  # vnpy not importable in isolated test contexts
    class _BaseStrategy:  # type: ignore
        pass


class LLMPortfolioStrategy(_BaseStrategy):
    """vnpy_portfoliostrategy template driven by AgentRunner."""

    agent_id: str = ''

    def __init__(self, strategy_engine, strategy_name, vt_symbols, setting):
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        from agents.runner import AgentRunner
        self._runner = AgentRunner(llm=setting.get('llm'))
        self._agent_id = setting.get('agent_id') or self.agent_id
        self._cash = float(setting.get('initial_capital', 1_000_000.0))
        self._positions: dict = {}
        self.daily_decisions: list = []

    def on_init(self):
        pass

    def on_start(self):
        pass

    def on_bars(self, bars: dict):  # vnpy hook
        day_decisions = self._process_bars(bars)
        self.daily_decisions.append((self._extract_date(bars), day_decisions))

    def _extract_date(self, bars: dict) -> str:
        for bar in bars.values():
            return bar.datetime.strftime('%Y-%m-%d')
        return ''

    def _process_bars(self, bars: dict) -> list:
        date = self._extract_date(bars)
        mark_prices = {}
        for vt_symbol, bar in bars.items():
            symbol, _, exchange = vt_symbol.partition('.')
            exch_val = getattr(bar.exchange, 'value', exchange)
            code = vt_to_biyingtong(bar.symbol, exch_val)
            mark_prices[code] = float(bar.close_price)

        from backtest.portfolio_adapter import build_portfolio
        portfolio = build_portfolio(
            cash=self._cash, positions=self._positions,
            mark_prices=mark_prices,
        )
        return self._runner.run_day(
            agent_id=self._agent_id,
            date=date,
            portfolio=portfolio,
            market_context={},
            mark_prices=mark_prices,
        )
