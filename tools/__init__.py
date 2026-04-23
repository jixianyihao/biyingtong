"""Tool callables for LLM agents. Each module exports SPEC + call(input)."""
from __future__ import annotations

from llm.base import ToolSpec

from . import (
    get_financials, get_index, get_kline, get_news, get_portfolio,
    get_snapshot, get_technical, place_decision,
)

def _bind(mod):
    """Return a thunk that looks up mod.call at invocation time.

    This keeps the tool function reference dynamic so tests can
    monkeypatch `<module>.call` and have AgentRunner pick up the patch.
    """
    def _invoke(input):
        return mod.call(input)
    return _invoke


ALL_TOOLS: dict = {
    'place_decision': (place_decision.SPEC, _bind(place_decision)),
    'get_kline': (get_kline.SPEC, _bind(get_kline)),
    'get_snapshot': (get_snapshot.SPEC, _bind(get_snapshot)),
    'get_financials': (get_financials.SPEC, _bind(get_financials)),
    'get_technical': (get_technical.SPEC, _bind(get_technical)),
    'get_index': (get_index.SPEC, _bind(get_index)),
    'get_portfolio': (get_portfolio.SPEC, _bind(get_portfolio)),
    'get_news': (get_news.SPEC, _bind(get_news)),
}


def filter_allowed(tool_names: list[str]) -> dict:
    result = {'place_decision': ALL_TOOLS['place_decision']}
    for name in tool_names:
        if name in ALL_TOOLS:
            result[name] = ALL_TOOLS[name]
    return result
