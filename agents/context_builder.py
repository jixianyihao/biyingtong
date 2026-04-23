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
        'closes_last_30d': [round(c, 2) for c in closes[:30]],
        'return_30d_pct': round(return_pct, 2),
        'volatility_30d_pct': round(vol, 2),
        'latest_close': round(latest, 2),
    }


def build_market_snapshot(universe: list[str], as_of_date: date) -> dict:
    """Fetch + summarize per-stock data for the given universe."""
    from tools import get_kline, get_financials, get_technical

    stocks: dict = {}
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

        tech = _try(get_technical.call, {'code': code})
        technical = None
        if tech:
            indicators = tech.get('indicators', tech)
            technical = {
                k: indicators.get(k) for k in ('ma20', 'rsi14', 'macd')
                if indicators.get(k) is not None
            } or None

        stocks[code] = {
            'kline_summary': kline_summary,
            'financials': financials,
            'technical': technical,
        }
    return {
        'date': as_of_date.strftime('%Y-%m-%d'),
        'stocks': stocks,
    }
