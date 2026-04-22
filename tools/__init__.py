"""Tool callables for LLM agents. Each module exports SPEC + call(input)."""
from __future__ import annotations

from llm.base import ToolSpec

from . import get_kline, get_snapshot, place_decision

ALL_TOOLS: dict = {
    'place_decision': (place_decision.SPEC, place_decision.call),
    'get_kline': (get_kline.SPEC, get_kline.call),
    'get_snapshot': (get_snapshot.SPEC, get_snapshot.call),
}


def filter_allowed(tool_names: list[str]) -> dict:
    result = {'place_decision': ALL_TOOLS['place_decision']}
    for name in tool_names:
        if name in ALL_TOOLS:
            result[name] = ALL_TOOLS[name]
    return result
