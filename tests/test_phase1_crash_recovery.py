"""Flask startup crash recovery for deployed agents."""
from __future__ import annotations

import pytest


@pytest.fixture
def _tmp_deployed_agents(observability_storage, tmp_path):
    """Swap in a tmp_path-scoped DeployedAgentStore so we don't touch
    the real data/agent_state.db. Mirrors deploy_storage in test_p3f_phase1.py.
    """
    import storage
    from storage.sqlite_deployed_agents import SQLiteDeployedAgentStore
    d = SQLiteDeployedAgentStore(tmp_path=tmp_path)
    d.init_schema()
    storage.set_deployed_agents(d)
    return tmp_path


def test_pid_alive_false_for_nonexistent_pid():
    from app import _pid_alive
    # PID 0 is invalid on all platforms
    assert _pid_alive(0) is False
    # PID -1 is invalid
    assert _pid_alive(-1) is False
    # A huge PID that almost certainly doesn't exist
    assert _pid_alive(999999999) is False


def test_pid_alive_true_for_current_process():
    """Our own PID is alive."""
    import os
    from app import _pid_alive
    assert _pid_alive(os.getpid()) is True


def test_recover_marks_dead_agent_crashed(_tmp_deployed_agents):
    """If a deployed_agent's PID doesn't exist, it's flipped to 'crashed'."""
    import storage
    from app import _recover_deployed_agents

    storage.deployed_agents().upsert('a-dead', pid=999999999, schedule='daily')
    assert storage.deployed_agents().get('a-dead').status == 'running'

    n = _recover_deployed_agents()
    assert n >= 1
    assert storage.deployed_agents().get('a-dead').status == 'crashed'


def test_recover_leaves_live_agent_alone(_tmp_deployed_agents):
    """A deployed_agent whose PID is our own process is not touched."""
    import os
    import storage
    from app import _recover_deployed_agents

    storage.deployed_agents().upsert('a-live', pid=os.getpid(), schedule='daily')
    _recover_deployed_agents()
    assert storage.deployed_agents().get('a-live').status == 'running'


def test_recover_no_deployments_returns_zero(_tmp_deployed_agents):
    from app import _recover_deployed_agents
    # _tmp_deployed_agents gives an empty deployed_agents store
    n = _recover_deployed_agents()
    assert n == 0
