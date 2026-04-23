"""Build the ValidationEngine portfolio dict from engine state + mark prices."""
from __future__ import annotations


def build_portfolio(cash: float, positions: dict,
                    mark_prices: dict) -> dict:
    """Return {equity, cash, positions} suitable for ValidationEngine."""
    clean_positions: dict[str, dict] = {}
    equity = float(cash)
    for code, info in (positions or {}).items():
        shares = int(info.get('shares', 0) or 0)
        if shares <= 0:
            continue
        avg_price = float(info.get('avg_price', 0.0))
        mark = float(mark_prices.get(code, avg_price))
        equity += shares * mark
        clean_positions[code] = {
            'shares': shares,
            'avg_price': avg_price,
        }
    return {
        'cash': float(cash),
        'equity': equity,
        'positions': clean_positions,
    }
