"""Devcontainer config generator and codespace machine selector.

Replaces static devcontainer config and hardcoded machine types in
github_codespaces_full_client.py.
"""

from pydantic import BaseModel, Field
from typing import Optional

# Latest LTS versions
_LATEST_LTS = {
    "python": "3.12",
    "node": "20",
    "go": "1.22",
    "rust": "1.79",
}

# Machine types for GitHub Codespaces
_MACHINE_TYPES = {
    "basicLinux32gb": {"cpus": 4, "memory_gb": 32, "storage_gb": 256, "cost_per_hour": 0.18},
    "standardLinux32gb": {"cpus": 8, "memory_gb": 32, "storage_gb": 256, "cost_per_hour": 0.27},
    "standardLinux64gb": {"cpus": 8, "memory_gb": 64, "storage_gb": 512, "cost_per_hour": 0.45},
    "premiumLinux32gb": {"cpus": 16, "memory_gb": 32, "storage_gb": 256, "cost_per_hour": 0.54},
    "premiumLinux64gb": {"cpus": 16, "memory_gb": 64, "storage_gb": 512, "cost_per_hour": 0.90},
}


class DevcontainerConfig(BaseModel):
    """Generated devcontainer configuration."""
    image: str = Field(description="Docker base image")
    features: dict = Field(default_factory=dict, description="Dev container features")
    extensions: list[str] = Field(default_factory=list, description="VS Code extensions")
    forward_ports: list[int] = Field(default_factory=list, description="Ports to forward")
    post_create_command: str = Field(default="", description="Command to run after container creation")


def generate_devcontainer_config(
    project_type: str = "solidity",
    required_tools: Optional[list[str]] = None,
) -> DevcontainerConfig:
    """
    Generate a devcontainer configuration based on project type.

    Args:
        project_type: Type of project ("solidity", "python", "fullstack", "rust")
        required_tools: Additional tools needed

    Returns:
        DevcontainerConfig with appropriate image, features, and extensions.
    """
    tools = required_tools or []
    python_ver = _LATEST_LTS["python"]
    node_ver = _LATEST_LTS["node"]

    if project_type == "solidity":
        return DevcontainerConfig(
            image=f"mcr.microsoft.com/devcontainers/python:{python_ver}",
            features={
                f"ghcr.io/devcontainers/features/node:1": {"version": node_ver},
                "ghcr.io/devcontainers/features/rust:1": {},
            },
            extensions=[
                "NomicFoundation.hardhat-solidity",
                "tintinweb.solidity-visual-auditor",
                "ms-python.python",
            ],
            forward_ports=[8000, 3000],
            post_create_command="pip install -r requirements.txt 2>/dev/null || true",
        )

    elif project_type == "fullstack":
        return DevcontainerConfig(
            image=f"mcr.microsoft.com/devcontainers/python:{python_ver}",
            features={
                f"ghcr.io/devcontainers/features/node:1": {"version": node_ver},
            },
            extensions=[
                "dbaeumer.vscode-eslint",
                "esbenp.prettier-vscode",
                "ms-python.python",
            ],
            forward_ports=[8000, 3000, 5173],
            post_create_command="npm install && pip install -r requirements.txt 2>/dev/null || true",
        )

    elif project_type == "rust":
        return DevcontainerConfig(
            image=f"mcr.microsoft.com/devcontainers/rust:1",
            features={},
            extensions=[
                "rust-lang.rust-analyzer",
                "vadimcn.vscode-lldb",
            ],
            forward_ports=[8000],
            post_create_command="cargo build",
        )

    # Default Python
    return DevcontainerConfig(
        image=f"mcr.microsoft.com/devcontainers/python:{python_ver}",
        features={},
        extensions=["ms-python.python"],
        forward_ports=[8000],
    )


def select_codespace_machine(
    task_requirements: Optional[dict] = None,
    budget_per_hour: float = 1.0,
) -> str:
    """
    Select appropriate Codespace machine type based on task and budget.

    Args:
        task_requirements: Dict with optional keys: cpus, memory_gb, needs_gpu
        budget_per_hour: Maximum acceptable cost per hour in USD

    Returns:
        Machine type string.
    """
    reqs = task_requirements or {}
    needed_cpus = reqs.get("cpus", 4)
    needed_mem = reqs.get("memory_gb", 16)

    # Filter by budget and requirements
    candidates = []
    for name, specs in _MACHINE_TYPES.items():
        if specs["cost_per_hour"] > budget_per_hour:
            continue
        if specs["cpus"] >= needed_cpus and specs["memory_gb"] >= needed_mem:
            candidates.append((name, specs))

    if candidates:
        # Pick the cheapest that meets requirements
        candidates.sort(key=lambda x: x[1]["cost_per_hour"])
        return candidates[0][0]

    # Fallback: cheapest available
    fallback = min(_MACHINE_TYPES.items(), key=lambda x: x[1]["cost_per_hour"])
    return fallback[0]
