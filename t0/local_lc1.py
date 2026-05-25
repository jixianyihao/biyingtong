from __future__ import annotations

import struct
from pathlib import Path
from statistics import median
from typing import Any, Iterable


LC1_RECORD = struct.Struct('<HHfffffii')
DEFAULT_MINLINE_ROOTS = [
    Path(r'C:\new_tdx_mock\vipdoc\sh\minline'),
    Path(r'C:\new_tdx_mock\vipdoc\sz\minline'),
    Path(r'C:\new_tdx64\vipdoc\sh\minline'),
    Path(r'C:\new_tdx64\vipdoc\sz\minline'),
]


def _code_from_path(path: Path) -> str:
    stem = path.stem.lower()
    suffix = '.SH' if stem.startswith('sh') else '.SZ'
    return stem[2:].upper() + suffix


def _path_for_code(root: str | Path, code: str) -> Path:
    raw = code[:6].lower()
    market = code[-2:].lower()
    r = Path(root)
    if r.name.lower() == 'minline':
        return r / f'{market}{raw}.lc1'
    return r / market / 'minline' / f'{market}{raw}.lc1'


def _is_normal_a_share(code: str) -> bool:
    return code.startswith(('60', '68', '00', '30'))


def _decode_date(raw: int) -> tuple[int, int, int]:
    year = raw // 2048 + 2004
    rem = raw % 2048
    return year, rem // 100, rem % 100


def parse_lc1_file(path: str | Path) -> list[dict[str, Any]]:
    """Parse a TDX 1-minute .lc1 file into OHLCV bars.

    TDX minute records are 32 bytes:
    uint16 date, uint16 minute, float open/high/low/close/amount, int volume,
    int reserved. The date encoding is (year - 2004) * 2048 + month * 100 + day.
    """
    p = Path(path)
    data = p.read_bytes()
    limit = len(data) // LC1_RECORD.size * LC1_RECORD.size
    bars: list[dict[str, Any]] = []
    for rec in LC1_RECORD.iter_unpack(data[:limit]):
        raw_date, raw_minute, open_, high, low, close, amount, volume, _ = rec
        if close <= 0 or high <= 0 or low <= 0:
            continue
        year, month, day = _decode_date(raw_date)
        hour = raw_minute // 60
        minute = raw_minute % 60
        if not (1 <= month <= 12 and 1 <= day <= 31 and 9 <= hour <= 15):
            continue
        bars.append({
            'date': f'{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:00',
            'open': round(float(open_), 4),
            'high': round(float(high), 4),
            'low': round(float(low), 4),
            'close': round(float(close), 4),
            'vol': int(volume),
            'amount': round(float(amount), 4),
        })
    return bars


def load_lc1_bars_for_code(
    code: str,
    roots: Iterable[str | Path] | None = None,
) -> list[dict[str, Any]]:
    for root in roots or DEFAULT_MINLINE_ROOTS:
        p = _path_for_code(root, code)
        if p.exists():
            return parse_lc1_file(p)
    return []


def _candidate_metrics(code: str, path: Path, bars: list[dict[str, Any]]) -> dict[str, Any] | None:
    by_day: dict[str, list[dict[str, Any]]] = {}
    for bar in bars:
        by_day.setdefault(str(bar['date'])[:10], []).append(bar)
    if not bars or not by_day:
        return None

    first_price = float(bars[0]['close'])
    last_price = float(bars[-1]['close'])
    if first_price <= 0:
        return None

    amps: list[float] = []
    ordered_intraday_range = 0.0
    for rows in by_day.values():
        high = max(float(r['high']) for r in rows)
        low = min(float(r['low']) for r in rows)
        if low > 0:
            amps.append((high / low - 1.0) * 100.0)

        min_so_far = float(rows[0]['low'])
        best_after_low = 0.0
        for row in rows:
            best_after_low = max(best_after_low, float(row['high']) - min_so_far)
            min_so_far = min(min_so_far, float(row['low']))
        ordered_intraday_range += best_after_low

    if not amps:
        return None
    period_return_pct = (last_price / first_price - 1.0) * 100.0
    avg_amp = sum(amps) / len(amps)
    med_amp = median(amps)
    opportunity_1000 = ordered_intraday_range * 1000
    score = avg_amp * 12.0 + med_amp * 4.0 + max(period_return_pct, 0.0) * 0.2
    return {
        'code': code,
        'path': str(path),
        'first_date': str(bars[0]['date'])[:10],
        'last_date': str(bars[-1]['date'])[:10],
        'days': len(by_day),
        'bar_count': len(bars),
        'first_price': round(first_price, 4),
        'last_price': round(last_price, 4),
        'period_return_pct': round(period_return_pct, 4),
        'avg_intraday_amp_pct': round(avg_amp, 4),
        'median_intraday_amp_pct': round(med_amp, 4),
        'ordered_opportunity_1000': round(opportunity_1000, 4),
        'score': round(score, 4),
    }


def _candidate_metrics_from_file(code: str, path: Path) -> dict[str, Any] | None:
    data = path.read_bytes()
    limit = len(data) // LC1_RECORD.size * LC1_RECORD.size
    first_date = last_date = None
    first_price = last_price = None
    day_key = None
    day_high = -1.0
    day_low = float('inf')
    min_so_far = None
    best_after_low = 0.0
    amps: list[float] = []
    ordered_intraday_range = 0.0
    bar_count = 0

    for rec in LC1_RECORD.iter_unpack(data[:limit]):
        raw_date, raw_minute, _, high, low, close, _, _, _ = rec
        if close <= 0 or high <= 0 or low <= 0:
            continue
        year, month, day = _decode_date(raw_date)
        hour = raw_minute // 60
        minute = raw_minute % 60
        if not (1 <= month <= 12 and 1 <= day <= 31 and 9 <= hour <= 15):
            continue
        current_day = f'{year:04d}-{month:02d}-{day:02d}'
        if day_key is None:
            day_key = current_day
            day_high = float(high)
            day_low = float(low)
            min_so_far = float(low)
            best_after_low = 0.0
        elif current_day != day_key:
            if day_low > 0:
                amps.append((day_high / day_low - 1.0) * 100.0)
            ordered_intraday_range += best_after_low
            day_key = current_day
            day_high = float(high)
            day_low = float(low)
            min_so_far = float(low)
            best_after_low = 0.0

        day_high = max(day_high, float(high))
        day_low = min(day_low, float(low))
        if min_so_far is None:
            min_so_far = float(low)
        best_after_low = max(best_after_low, float(high) - min_so_far)
        min_so_far = min(min_so_far, float(low))

        timestamp = f'{current_day} {hour:02d}:{minute:02d}:00'
        if first_price is None:
            first_price = float(close)
            first_date = current_day
        last_price = float(close)
        last_date = current_day
        bar_count += 1

    if day_key is not None:
        if day_low > 0:
            amps.append((day_high / day_low - 1.0) * 100.0)
        ordered_intraday_range += best_after_low
    if not first_price or last_price is None or not amps:
        return None

    period_return_pct = (last_price / first_price - 1.0) * 100.0
    avg_amp = sum(amps) / len(amps)
    med_amp = median(amps)
    opportunity_1000 = ordered_intraday_range * 1000
    score = avg_amp * 12.0 + med_amp * 4.0 + max(period_return_pct, 0.0) * 0.2
    return {
        'code': code,
        'path': str(path),
        'first_date': first_date,
        'last_date': last_date,
        'days': len(amps),
        'bar_count': bar_count,
        'first_price': round(first_price, 4),
        'last_price': round(last_price, 4),
        'period_return_pct': round(period_return_pct, 4),
        'avg_intraday_amp_pct': round(avg_amp, 4),
        'median_intraday_amp_pct': round(med_amp, 4),
        'ordered_opportunity_1000': round(opportunity_1000, 4),
        'score': round(score, 4),
    }


def scan_lc1_candidates(
    roots: Iterable[str | Path] | None = None,
    *,
    top_n: int = 30,
    max_files: int = 10_000,
    min_days: int = 50,
    min_avg_amp_pct: float = 3.0,
    max_avg_amp_pct: float = 15.0,
    min_price: float = 2.0,
    max_price: float = 300.0,
    min_return_pct: float = -30.0,
    max_return_pct: float = 120.0,
) -> list[dict[str, Any]]:
    paths: list[Path] = []
    for root in roots or DEFAULT_MINLINE_ROOTS:
        r = Path(root)
        if r.exists():
            paths.extend(r.glob('*.lc1'))
    paths = sorted(paths, key=lambda p: (-p.stat().st_size, str(p)))[:max_files]

    rows: list[dict[str, Any]] = []
    for path in paths:
        code = _code_from_path(path)
        if not _is_normal_a_share(code):
            continue
        metrics = _candidate_metrics_from_file(code, path)
        if not metrics:
            continue
        if metrics['days'] < min_days:
            continue
        if not (min_price <= metrics['first_price'] <= max_price):
            continue
        if not (min_price <= metrics['last_price'] <= max_price):
            continue
        if not (min_avg_amp_pct <= metrics['avg_intraday_amp_pct'] <= max_avg_amp_pct):
            continue
        if not (min_return_pct <= metrics['period_return_pct'] <= max_return_pct):
            continue
        rows.append(metrics)

    rows.sort(
        key=lambda r: (
            r['score'],
            r['avg_intraday_amp_pct'],
            r['ordered_opportunity_1000'],
        ),
        reverse=True,
    )
    return rows[:max(1, top_n)]
