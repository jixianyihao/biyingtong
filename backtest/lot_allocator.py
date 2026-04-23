"""Iterative A-share lot allocator — exact-fee-aware share count.

Replaces the older ``alloc * 0.995`` fee-buffer hack in baselines.
Always returns a multiple of 100 (A-share minimum lot) such that
``shares * price + fee_model.fee(buy) <= cash``. Returns 0 if even 100 shares
don't fit.
"""
from __future__ import annotations

import math

from .commission import FeeModel


_LOT = 100


def allocate_lot(*, cash: float, price: float,
                 fee_model: FeeModel) -> int:
    """Largest 100-share multiple that fits within cash + commission budget."""
    if cash <= 0 or price <= 0:
        return 0
    naive_raw = int(math.floor(cash / price))
    shares = (naive_raw // _LOT) * _LOT
    while shares >= _LOT:
        fee = fee_model.fee(side='buy', shares=shares, price=price)
        if shares * price + fee <= cash:
            return shares
        shares -= _LOT
    return 0
