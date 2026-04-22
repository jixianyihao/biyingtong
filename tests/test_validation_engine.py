"""ValidationEngine orchestration + audit integration."""
import pytest


@pytest.fixture
def wired(tmp_path):
    """Set up stores + import handlers (side-effect registers)."""
    import storage
    from storage.sqlite_redline import SQLiteRedLineStore
    from storage.sqlite_stock_status import SQLiteStockStatusStore
    from storage.sqlite_audit import SQLiteAuditStore
    from validation.base import DEFAULT_REDLINES

    rl = SQLiteRedLineStore(tmp_path=tmp_path); rl.init_schema()
    ss = SQLiteStockStatusStore(tmp_path=tmp_path); ss.init_schema()
    au = SQLiteAuditStore(tmp_path=tmp_path); au.init_schema()
    storage.set_redline(rl)
    storage.set_stock_status(ss)
    storage.set_audit(au)

    from validation import rules
    rules.reset()
    # Re-register all handlers after reset by importing and instantiating their Handler classes
    from validation.handlers.position_max_pct import Handler as PositionMaxPctHandler
    from validation.handlers.ban_st import Handler as BanStHandler
    from validation.handlers.max_holdings import Handler as MaxHoldingsHandler
    from validation.handlers.daily_loss_limit_pct import Handler as DailyLossLimitPctHandler

    rules.register(PositionMaxPctHandler())
    rules.register(BanStHandler())
    rules.register(MaxHoldingsHandler())
    rules.register(DailyLossLimitPctHandler())

    rl.set({**DEFAULT_REDLINES, 'position_max_pct': 15.0, 'ban_st': True})
    return {'redline': rl, 'stock_status': ss, 'audit': au}


def _portfolio(positions=None, equity=1_000_000, cash=1_000_000):
    return {'equity': equity, 'cash': cash, 'positions': positions or {}}


def _req(decision, portfolio=None, market_context=None, override=None):
    from validation.engine import ValidationEngine
    return ValidationEngine().validate(
        agent_id='a1',
        decision=decision,
        portfolio=portfolio or _portfolio(),
        market_context=market_context or {},
        rules_override=override or {},
    )


def test_approved_path(wired):
    out = _req(decision={'action': 'buy', 'code': 'X.SH',
                         'shares': 100, 'price': 10.0})
    assert out.outcome == 'approved'
    assert out.decision_out == {'action': 'buy', 'code': 'X.SH',
                                'shares': 100, 'price': 10.0}
    assert out.violations == ()


def test_rejected_on_redline_ban_st(wired):
    from storage.base import StockStatusRow
    wired['stock_status'].upsert(StockStatusRow(
        code='ST.SH', name='*ST X', is_st=True,
        is_suspended=False, is_delisted=False,
    ))
    out = _req(decision={'action': 'buy', 'code': 'ST.SH',
                         'shares': 100, 'price': 10.0})
    assert out.outcome == 'rejected'
    assert out.decision_out is None
    assert any(v.rule_id == 'ban_st' for v in out.violations)


def test_modified_on_position_max_pct(wired):
    out = _req(decision={'action': 'buy', 'code': 'X.SH',
                         'shares': 200, 'price': 1000.0})
    assert out.outcome == 'modified'
    assert out.decision_out['shares'] == 150
    assert any(v.rule_id == 'position_max_pct' and v.severity == 'modify'
               for v in out.violations)


def test_reject_wins_over_modify(wired):
    """If any handler rejects, modifications are discarded."""
    from storage.base import StockStatusRow
    wired['stock_status'].upsert(StockStatusRow(
        code='ST.SH', name='*ST X', is_st=True,
        is_suspended=False, is_delisted=False,
    ))
    out = _req(decision={'action': 'buy', 'code': 'ST.SH',
                         'shares': 200, 'price': 1000.0})
    assert out.outcome == 'rejected'
    assert out.decision_out is None


def test_audit_row_written_on_approve(wired):
    import storage
    _req(decision={'action': 'buy', 'code': 'X.SH',
                   'shares': 10, 'price': 10.0})
    rows = storage.audit().query_by_agent('a1')
    assert len(rows) == 1
    assert rows[0]['kind'] == 'validation'
    assert rows[0]['details']['outcome'] == 'approved'


def test_audit_row_captures_violations(wired):
    import storage
    _req(decision={'action': 'buy', 'code': 'X.SH',
                   'shares': 200, 'price': 1000.0})
    row = storage.audit().query_by_agent('a1')[0]
    assert row['details']['outcome'] == 'modified'
    v_ids = [v['rule_id'] for v in row['details']['violations']]
    assert 'position_max_pct' in v_ids


def test_override_narrows_rule(wired):
    out = _req(
        decision={'action': 'buy', 'code': 'X.SH',
                  'shares': 100, 'price': 1000.0},
        override={'position_max_pct': 5.0},
    )
    assert out.outcome == 'modified'
    assert out.decision_out['shares'] == 50


def test_override_cannot_widen(wired):
    """RedLine is 15; override 40 must be clamped to 15."""
    out = _req(
        decision={'action': 'buy', 'code': 'X.SH',
                  'shares': 200, 'price': 1000.0},
        override={'position_max_pct': 40.0},
    )
    assert out.outcome == 'modified'
    assert out.decision_out['shares'] == 150
