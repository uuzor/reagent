from agentfield import AgentRouter
from pydantic import BaseModel, Field
import os
import subprocess
from typing import Optional, List, Any, Dict

from file_manager import FileManager
from context import AgentContext

# Router for coding and code generation
coding_router = AgentRouter(prefix="coding", tags=["coding", "generation"])

_fm: FileManager | None = None


def _get_fm() -> FileManager | None:
    global _fm
    if _fm is None and os.getenv("GITLAB_TOKEN"):
        _fm = FileManager()
    return _fm


class ContractCodeInput(BaseModel):
    """Contract specification input for code generation."""
    name: str = Field(default="Contract", description="Contract name")
    description: str = Field(default="", description="Contract description")
    features: List[str] = Field(default_factory=list, description="Key features")
    blockchain: str = Field(default="ethereum", description="Target blockchain")
    standards: List[str] = Field(default_factory=list, description="ERC standards")
    additional_requirements: Optional[str] = Field(default=None, description="Additional requirements")
    test_feedback: Optional[str] = Field(default=None, description="Feedback from testing")
    market_research: Optional[Dict[str, Any]] = Field(default=None, description="Market research data")


class ContractCode(BaseModel):
    """Structured output for generated contract code."""
    solidity_code: str = Field(description="Solidity contract code")
    test_code: str = Field(description="Unit test code")
    deployment_script: str = Field(description="Deployment script")


def _parse_spec_string(text: str) -> dict:
    """Parse a stringified Pydantic model into a dict.

    AgentField SDK stringifies Pydantic models in cross-agent calls,
    producing: "name='Foo' description='Bar' features=['a', 'b']"
    """
    result = {}
    import ast
    import re

    # Match key=value pairs where value can be quoted string or list
    pattern = r"(\w+)=((?:'(?:[^'\\]|\\.)*')|(?:\"(?:[^\"\\]|\\.)*\")|(?:\[[^\]]*\]))"
    for match in re.finditer(pattern, text):
        key = match.group(1)
        value_str = match.group(2)
        try:
            result[key] = ast.literal_eval(value_str)
        except (ValueError, SyntaxError):
            result[key] = value_str.strip("'\"")

    return result


@coding_router.reasoner(tags=["ai", "qwen", "qoder"])
async def generate_contract_code(
    spec: dict,
    recovery_context: str | None = None,
    context: dict | None = None,
) -> dict:
    """
    Generate smart contract code from specification using Qwen Cloud.
    Pushes code to a GitLab branch via FileManager and creates an MR.
    Falls back to local file write if FileManager is not available.

    Args:
        spec: Contract specification (dict or stringified model)
        recovery_context: Optional context from previous failed attempts to guide improvements
        context: Structured AgentContext dict for mind building across stages
    """
    fm = _get_fm()

    # Handle spec being either a dict or a stringified Pydantic model
    if isinstance(spec, str):
        # Parse stringified model: "name='Foo' description='Bar' features=['a', 'b']"
        spec_dict = _parse_spec_string(spec)
    elif hasattr(spec, 'model_dump'):
        spec_dict = spec.model_dump()
    elif isinstance(spec, dict):
        spec_dict = spec
    else:
        spec_dict = {}

    contract_name = spec_dict.get("name", "Contract")
    branch_name = f"reagent/{contract_name.lower().replace(' ', '-')}"

    # Build prompt with recovery context if provided
    prompt = f"""Contract Name: {spec_dict.get('name', 'Contract')}
Description: {spec_dict.get('description', '')}
Features: {', '.join(spec_dict.get('features', []))}
Blockchain: {spec_dict.get('blockchain', 'ethereum')}
Standards: {', '.join(spec_dict.get('standards', []))}"""

    if spec_dict.get('additional_requirements'):
        prompt += f"\nAdditional Requirements: {spec_dict['additional_requirements']}"
    if spec_dict.get('test_feedback'):
        prompt += f"\nTest Feedback: {spec_dict['test_feedback']}"

    prompt += "\n\nGenerate Solidity code, tests, and deployment script."

    if recovery_context:
        prompt += f"\n\nPrevious attempt had issues:\n{recovery_context}\nPlease address these issues in the new implementation."

    # Inject structured context (mind building)
    if context:
        ctx = AgentContext.from_dict(context) if isinstance(context, dict) else context
        context_prompt = ctx.build_injection_prompt()
        if context_prompt:
            prompt += f"\n\n{context_prompt}"

    # Use the dynamic prompt builder for code generation
    from agents.prompt_builder import build_system_prompt
    from agents.file_agent import determine_file_structure
    from agents.blockchain_agent import recommend_blockchain

    system_prompt = build_system_prompt(
        task_type="code",
        style_guide="detailed",
        security_level="high",
        library_pref="openzeppelin",
    )

    code = await coding_router.ai(
        system=system_prompt,
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
            description=f"Auto-generated contract: {spec_dict.get('name', 'Contract')}\n{spec_dict.get('description', '')}",
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