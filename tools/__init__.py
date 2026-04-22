"""Tool callables for LLM agents. Each module exports SPEC + call(input)."""
from __future__ import annotations

from llm.base import ToolSpec

from . import (
    get_financials, get_index, get_kline, get_news, get_portfolio,
    get_snapshot, get_technical, place_decision,
)

ALL_TOOLS: dict = {
    'place_decision': (place_decision.SPEC, place_decision.call),
    'get_kline': (get_kline.SPEC, get_kline.call),
    'get_snapshot': (get_snapshot.SPEC, get_snapshot.call),
    'get_financials': (get_financials.SPEC, get_financials.call),
    'get_technical': (get_technical.SPEC, get_technical.call),
    'get_index': (get_index.SPEC, get_index.call),
    'get_portfolio': (get_portfolio.SPEC, get_portfolio.call),
    'get_news': (get_news.SPEC, get_news.call),
}


def filter_allowed(tool_names: list[str]) -> dict:
    result = {'place_decision': ALL_TOOLS['place_decision']}
    for name in tool_names:
        if name in ALL_TOOLS:
            result[name] = ALL_TOOLS[name]
    return result
