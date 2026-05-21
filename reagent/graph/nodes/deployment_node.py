"""Deployment node — wraps the existing deployment stage router."""

from ..state import ContractDevState


async def deployment_node(state: ContractDevState) -> dict:
    """
    Execute deployment stage as a LangGraph node.

    Calls the existing deployment reasoner via app.call().
    Requires contract code from the coding stage.
    """
    from ..utils import get_orchestrator_router, emit_stage_event

    orchestrator = get_orchestrator_router()
    workflow_id = state.get("workflow_id", "unknown")

    await emit_stage_event("start", workflow_id, "deployment")

    code = state.get("contract_code")
    if not code:
        error = "No contract code for deployment"
        await emit_stage_event("error", workflow_id, "deployment", error=error)
        return {
            "errors": state.get("errors", []) + [{"stage": "deployment", "error": error}],
            "current_stage": "deployment",
        }

    try:
        kwargs = {"code": code}
        spec = state.get("spec")
        if spec:
            kwargs["spec"] = spec

        result = await orchestrator.app.call(
            f"{orchestrator.app.node_id}.deployment_deploy_contract",
            **kwargs,
        )

        await emit_stage_event("complete", workflow_id, "deployment", data={"deployment": result})

        return {
            "deployment_result": result,
            "current_stage": "deployment",
            "stages_completed": state.get("stages_completed", []) + ["deployment"],
        }
    except Exception as e:
        await emit_stage_event("error", workflow_id, "deployment", error=str(e))
        return {
            "errors": state.get("errors", []) + [{"stage": "deployment", "error": str(e)}],
            "current_stage": "deployment",
        }
