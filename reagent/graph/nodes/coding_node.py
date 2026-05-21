"""Coding node — wraps the existing coding stage router."""

from ..state import ContractDevState


async def coding_node(state: ContractDevState) -> dict:
    """
    Execute coding stage as a LangGraph node.

    Calls the existing coding_generate_contract_code reasoner via app.call().
    Requires a valid spec from the ideation stage.
    """
    from ..utils import get_orchestrator_router, emit_stage_event

    orchestrator = get_orchestrator_router()
    workflow_id = state.get("workflow_id", "unknown")

    await emit_stage_event("start", workflow_id, "coding")

    # Validate spec exists
    spec = state.get("spec")
    if not spec:
        error = "No valid specification from ideation"
        await emit_stage_event("error", workflow_id, "coding", error=error)
        return {
            "errors": state.get("errors", []) + [{"stage": "coding", "error": error}],
            "current_stage": "coding",
        }

    try:
        kwargs = {"spec": spec}
        ctx = state.get("agent_context")
        if ctx:
            kwargs["context"] = ctx

        # Recommend blockchain from requirements
        try:
            from agents.blockchain_agent import recommend_blockchain
            requirements = state.get("requirements", "")
            blockchain = recommend_blockchain(requirements)
            kwargs["target_blockchain"] = blockchain
        except Exception:
            pass  # Fallback: reasoner uses its own defaults

        # Determine file structure from requirements
        try:
            from agents.file_agent import determine_file_structure
            file_struct = determine_file_structure(requirements)
            kwargs["file_structure"] = file_struct
        except Exception:
            pass

        # Add test feedback if looping back from testing
        if state.get("test_results"):
            kwargs["recovery_context"] = f"Previous testing feedback: {state['test_results']}"

        code = await orchestrator.app.call(
            f"{orchestrator.app.node_id}.coding_generate_contract_code",
            **kwargs,
        )

        await emit_stage_event("complete", workflow_id, "coding", data={"code": code})

        return {
            "contract_code": code,
            "current_stage": "coding",
            "stages_completed": state.get("stages_completed", []) + ["coding"],
        }
    except Exception as e:
        await emit_stage_event("error", workflow_id, "coding", error=str(e))
        return {
            "errors": state.get("errors", []) + [{"stage": "coding", "error": str(e)}],
            "current_stage": "coding",
        }
