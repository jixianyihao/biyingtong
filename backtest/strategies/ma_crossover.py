"""MA Crossover strategy — buy on golden cross, sell on death cross."""
from __future__ import annotations

from datetime import date

_DEFAULT_PARAMS = {
    'fast': 10,
    'slow': 30,
    'position_pct': 0.3,   # fraction of equity to allocate per buy
}


class MACrossover:
    name: str = 'ma_crossover'

    def __init__(self, params: dict | None = None):
        self.params = {**_DEFAULT_PARAMS, **(params or {})}

    def on_day(self, date: date, close_history: dict, portfolio: dict) -> list[dict]:
        fast = int(self.params['fast'])
        slow = int(self.params['slow'])
        position_pct = float(self.params['position_pct'])

        decisions: list[dict] = []
        positions = portfolio.get('positions', {}) or {}
        equity = float(portfolio.get('equity', 0.0))

        for code, series in close_history.items():
            if len(series) < slow + 1:
                continue
            closes = [c for _, c in series]
            fast_now = sum(closes[-fast:]) / fast
            slow_now = sum(closes[-slow:]) / slow

            held = int(positions.get(code, {}).get('shares', 0))
            price = closes[-1]

            # State-based: fast > slow and flat → buy; fast < slow and held → sell.
            if fast_now > slow_now and held == 0:
                target_value = equity * position_pct
                shares = int(target_value / price // 100) * 100
                if shares > 0:
                    decisions.append({
                        'action': 'buy', 'code': code, 'shares': shares,
                        'reason': f'MA{fast}/MA{slow} golden cross',
                    })
            elif fast_now < slow_now and held > 0:
                decisions.append({
                    'action': 'sell', 'code': code, 'shares': held,
                    'reason': f'MA{fast}/MA{slow} death cross',
                })

        return decisions
