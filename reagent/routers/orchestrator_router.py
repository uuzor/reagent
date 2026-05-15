from agentfield import AgentRouter
from pydantic import BaseModel, Field
import os
import time

from file_manager import FileManager

# Router for orchestration and workflow management
orchestrator_router = AgentRouter(prefix="orchestrate", tags=["orchestration", "workflow"])

_fm: FileManager | None = None


def _get_fm() -> FileManager | None:
    global _fm
    if _fm is None and os.getenv("GITLAB_TOKEN"):
        _fm = FileManager()
    return _fm


class OrchestrationResult(BaseModel):
    """Structured output for orchestration result."""
    workflow_id: str = Field(description="Unique workflow ID")
    stages_completed: list[str] = Field(description="Completed stages")
    current_stage: str = Field(description="Current active stage")
    status: str = Field(description="Overall status")
    outputs: dict = Field(description="Stage outputs")
    gitlab_issue: dict | None = Field(default=None, description="GitLab tracking issue reference")


@orchestrator_router.reasoner(tags=["ai", "coordination"])
async def orchestrate_contract_development(requirements: str) -> dict:
    """
    Orchestrate the full smart contract development workflow.
    Creates a GitLab issue for tracking and logs each stage completion.
    """
    workflow_id = f"workflow_{int(time.time())}"
    fm = _get_fm()

    # Create tracking issue in GitLab
    issue_ref = None
    if fm:
        issue = fm.gl.create_issue(
            title=f"Smart contract workflow: {workflow_id}",
            description=f"Requirements:\n{requirements}",
            labels=["reagent", "orchestration"],
        )
        issue_ref = issue

    stages_completed = []
    outputs = {}

    # Stage 1: Ideation
    spec = await orchestrator_router.app.call(
        f"{orchestrator_router.app.node_id}.ideation_generate_contract_spec",
        requirements=requirements,
    )
    stages_completed.append("ideation")
    outputs["spec"] = spec
    if fm and issue_ref:
        fm.gl.add_issue_note(issue_ref["iid"], f"Stage 1 complete: ideation — spec for '{spec.get('name')}' generated")

    # Stage 2: Coding
    code = await orchestrator_router.app.call(
        f"{orchestrator_router.app.node_id}.coding_generate_contract_code",
        spec=spec,
    )
    stages_completed.append("coding")
    outputs["code"] = code
    if fm and issue_ref:
        fm.gl.add_issue_note(issue_ref["iid"], f"Stage 2 complete: coding — {code.get('solidity_code', '')[:100]}...")

    # Stage 3: Testing
    contract_path = f"contracts/{spec.get('name', 'Contract')}.sol"
    test_results = await orchestrator_router.app.call(
        f"{orchestrator_router.app.node_id}.testing_run_comprehensive_tests",
        contract_path=contract_path,
    )
    stages_completed.append("testing")
    outputs["tests"] = test_results
    if fm and issue_ref:
        passed = test_results.get("passed", False)
        fm.gl.add_issue_note(issue_ref["iid"], f"Stage 3 complete: testing — {'PASSED' if passed else 'FAILED'}")

    # Stage 4: Auditing
    audit = await orchestrator_router.app.call(
        f"{orchestrator_router.app.node_id}.auditing_comprehensive_audit",
        contract_code=code.get("solidity_code", ""),
        contract_path=contract_path,
    )
    stages_completed.append("auditing")
    outputs["audit"] = audit
    if fm and issue_ref:
        fm.gl.add_issue_note(issue_ref["iid"], f"Stage 4 complete: auditing — risk level: {audit.get('overall_risk')}")

    # Stage 5: Deployment (if tests pass)
    deployment = None
    monitor = None
    current_stage = "testing_fixes"
    if test_results.get("passed", False):
        deployment = await orchestrator_router.app.call(
            f"{orchestrator_router.app.node_id}.deployment_deploy_contract",
            contract_path=contract_path,
        )
        stages_completed.append("deployment")
        outputs["deployment"] = deployment
        current_stage = "monitoring"

        # Start monitoring
        monitor = await orchestrator_router.app.call(
            f"{orchestrator_router.app.node_id}.monitoring_monitor_contract",
            contract_address=deployment.get("contract_address", ""),
        )
        outputs["monitoring"] = monitor
        if fm and issue_ref:
            fm.gl.add_issue_note(issue_ref["iid"], f"Stage 5 complete: deployed to {deployment.get('network')} at {deployment.get('contract_address')}")
    else:
        if fm and issue_ref:
            fm.gl.add_issue_note(issue_ref["iid"], "Deployment skipped — tests did not pass. Requires fixes.")

    result = OrchestrationResult(
        workflow_id=workflow_id,
        stages_completed=stages_completed,
        current_stage=current_stage,
        status="completed" if deployment else "pending_fixes",
        outputs=outputs,
        gitlab_issue=issue_ref,
    )

    orchestrator_router.app.note(
        f"Workflow {workflow_id} completed stages: {stages_completed}",
        tags=["orchestration", "workflow"],
    )

    return result.model_dump()


@orchestrator_router.skill(tags=["status", "query"])
def get_workflow_status(workflow_id: str, issue_iid: int | None = None) -> dict:
    """
    Get status of a specific workflow from GitLab issue or local state.
    """
    fm = _get_fm()
    if fm and issue_iid:
        issue = fm.gl.get_issue(issue_iid)
        return {
            "workflow_id": workflow_id,
            "status": issue["state"],
            "title": issue["title"],
            "web_url": issue["web_url"],
        }
    return {
        "workflow_id": workflow_id,
        "status": "unknown",
        "note": "Provide issue_iid or configure GITLAB_TOKEN for live tracking",
    }


@orchestrator_router.skill(tags=["retry", "error-handling"])
def retry_failed_stage(workflow_id: str, stage: str) -> dict:
    """
    Retry a failed stage in the workflow.
    """
    return {
        "workflow_id": workflow_id,
        "stage": stage,
        "status": "retry_initiated",
        "note": "Retry logic requires workflow state management"
    }