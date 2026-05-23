"""Pre-fetch structured market data for injection into LLM user message.

Eliminates per-day tool-loop roundtrips — the agent starts with complete
research context and can decide in a single LLM turn.
"""
from __future__ import annotations

import math
import statistics
from datetime import date


def _try(fn, *a, **kw):
    """Call fn, return None on any exception."""
    try:
        return fn(*a, **kw)
    except Exception:  # noqa: BLE001
        return None


def _summarize_kline(bars: list[dict]) -> dict | None:
    if not bars:
        return None
    closes = [float(b.get('close', 0)) for b in bars if b.get('close') is not None]
    if not closes:
        return None
    latest = closes[0] if bars[0].get('date', '') >= bars[-1].get('date', '') else closes[-1]
    oldest = closes[-1] if bars[0].get('date', '') >= bars[-1].get('date', '') else closes[0]
    return_pct = ((latest - oldest) / oldest * 100.0) if oldest else 0.0
    if len(closes) >= 2:
        daily_rets = [(closes[i] - closes[i + 1]) / closes[i + 1] * 100.0
                      for i in range(len(closes) - 1) if closes[i + 1]]
        vol = statistics.stdev(daily_rets) if len(daily_rets) >= 2 else 0.0
    else:
        vol = 0.0
    return {
        'return_30d_pct': round(return_pct, 2),
        'volatility_30d_pct': round(vol, 2),
        'latest_close': round(latest, 2),
        'high_30d': round(max(closes), 2),
        'low_30d': round(min(closes), 2),
    }


def _last_finite(values: list | None) -> float | None:
    """Return latest finite numeric value from a TA-Lib-style output list."""
    for raw in reversed(values or []):
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            return value
    return None


def _summarize_technical(indicator_results: dict[str, dict | None]) -> dict | None:
    """Compact RSI/MACD/MA outputs into latest values for the prompt."""
    rsi = indicator_results.get('RSI') or {}
    macd = indicator_results.get('MACD') or {}
    ma = indicator_results.get('MA') or {}
    out = {}

    rsi14 = _last_finite(rsi.get('values'))
    if rsi14 is not None:
        out['rsi14'] = round(rsi14, 2)

    ma20 = _last_finite(ma.get('values'))
    if ma20 is not None:
        out['ma20'] = round(ma20, 2)

    dif = _last_finite(macd.get('dif'))
    dea = _last_finite(macd.get('dea'))
    bar = _last_finite(macd.get('bar'))
    if dif is not None:
        out['macd_dif'] = round(dif, 4)
    if dea is not None:
        out['macd_dea'] = round(dea, 4)
    if bar is not None:
        out['macd_bar'] = round(bar, 4)

    return out or None


def _summarize_capital_flow(flow: dict | None) -> dict | None:
    """Compact get_capital_flow rows into latest field -> value mapping."""
    rows = (flow or {}).get('rows') or []
    out = {}
    for row in rows:
        field = row.get('field')
        if not field:
            continue
        raw = row.get('value')
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = raw
        out[field] = value
    return out or None


def build_market_snapshot(universe: list[str], as_of_date: date) -> dict:
    """Fetch + summarize per-stock data for the given universe."""
    from tools import get_kline, get_financials, get_technical, get_capital_flow

    stocks: dict = {}
    ymd = as_of_date.strftime('%Y%m%d')
    for code in universe:
        bars = _try(get_kline.call, {'code': code, 'period': '1d', 'count': 30})
        kline_summary = _summarize_kline(bars.get('bars', []) if bars else [])

        fin = _try(get_financials.call, {'code': code})
        financials = None
        if fin:
            financials = {
                k: fin.get(k) for k in
                ('pe', 'pb', 'roe', 'net_margin', 'revenue_growth')
                if fin.get(k) is not None
            } or None

        technical = _summarize_technical({
            'RSI': _try(get_technical.call, {
                'code': code, 'indicator': 'RSI', 'period': 14,
            }),
            'MACD': _try(get_technical.call, {
                'code': code, 'indicator': 'MACD',
            }),
            'MA': _try(get_technical.call, {
                'code': code, 'indicator': 'MA', 'period': 20,
            }),
        })

        capital_flow = _summarize_capital_flow(_try(
            get_capital_flow.call,
            {'code': code, 'start_date': ymd, 'end_date': ymd},
        ))

        stocks[code] = {
            'kline_summary': kline_summary,
            'financials': financials,
            'technical': technical,
            'capital_flow': capital_flow,
        }
    return {
        'date': as_of_date.strftime('%Y-%m-%d'),
        'stocks': stocks,
    }
