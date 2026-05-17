# Reagent Architecture Restructuring — 5 Pillars

## Context

Reagent is an AI smart contract agent with 6 pipeline stages managed by an adaptive orchestrator. It has 4 integrations (GitLab, Bright Data, Nosana, GitHub Codespaces), but the Codespaces integration is broken (router imports from a non-existent module, missing 4 classes, not registered in main.py). There's no event system for frontend consumption, no structured context injection, no mode switching, and no compute tier routing.

This restructuring addresses:
- **Codespaces as free-tier primary compute** — run code in user's GitHub, zero platform cost
- **Nosana as premium compute** — GPU/heavy tasks and paid users
- **Event logging & streaming** — frontend needs real-time workflow updates
- **Context injection** — "mind building" so the agent learns from user input across stages
- **Mode switching** — Plan (analyze only), Orchestrate (full pipeline), Code (direct generation)

---

## Phase 1: Compute Foundation — Fix Codespaces + Abstraction Layer

### 1A. Add missing classes to Codespaces client

**Modify:** `reagent/github_codespaces_full_client.py` — append 4 classes that the router tries to import:

- `SecureTokenStore` — Fernet-based encrypt/decrypt/revoke for GitHub OAuth tokens
- `CodespaceConfig(BaseModel)` — repo, branch, machine type, idle timeout, retention
- `CodespaceWorkflow(BaseModel)` — workflow_id, user_id, codespace_name, status, logs, timestamps
- `CodespaceOrchestrator` — high-level orchestration: `setup_codespace()`, `execute_workflow_via_commits()`, `execute_command()`, `cleanup_codespace()`

### 1B. Fix router import

**Modify:** `reagent/routers/github_codespace_router.py` line 17
- Change `from github_codespace_client import ...` → `from github_codespaces_full_client import ...`

### 1C. Register in main.py

**Modify:** `reagent/main.py` — add `from routers.github_codespace_router import github_router` + `app.include_router(github_router)`
**Modify:** `reagent/routers/__init__.py` — export `github_router`

### 1D. Compute abstraction layer

**Create:** `reagent/compute.py`

```python
class ComputeTier(str, Enum):       # CODESPACES | NOSANA
class ComputeCapability(str, Enum):  # COMPILE | TEST | GPU | DEPLOY | SHELL

class ComputeResult(BaseModel):     # exit_code, stdout, stderr, success, backend, metadata

class ComputeBackend(Protocol):
    tier: ComputeTier
    capabilities: set[ComputeCapability]
    async def execute(command, cwd, env, timeout) -> ComputeResult
    async def upload_file(path, content) -> str
    async def download_file(path) -> str
    async def is_available() -> bool

class CodespaceComputeBackend:   # wraps GitHubCodespacesClient
class NosanaComputeBackend:      # wraps NosanaClient
class ComputeRouter:             # tier selection logic:
    # 1. Free user + no GPU → Codespaces
    # 2. GPU needed OR premium user → Nosana
    # 3. Fallback → local subprocess
    def select_backend(capabilities, user_tier) -> ComputeBackend
    async def execute(command, **kwargs) -> ComputeResult
```

### 1E. Compute AgentField router

**Create:** `reagent/routers/compute_router.py` — exposes `select_compute_tier`, `execute_command`, `get_compute_status` as skills

**Create:** `reagent/tests/test_compute.py` — unit tests for ComputeRouter tier selection

---

## Phase 2: Event Logging & Streaming

### 2A. Event system core

**Create:** `reagent/events.py`

```python
class EventType(str, Enum):
    WORKFLOW_START, WORKFLOW_STATUS, WORKFLOW_COMPLETE, WORKFLOW_FAILED,
    STAGE_START, STAGE_PROGRESS, STAGE_COMPLETE, STAGE_ERROR,
    FEEDBACK_LOOP, LOG_LINE, COMPUTE_TIER_SELECTED, CONTEXT_INJECTED

class WorkflowEvent:       # event_type, workflow_id, stage, timestamp, data, message

class EventBus:            # in-process async pub/sub
    async def emit(event)                    # fan-out to all subscriber queues
    def subscribe(workflow_id=None) -> Queue  # one queue per subscriber
    def unsubscribe(subscriber_id)
    def get_history(workflow_id, limit) -> list  # ring buffer store
```

Singleton: `get_event_bus()`

### 2B. SSE streaming router

**Create:** `reagent/routers/events_router.py`

- `subscribe_workflow_events(workflow_id)` — SSE stream (NDJSON `data: {...}` lines)
- `get_workflow_events(workflow_id, limit)` — historical events
- `websocket_events(websocket, workflow_id)` — WebSocket endpoint

Register in `main.py` and `routers/__init__.py`.

### 2C. Wire events into orchestrator

**Modify:** `reagent/routers/orchestrator_router.py` — emit `WorkflowEvent` at:
- Workflow start/complete/failed
- Each stage start/complete/error
- Feedback loops
- Compute tier selections (Phase 5)

### 2D. Tests

**Create:** `reagent/tests/test_events.py` — EventBus emit/subscribe/history tests

---

## Phase 3: Context Injection (Mind Building)

### 3A. AgentContext system

**Create:** `reagent/context.py`

```python
class ContextSource(str, Enum):
    USER_INPUT, STAGE_OUTPUT, ERROR_RECOVERY, MARKET_RESEARCH, PREFERENCE, PROJECT_CONTEXT

class ContextEntry(BaseModel):    # source, content, stage, timestamp, relevance_score
class AgentContext(BaseModel):
    workflow_id: str
    user_id: str | None
    entries: list[ContextEntry]
    project_context: dict
    user_preferences: dict
    active_recovery: str | None
    user_tier: str = "free"           # free | premium
    github_connected: bool = False
    nosana_connected: bool = False

    def add_entry(source, content, stage)
    def set_recovery_context(error, stage)
    def clear_recovery_context()
    def build_injection_prompt(max_entries=20) -> str   # condensed prompt for AI
    def to_dict() / from_dict(data)                    # serialize for persistence
```

### 3B. Wire context into stage routers

**Modify:** each stage router (`ideation_router.py`, `coding_router.py`, `testing_router.py`, `auditing_router.py`, `deployment_router.py`, `monitoring_router.py`):
- Add `context: dict | None = None` parameter (keep `recovery_context` for backward compat)
- If context provided, deserialize to `AgentContext`, call `build_injection_prompt()`, append to AI prompt

### 3C. Wire context into orchestrator

**Modify:** `reagent/routers/orchestrator_router.py`:
- Create `AgentContext` at workflow start
- Add user input as `ContextEntry`
- Pass `context.to_dict()` to every `app.call()` to stage routers
- After each stage, add `ContextEntry(source=STAGE_OUTPUT, ...)`
- On failures, call `context.set_recovery_context()`
- Emit `CONTEXT_INJECTED` event on each injection

### 3D. Tests

**Create:** `reagent/tests/test_context.py` — AgentContext accumulation, injection prompt, serialization

---

## Phase 4: Mode Switching (Plan, Orchestrate, Code)

### 4A. Mode definitions

**Create:** `reagent/modes.py`

```python
class ExecutionMode(str, Enum):
    PLAN = "plan"              # AI analysis only, no execution
    ORCHESTRATE = "orchestrate"  # Full pipeline with feedback loops
    CODE = "code"               # Direct code generation, skip planning

class ModeConfig(BaseModel):
    mode: ExecutionMode = ExecutionMode.ORCHESTRATE
    plan_depth: str = "detailed"          # summary | detailed | comprehensive
    max_iterations: int = 20              # orchestrate mode
    max_retries_per_stage: int = 3        # orchestrate mode
    code_include_tests: bool = True       # code mode
    code_include_deployment: bool = False # code mode
    preferred_compute_tier: str = "codespaces"
```

### 4B. Plan mode router

**Create:** `reagent/routers/plan_router.py`

```python
class PlanOutput(BaseModel):
    requirements_analysis: str
    proposed_architecture: str
    stage_plan: list[dict]          # [{stage, description, dependencies}]
    risk_assessment: str
    cost_estimate: dict | None
    recommendations: list[str]

@plan_router.reasoner(tags=["ai", "planning"])
async def analyze_and_plan(requirements, context=None, plan_depth="detailed") -> dict
```

### 4C. Code mode router

**Create:** `reagent/routers/code_router.py`

```python
@code_router.reasoner(tags=["ai", "generation", "direct"])
async def direct_code_generation(requirements, context=None, target_blockchain="ethereum", include_tests=True) -> dict
```

### 4D. Modify orchestrator

**Modify:** `reagent/routers/orchestrator_router.py`:

Add `mode: str = "orchestrate"` and `context: dict | None = None` params to `orchestrate_contract_development_adaptive`:

- If `mode == "plan"` → `app.call("reagent.plan_analyze_and_plan", ...)`
- If `mode == "code"` → `app.call("reagent.code_direct_code_generation", ...)`
- If `mode == "orchestrate"` → existing adaptive loop (enhanced with context + events)

### 4E. Register new routers

**Modify:** `reagent/routers/__init__.py` + `reagent/main.py` — add `plan_router`, `code_router`

### 4F. Tests

**Create:** `reagent/tests/test_modes.py` — mode dispatch, PlanOutput schema, code generation flow

---

## Phase 5: Compute Tier Routing + Integration

### 5A. Wire ComputeRouter into orchestrator

**Modify:** `reagent/routers/orchestrator_router.py` — replace direct subprocess/GitLab-only execution paths with `ComputeRouter` calls:
- `_execute_coding` → use `ComputeBackend.execute()` for `solc` compilation
- `_execute_testing` → use `ComputeBackend.execute()` for `forge test`
- `_execute_deployment` → use `ComputeBackend.execute()` for deploy scripts

### 5B. Tier selection from context

The `ComputeRouter.select_backend()` reads `user_tier`, `github_connected`, `nosana_connected` from `AgentContext`:
- Free user + Codespaces connected + no GPU → Codespaces
- GPU required → Nosana (regardless of tier)
- Premium user → Nosana (preferred)
- Codespaces unavailable → escalate to Nosana or local fallback

### 5C. Escalation events + context

When compute escalates mid-workflow (e.g., Codespaces fails → Nosana), emit `COMPUTE_TIER_SELECTED` event and inject context entry.

### 5D. Tests

**Create:** `reagent/tests/test_compute_routing.py` — tier selection scenarios, escalation, fallback

---

## Files Summary

| Phase | Action | File |
|-------|--------|------|
| 1 | MODIFY | `reagent/github_codespaces_full_client.py` |
| 1 | MODIFY | `reagent/routers/github_codespace_router.py` |
| 1 | MODIFY | `reagent/main.py` |
| 1 | MODIFY | `reagent/routers/__init__.py` |
| 1 | CREATE | `reagent/compute.py` |
| 1 | CREATE | `reagent/routers/compute_router.py` |
| 1 | CREATE | `reagent/tests/test_compute.py` |
| 2 | CREATE | `reagent/events.py` |
| 2 | CREATE | `reagent/routers/events_router.py` |
| 2 | MODIFY | `reagent/routers/orchestrator_router.py` |
| 2 | CREATE | `reagent/tests/test_events.py` |
| 3 | CREATE | `reagent/context.py` |
| 3 | MODIFY | `reagent/routers/ideation_router.py` |
| 3 | MODIFY | `reagent/routers/coding_router.py` |
| 3 | MODIFY | `reagent/routers/testing_router.py` |
| 3 | MODIFY | `reagent/routers/auditing_router.py` |
| 3 | MODIFY | `reagent/routers/deployment_router.py` |
| 3 | MODIFY | `reagent/routers/monitoring_router.py` |
| 3 | CREATE | `reagent/tests/test_context.py` |
| 4 | CREATE | `reagent/modes.py` |
| 4 | CREATE | `reagent/routers/plan_router.py` |
| 4 | CREATE | `reagent/routers/code_router.py` |
| 4 | CREATE | `reagent/tests/test_modes.py` |
| 5 | MODIFY | `reagent/routers/orchestrator_router.py` (compute calls) |
| 5 | CREATE | `reagent/tests/test_compute_routing.py` |

---

## Verification

After each phase, run: `cd reagent && python -m pytest tests/ -v`

End-to-end verification after Phase 5:
1. Start agent: `cd reagent && python main.py`
2. Test Codespaces connect: `POST /orchestrate/...` with `mode="plan"`
3. Test plan mode returns PlanOutput without execution
4. Test code mode generates Solidity directly
5. Test orchestrate mode with Codespaces backend (mock if no real Codespace)
6. Verify SSE stream at `/events/subscribe_workflow_events`
7. Verify context accumulates across stages (check `CONTEXT_INJECTED` events)
8. Verify compute tier selection: free→Codespaces, premium→Nosana
