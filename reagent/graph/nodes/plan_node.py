"""Plan node — AI analysis only, no execution."""

from ..state import ContractDevState


async def plan_node(state: ContractDevState) -> dict:
    """
    Execute plan mode as a LangGraph node.

    Calls the existing plan_analyze_and_plan reasoner via app.call().
    Analyzes requirements and produces a development plan without executing.
    """
    from ..graph.utils import get_orchestrator_router, emit_stage_event

    orchestrator = get_orchestrator_router()
    workflow_id = state.get("workflow_id", "unknown")

    await emit_stage_event("start", workflow_id, "plan")

    try:
        kwargs = {"requirements": state["requirements"]}
        ctx = state.get("agent_context")
        if ctx:
            kwargs["context"] = ctx

        plan = await orchestrator.app.call(
            f"{orchestrator.app.node_id}.plan_analyze_and_plan",
            **kwargs,
        )

        await emit_stage_event("complete", workflow_id, "plan", data={"plan": plan})

        return {
            "spec": plan,
            "current_stage": "plan",
            "stages_completed": state.get("stages_completed", []) + ["plan"],
        }
    except Exception as e:
        await emit_stage_event("error", workflow_id, "plan", error=str(e))
        return {
            "errors": state.get("errors", []) + [{"stage": "plan", "error": str(e)}],
            "current_stage": "plan",
        }
