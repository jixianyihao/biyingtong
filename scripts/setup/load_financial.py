"""Ingest PE/PB/ROE/margins/growth via tq.get_financial_data → storage.financial().

FN field mapping (see docs/references/tqcenter_docs/TdxQuant__mindoc-1h10m001ic888.md):
- FN1   每股收益          → trailing PE = price / FN1
- FN4   每股净资产        → PB = price / FN4
- FN6   净资产收益率      (backup: FN197)
- FN183 营业收入增长率    → revenue_growth
- FN184 净利润增长率      → net_profit_growth
- FN202 销售毛利率        → gross_margin

Requires TDX client to have downloaded 专业财务 data.
"""
from __future__ import annotations

from datetime import date

_FN_FIELDS = ['FN1', 'FN4', 'FN6', 'FN183', 'FN184', 'FN197', 'FN202']


def _as_float(value) -> float | None:
    try:
        if value is None or value == '' or value == '--':
            return None
        f = float(value)
        if abs(f) > 1e8:
            return None
        return f
    except (TypeError, ValueError):
        return None


def _normalize_code(code: str) -> str:
    if '.' in code:
        return code
    if code.startswith(('6', '9')):
        return f'{code}.SH'
    return f'{code}.SZ'


def _get_latest_price(full_code: str) -> float | None:
    from tdx_service import tdx
    snap = tdx.get_snapshot(full_code)
    if not snap:
        return None
    return _as_float(snap.get('price'))


def load_financial(symbols: list[str], as_of: date | None = None,
                   start_time: str = '20240101') -> int:
    """Fetch professional financial data and persist via storage.financial().

    Returns number of stocks written.
    """
    if as_of is None:
        as_of = date.today()

    from tdx_service import tdx
    tdx.ensure_connected()

    full_codes = [_normalize_code(s) for s in symbols]

    from tqcenter import tq
    try:
        fd = tq.get_financial_data(
            stock_list=full_codes,
            field_list=_FN_FIELDS,
            start_time=start_time,
            end_time='',
            report_type='announce_time',
        )
    except Exception as e:  # noqa: BLE001
        print(f'[load_financial] get_financial_data FAILED: {e}')
        return 0

    if not fd:
        return 0

    rows: list[dict] = []
    for bare, full in zip(symbols, full_codes):
        df = fd.get(full)
        if df is None or len(df) == 0:
            continue

        row = df.iloc[-1]
        fn1 = _as_float(row.get('FN1'))
        fn4 = _as_float(row.get('FN4'))
        fn6 = _as_float(row.get('FN6'))
        fn183 = _as_float(row.get('FN183'))
        fn184 = _as_float(row.get('FN184'))
        fn197 = _as_float(row.get('FN197'))
        fn202 = _as_float(row.get('FN202'))

        price = _get_latest_price(full)
        pe = round(price / fn1, 2) if (price and fn1 and fn1 > 0) else None
        pb = round(price / fn4, 2) if (price and fn4 and fn4 > 0) else None
        roe = fn6 if fn6 is not None else fn197

        db_row = {
            'stock_code': bare,
            'date': as_of.isoformat(),
            'pe': pe, 'pb': pb, 'roe': roe,
            'gross_margin': fn202,
            'revenue_growth': fn183,
            'net_profit_growth': fn184,
        }
        if all(v is None for v in (pe, pb, roe, fn202, fn183, fn184)):
            continue
        rows.append(db_row)

    from storage import financial
    store = financial()
    store.init_schema()
    return store.upsert(rows)


if __name__ == '__main__':
    n = load_financial(['600519', '000858', '600036', '300750', '002415'])
    print(f'wrote {n} rows via storage.financial()')
