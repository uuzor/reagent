"""State schema for the contract development LangGraph workflow."""

from typing import Any, Optional
from typing_extensions import TypedDict


class ContractDevState(TypedDict, total=False):
    """
    Accumulated state for the contract development workflow.

    Uses total=False so nodes can return partial updates.
    LangGraph merges node outputs into the running state.
    """

    # Core workflow data
    workflow_id: str
    requirements: str
    mode: str  # "plan" | "orchestrate" | "code"

    # Stage outputs (accumulated)
    spec: Optional[dict]
    contract_code: Optional[dict]
    test_results: Optional[dict]
    audit_report: Optional[dict]
    deployment_result: Optional[dict]
    monitoring_report: Optional[dict]

    # Control flow
    current_stage: str
    retry_counts: dict  # stage_name -> int
    stages_completed: list
    feedback_loops: list  # [{"from": str, "to": str, "reason": str}]

    # Human-in-the-loop
    human_review: Optional[dict]  # {"approved": bool, "comments": str}

    # Context system
    agent_context: dict  # AgentContext.to_dict()

    # Observability
    stage_costs: dict  # stage_name -> {"tokens": int, "cost_usd": float}
    trace_id: str

    # Error tracking
    errors: list  # [{"stage": str, "error": str, "timestamp": float}]
