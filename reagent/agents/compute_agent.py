"""Compute backend selection agent.

Replaces the hardcoded if/else tree in compute.py:326-369.
Agent evaluates backend availability, cost, performance, and task requirements
to make an informed routing decision.
"""

import logging
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BackendInfo(BaseModel):
    """Metadata about a compute backend."""
    name: str
    available: bool
    cost_per_minute: float = 0.0
    relative_speed: float = 1.0  # 1.0 = baseline local
    capabilities: list[str] = Field(default_factory=list)


class ComputeSelectionDecision(BaseModel):
    """Agent decision for compute backend selection."""
    backend: str = Field(description="Selected backend: 'codespaces', 'nosana', or 'local'")
    reason: str = Field(description="Why this backend was chosen")
    estimated_cost_usd: float = Field(default=0.0)
    fallback: str = Field(default="local", description="Fallback if selected backend is unavailable")


def get_backend_info(compute_router) -> dict[str, BackendInfo]:
    """Get metadata for all available compute backends."""
    backends = {}

    # Codespaces
    cs = compute_router._codespaces_backend
    if cs:
        backends["codespaces"] = BackendInfo(
            name="codespaces",
            available=True,  # Already connected
            cost_per_minute=0.0,  # Free tier
            relative_speed=1.0,
            capabilities=[c.value for c in cs.capabilities],
        )

    # Nosana
    ns = compute_router._nosana_backend
    if ns:
        backends["nosana"] = BackendInfo(
            name="nosana",
            available=True,
            cost_per_minute=0.02,  # Approximate
            relative_speed=2.0,  # GPU accelerated
            capabilities=[c.value for c in ns.capabilities],
        )

    # Local (always available)
    lb = compute_router._local_backend
    backends["local"] = BackendInfo(
        name="local",
        available=True,
        cost_per_minute=0.0,
        relative_speed=1.0,
        capabilities=[c.value for c in lb.capabilities],
    )

    return backends


def select_compute_backend(
    compute_router,
    required_capabilities: set,
    user_tier: str = "free",
    github_connected: bool = False,
    nosana_connected: bool = False,
) -> Any:
    """
    Select compute backend using agent evaluation instead of if/else tree.

    Evaluates:
    - Backend availability and capabilities
    - Task requirements (GPU, compile, test, deploy)
    - User tier and cost constraints
    - Performance needs

    Args:
        compute_router: ComputeRouter instance
        required_capabilities: Set of ComputeCapability needed
        user_tier: "free" or "premium"
        github_connected: Whether Codespaces is available
        nosana_connected: Whether Nosana is configured

    Returns:
        Selected ComputeBackend instance.
    """
    caps = {c.value for c in required_capabilities} if required_capabilities else set()
    needs_gpu = "gpu" in caps
    backends = get_backend_info(compute_router)

    decision = _evaluate_selection(backends, caps, needs_gpu, user_tier)

    logger.info(
        f"Compute selection: {decision.backend} "
        f"(reason: {decision.reason}, cost: ${decision.estimated_cost_usd:.4f})"
    )

    # Return the selected backend
    if decision.backend == "codespaces" and compute_router._codespaces_backend:
        return compute_router._codespaces_backend
    elif decision.backend == "nosana" and compute_router._nosana_backend:
        return compute_router._nosana_backend

    # Fallback chain
    if decision.fallback == "codespaces" and compute_router._codespaces_backend:
        return compute_router._codespaces_backend
    elif decision.fallback == "nosana" and compute_router._nosana_backend:
        return compute_router._nosana_backend

    return compute_router._local_backend


def _evaluate_selection(
    backends: dict[str, BackendInfo],
    caps: set[str],
    needs_gpu: bool,
    user_tier: str,
) -> ComputeSelectionDecision:
    """Evaluate backend selection using agent logic."""

    # GPU tasks require Nosana
    if needs_gpu:
        if "nosana" in backends and backends["nosana"].available:
            return ComputeSelectionDecision(
                backend="nosana",
                reason="GPU capability required, Nosana available",
                estimated_cost_usd=0.02,
                fallback="local",
            )
        return ComputeSelectionDecision(
            backend="local",
            reason="GPU required but no GPU backend available",
            fallback="local",
        )

    # Free tier: prefer zero-cost backends
    if user_tier == "free":
        if "codespaces" in backends and backends["codespaces"].available:
            return ComputeSelectionDecision(
                backend="codespaces",
                reason="Free tier, Codespaces available (zero cost)",
                estimated_cost_usd=0.0,
                fallback="nosana",
            )
        if "nosana" in backends and backends["nosana"].available:
            return ComputeSelectionDecision(
                backend="nosana",
                reason="Free tier, Codespaces unavailable, using Nosana",
                estimated_cost_usd=0.02,
                fallback="local",
            )

    # Premium tier: prefer fastest available
    if user_tier == "premium":
        if "nosana" in backends and backends["nosana"].available:
            return ComputeSelectionDecision(
                backend="nosana",
                reason="Premium tier, Nosana available (fastest)",
                estimated_cost_usd=0.02,
                fallback="codespaces",
            )

    # Default fallback
    if "codespaces" in backends and backends["codespaces"].available:
        return ComputeSelectionDecision(
            backend="codespaces",
            reason="Default: Codespaces available",
            fallback="local",
        )

    return ComputeSelectionDecision(
        backend="local",
        reason="Default: falling back to local",
        fallback="local",
    )
