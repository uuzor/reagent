"""Monitoring node — wraps the existing monitoring stage router."""

from ..state import ContractDevState


async def monitoring_node(state: ContractDevState) -> dict:
    """
    Execute monitoring stage as a LangGraph node.

    Calls the existing monitoring reasoner via app.call().
    Requires deployment result from the deployment stage.
    """
    from ..graph.utils import get_orchestrator_router, emit_stage_event

    orchestrator = get_orchestrator_router()
    workflow_id = state.get("workflow_id", "unknown")

    await emit_stage_event("start", workflow_id, "monitoring")

    deployment = state.get("deployment_result")
    if not deployment:
        error = "No deployment result for monitoring"
        await emit_stage_event("error", workflow_id, "monitoring", error=error)
        return {
            "errors": state.get("errors", []) + [{"stage": "monitoring", "error": error}],
            "current_stage": "monitoring",
        }

    try:
        kwargs = {"deployment": deployment}
        ctx = state.get("agent_context")
        if ctx:
            kwargs["context"] = ctx

        result = await orchestrator.app.call(
            f"{orchestrator.app.node_id}.monitoring_setup",
            **kwargs,
        )

        await emit_stage_event("complete", workflow_id, "monitoring", data={"monitoring": result})

        return {
            "monitoring_report": result,
            "current_stage": "monitoring",
            "stages_completed": state.get("stages_completed", []) + ["monitoring"],
        }
    except Exception as e:
        await emit_stage_event("error", workflow_id, "monitoring", error=str(e))
        return {
            "errors": state.get("errors", []) + [{"stage": "monitoring", "error": str(e)}],
            "current_stage": "monitoring",
        }
