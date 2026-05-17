"""
Compute Router — AgentField router exposing compute tier selection and execution.
"""
import os
import sys
from pathlib import Path
from typing import Optional

from agentfield import AgentRouter

sys.path.insert(0, str(Path(__file__).parent.parent))

from compute import (
    ComputeRouter,
    ComputeTier,
    ComputeCapability,
    ComputeResult,
    CodespaceComputeBackend,
    NosanaComputeBackend,
    get_compute_router,
)

compute_router = AgentRouter(prefix="compute", tags=["compute", "infrastructure"])


@compute_router.skill(tags=["select", "tier"])
def select_compute_tier(
    task_type: str = "shell",
    requires_gpu: bool = False,
    user_tier: str = "free",
    github_connected: bool = False,
    nosana_connected: bool = False,
) -> dict:
    """Select the appropriate compute tier for a task.

    Args:
        task_type: Type of task (compile, test, deploy, shell)
        requires_gpu: Whether the task requires GPU
        user_tier: User's tier (free or premium)
        github_connected: Whether user has GitHub Codespaces connected
        nosana_connected: Whether Nosana is configured

    Returns:
        Selected tier and reason for selection
    """
    router = get_compute_router()

    cap_map = {
        "compile": {ComputeCapability.COMPILE},
        "test": {ComputeCapability.TEST},
        "deploy": {ComputeCapability.DEPLOY},
        "shell": {ComputeCapability.SHELL},
    }
    caps = cap_map.get(task_type, {ComputeCapability.SHELL})
    if requires_gpu:
        caps.add(ComputeCapability.GPU)

    backend = router.select_backend(
        required_capabilities=caps,
        user_tier=user_tier,
        github_connected=github_connected,
        nosana_connected=nosana_connected,
    )

    reason = _selection_reason(backend.tier, requires_gpu, user_tier, github_connected)

    return {
        "tier": backend.tier.value,
        "reason": reason,
        "capabilities": [c.value for c in caps],
    }


@compute_router.skill(tags=["execute", "command"])
async def execute_command(
    command: str,
    task_type: str = "shell",
    requires_gpu: bool = False,
    user_tier: str = "free",
    github_connected: bool = False,
    nosana_connected: bool = False,
    cwd: str = "/workspace",
    timeout: int = 300,
) -> dict:
    """Execute a command on the appropriate compute backend.

    Returns the execution result including stdout, stderr, and exit code.
    """
    router = get_compute_router()

    cap_map = {
        "compile": {ComputeCapability.COMPILE},
        "test": {ComputeCapability.TEST},
        "deploy": {ComputeCapability.DEPLOY},
        "shell": {ComputeCapability.SHELL},
    }
    caps = cap_map.get(task_type, {ComputeCapability.SHELL})
    if requires_gpu:
        caps.add(ComputeCapability.GPU)

    result = await router.execute(
        command=command,
        required_capabilities=caps,
        user_tier=user_tier,
        github_connected=github_connected,
        nosana_connected=nosana_connected,
        cwd=cwd,
        timeout=timeout,
    )
    return result.model_dump()


@compute_router.skill(tags=["status"])
def get_compute_status() -> dict:
    """Check available compute backends and their status."""
    router = get_compute_router()
    backends = {
        "codespaces": router._codespaces_backend is not None,
        "nosana": router._nosana_backend is not None,
        "local": True,
    }
    return {
        "available_backends": backends,
        "default_tier": "codespaces" if router._codespaces_backend else "local",
    }


def _selection_reason(tier: ComputeTier, gpu: bool, user_tier: str, github: bool) -> str:
    if gpu and tier == ComputeTier.NOSANA:
        return "GPU required — routed to Nosana"
    if user_tier == "free" and tier == ComputeTier.CODESPACES:
        return "Free tier with Codespaces connected — zero-cost execution"
    if user_tier == "premium" and tier == ComputeTier.NOSANA:
        return "Premium tier — routed to Nosana"
    if tier == ComputeTier.CODESPACES:
        return "Codespaces available — selected as default"
    return "Local fallback — no cloud backend available"
