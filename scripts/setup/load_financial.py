"""Load PE/PB/ROE/margins/growth for a set of stocks into data/financial_cache.db.

Uses the existing tdx_service singleton (tqcenter SDK). Idempotent: UPSERTs
by (stock_code, date). Safe to re-run.

tqcenter's ``get_stock_info`` returns a Chinese-balance-sheet style dict with
keys like ``J_mgsy`` (EPS), ``J_mgjzc`` (BVPS), ``J_jyl`` (pre-computed ROE %),
``J_yysy`` (revenue), ``J_yycb`` (cost). PE/PB need a live price, so we pull
that from ``tdx.get_snapshot(...)`` and compute ``PE = price / EPS`` etc.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = REPO_ROOT / 'data' / 'financial_cache.db'

SCHEMA = '''
CREATE TABLE IF NOT EXISTS financial_data (
    stock_code         TEXT NOT NULL,
    date               DATE NOT NULL,
    pe                 REAL,
    pb                 REAL,
    roe                REAL,
    gross_margin       REAL,
    revenue_growth     REAL,
    net_profit_growth  REAL,
    PRIMARY KEY (stock_code, date)
);
'''


def _ensure_schema(con: sqlite3.Connection) -> None:
    con.execute('PRAGMA journal_mode=WAL')
    con.execute(SCHEMA)
    con.commit()


def _as_float(value) -> float | None:
    try:
        if value is None or value == '' or value == '--':
            return None
        f = float(value)
        # TDX sometimes returns sentinel values like 9999999 for N/A
        if abs(f) > 1e8:
            return None
        return f
    except (TypeError, ValueError):
        return None


def _normalize_code(code: str) -> str:
    """tdx_service expects '600519.SH'; some callers pass bare '600519'."""
    if '.' in code:
        return code
    if code.startswith(('6', '9')):
        return f'{code}.SH'
    return f'{code}.SZ'


def _derive_metrics(info: dict, price: float | None) -> dict:
    """Compute PE/PB/ROE/gross_margin from tqcenter's balance-sheet dict.

    Keys used (Chinese A-share convention):
      * J_mgsy  = ÿ������ (EPS, yuan/share)
      * J_mgjzc = ÿ�ɾ��ʲ� (BVPS, yuan/share)
      * J_jyl   = ����ʲ������� / ROE (already in %)
      * J_yysy  = Ӫҵ���� (revenue)
      * J_yycb  = Ӫҵ�ɱ� (cost of revenue)
      * J_jly   = ������ (net profit) -- fallback for ROE if J_jyl missing
      * J_jzc   = ���ʲ� -- fallback for ROE denom
    """
    eps = _as_float(info.get('J_mgsy'))
    bvps = _as_float(info.get('J_mgjzc'))
    roe = _as_float(info.get('J_jyl'))
    yysy = _as_float(info.get('J_yysy'))
    yycb = _as_float(info.get('J_yycb'))
    jly = _as_float(info.get('J_jly'))
    jzc = _as_float(info.get('J_jzc'))

    pe = None
    if price and eps and eps > 0:
        pe = price / eps

    pb = None
    if price and bvps and bvps > 0:
        pb = price / bvps

    if roe is None and jly is not None and jzc and jzc > 0:
        roe = jly / jzc * 100.0

    gross_margin = None
    if yysy and yysy > 0 and yycb is not None:
        gross_margin = (yysy - yycb) / yysy * 100.0

    return {
        'pe': pe,
        'pb': pb,
        'roe': roe,
        'gross_margin': gross_margin,
        'revenue_growth': None,  # not exposed by tqcenter single-period snapshot
        'net_profit_growth': None,
    }


def load_financial(symbols: list[str], as_of: date | None = None) -> int:
    """Fetch financial data for `symbols` and UPSERT into CACHE_PATH.

    Returns count of symbols successfully written.
    """
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if as_of is None:
        as_of = date.today()

    from tdx_service import tdx
    tdx.ensure_connected()

    written = 0
    con = sqlite3.connect(CACHE_PATH)
    try:
        _ensure_schema(con)
        for bare in symbols:
            full = _normalize_code(bare)
            try:
                info = tdx.get_stock_info(full)
            except Exception as e:  # noqa: BLE001
                print(f'[load_financial] {full} FAILED: {e}')
                continue
            if not info or not isinstance(info, dict):
                continue
            try:
                snap = tdx.get_snapshot(full)
            except Exception as e:  # noqa: BLE001
                print(f'[load_financial] {full} snapshot FAILED: {e}')
                snap = None
            price = None
            if isinstance(snap, dict):
                price = _as_float(snap.get('price'))

            metrics = _derive_metrics(info, price)
            row = (
                bare,
                as_of.isoformat(),
                metrics['pe'],
                metrics['pb'],
                metrics['roe'],
                metrics['gross_margin'],
                metrics['revenue_growth'],
                metrics['net_profit_growth'],
            )
            if all(v is None for v in row[2:]):
                # No usable data; skip
                continue
            con.execute(
                '''INSERT OR REPLACE INTO financial_data
                   (stock_code, date, pe, pb, roe, gross_margin, revenue_growth, net_profit_growth)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                row,
            )
            written += 1
        con.commit()
    finally:
        con.close()
    return written


if __name__ == '__main__':
    # Smoke test: load a handful of stocks
    n = load_financial(['600519', '000858', '600036', '300750', '002415'])
    print(f'wrote {n} rows to {CACHE_PATH}')
