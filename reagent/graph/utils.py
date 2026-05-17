"""Shared utilities for graph nodes."""

from events import emit_event, EventType


def get_orchestrator_router():
    """Get the orchestrator router for cross-agent calls.

    Imported lazily to avoid circular imports.
    """
    from routers.orchestrator_router import orchestrator_router
    return orchestrator_router


async def emit_stage_event(
    event_kind: str,
    workflow_id: str,
    stage: str,
    data: dict | None = None,
    error: str | None = None,
) -> None:
    """Emit a stage lifecycle event to the EventBus.

    Args:
        event_kind: "start", "complete", or "error"
        workflow_id: Workflow identifier
        stage: Stage name
        data: Optional event data payload
        error: Optional error message for error events
    """
    if event_kind == "start":
        await emit_event(
            EventType.STAGE_START,
            workflow_id=workflow_id,
            stage=stage,
            message=f"Stage {stage} started",
        )
    elif event_kind == "complete":
        await emit_event(
            EventType.STAGE_COMPLETE,
            workflow_id=workflow_id,
            stage=stage,
            data=data or {},
            message=f"Stage {stage} completed",
        )
    elif event_kind == "error":
        await emit_event(
            EventType.STAGE_FAILED,
            workflow_id=workflow_id,
            stage=stage,
            data={"error": error} if error else {},
            message=f"Stage {stage} failed: {error}",
        )
