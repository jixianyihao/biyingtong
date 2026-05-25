from __future__ import annotations

import struct
from pathlib import Path

import pytest

from t0.local_lc1 import parse_lc1_file, scan_lc1_candidates


def _date_code(year: int, month: int, day: int) -> int:
    return (year - 2004) * 2048 + month * 100 + day


def _write_lc1(
    path: Path,
    code: str,
    closes: list[float],
    *,
    intraday_amp_pct: float = 4.0,
) -> None:
    market = code[-2:].lower()
    raw = code[:6]
    target = path / market / 'minline'
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    day = 1
    for i, close in enumerate(closes):
        if i and i % 4 == 0:
            day += 1
        dt = _date_code(2026, 5, day)
        minute = 9 * 60 + 31 + (i % 4)
        high = close * (1 + intraday_amp_pct / 200.0)
        low = close * (1 - intraday_amp_pct / 200.0)
        rows.append(struct.pack(
            '<HHfffffii',
            dt, minute,
            close, high, low, close,
            close * 100_000,
            100_000,
            0,
        ))
    (target / f'{market}{raw}.lc1').write_bytes(b''.join(rows))


def test_parse_lc1_file_decodes_tdx_minute_records(tmp_path):
    _write_lc1(tmp_path, '688981.SH', [10.0, 10.2, 10.4, 10.3])

    bars = parse_lc1_file(tmp_path / 'sh' / 'minline' / 'sh688981.lc1')

    assert bars[0]['date'] == '2026-05-01 09:31:00'
    assert bars[0]['open'] == pytest.approx(10.0)
    assert bars[0]['high'] == pytest.approx(10.2)
    assert bars[0]['low'] == pytest.approx(9.8)
    assert bars[-1]['date'] == '2026-05-01 09:34:00'


def test_scan_lc1_candidates_filters_and_ranks_normal_a_share_files(tmp_path):
    _write_lc1(tmp_path, '688981.SH', [10 + i * 0.05 for i in range(80)])
    _write_lc1(tmp_path, '880001.SH', [10 + i * 0.05 for i in range(80)])

    rows = scan_lc1_candidates(
        [tmp_path / 'sh' / 'minline'],
        top_n=5,
        min_days=10,
        min_avg_amp_pct=1.0,
        max_avg_amp_pct=20.0,
    )

    assert [r['code'] for r in rows] == ['688981.SH']
    assert rows[0]['days'] == 20
    assert rows[0]['bar_count'] == 80
    assert rows[0]['period_return_pct'] > 0
    assert rows[0]['avg_intraday_amp_pct'] > 1.0


def test_scan_lc1_candidates_stable_t_profile_prefers_moderate_trends(tmp_path):
    _write_lc1(
        tmp_path,
        '688981.SH',
        [100 + i * 0.08 for i in range(80)],  # steady +6.3%
        intraday_amp_pct=4.0,
    )
    _write_lc1(
        tmp_path,
        '002885.SZ',
        [20 + i * 0.25 for i in range(80)],  # explosive +98.8%
        intraday_amp_pct=4.0,
    )

    rows = scan_lc1_candidates(
        [tmp_path / 'sh' / 'minline', tmp_path / 'sz' / 'minline'],
        top_n=2,
        min_days=10,
        min_avg_amp_pct=1.0,
        max_avg_amp_pct=20.0,
        max_return_pct=150.0,
        score_profile='stable_t',
    )

    assert [r['code'] for r in rows] == ['688981.SH', '002885.SZ']
    assert rows[0]['stable_t_score'] > rows[1]['stable_t_score']
