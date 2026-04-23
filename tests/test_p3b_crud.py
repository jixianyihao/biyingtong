"""P3-B CRUD: agent/persona update + delete + prompt rollback."""
from __future__ import annotations


def test_agent_store_protocol_has_update_method():
    from storage.base import AgentStore
    assert 'update' in dir(AgentStore)


def test_agent_store_protocol_has_delete_method():
    from storage.base import AgentStore
    assert 'delete' in dir(AgentStore)


def test_agent_store_protocol_has_set_current_prompt_version_method():
    from storage.base import AgentStore
    assert 'set_current_prompt_version' in dir(AgentStore)


def test_persona_store_protocol_has_delete_method():
    from storage.base import PersonaStore
    assert 'delete' in dir(PersonaStore)


def test_prompt_version_store_protocol_has_rollback_method():
    from storage.base import PromptVersionStore
    assert 'rollback' in dir(PromptVersionStore)
