"""Strategy rating (Spec §9) — 5 sub-scores + weighted overall + letter."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StrategyRating:
    """5 sub-scores + weighted overall + letter grade."""
    return_power: float          # ① 收益能力
    risk_control: float          # ② 风险控制
    stability: float             # ③ 稳定性
    trading_efficiency: float    # ④ 交易效率
    overfitting_risk: float      # ⑤ 过拟合风险 (HIGHER = LESS leakage = BETTER)
    overall: float
    letter: str                  # A+ / A / B / C / D
    notes: tuple = field(default_factory=tuple)  # approximations used


_WEIGHTS = {
    'return_power': 0.30,
    'risk_control': 0.30,
    'stability': 0.15,
    'trading_efficiency': 0.15,
    'overfitting_risk': 0.10,
}

_MIN_ZONE_DAYS = 10


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _grade(overall: float) -> str:
    if overall >= 90: return 'A+'
    if overall >= 80: return 'A'
    if overall >= 70: return 'B'
    if overall >= 60: return 'C'
    return 'D'


def compute_strategy_rating(result) -> StrategyRating:
    """Compute from a BacktestResult (or dict with same shape)."""
    # Normalise result into dict-like accessors (supports dataclass or dict)
    stats = result.stats if hasattr(result, 'stats') else result['stats']
    zone_stats = result.zone_stats if hasattr(result, 'zone_stats') else result['zone_stats']
    if hasattr(stats, 'sharpe'):
        s = stats
        sharpe = s.sharpe
        mdd = s.max_drawdown_pct
        max_daily_loss = s.max_daily_loss_pct
        trade_count = s.trade_count
        total_return = s.total_return_pct
    else:
        sharpe = stats['sharpe']
        mdd = stats['max_drawdown_pct']
        max_daily_loss = stats['max_daily_loss_pct']
        trade_count = stats['trade_count']
        total_return = stats['total_return_pct']

    by_zone = {}
    for z in zone_stats:
        zd = {'zone': z.zone, 'days': z.days, 'stats': z.stats} if hasattr(z, 'zone') else z
        by_zone[zd['zone']] = zd

    notes: list[str] = []

    # ① Return power: prefer clean_zone_sharpe, fall back to overall
    clean = by_zone.get('clean')
    if clean and clean['days'] >= _MIN_ZONE_DAYS and clean['stats']:
        clean_sharpe = float(clean['stats'].get('sharpe', sharpe))
    else:
        clean_sharpe = sharpe
        notes.append('return_power 用全期 sharpe (无足够 clean 区数据)')
    return_power = _clamp(clean_sharpe / 2.5 * 100)

    # ② Risk control
    mdd_score = 100 * max(0.0, 1 - abs(mdd) / 30)
    daily_score = 100 * max(0.0, 1 - abs(max_daily_loss) / 10)
    risk_control = _clamp(0.6 * mdd_score + 0.4 * daily_score)

    # ③ Stability — MVP proxy
    stability = _clamp(100 - abs(mdd) * 2)
    notes.append('stability 用 MDD 近似 (月收益数据未持久化)')

    # ④ Trading efficiency
    if trade_count < 5:
        trading_efficiency = 0.0
        notes.append('trading_efficiency = 0 (trade_count < 5)')
    else:
        avg = total_return / trade_count
        cost_ratio = 0.0
        trading_efficiency = _clamp(50 + avg * 5 - cost_ratio * 100)
        notes.append('trading_efficiency 不含手续费 drag (total_fees 未持久化)')

    # ⑤ Overfitting risk
    pollution = by_zone.get('pollution')
    if (clean and pollution
            and clean['days'] >= _MIN_ZONE_DAYS
            and pollution['days'] >= _MIN_ZONE_DAYS
            and clean['stats'] and pollution['stats']):
        p_sharpe = float(pollution['stats'].get('sharpe', 0.0))
        c_sharpe = float(clean['stats'].get('sharpe', 0.0))
        divergence = abs(p_sharpe - c_sharpe)
        overfitting_risk = _clamp(100 * max(0.0, 1 - divergence / 2.0))
    else:
        overfitting_risk = 50.0
        notes.append('overfitting_risk = 50 中性分 (分区数据不足)')

    overall = (
        _WEIGHTS['return_power'] * return_power
        + _WEIGHTS['risk_control'] * risk_control
        + _WEIGHTS['stability'] * stability
        + _WEIGHTS['trading_efficiency'] * trading_efficiency
        + _WEIGHTS['overfitting_risk'] * overfitting_risk
    )
    return StrategyRating(
        return_power=round(return_power, 1),
        risk_control=round(risk_control, 1),
        stability=round(stability, 1),
        trading_efficiency=round(trading_efficiency, 1),
        overfitting_risk=round(overfitting_risk, 1),
        overall=round(overall, 1),
        letter=_grade(overall),
        notes=tuple(notes),
    )
