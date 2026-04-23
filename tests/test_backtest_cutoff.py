"""Cross-cutoff zone classification."""
from datetime import date


def test_pollution_before_cutoff():
    from backtest.cutoff import classify_date
    assert classify_date(date(2024, 5, 1), cutoff='2024-06-01') == 'pollution'


def test_buffer_at_cutoff():
    from backtest.cutoff import classify_date
    assert classify_date(date(2024, 6, 1), cutoff='2024-06-01') == 'buffer'


def test_buffer_within_60_days():
    from backtest.cutoff import classify_date
    assert classify_date(date(2024, 7, 20), cutoff='2024-06-01') == 'buffer'


def test_clean_after_60_days():
    from backtest.cutoff import classify_date
    assert classify_date(date(2024, 8, 1), cutoff='2024-06-01') == 'clean'


def test_zone_windows_groups_days():
    from backtest.cutoff import zone_windows
    days = [date(2024, 5, 15), date(2024, 6, 1), date(2024, 7, 15),
            date(2024, 8, 10)]
    groups = zone_windows(days, cutoff='2024-06-01')
    assert groups['pollution'] == [date(2024, 5, 15)]
    assert groups['buffer'] == [date(2024, 6, 1), date(2024, 7, 15)]
    assert groups['clean'] == [date(2024, 8, 10)]


def test_zone_windows_all_one_zone():
    from backtest.cutoff import zone_windows
    groups = zone_windows([date(2024, 1, 1), date(2024, 2, 1)],
                          cutoff='2024-06-01')
    assert groups['pollution'] == [date(2024, 1, 1), date(2024, 2, 1)]
    assert groups['buffer'] == []
    assert groups['clean'] == []


def test_custom_buffer_days():
    from backtest.cutoff import classify_date
    assert classify_date(date(2024, 7, 1), cutoff='2024-06-01',
                         buffer_days=30) == 'clean'
