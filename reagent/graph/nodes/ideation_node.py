"""Ideation node — wraps the existing ideation stage router."""

from ..state import ContractDevState
from context import AgentContext, ContextSource


async def ideation_node(state: ContractDevState) -> dict:
    """
    Execute ideation stage as a LangGraph node.

    Calls the existing ideation_generate_contract_spec reasoner via app.call().
    Returns partial state update with spec and tracking fields.
    """
    from ..utils import get_orchestrator_router, emit_stage_event

    orchestrator = get_orchestrator_router()
    workflow_id = state.get("workflow_id", "unknown")

    await emit_stage_event("start", workflow_id, "ideation")

    try:
        kwargs = {"requirements": state["requirements"]}
        ctx = state.get("agent_context")
        if ctx:
            kwargs["context"] = ctx

        spec = await orchestrator.app.call(
            f"{orchestrator.app.node_id}.ideation_generate_contract_spec",
            **kwargs,
        )

        await emit_stage_event("complete", workflow_id, "ideation", data={"spec": spec})

        return {
            "spec": spec,
            "current_stage": "ideation",
            "stages_completed": state.get("stages_completed", []) + ["ideation"],
        }
    except Exception as e:
        await emit_stage_event("error", workflow_id, "ideation", error=str(e))
        return {
            "errors": state.get("errors", []) + [{"stage": "ideation", "error": str(e)}],
            "current_stage": "ideation",
        }
