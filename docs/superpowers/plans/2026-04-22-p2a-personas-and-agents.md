# P2a — Storage expansion + Persona definitions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the `storage/` layer with three new domains (personas, agents, prompt_versions) and seed the 5 built-in personas from Spec § 4.3. After this sub-plan, the DB can answer "who are the agents, what persona do they inherit, what's the latest prompt?" — foundation for every later backtest-related sub-plan.

**Architecture:** Follow the P1 pattern: a new Protocol in `storage/base.py` per domain, a new `storage/sqlite_*.py` implementation, a factory entry in `storage/__init__.py`. Personas are declared as Python data modules in a new `personas/` package and seeded into the DB via `personas.seed()`. Agent instances are a `persona_id × model_id × rules_override` triple; creating one atomically inserts a `prompt_version` v1 that snapshots the persona's system prompt.

**Tech Stack:** Python 3.10+ stdlib (`sqlite3`, `json`, `dataclasses`, `datetime`, `decimal`), existing P1 storage layer + LLM model registry, pytest. No new external dependencies.

---

## Spec References

- § 4.1 Four-Dimensional Agent Model (persona / model / rules / schedule)
- § 4.2 Multi-Instance Mode (same persona × different models)
- § 4.3 Five Built-in Personas
- § 10.1 Prompt Versioning schema
- § 10.2 Auto-versioning (initial version on agent creation)

**Deferred to later P2 sub-plans:**
- P2b: `redlines` + `audit_log` tables (used by validation engine)
- P2c: `backtest_results` table (used by LLMStrategy runner)
- P2d: baseline strategies, rating formulas, health scoring
- P2e: Flask API endpoints + SSE + prompt editing

## Deliverables

1. `data_schema/agent_state.py` extended with `SCHEMA_PERSONAS`, `SCHEMA_AGENTS`, `SCHEMA_PROMPT_VERSIONS`
2. `storage/base.py` extended with `Persona` / `Agent` / `PromptVersion` dataclasses and `PersonaStore` / `AgentStore` / `PromptVersionStore` Protocols
3. `storage/sqlite_personas.py`, `storage/sqlite_agents.py`, `storage/sqlite_prompt_versions.py` SQLite implementations
4. `storage/__init__.py` factories `personas()` / `agents()` / `prompt_versions()` with `set_*` and `reset` support
5. `personas/` package with 5 persona modules (linyuan, fuyou, buffet, soros, quant_neutral)
6. `personas.seed()` helper that inserts all 5 personas into the DB (idempotent)
7. Agent creation workflow: `SQLiteAgentStore.create_from_persona(persona_id, model_id, **overrides)` atomically writes the Agent row + PromptVersion v1
8. E2E integration test: seed personas → create agent instance for `林园 × claude-opus-4-7` → verify persona, agent, and initial prompt version all link correctly

## File Structure

```
biyingtong/
├── data_schema/
│   └── agent_state.py                   # EXTEND (Task 1): +3 SCHEMA constants
├── storage/
│   ├── base.py                          # EXTEND (Task 2): +3 dataclasses +3 Protocols
│   ├── __init__.py                      # EXTEND (Tasks 3-5): +3 factories
│   ├── sqlite_personas.py               # NEW (Task 3)
│   ├── sqlite_agents.py                 # NEW (Task 4)
│   └── sqlite_prompt_versions.py        # NEW (Task 5)
├── personas/                            # NEW package (Task 6)
│   ├── __init__.py                      # ALL_PERSONAS registry
│   ├── linyuan.py
│   ├── fuyou.py
│   ├── buffet.py
│   ├── soros.py
│   └── quant_neutral.py
└── tests/
    ├── test_storage_personas.py         # NEW (Task 3)
    ├── test_storage_agents.py           # NEW (Task 4)
    ├── test_storage_prompt_versions.py  # NEW (Task 5)
    ├── test_personas_data.py            # NEW (Task 6)
    └── test_personas_seed_e2e.py        # NEW (Task 7)
```

**Rationale:**
- Three separate `sqlite_*.py` files because each Store class owns one table and has distinct query patterns. Keeping them separate means Task 3 / 4 / 5 produce independently reviewable units.
- `personas/` is a package of data modules (no logic beyond the `PERSONA` dict each exports). Easy to add a 6th persona later without touching storage code.
- Auto-versioning lives in `SQLiteAgentStore.create_from_persona`, which imports `storage.prompt_versions()` — storage modules know about each other via the factory, never via hard imports.

---

## Shared type contracts (introduced in Tasks 1-2, consumed throughout)

```python
# data_schema/agent_state.py (added by Task 1)
SCHEMA_PERSONAS = '''
CREATE TABLE IF NOT EXISTS personas (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    style_desc       TEXT,
    system_prompt    TEXT NOT NULL,
    default_pool     TEXT NOT NULL,   -- JSON list of stock codes
    pool_filter      TEXT,            -- JSON or NULL
    default_schedule TEXT NOT NULL,   -- 'daily'|'weekly'|'monthly'|'intraday_5m'
    default_rules    TEXT NOT NULL,   -- JSON
    allowed_tools    TEXT NOT NULL,   -- JSON list
    is_builtin       INTEGER DEFAULT 0,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);
'''

SCHEMA_AGENTS = '''
CREATE TABLE IF NOT EXISTS agents (
    id                        TEXT PRIMARY KEY,
    persona_id                TEXT NOT NULL REFERENCES personas(id),
    model_id                  TEXT NOT NULL REFERENCES llm_models(id),
    display_name              TEXT NOT NULL,
    rules_override            TEXT NOT NULL,   -- JSON
    initial_capital           REAL NOT NULL,
    status                    TEXT DEFAULT 'created',
    subprocess_pid            INTEGER,
    health_score              INTEGER DEFAULT 100,
    trust_rating              TEXT DEFAULT 'A',
    current_prompt_version_id INTEGER,         -- FK to prompt_versions.id
    created_at                DATETIME DEFAULT CURRENT_TIMESTAMP
);
'''

SCHEMA_PROMPT_VERSIONS = '''
CREATE TABLE IF NOT EXISTS prompt_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    version_number  INTEGER NOT NULL,
    system_prompt   TEXT NOT NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    note            TEXT,
    UNIQUE(agent_id, version_number)
);
CREATE INDEX IF NOT EXISTS prompt_by_agent ON prompt_versions(agent_id, version_number DESC);
'''
```

```python
# storage/base.py (added by Task 2)

@dataclass
class Persona:
    id: str
    name: str
    style_desc: str
    system_prompt: str
    default_pool: list[str]
    pool_filter: dict | None
    default_schedule: str
    default_rules: dict
    allowed_tools: list[str]
    is_builtin: bool
    created_at: str | None = None   # ISO string from DB; None when not yet saved


@dataclass
class Agent:
    id: str
    persona_id: str
    model_id: str
    display_name: str
    rules_override: dict
    initial_capital: float
    status: str
    subprocess_pid: int | None
    health_score: int
    trust_rating: str
    current_prompt_version_id: int | None
    created_at: str | None = None


@dataclass
class PromptVersion:
    id: int
    agent_id: str
    version_number: int
    system_prompt: str
    created_at: str | None
    note: str | None = None


@runtime_checkable
class PersonaStore(Protocol):
    def init_schema(self) -> None: ...
    def upsert(self, persona: Persona) -> None: ...
    def get(self, persona_id: str) -> Persona | None: ...
    def list_all(self) -> list[Persona]: ...


@runtime_checkable
class AgentStore(Protocol):
    def init_schema(self) -> None: ...
    def create_from_persona(
        self,
        persona_id: str,
        model_id: str,
        display_name: str,
        rules_override: dict | None = None,
        initial_capital: float = 1_000_000,
    ) -> Agent: ...
    def get(self, agent_id: str) -> Agent | None: ...
    def list_all(self) -> list[Agent]: ...
    def update_status(self, agent_id: str, status: str) -> None: ...


@runtime_checkable
class PromptVersionStore(Protocol):
    def init_schema(self) -> None: ...
    def insert(self, agent_id: str, system_prompt: str,
               note: str | None = None) -> PromptVersion: ...
    def get_latest(self, agent_id: str) -> PromptVersion | None: ...
    def list_for_agent(self, agent_id: str) -> list[PromptVersion]: ...
```

---

### Task 1: Extend `data_schema/agent_state.py` with new SCHEMAs

**Files:**
- Modify: `data_schema/agent_state.py`
- Test: `tests/test_storage_personas.py` (minimal smoke test only; full tests in Task 3)

- [ ] **Step 1: Read the existing file**

Run: `cat data_schema/agent_state.py`
Expected: file has `SCHEMA_LLM_MODELS` constant from P1 Task 5.

- [ ] **Step 2: Append new SCHEMA constants**

Edit `data_schema/agent_state.py`. Keep the `SCHEMA_LLM_MODELS` constant unchanged; append three new constants:

```python
"""SQL DDL for agent_state.db tables.

Centralized so storage/sqlite_* modules can share exact-match schema.
"""

SCHEMA_LLM_MODELS = '''
CREATE TABLE IF NOT EXISTS llm_models (
    id                TEXT PRIMARY KEY,
    provider          TEXT NOT NULL,
    display_name      TEXT NOT NULL,
    api_model_id      TEXT NOT NULL,
    training_cutoff   DATE NOT NULL,
    supports_tool_use INTEGER DEFAULT 1,
    max_tokens_out    INTEGER DEFAULT 4096,
    enabled           INTEGER DEFAULT 1
);
'''

# --- Added in P2a ---

SCHEMA_PERSONAS = '''
CREATE TABLE IF NOT EXISTS personas (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    style_desc       TEXT,
    system_prompt    TEXT NOT NULL,
    default_pool     TEXT NOT NULL,
    pool_filter      TEXT,
    default_schedule TEXT NOT NULL,
    default_rules    TEXT NOT NULL,
    allowed_tools    TEXT NOT NULL,
    is_builtin       INTEGER DEFAULT 0,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);
'''

SCHEMA_AGENTS = '''
CREATE TABLE IF NOT EXISTS agents (
    id                        TEXT PRIMARY KEY,
    persona_id                TEXT NOT NULL REFERENCES personas(id),
    model_id                  TEXT NOT NULL REFERENCES llm_models(id),
    display_name              TEXT NOT NULL,
    rules_override            TEXT NOT NULL,
    initial_capital           REAL NOT NULL,
    status                    TEXT DEFAULT 'created',
    subprocess_pid            INTEGER,
    health_score              INTEGER DEFAULT 100,
    trust_rating              TEXT DEFAULT 'A',
    current_prompt_version_id INTEGER,
    created_at                DATETIME DEFAULT CURRENT_TIMESTAMP
);
'''

SCHEMA_PROMPT_VERSIONS = '''
CREATE TABLE IF NOT EXISTS prompt_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    version_number  INTEGER NOT NULL,
    system_prompt   TEXT NOT NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    note            TEXT,
    UNIQUE(agent_id, version_number)
);
'''

SCHEMA_PROMPT_VERSION_INDEX = '''
CREATE INDEX IF NOT EXISTS prompt_by_agent
  ON prompt_versions(agent_id, version_number DESC);
'''
```

- [ ] **Step 3: Create smoke test**

Create `tests/test_storage_personas.py` (placeholder with one minimal test — full persona-store tests come in Task 3):

```python
"""Smoke test for persona schema DDL."""
import sqlite3


def test_personas_schema_applies_cleanly(tmp_path):
    from data_schema.agent_state import SCHEMA_PERSONAS
    db = tmp_path / 'test.db'
    con = sqlite3.connect(db)
    try:
        con.execute(SCHEMA_PERSONAS)
        con.commit()
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='personas'"
        ).fetchall()
    finally:
        con.close()
    assert len(rows) == 1


def test_agents_schema_applies_cleanly(tmp_path):
    from data_schema.agent_state import SCHEMA_PERSONAS, SCHEMA_AGENTS
    db = tmp_path / 'test.db'
    con = sqlite3.connect(db)
    try:
        con.execute(SCHEMA_PERSONAS)
        con.execute(SCHEMA_AGENTS)
        con.commit()
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agents'"
        ).fetchall()
    finally:
        con.close()
    assert len(rows) == 1


def test_prompt_versions_schema_applies_cleanly(tmp_path):
    from data_schema.agent_state import (
        SCHEMA_PERSONAS, SCHEMA_AGENTS, SCHEMA_PROMPT_VERSIONS,
        SCHEMA_PROMPT_VERSION_INDEX,
    )
    db = tmp_path / 'test.db'
    con = sqlite3.connect(db)
    try:
        con.execute(SCHEMA_PERSONAS)
        con.execute(SCHEMA_AGENTS)
        con.execute(SCHEMA_PROMPT_VERSIONS)
        con.execute(SCHEMA_PROMPT_VERSION_INDEX)
        con.commit()
    finally:
        con.close()
```

- [ ] **Step 4: Run the smoke test**

Run: `pytest tests/test_storage_personas.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add data_schema/agent_state.py tests/test_storage_personas.py
git commit -m "feat(p2a): schemas for personas + agents + prompt_versions"
```

---

### Task 2: Extend `storage/base.py` with dataclasses + Protocols

**Files:**
- Modify: `storage/base.py`
- Test: `tests/test_storage_base.py` (extend existing; don't touch P1 tests)

- [ ] **Step 1: Read the existing file**

Run: `cat storage/base.py`
Expected: `Message`/`ModelInfo` dataclasses and `KlineStore`/`FinancialStore`/`ModelStore`/`CalendarStore` Protocols from P1.

- [ ] **Step 2: Append new dataclasses and Protocols**

Open `storage/base.py`. Leave all existing content intact; append after the existing `CalendarStore` Protocol:

```python


# --- Added in P2a ---

@dataclass
class Persona:
    """Reusable investment-philosophy definition. See Spec § 4.3 for the 5 built-ins."""
    id: str
    name: str
    style_desc: str
    system_prompt: str
    default_pool: list[str]
    pool_filter: dict | None
    default_schedule: str
    default_rules: dict
    allowed_tools: list[str]
    is_builtin: bool
    created_at: str | None = None


@dataclass
class Agent:
    """An agent instance = persona × model × rules_override.

    Multiple instances can share a persona, differing only by model_id or
    rules_override, enabling head-to-head comparison (Spec § 4.2).
    """
    id: str
    persona_id: str
    model_id: str
    display_name: str
    rules_override: dict
    initial_capital: float
    status: str
    subprocess_pid: int | None
    health_score: int
    trust_rating: str
    current_prompt_version_id: int | None
    created_at: str | None = None


@dataclass
class PromptVersion:
    """Immutable snapshot of an agent's system_prompt at a point in time."""
    id: int
    agent_id: str
    version_number: int
    system_prompt: str
    created_at: str | None
    note: str | None = None


@runtime_checkable
class PersonaStore(Protocol):
    """Reads/writes the personas table."""
    def init_schema(self) -> None: ...
    def upsert(self, persona: Persona) -> None:
        """Insert or replace by id. Idempotent."""
        ...
    def get(self, persona_id: str) -> Persona | None: ...
    def list_all(self) -> list[Persona]: ...


@runtime_checkable
class AgentStore(Protocol):
    """Reads/writes the agents table + coordinates initial prompt version creation."""
    def init_schema(self) -> None: ...
    def create_from_persona(
        self,
        persona_id: str,
        model_id: str,
        display_name: str,
        rules_override: dict | None = None,
        initial_capital: float = 1_000_000,
    ) -> Agent:
        """Atomically: insert new Agent row + PromptVersion v1 snapshotting
        the persona's current system_prompt. Returns the fresh Agent."""
        ...
    def get(self, agent_id: str) -> Agent | None: ...
    def list_all(self) -> list[Agent]: ...
    def update_status(self, agent_id: str, status: str) -> None: ...


@runtime_checkable
class PromptVersionStore(Protocol):
    """Reads/writes the prompt_versions table."""
    def init_schema(self) -> None: ...
    def insert(
        self, agent_id: str, system_prompt: str, note: str | None = None,
    ) -> PromptVersion:
        """Insert a new version; version_number = max(existing) + 1. Returns the row."""
        ...
    def get_latest(self, agent_id: str) -> PromptVersion | None: ...
    def list_for_agent(self, agent_id: str) -> list[PromptVersion]:
        """Ascending by version_number."""
        ...
```

- [ ] **Step 3: Append to existing test file**

Open `tests/test_storage_base.py`. Leave existing tests intact. Append:

```python


def test_persona_dataclass():
    from storage.base import Persona
    p = Persona(
        id='x', name='Test', style_desc='desc',
        system_prompt='prompt', default_pool=['600519.SH'],
        pool_filter=None, default_schedule='daily',
        default_rules={'position_max_pct': 30.0},
        allowed_tools=['get_kline'], is_builtin=True,
    )
    assert p.id == 'x'
    assert p.created_at is None


def test_agent_dataclass():
    from storage.base import Agent
    a = Agent(
        id='a1', persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='林园 · Claude Opus 4.7', rules_override={},
        initial_capital=1_000_000, status='created',
        subprocess_pid=None, health_score=100, trust_rating='A',
        current_prompt_version_id=None,
    )
    assert a.persona_id == 'linyuan'


def test_prompt_version_dataclass():
    from storage.base import PromptVersion
    v = PromptVersion(
        id=1, agent_id='a1', version_number=1,
        system_prompt='You are X', created_at='2026-04-22T00:00:00',
    )
    assert v.note is None


def test_persona_store_protocol_runtime_checkable():
    from storage.base import Persona, PersonaStore

    class Compliant:
        def init_schema(self): pass
        def upsert(self, persona): pass
        def get(self, persona_id): return None
        def list_all(self): return []

    assert isinstance(Compliant(), PersonaStore)


def test_agent_store_protocol_runtime_checkable():
    from storage.base import AgentStore

    class Compliant:
        def init_schema(self): pass
        def create_from_persona(self, persona_id, model_id, display_name,
                                 rules_override=None, initial_capital=1_000_000):
            return None  # type: ignore
        def get(self, agent_id): return None
        def list_all(self): return []
        def update_status(self, agent_id, status): pass

    assert isinstance(Compliant(), AgentStore)


def test_prompt_version_store_protocol_runtime_checkable():
    from storage.base import PromptVersionStore

    class Compliant:
        def init_schema(self): pass
        def insert(self, agent_id, system_prompt, note=None): return None  # type: ignore
        def get_latest(self, agent_id): return None
        def list_for_agent(self, agent_id): return []

    assert isinstance(Compliant(), PromptVersionStore)
```

- [ ] **Step 4: Run the extended test suite**

Run: `pytest tests/test_storage_base.py -v`
Expected: All previous tests still pass + 6 new tests PASS = 12+ tests total green.

- [ ] **Step 5: Commit**

```bash
git add storage/base.py tests/test_storage_base.py
git commit -m "feat(p2a): Persona/Agent/PromptVersion dataclasses + Protocols"
```

---

### Task 3: SQLitePersonaStore

**Files:**
- Create: `storage/sqlite_personas.py`
- Modify: `storage/__init__.py` — add `personas()` factory + `set_personas()` + reset wiring
- Test: extend `tests/test_storage_personas.py`

- [ ] **Step 1: Write the failing test**

Open `tests/test_storage_personas.py`. Append (after the smoke tests from Task 1):

```python


def _sample_persona():
    from storage.base import Persona
    return Persona(
        id='test_p', name='Test Persona',
        style_desc='Test style',
        system_prompt='You are a test agent.',
        default_pool=['600519.SH', '000858.SZ'],
        pool_filter=None,
        default_schedule='weekly',
        default_rules={'position_max_pct': 20.0, 'cash_min_pct': 5.0},
        allowed_tools=['get_kline', 'get_financials'],
        is_builtin=True,
    )


def test_sqlite_persona_store_satisfies_protocol(tmp_path):
    from storage.base import PersonaStore
    from storage.sqlite_personas import SQLitePersonaStore
    assert isinstance(SQLitePersonaStore(tmp_path=tmp_path), PersonaStore)


def test_upsert_and_get(tmp_path):
    from storage.sqlite_personas import SQLitePersonaStore
    store = SQLitePersonaStore(tmp_path=tmp_path)
    store.init_schema()

    p = _sample_persona()
    store.upsert(p)

    loaded = store.get('test_p')
    assert loaded is not None
    assert loaded.id == 'test_p'
    assert loaded.name == 'Test Persona'
    assert loaded.default_pool == ['600519.SH', '000858.SZ']
    assert loaded.default_rules == {'position_max_pct': 20.0, 'cash_min_pct': 5.0}
    assert loaded.allowed_tools == ['get_kline', 'get_financials']
    assert loaded.is_builtin is True
    assert loaded.created_at is not None


def test_upsert_replaces_existing(tmp_path):
    from storage.sqlite_personas import SQLitePersonaStore
    store = SQLitePersonaStore(tmp_path=tmp_path)
    store.init_schema()

    p = _sample_persona()
    store.upsert(p)

    # Re-upsert with changed system_prompt
    from dataclasses import replace
    p2 = replace(p, system_prompt='Updated prompt.')
    store.upsert(p2)

    loaded = store.get('test_p')
    assert loaded.system_prompt == 'Updated prompt.'

    # Still only one row
    assert len(store.list_all()) == 1


def test_get_missing_returns_none(tmp_path):
    from storage.sqlite_personas import SQLitePersonaStore
    store = SQLitePersonaStore(tmp_path=tmp_path)
    store.init_schema()
    assert store.get('nonexistent') is None


def test_list_all_sorted_by_id(tmp_path):
    from storage.sqlite_personas import SQLitePersonaStore
    store = SQLitePersonaStore(tmp_path=tmp_path)
    store.init_schema()

    from dataclasses import replace
    p = _sample_persona()
    store.upsert(replace(p, id='z_later'))
    store.upsert(replace(p, id='a_earlier'))

    ids = [row.id for row in store.list_all()]
    assert ids == ['a_earlier', 'z_later']


def test_pool_filter_roundtrip_with_none(tmp_path):
    from storage.sqlite_personas import SQLitePersonaStore
    from dataclasses import replace
    store = SQLitePersonaStore(tmp_path=tmp_path)
    store.init_schema()

    p = _sample_persona()
    store.upsert(p)
    loaded = store.get('test_p')
    assert loaded.pool_filter is None


def test_pool_filter_roundtrip_with_dict(tmp_path):
    from storage.sqlite_personas import SQLitePersonaStore
    from dataclasses import replace
    store = SQLitePersonaStore(tmp_path=tmp_path)
    store.init_schema()

    p = replace(_sample_persona(), pool_filter={'top_momentum': 15, 'top_value': 10})
    store.upsert(p)
    loaded = store.get('test_p')
    assert loaded.pool_filter == {'top_momentum': 15, 'top_value': 10}


def test_storage_factory_returns_sqlite_persona_store(tmp_path, monkeypatch):
    """storage.personas() returns SQLitePersonaStore by default."""
    import storage
    storage.reset()
    from storage.sqlite_personas import SQLitePersonaStore
    assert isinstance(storage.personas(), SQLitePersonaStore)
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `pytest tests/test_storage_personas.py -v`
Expected: 3 smoke tests from Task 1 pass + new tests fail with `ModuleNotFoundError: storage.sqlite_personas`.

- [ ] **Step 3: Create `storage/sqlite_personas.py`**

Content (EXACTLY this):

```python
"""SQLitePersonaStore — personas table (agent philosophy definitions)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from data_schema.agent_state import SCHEMA_PERSONAS

from .base import Persona, PersonaStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _dumps_or_null(value):
    return None if value is None else json.dumps(value, ensure_ascii=False)


def _loads_or_none(text):
    return None if text is None else json.loads(text)


class SQLitePersonaStore(PersonaStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.execute(SCHEMA_PERSONAS)
            con.commit()
        finally:
            con.close()

    def upsert(self, persona: Persona) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(SCHEMA_PERSONAS)
            con.execute(
                '''INSERT OR REPLACE INTO personas
                   (id, name, style_desc, system_prompt,
                    default_pool, pool_filter, default_schedule,
                    default_rules, allowed_tools, is_builtin)
                   VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (
                    persona.id, persona.name, persona.style_desc,
                    persona.system_prompt,
                    json.dumps(persona.default_pool, ensure_ascii=False),
                    _dumps_or_null(persona.pool_filter),
                    persona.default_schedule,
                    json.dumps(persona.default_rules, ensure_ascii=False),
                    json.dumps(persona.allowed_tools, ensure_ascii=False),
                    1 if persona.is_builtin else 0,
                ),
            )
            con.commit()
        finally:
            con.close()

    def _row_to_persona(self, row) -> Persona:
        return Persona(
            id=row[0], name=row[1], style_desc=row[2],
            system_prompt=row[3],
            default_pool=json.loads(row[4]),
            pool_filter=_loads_or_none(row[5]),
            default_schedule=row[6],
            default_rules=json.loads(row[7]),
            allowed_tools=json.loads(row[8]),
            is_builtin=bool(row[9]),
            created_at=row[10],
        )

    def get(self, persona_id: str) -> Persona | None:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                '''SELECT id, name, style_desc, system_prompt,
                          default_pool, pool_filter, default_schedule,
                          default_rules, allowed_tools, is_builtin, created_at
                   FROM personas WHERE id = ?''',
                (persona_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        return self._row_to_persona(row) if row else None

    def list_all(self) -> list[Persona]:
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                '''SELECT id, name, style_desc, system_prompt,
                          default_pool, pool_filter, default_schedule,
                          default_rules, allowed_tools, is_builtin, created_at
                   FROM personas ORDER BY id''',
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [self._row_to_persona(r) for r in rows]
```

- [ ] **Step 4: Wire factory in `storage/__init__.py`**

Open `storage/__init__.py`. Currently has 4 factories (kline/financial/models/calendar). Add a fifth.

Make these exact edits:

1. Add import at top of imports block:
```python
from .base import (
    Agent, AgentStore, CalendarStore, FinancialStore,
    KlineStore, ModelInfo, ModelStore, Persona, PersonaStore,
    PromptVersion, PromptVersionStore,
)
```
(This replaces the existing single-line `from .base import (...)` import. The P1 import has 5 names; this adds 5 more: Agent, AgentStore, Persona, PersonaStore, PromptVersion, PromptVersionStore — 6 total additions.)

2. Add a new singleton variable next to `_calendar`:
```python
_personas: PersonaStore | None = None
```

3. Add factory function after `calendar()`:
```python
def personas() -> PersonaStore:
    global _personas
    if _personas is None:
        from .sqlite_personas import SQLitePersonaStore
        _personas = SQLitePersonaStore()
    return _personas
```

4. Add setter after `set_calendar`:
```python
def set_personas(impl: PersonaStore) -> None:
    global _personas
    _personas = impl
```

5. Extend `reset()` — add `_personas = None` inside.

The final file should look like this (new additions commented):

```python
"""Storage factory — returns singletons of the configured backend."""
from __future__ import annotations

from .base import (
    Agent, AgentStore, CalendarStore, FinancialStore,
    KlineStore, ModelInfo, ModelStore, Persona, PersonaStore,
    PromptVersion, PromptVersionStore,
)

_kline: KlineStore | None = None
_financial: FinancialStore | None = None
_models: ModelStore | None = None
_calendar: CalendarStore | None = None
_personas: PersonaStore | None = None  # P2a


def kline() -> KlineStore:
    global _kline
    if _kline is None:
        from .sqlite_kline import SQLiteKlineStore
        _kline = SQLiteKlineStore()
    return _kline


def financial() -> FinancialStore:
    global _financial
    if _financial is None:
        from .sqlite_financial import SQLiteFinancialStore
        _financial = SQLiteFinancialStore()
    return _financial


def models() -> ModelStore:
    global _models
    if _models is None:
        from .sqlite_models import SQLiteModelStore
        _models = SQLiteModelStore()
    return _models


def calendar() -> CalendarStore:
    global _calendar
    if _calendar is None:
        from .sqlite_calendar import SQLiteCalendarStore
        _calendar = SQLiteCalendarStore()
    return _calendar


def personas() -> PersonaStore:  # P2a
    global _personas
    if _personas is None:
        from .sqlite_personas import SQLitePersonaStore
        _personas = SQLitePersonaStore()
    return _personas


def set_kline(impl: KlineStore) -> None:
    global _kline
    _kline = impl


def set_financial(impl: FinancialStore) -> None:
    global _financial
    _financial = impl


def set_models(impl: ModelStore) -> None:
    global _models
    _models = impl


def set_calendar(impl: CalendarStore) -> None:
    global _calendar
    _calendar = impl


def set_personas(impl: PersonaStore) -> None:  # P2a
    global _personas
    _personas = impl


def reset() -> None:
    global _kline, _financial, _models, _calendar, _personas
    _kline = None
    _financial = None
    _models = None
    _calendar = None
    _personas = None
```

Note: Tasks 4 and 5 will append additional singleton variables (_agents, _prompt_versions), factories, setters, and extend `reset()` further. Do not add those now.

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_storage_personas.py tests/test_storage_base.py -v`
Expected: All persona store tests pass + all existing base tests pass.

- [ ] **Step 6: Commit**

```bash
git add storage/sqlite_personas.py storage/__init__.py tests/test_storage_personas.py
git commit -m "feat(p2a): SQLitePersonaStore + storage.personas() factory"
```

---

### Task 4: SQLiteAgentStore

**Files:**
- Create: `storage/sqlite_agents.py`
- Modify: `storage/__init__.py` — add `agents()` factory
- Test: `tests/test_storage_agents.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_storage_agents.py`:

```python
"""SQLiteAgentStore — agent instances (persona × model × rules_override)."""


def _prepare_persona(tmp_path):
    """Seed a minimal persona so agent creation can reference it."""
    import storage
    from storage.base import Persona
    from storage.sqlite_personas import SQLitePersonaStore
    pstore = SQLitePersonaStore(tmp_path=tmp_path)
    pstore.init_schema()
    pstore.upsert(Persona(
        id='p_test', name='Test Persona', style_desc='',
        system_prompt='You are persona p_test.',
        default_pool=['600519.SH'], pool_filter=None,
        default_schedule='weekly',
        default_rules={'position_max_pct': 30.0},
        allowed_tools=['get_kline'], is_builtin=True,
    ))
    storage.set_personas(pstore)


def _prepare_prompt_version_store(tmp_path):
    """Seed prompt_versions table + factory so agent.create_from_persona works."""
    import storage
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    pv = SQLitePromptVersionStore(tmp_path=tmp_path)
    pv.init_schema()
    storage.set_prompt_versions(pv)


def test_sqlite_agent_store_satisfies_protocol(tmp_path):
    from storage.base import AgentStore
    from storage.sqlite_agents import SQLiteAgentStore
    assert isinstance(SQLiteAgentStore(tmp_path=tmp_path), AgentStore)


def test_create_from_persona_inserts_agent_and_v1(tmp_path):
    _prepare_persona(tmp_path)
    _prepare_prompt_version_store(tmp_path)
    from storage.sqlite_agents import SQLiteAgentStore
    store = SQLiteAgentStore(tmp_path=tmp_path)
    store.init_schema()

    agent = store.create_from_persona(
        persona_id='p_test',
        model_id='claude-opus-4-7',
        display_name='p_test · Claude Opus 4.7',
    )
    assert agent.id.startswith('p_test_')
    assert agent.persona_id == 'p_test'
    assert agent.model_id == 'claude-opus-4-7'
    assert agent.display_name == 'p_test · Claude Opus 4.7'
    assert agent.status == 'created'
    assert agent.health_score == 100
    assert agent.trust_rating == 'A'
    assert agent.current_prompt_version_id is not None
    assert agent.initial_capital == 1_000_000.0

    # Verify prompt_versions v1 was inserted with the persona's system_prompt
    import storage
    pv = storage.prompt_versions().get_latest(agent.id)
    assert pv is not None
    assert pv.version_number == 1
    assert pv.system_prompt == 'You are persona p_test.'
    assert pv.id == agent.current_prompt_version_id


def test_create_from_persona_applies_rules_override(tmp_path):
    _prepare_persona(tmp_path)
    _prepare_prompt_version_store(tmp_path)
    from storage.sqlite_agents import SQLiteAgentStore
    store = SQLiteAgentStore(tmp_path=tmp_path)
    store.init_schema()

    agent = store.create_from_persona(
        persona_id='p_test', model_id='claude-opus-4-7',
        display_name='custom',
        rules_override={'daily_loss_max_pct': 2.0},
        initial_capital=500_000,
    )
    assert agent.rules_override == {'daily_loss_max_pct': 2.0}
    assert agent.initial_capital == 500_000.0


def test_create_from_persona_unknown_persona_raises(tmp_path):
    _prepare_prompt_version_store(tmp_path)  # needs prompt_versions wired
    from storage.sqlite_agents import SQLiteAgentStore
    import storage
    # Empty persona store so persona lookup returns None
    from storage.sqlite_personas import SQLitePersonaStore
    pstore = SQLitePersonaStore(tmp_path=tmp_path)
    pstore.init_schema()
    storage.set_personas(pstore)

    store = SQLiteAgentStore(tmp_path=tmp_path)
    store.init_schema()

    import pytest
    with pytest.raises(ValueError, match='persona'):
        store.create_from_persona(
            persona_id='does_not_exist', model_id='claude-opus-4-7',
            display_name='x',
        )


def test_get_and_list(tmp_path):
    _prepare_persona(tmp_path)
    _prepare_prompt_version_store(tmp_path)
    from storage.sqlite_agents import SQLiteAgentStore
    store = SQLiteAgentStore(tmp_path=tmp_path)
    store.init_schema()

    a1 = store.create_from_persona(
        persona_id='p_test', model_id='claude-opus-4-7',
        display_name='inst1',
    )
    a2 = store.create_from_persona(
        persona_id='p_test', model_id='gpt-5',
        display_name='inst2',
    )

    loaded = store.get(a1.id)
    assert loaded is not None
    assert loaded.display_name == 'inst1'

    all_agents = store.list_all()
    assert len(all_agents) == 2
    assert {a.id for a in all_agents} == {a1.id, a2.id}


def test_update_status(tmp_path):
    _prepare_persona(tmp_path)
    _prepare_prompt_version_store(tmp_path)
    from storage.sqlite_agents import SQLiteAgentStore
    store = SQLiteAgentStore(tmp_path=tmp_path)
    store.init_schema()

    a = store.create_from_persona(
        persona_id='p_test', model_id='claude-opus-4-7',
        display_name='x',
    )
    assert a.status == 'created'

    store.update_status(a.id, 'backtested')
    loaded = store.get(a.id)
    assert loaded.status == 'backtested'


def test_storage_factory_returns_sqlite_agent_store(tmp_path):
    import storage
    storage.reset()
    from storage.sqlite_agents import SQLiteAgentStore
    assert isinstance(storage.agents(), SQLiteAgentStore)
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `pytest tests/test_storage_agents.py -v`
Expected: FAIL — `ModuleNotFoundError: storage.sqlite_agents`. Some tests also depend on `storage.sqlite_prompt_versions` (Task 5) and `storage.set_prompt_versions`. They'll fail on the same ModuleNotFoundError — expected; Task 5 will make them pass.

- [ ] **Step 3: Create `storage/sqlite_agents.py`**

Content (EXACTLY this):

```python
"""SQLiteAgentStore — agents table + atomic prompt-version-on-create."""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from data_schema.agent_state import SCHEMA_AGENTS

from .base import Agent, AgentStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


class SQLiteAgentStore(AgentStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.execute(SCHEMA_AGENTS)
            con.commit()
        finally:
            con.close()

    def create_from_persona(
        self,
        persona_id: str,
        model_id: str,
        display_name: str,
        rules_override: dict | None = None,
        initial_capital: float = 1_000_000,
    ) -> Agent:
        # Fetch persona via factory (caller is responsible for wiring)
        from . import personas as _personas_factory
        from . import prompt_versions as _pv_factory

        persona = _personas_factory().get(persona_id)
        if persona is None:
            raise ValueError(f'persona {persona_id!r} not found; seed or upsert it first')

        agent_id = f'{persona_id}_{uuid.uuid4().hex[:8]}'

        rules_override_dict = rules_override or {}
        rules_json = json.dumps(rules_override_dict, ensure_ascii=False)

        # Step 1: insert Agent row (current_prompt_version_id=NULL)
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(SCHEMA_AGENTS)
            con.execute(
                '''INSERT INTO agents
                   (id, persona_id, model_id, display_name, rules_override,
                    initial_capital, status, subprocess_pid, health_score,
                    trust_rating, current_prompt_version_id)
                   VALUES (?, ?, ?, ?, ?, ?, 'created', NULL, 100, 'A', NULL)''',
                (agent_id, persona_id, model_id, display_name,
                 rules_json, float(initial_capital)),
            )
            con.commit()
        finally:
            con.close()

        # Step 2: insert initial PromptVersion v1 with persona.system_prompt
        pv = _pv_factory().insert(
            agent_id=agent_id,
            system_prompt=persona.system_prompt,
            note='initial version (from persona at creation time)',
        )

        # Step 3: backfill agents.current_prompt_version_id
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(
                'UPDATE agents SET current_prompt_version_id = ? WHERE id = ?',
                (pv.id, agent_id),
            )
            con.commit()
        finally:
            con.close()

        loaded = self.get(agent_id)
        assert loaded is not None
        return loaded

    def _row_to_agent(self, row) -> Agent:
        return Agent(
            id=row[0], persona_id=row[1], model_id=row[2],
            display_name=row[3],
            rules_override=json.loads(row[4]),
            initial_capital=row[5],
            status=row[6],
            subprocess_pid=row[7],
            health_score=row[8],
            trust_rating=row[9],
            current_prompt_version_id=row[10],
            created_at=row[11],
        )

    def get(self, agent_id: str) -> Agent | None:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                '''SELECT id, persona_id, model_id, display_name,
                          rules_override, initial_capital, status,
                          subprocess_pid, health_score, trust_rating,
                          current_prompt_version_id, created_at
                   FROM agents WHERE id = ?''',
                (agent_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        return self._row_to_agent(row) if row else None

    def list_all(self) -> list[Agent]:
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                '''SELECT id, persona_id, model_id, display_name,
                          rules_override, initial_capital, status,
                          subprocess_pid, health_score, trust_rating,
                          current_prompt_version_id, created_at
                   FROM agents ORDER BY created_at''',
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [self._row_to_agent(r) for r in rows]

    def update_status(self, agent_id: str, status: str) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(SCHEMA_AGENTS)
            con.execute(
                'UPDATE agents SET status = ? WHERE id = ?',
                (status, agent_id),
            )
            con.commit()
        finally:
            con.close()
```

- [ ] **Step 4: Wire factory in `storage/__init__.py`**

Add to the imports (extend the existing `from .base import (...)` block to include `Agent` and `AgentStore` if not already there — they should already be in from Task 2).

Add singleton holder, factory, setter, reset line. The final file:

```python
"""Storage factory — returns singletons of the configured backend."""
from __future__ import annotations

from .base import (
    Agent, AgentStore, CalendarStore, FinancialStore,
    KlineStore, ModelInfo, ModelStore, Persona, PersonaStore,
    PromptVersion, PromptVersionStore,
)

_kline: KlineStore | None = None
_financial: FinancialStore | None = None
_models: ModelStore | None = None
_calendar: CalendarStore | None = None
_personas: PersonaStore | None = None
_agents: AgentStore | None = None


def kline() -> KlineStore:
    global _kline
    if _kline is None:
        from .sqlite_kline import SQLiteKlineStore
        _kline = SQLiteKlineStore()
    return _kline


def financial() -> FinancialStore:
    global _financial
    if _financial is None:
        from .sqlite_financial import SQLiteFinancialStore
        _financial = SQLiteFinancialStore()
    return _financial


def models() -> ModelStore:
    global _models
    if _models is None:
        from .sqlite_models import SQLiteModelStore
        _models = SQLiteModelStore()
    return _models


def calendar() -> CalendarStore:
    global _calendar
    if _calendar is None:
        from .sqlite_calendar import SQLiteCalendarStore
        _calendar = SQLiteCalendarStore()
    return _calendar


def personas() -> PersonaStore:
    global _personas
    if _personas is None:
        from .sqlite_personas import SQLitePersonaStore
        _personas = SQLitePersonaStore()
    return _personas


def agents() -> AgentStore:
    global _agents
    if _agents is None:
        from .sqlite_agents import SQLiteAgentStore
        _agents = SQLiteAgentStore()
    return _agents


def set_kline(impl: KlineStore) -> None:
    global _kline
    _kline = impl


def set_financial(impl: FinancialStore) -> None:
    global _financial
    _financial = impl


def set_models(impl: ModelStore) -> None:
    global _models
    _models = impl


def set_calendar(impl: CalendarStore) -> None:
    global _calendar
    _calendar = impl


def set_personas(impl: PersonaStore) -> None:
    global _personas
    _personas = impl


def set_agents(impl: AgentStore) -> None:
    global _agents
    _agents = impl


def reset() -> None:
    global _kline, _financial, _models, _calendar, _personas, _agents
    _kline = None
    _financial = None
    _models = None
    _calendar = None
    _personas = None
    _agents = None
```

Note: `prompt_versions()` and `set_prompt_versions()` factories are added in Task 5. The agent tests above will pass only after Task 5 completes; keeping them here (written but failing for lack of prompt_versions) is a deliberate TDD shape.

- [ ] **Step 5: Partial run**

Run: `pytest tests/test_storage_agents.py::test_sqlite_agent_store_satisfies_protocol -v`
Expected: PASS (doesn't need prompt_versions).

Run: `pytest tests/test_storage_agents.py -v 2>&1 | tail -20`
Expected: most tests FAIL with `AttributeError: module 'storage' has no attribute 'prompt_versions'` or `set_prompt_versions` — this is expected; Task 5 will fix it.

- [ ] **Step 6: Commit**

```bash
git add storage/sqlite_agents.py storage/__init__.py tests/test_storage_agents.py
git commit -m "feat(p2a): SQLiteAgentStore with create_from_persona"
```

---

### Task 5: SQLitePromptVersionStore + auto-versioning complete

**Files:**
- Create: `storage/sqlite_prompt_versions.py`
- Modify: `storage/__init__.py` — add `prompt_versions()` factory
- Test: `tests/test_storage_prompt_versions.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_storage_prompt_versions.py`:

```python
"""SQLitePromptVersionStore — immutable prompt snapshots per agent."""


def test_sqlite_prompt_version_store_satisfies_protocol(tmp_path):
    from storage.base import PromptVersionStore
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    assert isinstance(SQLitePromptVersionStore(tmp_path=tmp_path), PromptVersionStore)


def test_insert_first_version(tmp_path):
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    store = SQLitePromptVersionStore(tmp_path=tmp_path)
    store.init_schema()

    v = store.insert(agent_id='a1', system_prompt='First prompt')
    assert v.version_number == 1
    assert v.system_prompt == 'First prompt'
    assert v.id > 0
    assert v.created_at is not None


def test_insert_increments_version(tmp_path):
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    store = SQLitePromptVersionStore(tmp_path=tmp_path)
    store.init_schema()

    store.insert(agent_id='a1', system_prompt='v1')
    v2 = store.insert(agent_id='a1', system_prompt='v2', note='rev for X')

    assert v2.version_number == 2
    assert v2.note == 'rev for X'


def test_versions_are_per_agent(tmp_path):
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    store = SQLitePromptVersionStore(tmp_path=tmp_path)
    store.init_schema()

    v1_a = store.insert(agent_id='a1', system_prompt='hi')
    v1_b = store.insert(agent_id='b1', system_prompt='hi')
    v2_a = store.insert(agent_id='a1', system_prompt='hi v2')

    # Each agent's counter is independent
    assert v1_a.version_number == 1
    assert v1_b.version_number == 1
    assert v2_a.version_number == 2


def test_get_latest_returns_newest(tmp_path):
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    store = SQLitePromptVersionStore(tmp_path=tmp_path)
    store.init_schema()

    store.insert(agent_id='a1', system_prompt='v1')
    store.insert(agent_id='a1', system_prompt='v2')
    latest = store.get_latest('a1')
    assert latest.version_number == 2
    assert latest.system_prompt == 'v2'


def test_get_latest_missing_returns_none(tmp_path):
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    store = SQLitePromptVersionStore(tmp_path=tmp_path)
    store.init_schema()
    assert store.get_latest('nonexistent') is None


def test_list_for_agent_ascending(tmp_path):
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    store = SQLitePromptVersionStore(tmp_path=tmp_path)
    store.init_schema()

    store.insert(agent_id='a1', system_prompt='v1')
    store.insert(agent_id='a1', system_prompt='v2')
    store.insert(agent_id='a1', system_prompt='v3')

    versions = store.list_for_agent('a1')
    assert [v.version_number for v in versions] == [1, 2, 3]
    assert versions[0].system_prompt == 'v1'
    assert versions[-1].system_prompt == 'v3'


def test_storage_factory_returns_sqlite_prompt_version_store(tmp_path):
    import storage
    storage.reset()
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    assert isinstance(storage.prompt_versions(), SQLitePromptVersionStore)
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `pytest tests/test_storage_prompt_versions.py -v`
Expected: FAIL — no module.

- [ ] **Step 3: Create `storage/sqlite_prompt_versions.py`**

Content (EXACTLY this):

```python
"""SQLitePromptVersionStore — immutable per-agent prompt history."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from data_schema.agent_state import (
    SCHEMA_PROMPT_VERSIONS, SCHEMA_PROMPT_VERSION_INDEX,
)

from .base import PromptVersion, PromptVersionStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


class SQLitePromptVersionStore(PromptVersionStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.execute(SCHEMA_PROMPT_VERSIONS)
            con.execute(SCHEMA_PROMPT_VERSION_INDEX)
            con.commit()
        finally:
            con.close()

    def insert(
        self, agent_id: str, system_prompt: str, note: str | None = None,
    ) -> PromptVersion:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(SCHEMA_PROMPT_VERSIONS)
            con.execute(SCHEMA_PROMPT_VERSION_INDEX)

            # Compute next version_number for this agent
            row = con.execute(
                'SELECT COALESCE(MAX(version_number), 0) FROM prompt_versions '
                'WHERE agent_id = ?',
                (agent_id,),
            ).fetchone()
            next_version = (row[0] if row else 0) + 1

            cursor = con.execute(
                '''INSERT INTO prompt_versions
                   (agent_id, version_number, system_prompt, note)
                   VALUES (?, ?, ?, ?)''',
                (agent_id, next_version, system_prompt, note),
            )
            new_id = cursor.lastrowid
            con.commit()

            # Fetch the created row to populate created_at
            row = con.execute(
                '''SELECT id, agent_id, version_number, system_prompt,
                          created_at, note
                   FROM prompt_versions WHERE id = ?''',
                (new_id,),
            ).fetchone()
        finally:
            con.close()
        return PromptVersion(
            id=row[0], agent_id=row[1], version_number=row[2],
            system_prompt=row[3], created_at=row[4], note=row[5],
        )

    def _row_to_version(self, row) -> PromptVersion:
        return PromptVersion(
            id=row[0], agent_id=row[1], version_number=row[2],
            system_prompt=row[3], created_at=row[4], note=row[5],
        )

    def get_latest(self, agent_id: str) -> PromptVersion | None:
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                '''SELECT id, agent_id, version_number, system_prompt,
                          created_at, note
                   FROM prompt_versions WHERE agent_id = ?
                   ORDER BY version_number DESC LIMIT 1''',
                (agent_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        return self._row_to_version(row) if row else None

    def list_for_agent(self, agent_id: str) -> list[PromptVersion]:
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                '''SELECT id, agent_id, version_number, system_prompt,
                          created_at, note
                   FROM prompt_versions WHERE agent_id = ?
                   ORDER BY version_number ASC''',
                (agent_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [self._row_to_version(r) for r in rows]
```

- [ ] **Step 4: Wire factory in `storage/__init__.py`**

Final form of `storage/__init__.py` (adds prompt_versions factory on top of what Task 4 produced):

```python
"""Storage factory — returns singletons of the configured backend."""
from __future__ import annotations

from .base import (
    Agent, AgentStore, CalendarStore, FinancialStore,
    KlineStore, ModelInfo, ModelStore, Persona, PersonaStore,
    PromptVersion, PromptVersionStore,
)

_kline: KlineStore | None = None
_financial: FinancialStore | None = None
_models: ModelStore | None = None
_calendar: CalendarStore | None = None
_personas: PersonaStore | None = None
_agents: AgentStore | None = None
_prompt_versions: PromptVersionStore | None = None


def kline() -> KlineStore:
    global _kline
    if _kline is None:
        from .sqlite_kline import SQLiteKlineStore
        _kline = SQLiteKlineStore()
    return _kline


def financial() -> FinancialStore:
    global _financial
    if _financial is None:
        from .sqlite_financial import SQLiteFinancialStore
        _financial = SQLiteFinancialStore()
    return _financial


def models() -> ModelStore:
    global _models
    if _models is None:
        from .sqlite_models import SQLiteModelStore
        _models = SQLiteModelStore()
    return _models


def calendar() -> CalendarStore:
    global _calendar
    if _calendar is None:
        from .sqlite_calendar import SQLiteCalendarStore
        _calendar = SQLiteCalendarStore()
    return _calendar


def personas() -> PersonaStore:
    global _personas
    if _personas is None:
        from .sqlite_personas import SQLitePersonaStore
        _personas = SQLitePersonaStore()
    return _personas


def agents() -> AgentStore:
    global _agents
    if _agents is None:
        from .sqlite_agents import SQLiteAgentStore
        _agents = SQLiteAgentStore()
    return _agents


def prompt_versions() -> PromptVersionStore:
    global _prompt_versions
    if _prompt_versions is None:
        from .sqlite_prompt_versions import SQLitePromptVersionStore
        _prompt_versions = SQLitePromptVersionStore()
    return _prompt_versions


def set_kline(impl: KlineStore) -> None:
    global _kline
    _kline = impl


def set_financial(impl: FinancialStore) -> None:
    global _financial
    _financial = impl


def set_models(impl: ModelStore) -> None:
    global _models
    _models = impl


def set_calendar(impl: CalendarStore) -> None:
    global _calendar
    _calendar = impl


def set_personas(impl: PersonaStore) -> None:
    global _personas
    _personas = impl


def set_agents(impl: AgentStore) -> None:
    global _agents
    _agents = impl


def set_prompt_versions(impl: PromptVersionStore) -> None:
    global _prompt_versions
    _prompt_versions = impl


def reset() -> None:
    global _kline, _financial, _models, _calendar
    global _personas, _agents, _prompt_versions
    _kline = None
    _financial = None
    _models = None
    _calendar = None
    _personas = None
    _agents = None
    _prompt_versions = None
```

- [ ] **Step 5: Run the prompt-versions tests AND the previously-failing agent tests**

Run: `pytest tests/test_storage_prompt_versions.py tests/test_storage_agents.py -v`
Expected: BOTH files fully green now (8 prompt_versions + 7 agent tests).

- [ ] **Step 6: Run full test suite to ensure nothing regressed**

Run: `pytest tests/ --tb=short 2>&1 | tail -5`
Expected: All ~120 tests still green (P1 104 + Task 1 3 + Task 2 6 + Task 3 8 + Task 4 7 + Task 5 8 = ~136).

- [ ] **Step 7: Commit**

```bash
git add storage/sqlite_prompt_versions.py storage/__init__.py tests/test_storage_prompt_versions.py
git commit -m "feat(p2a): SQLitePromptVersionStore + complete agent auto-versioning"
```

---

### Task 6: `personas/` package — 5 persona modules

**Files:**
- Create: `personas/__init__.py`
- Create: `personas/linyuan.py`
- Create: `personas/fuyou.py`
- Create: `personas/buffet.py`
- Create: `personas/soros.py`
- Create: `personas/quant_neutral.py`
- Test: `tests/test_personas_data.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_personas_data.py`:

```python
"""Persona data modules — sanity-check structure."""


def test_all_personas_registered():
    from personas import ALL_PERSONAS
    assert set(ALL_PERSONAS.keys()) == {
        'linyuan', 'fuyou', 'buffet', 'soros', 'quant_neutral',
    }


def test_every_persona_has_required_keys():
    from personas import ALL_PERSONAS
    required = {
        'id', 'name', 'style_desc', 'system_prompt',
        'default_pool', 'pool_filter', 'default_schedule',
        'default_rules', 'allowed_tools', 'is_builtin',
    }
    for key, data in ALL_PERSONAS.items():
        missing = required - set(data.keys())
        assert not missing, f'{key} missing keys: {missing}'


def test_persona_id_matches_registry_key():
    from personas import ALL_PERSONAS
    for key, data in ALL_PERSONAS.items():
        assert data['id'] == key


def test_every_pool_is_non_empty_and_valid_format():
    from personas import ALL_PERSONAS
    for key, data in ALL_PERSONAS.items():
        pool = data['default_pool']
        assert isinstance(pool, list)
        assert len(pool) > 0, f'{key} has empty default_pool'
        for code in pool:
            assert isinstance(code, str)
            assert '.' in code, f'{key}: code {code!r} must be like 600519.SH'
            prefix, suffix = code.split('.', 1)
            assert prefix.isdigit() and len(prefix) == 6
            assert suffix in ('SH', 'SZ'), f'{key}: code {code!r} has bad suffix'


def test_every_schedule_is_valid():
    from personas import ALL_PERSONAS
    valid = {'daily', 'weekly', 'monthly', 'intraday_5m'}
    for key, data in ALL_PERSONAS.items():
        assert data['default_schedule'] in valid, (
            f'{key}: bad schedule {data["default_schedule"]!r}'
        )


def test_every_default_rules_has_position_max_pct():
    """All built-in personas must cap single-position size."""
    from personas import ALL_PERSONAS
    for key, data in ALL_PERSONAS.items():
        rules = data['default_rules']
        assert 'position_max_pct' in rules, f'{key} missing position_max_pct rule'
        assert 0 < rules['position_max_pct'] <= 100


def test_system_prompts_are_substantial():
    """Each persona's prompt should be at least a few sentences."""
    from personas import ALL_PERSONAS
    for key, data in ALL_PERSONAS.items():
        assert len(data['system_prompt']) > 100, (
            f'{key} system_prompt suspiciously short'
        )


def test_allowed_tools_includes_get_kline():
    """Every persona needs K-line access; place_decision is always granted implicitly."""
    from personas import ALL_PERSONAS
    for key, data in ALL_PERSONAS.items():
        assert 'get_kline' in data['allowed_tools'], (
            f'{key} should include get_kline in allowed_tools'
        )
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `pytest tests/test_personas_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'personas'`.

- [ ] **Step 3: Create `personas/linyuan.py`**

Content (EXACTLY this):

```python
"""Persona: 林园风格 (Lin Yuan Style) — value investor.

Pool: a 15-stock subset of 白酒/医药/消费 core holdings. The Spec § 4.3 calls
for a 40-stock pool; for MVP we pick 15 well-known tickers that exercise the
backtest flow without requiring curated sector bucketing. Expand in a later
release.
"""

PERSONA = {
    'id': 'linyuan',
    'name': '林园风格',
    'style_desc': '价值投资 · 重仓白酒医药消费 · 长期持有',
    'system_prompt': """你是林园，一位坚守价值投资理念的基金经理。

投资原则：
1. 只买看得懂的行业，偏好白酒、医药、消费
2. 寻找"印钞机"企业：ROE > 15%，毛利率 > 30%
3. 安全边际至上：PE 低于行业均值 20%
4. 长期持有：平均持仓周期 > 6个月
5. 重仓龙头：单只股票 ≤ 30%，前5重仓 ≥ 70%

避免：追涨杀跌、短线交易、科技股/周期股/新概念

决策风格：
- 每周决策一次（rebalance_schedule=weekly）
- 先看 ROE 和毛利率，再看 PE 安全边际
- 市场情绪极端时（恐慌或狂热）反向操作
- 不强求每周都要交易；没有明确机会就持有现金""",
    'default_pool': [
        '600519.SH',   # 贵州茅台
        '000858.SZ',   # 五粮液
        '000568.SZ',   # 泸州老窖
        '600436.SH',   # 片仔癀
        '600276.SH',   # 恒瑞医药
        '000538.SZ',   # 云南白药
        '300760.SZ',   # 迈瑞医疗
        '600887.SH',   # 伊利股份
        '000651.SZ',   # 格力电器
        '000333.SZ',   # 美的集团
        '600690.SH',   # 海尔智家
        '601318.SH',   # 中国平安
        '600036.SH',   # 招商银行
        '000001.SZ',   # 平安银行
        '000725.SZ',   # 京东方A
    ],
    'pool_filter': None,
    'default_schedule': 'weekly',
    'default_rules': {
        'position_max_pct': 30.0,
        'cash_min_pct': 10.0,
        'ban_st': True,
        'ban_limit_up': True,
        'max_drawdown_pct': -15.0,
    },
    'allowed_tools': [
        'get_kline', 'get_financials', 'get_technical',
        'get_index', 'get_portfolio',
    ],
    'is_builtin': True,
}
```

- [ ] **Step 4: Create `personas/fuyou.py`**

Content:

```python
"""Persona: 浮游风格 (Fu You Style) — short-term 游资 speculator.

Pool: 15 high-turnover large-caps + 热门板块 龙头. The Spec § 4.3 has this
persona with a 50-stock dynamically-refreshed pool; MVP uses a static
approximation and defers the monthly refresh filter to a later release.
"""

PERSONA = {
    'id': 'fuyou',
    'name': '浮游风格',
    'style_desc': '短线游资 · 题材热点 · 快进快出',
    'system_prompt': """你是一位短线游资操盘手。

交易原则：
1. 追热点：关注涨停板、板块轮动、资金流入
2. 量价配合：放量突破优先，缩量回调观望
3. 快进快出：持仓 1-5 天，不恋战
4. 严格止损：单票亏损 > 4% 立即止损
5. 分仓操作：单票 ≤ 20%，同时持有 ≤ 5 只

避免：长期持有、逆势加仓、重仓单票

决策风格：
- 每日决策（rebalance_schedule=daily）
- 关注近期涨停/放量异动
- 没有明确信号时，优先持现金
- 对持仓的止损线（-4%）绝对服从""",
    'default_pool': [
        '300750.SZ',   # 宁德时代
        '002594.SZ',   # 比亚迪
        '688981.SH',   # 中芯国际
        '002415.SZ',   # 海康威视
        '300059.SZ',   # 东方财富
        '300014.SZ',   # 亿纬锂能
        '300142.SZ',   # 沃森生物
        '600570.SH',   # 恒生电子
        '002410.SZ',   # 广联达
        '300760.SZ',   # 迈瑞医疗
        '603501.SH',   # 韦尔股份
        '600584.SH',   # 长电科技
        '002241.SZ',   # 歌尔股份
        '002475.SZ',   # 立讯精密
        '603259.SH',   # 药明康德
    ],
    'pool_filter': {
        '_deferred': True,
        'note': 'Dynamic refresh (high-turnover + 涨停 last 10d) deferred to post-MVP',
    },
    'default_schedule': 'daily',
    'default_rules': {
        'position_max_pct': 20.0,
        'stop_loss_pct': -4.0,
        'max_holdings': 5,
        'cash_min_pct': 20.0,
        'ban_st': True,
        'max_drawdown_pct': -10.0,
    },
    'allowed_tools': [
        'get_kline', 'get_snapshot', 'get_technical',
        'get_index', 'get_portfolio',
    ],
    'is_builtin': True,
}
```

- [ ] **Step 5: Create `personas/buffet.py`**

Content:

```python
"""Persona: 巴菲特风格 (Buffett Style) — moat + safety margin + excellent management."""

PERSONA = {
    'id': 'buffet',
    'name': '巴菲特风格',
    'style_desc': '护城河 · 安全边际 · ROE > 15%',
    'system_prompt': """你是沃伦·巴菲特风格的价值投资者。

投资原则：
1. 护城河：只买具有持久竞争优势的企业
2. 安全边际：只在价格远低于内在价值时买入
3. ROE > 15%：连续 5 年高 ROE
4. 简单易懂：只投自己能理解的生意
5. 长期持有：ideally forever，月度评估

避免：频繁交易、热门概念、高负债企业

决策风格：
- 每月首个交易日决策（rebalance_schedule=monthly）
- 重点看 ROE 稳定性、管理层、估值折价
- 现金是持有机会，不是焦虑
- 月度决策常常就是"继续持有"""",
    'default_pool': [
        '600036.SH',   # 招商银行
        '002142.SZ',   # 宁波银行
        '601166.SH',   # 兴业银行
        '000001.SZ',   # 平安银行
        '601398.SH',   # 工商银行
        '600900.SH',   # 长江电力
        '600886.SH',   # 国投电力
        '600519.SH',   # 贵州茅台
        '000858.SZ',   # 五粮液
        '600887.SH',   # 伊利股份
        '000651.SZ',   # 格力电器
        '000333.SZ',   # 美的集团
        '601857.SH',   # 中国石油
        '601088.SH',   # 中国神华
        '000002.SZ',   # 万科A
    ],
    'pool_filter': None,
    'default_schedule': 'monthly',
    'default_rules': {
        'position_max_pct': 25.0,
        'cash_min_pct': 15.0,
        'ban_st': True,
        'max_drawdown_pct': -12.0,
    },
    'allowed_tools': [
        'get_kline', 'get_financials', 'get_technical',
        'get_index', 'get_portfolio',
    ],
    'is_builtin': True,
}
```

- [ ] **Step 6: Create `personas/soros.py`**

Content:

```python
"""Persona: 索罗斯反身性 (Soros Reflexivity) — macro + trend following."""

PERSONA = {
    'id': 'soros',
    'name': '索罗斯反身性',
    'style_desc': '宏观对冲 · 反身性 · 追逐趋势',
    'system_prompt': """你是乔治·索罗斯风格的宏观对冲基金经理。

投资原则：
1. 反身性：市场偏见创造机会，识别并利用
2. 宏观视野：关注利率、汇率、政策、地缘政治
3. 趋势跟随：认准方向后重仓出击
4. 承认错误：方向错了立即砍仓，不固执
5. 大量现金：不确定时保持高现金比例 (>50%)

避免：分散投资、均值回归假设、忽视宏观

决策风格：
- 每周决策（rebalance_schedule=weekly）
- 关注板块轮动、资金流向、指数强弱对比
- 不明朗时大幅持现（cash_min_pct=30 但建议随时调高到 50）
- 方向判断错误的瞬间就止损，不等反弹""",
    'default_pool': [
        '510300.SH',   # 沪深300 ETF
        '510050.SH',   # 上证50 ETF
        '510500.SH',   # 中证500 ETF
        '159915.SZ',   # 创业板 ETF
        '510880.SH',   # 红利 ETF
        '601318.SH',   # 中国平安
        '600030.SH',   # 中信证券
        '600837.SH',   # 海通证券
        '601088.SH',   # 中国神华
        '601857.SH',   # 中国石油
        '601899.SH',   # 紫金矿业
        '600362.SH',   # 江西铜业
        '600547.SH',   # 山东黄金
        '518880.SH',   # 黄金 ETF
        '159941.SZ',   # 纳指 ETF
    ],
    'pool_filter': None,
    'default_schedule': 'weekly',
    'default_rules': {
        'position_max_pct': 25.0,
        'cash_min_pct': 30.0,
        'max_drawdown_pct': -18.0,
    },
    'allowed_tools': [
        'get_kline', 'get_technical', 'get_index',
        'get_portfolio', 'get_news',
    ],
    'is_builtin': True,
}
```

- [ ] **Step 7: Create `personas/quant_neutral.py`**

Content:

```python
"""Persona: 量化中性 (Quant Neutral) — multi-factor + market/sector neutral."""

PERSONA = {
    'id': 'quant_neutral',
    'name': '量化中性',
    'style_desc': '多因子 · 市值中性 · 低回撤',
    'system_prompt': """你是一位量化中性策略基金经理。

投资原则：
1. 多因子模型：动量、反转、质量、价值、成长因子
2. 市值中性：多头 + 空头组合，暴露 ≈ 0
3. 行业中性：不押注单一行业
4. 系统化：按信号交易，不受情绪影响
5. 风险控制：最大回撤 < 3%，单日亏损 < 0.5%

注意：模拟回测中无法真正做空，可用高现金比例替代

避免：主观判断、集中持仓、追涨杀跌

决策风格：
- 每日决策（rebalance_schedule=daily）
- 按因子综合得分排序，取 Top N
- 单票上限很低（8%），强调持仓分散
- 严格控制日亏损""",
    'default_pool': [
        '600519.SH', '000858.SZ', '600276.SH', '300760.SZ',
        '600887.SH', '000333.SZ', '000651.SZ', '601318.SH',
        '600036.SH', '000001.SZ', '601398.SH', '601988.SH',
        '600900.SH', '600519.SH', '300750.SZ', '002594.SZ',
        '688981.SH', '002415.SZ', '000725.SZ', '601088.SH',
    ][:15],  # 15 unique HS300 constituents
    'pool_filter': {
        '_deferred': True,
        'note': 'Weekly multi-factor re-screening (momentum/reversal/quality/value/growth) deferred to post-MVP',
    },
    'default_schedule': 'daily',
    'default_rules': {
        'position_max_pct': 8.0,
        'max_holdings': 15,
        'daily_loss_limit_pct': 0.5,
        'max_drawdown_pct': -5.0,
        'cash_min_pct': 10.0,
        'ban_st': True,
    },
    'allowed_tools': [
        'get_kline', 'get_financials', 'get_technical',
        'get_index', 'get_portfolio',
    ],
    'is_builtin': True,
}
```

**Note on the `[:15]` slicing**: the naive list has duplicates for MVP brevity; slicing to 15 de-dups via ordering. Deduplicate properly when expanding:

Actually the list has duplicate `600519.SH`. Let me rewrite that pool without dupes:

Replace the `default_pool` block with:

```python
    'default_pool': [
        '600519.SH',   # 贵州茅台
        '000858.SZ',   # 五粮液
        '600276.SH',   # 恒瑞医药
        '300760.SZ',   # 迈瑞医疗
        '600887.SH',   # 伊利股份
        '000333.SZ',   # 美的集团
        '000651.SZ',   # 格力电器
        '601318.SH',   # 中国平安
        '600036.SH',   # 招商银行
        '000001.SZ',   # 平安银行
        '601398.SH',   # 工商银行
        '601988.SH',   # 中国银行
        '600900.SH',   # 长江电力
        '300750.SZ',   # 宁德时代
        '002594.SZ',   # 比亚迪
    ],
```

(15 unique codes, use this version, remove the `[:15]` slicing.)

- [ ] **Step 8: Create `personas/__init__.py`**

Content (EXACTLY this):

```python
"""Registry of built-in personas."""
from __future__ import annotations

from .linyuan import PERSONA as LINYUAN
from .fuyou import PERSONA as FUYOU
from .buffet import PERSONA as BUFFET
from .soros import PERSONA as SOROS
from .quant_neutral import PERSONA as QUANT_NEUTRAL


ALL_PERSONAS: dict[str, dict] = {
    'linyuan': LINYUAN,
    'fuyou': FUYOU,
    'buffet': BUFFET,
    'soros': SOROS,
    'quant_neutral': QUANT_NEUTRAL,
}
```

- [ ] **Step 9: Run the persona-data tests**

Run: `pytest tests/test_personas_data.py -v`
Expected: 8 PASS.

- [ ] **Step 10: Commit**

```bash
git add personas/ tests/test_personas_data.py
git commit -m "feat(p2a): 5 built-in personas (linyuan/fuyou/buffet/soros/quant_neutral)"
```

---

### Task 7: `personas.seed()` + E2E integration test

**Files:**
- Modify: `personas/__init__.py` — add `seed()` helper
- Test: `tests/test_personas_seed_e2e.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_personas_seed_e2e.py`:

```python
"""E2E: seed personas → create agent → verify prompt version chain."""


def _setup_stores(tmp_path):
    """Wire all stores pointing at tmp_path."""
    import storage
    from storage.sqlite_personas import SQLitePersonaStore
    from storage.sqlite_agents import SQLiteAgentStore
    from storage.sqlite_prompt_versions import SQLitePromptVersionStore
    from storage.sqlite_models import SQLiteModelStore

    pstore = SQLitePersonaStore(tmp_path=tmp_path)
    pstore.init_schema()
    storage.set_personas(pstore)

    agent_store = SQLiteAgentStore(tmp_path=tmp_path)
    agent_store.init_schema()
    storage.set_agents(agent_store)

    pv_store = SQLitePromptVersionStore(tmp_path=tmp_path)
    pv_store.init_schema()
    storage.set_prompt_versions(pv_store)

    # Models are needed so agent.model_id references resolve (though there's no FK enforcement in SQLite)
    m_store = SQLiteModelStore(tmp_path=tmp_path)
    m_store.init_schema()
    m_store.seed()
    storage.set_models(m_store)


def test_seed_inserts_all_5_personas(tmp_path):
    _setup_stores(tmp_path)
    from personas import seed
    seed()

    import storage
    all_seeded = storage.personas().list_all()
    assert {p.id for p in all_seeded} == {
        'linyuan', 'fuyou', 'buffet', 'soros', 'quant_neutral',
    }


def test_seed_is_idempotent(tmp_path):
    _setup_stores(tmp_path)
    from personas import seed
    seed()
    seed()
    seed()

    import storage
    assert len(storage.personas().list_all()) == 5


def test_seeded_persona_has_full_data(tmp_path):
    _setup_stores(tmp_path)
    from personas import seed
    seed()

    import storage
    linyuan = storage.personas().get('linyuan')
    assert linyuan is not None
    assert linyuan.name == '林园风格'
    assert linyuan.default_schedule == 'weekly'
    assert 'value' in linyuan.system_prompt.lower() or '价值投资' in linyuan.system_prompt
    assert len(linyuan.default_pool) >= 10
    assert linyuan.default_rules.get('position_max_pct') == 30.0
    assert 'get_kline' in linyuan.allowed_tools
    assert linyuan.is_builtin is True


def test_create_agent_from_seeded_persona_links_prompt_version(tmp_path):
    """Full chain: seeded persona → create_from_persona → v1 prompt snapshot."""
    _setup_stores(tmp_path)
    from personas import seed
    seed()

    import storage
    agent = storage.agents().create_from_persona(
        persona_id='linyuan',
        model_id='claude-opus-4-7',
        display_name='林园 · Claude Opus 4.7',
    )
    assert agent.persona_id == 'linyuan'
    assert agent.model_id == 'claude-opus-4-7'
    assert agent.current_prompt_version_id is not None

    # The prompt version should have the persona's system_prompt verbatim
    pv = storage.prompt_versions().get_latest(agent.id)
    assert pv is not None
    assert pv.version_number == 1
    assert '林园' in pv.system_prompt
    assert pv.id == agent.current_prompt_version_id


def test_multiple_agents_from_same_persona_with_different_models(tmp_path):
    """Spec § 4.2: same persona + different models = separate instances."""
    _setup_stores(tmp_path)
    from personas import seed
    seed()

    import storage
    a_claude = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='claude-opus-4-7',
        display_name='林园 · Claude Opus',
    )
    a_gpt = storage.agents().create_from_persona(
        persona_id='linyuan', model_id='gpt-5',
        display_name='林园 · GPT-5',
    )
    assert a_claude.id != a_gpt.id
    assert a_claude.persona_id == a_gpt.persona_id == 'linyuan'
    assert a_claude.model_id == 'claude-opus-4-7'
    assert a_gpt.model_id == 'gpt-5'

    all_agents = storage.agents().list_all()
    assert len(all_agents) == 2
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `pytest tests/test_personas_seed_e2e.py -v`
Expected: FAIL — `personas` has no `seed` attribute.

- [ ] **Step 3: Add `seed()` to `personas/__init__.py`**

Modify `personas/__init__.py` to append a `seed()` function:

```python
"""Registry of built-in personas."""
from __future__ import annotations

from .linyuan import PERSONA as LINYUAN
from .fuyou import PERSONA as FUYOU
from .buffet import PERSONA as BUFFET
from .soros import PERSONA as SOROS
from .quant_neutral import PERSONA as QUANT_NEUTRAL


ALL_PERSONAS: dict[str, dict] = {
    'linyuan': LINYUAN,
    'fuyou': FUYOU,
    'buffet': BUFFET,
    'soros': SOROS,
    'quant_neutral': QUANT_NEUTRAL,
}


def seed() -> int:
    """Idempotently upsert all 5 built-in personas into storage.personas().

    Returns count of personas written.
    """
    from storage import personas as _personas_factory
    from storage.base import Persona

    store = _personas_factory()
    store.init_schema()

    for data in ALL_PERSONAS.values():
        persona = Persona(
            id=data['id'],
            name=data['name'],
            style_desc=data['style_desc'],
            system_prompt=data['system_prompt'],
            default_pool=data['default_pool'],
            pool_filter=data['pool_filter'],
            default_schedule=data['default_schedule'],
            default_rules=data['default_rules'],
            allowed_tools=data['allowed_tools'],
            is_builtin=data['is_builtin'],
        )
        store.upsert(persona)
    return len(ALL_PERSONAS)
```

- [ ] **Step 4: Run the E2E test**

Run: `pytest tests/test_personas_seed_e2e.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Seed real DB** (optional but recommended)

```bash
python -c "
from personas import seed
from storage import personas, models
models().init_schema()
models().seed()
n = seed()
print(f'Seeded {n} personas:')
for p in personas().list_all():
    print(f'  {p.id:15s} {p.name} [{p.default_schedule}] — {len(p.default_pool)} stocks')
"
```

Expected output lists 5 personas with their pools.

- [ ] **Step 6: Full test suite sanity check**

Run: `pytest tests/ --tb=short 2>&1 | tail -5`
Expected: All green; test count is ~140.

- [ ] **Step 7: Commit**

```bash
git add personas/__init__.py tests/test_personas_seed_e2e.py
git commit -m "feat(p2a): personas.seed() + E2E persona→agent→prompt chain test"
```

---

## Self-Review

### Spec Coverage

- ✅ **§ 4.1 Four-Dimensional Agent Model** (persona + model + rules + schedule) — `Persona` dataclass covers all four
- ✅ **§ 4.2 Multi-Instance Mode** — `create_from_persona` explicitly supports multiple instances per persona; `test_multiple_agents_from_same_persona_with_different_models` proves
- ✅ **§ 4.3 Five Built-in Personas** — Task 6 delivers all 5 with system prompts, pools, schedules, rules, and allowed_tools
- ✅ **§ 10.1 Prompt Versioning schema** — `prompt_versions` table with `(agent_id, version_number)` PK
- ✅ **§ 10.2 Auto-versioning** — `create_from_persona` inserts v1; future plans (P2e) will add edit-and-bump
- ⏭️ Intentionally deferred to other P2 sub-plans: redlines (P2b), audit_log (P2b), backtest_results (P2c), baselines (P2d), API (P2e)

### Placeholder Scan

No "TBD" / "implement later" / "similar to Task N" / empty test bodies. Every step has concrete code or commands.

### Type Consistency

- `Persona` / `Agent` / `PromptVersion` — defined Task 2, used Tasks 3-7 with identical field names
- `create_from_persona(persona_id, model_id, display_name, rules_override, initial_capital)` — same signature in Tasks 4 Protocol and 4 implementation and 7 tests
- `storage.personas()` / `storage.agents()` / `storage.prompt_versions()` — factory-function names consistent across tasks 3-7

### Dependencies

```
Task 1 (schemas)
Task 2 (dataclasses + protocols) ← needs 1
Task 3 (SQLitePersonaStore)       ← needs 1 + 2
Task 4 (SQLiteAgentStore)         ← needs 1 + 2 + 3 (imports personas factory)
                                    + 5 (imports prompt_versions factory — tests will be red until 5)
Task 5 (SQLitePromptVersionStore) ← needs 1 + 2; fixes Task 4's red tests
Task 6 (persona data modules)     ← needs 2 (Persona dataclass not required by data modules, but
                                            test_personas_data.py references structure only)
Task 7 (seed + E2E)               ← needs 3 + 4 + 5 + 6
```

Strict order: 1 → 2 → 3 → 4 → 5 → 6 → 7. Tasks 3/4/5 are tightly coupled — Task 4 writes failing tests that Task 5 turns green. This is intentional TDD shape, not an error.

### Execution Notes

- Real DB path is `data/agent_state.db`. P1 created it with the `llm_models` table; P2a adds three more tables. `PRAGMA journal_mode=WAL` is set at every store's init.
- Agent tests reference `claude-opus-4-7` and `gpt-5` — these model ids exist in `llm_models` seeded by P1 Task 5. No new model seeding needed.
- `tests/conftest.py` has an autouse fixture `_reset_storage_between_tests` that calls `storage.reset()`. All new tests inherit this reset behavior automatically.
- Estimated total: 2 days single-developer; ~1.5 days with parallel dispatch of Tasks 3/4/5 (though Task 4 blocks on Task 5 for final green).
