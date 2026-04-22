"""Validation core dataclasses + apply_override semantics."""


def test_defaults_expose_expected_keys():
    from validation.base import DEFAULT_REDLINES, DEFAULT_QUALITY_GATE
    # Spec § 7.1
    assert 'position_max_pct' in DEFAULT_REDLINES
    assert 'ban_st' in DEFAULT_REDLINES
    assert 'daily_loss_max_pct' in DEFAULT_REDLINES
    # Spec § 7.4
    assert 'min_sharpe' in DEFAULT_QUALITY_GATE
    assert 'max_drawdown_pct' in DEFAULT_QUALITY_GATE


def test_apply_override_narrows_upper_bound():
    from validation.base import apply_override
    redline = {'position_max_pct': 15.0}
    assert apply_override(redline, {'position_max_pct': 10.0}) \
        == {'position_max_pct': 10.0}


def test_apply_override_clamps_attempt_to_widen_upper_bound():
    from validation.base import apply_override
    redline = {'position_max_pct': 15.0}
    assert apply_override(redline, {'position_max_pct': 40.0}) \
        == {'position_max_pct': 15.0}


def test_apply_override_raises_lower_bound_only():
    from validation.base import apply_override
    redline = {'cash_min_pct': 5.0}
    assert apply_override(redline, {'cash_min_pct': 10.0}) \
        == {'cash_min_pct': 10.0}
    assert apply_override(redline, {'cash_min_pct': 2.0}) \
        == {'cash_min_pct': 5.0}


def test_apply_override_ban_toggle_is_or_not_override():
    from validation.base import apply_override
    assert apply_override({'ban_st': True}, {'ban_st': False}) == {'ban_st': True}
    assert apply_override({'ban_st': False}, {'ban_st': True}) == {'ban_st': True}
    assert apply_override({'ban_st': False}, {'ban_st': False}) == {'ban_st': False}


def test_apply_override_passes_through_unknown_keys_from_override():
    """Persona-specific rules (e.g., max_holdings) not in RedLine flow through."""
    from validation.base import apply_override
    result = apply_override({'position_max_pct': 15.0}, {'max_holdings': 10})
    assert result == {'position_max_pct': 15.0, 'max_holdings': 10}


def test_violation_and_result_dataclasses_exist():
    from validation.base import Violation, ValidationRequest, ValidationResult
    v = Violation(
        rule_id='position_max_pct', severity='modify',
        reason='shrunk', modification={'shares': 300},
    )
    assert v.rule_id == 'position_max_pct'
    import dataclasses
    assert dataclasses.is_dataclass(ValidationRequest)
    assert dataclasses.is_dataclass(ValidationResult)


def test_audit_entry_fields():
    from validation.base import AuditEntry
    e = AuditEntry(
        kind='validation', agent_id='a1', details={'x': 1},
    )
    assert e.kind == 'validation'
    assert e.agent_id == 'a1'
    assert e.persona_id is None
