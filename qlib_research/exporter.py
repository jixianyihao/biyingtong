from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


QLIB_COLUMNS = [
    'symbol', 'date', 'open', 'high', 'low', 'close',
    'volume', 'money', 'factor',
]


def qlib_symbol(code: str) -> str:
    token = (code or '').strip().upper()
    if token.endswith('.SZ'):
        return 'SZ' + token[:-3]
    if token.endswith('.SH'):
        return 'SH' + token[:-3]
    return token.replace('.', '')


def _timestamp(row: dict[str, Any]) -> str:
    raw = row.get('ts') or row.get('datetime') or row.get('date')
    return str(raw).replace('T', ' ')[:19]


def bars_to_qlib_rows(
    code: str,
    bars: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    symbol = qlib_symbol(code)
    rows: list[dict[str, Any]] = []
    for bar in bars:
        volume = float(bar.get('vol', bar.get('volume', 0.0)) or 0.0)
        close = float(bar.get('close') or 0.0)
        money = float(bar.get(
            'amount', bar.get('money', close * volume),
        ) or 0.0)
        rows.append({
            'symbol': symbol,
            'date': _timestamp(bar),
            'open': float(bar.get('open') or 0.0),
            'high': float(bar.get('high') or 0.0),
            'low': float(bar.get('low') or 0.0),
            'close': close,
            'volume': volume,
            'money': money,
            'factor': 1.0,
        })
    return rows


def write_qlib_csv(
    code: str,
    bars: list[dict[str, Any]],
    out_dir: str | Path,
) -> Path:
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f'{qlib_symbol(code)}.csv'
    rows = bars_to_qlib_rows(code, bars)
    with path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=QLIB_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path
