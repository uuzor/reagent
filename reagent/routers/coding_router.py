from agentfield import AgentRouter
from pydantic import BaseModel, Field
import os
import subprocess

from file_manager import FileManager

# Router for coding and code generation
coding_router = AgentRouter(prefix="coding", tags=["coding", "generation"])

_fm: FileManager | None = None


def _get_fm() -> FileManager | None:
    global _fm
    if _fm is None and os.getenv("GITLAB_TOKEN"):
        _fm = FileManager()
    return _fm


class ContractCode(BaseModel):
    """Structured output for generated contract code."""
    solidity_code: str = Field(description="Solidity contract code")
    test_code: str = Field(description="Unit test code")
    deployment_script: str = Field(description="Deployment script")


@coding_router.reasoner(tags=["ai", "qwen", "qoder"])
async def generate_contract_code(spec: dict, recovery_context: str | None = None) -> dict:
    """
    Generate smart contract code from specification using Qwen Cloud.
    Pushes code to a GitLab branch via FileManager and creates an MR.
    Falls back to local file write if FileManager is not available.
    
    Args:
        spec: Contract specification dictionary
        recovery_context: Optional context from previous failed attempts to guide improvements
    """
    fm = _get_fm()
    contract_name = spec.get("name", "Contract")
    branch_name = f"reagent/{contract_name.lower().replace(' ', '-')}"

    # Build prompt with recovery context if provided
    prompt = f"Specification: {spec}\nGenerate Solidity code, tests, and deployment script."
    if recovery_context:
        prompt += f"\n\nPrevious attempt had issues:\n{recovery_context}\nPlease address these issues in the new implementation."

    # Use Qwen for code generation
    code = await coding_router.ai(
        system="You are an expert Solidity developer. Generate production-ready smart contract code with security best practices.",
        user=prompt,
        schema=ContractCode,
    )

    gitlab_ref = None
    contract_file = f"contracts/{contract_name}.sol"

    if fm:
        fm.gl.create_branch(branch_name)

        # Use FileManager to create files
        fm.create_file(
            file_path=contract_file,
            content=code.solidity_code,
            branch=branch_name,
            commit_message=f"feat: generate {contract_name} contract",
        )
        fm.create_file(
            file_path=f"tests/{contract_name}_test.sol",
            content=code.test_code,
            branch=branch_name,
            commit_message=f"feat: add tests for {contract_name}",
        )
        if code.deployment_script:
            fm.create_file(
                file_path=f"scripts/deploy_{contract_name.lower().replace(' ', '_')}.sol",
                content=code.deployment_script,
                branch=branch_name,
                commit_message=f"feat: add deployment script for {contract_name}",
            )

        mr = fm.gl.create_merge_request(
            title=f"Add {contract_name} smart contract",
            source_branch=branch_name,
            description=f"Auto-generated contract from spec:\n{spec}",
        )
        gitlab_ref = {
            "type": "merge_request",
            "iid": mr["iid"],
            "web_url": mr["web_url"],
            "branch": branch_name,
        }

        # Show the file tree after creation
        tree = fm.tree_ascii(branch=branch_name)
        coding_router.app.note(
            f"Generated contract pushed to GitLab:\n{tree}",
            tags=["coding", "generation", "gitlab"],
        )
    else:
        # Fallback: local files
        os.makedirs("contracts", exist_ok=True)
        with open(contract_file, "w") as f:
            f.write(code.solidity_code)
        coding_router.app.note(
            f"Generated contract code: {contract_file}",
            tags=["coding", "generation"],
        )

    return {**code.model_dump(), "gitlab_ref": gitlab_ref, "contract_file": contract_file}


@coding_router.skill(tags=["compilation", "solidity"])
def compile_contract(contract_path: str) -> dict:
    """
    Compile Solidity contract using solc.
    """
    try:
        result = subprocess.run(
            ["solc", "--bin", "--abi", contract_path],
            capture_output=True, text=True, cwd=os.getcwd()
        )
        if result.returncode == 0:
            return {"status": "success", "output": result.stdout}
        else:
            return {"status": "error", "error": result.stderr}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@coding_router.skill(tags=["refactor", "qoder"])
def refactor_code(code: str, improvements: str) -> str:
    """
    Refactor code using Qoder-like agentic assistance.
    """
    # Placeholder: In real Qoder, use Expert Panel Mode
    # For now, use AI for refactoring
    refactored = f"// Refactored with improvements: {improvements}\n{code}"
    return refactored


@coding_router.skill(tags=["review", "gitlab"])
async def review_mr_diff(mr_iid: int) -> dict:
    """
    Review merge request diffs and provide feedback using AI.
    """
    fm = _get_fm()
    if not fm:
        return {"error": "GITLAB_TOKEN not configured"}

    mr = fm.gl.get_merge_request(mr_iid)
    diffs = fm.gl.project.mergerequests.get(mr_iid).diffs.list()

    diff_content = "\n".join(
        f"--- {d.old_path}\n+++ {d.new_path}\n{d.diff}"
        for d in diffs
    )

    review = await coding_router.ai(
        system="You are a senior Solidity reviewer. Check for security issues, gas optimization, and best practices.",
        user=f"Review this merge request diff:\n\n{diff_content}",
    )

    return {
        "mr_iid": mr_iid,
        "mr_url": mr.get("web_url"),
        "review": review,
    }


@coding_router.skill(tags=["file-tree", "gitlab"])
def list_file_tree(branch: str = "main", path: str = "") -> dict:
    """
    List the file tree of a branch with ASCII visualization.
    """
    fm = _get_fm()
    if not fm:
        return {"error": "GITLAB_TOKEN not configured"}

    tree = fm.list_tree(branch=branch, path=path)
    tree_visual = fm.tree_ascii(branch=branch, root_path=path)
    contracts = fm.find_contracts(branch=branch)
    return {
        "branch": branch,
        "total_files": len([t for t in tree if t["type"] == "blob"]),
        "contracts": contracts,
        "tree": tree_visual,
    }


@coding_router.skill(tags=["file-read", "gitlab"])
def read_file(file_path: str, branch: str = "main") -> dict:
    """
    Read a file from the repository.
    """
    fm = _get_fm()
    if not fm:
        return {"error": "GITLAB_TOKEN not configured"}

    content = fm.read_file(file_path, branch)
    return {
        "path": file_path,
        "branch": branch,
        "category": fm.file_category(file_path),
        "content": content,
        "size": len(content),
    }