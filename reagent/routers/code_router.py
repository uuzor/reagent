"""
Code Mode Router — Direct code generation without orchestration.
Skips planning and adaptive feedback loops, generates code directly.
"""
import os
import sys
from pathlib import Path

from agentfield import AgentRouter
from pydantic import BaseModel, Field
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from context import AgentContext
from events import emit_event, EventType

code_router = AgentRouter(prefix="code", tags=["direct", "generation"])


class DirectCodeOutput(BaseModel):
    """Structured output for direct code generation."""
    contract_name: str = Field(description="Name of the contract")
    solidity_code: str = Field(description="Generated Solidity code")
    test_code: str = Field(default="", description="Unit test code")
    deployment_script: str = Field(default="", description="Deployment script")
    explanation: str = Field(description="Brief explanation of the implementation")


@code_router.reasoner(tags=["ai", "generation", "direct"])
async def direct_code_generation(
    requirements: str,
    context: dict | None = None,
    target_blockchain: str = "ethereum",
    include_tests: bool = True,
    include_deployment: bool = False,
) -> dict:
    """
    Generate code directly from requirements, skipping orchestration.

    Single AI call that produces contract code, tests, and deployment script.
    No feedback loops, no stage progression — just direct generation.

    Args:
        requirements: What to build
        context: Structured AgentContext for mind building
        target_blockchain: Target blockchain (ethereum, polygon, arbitrum)
        include_tests: Whether to generate test code
        include_deployment: Whether to generate deployment script
    """
    user_prompt = f"""Requirements: {requirements}
Target Blockchain: {target_blockchain}
Include Tests: {include_tests}
Include Deployment: {include_deployment}

Generate production-ready Solidity smart contract code.
Use OpenZeppelin libraries where appropriate.
Follow security best practices and gas optimization patterns."""

    if context:
        ctx = AgentContext.from_dict(context) if isinstance(context, dict) else context
        context_prompt = ctx.build_injection_prompt()
        if context_prompt:
            user_prompt += f"\n\n{context_prompt}"

    result = await code_router.ai(
        system="""You are an expert Solidity developer. Generate production-ready smart contract code.
Follow security best practices, use OpenZeppelin, optimize for gas.
Generate clean, well-commented, auditable code.""",
        user=user_prompt,
        schema=DirectCodeOutput,
    )

    # Emit completion event
    await emit_event(
        EventType.WORKFLOW_COMPLETE,
        workflow_id=context.get("workflow_id", "code") if context else "code",
        data={"mode": "code", "contract_name": result.contract_name},
        message=f"Direct code generation completed: {result.contract_name}",
    )

    code_router.app.note(
        f"Direct code generated: {result.contract_name} ({len(result.solidity_code)} chars)",
        tags=["code", "direct"],
    )

    return result.model_dump()
