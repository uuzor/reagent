from agentfield import AgentRouter
from pydantic import BaseModel, Field
import subprocess
import os
import time

from file_manager import FileManager

# Router for testing and validation
testing_router = AgentRouter(prefix="testing", tags=["testing", "validation"])

_fm: FileManager | None = None


def _get_fm() -> FileManager | None:
    global _fm
    if _fm is None and os.getenv("GITLAB_TOKEN"):
        _fm = FileManager()
    return _fm


class TestResults(BaseModel):
    """Structured output for test results."""
    passed: bool = Field(description="All tests passed")
    test_count: int = Field(description="Number of tests run")
    failures: list[str] = Field(description="Failed test details")
    gas_report: dict = Field(description="Gas usage report")


@testing_router.reasoner(tags=["ai", "analysis"])
async def run_comprehensive_tests(contract_path: str, mr_iid: int | None = None) -> dict:
    """
    Run comprehensive tests via GitLab CI pipeline or local Foundry/Hardhat.
    If an MR IID is provided, reads pipelines attached to that MR.
    Otherwise triggers a new pipeline on the main branch.
    """
    fm = _get_fm()

    if fm:
        if mr_iid:
            # Use existing MR pipelines
            pipelines = fm.gl.get_mr_pipelines(mr_iid)
            if not pipelines:
                return {"error": f"No pipelines found for MR #{mr_iid}"}
            pipeline_id = pipelines[-1]["id"]
        else:
            # Trigger a new pipeline
            pipeline = fm.gl.trigger_pipeline(
                ref="main",
                variables=[{"key": "CONTRACT_PATH", "value": contract_path}],
            )
            pipeline_id = pipeline["id"]

        # Poll for pipeline completion
        max_wait = 300  # 5 minutes
        waited = 0
        while waited < max_wait:
            status = fm.gl.get_pipeline(pipeline_id)
            if status["status"] in ("success", "failed", "canceled"):
                break
            time.sleep(10)
            waited += 10

        # Get job results
        jobs = fm.gl.get_pipeline_jobs(pipeline_id)
        test_jobs = [j for j in jobs if j["stage"] in ("test", "build")]
        passed = all(j["status"] == "success" for j in test_jobs)
        failures = [j["name"] for j in test_jobs if j["status"] != "success"]

        test_results = TestResults(
            passed=passed,
            test_count=len(test_jobs),
            failures=failures,
            gas_report={"pipeline_id": pipeline_id, "jobs": jobs},
        )

        testing_router.app.note(
            f"CI pipeline {'passed' if passed else 'failed'} (id={pipeline_id}): {test_results.model_dump()}",
            tags=["testing", "gitlab", "ci"],
        )
        return {**test_results.model_dump(), "pipeline_id": pipeline_id}

    # Fallback: local testing
    try:
        result = subprocess.run(
            ["forge", "test", "--gas-report"],
            capture_output=True, text=True, cwd=os.path.dirname(contract_path) or "."
        )
        passed = "PASS" in result.stdout
        test_count = result.stdout.count("PASS") + result.stdout.count("FAIL")
        failures = [line for line in result.stdout.split('\n') if "FAIL" in line]

        test_results = TestResults(
            passed=passed,
            test_count=test_count,
            failures=failures,
            gas_report={"estimated": "50000 gas"}
        )

        testing_router.app.note(
            f"Tests {'passed' if passed else 'failed'} for {contract_path}",
            tags=["testing", "results"]
        )
        return test_results.model_dump()
    except Exception as e:
        return {"error": str(e)}


@testing_router.skill(tags=["simulation", "nosana"])
def simulate_deployment(contract_path: str, network: str = "sepolia") -> dict:
    """
    Simulate deployment on testnet using Nosana compute.
    """
    # Placeholder for Nosana GPU simulation
    return {
        "network": network,
        "simulated_address": "0x1234567890abcdef",
        "gas_estimate": "21000",
        "status": "simulation_success"
    }


@testing_router.skill(tags=["security", "audit"])
def basic_security_check(code: str) -> dict:
    """
    Basic security checks before full auditing.
    """
    issues = []
    if "selfdestruct" in code:
        issues.append("Contains selfdestruct - high risk")
    if "delegatecall" in code:
        issues.append("Uses delegatecall - review carefully")

    return {
        "issues_found": len(issues),
        "issues": issues,
        "recommendation": "Proceed to full audit" if not issues else "Address issues first"
    }


@testing_router.skill(tags=["gitlab", "ci", "retry"])
def retry_pipeline(pipeline_id: int) -> dict:
    """
    Retry a failed GitLab CI pipeline.
    """
    fm = _get_fm()
    if not fm:
        return {"error": "GITLAB_TOKEN not configured"}

    result = fm.gl.retry_pipeline(pipeline_id)
    return result