from __future__ import annotations

from dataclasses import dataclass

from .backtest import _exec_price, _fee


@dataclass(frozen=True)
class T0FillConfig:
    fee_bps: float = 2.5
    sell_tax_bps: float = 5.0
    slippage_bps: float = 2.0


@dataclass(frozen=True)
class T0Leg:
    side: str
    price: float
    shares: int
    cash_open: float


@dataclass(frozen=True)
class T0Fill:
    leg: T0Leg | None
    cash_delta: float
    pnl: float
    trade: dict


class MarketFillSimulator:
    """Marketable fill model for current T0 backtests.

    This preserves the existing portfolio semantics: a buy pays positive
    slippage, a sell receives negative slippage, and sell tax only applies on
    sells. More realistic limit/VWAP/POV fill simulators can implement the
    same open/close contract later.
    """

    def __init__(self, config: T0FillConfig | None = None):
        self.config = config or T0FillConfig()

    def _fee(self, price: float, shares: int, *, is_sell: bool) -> float:
        return _fee(
            price,
            shares,
            fee_bps=self.config.fee_bps,
            sell_tax_bps=self.config.sell_tax_bps,
            is_sell=is_sell,
        )

    def _exec_price(self, price: float, *, is_buy: bool) -> float:
        return _exec_price(
            price,
            is_buy=is_buy,
            slippage_bps=self.config.slippage_bps,
        )

    def open_leg(self, side: str, *, price: float, shares: int, ts: str) -> T0Fill:
        if side == 'sell_first':
            exec_price = self._exec_price(price, is_buy=False)
            fee = self._fee(exec_price, shares, is_sell=True)
            cash_delta = exec_price * shares - fee
            return T0Fill(
                leg=T0Leg(
                    side='sell_first',
                    price=exec_price,
                    shares=shares,
                    cash_open=cash_delta,
                ),
                cash_delta=cash_delta,
                pnl=0.0,
                trade={
                    'ts': ts, 'action': 'sell_t',
                    'shares': shares, 'price': round(exec_price, 4),
                    'fee': round(fee, 4),
                },
            )
        if side == 'buy_first':
            exec_price = self._exec_price(price, is_buy=True)
            fee = self._fee(exec_price, shares, is_sell=False)
            cash_delta = -(exec_price * shares + fee)
            return T0Fill(
                leg=T0Leg(
                    side='buy_first',
                    price=exec_price,
                    shares=shares,
                    cash_open=cash_delta,
                ),
                cash_delta=cash_delta,
                pnl=0.0,
                trade={
                    'ts': ts, 'action': 'buy_t',
                    'shares': shares, 'price': round(exec_price, 4),
                    'fee': round(fee, 4),
                },
            )
        raise ValueError(f'unknown T0 leg side={side!r}')

    def close_leg(
        self,
        leg: T0Leg,
        *,
        price: float,
        ts: str,
        reason: str,
    ) -> T0Fill:
        if leg.side == 'sell_first':
            exec_price = self._exec_price(price, is_buy=True)
            fee = self._fee(exec_price, leg.shares, is_sell=False)
            cash_delta = -(exec_price * leg.shares + fee)
            action = 'buy_back'
        elif leg.side == 'buy_first':
            exec_price = self._exec_price(price, is_buy=False)
            fee = self._fee(exec_price, leg.shares, is_sell=True)
            cash_delta = exec_price * leg.shares - fee
            action = 'sell_back'
        else:
            raise ValueError(f'unknown T0 leg side={leg.side!r}')
        pnl = leg.cash_open + cash_delta
        return T0Fill(
            leg=None,
            cash_delta=cash_delta,
            pnl=pnl,
            trade={
                'ts': ts,
                'action': action,
                'shares': leg.shares,
                'price': round(exec_price, 4),
                'fee': round(fee, 4),
                'pnl': round(pnl, 4),
                'reason': reason,
            },
        )
