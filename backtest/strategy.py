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


_EXCHANGE_TO_VT = {
    'SH': 'SSE',
    'SZ': 'SZSE',
}


def vt_to_biyingtong(symbol: str, exchange: str) -> str:
    """'600519' + 'SSE' → '600519.SH'."""
    suffix = _EXCHANGE_TO_BIYINGTONG.get(exchange, exchange)
    return f'{symbol}.{suffix}'


def biyingtong_to_vt(code: str) -> str:
    """'600519.SH' → '600519.SSE'. Inverse of vt_to_biyingtong."""
    if '.' not in code:
        return code
    sym, _, suffix = code.partition('.')
    exch = _EXCHANGE_TO_VT.get(suffix.upper(), suffix.upper())
    return f'{sym}.{exch}'


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
        self._bought_today: dict = {}  # vt_symbol -> shares bought on current bar

    def on_init(self):
        pass

    def on_start(self):
        pass

    def on_bars(self, bars: dict):  # vnpy hook
        # Reset T+1 tracker at the start of every bar (new trading day)
        self._bought_today = {}

        day_decisions = self._process_bars(bars)
        date_str = self._extract_date(bars)
        self.daily_decisions.append((date_str, day_decisions))

        for dec in day_decisions:
            action = dec.get('action')
            code = dec.get('code')
            shares = int(dec.get('shares') or dec.get('qty') or 0)
            if not code or shares <= 0 or action not in ('buy', 'sell'):
                continue

            vt_symbol = biyingtong_to_vt(code)
            bar = bars.get(vt_symbol)
            if bar is None:
                continue
            price = float(bar.close_price)

            if action == 'buy':
                self.buy(vt_symbol, price, shares)
                self._bought_today[vt_symbol] = (
                    self._bought_today.get(vt_symbol, 0) + shares
                )
            elif action == 'sell':
                held_today = self._bought_today.get(vt_symbol, 0)
                sellable = max(0, int(self.get_pos(vt_symbol)) - held_today)
                if sellable >= shares:
                    self.sell(vt_symbol, price, shares)

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
