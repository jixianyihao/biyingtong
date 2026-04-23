"""Book — cash + tranched positions with T+1 + commission.

A-share T+1: shares bought on day D may only be sold on day D+1 or later.
Each buy creates a Tranche with its own buy_date; sells FIFO-consume tranches
where `buy_date < today`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .commission import FeeModel


@dataclass
class Tranche:
    shares: int
    price: float        # entry price
    buy_date: date


@dataclass
class Fill:
    code: str
    side: str           # 'buy' | 'sell'
    shares: int
    price: float
    fee: float
    date: date


@dataclass
class Book:
    cash: float
    fee_model: FeeModel
    _tranches: dict = field(default_factory=dict)  # code -> list[Tranche]
    total_fees: float = 0.0
    fills: list = field(default_factory=list)  # list[Fill] — observability log

    def execute_buy(self, code: str, *, shares: int, price: float,
                    d: date) -> Fill | None:
        if shares <= 0 or price <= 0:
            return None
        notional = shares * price
        fee = round(self.fee_model.fee(side='buy', shares=shares, price=price), 4)
        total_cost = notional + fee
        if total_cost > self.cash:
            return None
        self.cash -= total_cost
        self.total_fees += fee
        self._tranches.setdefault(code, []).append(
            Tranche(shares=shares, price=price, buy_date=d)
        )
        fill = Fill(code=code, side='buy', shares=shares, price=price,
                    fee=fee, date=d)
        self.fills.append(fill)
        return fill

    def execute_sell(self, code: str, *, shares: int, price: float,
                     d: date) -> Fill | None:
        if shares <= 0 or price <= 0:
            return None
        tranches = self._tranches.get(code, [])
        # Only tranches bought strictly before today are sellable (T+1)
        sellable = [t for t in tranches if t.buy_date < d]
        available = sum(t.shares for t in sellable)
        if available <= 0:
            return None
        to_sell = min(shares, available)
        # FIFO-consume from oldest sellable tranche
        remaining = to_sell
        for t in sellable:
            if remaining <= 0:
                break
            take = min(t.shares, remaining)
            t.shares -= take
            remaining -= take
        # Purge zero-share tranches, preserve non-sellable (same-day) ones
        self._tranches[code] = [t for t in tranches if t.shares > 0]
        if not self._tranches[code]:
            del self._tranches[code]

        notional = to_sell * price
        fee = round(self.fee_model.fee(side='sell', shares=to_sell, price=price), 4)
        proceeds = notional - fee
        self.cash += proceeds
        self.total_fees += fee
        fill = Fill(code=code, side='sell', shares=to_sell, price=price,
                    fee=fee, date=d)
        self.fills.append(fill)
        return fill

    def positions_view(self) -> dict:
        """Aggregated per-code: shares + cost-weighted avg_price.

        Excludes codes with zero total shares.
        """
        out: dict = {}
        for code, tranches in self._tranches.items():
            total_shares = sum(t.shares for t in tranches)
            if total_shares <= 0:
                continue
            total_cost = sum(t.shares * t.price for t in tranches)
            out[code] = {
                'shares': total_shares,
                'avg_price': total_cost / total_shares,
            }
        return out

    def equity(self, mark_prices: dict) -> float:
        eq = self.cash
        for code, info in self.positions_view().items():
            mark = mark_prices.get(code, info['avg_price'])
            eq += info['shares'] * mark
        return eq
