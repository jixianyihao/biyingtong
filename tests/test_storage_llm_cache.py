"""SQLiteLLMDecisionCache — per-decision-day replay."""


def _entry(key_suffix=''):
    from backtest.base import CachedDecision
    return CachedDecision(
        agent_id='a1', date='2024-01-15',
        portfolio_hash='ph' + key_suffix,
        prompt_hash='rh' + key_suffix,
        decisions=[{'action': 'buy', 'code': 'X.SH',
                    'shares': 100, 'price': 10.0,
                    'reason': 'good value and growth prospects',
                    'thinking': 'full thinking trace'}],
    )


def test_has_empty(tmp_path):
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    c = SQLiteLLMDecisionCache(tmp_path=tmp_path)
    c.init_schema()
    assert c.has('nope') is False
    assert c.get('nope') is None


def test_put_then_get(tmp_path):
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    c = SQLiteLLMDecisionCache(tmp_path=tmp_path)
    c.init_schema()
    e = _entry()
    c.put(e)
    assert c.has(e.cache_key) is True
    got = c.get(e.cache_key)
    assert got is not None
    assert got.decisions[0]['code'] == 'X.SH'


def test_put_is_idempotent(tmp_path):
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    c = SQLiteLLMDecisionCache(tmp_path=tmp_path)
    c.init_schema()
    c.put(_entry())
    c.put(_entry())
    assert c.has(_entry().cache_key) is True


def test_distinct_keys_separate(tmp_path):
    from storage.sqlite_llm_cache import SQLiteLLMDecisionCache
    c = SQLiteLLMDecisionCache(tmp_path=tmp_path)
    c.init_schema()
    c.put(_entry(key_suffix='A'))
    c.put(_entry(key_suffix='B'))
    assert c.has(_entry(key_suffix='A').cache_key)
    assert c.has(_entry(key_suffix='B').cache_key)
