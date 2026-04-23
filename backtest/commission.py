"""A-share commission + stamp duty model."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeeModel:
    """Fee expressed as basis points (1 bp = 0.01%).

    A-share MVP defaults: 3 bp buy (brokerage only), 13 bp sell
    (3 bp brokerage + 10 bp stamp duty).
    """
    buy_bps: float = 3.0
    sell_bps: float = 13.0

    def fee(self, *, side: str, shares: int, price: float) -> float:
        if side == 'buy':
            bps = self.buy_bps
        elif side == 'sell':
            bps = self.sell_bps
        else:
            raise ValueError(f'unknown side: {side!r}')
        if shares <= 0 or price <= 0:
            return 0.0
        notional = shares * price
        return notional * (bps / 10_000.0)
