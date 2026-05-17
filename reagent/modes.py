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

    # Code mode settings
    code_target_blockchain: str = "ethereum"
    code_include_tests: bool = True
    code_include_deployment: bool = False

    # Compute tier preference
    preferred_compute_tier: str = "codespaces"  # codespaces | nosana
