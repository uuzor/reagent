# Interactive Orchestration Design - WebSocket Bidirectional Communication

## Problem Statement

Current orchestration is **fire-and-forget**: user sends requirements, agent runs autonomously for minutes/hours without interaction. This creates issues:

1. **No clarification** - Agent can't ask "Do you want ERC-20 or ERC-721?"
2. **No mid-workflow input** - User can't provide feedback during execution
3. **Poor UX** - User waits blindly without knowing what's happening
4. **Wasted compute** - Agent might go down wrong path without user guidance

## Solution: WebSocket Bidirectional Communication

### Architecture Overview

```
┌─────────────┐                    ┌──────────────────┐
│   Client    │◄──────WebSocket────►│  Orchestrator    │
│  (Browser)  │                     │   (FastAPI)      │
└─────────────┘                     └──────────────────┘
      │                                      │
      │ 1. Connect + Send Requirements       │
      ├─────────────────────────────────────►│
      │                                      │
      │ 2. Receive: "Starting ideation..."   │
      │◄─────────────────────────────────────┤
      │                                      │
      │ 3. Receive: "QUESTION: Token type?"  │
      │◄─────────────────────────────────────┤
      │                                      │
      │ 4. Send: "ERC-20 with burn feature"  │
      ├─────────────────────────────────────►│
      │                                      │
      │ 5. Receive: "Generating code..."     │
      │◄─────────────────────────────────────┤
      │                                      │
      │ 6. Receive: "QUESTION: Test network?"│
      │◄─────────────────────────────────────┤
      │                                      │
      │ 7. Send: "Sepolia testnet"           │
      ├─────────────────────────────────────►│
      │                                      │
      │ 8. Receive: "Workflow complete!"     │
      │◄─────────────────────────────────────┤
```

### Message Protocol

#### Client → Server Messages

```json
{
  "type": "start_workflow",
  "workflow_id": "optional-resume-id",
  "requirements": "Build an ERC-20 token",
  "mode": "orchestrate"
}

{
  "type": "answer",
  "workflow_id": "workflow_123",
  "question_id": "q_456",
  "answer": "ERC-20 with burn and pause features"
}

{
  "type": "inject_context",
  "workflow_id": "workflow_123",
  "stage": "coding",
  "suggestion": "Add emergency stop function"
}

{
  "type": "abort",
  "workflow_id": "workflow_123",
  "reason": "User cancelled"
}
```

#### Server → Client Messages

```json
{
  "type": "workflow_started",
  "workflow_id": "workflow_123",
  "timestamp": "2026-05-17T07:30:00Z"
}

{
  "type": "stage_started",
  "workflow_id": "workflow_123",
  "stage": "ideation",
  "message": "Analyzing requirements..."
}

{
  "type": "stage_progress",
  "workflow_id": "workflow_123",
  "stage": "coding",
  "progress": 45,
  "message": "Generating test suite..."
}

{
  "type": "question",
  "workflow_id": "workflow_123",
  "question_id": "q_456",
  "stage": "ideation",
  "question": "What type of token do you want?",
  "options": ["ERC-20", "ERC-721", "ERC-1155"],
  "timeout": 300,
  "default": "ERC-20"
}

{
  "type": "stage_complete",
  "workflow_id": "workflow_123",
  "stage": "testing",
  "success": true,
  "output": {"tests_passed": 15, "coverage": 95}
}

{
  "type": "feedback_loop",
  "workflow_id": "workflow_123",
  "from_stage": "testing",
  "to_stage": "coding",
  "reason": "3 tests failed, fixing code..."
}

{
  "type": "workflow_complete",
  "workflow_id": "workflow_123",
  "status": "completed",
  "outputs": {...}
}

{
  "type": "error",
  "workflow_id": "workflow_123",
  "stage": "deployment",
  "error": "Insufficient gas",
  "recoverable": true
}
```

---

## Implementation Plan

### Phase 1: Core Infrastructure

#### 1.1 Question System

```python
# reagent/questions.py

from pydantic import BaseModel, Field
from typing import List, Optional, Any
from enum import Enum
import asyncio
from datetime import datetime, timedelta

class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TEXT = "text"
    YES_NO = "yes_no"
    NUMBER = "number"

class Question(BaseModel):
    question_id: str
    workflow_id: str
    stage: str
    question: str
    question_type: QuestionType
    options: Optional[List[str]] = None
    default: Optional[Any] = None
    timeout: int = 300  # 5 minutes
    required: bool = True
    context: Optional[str] = None

class Answer(BaseModel):
    question_id: str
    workflow_id: str
    answer: Any
    timestamp: datetime

class QuestionManager:
    """Manages questions and answers for interactive workflows."""
    
    def __init__(self):
        self._pending_questions: Dict[str, Question] = {}
        self._answers: Dict[str, Answer] = {}
        self._answer_events: Dict[str, asyncio.Event] = {}
    
    async def ask_question(
        self,
        workflow_id: str,
        stage: str,
        question: str,
        question_type: QuestionType = QuestionType.TEXT,
        options: Optional[List[str]] = None,
        default: Any = None,
        timeout: int = 300,
        required: bool = True
    ) -> Any:
        """
        Ask a question and wait for answer.
        Returns answer or default if timeout.
        """
        question_id = f"q_{workflow_id}_{stage}_{int(time.time())}"
        
        q = Question(
            question_id=question_id,
            workflow_id=workflow_id,
            stage=stage,
            question=question,
            question_type=question_type,
            options=options,
            default=default,
            timeout=timeout,
            required=required
        )
        
        self._pending_questions[question_id] = q
        self._answer_events[question_id] = asyncio.Event()
        
        # Emit question event (will be sent via WebSocket)
        await get_event_bus().emit(WorkflowEvent(
            event_type=EventType.QUESTION_ASKED,
            workflow_id=workflow_id,
            stage=stage,
            data=q.model_dump(),
            message=question
        ))
        
        # Wait for answer with timeout
        try:
            await asyncio.wait_for(
                self._answer_events[question_id].wait(),
                timeout=timeout
            )
            
            answer = self._answers.get(question_id)
            if answer:
                return answer.answer
            elif default is not None:
                return default
            elif required:
                raise TimeoutError(f"No answer received for required question: {question}")
            else:
                return None
                
        except asyncio.TimeoutError:
            if default is not None:
                return default
            elif required:
                raise TimeoutError(f"Question timeout: {question}")
            else:
                return None
        finally:
            # Cleanup
            self._pending_questions.pop(question_id, None)
            self._answer_events.pop(question_id, None)
    
    def answer_question(self, question_id: str, answer: Any) -> bool:
        """Submit answer to a pending question."""
        if question_id not in self._pending_questions:
            return False
        
        question = self._pending_questions[question_id]
        
        self._answers[question_id] = Answer(
            question_id=question_id,
            workflow_id=question.workflow_id,
            answer=answer,
            timestamp=datetime.utcnow()
        )
        
        # Signal that answer is ready
        if question_id in self._answer_events:
            self._answer_events[question_id].set()
        
        return True
    
    def get_pending_questions(self, workflow_id: str) -> List[Question]:
        """Get all pending questions for a workflow."""
        return [
            q for q in self._pending_questions.values()
            if q.workflow_id == workflow_id
        ]

# Singleton
_question_manager: Optional[QuestionManager] = None

def get_question_manager() -> QuestionManager:
    global _question_manager
    if _question_manager is None:
        _question_manager = QuestionManager()
    return _question_manager
```

#### 1.2 WebSocket Handler

```python
# reagent/websocket_handler.py

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import asyncio
from datetime import datetime

class ConnectionManager:
    """Manages WebSocket connections for workflows."""
    
    def __init__(self):
        # workflow_id -> set of WebSocket connections
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._workflow_to_ws: Dict[WebSocket, str] = {}
    
    async def connect(self, websocket: WebSocket, workflow_id: str):
        """Accept WebSocket connection and associate with workflow."""
        await websocket.accept()
        
        if workflow_id not in self._connections:
            self._connections[workflow_id] = set()
        
        self._connections[workflow_id].add(websocket)
        self._workflow_to_ws[websocket] = workflow_id
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        workflow_id = self._workflow_to_ws.pop(websocket, None)
        if workflow_id and workflow_id in self._connections:
            self._connections[workflow_id].discard(websocket)
            if not self._connections[workflow_id]:
                del self._connections[workflow_id]
    
    async def send_to_workflow(self, workflow_id: str, message: dict):
        """Send message to all connections for a workflow."""
        if workflow_id not in self._connections:
            return
        
        message_json = json.dumps(message)
        dead_connections = set()
        
        for websocket in self._connections[workflow_id]:
            try:
                await websocket.send_text(message_json)
            except Exception:
                dead_connections.add(websocket)
        
        # Clean up dead connections
        for ws in dead_connections:
            self.disconnect(ws)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connections."""
        message_json = json.dumps(message)
        
        for connections in self._connections.values():
            for websocket in connections:
                try:
                    await websocket.send_text(message_json)
                except Exception:
                    pass

# Singleton
_connection_manager: Optional[ConnectionManager] = None

def get_connection_manager() -> ConnectionManager:
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager
```

#### 1.3 WebSocket Router

```python
# reagent/routers/websocket_router.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Optional
import json
import asyncio

from websocket_handler import get_connection_manager
from questions import get_question_manager
from events import get_event_bus, EventType

websocket_router = APIRouter()

@websocket_router.websocket("/ws/{workflow_id}")
async def websocket_endpoint(websocket: WebSocket, workflow_id: str):
    """
    WebSocket endpoint for interactive workflow communication.
    
    Client sends:
    - start_workflow: Begin new workflow
    - answer: Answer to question
    - inject_context: Mid-workflow suggestion
    - abort: Cancel workflow
    
    Server sends:
    - workflow_started, stage_started, stage_progress, stage_complete
    - question: Ask user for input
    - feedback_loop: Notify about stage retry
    - workflow_complete, error
    """
    cm = get_connection_manager()
    qm = get_question_manager()
    
    await cm.connect(websocket, workflow_id)
    
    # Subscribe to events for this workflow
    event_queue = get_event_bus().subscribe(workflow_id)
    
    # Task to forward events to WebSocket
    async def forward_events():
        try:
            while True:
                event = await event_queue.get()
                await websocket.send_json({
                    "type": event.event_type,
                    "workflow_id": event.workflow_id,
                    "stage": event.stage,
                    "timestamp": event.timestamp.isoformat(),
                    "message": event.message,
                    "data": event.data
                })
        except Exception:
            pass
    
    event_task = asyncio.create_task(forward_events())
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            msg_type = message.get("type")
            
            if msg_type == "start_workflow":
                # Start workflow in background
                requirements = message.get("requirements")
                mode = message.get("mode", "orchestrate")
                
                # This will be handled by orchestrator
                await websocket.send_json({
                    "type": "workflow_started",
                    "workflow_id": workflow_id,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                # Trigger orchestration (non-blocking)
                asyncio.create_task(
                    start_interactive_workflow(workflow_id, requirements, mode)
                )
            
            elif msg_type == "answer":
                # Answer to question
                question_id = message.get("question_id")
                answer = message.get("answer")
                
                success = qm.answer_question(question_id, answer)
                
                await websocket.send_json({
                    "type": "answer_received",
                    "question_id": question_id,
                    "success": success
                })
            
            elif msg_type == "inject_context":
                # User provides mid-workflow suggestion
                stage = message.get("stage")
                suggestion = message.get("suggestion")
                
                # Emit context injection event
                await get_event_bus().emit(WorkflowEvent(
                    event_type=EventType.CONTEXT_INJECTED,
                    workflow_id=workflow_id,
                    stage=stage,
                    data={"suggestion": suggestion},
                    message=f"User suggestion: {suggestion}"
                ))
                
                await websocket.send_json({
                    "type": "context_injected",
                    "workflow_id": workflow_id,
                    "stage": stage
                })
            
            elif msg_type == "abort":
                # User cancels workflow
                reason = message.get("reason", "User cancelled")
                
                await get_event_bus().emit(WorkflowEvent(
                    event_type=EventType.WORKFLOW_FAILED,
                    workflow_id=workflow_id,
                    data={"reason": reason},
                    message=f"Workflow aborted: {reason}"
                ))
                
                await websocket.send_json({
                    "type": "workflow_aborted",
                    "workflow_id": workflow_id
                })
                break
    
    except WebSocketDisconnect:
        pass
    finally:
        event_task.cancel()
        cm.disconnect(websocket)
        get_event_bus().unsubscribe(event_queue)


async def start_interactive_workflow(
    workflow_id: str,
    requirements: str,
    mode: str
):
    """Start interactive workflow (called from WebSocket)."""
    from routers.orchestrator_router import orchestrate_contract_development_interactive
    
    try:
        result = await orchestrate_contract_development_interactive(
            workflow_id=workflow_id,
            requirements=requirements,
            mode=mode
        )
    except Exception as e:
        await get_event_bus().emit(WorkflowEvent(
            event_type=EventType.WORKFLOW_FAILED,
            workflow_id=workflow_id,
            data={"error": str(e)},
            message=f"Workflow failed: {str(e)}"
        ))
```

### Phase 2: Interactive Orchestrator

Modify `orchestrator_router.py` to support questions:

```python
# Add to reagent/routers/orchestrator_router.py

from questions import get_question_manager, QuestionType
from events import get_event_bus, EventType, WorkflowEvent

@orchestrator_router.reasoner(tags=["ai", "coordination", "interactive"])
async def orchestrate_contract_development_interactive(
    workflow_id: str,
    requirements: str,
    mode: str = "orchestrate"
) -> dict:
    """
    Interactive orchestration with user questions and real-time feedback.
    """
    qm = get_question_manager()
    fm = _get_fm()

    # Initialize workflow state
    state = WorkflowState(
        workflow_id=workflow_id,
        requirements=requirements,
        current_stage=WorkflowStage.IDEATION.value
    )
    _workflow_states[workflow_id] = state

    # Emit workflow started event
    await get_event_bus().emit(WorkflowEvent(
        event_type=EventType.WORKFLOW_START,
        workflow_id=workflow_id,
        message="Workflow started"
    ))

    # Create tracking issue in GitLab
    if fm:
        issue = fm.gl.create_issue(
            title=f"Interactive workflow: {workflow_id}",
            description=f"Requirements:\n{requirements}",
            labels=["reagent", "interactive"],
        )
        state.gitlab_issue = issue

    feedback_loops = []
    max_iterations = 20
    iteration = 0

    while state.current_stage != WorkflowStage.COMPLETED.value and iteration < max_iterations:
        iteration += 1
        stage = state.current_stage
        
        # Emit stage started
        await get_event_bus().emit(WorkflowEvent(
            event_type=EventType.STAGE_START,
            workflow_id=workflow_id,
            stage=stage,
            message=f"Starting {stage} stage"
        ))

        try:
            # Execute current stage (with questions)
            if stage == WorkflowStage.IDEATION.value:
                result = await _execute_ideation_interactive(state, fm, qm)
            elif stage == WorkflowStage.CODING.value:
                result = await _execute_coding_interactive(state, fm, qm)
            # ... other stages
            
            # Emit stage complete
            await get_event_bus().emit(WorkflowEvent(
                event_type=EventType.STAGE_COMPLETE,
                workflow_id=workflow_id,
                stage=stage,
                data=result.model_dump(),
                message=f"Completed {stage} stage"
            ))
            
            # Store result and continue...
            # (rest of orchestration logic)
            
        except Exception as e:
            await get_event_bus().emit(WorkflowEvent(
                event_type=EventType.STAGE_ERROR,
                workflow_id=workflow_id,
                stage=stage,
                data={"error": str(e)},
                message=f"Error in {stage}: {str(e)}"
            ))
            break

    # Emit workflow complete
    await get_event_bus().emit(WorkflowEvent(
        event_type=EventType.WORKFLOW_COMPLETE,
        workflow_id=workflow_id,
        data={"status": state.status},
        message="Workflow completed"
    ))

    return result.model_dump()


async def _execute_ideation_interactive(
    state: WorkflowState,
    fm: Optional[FileManager],
    qm: QuestionManager
) -> StageResult:
    """Execute ideation with user questions."""
    
    # Ask user about token type
    token_type = await qm.ask_question(
        workflow_id=state.workflow_id,
        stage="ideation",
        question="What type of token do you want to create?",
        question_type=QuestionType.MULTIPLE_CHOICE,
        options=["ERC-20", "ERC-721", "ERC-1155", "Custom"],
        default="ERC-20",
        timeout=300
    )
    
    # Ask about features
    features = await qm.ask_question(
        workflow_id=state.workflow_id,
        stage="ideation",
        question="What features should the token have? (comma-separated)",
        question_type=QuestionType.TEXT,
        default="mintable,burnable",
        timeout=300
    )
    
    # Generate spec with user input
    enhanced_requirements = f"{state.requirements}\nToken Type: {token_type}\nFeatures: {features}"
    
    spec = await orchestrator_router.app.call(
        f"{orchestrator_router.app.node_id}.ideation_generate_contract_spec",
        requirements=enhanced_requirements,
    )
    
    return StageResult(
        stage=WorkflowStage.IDEATION.value,
        success=True,
        output=spec,
        next_stage=WorkflowStage.CODING.value
    )
```

---

## Usage Examples

### Client-Side (JavaScript)

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8001/ws/workflow_123');

ws.onopen = () => {
  // Start workflow
  ws.send(JSON.stringify({
    type: 'start_workflow',
    workflow_id: 'workflow_123',
    requirements: 'Build an ERC-20 token for DeFi',
    mode: 'orchestrate'
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  switch (message.type) {
    case 'question':
      // Display question to user
      const answer = prompt(message.question);
      
      // Send answer
      ws.send(JSON.stringify({
        type: 'answer',
        workflow_id: message.workflow_id,
        question_id: message.question_id,
        answer: answer
      }));
      break;
    
    case 'stage_started':
      console.log(`Stage started: ${message.stage}`);
      break;
    
    case 'stage_progress':
      console.log(`Progress: ${message.progress}%`);
      break;
    
    case 'workflow_complete':
      console.log('Workflow completed!', message.data);
      ws.close();
      break;
  }
};
```

### Client-Side (Python)

```python
import asyncio
import websockets
import json

async def interactive_workflow():
    uri = "ws://localhost:8001/ws/workflow_123"
    
    async with websockets.connect(uri) as websocket:
        # Start workflow
        await websocket.send(json.dumps({
            "type": "start_workflow",
            "workflow_id": "workflow_123",
            "requirements": "Build an ERC-20 token",
            "mode": "orchestrate"
        }))
        
        # Listen for messages
        async for message in websocket:
            data = json.loads(message)
            
            if data["type"] == "question":
                # Ask user
                print(f"\nQuestion: {data['question']}")
                if data.get("options"):
                    for i, opt in enumerate(data["options"], 1):
                        print(f"{i}. {opt}")
                
                answer = input("Your answer: ")
                
                # Send answer
                await websocket.send(json.dumps({
                    "type": "answer",
                    "workflow_id": data["workflow_id"],
                    "question_id": data["question_id"],
                    "answer": answer
                }))
            
            elif data["type"] == "stage_started":
                print(f"\n🚀 {data['message']}")
            
            elif data["type"] == "workflow_complete":
                print(f"\n✅ Workflow completed!")
                break

asyncio.run(interactive_workflow())
```

---

## Benefits

1. **Better UX** - User sees real-time progress and can provide input
2. **Smarter Agent** - Can ask clarifying questions instead of guessing
3. **Faster Iteration** - User can guide agent mid-workflow
4. **Error Recovery** - User can provide fixes when agent is stuck
5. **Transparency** - User knows exactly what's happening

---

## Next Steps

1. Implement `questions.py` - Question management system
2. Implement `websocket_handler.py` - Connection management
3. Add WebSocket router to `main.py`
4. Modify orchestrator to use questions
5. Create frontend demo with WebSocket client
6. Add tests for interactive workflows

---

## Compatibility

- **Backward Compatible**: Old HTTP POST still works (no questions asked)
- **Progressive Enhancement**: WebSocket adds interactivity, HTTP is fallback
- **Graceful Degradation**: If no answer received, uses defaults
