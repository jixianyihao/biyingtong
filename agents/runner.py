"""AgentRunner — daily LLM decision loop with cache + validation."""
from __future__ import annotations

import hashlib
import json

from backtest.base import CachedDecision
from llm.base import Message
from validation.engine import ValidationEngine

from .prompt_builder import build_messages, prompt_hash


_MAX_TOOL_ITERATIONS = 4  # snapshot pre-loads research; LLM should decide within a few turns


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
        self.last_thinking: dict | None = None

    def run_day(
        self,
        *,
        agent_id: str,
        date: str,
        portfolio: dict,
        market_context: dict,
        mark_prices: dict,
        market_snapshot: dict | None = None,
        on_event=None,
    ) -> list[dict]:
        """Return list of executed (validated/modified) decisions.

        If ``on_event`` is provided, it is called with event dicts of kind
        ``tool_call``, ``decision``, or ``blocked`` as the daily loop runs.
        Each event includes ``kind``, ``agent_id``, ``date``, and kind-specific
        fields. See P3-D SSE plan.
        """
        import storage

        def _emit(kind: str, **kwargs):
            if on_event is None:
                return
            on_event({'kind': kind, 'agent_id': agent_id,
                      'date': date, **kwargs})

        agent = storage.agents().get(agent_id)
        if agent is None:
            raise ValueError(f'unknown agent_id={agent_id}')
        persona = storage.personas().get(agent.persona_id)
        pv = storage.prompt_versions().get_latest(agent_id)
        if pv is None:
            raise RuntimeError(f'agent {agent_id} has no prompt version')
        system_prompt = pv.system_prompt

        model = storage.models().get(agent.model_id) if agent.model_id else None
        model_cutoff = model.training_cutoff if model else None

        messages = build_messages(
            system_prompt=system_prompt,
            date=date,
            portfolio=portfolio,
            market_context=market_context,
            default_pool=persona.default_pool if persona else [],
            market_snapshot=market_snapshot,
            model_cutoff=model_cutoff,
        )
        p_hash = prompt_hash(messages)
        port_hash = _portfolio_hash(portfolio)
        cache_key = CachedDecision.build_key(agent_id, date, port_hash, p_hash)

        # P3-A thinking capture
        thinking_reasoning: list[str] = []
        thinking_tool_calls: list[dict] = []
        thinking_decisions: list[dict] = []

        cache = storage.llm_cache()
        cached = cache.get(cache_key)
        if cached is not None:
            self.last_thinking = {
                'reasoning': '(cached — no LLM call)',
                'tool_calls': [],
                'decisions': [
                    {'action': d.get('action'), 'code': d.get('code'),
                     'shares': d.get('shares'), 'price': d.get('price'),
                     'outcome': 'cached',
                     'reasoning': d.get('reason') or d.get('reasoning')}
                    for d in cached.decisions
                ],
            }
            return list(cached.decisions)

        # Live LLM tool loop
        from tools import filter_allowed
        allowed = filter_allowed(persona.allowed_tools if persona else [])
        # When snapshot is provided, strip research tools — the LLM must decide
        # from the pre-loaded data. Empirical finding: GLM ignores prompt
        # directives and calls tools anyway; removing them from the schema is
        # the only way to enforce single-turn decisions.
        if market_snapshot and market_snapshot.get('stocks'):
            research_tools = {'get_kline', 'get_financials', 'get_technical',
                              'get_snapshot', 'get_index', 'get_news'}
            allowed = {name: v for name, v in allowed.items()
                       if name not in research_tools}
        # filter_allowed returns dict[name, (SPEC, call)]; extract specs for LLM
        tool_specs = [spec for spec, _ in allowed.values()]

        decisions_executed: list[dict] = []
        convo = list(messages)

        for _ in range(self._max_iterations):
            resp = self._llm.chat(messages=convo, tools=tool_specs)

            # Capture assistant text for thinking
            for m in resp.messages:
                if m.content:
                    thinking_reasoning.append(m.content)

            if not resp.tool_calls:
                break

            # Preserve the FULL assistant turn (text + tool_use) in conversation —
            # Anthropic-compatible APIs reject conversations where assistant
            # tool_use is missing or where tool_result has the wrong role.
            assistant_content: list = []
            for m in resp.messages:
                assistant_content.append({'type': 'text', 'text': m.content})
            for tc in resp.tool_calls:
                assistant_content.append({
                    'type': 'tool_use', 'id': tc.id,
                    'name': tc.name, 'input': tc.input,
                })
            if assistant_content:
                convo.append(Message(role='assistant', content=assistant_content))

            # Tool results are a SINGLE user message with tool_result blocks.
            tool_result_blocks: list = []
            terminated = False
            for call in resp.tool_calls:
                if call.name == 'place_decision':
                    decision = dict(call.input)
                    decision.setdefault('shares', decision.get('qty', 0))
                    decision.setdefault('price',
                                        mark_prices.get(decision.get('code'),
                                                        0.0))
                    result = self._engine.validate(
                        agent_id=agent_id,
                        decision=decision,
                        portfolio=portfolio,
                        market_context=market_context,
                        rules_override=agent.rules_override,
                        persona_id=agent.persona_id,
                        model_id=agent.model_id,
                    )
                    # Record decision regardless of validation outcome so the UI
                    # can show rejected attempts too.
                    thinking_decisions.append({
                        'action': decision.get('action'),
                        'code': decision.get('code'),
                        'shares': decision.get('shares'),
                        'price': decision.get('price'),
                        'outcome': result.outcome,
                        'reasoning': decision.get('reason')
                                     or decision.get('reasoning'),
                    })
                    if result.outcome == 'rejected':
                        reason_text = '; '.join(
                            v.reason for v in result.violations
                        ) if result.violations else 'rejected by validation'
                        _emit('blocked',
                              decision_input={
                                  'action': decision.get('action'),
                                  'code': decision.get('code'),
                                  'shares': decision.get('shares'),
                              },
                              reason=reason_text)
                    else:
                        _emit('decision',
                              action=decision.get('action'),
                              code=decision.get('code'),
                              shares=decision.get('shares'),
                              price=decision.get('price'),
                              outcome=result.outcome)
                    if result.outcome != 'rejected' and result.decision_out:
                        decisions_executed.append(result.decision_out)
                    terminated = True
                    break
                # Non-place_decision tool calls are research/query tools —
                # surface them in the thinking drawer.
                thinking_tool_calls.append({
                    'name': call.name,
                    'input': call.input or {},
                })
                _emit('tool_call', tool_name=call.name,
                      tool_input=call.input or {})
                # Execute the real tool via tools registry
                entry = allowed.get(call.name)
                if entry is None:
                    tool_result_blocks.append({
                        'type': 'tool_result',
                        'tool_use_id': call.id,
                        'content': json.dumps({
                            'error': f'tool {call.name!r} not allowed for this agent',
                        }),
                        'is_error': True,
                    })
                    continue
                _spec, tool_fn = entry
                try:
                    result = tool_fn(call.input or {})
                    tool_result_blocks.append({
                        'type': 'tool_result',
                        'tool_use_id': call.id,
                        'content': json.dumps(result, ensure_ascii=False,
                                              default=str),
                    })
                except Exception as e:  # noqa: BLE001
                    tool_result_blocks.append({
                        'type': 'tool_result',
                        'tool_use_id': call.id,
                        'content': json.dumps({
                            'error': f'{type(e).__name__}: {e}',
                        }),
                        'is_error': True,
                    })
            if terminated:
                break
            if tool_result_blocks:
                convo.append(Message(role='user', content=tool_result_blocks))

        cache.put(CachedDecision(
            agent_id=agent_id, date=date,
            portfolio_hash=port_hash, prompt_hash=p_hash,
            decisions=decisions_executed,
        ))
        self.last_thinking = {
            'reasoning': '\n'.join(thinking_reasoning).strip(),
            'tool_calls': thinking_tool_calls,
            'decisions': thinking_decisions,
        }
        return decisions_executed
