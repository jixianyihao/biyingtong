"""ValidationEngine — orchestrate RedLine + override + handlers + audit."""
from __future__ import annotations

from dataclasses import asdict

from .base import (
    AuditEntry, ValidationRequest, ValidationResult, Violation,
    apply_override,
)
from . import rules as _rules


class ValidationEngine:
    def validate(
        self,
        *,
        agent_id: str,
        decision: dict,
        portfolio: dict,
        market_context: dict,
        rules_override: dict | None = None,
        persona_id: str | None = None,
        model_id: str | None = None,
    ) -> ValidationResult:
        import storage
        redline = storage.redline().get()
        effective = apply_override(redline, rules_override)

        req = ValidationRequest(
            agent_id=agent_id, decision=dict(decision),
            portfolio=portfolio, market_context=market_context,
            rules=effective, persona_id=persona_id, model_id=model_id,
        )

        violations: list[Violation] = []
        for rule_id in effective:
            handler = _rules.get(rule_id)
            if handler is None:
                continue
            v = handler.check(req)
            if v is not None:
                violations.append(v)

        if any(v.severity == 'reject' for v in violations):
            outcome = 'rejected'
            decision_out = None
        elif any(v.severity == 'modify' for v in violations):
            outcome = 'modified'
            decision_out = dict(decision)
            for v in violations:
                if v.severity == 'modify' and v.modification:
                    decision_out.update(v.modification)
        else:
            outcome = 'approved'
            decision_out = dict(decision)

        storage.audit().log(AuditEntry(
            kind='validation',
            agent_id=agent_id,
            persona_id=persona_id,
            model_id=model_id,
            details={
                'outcome': outcome,
                'decision_in': dict(decision),
                'decision_out': decision_out,
                'violations': [asdict(v) for v in violations],
                'effective_rules': effective,
            },
        ))

        return ValidationResult(
            outcome=outcome,
            decision_out=decision_out,
            violations=tuple(violations),
        )
