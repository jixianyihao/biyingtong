# P3-F Phase 1 — Agent Deployment Architecture (No Real Money)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.
>
> **CRITICAL SCOPE LIMIT:** This plan implements deploy/stop/proposal infrastructure ONLY. NO actual TDX order placement. Approved proposals just set `status='approved'` in DB — they do NOT execute. Real-money execution is P3-F-Phase 2 and requires SEPARATE explicit user consent.

**Goal:** Let user "deploy" an agent so it runs in its own process and emits trade proposals on its schedule (daily/weekly/intraday). User reviews proposals in UI and approves/rejects. Approved = state change only, no real trade.

**Why split into Phase 1 / 2:**
- Phase 1 = pure architecture + UI flow + zero financial risk
- Phase 2 = wire approved proposals to TDX `place_order()` — irreversible, needs separate sign-off
- Splitting means Phase 1 can ship + be tested without any blast radius

**Architecture:**
- Each deployed agent → independent subprocess (`runner/agent_process.py`) launched by Flask via `subprocess.Popen`
- Subprocess writes structured JSONL to a per-agent log file; Flask tails it
- Subprocess on schedule fires AgentRunner.run_day → produces decisions → POSTs them as PROPOSALS to a Flask endpoint (in-process HTTP since both run on same machine)
- Proposals stored in new `trade_proposals` table with status: `pending | approved | rejected | expired`
- UI shows pending proposals in /risk page (already has "RiskMonitor" panel) + per-agent in /agent
- User clicks approve/reject → state change only, no execution
- Crash recovery: on startup, Flask checks deployed-agents table + restarts any whose process is dead

**Tech Stack:** Python 3.10 / Flask / subprocess / SQLite / React 19 / TypeScript

---

## File Structure

**Backend (new):**
- `runner/__init__.py`
- `runner/agent_process.py` — main entry point for the per-agent subprocess
- `runner/proposal_emitter.py` — helper to POST proposals to Flask
- `runner/scheduler.py` — schedule logic (daily/weekly/intraday tick computation)
- `data_schema/deployment_state.py` — DDL for `trade_proposals` + `deployed_agents`
- `storage/sqlite_proposals.py` — TradeProposalStore impl
- `storage/sqlite_deployed_agents.py` — DeployedAgentStore impl
- `storage/base.py` — TradeProposalStore + DeployedAgentStore Protocols
- `storage/__init__.py` — factory wiring
- `api/deploy.py` — POST/DELETE /api/agents/:id/deploy + GET /api/agents/:id/deploy_status
- `api/proposals.py` — GET /api/proposals + POST /api/proposals/:id/approve | reject + POST internal /api/proposals (subprocess→Flask)
- `tests/test_p3f_phase1.py`

**Backend (modify):**
- `api/__init__.py` — register new submodules
- (no other modifications)

**Frontend:**
- `frontend/src/api/types.ts` — TradeProposal, DeployStatus, etc.
- `frontend/src/api/client.ts` — 6 new methods
- `frontend/src/api/hooks.ts` — 6 new hooks
- `frontend/src/components/ProposalsPanel.tsx` — list + approve/reject
- `frontend/src/components/DeployButton.tsx` — start/stop in Agent.tsx
- `frontend/src/pages/Agent.tsx` — mount DeployButton + ProposalsPanel per agent
- `frontend/src/pages/Risk.tsx` — mount global ProposalsPanel for "pending review" inbox
- (Live page stays as ComingSoon — that's Phase 2 territory)

---

### Task 1: schemas + Protocols + dataclasses

**Files:**
- Create: `data_schema/deployment_state.py`
- Modify: `storage/base.py` — TradeProposalStore + DeployedAgentStore Protocols + dataclasses
- Test: `tests/test_p3f_phase1.py` (new)

Schema:

```sql
CREATE TABLE IF NOT EXISTS deployed_agents (
    agent_id     TEXT PRIMARY KEY,
    pid          INTEGER NOT NULL,
    started_at   DATETIME NOT NULL,
    status       TEXT NOT NULL,  -- 'running' | 'stopped' | 'crashed'
    schedule     TEXT NOT NULL   -- 'daily'|'weekly'|'intraday_5m'
);

CREATE TABLE IF NOT EXISTS trade_proposals (
    id           TEXT PRIMARY KEY,
    agent_id     TEXT NOT NULL,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decision_at  DATETIME NOT NULL,  -- when the agent made it
    action       TEXT NOT NULL,      -- 'buy'|'sell'|'hold'
    code         TEXT,
    shares       INTEGER,
    price        REAL,
    reason       TEXT,
    thinking     TEXT,
    status       TEXT NOT NULL,      -- 'pending'|'approved'|'rejected'|'expired'
    decided_by   TEXT,                -- user id (always 'user' in MVP)
    decided_at   DATETIME
);
CREATE INDEX IF NOT EXISTS proposals_by_status ON trade_proposals(status, created_at DESC);
CREATE INDEX IF NOT EXISTS proposals_by_agent  ON trade_proposals(agent_id, created_at DESC);
```

Protocol methods (additive — same dependency-inversion as P3-A/B/C):

```python
@runtime_checkable
class TradeProposalStore(Protocol):
    def init_schema(self) -> None: ...
    def insert(self, proposal: TradeProposal) -> None: ...
    def get(self, proposal_id: str) -> TradeProposal | None: ...
    def list_pending(self, agent_id: str | None = None, limit: int = 100) -> list: ...
    def list_for_agent(self, agent_id: str, limit: int = 100) -> list: ...
    def update_status(self, proposal_id: str, status: str, decided_by: str | None = None) -> bool: ...
```

```python
@runtime_checkable
class DeployedAgentStore(Protocol):
    def init_schema(self) -> None: ...
    def upsert(self, agent_id: str, pid: int, schedule: str) -> None: ...
    def get(self, agent_id: str): ...
    def list_running(self) -> list: ...
    def mark_stopped(self, agent_id: str) -> None: ...
    def mark_crashed(self, agent_id: str) -> None: ...
```

Dataclasses for `TradeProposal` + `DeployedAgent` in storage/base.py.

Tests: 3-4 dataclass shape + Protocol-has-method tests.

Commit.

---

### Task 2: SQLite impls

`storage/sqlite_proposals.py` + `storage/sqlite_deployed_agents.py` mirror existing patterns. ~80 lines each.

Tests: roundtrip insert/get + list_pending filter + update_status.

Commit.

---

### Task 3: subprocess runner — `runner/agent_process.py`

Standalone Python script. Args:
- `--agent-id` — required
- `--flask-url` — Flask base URL (default `http://127.0.0.1:5000`)

Lifecycle:
1. On start: load agent + persona + model from SQLite (read-only)
2. Build LLM via `llm.factory.build_llm(agent.model_id)`
3. Compute schedule from `persona.default_schedule`
4. Loop:
   - Sleep until next scheduled tick
   - Build a fake "today's portfolio" — Phase 1 just uses `initial_capital` cash, no real positions
   - Call `AgentRunner.run_day` to get decisions
   - For each decision: POST proposal to `{flask_url}/api/proposals` with HTTP basic auth or a shared secret env var
5. SIGTERM handler: stop loop cleanly + exit 0
6. Uncaught exception: log + exit 1 (Flask supervisor restarts it)

Tests: launch subprocess in pytest with a mocked Flask (use `responses` lib or a tiny inline server). Verify a proposal POST after a forced tick.

Commit.

---

### Task 4: Flask deploy/stop/list endpoints — `api/deploy.py`

```
POST /api/agents/:id/deploy → spawn subprocess + insert into deployed_agents → 202
POST /api/agents/:id/stop   → SIGTERM the pid + mark stopped → 200
GET  /api/agents/:id/deploy_status → {pid, status, started_at, schedule}
```

Implementation: use `subprocess.Popen` with `start_new_session=True` so Flask can shut down cleanly without killing children.

Crash recovery: on Flask startup (`app.py`), call `storage.deployed_agents().list_running()` and check each PID is still alive (psutil or `os.kill(pid, 0)`); mark dead ones as `crashed` and optionally auto-restart.

Tests: mock `subprocess.Popen` to verify command + args. Test crash detection logic with a fake dead pid.

Commit.

---

### Task 5: Proposals API — `api/proposals.py`

```
GET   /api/proposals?status=pending&agent_id=...&limit=100
GET   /api/proposals/:id
POST  /api/proposals (internal, called by subprocess) — requires shared-secret header
POST  /api/proposals/:id/approve
POST  /api/proposals/:id/reject
```

CRITICAL: The internal POST endpoint that subprocess uses to register proposals must validate a shared secret (env var `BIYINGTONG_PROPOSAL_TOKEN`) so external callers can't spoof proposals.

approve/reject endpoints: change DB state + return updated proposal. NO TDX call. Phase 2 will wire that in.

Tests: full HTTP coverage including auth check, status transitions, list filtering.

Commit.

---

### Task 6: Frontend — types + client + hooks

Boilerplate similar to P3-B Task 7. ~6 hooks: useProposals, useApproveProposal, useRejectProposal, useDeployAgent, useStopAgent, useDeployStatus.

Commit.

---

### Task 7: ProposalsPanel component

Renders pending proposals as cards. Each card: agent display_name + decision summary (action + code + shares + price + reason) + Approve/Reject buttons. Clicking approve fires mutation → list refetches.

Variant: takes optional `agentId` filter. When omitted, shows global inbox.

Commit.

---

### Task 8: DeployButton in Agent detail

A toggle button: "部署" / "已部署 · 停止". Shows current pid + uptime when running.

Commit.

---

### Task 9: Mount in pages

- Agent.tsx detail panel: DeployButton + ProposalsPanel(agentId)
- Risk.tsx: ProposalsPanel(undefined) as global pending inbox

Commit.

---

### Task 10: Crash recovery on Flask startup

In `app.py` after blueprint registration, run a startup hook:
```python
def _startup_recover_deployed_agents():
    import storage
    import os
    rows = storage.deployed_agents().list_running()
    for r in rows:
        if not _pid_alive(r.pid):
            storage.deployed_agents().mark_crashed(r.agent_id)
            # Optional: auto-restart based on agent.status
```

Commit.

---

### Task 11: E2E smoke + roadmap

- pytest -q full
- frontend build
- Manual: deploy a test agent → wait for tick → see proposal appear → approve → status changes
- Update status-and-roadmap

Commit + finishing-a-development-branch.

---

## Self-Review

**Spec coverage (§13 + §15.2):**
- §13.1 subprocess architecture ✅
- §13.2 message router (Flask + HTTP, not WebSocket — simpler) ✅
- §13.3 crash recovery ✅
- §15.2 POST /api/agents/:id/deploy ✅
- §15.2 POST /api/agents/:id/stop ✅
- §15.2 POST /api/agents/:id/approve ✅ (Phase 1 — DB only)
- §15.2 POST /api/agents/:id/reject ✅ (Phase 1 — DB only)
- §16 RiskMonitor → 待审批 ✅

**Explicitly NOT covered (Phase 2):**
- Real TDX `place_order()` call on approval
- Position state sync from TDX
- Slippage / partial fills handling
- Token cost tracking on live LLM calls

**Risks of Phase 1 alone:**
- Subprocesses + persistent Python processes = process leak if Flask crashes
- LLM API costs accrue on real schedule (not just on user-triggered backtest)
- Crash recovery needs filesystem permissions (psutil or `os.kill(pid, 0)`)

**Mitigations:**
- Subprocess writes a heartbeat file; supervisor checks freshness
- LLM cost guard: env var `MAX_LIVE_LLM_CALLS_PER_DAY` enforced in subprocess
- Document that Flask must run as a process owner that can signal child PIDs

---

## Execution

Subagent-driven. Estimated total: ~3 days single-person. Several tasks parallelizable:

- T1 + T2 sequential (T2 depends on T1)
- T3 + T4 + T5 parallelizable (different files)
- T6 + T7 + T8 parallelizable (different frontend files)
- T9 + T10 sequential (depend on the rest)
- T11 final

Aggressive parallel execution: ~1.5 days.
