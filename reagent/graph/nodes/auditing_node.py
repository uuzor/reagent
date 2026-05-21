"""Auditing node — wraps the existing auditing stage router."""

from ..state import ContractDevState


async def auditing_node(state: ContractDevState) -> dict:
    """
    Execute auditing stage as a LangGraph node.

    Calls the existing auditing reasoner via app.call().
    Requires contract code from the coding stage.
    """
    from ..utils import get_orchestrator_router, emit_stage_event

    orchestrator = get_orchestrator_router()
    workflow_id = state.get("workflow_id", "unknown")

    await emit_stage_event("start", workflow_id, "auditing")

    code = state.get("contract_code")
    if not code:
        error = "No contract code for auditing"
        await emit_stage_event("error", workflow_id, "auditing", error=error)
        return {
            "errors": state.get("errors", []) + [{"stage": "auditing", "error": error}],
            "current_stage": "auditing",
        }

    try:
        kwargs = {"code": code}
        ctx = state.get("agent_context")
        if ctx:
            kwargs["context"] = ctx

        # Run automated security scan before AI audit
        try:
            from agents.security_agent import run_security_scan
            solidity_code = code.get("solidity_code", "") if isinstance(code, dict) else ""
            if solidity_code:
                scan_results = run_security_scan(solidity_code)
                kwargs["security_scan_results"] = scan_results
        except Exception:
            pass  # Fallback: AI audit without scan results

        audit = await orchestrator.app.call(
            f"{orchestrator.app.node_id}.auditing_perform_audit",
            **kwargs,
        )

        await emit_stage_event("complete", workflow_id, "auditing", data={"audit": audit})

        return {
            "audit_report": audit,
            "current_stage": "auditing",
            "stages_completed": state.get("stages_completed", []) + ["auditing"],
        }
    except Exception as e:
        await emit_stage_event("error", workflow_id, "auditing", error=str(e))
        return {
            "errors": state.get("errors", []) + [{"stage": "auditing", "error": str(e)}],
            "current_stage": "auditing",
        }
