"""File structure agent.

Replaces hardcoded file paths (`contracts/{name}.sol`, `tests/{name}_test.sol`)
with a tool that determines appropriate file structure based on project type.
"""

from pydantic import BaseModel, Field
from typing import Optional


# Project structure templates
_PROJECT_TEMPLATES = {
    "foundry": {
        "contract": "src/{name}.sol",
        "test": "test/{name}.t.sol",
        "script": "script/{name}.s.sol",
        "audit": "reports/{name}_audit.json",
        "branch_prefix": "feat",
    },
    "hardhat": {
        "contract": "contracts/{name}.sol",
        "test": "test/{name}.test.ts",
        "script": "scripts/deploy-{name}.ts",
        "audit": "reports/{name}_audit.json",
        "branch_prefix": "feature",
    },
    "truffle": {
        "contract": "contracts/{name}.sol",
        "test": "test/{name}.js",
        "script": "migrations/2_deploy_{name}.js",
        "audit": "reports/{name}_audit.json",
        "branch_prefix": "feature",
    },
    "brownie": {
        "contract": "contracts/{name}.sol",
        "test": "tests/test_{name}.py",
        "script": "scripts/deploy_{name}.py",
        "audit": "reports/{name}_audit.json",
        "branch_prefix": "feature",
    },
}


class FileStructure(BaseModel):
    """Recommended file structure for a project."""
    framework: str = Field(description="Detected or recommended framework")
    contract_path: str = Field(description="Path pattern for contracts")
    test_path: str = Field(description="Path pattern for tests")
    script_path: str = Field(description="Path pattern for deployment scripts")
    audit_path: str = Field(description="Path pattern for audit reports")
    branch_prefix: str = Field(description="Recommended branch naming prefix")


def determine_file_structure(
    project_type: str = "foundry",
    contract_name: str = "Contract",
) -> FileStructure:
    """
    Determine file structure based on project framework.

    Args:
        project_type: "foundry", "hardhat", "truffle", "brownie"
        contract_name: Name of the contract (used for path generation)

    Returns:
        FileStructure with paths for contracts, tests, scripts, and reports.
    """
    template = _PROJECT_TEMPLATES.get(project_type, _PROJECT_TEMPLATES["foundry"])
    name_safe = contract_name.lower().replace(" ", "_")

    return FileStructure(
        framework=project_type,
        contract_path=template["contract"].format(name=contract_name),
        test_path=template["test"].format(name=name_safe),
        script_path=template["script"].format(name=name_safe),
        audit_path=template["audit"].format(name=name_safe),
        branch_prefix=template["branch_prefix"],
    )


def generate_branch_name(
    stage: str,
    contract_name: str,
    prefix: Optional[str] = None,
) -> str:
    """
    Generate a branch name based on stage and contract.

    Args:
        stage: Workflow stage (ideation, coding, testing, etc.)
        contract_name: Contract name
        prefix: Custom prefix (overrides project default)

    Returns:
        Formatted branch name.
    """
    pfx = prefix or "reagent"
    name = contract_name.lower().replace(" ", "-").replace("_", "-")
    return f"{pfx}/{stage}-{name}"


def classify_file(file_path: str) -> str:
    """
    Classify a file based on its path and extension.

    Args:
        file_path: Path to the file

    Returns:
        Category: "contract", "test", "script", "config", "report", "unknown"
    """
    path_lower = file_path.lower()

    if path_lower.startswith("test/") or path_lower.startswith("tests/"):
        return "test"
    if path_lower.startswith("script/") or path_lower.startswith("scripts/"):
        return "script"
    if path_lower.startswith("src/"):
        return "contract"
    if path_lower.startswith("contracts/"):
        return "contract"
    if path_lower.endswith((".t.sol", ".test.ts", ".test.js", ".spec.ts")):
        return "test"
    if path_lower.endswith(".s.sol"):
        return "script"
    if path_lower.endswith((".json", ".md")) and "audit" in path_lower:
        return "report"
    if path_lower.endswith((".sol",)):
        return "contract"
    if path_lower.endswith((".ts", ".js", ".py")):
        return "script"
    if path_lower.endswith((".toml", ".yaml", ".yml", ".json")):
        return "config"

    return "unknown"
