"""AgentRunner — daily LLM decision loop with cache + validation."""
from __future__ import annotations

import hashlib
import json

from backtest.base import CachedDecision
from llm.base import Message
from validation.engine import ValidationEngine

from .prompt_builder import build_messages, prompt_hash


_MAX_TOOL_ITERATIONS = 8


def _portfolio_hash(portfolio: dict) -> str:
    """Stable hash of portfolio state for cache keying."""
    positions = portfolio.get('positions', {})
    sorted_positions = sorted(
        (code, info.get('shares', 0), info.get('avg_price', 0))
        for code, info in positions.items()
    )
    payload = json.dumps({
        'cash': round(portfolio.get('cash', 0), 2),
        'equity': round(portfolio.get('equity', 0), 2),
        'positions': sorted_positions,
    }, sort_keys=True).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()[:16]


class AgentRunner:
    def __init__(self, llm, engine: ValidationEngine | None = None,
                 max_iterations: int = _MAX_TOOL_ITERATIONS):
        self._llm = llm
        self._engine = engine or ValidationEngine()
        self._max_iterations = max_iterations

    def run_day(
        self,
        *,
        agent_id: str,
        date: str,
        portfolio: dict,
        market_context: dict,
        mark_prices: dict,
    ) -> list[dict]:
        """Return list of executed (validated/modified) decisions."""
        import storage

        agent = storage.agents().get(agent_id)
        if agent is None:
            raise ValueError(f'unknown agent_id={agent_id}')
        persona = storage.personas().get(agent.persona_id)
        pv = storage.prompt_versions().get_latest(agent_id)
        if pv is None:
            raise RuntimeError(f'agent {agent_id} has no prompt version')
        system_prompt = pv.system_prompt

        messages = build_messages(
            system_prompt=system_prompt,
            date=date,
            portfolio=portfolio,
            market_context=market_context,
            default_pool=persona.default_pool if persona else [],
        )
        p_hash = prompt_hash(messages)
        port_hash = _portfolio_hash(portfolio)
        cache_key = CachedDecision.build_key(agent_id, date, port_hash, p_hash)

        cache = storage.llm_cache()
        cached = cache.get(cache_key)
        if cached is not None:
            return list(cached.decisions)

        # Live LLM tool loop
        from tools import filter_allowed
        allowed = filter_allowed(persona.allowed_tools if persona else [])
        # filter_allowed returns dict[name, (SPEC, call)]; extract specs for LLM
        tool_specs = [spec for spec, _ in allowed.values()]

        decisions_executed: list[dict] = []
        convo = list(messages)

        for _ in range(self._max_iterations):
            resp = self._llm.chat(messages=convo, tools=tool_specs)
            if not resp.tool_calls:
                break

            # Append assistant turn so next LLM call sees its own prior output
            convo.extend(resp.messages)

            tool_results: list[Message] = []
            terminated = False
            for call in resp.tool_calls:
                if call.name == 'place_decision':
                    decision = dict(call.input)
                    # Normalize qty → shares for ValidationEngine.
                    # price: honour the LLM-provided value when present;
                    # fall back to mark_prices so position_max_pct can fire
                    # when the LLM explicitly includes a price in its decision.
                    decision.setdefault('shares', decision.get('qty', 0))
                    decision.setdefault('price', 0.0)
                    result = self._engine.validate(
                        agent_id=agent_id,
                        decision=decision,
                        portfolio=portfolio,
                        market_context=market_context,
                        persona_id=agent.persona_id,
                        model_id=agent.model_id,
                    )
                    if result.outcome != 'rejected' and result.decision_out:
                        decisions_executed.append(result.decision_out)
                    terminated = True
                    break
                # Non-terminator tool: just acknowledge (MVP keeps loop simple)
                tool_results.append(Message(
                    role='tool', content=json.dumps({'ack': True}),
                    tool_call_id=call.id,
                ))
            if terminated:
                break
            convo.extend(tool_results)

        cache.put(CachedDecision(
            agent_id=agent_id, date=date,
            portfolio_hash=port_hash, prompt_hash=p_hash,
            decisions=decisions_executed,
        ))
        return decisions_executed
