"""WebSocket router for interactive workflow communication.

Provides WebSocket endpoints for real-time bidirectional communication
between clients and the orchestrator.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Optional
import json
import asyncio
import logging
from datetime import datetime

from websocket_handler import get_connection_manager
from questions import get_question_manager
from events import get_event_bus, EventType, WorkflowEvent

logger = logging.getLogger(__name__)


def _serialize_value(obj):
    """Recursively serialize objects for JSON, handling datetime and pydantic models."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize_value(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_value(item) for item in obj]
    if hasattr(obj, 'model_dump'):  # Pydantic v2
        return _serialize_value(obj.model_dump())
    if hasattr(obj, 'dict'):  # Pydantic v1
        return _serialize_value(obj.dict())
    return obj


def _event_to_message(event: WorkflowEvent) -> dict:
    """Convert WorkflowEvent to a JSON-serializable WebSocket message."""
    return {
        "type": event.event_type,
        "workflow_id": event.workflow_id,
        "stage": event.stage,
        "timestamp": event.timestamp.isoformat(),
        "message": event.message,
        "data": _serialize_value(event.data),
    }

# Create router (not AgentRouter, regular FastAPI router for WebSocket)
websocket_router = APIRouter(prefix="/ws", tags=["websocket"])


@websocket_router.websocket("/{workflow_id}")
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
    
    Args:
        websocket: WebSocket connection
        workflow_id: Workflow ID for this connection
    """
    cm = get_connection_manager()
    qm = get_question_manager()
    
    # Connect WebSocket
    await cm.connect(websocket, workflow_id)
    
    # Subscribe to events for this workflow
    subscriber_id, event_queue = get_event_bus().subscribe(workflow_id)
    
    # Task to forward events to WebSocket
    async def forward_events():
        """Forward events from event bus to WebSocket."""
        try:
            while True:
                event = await event_queue.get()
                message = _event_to_message(event)
                await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error forwarding events: {e}")
    
    # Start event forwarding task
    event_task = asyncio.create_task(forward_events())
    
    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "workflow_id": workflow_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "WebSocket connected successfully"
        })
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            msg_type = message.get("type")
            logger.info(f"Received WebSocket message: type={msg_type}, workflow={workflow_id}")
            
            if msg_type == "start_workflow":
                # Start workflow in background
                requirements = message.get("requirements")
                mode = message.get("mode", "orchestrate")
                
                await websocket.send_json({
                    "type": "workflow_started",
                    "workflow_id": workflow_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": "Workflow started"
                })
                
                # Trigger orchestration (non-blocking)
                asyncio.create_task(
                    start_interactive_workflow(workflow_id, requirements, mode)
                )
            
            elif msg_type == "answer":
                # Answer to question
                question_id = message.get("question_id")
                answer = message.get("answer")
                
                if not question_id:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Missing question_id"
                    })
                    continue
                
                success = qm.answer_question(question_id, answer)
                
                await websocket.send_json({
                    "type": "answer_received",
                    "question_id": question_id,
                    "success": success,
                    "message": "Answer received" if success else "Question not found"
                })
            
            elif msg_type == "inject_context":
                # User provides mid-workflow suggestion
                stage = message.get("stage")
                suggestion = message.get("suggestion")
                
                if not suggestion:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Missing suggestion"
                    })
                    continue
                
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
                    "stage": stage,
                    "message": "Context injected successfully"
                })
            
            elif msg_type == "abort":
                # User cancels workflow
                reason = message.get("reason", "User cancelled")
                
                await get_event_bus().emit(WorkflowEvent(
                    event_type=EventType.WORKFLOW_FAILED,
                    workflow_id=workflow_id,
                    data={"reason": reason, "aborted": True},
                    message=f"Workflow aborted: {reason}"
                ))
                
                await websocket.send_json({
                    "type": "workflow_aborted",
                    "workflow_id": workflow_id,
                    "message": f"Workflow aborted: {reason}"
                })
                break
            
            elif msg_type == "ping":
                # Heartbeat
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })

            elif msg_type == "file_tree":
                # Request file tree for a branch/repo
                branch = message.get("branch", "main")
                path = message.get("path", "")

                try:
                    from file_manager import FileManager
                    fm = FileManager()
                    files = fm.list_tree(branch=branch, path=path)
                    tree_str = fm.tree_ascii(branch=branch, path=path)

                    await websocket.send_json({
                        "type": "file_tree",
                        "workflow_id": workflow_id,
                        "branch": branch,
                        "path": path,
                        "files": files,
                        "tree": tree_str,
                        "total_files": len([f for f in files if f.get("type") == "blob"]),
                    })
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Failed to get file tree: {str(e)}"
                    })

            elif msg_type == "read_file":
                # Request file content
                file_path = message.get("path", "")
                branch = message.get("branch", "main")

                if not file_path:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Missing path"
                    })
                    continue

                try:
                    from file_manager import FileManager
                    fm = FileManager()
                    content = fm.read_file(file_path, branch=branch)
                    category = fm.file_category(file_path)

                    await websocket.send_json({
                        "type": "file_content",
                        "workflow_id": workflow_id,
                        "path": file_path,
                        "branch": branch,
                        "content": content,
                        "category": category,
                        "size": len(content),
                    })
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Failed to read file: {str(e)}"
                    })

            else:
                # Unknown message type
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}"
                })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: workflow={workflow_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Cleanup
        event_task.cancel()
        cm.disconnect(websocket)
        get_event_bus().unsubscribe(subscriber_id)


async def start_interactive_workflow(
    workflow_id: str,
    requirements: str,
    mode: str
):
    """Start interactive workflow via LangGraph (called from WebSocket).

    Args:
        workflow_id: Workflow ID
        requirements: User requirements
        mode: Execution mode (orchestrate, plan, code)
    """
    try:
        from routers.orchestrator_router import run_contract_workflow
        from events import get_event_bus, EventType, WorkflowEvent

        logger.info(f"Starting interactive LangGraph workflow: {workflow_id}")

        result = await run_contract_workflow(
            requirements=requirements,
            mode=mode,
            workflow_id=workflow_id,
        )

        # Emit workflow complete event (LangGraph doesn't emit this)
        status = result.get("status", "completed")
        if status == "failed":
            await get_event_bus().emit(WorkflowEvent(
                event_type=EventType.WORKFLOW_FAILED,
                workflow_id=workflow_id,
                data={"errors": result.get("errors", [])},
                message=f"Workflow failed: {result.get('errors', [])}"
            ))
        else:
            await get_event_bus().emit(WorkflowEvent(
                event_type=EventType.WORKFLOW_COMPLETE,
                workflow_id=workflow_id,
                data={"stages": result.get("stages_completed", [])},
                message="Workflow completed successfully"
            ))

        logger.info(f"Interactive workflow completed: {workflow_id}")

    except Exception as e:
        logger.error(f"Interactive workflow failed: {e}")

        await get_event_bus().emit(WorkflowEvent(
            event_type=EventType.WORKFLOW_FAILED,
            workflow_id=workflow_id,
            data={"error": str(e)},
            message=f"Workflow failed: {str(e)}"
        ))


@websocket_router.get("/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics.
    
    Returns:
        Statistics about active connections
    """
    cm = get_connection_manager()
    qm = get_question_manager()
    eb = get_event_bus()
    
    return {
        "connections": cm.get_stats(),
        "questions": qm.get_stats(),
        "events": eb.get_stats()
    }

# Made with Bob
