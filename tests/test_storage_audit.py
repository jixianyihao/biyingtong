"""SQLiteAuditStore — append-only log with indexed queries."""


def _store(tmp_path):
    from storage.sqlite_audit import SQLiteAuditStore
    s = SQLiteAuditStore(tmp_path=tmp_path)
    s.init_schema()
    return s


def test_log_returns_row_id(tmp_path):
    from validation.base import AuditEntry
    s = _store(tmp_path)
    rid = s.log(AuditEntry(kind='validation', agent_id='a1',
                           details={'outcome': 'approved'}))
    assert isinstance(rid, int)
    assert rid > 0


def test_query_by_agent_most_recent_first(tmp_path):
    import time
    from validation.base import AuditEntry
    s = _store(tmp_path)
    s.log(AuditEntry(kind='validation', agent_id='a1', details={'n': 1}))
    time.sleep(0.02)
    s.log(AuditEntry(kind='validation', agent_id='a1', details={'n': 2}))
    rows = s.query_by_agent('a1')
    assert len(rows) == 2
    assert rows[0]['details']['n'] == 2  # newest first


def test_query_by_agent_filters(tmp_path):
    from validation.base import AuditEntry
    s = _store(tmp_path)
    s.log(AuditEntry(kind='validation', agent_id='a1', details={}))
    s.log(AuditEntry(kind='validation', agent_id='a2', details={}))
    assert len(s.query_by_agent('a1')) == 1
    assert len(s.query_by_agent('a2')) == 1
    assert len(s.query_by_agent('a3')) == 0


def test_query_by_kind(tmp_path):
    from validation.base import AuditEntry
    s = _store(tmp_path)
    s.log(AuditEntry(kind='validation', agent_id='a1', details={}))
    s.log(AuditEntry(kind='trade_blocked', agent_id='a1', details={}))
    s.log(AuditEntry(kind='trade_executed', agent_id='a1', details={}))
    assert len(s.query_by_kind('validation')) == 1
    assert len(s.query_by_kind('trade_blocked')) == 1


def test_limit_caps_results(tmp_path):
    from validation.base import AuditEntry
    s = _store(tmp_path)
    for i in range(20):
        s.log(AuditEntry(kind='validation', agent_id='a1', details={'n': i}))
    assert len(s.query_by_agent('a1', limit=5)) == 5


def test_details_roundtrips_as_json(tmp_path):
    from validation.base import AuditEntry
    s = _store(tmp_path)
    s.log(AuditEntry(
        kind='validation', agent_id='a1',
        details={'violations': [{'rule_id': 'position_max_pct',
                                 'severity': 'modify'}]},
    ))
    row = s.query_by_agent('a1')[0]
    assert row['details']['violations'][0]['rule_id'] == 'position_max_pct'
