from __future__ import annotations

from t0.signals import IntradaySignalState, T0SignalConfig, evaluate_t0_signal


def test_band_signal_uses_intraday_position_only():
    state = IntradaySignalState(
        price=108.0,
        day_low=100.0,
        day_high=110.0,
        vwap=107.5,
        amplitude_pct=10.0,
    )

    signal = evaluate_t0_signal(
        state,
        T0SignalConfig(
            signal_mode='band',
            high_band=0.75,
            low_band=0.20,
            vwap_deviation_pct=99.0,
        ),
    )

    assert signal.sell is True
    assert signal.buy is False
    assert signal.position == 0.8
    assert signal.vwap_deviation_pct == 0.4651
    assert signal.reasons == ['band_high']


def test_vwap_deviation_signal_ignores_band_thresholds():
    state = IntradaySignalState(
        price=98.0,
        day_low=95.0,
        day_high=105.0,
        vwap=100.0,
        amplitude_pct=10.0,
    )

    signal = evaluate_t0_signal(
        state,
        T0SignalConfig(
            signal_mode='vwap_deviation',
            high_band=0.01,
            low_band=0.01,
            vwap_deviation_pct=1.0,
        ),
    )

    assert signal.sell is False
    assert signal.buy is True
    assert signal.position == 0.3
    assert signal.vwap_deviation_pct == -2.0
    assert signal.reasons == ['vwap_low']


def test_hybrid_signal_triggers_when_either_family_matches():
    state = IntradaySignalState(
        price=103.0,
        day_low=100.0,
        day_high=104.0,
        vwap=101.0,
        amplitude_pct=4.0,
    )

    signal = evaluate_t0_signal(
        state,
        T0SignalConfig(
            signal_mode='hybrid',
            high_band=0.90,
            low_band=0.05,
            vwap_deviation_pct=1.5,
        ),
    )

    assert signal.sell is True
    assert signal.buy is False
    assert signal.position == 0.75
    assert signal.vwap_deviation_pct == 1.9802
    assert signal.reasons == ['vwap_high']


def test_adaptive_vwap_signal_uses_deviation_zscore_not_fixed_percent():
    state = IntradaySignalState(
        price=100.8,
        day_low=99.0,
        day_high=101.0,
        vwap=100.0,
        amplitude_pct=2.0,
        vwap_deviation_std_pct=0.4,
    )

    signal = evaluate_t0_signal(
        state,
        T0SignalConfig(
            signal_mode='adaptive_vwap',
            # Static threshold is intentionally unreachable; adaptive mode
            # should trigger from z-score: 0.8 / 0.4 = 2.0.
            vwap_deviation_pct=99.0,
            vwap_zscore_threshold=1.5,
        ),
    )

    assert signal.sell is True
    assert signal.buy is False
    assert signal.vwap_deviation_pct == 0.8
    assert signal.vwap_zscore == 2.0
    assert signal.reasons == ['vwap_z_high']


def test_adaptive_vwap_signal_stays_flat_when_deviation_is_not_unusual():
    state = IntradaySignalState(
        price=100.8,
        day_low=99.0,
        day_high=101.0,
        vwap=100.0,
        amplitude_pct=2.0,
        vwap_deviation_std_pct=1.0,
    )

    signal = evaluate_t0_signal(
        state,
        T0SignalConfig(
            signal_mode='adaptive_vwap',
            vwap_deviation_pct=99.0,
            vwap_zscore_threshold=1.5,
        ),
    )

    assert signal.sell is False
    assert signal.buy is False
    assert signal.vwap_zscore == 0.8
    assert signal.reasons == []
