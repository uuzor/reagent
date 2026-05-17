"""Testing node — wraps the existing testing stage router."""

from ..state import ContractDevState


async def testing_node(state: ContractDevState) -> dict:
    """
    Execute testing stage as a LangGraph node.

    Calls the existing testing reasoner via app.call().
    Requires contract code from the coding stage.
    """
    from ..graph.utils import get_orchestrator_router, emit_stage_event

    orchestrator = get_orchestrator_router()
    workflow_id = state.get("workflow_id", "unknown")

    await emit_stage_event("start", workflow_id, "testing")

    code = state.get("contract_code")
    if not code:
        error = "No contract code from coding stage"
        await emit_stage_event("error", workflow_id, "testing", error=error)
        return {
            "errors": state.get("errors", []) + [{"stage": "testing", "error": error}],
            "current_stage": "testing",
        }

    try:
        kwargs = {"code": code}

        test_results = await orchestrator.app.call(
            f"{orchestrator.app.node_id}.testing_run_tests",
            **kwargs,
        )

        success = test_results.get("success", False) if isinstance(test_results, dict) else False

        await emit_stage_event(
            "complete" if success else "error",
            workflow_id, "testing",
            data=test_results if success else None,
            error=None if success else str(test_results),
        )

        return {
            "test_results": test_results,
            "current_stage": "testing",
            "stages_completed": state.get("stages_completed", []) + ["testing"],
        }
    except Exception as e:
        await emit_stage_event("error", workflow_id, "testing", error=str(e))
        return {
            "errors": state.get("errors", []) + [{"stage": "testing", "error": str(e)}],
            "current_stage": "testing",
        }
