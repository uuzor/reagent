from agentfield import AgentRouter
from pydantic import BaseModel, Field
import json
import os
import re
import time
from typing import Optional, List, Dict, Any
from enum import Enum

from file_manager import FileManager
from events import get_event_bus, emit_event, EventType
from context import AgentContext, ContextSource

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




# ──────────────────────────────────────────────────────────────
# AI decision maker (used by interactive orchestrator)
# ──────────────────────────────────────────────────────────────

@orchestrator_router.reasoner(tags=["ai", "decision"])
async def decide_next_stage(
    current_stage: str,
    stage_result: Dict[str, Any],
    workflow_state: Dict[str, Any]
) -> dict:
    """AI-powered decision maker for workflow progression."""
    analysis = await orchestrator_router.ai(
        system="""You are a smart contract development workflow coordinator.
Analyze the stage result and decide the next action.

Rules:
1. If stage succeeded → proceed to next stage
2. If stage failed with fixable error → go back to appropriate stage
3. If stage failed after max retries → mark as failed

Return JSON with: next_stage, reason, feedback_needed, suggestions""",
        user=f"""Current Stage: {current_stage}
Stage Result: {stage_result}
Workflow State: {workflow_state}
What should we do next?""",
    )

    if hasattr(analysis, 'model_dump'):
        raw = analysis.model_dump()
    elif isinstance(analysis, dict):
        raw = analysis
    else:
        raw = {'text': str(analysis)}

    if isinstance(raw, dict):
        text = raw.get('text', '') or raw.get('content', '') or json.dumps(raw)
    else:
        text = str(raw)

    # Extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?\s*```', text)
    if json_match:
        text = json_match.group(1).strip()

    try:
        analysis_dict = json.loads(text)
    except json.JSONDecodeError:
        analysis_dict = {
            'next_stage': 'failed',
            'reason': text[:500],
            'feedback_needed': False,
            'suggestions': []
        }

    analysis_dict.setdefault('next_stage', 'failed')
    analysis_dict.setdefault('reason', '')
    analysis_dict.setdefault('feedback_needed', False)
    analysis_dict.setdefault('suggestions', [])

    return analysis_dict


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
        
        # Update state requirements to reflect user's actual choices
        # This prevents decide_next_stage from seeing a mismatch between
        # original requirements (e.g. "ERC-20") and the spec (e.g. "ERC-1155")
        state.requirements = enhanced_requirements
        
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


async def _execute_testing(state: WorkflowState, fm: Optional[FileManager], workflow_id: str = "") -> StageResult:
    """Execute testing stage."""
    try:
        spec = state.stage_results[WorkflowStage.IDEATION.value]
        spec_name = spec.output.get("name", "Contract")
        contract_path = f"contracts/{spec_name}.sol"

        kwargs = {"contract_path": contract_path}
        if state.gitlab_issue:
            kwargs["mr_iid"] = state.gitlab_issue.get("iid")

        test_results = await orchestrator_router.app.call(
            f"{orchestrator_router.app.node_id}.testing_run_comprehensive_tests",
            **kwargs,
        )

        if fm and state.gitlab_issue:
            fm.gl.add_issue_note(
                state.gitlab_issue["iid"],
                f"Test results: {json.dumps(test_results, indent=2)}"
            )

        return StageResult(
            stage=WorkflowStage.TESTING.value,
            success=test_results.get("success", False),
            output=test_results,
            next_stage=WorkflowStage.AUDITING.value if test_results.get("success") else WorkflowStage.CODING.value
        )
    except Exception as e:
        return StageResult(
            stage=WorkflowStage.TESTING.value,
            success=False,
            output={},
            error=str(e),
            next_stage=WorkflowStage.TESTING.value
        )


async def _execute_auditing(state: WorkflowState, fm: Optional[FileManager], workflow_id: str = "") -> StageResult:
    """Execute auditing stage."""
    try:
        spec = state.stage_results[WorkflowStage.IDEATION.value]
        spec_name = spec.output.get("name", "Contract")
        contract_path = f"contracts/{spec_name}.sol"

        audit = await orchestrator_router.app.call(
            f"{orchestrator_router.app.node_id}.auditing_perform_audit",
            contract_path=contract_path,
            contract_spec=spec.output,
        )

        if fm:
            audit_report = json.dumps(audit, indent=2)
            fm.write_file(f"audits/{spec_name}_audit.json", audit_report, branch="main")

        if fm and state.gitlab_issue:
            severity = audit.get("severity", "unknown")
            fm.gl.add_issue_note(
                state.gitlab_issue["iid"],
                f"Audit complete: severity={severity}"
            )

        return StageResult(
            stage=WorkflowStage.AUDITING.value,
            success=audit.get("risk_level") not in ("critical", "high"),
            output=audit,
            next_stage=WorkflowStage.DEPLOYMENT.value
        )
    except Exception as e:
        return StageResult(
            stage=WorkflowStage.AUDITING.value,
            success=False,
            output={},
            error=str(e),
            next_stage=WorkflowStage.AUDITING.value
        )


async def _execute_monitoring(state: WorkflowState, fm: Optional[FileManager], workflow_id: str = "") -> StageResult:
    """Execute monitoring stage."""
    try:
        deployment_result = state.stage_results[WorkflowStage.DEPLOYMENT.value]

        monitor = await orchestrator_router.app.call(
            f"{orchestrator_router.app.node_id}.monitoring_monitor_contract",
            contract_address=deployment_result.output.get("contract_address", ""),
        )

        if fm and state.gitlab_issue:
            fm.gl.add_issue_note(
                state.gitlab_issue["iid"],
                f"Monitoring started for {deployment_result.output.get('contract_address')}"
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


# ──────────────────────────────────────────────────────────────
# LangGraph-based orchestration (Phases 1-5: unified, persistent, observable)
# ──────────────────────────────────────────────────────────────

@orchestrator_router.reasoner(tags=["ai", "coordination", "langgraph"])
async def run_contract_workflow(
    requirements: str,
    mode: str = "orchestrate",
    context: dict | None = None,
    workflow_id: str | None = None,
) -> dict:
    """
    Unified LangGraph-based contract development workflow.

    Phase 4: Single graph entry point replaces 3 duplicate orchestration
    implementations (orchestrate_contract_development, _adaptive, _interactive).
    Mode dispatch selects the appropriate subgraph:
    - "plan" → analysis only
    - "code" → direct code generation
    - "orchestrate" → full pipeline with feedback loops

    Phase 5: Includes cost tracking, structured logging, and LangSmith tracing.

    Args:
        requirements: What to build
        mode: "plan", "code", or "orchestrate"
        context: Structured AgentContext for mind building
        workflow_id: Optional workflow ID (generated if not provided)

    Returns:
        OrchestrationResult-compatible dict with workflow outputs.
    """
    import uuid
    from context import AgentContext
    from graph.observability import (
        CostTrackingCallback,
        workflow_logger,
        log_stage_event,
        enable_langsmith_tracing,
        is_langsmith_enabled,
    )

    # Enable LangSmith if configured
    enable_langsmith_tracing()

    workflow_id = workflow_id or f"workflow_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    # Set entry point based on mode
    entry_stage = {"plan": "plan", "code": "code", "orchestrate": "ideation"}.get(mode, "orchestrate")

    graph = create_compiled_graph(mode=mode, persistent=True)

    # Build initial agent context
    agent_ctx = AgentContext(workflow_id=workflow_id)
    if context:
        agent_ctx = AgentContext.from_dict(context) if isinstance(context, dict) else context
    agent_ctx.add_entry(
        source=ContextSource.USER_INPUT,
        content=requirements,
        stage="init",
    )

    initial_state = {
        "workflow_id": workflow_id,
        "requirements": requirements,
        "mode": mode,
        "current_stage": entry_stage,
        "retry_counts": {},
        "stages_completed": [],
        "feedback_loops": [],
        "agent_context": agent_ctx.to_dict(),
        "stage_costs": {},
        "trace_id": str(uuid.uuid4()),
        "errors": [],
    }

    # Phase 5: Cost tracking
    cost_tracker = CostTrackingCallback(workflow_id=workflow_id)
    config = {
        "configurable": {"thread_id": workflow_id},
        "callbacks": [cost_tracker],
    }

    log_stage_event("start", workflow_id, mode, data={"mode": mode})

    # Execute graph (thread_id enables checkpointing/resume)
    try:
        final_state = await graph.ainvoke(initial_state, config=config)
    except Exception as e:
        log_stage_event("error", workflow_id, mode, error=str(e))
        raise

    # Check if workflow ended due to errors
    errors = final_state.get("errors", [])
    status = "failed" if errors else "completed"

    # Phase 5: Attach cost summary
    cost_summary = cost_tracker.get_summary()

    log_stage_event("complete", workflow_id, mode, data={
        "status": status,
        "stages_completed": final_state.get("stages_completed", []),
        "cost_usd": cost_summary["total_cost_usd"],
    })

    if is_langsmith_enabled():
        workflow_logger.info(
            f"LangSmith tracing active for {workflow_id}",
            extra={"workflow_id": workflow_id, "trace_url": f"https://smith.langchain.com/o/..." },
        )

    return {
        "workflow_id": workflow_id,
        "stages_completed": final_state.get("stages_completed", []),
        "current_stage": final_state.get("current_stage", "unknown"),
        "status": status,
        "outputs": {
            "spec": final_state.get("spec"),
            "contract_code": final_state.get("contract_code"),
            "test_results": final_state.get("test_results"),
            "audit_report": final_state.get("audit_report"),
            "deployment_result": final_state.get("deployment_result"),
            "monitoring_report": final_state.get("monitoring_report"),
        },
        "gitlab_issue": None,
        "feedback_loops": final_state.get("feedback_loops", []),
        "errors": errors,
        "cost_summary": cost_summary,  # Phase 5
    }


# ──────────────────────────────────────────────────────────────
# LangGraph imports (lazy to avoid circular deps at module load)
# ──────────────────────────────────────────────────────────────

def create_compiled_graph(mode: str = "orchestrate", persistent: bool = True):
    """Create compiled LangGraph with checkpointing.

    Args:
        mode: "plan", "code", or "orchestrate"
        persistent: If True, use SQLite for state persistence.
                    If False, use in-memory (for testing).
    """
    if persistent:
        from graph.graph import create_persistent_graph
        return create_persistent_graph(mode=mode)
    else:
        from graph.graph import create_default_graph
        return create_default_graph(mode=mode)


async def get_workflow_state(workflow_id: str) -> dict | None:
    """
    Get the current state of a workflow by ID.

    Uses LangGraph's checkpointer to retrieve the latest state.
    Returns None if workflow not found.
    """
    graph = create_compiled_graph()
    try:
        state = graph.get_state({"configurable": {"thread_id": workflow_id}})
        if state and state.values:
            return dict(state.values)
    except Exception:
        pass
    return None


async def resume_workflow(workflow_id: str, human_review: dict) -> dict:
    """
    Resume a paused workflow after human review.

    Args:
        workflow_id: The workflow to resume
        human_review: {"approved": bool, "comments": str}

    Returns:
        Updated workflow state or error.
    """
    graph = create_compiled_graph()

    # Check if workflow exists
    existing = await get_workflow_state(workflow_id)
    if not existing:
        return {"error": f"Workflow {workflow_id} not found"}

    # Resume with human review input
    final_state = await graph.ainvoke(
        {"human_review": human_review},
        config={"configurable": {"thread_id": workflow_id}},
    )

    errors = final_state.get("errors", [])
    return {
        "workflow_id": workflow_id,
        "stages_completed": final_state.get("stages_completed", []),
        "current_stage": final_state.get("current_stage", "unknown"),
        "status": "failed" if errors else "completed",
        "outputs": {
            "spec": final_state.get("spec"),
            "contract_code": final_state.get("contract_code"),
            "test_results": final_state.get("test_results"),
            "audit_report": final_state.get("audit_report"),
            "deployment_result": final_state.get("deployment_result"),
            "monitoring_report": final_state.get("monitoring_report"),
        },
        "feedback_loops": final_state.get("feedback_loops", []),
        "errors": errors,
    }
