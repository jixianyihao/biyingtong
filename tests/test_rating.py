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
