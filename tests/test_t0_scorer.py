from __future__ import annotations

import pytest

from t0.scorer import score_minute_bars, score_snapshot


def _bar(time: str, close: float, high: float | None = None, low: float | None = None):
    return {
        'date': f'2026-05-22 {time}',
        'open': close,
        'high': high if high is not None else close,
        'low': low if low is not None else close,
        'close': close,
        'vol': 100_000,
    }


def test_early_pullback_after_strong_open_is_buy_t_candidate():
    bars = [
        _bar('09:31', 129.00, high=129.30, low=128.80),
        _bar('09:32', 130.20, high=130.50, low=129.00),
        _bar('09:33', 129.60, high=130.40, low=129.50),
        _bar('09:34', 128.80, high=129.80, low=128.60),
        _bar('09:35', 128.10, high=129.10, low=128.00),
    ]

    scored = score_minute_bars('688981.SH', bars, last_close=126.0)

    assert scored['code'] == '688981.SH'
    assert scored['action'] == 'buy_t_candidate'
    assert scored['metrics']['amplitude_pct'] == pytest.approx(1.98, abs=0.01)
    assert scored['metrics']['range_position'] == pytest.approx(0.04, abs=0.001)
    assert any('near intraday low' in r for r in scored['reasons'])


def test_late_spike_near_intraday_high_is_sell_t_candidate():
    bars = [
        _bar('09:31', 126.20, high=126.30, low=126.00),
        _bar('09:32', 127.40, high=127.50, low=126.20),
        _bar('09:33', 128.70, high=128.90, low=127.40),
        _bar('09:34', 129.20, high=129.50, low=128.60),
    ]

    scored = score_minute_bars('688981.SH', bars, last_close=126.0)

    assert scored['action'] == 'sell_t_candidate'
    assert scored['metrics']['range_position'] == pytest.approx(0.914, abs=0.001)
    assert any('near intraday high' in r for r in scored['reasons'])


def test_low_amplitude_is_watch():
    bars = [
        _bar('09:31', 126.10, high=126.20, low=126.00),
        _bar('09:32', 126.15, high=126.20, low=126.05),
        _bar('09:33', 126.18, high=126.22, low=126.10),
    ]

    scored = score_minute_bars('688981.SH', bars, last_close=126.0)

    assert scored['action'] == 'watch'
    assert any('amplitude below' in r for r in scored['reasons'])


def test_missing_minute_bars_is_invalid():
    scored = score_minute_bars('688981.SH', [], last_close=126.0)

    assert scored['action'] == 'invalid'
    assert scored['score'] == 0
    assert scored['metrics']['bar_count'] == 0


def test_snapshot_fallback_scores_current_intraday_range():
    scored = score_snapshot({
        'code': '688981.SH',
        'name': '中芯国际',
        'price': 131.33,
        'lastClose': 127.22,
        'open': 129.33,
        'high': 132.18,
        'low': 126.50,
        'vol': 1_199_477,
        'amount': 1_551_684.38,
    })

    assert scored['action'] == 'sell_t_candidate'
    assert scored['metrics']['amplitude_pct'] == pytest.approx(4.46, abs=0.01)
    assert scored['metrics']['range_position'] == pytest.approx(0.85, abs=0.01)
