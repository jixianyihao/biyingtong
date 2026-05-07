"""Assemble LLM messages for an agent decision point + hash utility."""
from __future__ import annotations

import hashlib
import json
import logging

from llm.base import Message

log = logging.getLogger(__name__)

# Rough token estimator: ~3.5 chars per token for Chinese+English mixed content.
CHARS_PER_TOKEN = 3.5

# Reserve tokens for output + tool definitions. Input must stay below this.
DEFAULT_MAX_INPUT_TOKENS = 250_000


def _estimate_tokens(text: str) -> int:
    """Rough token count estimate for budget checks."""
    return int(len(text) / CHARS_PER_TOKEN)


def _compress_snapshot(
    snapshot: dict,
    budget_chars: int,
) -> dict:
    """Compress market snapshot to fit within a character budget.

    Strategy (progressive):
    1. Drop closes_last_30d array (biggest single item per stock)
    2. Drop financials (less critical for short-term)
    3. Drop technical indicators (can be re-fetched via tools)
    4. Drop kline summary entirely (keep just code list)
    """
    import copy
    compressed = copy.deepcopy(snapshot)
    stocks = compressed.get('stocks', {})
    if not stocks:
        return compressed

    def _total_snapshot_chars(s: dict) -> int:
        return len(json.dumps(s, ensure_ascii=False))

    # Stage 1: Remove closes_last_30d arrays
    if _total_snapshot_chars(compressed) <= budget_chars:
        return compressed
    log.info('Context budget tight — removing closes_last_30d arrays')
    for code, data in stocks.items():
        ks = data.get('kline_summary')
        if ks and 'closes_last_30d' in ks:
            del ks['closes_last_30d']

    if _total_snapshot_chars(compressed) <= budget_chars:
        return compressed

    # Stage 2: Remove financials
    log.info('Context budget tight — removing financials')
    for code, data in stocks.items():
        data.pop('financials', None)

    if _total_snapshot_chars(compressed) <= budget_chars:
        return compressed

    # Stage 3: Remove technical indicators
    log.info('Context budget tight — removing technical indicators')
    for code, data in stocks.items():
        data.pop('technical', None)

    if _total_snapshot_chars(compressed) <= budget_chars:
        return compressed

    # Stage 4: Remove kline summary entirely
    log.info('Context budget tight — removing kline summaries')
    for code, data in stocks.items():
        data.pop('kline_summary', None)

    return compressed


def build_messages(
    *,
    system_prompt: str,
    date: str,
    portfolio: dict,
    market_context: dict,
    default_pool: list[str],
    market_snapshot: dict | None = None,
    model_cutoff: str | None = None,
    max_input_tokens: int = DEFAULT_MAX_INPUT_TOKENS,
) -> list[Message]:
    """Return [system Message, user Message].

    Automatically compresses market_snapshot if the total estimated
    token count exceeds max_input_tokens.
    """
    cash = portfolio.get('cash', 0)
    equity = portfolio.get('equity', 0)
    positions = portfolio.get('positions', {})

    lines = [f'决策日期：{date}']
    lines.append(f'组合：现金 {cash:.0f}，总资产 {equity:.0f}')
    if positions:
        lines.append('当前持仓：')
        for code, info in positions.items():
            lines.append(
                f'  - {code} × {info.get("shares", 0)} 股（均价 '
                f'{info.get("avg_price", 0):.2f}）'
            )
    else:
        lines.append('当前无持仓。')
    lines.append(f'备选池：{", ".join(default_pool)}')
    if market_context:
        lines.append('市场快照：')
        for k, v in market_context.items():
            lines.append(f'  - {k}: {v}')
    has_snapshot = bool(market_snapshot and market_snapshot.get('stocks'))
    if has_snapshot:
        lines.append('')
        lines.append('研究数据（本日完整快照——K线/财务/技术指标已齐全）:')
        for code, data in market_snapshot['stocks'].items():
            lines.append(f'  {code}:')
            ks = data.get('kline_summary')
            if ks:
                lines.append(
                    f'    K线: latest={ks.get("latest_close")}, '
                    f'30d_return={ks.get("return_30d_pct")}%, '
                    f'vol={ks.get("volatility_30d_pct")}%, '
                    f'30d_high={ks.get("high_30d")}, '
                    f'30d_low={ks.get("low_30d")}'
                )
            fin = data.get('financials')
            if fin:
                fin_str = ', '.join(f'{k}={v}' for k, v in fin.items())
                lines.append(f'    财务: {fin_str}')
            tech = data.get('technical')
            if tech:
                tech_str = ', '.join(f'{k}={v}' for k, v in tech.items())
                lines.append(f'    技术: {tech_str}')
    lines.append('')
    if has_snapshot:
        lines.append(
            '上述研究数据已经涵盖常规决策所需的K线/财务/技术指标。'
            '请**直接**基于这份数据调用 place_decision（'
            'buy / sell / hold 三选一，含理由与完整思考）。'
            '除非数据明显缺失某个关键维度，不要重复调用 get_kline/'
            'get_financials/get_technical——snapshot 已经是今天的最新数据。'
        )
    else:
        lines.append(
            '使用工具调研后调用 place_decision 给出当日决策（'
            'buy / sell / hold 三选一，含理由与完整思考）。'
        )
    user_msg = '\n'.join(lines)

    # Append cutoff disclaimer if available (spec §11.5)
    if model_cutoff:
        final_system = (
            system_prompt
            + f'\n\n[元信息] 今天是 {date}，你的训练数据截止于 {model_cutoff}。'
            f'{model_cutoff} 之后发生的事件不在你的训练数据里——避免引用'
            f'任何未来信息或未来事后才知道的结果，仅基于截止前的知识 + 上面提供的研究数据决策。'
        )
    else:
        final_system = system_prompt

    # --- Token budget check + auto-compression ---
    total_text = final_system + user_msg
    estimated_tokens = _estimate_tokens(total_text)

    if estimated_tokens > max_input_tokens and has_snapshot:
        # Calculate how many chars we can afford for the snapshot
        non_snapshot_chars = len(final_system) + len(user_msg) - len(
            json.dumps(market_snapshot, ensure_ascii=False)
        )
        budget_chars = int(max_input_tokens * CHARS_PER_TOKEN) - non_snapshot_chars
        log.info(
            'Token budget exceeded (%d > %d) — compressing snapshot (budget=%d chars)',
            estimated_tokens, max_input_tokens, budget_chars,
        )
        compressed = _compress_snapshot(market_snapshot, budget_chars)
        # Rebuild user_msg with compressed snapshot
        market_snapshot = compressed
        # Rebuild from scratch with compressed data
        return build_messages(
            system_prompt=system_prompt,
            date=date,
            portfolio=portfolio,
            market_context=market_context,
            default_pool=default_pool,
            market_snapshot=compressed,
            model_cutoff=model_cutoff,
            max_input_tokens=max_input_tokens,
        )

    return [
        Message(role='system', content=final_system),
        Message(role='user', content=user_msg),
    ]


def prompt_hash(messages: list[Message]) -> str:
    payload = json.dumps(
        [{'role': m.role, 'content': m.content} for m in messages],
        ensure_ascii=False, sort_keys=True,
    ).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()[:16]
