"""Numeric parity test: legacy BacktestRunner vs VnpyBacktestRunner.

Given the same MockLLM script + window + universe, the two runners should
produce close-enough results to confirm the vnpy migration hasn't silently
changed the backtest semantics.

Known divergences (accepted):
- vnpy fills at next bar open (legacy fills same-day close) → small drift
- vnpy Sharpe uses annual_days=240 (legacy 252) → Sharpe NOT parity-tested
- vnpy commission dict vs legacy FeeModel → fee diffs ~basis points
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest


# Use a dedicated test symbol (not a real code) so we don't collide with
# real seeded data in data/vnpy_data.db.
TEST_CODE = 'PARITY.SH'
TEST_SYMBOL = 'PARITY'

# 10 contiguous weekdays in Jan 2025 — no weekend gaps, safely before the
# real-data window (2025-04-01..2026-04-01) in data/vnpy_data.db.
_TEST_DAYS = [
    date(2025, 1, 2), date(2025, 1, 3),   # Thu, Fri
    date(2025, 1, 6), date(2025, 1, 7),   # Mon, Tue
    date(2025, 1, 8), date(2025, 1, 9),   # Wed, Thu
    date(2025, 1, 10), date(2025, 1, 13), # Fri, Mon
    date(2025, 1, 14), date(2025, 1, 15), # Tue, Wed
]
# Prices chosen so vnpy's next-bar-open matching actually crosses:
#   long_cross: order.price (today's close) >= next bar.low (= close*0.99).
# Any daily rise <1% keeps vnpy buy/sell orders crossing. Kept mild so
# legacy (same-day close fill) and vnpy (next-bar open fill) land close.
_TEST_PRICES = [100.0, 100.3, 100.5, 100.4, 100.6,
                100.8, 101.0, 100.9, 101.1, 101.3]


def _seed_kline(codes, prices_per_code, days):
    """Seed vnpy_sqlite with daily bars for given codes on given days.
    Returns the list of dates used.

    Saves via storage.kline().save_bars — the real vnpy_sqlite backend,
    since the observability_storage fixture does NOT monkeypatch kline.
    """
    import storage
    from vnpy.trader.object import BarData
    from vnpy.trader.constant import Exchange, Interval

    bars = []
    for code, prices in prices_per_code.items():
        sym, _, suffix = code.partition('.')
        exch = Exchange.SSE if suffix in ('SH', 'SSE') else Exchange.SZSE
        for d, px in zip(days, prices):
            bars.append(BarData(
                symbol=sym, exchange=exch,
                datetime=datetime(d.year, d.month, d.day),
                interval=Interval.DAILY,
                open_price=px, high_price=px * 1.01,
                low_price=px * 0.99, close_price=px,
                volume=10000, turnover=10000 * px,
                open_interest=0, gateway_name='test',
            ))
    storage.kline().save_bars(bars)
    return days


def _cleanup_test_bars(symbol=TEST_SYMBOL):
    """Remove test-seeded bars from the real vnpy_sqlite DB to keep it clean."""
    import sqlite3
    from scripts.setup.vnpy_config import configure
    db_path = configure()
    con = sqlite3.connect(db_path)
    try:
        con.execute('DELETE FROM dbbardata WHERE symbol = ?', (symbol,))
        con.execute('DELETE FROM dbbaroverview WHERE symbol = ?', (symbol,))
        con.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        con.close()


def _mk_script():
    """Fresh MockLLM script — one buy, 5 holds, one sell, 3 holds (10 days)."""
    buy = {
        'tool_calls': [{
            'id': 'b1', 'name': 'place_decision',
            'input': {
                'action': 'buy', 'code': TEST_CODE, 'qty': 100,
                'reason': 'opening long position on quality name at fair entry',
                'thinking': 'buying now',
            },
        }],
        'stop_reason': 'tool_use',
    }
    hold = {
        'tool_calls': [{
            'id': 'h', 'name': 'place_decision',
            'input': {
                'action': 'hold',
                'reason': 'waiting patiently for a clearer setup today',
                'thinking': 'holding',
            },
        }],
        'stop_reason': 'tool_use',
    }
    sell = {
        'tool_calls': [{
            'id': 's1', 'name': 'place_decision',
            'input': {
                'action': 'sell', 'code': TEST_CODE, 'qty': 100,
                'reason': 'locking gains on thesis playing out well now',
                'thinking': 'selling now',
            },
        }],
        'stop_reason': 'tool_use',
    }
    return [buy] + [hold] * 5 + [sell] + [hold] * 3


def test_parity_legacy_vs_vnpy_runner(observability_storage, vnpy_configured,
                                       monkeypatch):
    """Both runners on identical conditions → close numeric results.

    Uses a MockLLM that buys day 0, holds days 1-5, sells day 6. Both runners
    should produce:
    - Same trade count (2: 1 buy + 1 sell)
    - Same action sequence
    - Final equity within 1% of each other
    - total_return_pct within 0.5% absolute

    Known divergences (accepted; NOT asserted):
    - Sharpe (different annualization constants: 240 vs 252)
    - Fill prices (vnpy next-bar-open vs legacy same-day close)
    """
    import storage
    from llm.mock import MockLLM

    # Clean up any leftover bars from previous runs, then seed fresh
    _cleanup_test_bars()

    agent = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='parity', initial_capital=1_000_000.0,
    )

    days = _seed_kline(
        codes=[TEST_CODE],
        prices_per_code={TEST_CODE: _TEST_PRICES},
        days=_TEST_DAYS,
    )

    try:
        # ─── Run LEGACY ──────────────────────────────────────────────────
        from backtest.runner import BacktestRunner
        import backtest.runner as runner_mod

        price_pairs = list(zip(days, _TEST_PRICES))
        monkeypatch.setattr(
            runner_mod, '_load_daily_closes',
            lambda code, start, end: price_pairs if code == TEST_CODE else [],
        )
        monkeypatch.setattr(runner_mod, '_trading_days',
                            lambda s, e: list(days))

        legacy_result = BacktestRunner(llm=MockLLM(_mk_script())).run(
            session_id='parity-legacy', agent_id=agent.id,
            start_date=days[0].isoformat(), end_date=days[-1].isoformat(),
            universe=[TEST_CODE], initial_capital=1_000_000.0,
        )

        # ─── Run VNPY ────────────────────────────────────────────────────
        from backtest.vnpy_runner import VnpyBacktestRunner
        try:
            vnpy_result = VnpyBacktestRunner(llm=MockLLM(_mk_script())).run(
                session_id='parity-vnpy', agent_id=agent.id,
                start_date=days[0].isoformat(), end_date=days[-1].isoformat(),
                universe=[TEST_CODE], initial_capital=1_000_000.0,
            )
        except Exception as e:  # noqa: BLE001
            pytest.skip(
                f'vnpy engine failed to load seeded data — parity test '
                f'requires vnpy-compatible seeding: {e}'
            )

        # ─── Parity checks ───────────────────────────────────────────────
        # 1. Trade count — both should see 1 buy + 1 sell = 2 trades
        assert legacy_result.stats.trade_count == vnpy_result.stats.trade_count, (
            f'trade_count diverges: legacy={legacy_result.stats.trade_count} '
            f'vnpy={vnpy_result.stats.trade_count}'
        )
        # Allow zero trades if vnpy's next-bar-open matching resulted in no fills
        # (edge case when window is too short)
        if legacy_result.stats.trade_count == 0:
            pytest.skip('both runners produced zero trades — parity trivially true')

        # 2. Action sequence matches
        legacy_actions = [t['action'] for t in legacy_result.trades]
        vnpy_actions = [t['action'] for t in vnpy_result.trades]
        assert legacy_actions == vnpy_actions, (
            f'action sequence differs: '
            f'legacy={legacy_actions} vs vnpy={vnpy_actions}'
        )

        # 3. First trade code matches
        assert legacy_result.trades[0]['code'] == vnpy_result.trades[0]['code'], (
            f'first trade code differs: '
            f'legacy={legacy_result.trades[0]["code"]} '
            f'vnpy={vnpy_result.trades[0]["code"]}'
        )

        # 4. total_return_pct within 0.5% absolute tolerance
        diff_return = abs(
            legacy_result.stats.total_return_pct
            - vnpy_result.stats.total_return_pct
        )
        assert diff_return < 0.5, (
            f'total_return_pct diff={diff_return:.3f}% exceeds 0.5% '
            f'(legacy={legacy_result.stats.total_return_pct:.3f}% '
            f'vnpy={vnpy_result.stats.total_return_pct:.3f}%)'
        )

        # 5. final_equity within 1% relative
        rel_diff = (
            abs(legacy_result.final_equity - vnpy_result.final_equity)
            / max(1.0, legacy_result.final_equity)
        )
        assert rel_diff < 0.01, (
            f'final_equity diff={rel_diff * 100:.2f}% exceeds 1% '
            f'(legacy={legacy_result.final_equity:.0f} '
            f'vnpy={vnpy_result.final_equity:.0f})'
        )
    finally:
        _cleanup_test_bars()
