"""Daily record list → BacktestStats + per-zone ZoneStats."""
from __future__ import annotations

import math
from collections import defaultdict

from .base import BacktestStats, ZoneStats
from .cutoff import classify_date


def _sharpe(pnls: list[float]) -> float:
    if len(pnls) < 2:
        return 0.0
    mean = sum(pnls) / len(pnls)
    var = sum((x - mean) ** 2 for x in pnls) / (len(pnls) - 1)
    std = math.sqrt(var)
    if std == 0:
        return 0.0
    return (mean / std) * math.sqrt(252)


def _max_drawdown_pct(equities: list[float]) -> float:
    if not equities:
        return 0.0
    peak = equities[0]
    max_dd = 0.0
    for e in equities:
        if e > peak:
            peak = e
        dd = (e - peak) / peak * 100.0 if peak else 0.0
        if dd < max_dd:
            max_dd = dd
    return max_dd


def _stats_from_days(days: list, initial_capital: float) -> BacktestStats:
    if not days:
        return BacktestStats(
            sharpe=0.0, max_drawdown_pct=0.0, trade_count=0,
            win_rate=0.0, max_daily_loss_pct=0.0,
            total_return_pct=0.0, final_equity=initial_capital,
        )
    pnls = [d['pnl_pct'] for d in days]
    equities = [d['equity'] for d in days]
    trade_count = sum(d.get('trade_count', 0) for d in days)
    won = sum(d.get('won', 0) for d in days)
    final_equity = equities[-1]
    total_return_pct = (final_equity - initial_capital) / initial_capital * 100.0

    return BacktestStats(
        sharpe=_sharpe(pnls),
        max_drawdown_pct=_max_drawdown_pct(equities),
        trade_count=trade_count,
        win_rate=(won / trade_count * 100.0) if trade_count else 0.0,
        max_daily_loss_pct=min(pnls) if pnls else 0.0,
        total_return_pct=total_return_pct,
        final_equity=final_equity,
    )


def aggregate(days: list, cutoff: str, initial_capital: float):
    """Return (overall_stats, [ZoneStats, ...])."""
    overall = _stats_from_days(days, initial_capital)

    by_zone = defaultdict(list)
    for d in days:
        zone = classify_date(d['date'], cutoff)
        by_zone[zone].append(d)

    zones = []
    for name in ('pollution', 'buffer', 'clean'):
        zd = by_zone.get(name, [])
        if len(zd) < 2:
            zones.append(ZoneStats(zone=name, days=len(zd), stats={}))
            continue
        zone_stats = _stats_from_days(zd, initial_capital)
        zones.append(ZoneStats(
            zone=name, days=len(zd),
            stats={
                'sharpe': zone_stats.sharpe,
                'max_drawdown_pct': zone_stats.max_drawdown_pct,
                'trade_count': zone_stats.trade_count,
                'win_rate': zone_stats.win_rate,
                'max_daily_loss_pct': zone_stats.max_daily_loss_pct,
                'total_return_pct': zone_stats.total_return_pct,
                'final_equity': zone_stats.final_equity,
            },
        ))
    return overall, zones
