"""RSI Breakout — oversold → buy, overbought → sell (Wilder's smoothing)."""
from __future__ import annotations

from datetime import date

_DEFAULT_PARAMS = {
    'period': 14,
    'oversold': 30.0,
    'overbought': 70.0,
    'position_pct': 0.3,
}


def _rsi(closes: list[float], period: int) -> float:
    """Wilder's RSI over closes. Returns 50.0 if insufficient data."""
    if len(closes) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        gains.append(max(0.0, diff))
        losses.append(max(0.0, -diff))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gain = max(0.0, diff)
        loss = max(0.0, -diff)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


class RSIBreakout:
    name: str = 'rsi_breakout'

    def __init__(self, params: dict | None = None):
        self.params = {**_DEFAULT_PARAMS, **(params or {})}

    def on_day(self, date: date, close_history: dict, portfolio: dict) -> list[dict]:
        period = int(self.params['period'])
        oversold = float(self.params['oversold'])
        overbought = float(self.params['overbought'])
        position_pct = float(self.params['position_pct'])

        decisions: list[dict] = []
        positions = portfolio.get('positions', {}) or {}
        equity = float(portfolio.get('equity', 0.0))

        for code, series in close_history.items():
            if len(series) < period + 1:
                continue
            closes = [c for _, c in series]
            rsi = _rsi(closes, period)
            held = int(positions.get(code, {}).get('shares', 0))
            price = closes[-1]

            if rsi <= oversold and held == 0:
                target_value = equity * position_pct
                shares = int(target_value / price // 100) * 100
                if shares > 0:
                    decisions.append({
                        'action': 'buy', 'code': code, 'shares': shares,
                        'reason': f'RSI({period})={rsi:.1f} ≤ {oversold}',
                    })
            elif rsi >= overbought and held > 0:
                decisions.append({
                    'action': 'sell', 'code': code, 'shares': held,
                    'reason': f'RSI({period})={rsi:.1f} ≥ {overbought}',
                })

        return decisions
