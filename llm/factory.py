"""Build LLM adapter from model_id + server-side env credentials.

Credentials are read from environment variables — never accepted via HTTP.
Supported providers:
- 'anthropic' / 'anthropic_compatible' → ClaudeLLM (ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL)
- 'openrouter' / 'openai' → OpenAILLM (OPENROUTER_API_KEY or OPENAI_API_KEY, base_url from ModelInfo or env)
"""
from __future__ import annotations

import os


class LLMNotConfiguredError(RuntimeError):
    """Raised when env vars are missing for the requested provider."""


def build_llm(model_id: str):
    """Look up ModelInfo by id, return a configured LLMBase adapter."""
    import storage
    info = storage.models().get(model_id)
    if info is None:
        raise ValueError(f'unknown model_id: {model_id}')

    provider = (info.provider or '').lower()
    if provider in ('anthropic', 'anthropic_compatible'):
        token = os.environ.get('ANTHROPIC_AUTH_TOKEN') or os.environ.get('ANTHROPIC_API_KEY')
        base_url = os.environ.get('ANTHROPIC_BASE_URL')
        if not token:
            raise LLMNotConfiguredError(
                'ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY required for provider '
                + provider)
        from .claude import ClaudeLLM
        return ClaudeLLM(
            model_id=info.api_model_id,
            auth_token=token if 'AUTH_TOKEN' in os.environ else None,
            api_key=token if 'API_KEY' in os.environ and 'AUTH_TOKEN' not in os.environ else None,
            base_url=base_url,
            training_cutoff=info.training_cutoff,
        )

    if provider == 'openrouter':
        key = os.environ.get('OPENROUTER_API_KEY')
        if not key:
            raise LLMNotConfiguredError('OPENROUTER_API_KEY required for openrouter')
        from .openai_adapter import OpenAILLM
        return OpenAILLM(
            model_id=info.api_model_id, api_key=key,
            base_url='https://openrouter.ai/api/v1',
            provider='openrouter',
            training_cutoff=info.training_cutoff,
            extra_body={'provider': {'sort': 'throughput'}},
        )

    if provider == 'openai':
        key = os.environ.get('OPENAI_API_KEY')
        if not key:
            raise LLMNotConfiguredError('OPENAI_API_KEY required for openai')
        from .openai_adapter import OpenAILLM
        return OpenAILLM(
            model_id=info.api_model_id, api_key=key,
            provider='openai',
            training_cutoff=info.training_cutoff,
        )

    raise ValueError(f'no adapter for provider {provider!r}')
