from __future__ import annotations

import struct
from pathlib import Path

import pytest

from t0.local_lc1 import (
    _LC1_BARS_CACHE,
    _LC1_METRICS_CACHE,
    _sample_paths_evenly,
    load_lc1_bars_for_code,
    parse_lc1_file,
    scan_lc1_candidates,
)


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


def test_scan_lc1_candidates_max_files_samples_across_market_not_by_size(tmp_path):
    # The real TDX folder can have thousands of files. A max_files cap should
    # spread across the market instead of choosing only the largest files,
    # otherwise old/large histories dominate and smaller but valid T names are
    # never inspected.
    for raw in ['000001', '000003', '000005']:
        _write_lc1(
            tmp_path,
            f'{raw}.SZ',
            [100 + i * 0.01 for i in range(80)],
            intraday_amp_pct=0.5,
        )
    _write_lc1(
        tmp_path,
        '000011.SZ',
        [30 + i * 0.06 for i in range(16)],
        intraday_amp_pct=4.0,
    )
    for raw in ['000009', '000013']:
        _write_lc1(
            tmp_path,
            f'{raw}.SZ',
            [100 + i * 0.01 for i in range(80)],
            intraday_amp_pct=0.5,
        )

    rows = scan_lc1_candidates(
        [tmp_path / 'sz' / 'minline'],
        top_n=5,
        max_files=4,
        min_days=4,
        min_avg_amp_pct=1.0,
        max_avg_amp_pct=20.0,
        max_return_pct=150.0,
        score_profile='stable_t',
    )

    assert [r['code'] for r in rows] == ['000011.SZ']


def test_sample_paths_evenly_is_monotonic_when_limit_expands():
    paths = [Path(f'sz{i:06d}.lc1') for i in range(1, 31)]

    smaller = _sample_paths_evenly(paths, 6)
    larger = _sample_paths_evenly(paths, 12)

    assert set(smaller).issubset(set(larger))


def test_scan_lc1_candidates_reuses_metrics_until_file_changes(
    tmp_path,
    monkeypatch,
):
    _LC1_METRICS_CACHE.clear()
    _write_lc1(tmp_path, '000009.SZ', [30 + i * 0.06 for i in range(80)])

    read_count = 0
    original_read_bytes = Path.read_bytes

    def counted_read_bytes(path: Path):
        nonlocal read_count
        if path.name == 'sz000009.lc1':
            read_count += 1
        return original_read_bytes(path)

    monkeypatch.setattr(Path, 'read_bytes', counted_read_bytes)
    scan_args = {
        'top_n': 5,
        'max_files': 10,
        'min_days': 10,
        'min_avg_amp_pct': 1.0,
        'max_avg_amp_pct': 20.0,
        'score_profile': 'stable_t',
    }

    first = scan_lc1_candidates([tmp_path / 'sz' / 'minline'], **scan_args)
    second = scan_lc1_candidates([tmp_path / 'sz' / 'minline'], **scan_args)

    assert [r['code'] for r in first] == ['000009.SZ']
    assert [r['code'] for r in second] == ['000009.SZ']
    assert read_count == 1

    _write_lc1(
        tmp_path,
        '000009.SZ',
        [35 + i * 0.08 for i in range(80)],
    )
    third = scan_lc1_candidates([tmp_path / 'sz' / 'minline'], **scan_args)

    assert [r['code'] for r in third] == ['000009.SZ']
    assert read_count == 2


def test_load_lc1_bars_for_code_reuses_bars_until_file_changes(
    tmp_path,
    monkeypatch,
):
    _LC1_BARS_CACHE.clear()
    _write_lc1(tmp_path, '000009.SZ', [30 + i * 0.06 for i in range(80)])

    read_count = 0
    original_read_bytes = Path.read_bytes

    def counted_read_bytes(path: Path):
        nonlocal read_count
        if path.name == 'sz000009.lc1':
            read_count += 1
        return original_read_bytes(path)

    monkeypatch.setattr(Path, 'read_bytes', counted_read_bytes)
    roots = [tmp_path / 'sz' / 'minline']

    first = load_lc1_bars_for_code('000009.SZ', roots)
    second = load_lc1_bars_for_code('000009.SZ', roots)

    assert len(first) == 80
    assert len(second) == 80
    assert first is not second
    assert read_count == 1

    first[0]['close'] = -1
    third = load_lc1_bars_for_code('000009.SZ', roots)
    assert third[0]['close'] != -1

    _write_lc1(tmp_path, '000009.SZ', [35 + i * 0.08 for i in range(80)])
    fourth = load_lc1_bars_for_code('000009.SZ', roots)

    assert len(fourth) == 80
    assert read_count == 2
