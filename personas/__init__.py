"""Registry of built-in personas.

User 2026-04-26 dropped linyuan + buffet from default registry — value-investor
style was deemed unsuitable for the platform's quant-analyst focus. The .py
files remain importable so legacy tests can construct fixtures directly, but
they are NOT seeded into the default user-facing persona pool.
"""
from __future__ import annotations

from .fuyou import PERSONA as FUYOU
from .soros import PERSONA as SOROS
from .quant_neutral import PERSONA as QUANT_NEUTRAL
from .intraday_t0 import PERSONA as INTRADAY_T0
from .quant_sentiment import PERSONA as QUANT_SENTIMENT


ALL_PERSONAS: dict[str, dict] = {
    'fuyou': FUYOU,
    'soros': SOROS,
    'quant_neutral': QUANT_NEUTRAL,
    'intraday_t0': INTRADAY_T0,
    'quant_sentiment': QUANT_SENTIMENT,
}


def seed() -> int:
    """Idempotently upsert all built-in personas into storage.personas().

    Returns count of personas written.
    """
    from storage import personas as _personas_factory
    from storage.base import Persona

    store = _personas_factory()
    store.init_schema()

    for data in ALL_PERSONAS.values():
        persona = Persona(
            id=data['id'],
            name=data['name'],
            style_desc=data['style_desc'],
            system_prompt=data['system_prompt'],
            default_pool=data['default_pool'],
            pool_filter=data['pool_filter'],
            default_schedule=data['default_schedule'],
            default_rules=data['default_rules'],
            allowed_tools=data['allowed_tools'],
            is_builtin=data['is_builtin'],
        )
        store.upsert(persona)
    return len(ALL_PERSONAS)
