def test_spec():
    from tools.get_news import SPEC
    assert SPEC.name == 'get_news'


def test_empty_stub():
    from tools.get_news import call
    r = call({'code': '600519.SH'})
    assert r['news'] == []
