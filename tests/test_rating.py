"""Trust rating classifier."""


def test_a_plus_at_90():
    from agents.rating import classify_rating
    assert classify_rating(100) == 'A+'
    assert classify_rating(90) == 'A+'


def test_a_range():
    from agents.rating import classify_rating
    assert classify_rating(89) == 'A'
    assert classify_rating(80) == 'A'


def test_b_range():
    from agents.rating import classify_rating
    assert classify_rating(79) == 'B'
    assert classify_rating(60) == 'B'


def test_c_range():
    from agents.rating import classify_rating
    assert classify_rating(59) == 'C'
    assert classify_rating(0) == 'C'


def test_clamps_negative_to_c():
    from agents.rating import classify_rating
    assert classify_rating(-5) == 'C'


def test_compute_health_from_audit(tmp_path):
    """Health formula: 100 - 3*violations - 2*live_dev - 1*parse_failures."""
    import storage
    storage.reset()
    from storage.sqlite_audit import SQLiteAuditStore
    from validation.base import AuditEntry
    au = SQLiteAuditStore(tmp_path=tmp_path); au.init_schema()
    storage.set_audit(au)

    # Seed: 3 rejected + 2 modified + 4 approved over arbitrary dates today
    for _ in range(3):
        au.log(AuditEntry(kind='validation', agent_id='a1',
                          details={'outcome': 'rejected'}))
    for _ in range(2):
        au.log(AuditEntry(kind='validation', agent_id='a1',
                          details={'outcome': 'modified'}))
    for _ in range(4):
        au.log(AuditEntry(kind='validation', agent_id='a1',
                          details={'outcome': 'approved'}))

    from agents.rating import compute_health
    h = compute_health('a1')
    # 5 violations * 3 = 15; 0 live_dev; 0 parse_failures → 100 - 15 = 85
    assert h == 85


def test_compute_health_floors_at_zero(tmp_path):
    import storage
    storage.reset()
    from storage.sqlite_audit import SQLiteAuditStore
    from validation.base import AuditEntry
    au = SQLiteAuditStore(tmp_path=tmp_path); au.init_schema()
    storage.set_audit(au)

    # 40 rejected → 40*3=120 → would be -20 → clamp to 0
    for _ in range(40):
        au.log(AuditEntry(kind='validation', agent_id='a1',
                          details={'outcome': 'rejected'}))
    from agents.rating import compute_health
    assert compute_health('a1') == 0


def test_compute_health_no_data_is_100(tmp_path):
    import storage
    storage.reset()
    from storage.sqlite_audit import SQLiteAuditStore
    au = SQLiteAuditStore(tmp_path=tmp_path); au.init_schema()
    storage.set_audit(au)
    from agents.rating import compute_health
    assert compute_health('nope') == 100
