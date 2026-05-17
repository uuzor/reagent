"""
Event Logging & Streaming System
Provides structured event emission for workflow runs, enabling
real-time frontend updates via SSE/WebSocket and event history queries.
"""
import asyncio
import time
import json
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, AsyncIterator
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events emitted during workflow execution."""
    # Workflow lifecycle
    WORKFLOW_START = "workflow_start"
    WORKFLOW_STATUS = "workflow_status"
    WORKFLOW_COMPLETE = "workflow_complete"
    WORKFLOW_FAILED = "workflow_failed"

    # Stage lifecycle
    STAGE_START = "stage_start"
    STAGE_PROGRESS = "stage_progress"
    STAGE_COMPLETE = "stage_complete"
    STAGE_ERROR = "stage_error"

    # Orchestration
    FEEDBACK_LOOP = "feedback_loop"
    DECISION_MADE = "decision_made"

    # Compute
    COMPUTE_TIER_SELECTED = "compute_tier_selected"

    # Context
    CONTEXT_INJECTED = "context_injected"

    # General
    LOG_LINE = "log_line"


@dataclass
class WorkflowEvent:
    """A single event emitted during a workflow run."""
    event_type: EventType
    workflow_id: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    stage: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "workflow_id": self.workflow_id,
            "stage": self.stage,
            "timestamp": self.timestamp,
            "data": self.data,
            "message": self.message,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class EventBus:
    """In-process async event bus with fan-out to subscribers.

    Uses asyncio.Queue per subscriber for backpressure.
    Maintains a bounded ring buffer for event history queries.
    """

    def __init__(self, max_queue_size: int = 1000, max_store_size: int = 10000):
        self._subscribers: Dict[str, asyncio.Queue] = {}
        self._subscriber_filters: Dict[str, Optional[str]] = {}  # sub_id -> workflow_id filter
        self._event_store: List[WorkflowEvent] = []
        self._max_store_size = max_store_size
        self._max_queue_size = max_queue_size
        self._workflow_index: Dict[str, List[int]] = defaultdict(list)  # workflow_id -> indices

    async def emit(self, event: WorkflowEvent) -> None:
        """Publish event to all subscribers and store it."""
        self._store_event(event)

        dead_queues = []
        for sub_id, queue in self._subscribers.items():
            # Check workflow filter
            filter_wf = self._subscriber_filters.get(sub_id)
            if filter_wf and event.workflow_id != filter_wf:
                continue

            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"Dropping events for slow subscriber: {sub_id}")
                dead_queues.append(sub_id)

        for sub_id in dead_queues:
            self._subscribers.pop(sub_id, None)
            self._subscriber_filters.pop(sub_id, None)

    def subscribe(self, workflow_id: Optional[str] = None) -> tuple[str, asyncio.Queue]:
        """Create a subscriber queue. Optionally filter by workflow_id.

        Returns:
            Tuple of (subscriber_id, queue)
        """
        sub_id = str(uuid.uuid4())[:8]
        queue = asyncio.Queue(maxsize=self._max_queue_size)
        self._subscribers[sub_id] = queue
        self._subscriber_filters[sub_id] = workflow_id
        return sub_id, queue

    def unsubscribe(self, subscriber_id: str) -> None:
        """Remove a subscriber."""
        self._subscribers.pop(subscriber_id, None)
        self._subscriber_filters.pop(subscriber_id, None)

    def get_history(self, workflow_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve stored events for a workflow."""
        indices = self._workflow_index.get(workflow_id, [])
        recent = indices[-limit:]
        return [self._event_store[i].to_dict() for i in recent if i < len(self._event_store)]

    def get_all_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve recent events across all workflows."""
        events = self._event_store[-limit:]
        return [e.to_dict() for e in events]

    def _store_event(self, event: WorkflowEvent) -> None:
        """Store event in ring buffer with index."""
        idx = len(self._event_store)
        self._event_store.append(event)
        self._workflow_index[event.workflow_id].append(idx)

        # Trim if over max size
        if len(self._event_store) > self._max_store_size:
            trim = len(self._event_store) - self._max_store_size
            self._event_store = self._event_store[trim:]
            # Rebuild index (simplified — clear and rebuild)
            self._workflow_index = defaultdict(list)
            for i, e in enumerate(self._event_store):
                self._workflow_index[e.workflow_id].append(i)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def total_events(self) -> int:
        return len(self._event_store)


# Singleton
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def emit_event(
    event_type: EventType,
    workflow_id: str,
    stage: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    message: str = "",
) -> None:
    """Convenience function to emit an event via the singleton bus."""
    bus = get_event_bus()
    event = WorkflowEvent(
        event_type=event_type,
        workflow_id=workflow_id,
        stage=stage,
        data=data or {},
        message=message,
    )
    await bus.emit(event)
