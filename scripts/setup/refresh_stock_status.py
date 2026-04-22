"""Refresh stock_status table from TDX snapshot.

Usage: python -m scripts.setup.refresh_stock_status
"""
from __future__ import annotations

import storage
from storage.base import StockStatusRow


# HS300 market code per existing load_kline.py convention
_HS300_MARKET = '23'


def _is_st_name(name: str | None) -> bool:
    """Detect ST / *ST / S*ST prefix in stock name."""
    if not name:
        return False
    n = name.strip().upper().replace(' ', '')
    return n.startswith('ST') or n.startswith('*ST') or n.startswith('S*ST')


def _load_pool_codes() -> list[str]:
    """HS300 codes from TDX. Returns list of codes like '600519.SH'."""
    from tdx_service import tdx
    if not tdx.initialize() or not tdx.is_connected():
        raise RuntimeError('TDX not connected — launch 通达信 and press F12')
    lst = tdx.get_stock_list(market=_HS300_MARKET)
    codes: list[str] = []
    for item in lst:
        code = item.get('code') or item.get('stock_code')
        if code and '.' in code:
            codes.append(code)
    return codes


def _fetch_snapshot(codes: list[str]) -> dict[str, dict]:
    """Batched snapshot keyed by code. Each value has name + suspended flag."""
    from tdx_service import tdx
    raw = tdx.get_snapshots(codes)
    out: dict[str, dict] = {}
    for row in raw:
        code = row.get('code') or row.get('stock_code')
        if not code:
            continue
        out[code] = {
            'name': row.get('name') or row.get('stock_name'),
            'suspended': bool(row.get('suspended', False)),
        }
    return out


def run() -> int:
    """Return count of rows written."""
    codes = _load_pool_codes()
    snap = _fetch_snapshot(codes)
    rows = [
        StockStatusRow(
            code=code,
            name=info.get('name'),
            is_st=_is_st_name(info.get('name')),
            is_suspended=bool(info.get('suspended', False)),
            is_delisted=False,
        )
        for code, info in snap.items()
    ]
    return storage.stock_status().bulk_upsert(rows)


if __name__ == '__main__':
    n = run()
    print(f'refreshed stock_status: {n} rows')
