from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_t0_frontend_wires_pluggable_strategy_profiles():
    """T0Lab must expose strategy_profile instead of hard-coding backend default."""

    page = _read('frontend/src/pages/T0Lab.tsx')
    hooks = _read('frontend/src/api/hooks.ts')
    client = _read('frontend/src/api/client.ts')
    types = _read('frontend/src/api/types.ts')

    assert 'T0StrategyProfile' in types
    assert 'T0StrategyProfilesResponse' in types
    assert 't0StrategyProfiles' in client
    assert 'useT0StrategyProfiles' in hooks
    assert 'useT0StrategyProfiles' in page
    assert 'strategyProfile' in page
    assert 'strategy_profile: strategyProfile' in page
