from qlib_research.features import summarize_intraday_features


def test_summarize_intraday_features_reports_range_vwap_and_reversal():
    bars = [
        {
            'ts': '2026-01-05 09:31:00',
            'date': '2026-01-05',
            'open': 10.0,
            'high': 10.2,
            'low': 9.9,
            'close': 10.0,
            'vol': 1000,
        },
        {
            'ts': '2026-01-05 09:32:00',
            'date': '2026-01-05',
            'open': 10.0,
            'high': 10.4,
            'low': 9.8,
            'close': 9.9,
            'vol': 2000,
        },
        {
            'ts': '2026-01-05 14:56:00',
            'date': '2026-01-05',
            'open': 9.9,
            'high': 10.5,
            'low': 9.7,
            'close': 10.4,
            'vol': 2500,
        },
        {
            'ts': '2026-01-06 09:31:00',
            'date': '2026-01-06',
            'open': 10.5,
            'high': 10.8,
            'low': 10.2,
            'close': 10.3,
            'vol': 1200,
        },
        {
            'ts': '2026-01-06 14:56:00',
            'date': '2026-01-06',
            'open': 10.3,
            'high': 11.0,
            'low': 10.1,
            'close': 10.9,
            'vol': 2400,
        },
    ]

    summary = summarize_intraday_features('300951.SZ', bars)

    assert summary['code'] == '300951.SZ'
    assert summary['days'] == 2
    assert summary['bar_count'] == 5
    assert summary['avg_intraday_range_pct'] > 5.0
    assert summary['avg_amplitude_pct'] > 5.0
    assert summary['vwap_deviation_std_pct'] > 0.0
    assert summary['vwap_zscore_tail_count'] >= 0
    assert summary['opening_range_pct'] > 0.0
    assert summary['volume_cv'] > 0.0
    assert summary['reversal_score'] > 0.0
