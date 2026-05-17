"""
Events Router — AgentField router for SSE streaming and event history queries.
"""
import os
import sys
import asyncio
import json
from typing import Optional
from pathlib import Path

from agentfield import AgentRouter

sys.path.insert(0, str(Path(__file__).parent.parent))

from pathlib import Path
from events import get_event_bus, WorkflowEvent, EventType

events_router = AgentRouter(prefix="events", tags=["events", "streaming"])


@events_router.skill(tags=["subscribe", "sse"])
async def subscribe_workflow_events(workflow_id: str) -> list[dict]:
    """Subscribe to events for a given workflow.

    Returns recent events immediately. For live streaming,
    use the streaming endpoint which yields NDJSON lines as events arrive.

    SSE format: data: {"event_type": "...", ...}\n\n
    """
    bus = get_event_bus()
    history = bus.get_history(workflow_id, limit=50)
    return history


@events_router.skill(tags=["history"])
def get_workflow_events(workflow_id: str, limit: int = 100) -> dict:
    """Get historical events for a workflow."""
    bus = get_event_bus()
    events = bus.get_history(workflow_id, limit=limit)
    return {
        "workflow_id": workflow_id,
        "events": events,
        "total": len(events),
    }


@events_router.skill(tags=["history", "all"])
def get_all_events(limit: int = 100) -> dict:
    """Get recent events across all workflows."""
    bus = get_event_bus()
    events = bus.get_all_history(limit=limit)
    return {
        "events": events,
        "total": len(events),
    }


@events_router.skill(tags=["status"])
def get_events_status() -> dict:
    """Get event bus status."""
    bus = get_event_bus()
    return {
        "active_subscribers": bus.subscriber_count,
        "total_events_stored": bus.total_events,
    }
