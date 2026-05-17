"""Event bus system for real-time workflow updates.

Provides pub/sub event streaming for WebSocket clients and internal components.
"""

import asyncio
from collections import deque
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Event types for workflow tracking."""
    # Workflow events
    WORKFLOW_START = "workflow.started"
    WORKFLOW_STATUS = "workflow.status"
    WORKFLOW_COMPLETE = "workflow.complete"
    WORKFLOW_FAILED = "workflow.failed"
    
    # Stage events
    STAGE_START = "stage.started"
    STAGE_PROGRESS = "stage.progress"
    STAGE_COMPLETE = "stage.complete"
    STAGE_ERROR = "stage.error"
    
    # Interactive events
    QUESTION_ASKED = "question.asked"
    ANSWER_RECEIVED = "answer.received"
    CONTEXT_INJECTED = "context.injected"
    
    # Orchestration events
    FEEDBACK_LOOP = "feedback.loop"
    DECISION_MADE = "decision.made"
    COMPUTE_TIER_SELECTED = "compute.tier_selected"
    
    # System events
    LOG_LINE = "log.line"
    ERROR = "error"


class WorkflowEvent(BaseModel):
    """Event emitted during workflow execution."""
    event_id: str = Field(default_factory=lambda: f"evt_{int(datetime.utcnow().timestamp() * 1000)}")
    event_type: EventType
    workflow_id: str
    stage: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class EventBus:
    """In-process async pub/sub event bus for workflow events."""
    
    def __init__(self, max_history: int = 1000):
        """Initialize event bus.
        
        Args:
            max_history: Maximum events to keep in history per workflow
        """
        self.max_history = max_history
        
        # Subscribers: subscriber_id -> (queue, workflow_id_filter)
        self._subscribers: Dict[str, tuple[asyncio.Queue, Optional[str]]] = {}
        
        # Event history: workflow_id -> deque of events
        self._history: Dict[str, deque] = {}
        
        # Subscriber counter for unique IDs
        self._subscriber_counter = 0
    
    async def emit(self, event: WorkflowEvent) -> None:
        """Emit event to all subscribers.
        
        Args:
            event: Event to emit
        """
        # Store in history
        if event.workflow_id not in self._history:
            self._history[event.workflow_id] = deque(maxlen=self.max_history)
        self._history[event.workflow_id].append(event)
        
        # Fan out to subscribers
        dead_subscribers = []
        for subscriber_id, (queue, workflow_filter) in self._subscribers.items():
            # Check if subscriber is interested in this workflow
            if workflow_filter is None or workflow_filter == event.workflow_id:
                try:
                    # Non-blocking put
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    # Subscriber is too slow, mark for removal
                    dead_subscribers.append(subscriber_id)
        
        # Clean up dead subscribers
        for subscriber_id in dead_subscribers:
            self.unsubscribe(subscriber_id)
    
    def subscribe(self, workflow_id: Optional[str] = None, maxsize: int = 100) -> tuple[str, asyncio.Queue]:
        """Subscribe to events.
        
        Args:
            workflow_id: Filter events for specific workflow (None = all workflows)
            maxsize: Maximum queue size
            
        Returns:
            Tuple of (subscriber_id, queue)
        """
        self._subscriber_counter += 1
        subscriber_id = f"sub_{self._subscriber_counter}"
        
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._subscribers[subscriber_id] = (queue, workflow_id)
        
        return subscriber_id, queue
    
    def unsubscribe(self, subscriber_id: str) -> bool:
        """Unsubscribe from events.
        
        Args:
            subscriber_id: Subscriber ID from subscribe()
            
        Returns:
            True if unsubscribed, False if not found
        """
        if subscriber_id in self._subscribers:
            del self._subscribers[subscriber_id]
            return True
        return False
    
    def get_history(self, workflow_id: str, limit: Optional[int] = None) -> List[WorkflowEvent]:
        """Get event history for a workflow.
        
        Args:
            workflow_id: Workflow ID
            limit: Maximum events to return (most recent)
            
        Returns:
            List of events (oldest to newest)
        """
        if workflow_id not in self._history:
            return []
        
        events = list(self._history[workflow_id])
        
        if limit is not None and limit > 0:
            events = events[-limit:]
        
        return events
    
    def clear_history(self, workflow_id: str) -> None:
        """Clear event history for a workflow.
        
        Args:
            workflow_id: Workflow ID
        """
        if workflow_id in self._history:
            del self._history[workflow_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "active_subscribers": len(self._subscribers),
            "workflows_tracked": len(self._history),
            "total_events": sum(len(h) for h in self._history.values()),
        }


# Global singleton
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get global event bus singleton.
    
    Returns:
        EventBus instance
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset global event bus (for testing)."""
    global _event_bus
    _event_bus = None


async def emit_event(
    event_type: EventType,
    workflow_id: str,
    stage: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    message: str = "",
) -> None:
    """Convenience helper to emit an event.
    
    Args:
        event_type: Type of event
        workflow_id: Workflow ID
        stage: Optional stage name
        data: Optional event data dict
        message: Human-readable message
    """
    event = WorkflowEvent(
        event_type=event_type,
        workflow_id=workflow_id,
        stage=stage,
        data=data or {},
        message=message,
    )
    await get_event_bus().emit(event)

# Made with Bob
