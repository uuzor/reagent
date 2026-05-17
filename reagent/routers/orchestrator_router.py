from agentfield import AgentRouter
from pydantic import BaseModel, Field
import os
import time
from typing import Optional, List, Dict, Any
from enum import Enum

from file_manager import FileManager
from events import get_event_bus, emit_event, EventType
from context import AgentContext, ContextSource
from modes import ExecutionMode, ModeConfig
from compute import get_compute_router, ComputeCapability

# Router for orchestration and workflow management
orchestrator_router = AgentRouter(prefix="orchestrate", tags=["orchestration", "workflow"])

_fm: FileManager | None = None


def _get_fm() -> FileManager | None:
    global _fm
    if _fm is None and os.getenv("GITLAB_TOKEN"):
        _fm = FileManager()
    return _fm


class WorkflowStage(str, Enum):
    """Workflow stages."""
    IDEATION = "ideation"
    CODING = "coding"
    TESTING = "testing"
    AUDITING = "auditing"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    COMPLETED = "completed"
    FAILED = "failed"


# Stage order for workflow progression
STAGE_ORDER = [
    WorkflowStage.IDEATION.value,
    WorkflowStage.CODING.value,
    WorkflowStage.TESTING.value,
    WorkflowStage.AUDITING.value,
    WorkflowStage.DEPLOYMENT.value,
    WorkflowStage.MONITORING.value,
]


class ErrorRecoveryDecision(BaseModel):
    """Structured AI output for error recovery decisions."""
    analysis: str = Field(description="Analysis of the error and context")
    action: str = Field(description="Action to take: retry_same, go_back, or abort")
    target_stage: str = Field(description="Target stage to execute next")
    context_to_inject: str = Field(description="Context to pass to the next stage for recovery")
    confidence: float = Field(description="Confidence level in this decision (0-1)", ge=0, le=1)


class StageResult(BaseModel):
    """Result from a workflow stage."""
    stage: str
    success: bool
    output: Dict[str, Any]
    error: Optional[str] = None
    retry_count: int = 0
    next_stage: Optional[str] = None  # AI-determined next stage


class WorkflowState(BaseModel):
    """Complete workflow state for recovery and feedback loops."""
    workflow_id: str
    requirements: str
    current_stage: str
    stages_completed: List[str] = []
    stage_results: Dict[str, StageResult] = {}
    retry_counts: Dict[str, int] = {}
    max_retries: int = 3
    gitlab_issue: Optional[Dict] = None
    status: str = "in_progress"


class OrchestrationResult(BaseModel):
    """Structured output for orchestration result."""
    workflow_id: str = Field(description="Unique workflow ID")
    stages_completed: list[str] = Field(description="Completed stages")
    current_stage: str = Field(description="Current active stage")
    status: str = Field(description="Overall status")
    outputs: dict = Field(description="Stage outputs")
    gitlab_issue: dict | None = Field(default=None, description="GitLab tracking issue reference")
    feedback_loops: List[Dict] = Field(default=[], description="Feedback loops executed")


# In-memory workflow state (in production, use Redis/database)
_workflow_states: Dict[str, WorkflowState] = {}


@orchestrator_router.reasoner(tags=["ai", "decision"])
async def decide_next_stage(
    current_stage: str,
    stage_result: Dict[str, Any],
    workflow_state: Dict[str, Any]
) -> dict:
    """
    AI-powered decision maker for workflow progression.
    Analyzes stage results and decides next action (proceed, retry, or go back).
    """
    # Use AI to analyze the situation
    analysis = await orchestrator_router.ai(
        system="""You are a smart contract development workflow coordinator.
Analyze the stage result and decide the next action.

Rules:
1. If stage succeeded → proceed to next stage
2. If stage failed with fixable error → go back to appropriate stage
3. If stage failed after max retries → mark as failed
4. Consider dependencies: coding needs ideation, testing needs coding, etc.

Return JSON with:
- next_stage: "ideation"|"coding"|"testing"|"auditing"|"deployment"|"monitoring"|"failed"
- reason: explanation
- feedback_needed: true/false (if need to go back)
- suggestions: list of improvements""",
        user=f"""Current Stage: {current_stage}
Stage Result: {stage_result}
Workflow State: {workflow_state}

What should we do next?""",
    )
    
    # Convert MultimodalResponse to dict if needed
    if hasattr(analysis, 'model_dump'):
        analysis_dict = analysis.model_dump()
    elif isinstance(analysis, dict):
        analysis_dict = analysis
    else:
        # Fallback: try to access as object attributes
        analysis_dict = {
            'next_stage': getattr(analysis, 'next_stage', 'failed'),
            'reason': getattr(analysis, 'reason', str(analysis)),
            'feedback_needed': getattr(analysis, 'feedback_needed', False),
            'suggestions': getattr(analysis, 'suggestions', [])
        }
    
    orchestrator_router.app.note(
        f"Decision for {current_stage}: {analysis_dict.get('next_stage')} - {analysis_dict.get('reason')}",
        tags=["orchestration", "decision"]
    )
    
    return analysis_dict


@orchestrator_router.reasoner(tags=["ai", "coordination", "adaptive"])
async def orchestrate_contract_development_adaptive(
    requirements: str,
    mode: str = "orchestrate",
    context: dict | None = None,
) -> dict:
    """
    Adaptive orchestration with feedback loops and error recovery.
    Uses AI to decide next steps based on stage results.

    Supports three execution modes:
    - plan: AI analysis only, no execution
    - orchestrate: Full pipeline with feedback loops (default)
    - code: Direct code generation, skip planning

    Args:
        requirements: User requirements for the smart contract
        mode: Execution mode (plan, orchestrate, code)
        context: Optional AgentContext dict for mind building across stages
    """
    mode_config = ModeConfig(mode=ExecutionMode(mode))

    # Mode dispatch — plan and code delegate to their own routers
    if mode_config.mode == ExecutionMode.PLAN:
        return await orchestrator_router.app.call(
            f"{orchestrator_router.app.node_id}.plan_analyze_and_plan",
            requirements=requirements,
            context=context,
            plan_depth=mode_config.plan_depth,
        )

    if mode_config.mode == ExecutionMode.CODE:
        return await orchestrator_router.app.call(
            f"{orchestrator_router.app.node_id}.code_direct_code_generation",
            requirements=requirements,
            context=context,
            target_blockchain=mode_config.code_target_blockchain,
            include_tests=mode_config.code_include_tests,
            include_deployment=mode_config.code_include_deployment,
        )

    # ORCHESTRATE mode — full adaptive pipeline below
    workflow_id = f"workflow_{int(time.time())}"
    fm = _get_fm()

    # Initialize or restore agent context
    agent_ctx = AgentContext.from_dict(context) if context else AgentContext(workflow_id=workflow_id)
    agent_ctx.workflow_id = workflow_id
    agent_ctx.add_entry(ContextSource.USER_INPUT, requirements)

    # Initialize workflow state
    state = WorkflowState(
        workflow_id=workflow_id,
        requirements=requirements,
        current_stage=WorkflowStage.IDEATION.value
    )
    _workflow_states[workflow_id] = state

    # Emit workflow start event
    await emit_event(
        EventType.WORKFLOW_START,
        workflow_id=workflow_id,
        data={"requirements": requirements[:500]},
        message=f"Workflow started: {workflow_id}",
    )

    # Emit context injected event
    await emit_event(
        EventType.CONTEXT_INJECTED,
        workflow_id=workflow_id,
        data={"entries_count": len(agent_ctx.entries), "user_tier": agent_ctx.user_tier},
        message=f"Context initialized with {len(agent_ctx.entries)} entries",
    )

    # Select compute tier and emit event
    compute = get_compute_router()
    backend = compute.select_backend(
        required_capabilities={ComputeCapability.COMPILE, ComputeCapability.TEST},
        user_tier=agent_ctx.user_tier,
        github_connected=agent_ctx.github_connected,
        nosana_connected=agent_ctx.nosana_connected,
    )
    await emit_event(
        EventType.COMPUTE_TIER_SELECTED,
        workflow_id=workflow_id,
        data={
            "tier": backend.tier.value,
            "user_tier": agent_ctx.user_tier,
            "capabilities": ["compile", "test"],
        },
        message=f"Compute tier selected: {backend.tier.value}",
    )

    # Create tracking issue in GitLab
    if fm:
        issue = fm.gl.create_issue(
            title=f"Adaptive workflow: {workflow_id}",
            description=f"Requirements:\n{requirements}\n\nThis workflow uses adaptive orchestration with feedback loops.",
            labels=["reagent", "orchestration", "adaptive"],
        )
        state.gitlab_issue = issue

    feedback_loops = []
    max_iterations = 20  # Prevent infinite loops
    iteration = 0

    while state.current_stage != WorkflowStage.COMPLETED.value and iteration < max_iterations:
        iteration += 1
        stage = state.current_stage

        # Emit stage start event
        await emit_event(
            EventType.STAGE_START,
            workflow_id=workflow_id,
            stage=stage,
            data={"iteration": iteration},
            message=f"Starting stage: {stage} (iteration {iteration})",
        )

        orchestrator_router.app.note(
            f"Iteration {iteration}: Executing stage {stage}",
            tags=["orchestration", "iteration"]
        )

        try:
            # Execute current stage (pass context to AI-calling stages)
            ctx_dict = agent_ctx.to_dict()
            if stage == WorkflowStage.IDEATION.value:
                result = await _execute_ideation(state, fm, workflow_id, ctx_dict)
            elif stage == WorkflowStage.CODING.value:
                result = await _execute_coding(state, fm, workflow_id, ctx_dict)
            elif stage == WorkflowStage.TESTING.value:
                result = await _execute_testing(state, fm, workflow_id)
            elif stage == WorkflowStage.AUDITING.value:
                result = await _execute_auditing(state, fm, workflow_id, ctx_dict)
            elif stage == WorkflowStage.DEPLOYMENT.value:
                result = await _execute_deployment(state, fm, workflow_id)
            elif stage == WorkflowStage.MONITORING.value:
                result = await _execute_monitoring(state, fm, workflow_id, ctx_dict)
                state.current_stage = WorkflowStage.COMPLETED.value
                break
            else:
                break

            # Store result
            state.stage_results[stage] = result

            # Accumulate context from stage result
            if result.success:
                agent_ctx.add_entry(ContextSource.STAGE_OUTPUT, f"Stage {stage} completed", stage=stage)
            else:
                agent_ctx.set_recovery_context(result.error or "Unknown error", stage)

            if result.success:
                if stage not in state.stages_completed:
                    state.stages_completed.append(stage)
                state.retry_counts[stage] = 0

                # Emit stage complete event
                await emit_event(
                    EventType.STAGE_COMPLETE,
                    workflow_id=workflow_id,
                    stage=stage,
                    data={"success": True},
                    message=f"Stage {stage} completed successfully",
                )
            else:
                # Increment retry count
                state.retry_counts[stage] = state.retry_counts.get(stage, 0) + 1

                # Emit stage error event
                await emit_event(
                    EventType.STAGE_ERROR,
                    workflow_id=workflow_id,
                    stage=stage,
                    data={"error": result.error, "retry_count": state.retry_counts[stage]},
                    message=f"Stage {stage} failed: {result.error}",
                )

            # AI decides next stage
            decision = await decide_next_stage(
                current_stage=stage,
                stage_result=result.model_dump(),
                workflow_state={
                    "stages_completed": state.stages_completed,
                    "retry_counts": state.retry_counts,
                    "requirements": state.requirements
                }
            )

            # Emit decision event
            await emit_event(
                EventType.DECISION_MADE,
                workflow_id=workflow_id,
                stage=stage,
                data={
                    "next_stage": decision.get("next_stage"),
                    "reason": decision.get("reason"),
                    "feedback_needed": decision.get("feedback_needed"),
                },
                message=f"Decision: proceed to {decision.get('next_stage')}",
            )

            next_stage = decision.get("next_stage")
            is_feedback = decision.get("feedback_needed", False)

            if is_feedback:
                feedback_loops.append({
                    "from": stage,
                    "to": next_stage,
                    "reason": decision.get("reason"),
                    "iteration": iteration
                })

                # Emit feedback loop event
                await emit_event(
                    EventType.FEEDBACK_LOOP,
                    workflow_id=workflow_id,
                    stage=stage,
                    data={"from": stage, "to": next_stage, "reason": decision.get("reason")},
                    message=f"Feedback loop: {stage} -> {next_stage}",
                )

                if fm and state.gitlab_issue:
                    fm.gl.add_issue_note(
                        state.gitlab_issue["iid"],
                        f"Feedback loop: {stage} -> {next_stage}\nReason: {decision.get('reason')}"
                    )

            # Check if we should stop
            if next_stage == "failed" or state.retry_counts.get(stage, 0) >= state.max_retries:
                state.status = "failed"
                state.current_stage = WorkflowStage.FAILED.value
                break

            state.current_stage = next_stage

        except Exception as e:
            orchestrator_router.app.note(
                f"Error in stage {stage}: {str(e)}",
                tags=["orchestration", "error"]
            )

            # Emit stage error event
            await emit_event(
                EventType.STAGE_ERROR,
                workflow_id=workflow_id,
                stage=stage,
                data={"error": str(e), "exception": True},
                message=f"Exception in stage {stage}: {str(e)}",
            )

            state.status = "failed"
            state.current_stage = WorkflowStage.FAILED.value
            break

    # Final status
    if state.current_stage == WorkflowStage.COMPLETED.value:
        state.status = "completed"
        await emit_event(
            EventType.WORKFLOW_COMPLETE,
            workflow_id=workflow_id,
            data={"stages_completed": state.stages_completed},
            message=f"Workflow {workflow_id} completed successfully",
        )
    elif state.current_stage == WorkflowStage.FAILED.value:
        state.status = "failed"
        await emit_event(
            EventType.WORKFLOW_FAILED,
            workflow_id=workflow_id,
            data={"failed_at": state.current_stage, "retry_counts": state.retry_counts},
            message=f"Workflow {workflow_id} failed",
        )

    result = OrchestrationResult(
        workflow_id=workflow_id,
        stages_completed=state.stages_completed,
        current_stage=state.current_stage,
        status=state.status,
        outputs={k: v.output for k, v in state.stage_results.items()},
        gitlab_issue=state.gitlab_issue,
        feedback_loops=feedback_loops
    )

    orchestrator_router.app.note(
        f"Workflow {workflow_id} completed with {len(feedback_loops)} feedback loops",
        tags=["orchestration", "workflow", "completed"]
    )

    return result.model_dump()


# Stage execution functions with error handling

async def _execute_ideation(state: WorkflowState, fm: Optional[FileManager], workflow_id: str = "", context: dict | None = None) -> StageResult:
    """Execute ideation stage."""
    try:
        # Get context from previous attempts if any
        recovery = ""
        if WorkflowStage.CODING.value in state.stage_results:
            coding_result = state.stage_results[WorkflowStage.CODING.value]
            if not coding_result.success:
                recovery = f"\nPrevious coding attempt failed: {coding_result.error}\nPlease refine the specification."

        kwargs = {"requirements": state.requirements + recovery}
        if context:
            kwargs["context"] = context

        spec = await orchestrator_router.app.call(
            f"{orchestrator_router.app.node_id}.ideation_generate_contract_spec",
            **kwargs,
        )
        
        if fm and state.gitlab_issue:
            fm.gl.add_issue_note(
                state.gitlab_issue["iid"],
                f"✓ Ideation complete: {spec.get('name', 'Contract')}"
            )
        
        return StageResult(
            stage=WorkflowStage.IDEATION.value,
            success=True,
            output=spec,
            next_stage=WorkflowStage.CODING.value
        )
    except Exception as e:
        return StageResult(
            stage=WorkflowStage.IDEATION.value,
            success=False,
            output={},
            error=str(e),
            next_stage=WorkflowStage.IDEATION.value  # Retry
        )


async def _execute_coding(state: WorkflowState, fm: Optional[FileManager], workflow_id: str = "", context: dict | None = None) -> StageResult:
    """Execute coding stage."""
    try:
        spec = state.stage_results.get(WorkflowStage.IDEATION.value)
        if not spec or not spec.success:
            return StageResult(
                stage=WorkflowStage.CODING.value,
                success=False,
                output={},
                error="No valid specification from ideation",
                next_stage=WorkflowStage.IDEATION.value  # Go back
            )

        # Get feedback from testing if available
        spec_data = spec.output
        if WorkflowStage.TESTING.value in state.stage_results:
            test_result = state.stage_results[WorkflowStage.TESTING.value]
            if not test_result.success:
                spec_data["test_feedback"] = test_result.error

        kwargs = {"spec": spec_data}
        if context:
            kwargs["context"] = context

        code = await orchestrator_router.app.call(
            f"{orchestrator_router.app.node_id}.coding_generate_contract_code",
            **kwargs,
        )
        
        if fm and state.gitlab_issue:
            fm.gl.add_issue_note(
                state.gitlab_issue["iid"],
                f"✓ Coding complete: {len(code.get('solidity_code', ''))} characters"
            )
        
        return StageResult(
            stage=WorkflowStage.CODING.value,
            success=True,
            output=code,
            next_stage=WorkflowStage.TESTING.value
        )
    except Exception as e:
        return StageResult(
            stage=WorkflowStage.CODING.value,
            success=False,
            output={},
            error=str(e),
            next_stage=WorkflowStage.IDEATION.value  # May need better spec
        )


async def _execute_testing(state: WorkflowState, fm: Optional[FileManager], workflow_id: str = "") -> StageResult:
    """Execute testing stage."""
    try:
        code_result = state.stage_results.get(WorkflowStage.CODING.value)
        if not code_result or not code_result.success:
            return StageResult(
                stage=WorkflowStage.TESTING.value,
                success=False,
                output={},
                error="No valid code from coding stage",
                next_stage=WorkflowStage.CODING.value
            )

        spec = state.stage_results[WorkflowStage.IDEATION.value].output
        contract_path = f"contracts/{spec.get('name', 'Contract')}.sol"
        
        test_results = await orchestrator_router.app.call(
            f"{orchestrator_router.app.node_id}.testing_run_comprehensive_tests",
            contract_path=contract_path,
        )
        
        passed = test_results.get("passed", False)
        
        if fm and state.gitlab_issue:
            fm.gl.add_issue_note(
                state.gitlab_issue["iid"],
                f"{'✓' if passed else '✗'} Testing: {'PASSED' if passed else 'FAILED'}"
            )
        
        if not passed:
            return StageResult(
                stage=WorkflowStage.TESTING.value,
                success=False,
                output=test_results,
                error=f"Tests failed: {test_results.get('failures', [])}",
                next_stage=WorkflowStage.CODING.value  # Go back to fix code
            )
        
        return StageResult(
            stage=WorkflowStage.TESTING.value,
            success=True,
            output=test_results,
            next_stage=WorkflowStage.AUDITING.value
        )
    except Exception as e:
        return StageResult(
            stage=WorkflowStage.TESTING.value,
            success=False,
            output={},
            error=str(e),
            next_stage=WorkflowStage.CODING.value
        )


async def _execute_auditing(state: WorkflowState, fm: Optional[FileManager], workflow_id: str = "", context: dict | None = None) -> StageResult:
    """Execute auditing stage."""
    try:
        code_result = state.stage_results[WorkflowStage.CODING.value]
        spec = state.stage_results[WorkflowStage.IDEATION.value].output
        contract_path = f"contracts/{spec.get('name', 'Contract')}.sol"

        kwargs = {
            "contract_code": code_result.output.get("solidity_code", ""),
            "contract_path": contract_path,
        }
        if context:
            kwargs["context"] = context

        audit = await orchestrator_router.app.call(
            f"{orchestrator_router.app.node_id}.auditing_comprehensive_audit",
            **kwargs,
        )
        
        risk_level = audit.get("overall_risk", "unknown")
        
        if fm and state.gitlab_issue:
            fm.gl.add_issue_note(
                state.gitlab_issue["iid"],
                f"✓ Audit complete: Risk level {risk_level}"
            )
        
        # High risk should go back to coding
        if risk_level in ["high", "critical"]:
            return StageResult(
                stage=WorkflowStage.AUDITING.value,
                success=False,
                output=audit,
                error=f"High risk issues found: {audit.get('issues', [])}",
                next_stage=WorkflowStage.CODING.value
            )
        
        return StageResult(
            stage=WorkflowStage.AUDITING.value,
            success=True,
            output=audit,
            next_stage=WorkflowStage.DEPLOYMENT.value
        )
    except Exception as e:
        return StageResult(
            stage=WorkflowStage.AUDITING.value,
            success=False,
            output={},
            error=str(e),
            next_stage=WorkflowStage.AUDITING.value  # Retry audit
        )


async def _execute_deployment(state: WorkflowState, fm: Optional[FileManager], workflow_id: str = "") -> StageResult:
    """Execute deployment stage."""
    try:
        spec = state.stage_results[WorkflowStage.IDEATION.value].output
        contract_path = f"contracts/{spec.get('name', 'Contract')}.sol"
        
        deployment = await orchestrator_router.app.call(
            f"{orchestrator_router.app.node_id}.deployment_deploy_contract",
            contract_path=contract_path,
        )
        
        if not deployment.get("success", False):
            return StageResult(
                stage=WorkflowStage.DEPLOYMENT.value,
                success=False,
                output=deployment,
                error=deployment.get("error", "Deployment failed"),
                next_stage=WorkflowStage.CODING.value  # May need code fixes
            )
        
        if fm and state.gitlab_issue:
            fm.gl.add_issue_note(
                state.gitlab_issue["iid"],
                f"✓ Deployed to {deployment.get('network')} at {deployment.get('contract_address')}"
            )
        
        return StageResult(
            stage=WorkflowStage.DEPLOYMENT.value,
            success=True,
            output=deployment,
            next_stage=WorkflowStage.MONITORING.value
        )
    except Exception as e:
        return StageResult(
            stage=WorkflowStage.DEPLOYMENT.value,
            success=False,
            output={},
            error=str(e),
            next_stage=WorkflowStage.DEPLOYMENT.value  # Retry deployment
        )


async def _execute_monitoring(state: WorkflowState, fm: Optional[FileManager], workflow_id: str = "", context: dict | None = None) -> StageResult:
    """Execute monitoring stage."""
    try:
        deployment_result = state.stage_results[WorkflowStage.DEPLOYMENT.value]

        kwargs = {
            "contract_address": deployment_result.output.get("contract_address", ""),
        }
        if context:
            kwargs["context"] = context

        monitor = await orchestrator_router.app.call(
            f"{orchestrator_router.app.node_id}.monitoring_monitor_contract",
            **kwargs,
        )
        
        if fm and state.gitlab_issue:
            fm.gl.add_issue_note(
                state.gitlab_issue["iid"],
                f"✓ Monitoring started for {deployment_result.output.get('contract_address')}"
            )
        
        return StageResult(
            stage=WorkflowStage.MONITORING.value,
            success=True,
            output=monitor,
            next_stage=WorkflowStage.COMPLETED.value
        )
    except Exception as e:
        return StageResult(
            stage=WorkflowStage.MONITORING.value,
            success=False,
            output={},
            error=str(e),
            next_stage=WorkflowStage.MONITORING.value
        )


@orchestrator_router.reasoner(tags=["ai", "coordination"])
async def orchestrate_contract_development(requirements: str) -> dict:
    """
    Original linear orchestration (kept for backward compatibility).
    For adaptive orchestration with feedback loops, use orchestrate_contract_development_adaptive.
    """
    return await orchestrate_contract_development_adaptive(requirements)


@orchestrator_router.skill(tags=["status", "query"])
def get_workflow_status(workflow_id: str, issue_iid: int | None = None) -> dict:
    """
    Get status of a specific workflow from memory or GitLab issue.
    """
    # Check in-memory state first
    if workflow_id in _workflow_states:
        state = _workflow_states[workflow_id]
        return {
            "workflow_id": workflow_id,
            "status": state.status,
            "current_stage": state.current_stage,
            "stages_completed": state.stages_completed,
            "retry_counts": state.retry_counts,
        }
    
    # Fallback to GitLab
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
        "note": "Workflow not found in memory. Provide issue_iid for GitLab lookup.",
    }


@orchestrator_router.skill(tags=["retry", "error-handling"])
def retry_failed_stage(workflow_id: str, stage: str) -> dict:
    """
    Manually retry a failed stage in the workflow.
    """
    if workflow_id not in _workflow_states:
        return {
            "success": False,
            "error": "Workflow not found"
        }
    
    state = _workflow_states[workflow_id]
    state.current_stage = stage
    state.retry_counts[stage] = 0  # Reset retry count
    
    return {
        "workflow_id": workflow_id,
        "stage": stage,
        "status": "retry_initiated",
        "note": "Stage reset. Call orchestrate_contract_development_adaptive to continue."
    }


@orchestrator_router.skill(tags=["state", "management"])
def list_active_workflows() -> dict:
    """
    List all active workflows in memory.
    """
    workflows = []
    for wf_id, state in _workflow_states.items():
        workflows.append({
            "workflow_id": wf_id,
            "status": state.status,
            "current_stage": state.current_stage,
            "stages_completed": len(state.stages_completed),
            "requirements": state.requirements[:100] + "..." if len(state.requirements) > 100 else state.requirements
        })
    
    return {
        "total_workflows": len(workflows),
        "workflows": workflows
    }

# Made with Bob


# Interactive Orchestration with Questions
# ========================================

@orchestrator_router.reasoner(tags=["ai", "coordination", "interactive"])
async def orchestrate_contract_development_interactive(
    workflow_id: str,
    requirements: str,
    mode: str = "orchestrate"
) -> dict:
    """
    Interactive orchestration with user questions and real-time feedback.
    Uses WebSocket for bidirectional communication.
    
    Args:
        workflow_id: Unique workflow ID
        requirements: User requirements
        mode: Execution mode (orchestrate, plan, code)
        
    Returns:
        Orchestration result dictionary
    """
    from questions import get_question_manager, QuestionType
    from events import get_event_bus, EventType, WorkflowEvent
    
    qm = get_question_manager()
    eb = get_event_bus()
    fm = _get_fm()

    # Initialize workflow state
    state = WorkflowState(
        workflow_id=workflow_id,
        requirements=requirements,
        current_stage=WorkflowStage.IDEATION.value
    )
    _workflow_states[workflow_id] = state

    # Emit workflow started event
    await eb.emit(WorkflowEvent(
        event_type=EventType.WORKFLOW_START,
        workflow_id=workflow_id,
        message="Interactive workflow started"
    ))

    # Create tracking issue in GitLab
    if fm:
        issue = fm.gl.create_issue(
            title=f"Interactive workflow: {workflow_id}",
            description=f"Requirements:\n{requirements}\n\nMode: {mode}",
            labels=["reagent", "interactive"],
        )
        state.gitlab_issue = issue

    feedback_loops = []
    max_iterations = 20
    iteration = 0

    while state.current_stage != WorkflowStage.COMPLETED.value and iteration < max_iterations:
        iteration += 1
        stage = state.current_stage
        
        # Emit stage started
        await eb.emit(WorkflowEvent(
            event_type=EventType.STAGE_START,
            workflow_id=workflow_id,
            stage=stage,
            message=f"Starting {stage} stage (iteration {iteration})"
        ))

        try:
            # Execute current stage with questions
            if stage == WorkflowStage.IDEATION.value:
                result = await _execute_ideation_interactive(state, fm, qm, eb)
            elif stage == WorkflowStage.CODING.value:
                result = await _execute_coding_interactive(state, fm, qm, eb)
            elif stage == WorkflowStage.TESTING.value:
                result = await _execute_testing(state, fm, workflow_id)
            elif stage == WorkflowStage.AUDITING.value:
                result = await _execute_auditing(state, fm, workflow_id)
            elif stage == WorkflowStage.DEPLOYMENT.value:
                result = await _execute_deployment_interactive(state, fm, qm, eb)
            elif stage == WorkflowStage.MONITORING.value:
                result = await _execute_monitoring(state, fm)
                state.current_stage = WorkflowStage.COMPLETED.value
                break
            else:
                break

            # Store result
            state.stage_results[stage] = result
            
            # Emit stage complete
            await eb.emit(WorkflowEvent(
                event_type=EventType.STAGE_COMPLETE if result.success else EventType.STAGE_ERROR,
                workflow_id=workflow_id,
                stage=stage,
                data=result.model_dump(),
                message=f"{'Completed' if result.success else 'Failed'} {stage} stage"
            ))
            
            if result.success:
                if stage not in state.stages_completed:
                    state.stages_completed.append(stage)
                state.retry_counts[stage] = 0
            else:
                state.retry_counts[stage] = state.retry_counts.get(stage, 0) + 1

            # AI decides next stage
            decision = await decide_next_stage(
                current_stage=stage,
                stage_result=result.model_dump(),
                workflow_state={
                    "stages_completed": state.stages_completed,
                    "retry_counts": state.retry_counts,
                    "requirements": state.requirements
                }
            )

            next_stage = decision.get("next_stage")
            is_feedback = decision.get("feedback_needed", False)
            
            if is_feedback:
                feedback_loops.append({
                    "from": stage,
                    "to": next_stage,
                    "reason": decision.get("reason"),
                    "iteration": iteration
                })
                
                await eb.emit(WorkflowEvent(
                    event_type=EventType.FEEDBACK_LOOP,
                    workflow_id=workflow_id,
                    stage=stage,
                    data={"from": stage, "to": next_stage, "reason": decision.get("reason")},
                    message=f"Feedback loop: {stage} → {next_stage}"
                ))
                
                if fm and state.gitlab_issue:
                    fm.gl.add_issue_note(
                        state.gitlab_issue["iid"],
                        f"🔄 Feedback loop: {stage} → {next_stage}\nReason: {decision.get('reason')}"
                    )

            # Check if we should stop
            if next_stage == "failed" or state.retry_counts.get(stage, 0) >= state.max_retries:
                state.status = "failed"
                state.current_stage = WorkflowStage.FAILED.value
                break

            state.current_stage = next_stage

        except Exception as e:
            await eb.emit(WorkflowEvent(
                event_type=EventType.ERROR,
                workflow_id=workflow_id,
                stage=stage,
                data={"error": str(e)},
                message=f"Error in stage {stage}: {str(e)}"
            ))
            state.status = "failed"
            state.current_stage = WorkflowStage.FAILED.value
            break

    # Final status
    if state.current_stage == WorkflowStage.COMPLETED.value:
        state.status = "completed"
    elif state.current_stage == WorkflowStage.FAILED.value:
        state.status = "failed"

    # Emit workflow complete
    await eb.emit(WorkflowEvent(
        event_type=EventType.WORKFLOW_COMPLETE if state.status == "completed" else EventType.WORKFLOW_FAILED,
        workflow_id=workflow_id,
        data={"status": state.status, "feedback_loops": len(feedback_loops)},
        message=f"Workflow {state.status}"
    ))

    result = OrchestrationResult(
        workflow_id=workflow_id,
        stages_completed=state.stages_completed,
        current_stage=state.current_stage,
        status=state.status,
        outputs={k: v.output for k, v in state.stage_results.items()},
        gitlab_issue=state.gitlab_issue,
        feedback_loops=feedback_loops
    )

    return result.model_dump()


# Interactive stage execution functions
# ======================================

async def _execute_ideation_interactive(
    state: WorkflowState,
    fm: Optional[FileManager],
    qm,  # QuestionManager
    eb   # EventBus
) -> StageResult:
    """Execute ideation stage with user questions."""
    from questions import QuestionType
    from events import EventType, WorkflowEvent
    
    try:
        # Ask user about token type
        token_type = await qm.ask_question(
            workflow_id=state.workflow_id,
            stage="ideation",
            question="What type of token do you want to create?",
            question_type=QuestionType.MULTIPLE_CHOICE,
            options=["ERC-20", "ERC-721 (NFT)", "ERC-1155 (Multi-token)", "Custom"],
            default="ERC-20",
            timeout=300
        )
        
        # Ask about features
        features = await qm.ask_question(
            workflow_id=state.workflow_id,
            stage="ideation",
            question="What features should the token have? (comma-separated, e.g., mintable,burnable,pausable)",
            question_type=QuestionType.TEXT,
            default="mintable,burnable",
            timeout=300
        )
        
        # Ask about blockchain
        blockchain = await qm.ask_question(
            workflow_id=state.workflow_id,
            stage="ideation",
            question="Which blockchain should this be deployed to?",
            question_type=QuestionType.MULTIPLE_CHOICE,
            options=["Ethereum", "Polygon", "BSC", "Arbitrum", "Optimism"],
            default="Ethereum",
            timeout=300
        )
        
        # Generate spec with user input
        enhanced_requirements = f"""{state.requirements}

User Specifications:
- Token Type: {token_type}
- Features: {features}
- Target Blockchain: {blockchain}
"""
        
        spec = await orchestrator_router.app.call(
            f"{orchestrator_router.app.node_id}.ideation_generate_contract_spec",
            requirements=enhanced_requirements,
        )
        
        if fm and state.gitlab_issue:
            fm.gl.add_issue_note(
                state.gitlab_issue["iid"],
                f"✓ Ideation complete: {spec.get('name', 'Contract')}\nType: {token_type}\nFeatures: {features}"
            )
        
        return StageResult(
            stage=WorkflowStage.IDEATION.value,
            success=True,
            output=spec,
            next_stage=WorkflowStage.CODING.value
        )
    except Exception as e:
        return StageResult(
            stage=WorkflowStage.IDEATION.value,
            success=False,
            output={},
            error=str(e),
            next_stage=WorkflowStage.IDEATION.value
        )


async def _execute_coding_interactive(
    state: WorkflowState,
    fm: Optional[FileManager],
    qm,  # QuestionManager
    eb   # EventBus
) -> StageResult:
    """Execute coding stage with optional user input."""
    from questions import QuestionType
    
    try:
        spec = state.stage_results.get(WorkflowStage.IDEATION.value)
        if not spec or not spec.success:
            return StageResult(
                stage=WorkflowStage.CODING.value,
                success=False,
                output={},
                error="No valid specification from ideation",
                next_stage=WorkflowStage.IDEATION.value
            )

        # Ask if user wants to add any specific requirements
        additional_req = await qm.ask_question(
            workflow_id=state.workflow_id,
            stage="coding",
            question="Any additional coding requirements or constraints? (press Enter to skip)",
            question_type=QuestionType.TEXT,
            default="",
            timeout=180,
            required=False
        )
        
        context = spec.output
        if additional_req:
            context["additional_requirements"] = additional_req
        
        # Get feedback from testing if available
        if WorkflowStage.TESTING.value in state.stage_results:
            test_result = state.stage_results[WorkflowStage.TESTING.value]
            if not test_result.success:
                context["test_feedback"] = test_result.error

        code = await orchestrator_router.app.call(
            f"{orchestrator_router.app.node_id}.coding_generate_contract_code",
            spec=context,
        )
        
        if fm and state.gitlab_issue:
            fm.gl.add_issue_note(
                state.gitlab_issue["iid"],
                f"✓ Coding complete: {len(code.get('solidity_code', ''))} characters"
            )
        
        return StageResult(
            stage=WorkflowStage.CODING.value,
            success=True,
            output=code,
            next_stage=WorkflowStage.TESTING.value
        )
    except Exception as e:
        return StageResult(
            stage=WorkflowStage.CODING.value,
            success=False,
            output={},
            error=str(e),
            next_stage=WorkflowStage.IDEATION.value
        )


async def _execute_deployment_interactive(
    state: WorkflowState,
    fm: Optional[FileManager],
    qm,  # QuestionManager
    eb   # EventBus
) -> StageResult:
    """Execute deployment stage with user confirmation."""
    from questions import QuestionType
    
    try:
        spec = state.stage_results[WorkflowStage.IDEATION.value].output
        contract_path = f"contracts/{spec.get('name', 'Contract')}.sol"
        
        # Ask for deployment confirmation
        confirm = await qm.ask_question(
            workflow_id=state.workflow_id,
            stage="deployment",
            question="Ready to deploy? This will deploy to testnet.",
            question_type=QuestionType.YES_NO,
            options=["yes", "no"],
            default="yes",
            timeout=300
        )
        
        if confirm.lower() not in ["yes", "y", "true"]:
            return StageResult(
                stage=WorkflowStage.DEPLOYMENT.value,
                success=False,
                output={"skipped": True},
                error="User cancelled deployment",
                next_stage=WorkflowStage.DEPLOYMENT.value
            )
        
        deployment = await orchestrator_router.app.call(
            f"{orchestrator_router.app.node_id}.deployment_deploy_contract",
            contract_path=contract_path,
        )
        
        if not deployment.get("success", False):
            return StageResult(
                stage=WorkflowStage.DEPLOYMENT.value,
                success=False,
                output=deployment,
                error=deployment.get("error", "Deployment failed"),
                next_stage=WorkflowStage.CODING.value
            )
        
        if fm and state.gitlab_issue:
            fm.gl.add_issue_note(
                state.gitlab_issue["iid"],
                f"✓ Deployed to {deployment.get('network')} at {deployment.get('contract_address')}"
            )
        
        return StageResult(
            stage=WorkflowStage.DEPLOYMENT.value,
            success=True,
            output=deployment,
            next_stage=WorkflowStage.MONITORING.value
        )
    except Exception as e:
        return StageResult(
            stage=WorkflowStage.DEPLOYMENT.value,
            success=False,
            output={},
            error=str(e),
            next_stage=WorkflowStage.DEPLOYMENT.value
        )

# Made with Bob
