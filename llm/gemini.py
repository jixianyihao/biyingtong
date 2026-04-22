"""Google Gemini adapter."""
from __future__ import annotations

from .base import LLMBase, LLMError, LLMResponse, Message, ToolCall, ToolSpec, Usage


def _build_model(model_id: str, api_key: str, tools_config, system_instruction):
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name=model_id,
        tools=tools_config,
        system_instruction=system_instruction,
    )


_STOP_MAP = {'STOP': 'end_turn', 'MAX_TOKENS': 'max_tokens',
             'SAFETY': 'error', 'RECITATION': 'error', 'OTHER': 'other'}


class GeminiLLM(LLMBase):
    provider = 'gemini'

    def __init__(self, model_id: str, api_key: str, training_cutoff: str = '2025-08-31'):
        self.model_id = model_id
        self.training_cutoff = training_cutoff
        self._api_key = api_key

    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        cacheable_prefix_len: int = 0,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        system_msgs = [m for m in messages if m.role == 'system']
        other_msgs = [m for m in messages if m.role != 'system']

        sys_text = None
        if system_msgs:
            sys_text = '\n\n'.join(
                m.content if isinstance(m.content, str) else str(m.content)
                for m in system_msgs
            )

        tools_config = None
        if tools:
            tools_config = [{
                'function_declarations': [
                    {'name': t.name, 'description': t.description,
                     'parameters': t.input_schema}
                    for t in tools
                ],
            }]

        try:
            model = _build_model(
                model_id=self.model_id, api_key=self._api_key,
                tools_config=tools_config, system_instruction=sys_text,
            )
        except Exception as e:  # noqa: BLE001
            raise LLMError('gemini', 'other', f'build model failed: {e}') from e

        history = []
        for m in other_msgs:
            content_str = m.content if isinstance(m.content, str) else str(m.content)
            history.append({
                'role': 'model' if m.role == 'assistant' else m.role,
                'parts': [{'text': content_str}],
            })

        try:
            raw = model.generate_content(
                history,
                generation_config={
                    'temperature': temperature,
                    'max_output_tokens': max_tokens,
                },
            )
        except Exception as e:  # noqa: BLE001
            raise LLMError('gemini', 'other', str(e)) from e

        reply: list[Message] = []
        tool_calls: list[ToolCall] = []
        has_fc = False
        cand = raw.candidates[0] if raw.candidates else None

        if cand:
            for i, part in enumerate(cand.content.parts):
                if getattr(part, 'text', None):
                    reply.append(Message(role='assistant', content=part.text))
                fc = getattr(part, 'function_call', None)
                if fc:
                    has_fc = True
                    tool_calls.append(ToolCall(
                        id=f'gemini_tc_{i}',
                        name=fc.name,
                        input=dict(fc.args) if fc.args else {},
                    ))

        finish = getattr(cand, 'finish_reason', 'STOP') if cand else 'STOP'
        finish_str = finish.name if hasattr(finish, 'name') else str(finish)
        stop = _STOP_MAP.get(finish_str, 'other')
        if has_fc:
            stop = 'tool_use'

        um = raw.usage_metadata
        usage = Usage(
            input_tokens=getattr(um, 'prompt_token_count', 0),
            output_tokens=getattr(um, 'candidates_token_count', 0),
            cached_read_tokens=getattr(um, 'cached_content_token_count', 0) or 0,
        )

        return LLMResponse(messages=reply, tool_calls=tool_calls,
                           stop_reason=stop, usage=usage)
