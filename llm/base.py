"""Canonical types + abstract base class for vendor-neutral LLM adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


@dataclass
class Message:
    role: Literal['system', 'user', 'assistant', 'tool']
    content: str | list
    tool_call_id: str | None = None


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int
    cached_read_tokens: int = 0
    cached_write_tokens: int = 0


@dataclass
class LLMResponse:
    messages: list[Message]
    tool_calls: list[ToolCall]
    stop_reason: str
    usage: Usage


class LLMError(Exception):
    def __init__(self, provider: str, kind: str, message: str, retryable: bool = False):
        self.provider = provider
        self.kind = kind
        self.retryable = retryable
        super().__init__(message)


class LLMBase(ABC):
    provider: str
    model_id: str
    training_cutoff: str

    @abstractmethod
    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        cacheable_prefix_len: int = 0,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> LLMResponse: ...
