from pathlib import Path

from qlib_research.exporter import bars_to_qlib_rows, write_qlib_csv


def _bars():
    return [
        {
            'ts': '2026-01-05 09:31:00',
            'date': '2026-01-05',
            'open': 10.0,
            'high': 10.2,
            'low': 9.9,
            'close': 10.1,
            'vol': 1200,
            'amount': 12120.0,
        },
        {
            'ts': '2026-01-05 09:32:00',
            'date': '2026-01-05',
            'open': 10.1,
            'high': 10.3,
            'low': 10.0,
            'close': 10.25,
            'vol': 1500,
            'amount': 15375.0,
        },
    ]


def test_bars_to_qlib_rows_preserves_minute_timestamp_and_required_columns():
    rows = bars_to_qlib_rows('300951.SZ', _bars())

    assert rows == [
        {
            'symbol': 'SZ300951',
            'date': '2026-01-05 09:31:00',
            'open': 10.0,
            'high': 10.2,
            'low': 9.9,
            'close': 10.1,
            'volume': 1200.0,
            'money': 12120.0,
            'factor': 1.0,
        },
        {
            'symbol': 'SZ300951',
            'date': '2026-01-05 09:32:00',
            'open': 10.1,
            'high': 10.3,
            'low': 10.0,
            'close': 10.25,
            'volume': 1500.0,
            'money': 15375.0,
            'factor': 1.0,
        },
    ]


def test_write_qlib_csv_writes_one_file_per_symbol(tmp_path: Path):
    path = write_qlib_csv('300951.SZ', _bars(), tmp_path)

    assert path == tmp_path / 'SZ300951.csv'
    text = path.read_text(encoding='utf-8')
    assert text.splitlines()[0] == (
        'symbol,date,open,high,low,close,volume,money,factor'
    )
    assert (
        'SZ300951,2026-01-05 09:31:00,10.0,10.2,9.9,10.1,'
        '1200.0,12120.0,1.0'
    ) in text
