from agentfield import AgentRouter
from pydantic import BaseModel, Field
import subprocess
import os
import json

from file_manager import FileManager
from context import AgentContext

# Router for auditing and analysis
auditing_router = AgentRouter(prefix="auditing", tags=["auditing", "security"])

_fm: FileManager | None = None


def _get_fm() -> FileManager | None:
    global _fm
    if _fm is None and os.getenv("GITLAB_TOKEN"):
        _fm = FileManager()
    return _fm


class AuditReport(BaseModel):
    """Structured output for audit report."""
    overall_risk: str = Field(description="low/medium/high/critical")
    vulnerabilities: list[dict] = Field(description="Found vulnerabilities")
    recommendations: list[str] = Field(description="Security recommendations")
    compliance_score: int = Field(ge=0, le=100, description="Compliance score")


@auditing_router.reasoner(tags=["ai", "z-ai", "analysis"])
async def comprehensive_audit(contract_code: str, contract_path: str, branch: str = "main", context: dict | None = None) -> dict:
    """
    Perform comprehensive security audit using AI and static analysis.
    Reads contract from GitLab if contract_code is empty but contract_path is given.
    Writes audit report to the repository.

    Args:
        contract_code: Solidity source code to audit
        contract_path: Path to contract file in repository
        branch: Git branch to read from
        context: Structured AgentContext dict for mind building across stages
    """
    fm = _get_fm()

    # Read contract from GitLab if code not provided
    if not contract_code and fm and contract_path:
        contract_code = fm.get_file_from_branch(contract_path, branch)
        if not contract_code:
            return {"error": f"Could not read {contract_path} from branch {branch}"}

    # Build prompt with context injection
    user_prompt = f"Contract code:\n{contract_code}\n\nPerform security audit and provide detailed report."
    if context:
        ctx = AgentContext.from_dict(context) if isinstance(context, dict) else context
        context_prompt = ctx.build_injection_prompt()
        if context_prompt:
            user_prompt += f"\n\n{context_prompt}"

    # Use AI for audit
    audit = await auditing_router.ai(
        system="You are a senior smart contract auditor. Analyze code for vulnerabilities, gas optimization, and best practices.",
        user=user_prompt,
        schema=AuditReport,
    )

    # Run static analysis tools (e.g., Slither)
    static_issues = []
    if fm and contract_path:
        # Try Slither if available locally
        try:
            result = subprocess.run(
                ["slither", contract_path],
                capture_output=True, text=True, timeout=60
            )
            if result.stdout.strip():
                static_issues = [{"type": "static_slither", "issue": result.stdout[:500]}]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            static_issues = [{"type": "static", "issue": "Slither not available — skipping static analysis"}]

    # Combine AI and static analysis
    audit.vulnerabilities.extend(static_issues)

    # Write audit report to GitLab
    gitlab_ref = None
    if fm:
        report_path = f"audits/{contract_path.replace('.sol', '')}_audit.json"
        report_content = json.dumps(audit.model_dump(), indent=2)
        fm.create_file(
            file_path=report_path,
            content=report_content,
            branch=branch,
            commit_message=f"audit: {contract_path} — risk: {audit.overall_risk}",
        )
        gitlab_ref = {"report_path": report_path, "branch": branch}

    auditing_router.app.note(
        f"Audit completed with risk level: {audit.overall_risk}",
        tags=["auditing", "security"],
    )

    return {**audit.model_dump(), "gitlab_ref": gitlab_ref}


@auditing_router.skill(tags=["static-analysis", "slither"])
def run_slither_analysis(contract_path: str) -> dict:
    """
    Run Slither static analysis.
    """
    try:
        result = subprocess.run(
            ["slither", contract_path],
            capture_output=True, text=True
        )
        return {
            "tool": "slither",
            "output": result.stdout,
            "errors": result.stderr,
            "exit_code": result.returncode
        }
    except Exception as e:
        return {"error": str(e)}


@auditing_router.skill(tags=["compliance", "erc"])
def check_erc_compliance(code: str, standards: list[str]) -> dict:
    """
    Check compliance with ERC standards.
    """
    compliance = {}
    for standard in standards:
        if standard == "ERC-20":
            compliance[standard] = "transfer" in code and "balanceOf" in code
        elif standard == "ERC-721":
            compliance[standard] = "ownerOf" in code and "transferFrom" in code
        else:
            compliance[standard] = False

    return {
        "standards_checked": standards,
        "compliance": compliance,
        "score": sum(compliance.values()) / len(standards) * 100 if standards else 0
    }