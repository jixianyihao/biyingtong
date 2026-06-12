from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntradaySignalState:
    price: float
    day_low: float
    day_high: float
    vwap: float
    amplitude_pct: float
    vwap_deviation_std_pct: float = 0.0


@dataclass(frozen=True)
class T0SignalConfig:
    signal_mode: str = 'band'
    high_band: float = 0.82
    low_band: float = 0.25
    vwap_deviation_pct: float = 1.0
    vwap_zscore_threshold: float = 1.5


@dataclass(frozen=True)
class T0Signal:
    buy: bool
    sell: bool
    position: float
    vwap_deviation_pct: float
    vwap_zscore: float
    reasons: list[str]


def _mode_flags(signal_mode: str) -> tuple[bool, bool, bool]:
    mode = (signal_mode or 'band').strip().lower()
    return (
        mode in {'band', 'hybrid'},
        mode in {'vwap_deviation', 'hybrid'},
        mode in {'adaptive_vwap', 'hybrid_adaptive'},
    )


def evaluate_t0_signal(
    state: IntradaySignalState,
    config: T0SignalConfig,
) -> T0Signal:
    """Evaluate intraday T entry signals without touching portfolio state.

    This layer decides whether price location is interesting. Position sizing,
    T+1 sellability, fees, slippage, and fill simulation are deliberately owned
    by the portfolio/execution layers.
    """
    rng = state.day_high - state.day_low
    position = (state.price - state.day_low) / rng if rng > 0 else 0.5
    vwap_deviation = (
        (state.price / state.vwap - 1.0) * 100.0
        if state.vwap > 0 else 0.0
    )
    vwap_zscore = (
        vwap_deviation / state.vwap_deviation_std_pct
        if state.vwap_deviation_std_pct > 0 else 0.0
    )
    use_band_signal, use_vwap_signal, use_adaptive_vwap = _mode_flags(
        config.signal_mode,
    )

    sell = False
    buy = False
    reasons: list[str] = []
    if use_band_signal and position >= config.high_band:
        sell = True
        reasons.append('band_high')
    if use_band_signal and position <= config.low_band:
        buy = True
        reasons.append('band_low')
    if use_vwap_signal and vwap_deviation >= config.vwap_deviation_pct:
        sell = True
        reasons.append('vwap_high')
    if use_vwap_signal and vwap_deviation <= -config.vwap_deviation_pct:
        buy = True
        reasons.append('vwap_low')
    if use_adaptive_vwap and vwap_zscore >= config.vwap_zscore_threshold:
        sell = True
        reasons.append('vwap_z_high')
    if use_adaptive_vwap and vwap_zscore <= -config.vwap_zscore_threshold:
        buy = True
        reasons.append('vwap_z_low')

    return T0Signal(
        buy=buy,
        sell=sell,
        position=round(position, 4),
        vwap_deviation_pct=round(vwap_deviation, 4),
        vwap_zscore=round(vwap_zscore, 4),
        reasons=reasons,
    )
