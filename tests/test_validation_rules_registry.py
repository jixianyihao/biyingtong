"""RuleHandler Protocol + registry."""
import pytest


def _dummy_req():
    from validation.base import ValidationRequest
    return ValidationRequest(
        agent_id='a1', decision={}, portfolio={}, market_context={},
        rules={'position_max_pct': 15.0},
    )


def test_register_then_get():
    from validation import rules

    rules.reset()

    class FakeHandler:
        RULE_ID = 'fake'

        def check(self, req):
            return None

    rules.register(FakeHandler())
    assert rules.get('fake').__class__.__name__ == 'FakeHandler'


def test_list_all_returns_registered():
    from validation import rules
    rules.reset()

    class A:
        RULE_ID = 'a'
        def check(self, req): return None

    class B:
        RULE_ID = 'b'
        def check(self, req): return None

    rules.register(A())
    rules.register(B())
    assert {h.RULE_ID for h in rules.list_all()} == {'a', 'b'}


def test_register_same_id_replaces():
    from validation import rules
    rules.reset()

    class H1:
        RULE_ID = 'dup'
        def check(self, req): return None

    class H2:
        RULE_ID = 'dup'
        def check(self, req): return None

    rules.register(H1())
    rules.register(H2())
    assert rules.get('dup').__class__.__name__ == 'H2'
    assert len(rules.list_all()) == 1


def test_get_unknown_returns_none():
    from validation import rules
    rules.reset()
    assert rules.get('nope') is None


def test_register_rejects_handler_without_rule_id():
    from validation import rules
    rules.reset()

    class Bad:
        def check(self, req): return None

    with pytest.raises(TypeError):
        rules.register(Bad())
