# Adaptive Orchestration with Feedback Loops

## Overview

The Reagent orchestrator now supports **adaptive orchestration** with intelligent feedback loops and error recovery. Instead of a rigid linear workflow, the system uses AI to decide the next action based on stage results, enabling automatic error recovery and iterative refinement.

## Key Features

### 1. **Feedback Loops**
Agents can return to previous stages when needed:
- **Coding → Ideation**: When code generation needs better specifications
- **Testing → Coding**: When tests fail and code needs fixes
- **Auditing → Coding**: When security issues are found
- **Deployment → Coding**: When deployment fails due to code issues

### 2. **AI-Powered Decision Making**
After each stage, an AI reasoner analyzes the result and decides:
- ✅ **Proceed** to next stage (if successful)
- 🔄 **Go back** to previous stage (if fixable error)
- 🔁 **Retry** current stage (if transient error)
- ❌ **Fail** workflow (if max retries exceeded)

### 3. **Error Recovery**
- Automatic retry with context from failures
- Maximum retry limits per stage (default: 3)
- Intelligent error analysis and routing
- Context preservation across retries

### 4. **State Management**
- Complete workflow state tracking
- In-memory state for fast access
- GitLab issue integration for persistence
- Recovery from interruptions

## Architecture

### Linear vs Adaptive Flow

**Old Linear Flow:**
```
Ideation → Coding → Testing → Auditing → Deployment → Monitoring
   ↓         ↓         ↓          ↓            ↓           ↓
 Fixed    Fixed     Fixed      Fixed        Fixed       Fixed
```

**New Adaptive Flow:**
```
                    ┌─────────────┐
                    │  Ideation   │
                    └──────┬──────┘
                           ↓
                    ┌──────────────┐
              ┌────→│    Coding    │←────┐
              │     └──────┬───────┘     │
              │            ↓              │
              │     ┌──────────────┐     │
              │     │   Testing    │─────┘
              │     └──────┬───────┘
              │            ↓
              │     ┌──────────────┐
              └─────│   Auditing   │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │  Deployment  │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │  Monitoring  │
                    └──────────────┘
```

### Workflow State

```python
class WorkflowState:
    workflow_id: str              # Unique identifier
    requirements: str             # Original requirements
    current_stage: str            # Current active stage
    stages_completed: List[str]   # Successfully completed stages
    stage_results: Dict           # Results from each stage
    retry_counts: Dict            # Retry attempts per stage
    max_retries: int = 3          # Maximum retries per stage
    gitlab_issue: Optional[Dict]  # GitLab tracking issue
    status: str                   # Overall status
```

### Stage Result

```python
class StageResult:
    stage: str                    # Stage name
    success: bool                 # Success/failure
    output: Dict[str, Any]        # Stage output data
    error: Optional[str]          # Error message if failed
    retry_count: int              # Number of retries
    next_stage: Optional[str]     # AI-determined next stage
```

## Usage

### Basic Usage

```python
from routers.orchestrator_router import orchestrator_router

# Start adaptive orchestration
result = await orchestrator_router.orchestrate_contract_development_adaptive(
    requirements="Create a DeFi yield farming contract with staking rewards"
)

print(f"Workflow ID: {result['workflow_id']}")
print(f"Status: {result['status']}")
print(f"Stages Completed: {result['stages_completed']}")
print(f"Feedback Loops: {len(result['feedback_loops'])}")
```

### Monitoring Workflow

```python
# Get workflow status
status = orchestrator_router.get_workflow_status(workflow_id="workflow_123")

print(f"Current Stage: {status['current_stage']}")
print(f"Retry Counts: {status['retry_counts']}")
```

### Manual Retry

```python
# Manually retry a failed stage
result = orchestrator_router.retry_failed_stage(
    workflow_id="workflow_123",
    stage="testing"
)
```

### List Active Workflows

```python
# List all active workflows
workflows = orchestrator_router.list_active_workflows()

for wf in workflows['workflows']:
    print(f"{wf['workflow_id']}: {wf['status']} at {wf['current_stage']}")
```

## Decision Logic

The AI decision maker (`decide_next_stage`) analyzes each stage result using these rules:

### 1. **Ideation Stage**
- ✅ Success → Proceed to **Coding**
- ❌ Failure → Retry **Ideation** (up to max_retries)

### 2. **Coding Stage**
- ✅ Success → Proceed to **Testing**
- ❌ Failure (unclear spec) → Go back to **Ideation**
- ❌ Failure (code error) → Retry **Coding**

### 3. **Testing Stage**
- ✅ Success (all tests pass) → Proceed to **Auditing**
- ❌ Failure (test failures) → Go back to **Coding** with test feedback
- ❌ Failure (test setup error) → Retry **Testing**

### 4. **Auditing Stage**
- ✅ Success (low/medium risk) → Proceed to **Deployment**
- ❌ Failure (high/critical risk) → Go back to **Coding** with security feedback
- ❌ Failure (audit error) → Retry **Auditing**

### 5. **Deployment Stage**
- ✅ Success → Proceed to **Monitoring**
- ❌ Failure (compilation error) → Go back to **Coding**
- ❌ Failure (network error) → Retry **Deployment**

### 6. **Monitoring Stage**
- ✅ Success → **Completed**
- ❌ Failure → Retry **Monitoring**

## Example Scenarios

### Scenario 1: Test Failure Loop

```
1. Ideation → Success (spec generated)
2. Coding → Success (code generated)
3. Testing → Failure (3 tests failed)
   ↓ AI Decision: Go back to Coding with test feedback
4. Coding → Success (code fixed based on test failures)
5. Testing → Success (all tests pass)
6. Auditing → Success
7. Deployment → Success
8. Monitoring → Success
Status: Completed with 1 feedback loop
```

### Scenario 2: Security Issue Loop

```
1. Ideation → Success
2. Coding → Success
3. Testing → Success
4. Auditing → Failure (reentrancy vulnerability found)
   ↓ AI Decision: Go back to Coding with security feedback
5. Coding → Success (vulnerability fixed)
6. Testing → Success (tests still pass)
7. Auditing → Success (no critical issues)
8. Deployment → Success
9. Monitoring → Success
Status: Completed with 1 feedback loop
```

### Scenario 3: Multiple Retries

```
1. Ideation → Success
2. Coding → Failure (unclear spec)
   ↓ AI Decision: Go back to Ideation
3. Ideation → Success (refined spec)
4. Coding → Success
5. Testing → Failure (test setup error)
   ↓ AI Decision: Retry Testing
6. Testing → Failure (still failing)
   ↓ AI Decision: Go back to Coding
7. Coding → Success (fixed test compatibility)
8. Testing → Success
9. Auditing → Success
10. Deployment → Success
11. Monitoring → Success
Status: Completed with 3 feedback loops
```

## GitLab Integration

Each feedback loop is tracked in GitLab:

```
Issue: Smart contract workflow: workflow_1234567890

Comments:
✓ Ideation complete: DeFiYieldFarm
✓ Coding complete: 1250 characters
✗ Testing: FAILED
🔄 Feedback loop: testing → coding
   Reason: Tests failed, need to fix code based on test failures
✓ Coding complete: 1300 characters (updated)
✓ Testing: PASSED
✓ Audit complete: Risk level medium
✓ Deployed to sepolia at 0x1234...
✓ Monitoring started for 0x1234...
```

## Configuration

### Environment Variables

```bash
# Maximum retries per stage (default: 3)
WORKFLOW_MAX_RETRIES=3

# Maximum iterations to prevent infinite loops (default: 20)
WORKFLOW_MAX_ITERATIONS=20

# Enable GitLab tracking
GITLAB_TOKEN=your_gitlab_token
```

### Customization

You can customize the decision logic by modifying the `decide_next_stage` reasoner:

```python
@orchestrator_router.reasoner(tags=["ai", "decision"])
async def decide_next_stage(
    current_stage: str,
    stage_result: Dict[str, Any],
    workflow_state: Dict[str, Any]
) -> dict:
    # Custom decision logic here
    analysis = await orchestrator_router.ai(
        system="Your custom decision rules...",
        user=f"Analyze: {stage_result}"
    )
    return analysis
```

## Benefits

### 1. **Resilience**
- Automatic recovery from failures
- No manual intervention needed
- Intelligent error routing

### 2. **Quality**
- Iterative refinement
- Multiple validation passes
- Security-first approach

### 3. **Efficiency**
- Only retry what's needed
- Context preservation
- Parallel-ready architecture

### 4. **Observability**
- Complete audit trail
- GitLab integration
- Feedback loop tracking

## Comparison with Linear Orchestration

| Feature | Linear | Adaptive |
|---------|--------|----------|
| Error Recovery | ❌ Manual | ✅ Automatic |
| Feedback Loops | ❌ No | ✅ Yes |
| AI Decision Making | ❌ No | ✅ Yes |
| Retry Logic | ❌ Basic | ✅ Intelligent |
| State Management | ⚠️ Limited | ✅ Complete |
| Context Preservation | ❌ No | ✅ Yes |
| GitLab Tracking | ✅ Yes | ✅ Enhanced |
| Max Iterations | ❌ None | ✅ Configurable |

## Future Enhancements

### Planned Features

1. **Parallel Execution**
   - Run independent stages in parallel
   - Testing and auditing simultaneously
   - Faster overall workflow

2. **Learning from History**
   - Analyze past workflows
   - Predict likely failures
   - Optimize decision making

3. **Custom Stage Plugins**
   - Add custom stages
   - Define custom transitions
   - Extensible architecture

4. **Real-time Monitoring**
   - WebSocket updates
   - Live progress tracking
   - Interactive intervention

5. **Multi-Contract Workflows**
   - Orchestrate multiple contracts
   - Dependency management
   - Batch operations

## API Reference

### Reasoners

#### `orchestrate_contract_development_adaptive(requirements: str) -> dict`
Main adaptive orchestration function with feedback loops.

**Parameters:**
- `requirements` (str): Contract requirements

**Returns:**
- `workflow_id` (str): Unique workflow identifier
- `stages_completed` (list): Successfully completed stages
- `current_stage` (str): Current stage
- `status` (str): Overall status
- `outputs` (dict): Stage outputs
- `gitlab_issue` (dict): GitLab issue reference
- `feedback_loops` (list): Feedback loops executed

#### `decide_next_stage(current_stage, stage_result, workflow_state) -> dict`
AI-powered decision maker for next action.

**Returns:**
- `next_stage` (str): Next stage to execute
- `reason` (str): Explanation
- `feedback_needed` (bool): Whether going back
- `suggestions` (list): Improvement suggestions

### Skills

#### `get_workflow_status(workflow_id: str, issue_iid: int = None) -> dict`
Get workflow status from memory or GitLab.

#### `retry_failed_stage(workflow_id: str, stage: str) -> dict`
Manually retry a failed stage.

#### `list_active_workflows() -> dict`
List all active workflows in memory.

## Troubleshooting

### Infinite Loops
If workflow exceeds max_iterations (default: 20):
- Check decision logic
- Review stage error messages
- Increase max_retries if needed

### Memory Issues
Workflows are stored in memory:
- Clear old workflows periodically
- Use GitLab for long-term tracking
- Consider Redis for production

### GitLab Sync
If GitLab tracking fails:
- Check GITLAB_TOKEN
- Verify network connectivity
- Workflow continues without GitLab

---

**Last Updated:** 2026-05-16  
**Version:** 2.0.0  
**Status:** Production Ready