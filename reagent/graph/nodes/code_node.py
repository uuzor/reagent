"""Code node — direct code generation, skips planning."""

from ..state import ContractDevState


async def code_node(state: ContractDevState) -> dict:
    """
    Execute code mode as a LangGraph node.

    Calls the existing code_direct_code_generation reasoner via app.call().
    Generates code directly from requirements, skipping planning/ideation.
    """
    from ..utils import get_orchestrator_router, emit_stage_event

    orchestrator = get_orchestrator_router()
    workflow_id = state.get("workflow_id", "unknown")

    await emit_stage_event("start", workflow_id, "code")

    try:
        kwargs = {"requirements": state["requirements"]}
        ctx = state.get("agent_context")
        if ctx:
            kwargs["context"] = ctx

        code = await orchestrator.app.call(
            f"{orchestrator.app.node_id}.code_direct_code_generation",
            **kwargs,
        )

        await emit_stage_event("complete", workflow_id, "code", data={"code": code})

        return {
            "contract_code": code,
            "current_stage": "code",
            "stages_completed": state.get("stages_completed", []) + ["code"],
        }
    except Exception as e:
        await emit_stage_event("error", workflow_id, "code", error=str(e))
        return {
            "errors": state.get("errors", []) + [{"stage": "code", "error": str(e)}],
            "current_stage": "code",
        }
