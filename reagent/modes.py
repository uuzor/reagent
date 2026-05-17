"""
Mode Switching System
Defines the three execution modes for Reagent:
- Plan: AI analysis only, no execution
- Orchestrate: Full adaptive pipeline with feedback loops
- Code: Direct code generation, skip planning
"""
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class ExecutionMode(str, Enum):
    """Available execution modes."""
    PLAN = "plan"
    ORCHESTRATE = "orchestrate"
    CODE = "code"


class ModeConfig(BaseModel):
    """Configuration for each execution mode."""
    mode: ExecutionMode = ExecutionMode.ORCHESTRATE

    # Plan mode settings
    plan_depth: str = "detailed"  # summary | detailed | comprehensive

    # Orchestrate mode settings
    max_iterations: int = 20
    max_retries_per_stage: int = 3

    # Code mode settings — uses blockchain agent for recommendation
    code_target_blockchain: str = ""  # Empty = auto-recommend
    code_include_tests: bool = True
    code_include_deployment: bool = False

    # Compute tier preference
    preferred_compute_tier: str = "codespaces"  # codespaces | nosana

    def resolve_blockchain(self, use_case: str = "general") -> str:
        """Resolve target blockchain, using agent recommendation if not set."""
        if self.code_target_blockchain:
            return self.code_target_blockchain
        from agents.blockchain_agent import recommend_blockchain
        rec = recommend_blockchain(use_case=use_case)
        return rec.blockchain
