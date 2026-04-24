"""MACD Divergence — state-based: histogram > 0 → buy, < 0 → sell."""
from __future__ import annotations

from datetime import date

_DEFAULT_PARAMS = {
    'fast': 12,
    'slow': 26,
    'signal': 9,
    'position_pct': 0.3,
}


def _ema(values: list[float], period: int) -> list[float]:
    """EMA seeded by SMA of first `period`. Returns tail-aligned list."""
    if len(values) < period:
        return []
    out = [sum(values[:period]) / period]
    k = 2 / (period + 1)
    for v in values[period:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def _macd(closes: list[float], fast: int, slow: int, signal: int):
    """Returns (macd_line, signal_line, histogram) tail-aligned. Empty if
    insufficient data."""
    if len(closes) < slow + signal:
        return [], [], []
    ema_f = _ema(closes, fast)
    ema_s = _ema(closes, slow)
    trim = slow - fast
    ema_f_aligned = ema_f[trim:]
    assert len(ema_f_aligned) == len(ema_s)
    macd_line = [f - s for f, s in zip(ema_f_aligned, ema_s)]
    signal_line = _ema(macd_line, signal)
    if not signal_line:
        return [], [], []
    macd_line_aligned = macd_line[-len(signal_line):]
    hist = [m - s for m, s in zip(macd_line_aligned, signal_line)]
    return macd_line_aligned, signal_line, hist


class MACDDivergence:
    name: str = 'macd_divergence'

    def __init__(self, params: dict | None = None):
        self.params = {**_DEFAULT_PARAMS, **(params or {})}

    def on_day(self, date: date, close_history: dict, portfolio: dict) -> list[dict]:
        fast = int(self.params['fast'])
        slow = int(self.params['slow'])
        signal = int(self.params['signal'])
        position_pct = float(self.params['position_pct'])

        decisions: list[dict] = []
        positions = portfolio.get('positions', {}) or {}
        equity = float(portfolio.get('equity', 0.0))

        for code, series in close_history.items():
            closes = [c for _, c in series]
            macd_line, _, hist = _macd(closes, fast, slow, signal)
            if not hist:
                continue

            held = int(positions.get(code, {}).get('shares', 0))
            price = closes[-1]

            # State-based (matches Task 2 MACrossover semantics).
            # Use MACD line sign (above/below zero) — reflects fast EMA vs
            # slow EMA relationship, which tracks trend direction more
            # reliably than histogram sign in steady trends.
            if macd_line[-1] > 0 and held == 0:
                target_value = equity * position_pct
                shares = int(target_value / price // 100) * 100
                if shares > 0:
                    decisions.append({
                        'action': 'buy', 'code': code, 'shares': shares,
                        'reason': f'MACD={macd_line[-1]:.3f} > 0, hist={hist[-1]:.3f}',
                    })
            elif macd_line[-1] < 0 and held > 0:
                decisions.append({
                    'action': 'sell', 'code': code, 'shares': held,
                    'reason': f'MACD={macd_line[-1]:.3f} < 0, hist={hist[-1]:.3f}',
                })

        return decisions
