# Compute Strategy & Architecture Analysis

## 🎯 Strategic Requirements

### 1. **Compute Tier Strategy**
- **Free/Regular Users** → GitHub Codespaces (no cost to you)
- **Premium Users** → Nosana (for AI models, heavy compute)
- **Fallback** → Nosana when GitHub fails or is unavailable

### 2. **Event Logging & Streaming**
- Real-time event streaming for frontend
- Progress updates during workflow execution
- Stage-by-stage logging with timestamps

### 3. **Context Injection**
- User suggestions during workflow
- Mid-execution guidance
- Interactive refinement

### 4. **Mode Switching**
- **Plan Mode** - Generate execution plan
- **Orchestrate Mode** - Execute workflow
- **Code Mode** - Direct code generation

---

## 🏗️ Proposed Architecture

### Compute Tier System

```
┌─────────────────────────────────────────────────────────┐
│                    User Request                          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │   Compute Selector    │
         │  (AI-powered choice)  │
         └───────────┬───────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│  GitHub  │  │  Nosana  │  │  Local   │
│Codespace │  │  Compute │  │  Exec    │
└──────────┘  └──────────┘  └──────────┘
  Free Tier    Premium/AI    Fallback
```

### Decision Logic

```python
def select_compute_backend(task_type, user_tier, task_requirements):
    """
    AI-powered compute backend selection
    """
    if task_type in ["ai_model", "gpu_required", "heavy_compute"]:
        if user_tier == "premium":
            return "nosana"
        else:
            return "github_codespace"  # Try first, fallback to local
    
    elif task_type in ["compile", "test", "deploy"]:
        if user_tier == "free":
            return "github_codespace"
        else:
            return "nosana"  # Premium gets faster Nosana
    
    else:
        return "github_codespace"  # Default to free tier
```

---

## 📡 Event Logging & Streaming Architecture

### WebSocket-Based Event Streaming

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend                            │
│              (React/Vue/Next.js)                         │
└────────────────────┬────────────────────────────────────┘
                     │ WebSocket Connection
                     │ ws://api.reagent.ai/stream/{workflow_id}
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  Event Stream Server                     │
│              (FastAPI WebSocket)                         │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  Event Bus (Redis)                       │
│         Pub/Sub for real-time events                     │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│Ideation  │  │  Coding  │  │ Testing  │
│  Agent   │  │  Agent   │  │  Agent   │
└──────────┘  └──────────┘  └──────────┘
```

### Event Types

```python
class EventType(str, Enum):
    # Workflow events
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    
    # Stage events
    STAGE_STARTED = "stage.started"
    STAGE_PROGRESS = "stage.progress"
    STAGE_COMPLETED = "stage.completed"
    STAGE_FAILED = "stage.failed"
    
    # Feedback loop events
    FEEDBACK_LOOP = "feedback.loop"
    DECISION_MADE = "decision.made"
    
    # Compute events
    COMPUTE_SELECTED = "compute.selected"
    COMPUTE_STARTED = "compute.started"
    COMPUTE_COMPLETED = "compute.completed"
    
    # User interaction events
    USER_SUGGESTION = "user.suggestion"
    CONTEXT_INJECTED = "context.injected"
    
    # Log events
    LOG_INFO = "log.info"
    LOG_WARNING = "log.warning"
    LOG_ERROR = "log.error"

class WorkflowEvent(BaseModel):
    event_id: str
    workflow_id: str
    event_type: EventType
    timestamp: datetime
    stage: Optional[str]
    data: Dict[str, Any]
    message: str
```

### Event Streaming Implementation

```python
# In orchestrator_router.py
from fastapi import WebSocket
import asyncio
import json

class EventStreamer:
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}
        self.redis_client = redis.Redis()
    
    async def connect(self, workflow_id: str, websocket: WebSocket):
        """Connect frontend to workflow event stream"""
        await websocket.accept()
        if workflow_id not in self.connections:
            self.connections[workflow_id] = []
        self.connections[workflow_id].append(websocket)
    
    async def emit(self, workflow_id: str, event: WorkflowEvent):
        """Emit event to all connected clients"""
        # Publish to Redis for persistence
        self.redis_client.publish(
            f"workflow:{workflow_id}",
            event.model_dump_json()
        )
        
        # Send to WebSocket clients
        if workflow_id in self.connections:
            for ws in self.connections[workflow_id]:
                try:
                    await ws.send_json(event.model_dump())
                except:
                    self.connections[workflow_id].remove(ws)
    
    async def emit_stage_progress(
        self, 
        workflow_id: str, 
        stage: str, 
        progress: int,
        message: str
    ):
        """Emit stage progress update"""
        event = WorkflowEvent(
            event_id=f"{workflow_id}_{int(time.time())}",
            workflow_id=workflow_id,
            event_type=EventType.STAGE_PROGRESS,
            timestamp=datetime.now(),
            stage=stage,
            data={"progress": progress},
            message=message
        )
        await self.emit(workflow_id, event)

# Global event streamer
event_streamer = EventStreamer()

# Usage in orchestrator
async def _execute_ideation(state: WorkflowState, fm: Optional[FileManager]) -> StageResult:
    # Emit stage started
    await event_streamer.emit_stage_progress(
        state.workflow_id,
        "ideation",
        0,
        "Starting ideation stage..."
    )
    
    # Execute stage
    spec = await orchestrator_router.app.call(...)
    
    # Emit progress updates
    await event_streamer.emit_stage_progress(
        state.workflow_id,
        "ideation",
        50,
        "Analyzing market trends..."
    )
    
    # More work...
    
    await event_streamer.emit_stage_progress(
        state.workflow_id,
        "ideation",
        100,
        "Ideation complete!"
    )
    
    return result
```

---

## 🎨 Context Injection System

### Interactive Workflow with User Suggestions

```python
class UserSuggestion(BaseModel):
    workflow_id: str
    stage: str
    suggestion: str
    timestamp: datetime
    priority: str = "normal"  # normal, high, critical

class ContextInjector:
    def __init__(self):
        self.suggestions: Dict[str, List[UserSuggestion]] = {}
    
    def add_suggestion(self, suggestion: UserSuggestion):
        """Add user suggestion to workflow context"""
        if suggestion.workflow_id not in self.suggestions:
            self.suggestions[suggestion.workflow_id] = []
        self.suggestions[suggestion.workflow_id].append(suggestion)
        
        # Emit event
        event_streamer.emit(
            suggestion.workflow_id,
            WorkflowEvent(
                event_type=EventType.USER_SUGGESTION,
                message=f"User suggestion: {suggestion.suggestion}",
                data=suggestion.model_dump()
            )
        )
    
    def get_context_for_stage(self, workflow_id: str, stage: str) -> str:
        """Get all relevant suggestions for a stage"""
        if workflow_id not in self.suggestions:
            return ""
        
        relevant = [
            s for s in self.suggestions[workflow_id]
            if s.stage == stage or s.priority == "critical"
        ]
        
        if not relevant:
            return ""
        
        context = "\n\n=== USER SUGGESTIONS ===\n"
        for s in relevant:
            context += f"- {s.suggestion}\n"
        context += "=== END SUGGESTIONS ===\n"
        
        return context

# Global context injector
context_injector = ContextInjector()

# API endpoint for user suggestions
@orchestrator_router.skill(tags=["interaction"])
def inject_user_suggestion(
    workflow_id: str,
    stage: str,
    suggestion: str,
    priority: str = "normal"
) -> dict:
    """
    Allow user to inject suggestions during workflow execution.
    """
    suggestion_obj = UserSuggestion(
        workflow_id=workflow_id,
        stage=stage,
        suggestion=suggestion,
        timestamp=datetime.now(),
        priority=priority
    )
    
    context_injector.add_suggestion(suggestion_obj)
    
    return {
        "success": True,
        "message": "Suggestion added to workflow context",
        "suggestion_id": f"{workflow_id}_{int(time.time())}"
    }

# Usage in stage execution
async def _execute_coding(state: WorkflowState, fm: Optional[FileManager]) -> StageResult:
    spec = state.stage_results[WorkflowStage.IDEATION.value].output
    
    # Get user suggestions for this stage
    user_context = context_injector.get_context_for_stage(
        state.workflow_id,
        WorkflowStage.CODING.value
    )
    
    # Inject into prompt
    if user_context:
        spec["user_suggestions"] = user_context
    
    code = await orchestrator_router.app.call(
        f"{orchestrator_router.app.node_id}.coding_generate_contract_code",
        spec=spec,
    )
    
    return result
```

---

## 🔀 Mode Switching System

### Three Operating Modes

```python
class OperatingMode(str, Enum):
    PLAN = "plan"           # Generate execution plan only
    ORCHESTRATE = "orchestrate"  # Execute full workflow
    CODE = "code"           # Direct code generation

class ModeConfig(BaseModel):
    mode: OperatingMode
    auto_execute: bool = False
    require_approval: bool = True
    stream_events: bool = True
    compute_backend: str = "auto"  # auto, github, nosana, local

# Mode-specific orchestrators

@orchestrator_router.reasoner(tags=["ai", "planning"])
async def plan_mode(requirements: str, config: ModeConfig) -> dict:
    """
    PLAN MODE: Generate execution plan without executing.
    Returns detailed plan with estimated costs, time, and stages.
    """
    # Use AI to analyze requirements
    analysis = await orchestrator_router.ai(
        system="""You are a smart contract development planner.
Analyze requirements and create a detailed execution plan.

Return JSON with:
- stages: list of stages with descriptions
- estimated_time: total time in minutes
- estimated_cost: cost breakdown
- risks: potential issues
- recommendations: suggestions for success
- compute_requirements: what compute is needed per stage""",
        user=f"Requirements: {requirements}\n\nCreate execution plan."
    )
    
    # Emit plan event
    await event_streamer.emit(
        workflow_id="plan_" + str(int(time.time())),
        event=WorkflowEvent(
            event_type=EventType.WORKFLOW_STARTED,
            message="Plan generated",
            data=analysis
        )
    )
    
    return {
        "mode": "plan",
        "plan": analysis,
        "ready_to_execute": True,
        "approval_required": config.require_approval
    }


@orchestrator_router.reasoner(tags=["ai", "orchestration"])
async def orchestrate_mode(
    requirements: str, 
    config: ModeConfig,
    plan: Optional[Dict] = None
) -> dict:
    """
    ORCHESTRATE MODE: Full workflow execution with feedback loops.
    """
    # If plan provided, use it; otherwise generate one
    if not plan:
        plan_result = await plan_mode(requirements, config)
        plan = plan_result["plan"]
    
    # Execute adaptive orchestration
    result = await orchestrate_contract_development_adaptive(
        requirements=requirements
    )
    
    return {
        "mode": "orchestrate",
        "plan": plan,
        "execution": result
    }


@orchestrator_router.reasoner(tags=["ai", "coding"])
async def code_mode(
    requirements: str,
    config: ModeConfig,
    context: Optional[str] = None
) -> dict:
    """
    CODE MODE: Direct code generation without full workflow.
    Fast path for experienced users.
    """
    # Generate spec quickly
    spec = await orchestrator_router.app.call(
        f"{orchestrator_router.app.node_id}.ideation_generate_contract_spec",
        requirements=requirements + (f"\n\nContext: {context}" if context else ""),
    )
    
    # Generate code immediately
    code = await orchestrator_router.app.call(
        f"{orchestrator_router.app.node_id}.coding_generate_contract_code",
        spec=spec,
    )
    
    return {
        "mode": "code",
        "spec": spec,
        "code": code,
        "note": "Code generated. Run tests separately if needed."
    }


# Mode switcher
@orchestrator_router.skill(tags=["mode"])
def switch_mode(
    current_mode: str,
    target_mode: str,
    workflow_id: Optional[str] = None
) -> dict:
    """
    Switch between operating modes.
    Can pause orchestrate mode and switch to plan/code mode.
    """
    valid_transitions = {
        "plan": ["orchestrate", "code"],
        "orchestrate": ["plan"],  # Can pause and replan
        "code": ["plan", "orchestrate"]
    }
    
    if target_mode not in valid_transitions.get(current_mode, []):
        return {
            "success": False,
            "error": f"Cannot switch from {current_mode} to {target_mode}"
        }
    
    # Emit mode switch event
    if workflow_id:
        event_streamer.emit(
            workflow_id,
            WorkflowEvent(
                event_type=EventType.LOG_INFO,
                message=f"Mode switched: {current_mode} → {target_mode}",
                data={"from": current_mode, "to": target_mode}
            )
        )
    
    return {
        "success": True,
        "previous_mode": current_mode,
        "current_mode": target_mode,
        "message": f"Switched to {target_mode} mode"
    }
```

---

## 🎮 Frontend Integration Example

### React Component for Event Streaming

```typescript
// WorkflowMonitor.tsx
import { useEffect, useState } from 'react';

interface WorkflowEvent {
  event_id: string;
  workflow_id: string;
  event_type: string;
  timestamp: string;
  stage?: string;
  data: any;
  message: string;
}

export function WorkflowMonitor({ workflowId }: { workflowId: string }) {
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [currentStage, setCurrentStage] = useState<string>('');
  const [progress, setProgress] = useState<number>(0);

  useEffect(() => {
    // Connect to WebSocket
    const ws = new WebSocket(`ws://api.reagent.ai/stream/${workflowId}`);
    
    ws.onmessage = (event) => {
      const data: WorkflowEvent = JSON.parse(event.data);
      
      setEvents(prev => [...prev, data]);
      
      if (data.event_type === 'stage.started') {
        setCurrentStage(data.stage || '');
        setProgress(0);
      } else if (data.event_type === 'stage.progress') {
        setProgress(data.data.progress);
      }
    };
    
    return () => ws.close();
  }, [workflowId]);

  return (
    <div className="workflow-monitor">
      <h2>Workflow: {workflowId}</h2>
      <div className="current-stage">
        <h3>Current Stage: {currentStage}</h3>
        <progress value={progress} max={100} />
      </div>
      <div className="event-log">
        {events.map(event => (
          <div key={event.event_id} className={`event ${event.event_type}`}>
            <span className="timestamp">{event.timestamp}</span>
            <span className="message">{event.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// User suggestion component
export function SuggestionInput({ workflowId, currentStage }: any) {
  const [suggestion, setSuggestion] = useState('');
  
  const submitSuggestion = async () => {
    await fetch('/api/inject_user_suggestion', {
      method: 'POST',
      body: JSON.stringify({
        workflow_id: workflowId,
        stage: currentStage,
        suggestion: suggestion,
        priority: 'normal'
      })
    });
    setSuggestion('');
  };
  
  return (
    <div className="suggestion-input">
      <textarea 
        value={suggestion}
        onChange={(e) => setSuggestion(e.target.value)}
        placeholder="Add a suggestion for the current stage..."
      />
      <button onClick={submitSuggestion}>Submit Suggestion</button>
    </div>
  );
}
```

---

## 📊 Implementation Priority

### Phase 1: Compute Strategy (Week 1)
1. ✅ Implement compute backend selector
2. ✅ Add GitHub Codespaces as default for free tier
3. ✅ Add Nosana as premium/fallback option
4. ✅ Add cost tracking per backend

### Phase 2: Event Streaming (Week 2)
1. ✅ Add WebSocket support to FastAPI
2. ✅ Implement EventStreamer class
3. ✅ Add event emission to all stages
4. ✅ Create frontend WebSocket client

### Phase 3: Context Injection (Week 2)
1. ✅ Implement ContextInjector class
2. ✅ Add API endpoint for user suggestions
3. ✅ Integrate context into stage execution
4. ✅ Add frontend suggestion UI

### Phase 4: Mode Switching (Week 3)
1. ✅ Implement plan_mode
2. ✅ Implement orchestrate_mode
3. ✅ Implement code_mode
4. ✅ Add mode switcher
5. ✅ Add frontend mode selector

---

## 🎯 Benefits of This Architecture

### 1. **Cost Optimization**
- Free users use GitHub Codespaces (no cost to you)
- Premium users get faster Nosana compute
- Automatic fallback prevents service disruption

### 2. **Real-time Feedback**
- Frontend sees every stage progress
- Users can intervene mid-workflow
- Complete transparency

### 3. **Flexibility**
- Three modes for different use cases
- User suggestions improve results
- Mode switching for power users

### 4. **Scalability**
- WebSocket scales with Redis pub/sub
- Multiple compute backends
- Event-driven architecture

---

## 📝 Next Steps

1. **Implement EventStreamer** - Add WebSocket support
2. **Add ContextInjector** - Enable user suggestions
3. **Create Mode System** - Implement three modes
4. **Update Frontend** - Add real-time monitoring
5. **Test End-to-End** - Verify all features work together

This architecture gives you:
- ✅ Cost-effective compute strategy
- ✅ Real-time event streaming
- ✅ Interactive context injection
- ✅ Flexible mode switching
- ✅ Production-ready scalability