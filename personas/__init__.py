"""Registry of built-in personas."""
from __future__ import annotations

from .linyuan import PERSONA as LINYUAN
from .fuyou import PERSONA as FUYOU
from .buffet import PERSONA as BUFFET
from .soros import PERSONA as SOROS
from .quant_neutral import PERSONA as QUANT_NEUTRAL


ALL_PERSONAS: dict[str, dict] = {
    'linyuan': LINYUAN,
    'fuyou': FUYOU,
    'buffet': BUFFET,
    'soros': SOROS,
    'quant_neutral': QUANT_NEUTRAL,
}
