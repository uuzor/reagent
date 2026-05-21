"""Conditional routing edges for the contract development workflow.

Phase 2: AI-powered routing with LangChain StructuredOutput replaces
the brittle markdown-regex parsing in decide_next_stage().

Each routing function uses AI to analyze stage results and decide the next node.
Hardcoded rules serve as fallback when AI is unavailable.
"""

from pydantic import BaseModel, Field
from typing import Optional

from .state import ContractDevState

MAX_RETRIES = 3


class RoutingDecision(BaseModel):
    """Structured AI output for routing decisions.

    Used with LangChain StructuredOutput to get typed responses
    — no markdown regex parsing needed.
    """
    next_stage: str = Field(
        description="Next stage to execute: 'coding', 'testing', 'auditing', 'deployment', 'monitoring', or 'end'"
    )
    reason: str = Field(description="Explanation for this routing decision")
    retry: bool = Field(default=False, description="Whether this is a retry of a failed stage")
    suggestions: list[str] = Field(default_factory=list, description="Suggestions for the next stage")


# ──────────────────────────────────────────────────────────────
# AI-powered routing (Phase 2)
# ──────────────────────────────────────────────────────────────

async def ai_route_after_stage(state: ContractDevState, stage: str, candidates: list[str]) -> RoutingDecision:
    """
    Use AI to decide the next stage after a given stage completes.

    Args:
        state: Current workflow state
        stage: The stage that just completed
        candidates: List of valid next stages (e.g. ['auditing', 'coding', 'end'])

    Returns:
        RoutingDecision with the next stage and reasoning.
    """
    from graph.utils import get_orchestrator_router

    router = get_orchestrator_router()

    # Build context for AI decision
    stage_output = state.get(f"{_stage_to_key(stage)}")
    errors = state.get("errors", [])
    stage_errors = [e for e in errors if e.get("stage") == stage]
    retry_count = state.get("retry_counts", {}).get(stage, 0)

    user_prompt = f"""Stage just completed: {stage}
Retry count for this stage: {retry_count}/{MAX_RETRIES}
Candidates for next stage: {candidates}"""

    if stage_output:
        user_prompt += f"\n\nStage output summary: {_summarize_output(stage, stage_output)}"

    if stage_errors:
        user_prompt += f"\n\nErrors: {[e.get('error', '') for e in stage_errors]}"

    # Check if human rejected the output
    human_review = state.get("human_review")
    if human_review and not human_review.get("approved", True):
        user_prompt += f"\n\nHuman review rejected: {human_review.get('comments', '')}"

    try:
        decision = await router.ai(
            system=f"""You are a smart contract development workflow router.
Analyze the stage result and decide the next action.

Rules:
1. If stage succeeded with no issues → proceed to the next logical stage
2. If stage failed with fixable error → retry (go back to appropriate stage)
3. If stage failed after {MAX_RETRIES} retries → end the workflow
4. If human reviewer rejected the output → go back to fix it
5. Consider dependencies: coding needs spec, testing needs code, etc.

Choose from these candidates: {candidates}""",
            user=user_prompt,
            schema=RoutingDecision,
        )

        # Validate the decision is in candidates
        if decision.next_stage not in candidates:
            decision.next_stage = candidates[0]  # Default to first candidate

        return decision

    except Exception:
        # Fallback to hardcoded rules if AI fails
        return _fallback_route(stage, state, candidates)


def _fallback_route(stage: str, state: ContractDevState, candidates: list[str]) -> RoutingDecision:
    """Hardcoded routing fallback when AI is unavailable.

    Uses the adaptive retry agent to determine retry counts based on error type.
    """
    from agents.retry_agent import decide_retry_count

    retry_count = state.get("retry_counts", {}).get(stage, 0)
    errors = state.get("errors", [])
    stage_errors = [e for e in errors if e.get("stage") == stage]
    error_msg = stage_errors[-1].get("error", "") if stage_errors else ""

    retry_decision = decide_retry_count(error_msg, stage, retry_count)

    if stage == "testing":
        test_results = state.get("test_results")
        if test_results and test_results.get("success", False):
            return RoutingDecision(next_stage="auditing", reason="Tests passed")
        if retry_decision.should_retry:
            return RoutingDecision(next_stage="coding", reason=retry_decision.reason, retry=True)
        return RoutingDecision(next_stage="end", reason=retry_decision.reason)

    elif stage == "auditing":
        audit = state.get("audit_report")
        if audit and not audit.get("critical_issues", []):
            return RoutingDecision(next_stage="deployment", reason="Audit passed")
        if retry_decision.should_retry:
            return RoutingDecision(next_stage="coding", reason=retry_decision.reason, retry=True)
        return RoutingDecision(next_stage="end", reason=retry_decision.reason)

    elif stage == "deployment":
        deployment = state.get("deployment_result")
        if deployment and deployment.get("success", False):
            return RoutingDecision(next_stage="monitoring", reason="Deployment succeeded")
        if retry_decision.should_retry:
            return RoutingDecision(next_stage="coding", reason=retry_decision.reason, retry=True)
        return RoutingDecision(next_stage="end", reason=retry_decision.reason)

    # Default: proceed to first candidate
    return RoutingDecision(next_stage=candidates[0] if candidates else "end", reason="Default routing")


# ──────────────────────────────────────────────────────────────
# LangGraph edge functions (async, call AI routing)
# ──────────────────────────────────────────────────────────────

async def route_after_testing(state: ContractDevState) -> str:
    """AI-powered routing after testing stage."""
    decision = await ai_route_after_stage(state, "testing", ["auditing", "coding", "end"])
    next_stage = _normalize_next_stage(decision.next_stage)

    # Emit feedback loop event if routing back to coding
    if next_stage == "coding":
        from .utils import emit_stage_event
        wf_id = state.get("workflow_id", "unknown")
        await emit_stage_event("feedback", wf_id, "testing", data={
            "from": "testing",
            "to": "coding",
            "reason": decision.reason,
        })

    return next_stage


async def route_after_auditing(state: ContractDevState) -> str:
    """AI-powered routing after auditing stage."""
    decision = await ai_route_after_stage(state, "auditing", ["deployment", "coding", "end"])
    next_stage = _normalize_next_stage(decision.next_stage)

    if next_stage == "coding":
        from .utils import emit_stage_event
        wf_id = state.get("workflow_id", "unknown")
        await emit_stage_event("feedback", wf_id, "auditing", data={
            "from": "auditing",
            "to": "coding",
            "reason": decision.reason,
        })

    return next_stage


async def route_after_deployment(state: ContractDevState) -> str:
    """AI-powered routing after deployment stage."""
    decision = await ai_route_after_stage(state, "deployment", ["monitoring", "coding", "end"])
    next_stage = _normalize_next_stage(decision.next_stage)

    if next_stage == "coding":
        from .utils import emit_stage_event
        wf_id = state.get("workflow_id", "unknown")
        await emit_stage_event("feedback", wf_id, "deployment", data={
            "from": "deployment",
            "to": "coding",
            "reason": decision.reason,
        })

    return next_stage


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _normalize_next_stage(stage: str) -> str:
    """Normalize AI response to LangGraph node name."""
    if stage in ("end", "failed", "__end__", "completed"):
        return "__end__"
    return stage


def _stage_to_key(stage: str) -> str:
    """Map stage name to state key."""
    mapping = {
        "ideation": "spec",
        "coding": "contract_code",
        "testing": "test_results",
        "auditing": "audit_report",
        "deployment": "deployment_result",
        "monitoring": "monitoring_report",
    }
    return mapping.get(stage, stage)


def _summarize_output(stage: str, output: dict) -> str:
    """Create a brief summary of stage output for AI context."""
    if stage == "testing":
        return f"Success: {output.get('success', False)}, Tests: {output.get('tests_run', 'unknown')}"
    elif stage == "auditing":
        critical = output.get("critical_issues", [])
        return f"Critical issues: {len(critical)}, Severity: {output.get('severity', 'unknown')}"
    elif stage == "deployment":
        return f"Success: {output.get('success', False)}, Network: {output.get('network', 'unknown')}"
    elif stage == "coding":
        return f"Contract: {output.get('contract_name', 'unknown')}, Size: {len(output.get('solidity_code', ''))} chars"
    elif stage == "ideation":
        return f"Spec: {output.get('name', 'unknown')}, Standards: {output.get('standards', [])}"
    return str(output)[:200]
