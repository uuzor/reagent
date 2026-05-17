"""
Plan Mode Router — AI analysis and planning without execution.
Produces a detailed plan that the user can review and approve before proceeding.
"""
import os
import sys
from pathlib import Path

from agentfield import AgentRouter
from pydantic import BaseModel, Field
from typing import Optional, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from context import AgentContext
from events import emit_event, EventType

plan_router = AgentRouter(prefix="plan", tags=["planning", "analysis"])


class PlanOutput(BaseModel):
    """Structured output for plan mode."""
    requirements_analysis: str = Field(description="Analysis of the requirements")
    proposed_architecture: str = Field(description="Proposed contract architecture")
    stage_plan: List[dict] = Field(description="Planned stages with descriptions")
    risk_assessment: str = Field(description="Risk assessment")
    cost_estimate: Optional[dict] = Field(default=None, description="Estimated cost")
    recommendations: List[str] = Field(description="Key recommendations")


@plan_router.reasoner(tags=["ai", "planning"])
async def analyze_and_plan(
    requirements: str,
    context: dict | None = None,
    plan_depth: str = "detailed",
) -> dict:
    """
    Analyze requirements and produce a detailed plan without executing.

    Uses AI to:
    1. Analyze requirements and identify contract components
    2. Propose architecture (ERC standards, security patterns)
    3. Break down into pipeline stages with descriptions
    4. Assess risks and estimate costs
    5. Generate recommendations

    Returns a PlanOutput that can be reviewed/approved by user.
    """
    # Build prompt with context injection
    user_prompt = f"Requirements:\n{requirements}\n\n"
    user_prompt += f"Plan depth: {plan_depth}\n\n"
    user_prompt += """Analyze these requirements and produce a detailed development plan.

Consider:
1. What ERC standards are needed?
2. What security patterns should be applied?
3. What are the main contract components?
4. What risks exist?
5. What is the recommended stage-by-stage approach?

Produce a structured plan with architecture, stage breakdown, risk assessment, and recommendations."""

    if context:
        ctx = AgentContext.from_dict(context) if isinstance(context, dict) else context
        context_prompt = ctx.build_injection_prompt()
        if context_prompt:
            user_prompt += f"\n\n{context_prompt}"

    plan = await plan_router.ai(
        system="""You are a senior smart contract architect and planner.
Analyze requirements and produce detailed, actionable development plans.
Focus on security best practices, gas optimization, and proven patterns.
Be specific about ERC standards, architecture decisions, and risk mitigation.""",
        user=user_prompt,
        schema=PlanOutput,
    )

    # Emit plan event
    await emit_event(
        EventType.WORKFLOW_COMPLETE,
        workflow_id=context.get("workflow_id", "plan") if context else "plan",
        data={"mode": "plan", "plan_depth": plan_depth},
        message="Plan analysis completed",
    )

    plan_router.app.note(
        f"Plan generated: {len(plan.stage_plan)} stages, risk={plan.risk_assessment}",
        tags=["planning", "plan"],
    )

    return plan.model_dump()


@plan_router.skill(tags=["plan", "info"])
def get_plan_template(plan_depth: str = "detailed") -> dict:
    """Get a plan template showing what a plan output looks like."""
    return {
        "plan_depth": plan_depth,
        "template": PlanOutput(
            requirements_analysis="Analysis of the user's requirements",
            proposed_architecture="Proposed contract architecture and patterns",
            stage_plan=[
                {"stage": "ideation", "description": "Generate contract specification"},
                {"stage": "coding", "description": "Implement Solidity contract"},
                {"stage": "testing", "description": "Run comprehensive test suite"},
                {"stage": "auditing", "description": "Security audit and analysis"},
                {"stage": "deployment", "description": "Deploy to target network"},
                {"stage": "monitoring", "description": "Monitor deployed contract"},
            ],
            risk_assessment="Risk level assessment",
            cost_estimate={"gas_estimate": "TBD", "compute_tier": "codespaces"},
            recommendations=["Follow security best practices", "Use OpenZeppelin libraries"],
        ).model_dump(),
    }
