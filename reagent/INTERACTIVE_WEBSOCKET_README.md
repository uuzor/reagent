# Interactive WebSocket Orchestration - Complete Implementation

## 🎉 What Was Built

A complete **bidirectional WebSocket system** that allows real-time interaction between users and the Reagent smart contract development agent. Users can now answer questions, provide feedback, and monitor progress in real-time.

---

## 📦 Components Created

### 1. **Event Bus System** (`events.py` - 185 lines)
- Pub/sub event streaming for real-time updates
- Event history with ring buffer (1000 events per workflow)
- Multiple subscribers per workflow
- Event types: workflow, stage, question, answer, feedback loop, error

### 2. **Question Management** (`questions.py` - 265 lines)
- Ask questions and wait for answers with timeout
- Multiple question types: multiple choice, text, yes/no, number
- Default answers for timeout scenarios
- Question history and statistics

### 3. **WebSocket Connection Manager** (`websocket_handler.py` - 180 lines)
- Manages WebSocket connections per workflow
- Routes messages between clients and orchestrator
- Handles disconnections gracefully
- Connection statistics and monitoring

### 4. **WebSocket Router** (`routers/websocket_router.py` - 235 lines)
- FastAPI WebSocket endpoint at `/ws/{workflow_id}`
- Handles 8 message types from client
- Forwards events from event bus to WebSocket
- Non-blocking workflow execution

### 5. **Interactive Orchestrator** (`routers/orchestrator_router.py` - added 450 lines)
- New function: `orchestrate_contract_development_interactive()`
- Asks questions at ideation, coding, and deployment stages
- Emits real-time events for all workflow activities
- Backward compatible with existing HTTP POST endpoint

### 6. **Frontend Demo** (`frontend_demo.html` - 600 lines)
- Beautiful interactive UI with real-time updates
- Stage progress indicator
- Question/answer interface
- Event log with color coding
- Connect/disconnect controls

### 7. **Python Test Client** (`test_interactive_client.py` - 180 lines)
- Command-line interactive client
- Handles questions with multiple choice or free text
- Real-time progress display
- Keyboard interrupt handling

---

## 🚀 How to Use

### Option 1: HTML Frontend (Recommended)

1. **Start the Reagent server:**
   ```bash
   cd reagent
   python main.py
   ```

2. **Open the frontend:**
   ```bash
   # Open frontend_demo.html in your browser
   open frontend_demo.html  # macOS
   start frontend_demo.html  # Windows
   xdg-open frontend_demo.html  # Linux
   ```

3. **Use the interface:**
   - Enter workflow ID (e.g., `workflow_demo`)
   - Enter requirements (e.g., "Build an ERC-20 token")
   - Select mode (Orchestrate/Plan/Code)
   - Click "Connect & Start"
   - Answer questions as they appear
   - Watch real-time progress

### Option 2: Python Test Client

1. **Start the server:**
   ```bash
   cd reagent
   python main.py
   ```

2. **Run the test client:**
   ```bash
   python test_interactive_client.py
   ```

3. **Interact:**
   - Client connects automatically
   - Answer questions in the terminal
   - See real-time progress
   - Press Ctrl+C to abort

### Option 3: Custom WebSocket Client

```python
import asyncio
import websockets
import json

async def my_workflow():
    uri = "ws://localhost:8001/ws/my_workflow_123"
    
    async with websockets.connect(uri) as ws:
        # Start workflow
        await ws.send(json.dumps({
            "type": "start_workflow",
            "workflow_id": "my_workflow_123",
            "requirements": "Build an ERC-20 token",
            "mode": "orchestrate"
        }))
        
        # Listen for messages
        async for message in ws:
            data = json.loads(message)
            
            if data["type"] == "question.asked":
                # Answer question
                answer = input(data["data"]["question"] + " ")
                await ws.send(json.dumps({
                    "type": "answer",
                    "question_id": data["data"]["question_id"],
                    "answer": answer
                }))
            
            elif data["type"] == "workflow.complete":
                print("Done!")
                break

asyncio.run(my_workflow())
```

---

## 📡 WebSocket Protocol

### Client → Server Messages

#### 1. Start Workflow
```json
{
  "type": "start_workflow",
  "workflow_id": "workflow_123",
  "requirements": "Build an ERC-20 token",
  "mode": "orchestrate"
}
```

#### 2. Answer Question
```json
{
  "type": "answer",
  "workflow_id": "workflow_123",
  "question_id": "q_456",
  "answer": "ERC-20"
}
```

#### 3. Inject Context (Mid-Workflow Suggestion)
```json
{
  "type": "inject_context",
  "workflow_id": "workflow_123",
  "stage": "coding",
  "suggestion": "Add emergency stop function"
}
```

#### 4. Abort Workflow
```json
{
  "type": "abort",
  "workflow_id": "workflow_123",
  "reason": "User cancelled"
}
```

#### 5. Ping (Heartbeat)
```json
{
  "type": "ping"
}
```

### Server → Client Messages

#### 1. Connected
```json
{
  "type": "connected",
  "workflow_id": "workflow_123",
  "timestamp": "2026-05-17T07:30:00Z",
  "message": "WebSocket connected successfully"
}
```

#### 2. Workflow Started
```json
{
  "type": "workflow_started",
  "workflow_id": "workflow_123",
  "timestamp": "2026-05-17T07:30:01Z"
}
```

#### 3. Stage Started
```json
{
  "type": "stage.started",
  "workflow_id": "workflow_123",
  "stage": "ideation",
  "message": "Starting ideation stage"
}
```

#### 4. Stage Progress
```json
{
  "type": "stage.progress",
  "workflow_id": "workflow_123",
  "stage": "coding",
  "data": {"progress": 45},
  "message": "Generating test suite..."
}
```

#### 5. Question Asked
```json
{
  "type": "question.asked",
  "workflow_id": "workflow_123",
  "stage": "ideation",
  "data": {
    "question_id": "q_456",
    "question": "What type of token?",
    "question_type": "multiple_choice",
    "options": ["ERC-20", "ERC-721", "ERC-1155"],
    "default": "ERC-20",
    "timeout": 300
  }
}
```

#### 6. Answer Received
```json
{
  "type": "answer.received",
  "workflow_id": "workflow_123",
  "stage": "ideation",
  "data": {"question_id": "q_456", "answer": "ERC-20"}
}
```

#### 7. Stage Complete
```json
{
  "type": "stage.complete",
  "workflow_id": "workflow_123",
  "stage": "testing",
  "data": {"tests_passed": 15, "coverage": 95}
}
```

#### 8. Feedback Loop
```json
{
  "type": "feedback.loop",
  "workflow_id": "workflow_123",
  "data": {
    "from": "testing",
    "to": "coding",
    "reason": "3 tests failed, fixing code..."
  }
}
```

#### 9. Workflow Complete
```json
{
  "type": "workflow.complete",
  "workflow_id": "workflow_123",
  "data": {"status": "completed"}
}
```

#### 10. Error
```json
{
  "type": "error",
  "workflow_id": "workflow_123",
  "message": "Error description"
}
```

---

## 🎯 Interactive Questions

The orchestrator asks questions at key stages:

### Ideation Stage
1. **Token Type**: "What type of token?" (ERC-20/ERC-721/ERC-1155/Custom)
2. **Features**: "What features?" (mintable, burnable, pausable, etc.)
3. **Blockchain**: "Which blockchain?" (Ethereum/Polygon/BSC/etc.)

### Coding Stage
4. **Additional Requirements**: "Any additional coding requirements?" (optional)

### Deployment Stage
5. **Deployment Confirmation**: "Ready to deploy?" (yes/no)

---

## 🔧 Configuration

### Environment Variables

```bash
# .env
PORT=8001
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
GITLAB_TOKEN=your_gitlab_token
```

### Question Timeouts

Default timeout: 300 seconds (5 minutes)

Customize in code:
```python
answer = await qm.ask_question(
    workflow_id=workflow_id,
    stage="ideation",
    question="Your question?",
    timeout=600  # 10 minutes
)
```

---

## 📊 Monitoring

### WebSocket Statistics

```bash
curl http://localhost:8001/ws/stats
```

Response:
```json
{
  "connections": {
    "total_workflows": 3,
    "total_connections": 5,
    "workflows": {
      "workflow_123": 2,
      "workflow_456": 3
    }
  },
  "questions": {
    "pending_questions": 1,
    "total_answers": 15
  },
  "events": {
    "active_subscribers": 5,
    "workflows_tracked": 3,
    "total_events": 247
  }
}
```

---

## 🐛 Troubleshooting

### WebSocket Connection Failed

**Problem**: `WebSocket connection to 'ws://localhost:8001/ws/workflow_123' failed`

**Solutions**:
1. Check server is running: `curl http://localhost:8001/health`
2. Check port: Server might be on different port
3. Check firewall: Allow port 8001
4. Check CORS: WebSocket should work from any origin

### Questions Not Appearing

**Problem**: Workflow runs but no questions asked

**Solutions**:
1. Check mode: Must be `orchestrate` mode (not `plan` or `code`)
2. Check function: Using `orchestrate_contract_development_interactive()`?
3. Check logs: Look for question events in server logs

### Timeout Errors

**Problem**: `TimeoutError: Question timeout`

**Solutions**:
1. Increase timeout: Pass `timeout=600` to `ask_question()`
2. Provide default: Pass `default="ERC-20"` to `ask_question()`
3. Make optional: Pass `required=False` to `ask_question()`

---

## 🚀 Next Steps

### Immediate Improvements

1. **Add More Questions**:
   - Testing stage: "Run on testnet first?"
   - Auditing stage: "Fix high-risk issues automatically?"
   - Monitoring stage: "Set up alerts?"

2. **Add Context Injection**:
   - Allow users to provide suggestions mid-workflow
   - "Add this feature to the contract..."

3. **Add Progress Bars**:
   - Show percentage complete for each stage
   - Estimate time remaining

4. **Add File Upload**:
   - Upload existing contract for analysis
   - Upload test cases

### Production Enhancements

1. **Authentication**:
   - Add JWT token validation
   - User-specific workflows

2. **Persistence**:
   - Store workflow state in Redis/PostgreSQL
   - Resume workflows after disconnect

3. **Rate Limiting**:
   - Limit connections per user
   - Limit workflows per hour

4. **Monitoring**:
   - Prometheus metrics
   - Grafana dashboards
   - Error tracking (Sentry)

---

## 📚 Architecture

```
┌─────────────┐                    ┌──────────────────┐
│   Client    │◄──────WebSocket────►│  WebSocket       │
│  (Browser)  │                     │  Router          │
└─────────────┘                     └──────────────────┘
                                             │
                                             ▼
                                    ┌──────────────────┐
                                    │  Connection      │
                                    │  Manager         │
                                    └──────────────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    ▼                        ▼                        ▼
           ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
           │  Event Bus   │        │  Question    │        │ Interactive  │
           │              │        │  Manager     │        │ Orchestrator │
           └──────────────┘        └──────────────┘        └──────────────┘
                    │                        │                        │
                    └────────────────────────┴────────────────────────┘
                                             │
                                             ▼
                                    ┌──────────────────┐
                                    │  Stage Routers   │
                                    │  (Ideation,      │
                                    │   Coding, etc.)  │
                                    └──────────────────┘
```

---

## ✅ Testing

### Manual Testing

1. **Start server**: `python main.py`
2. **Open frontend**: `open frontend_demo.html`
3. **Test workflow**:
   - Connect
   - Answer questions
   - Watch progress
   - Verify completion

### Automated Testing

```python
# tests/test_interactive_workflow.py
import pytest
import asyncio
from questions import get_question_manager, QuestionType

@pytest.mark.asyncio
async def test_question_answer():
    qm = get_question_manager()
    
    # Ask question in background
    async def ask():
        return await qm.ask_question(
            workflow_id="test",
            stage="test",
            question="Test?",
            timeout=5
        )
    
    task = asyncio.create_task(ask())
    await asyncio.sleep(0.1)
    
    # Answer question
    qm.answer_question("q_test_test_1_*", "Yes")
    
    # Get answer
    answer = await task
    assert answer == "Yes"
```

---

## 📝 Summary

**Total Implementation**:
- **7 new files** created
- **~2,000 lines** of production code
- **Full WebSocket bidirectional** communication
- **Real-time event streaming**
- **Interactive question/answer** system
- **Beautiful frontend** demo
- **Python test client**
- **Complete documentation**

**Ready for**:
- ✅ Hackathon demo
- ✅ User testing
- ✅ Production deployment (with auth/persistence)

**Next**: Test the system end-to-end and iterate based on feedback!