from agentfield import AgentRouter
from pydantic import BaseModel, Field
import os
import sys
from pathlib import Path
import time

# Add parent directory to path to import nosana_client
sys.path.insert(0, str(Path(__file__).parent.parent))
from nosana_client import NosanaClient

# Router for Nosana compute operations
nosana_router = AgentRouter(prefix="nosana", tags=["compute", "nosana", "gpu"])

# Initialize Nosana client
_nosana: NosanaClient | None = None


def _get_nosana() -> NosanaClient:
    """Get or create Nosana client instance."""
    global _nosana
    if _nosana is None:
        _nosana = NosanaClient()
    return _nosana


class DeploymentInfo(BaseModel):
    """Structured output for deployment."""
    deployment_id: str = Field(description="Deployment identifier")
    status: str = Field(description="Deployment status")
    name: str = Field(description="Deployment name")
    endpoints: list = Field(default=[], description="Exposed endpoints")
    created_at: str = Field(description="Creation timestamp")


class CompilationResult(BaseModel):
    """Structured output for contract compilation."""
    deployment_id: str = Field(description="Deployment ID")
    contract_name: str = Field(description="Contract name")
    success: bool = Field(description="Compilation success")
    status: str = Field(description="Deployment status")
    solc_version: str = Field(default="0.8.20", description="Solidity version")


@nosana_router.reasoner(tags=["ai", "compilation"])
async def compile_contract_on_nosana(
    contract_code: str,
    contract_name: str = "Contract",
    solc_version: str = "0.8.20"
) -> dict:
    """
    Compile Solidity contract using Nosana decentralized compute.
    Creates a deployment with solc compiler.
    """
    nosana = _get_nosana()
    
    # Compile using Nosana
    result = nosana.compile_solidity(
        contract_code, 
        contract_name, 
        solc_version=solc_version,
        timeout_minutes=10
    )
    
    # Use AI to analyze compilation result
    analysis = await nosana_router.ai(
        system="You are a Solidity compilation expert. Analyze this compilation result.",
        user=f"Contract: {contract_name}\nResult: {result}\nProvide insights on the compilation.",
    )
    
    nosana_router.app.note(
        f"Compiled {contract_name} on Nosana compute (deployment: {result.get('deployment_id')})",
        tags=["nosana", "compilation"]
    )
    
    return {
        **result,
        "ai_analysis": analysis
    }


@nosana_router.skill(tags=["deployment", "create"])
def create_deployment(
    name: str,
    image: str = "ubuntu:22.04",
    commands: list[str] = None,
    timeout_minutes: int = 30,
    gpu_required: bool = False,
    expose_port: int = None
) -> dict:
    """
    Create a deployment on Nosana network.
    Returns deployment details and endpoints.
    """
    nosana = _get_nosana()
    
    # Build job definition
    job_def = nosana.build_container_job(
        image=image,
        commands=commands or ["echo 'Deployment ready'"],
        gpu=gpu_required,
        expose_port=expose_port
    )
    
    # Create deployment
    deployment = nosana.create_deployment(
        name=name,
        job_definition=job_def,
        timeout=timeout_minutes,
        strategy="SIMPLE"
    )
    
    if not deployment.get("success"):
        return deployment
    
    # Auto-start deployment
    deployment_id = deployment["id"]
    start_result = nosana.start_deployment(deployment_id)
    
    return {
        "deployment_id": deployment_id,
        "name": name,
        "status": start_result.get("status", "STARTING"),
        "image": image,
        "timeout_minutes": timeout_minutes,
        "endpoints": deployment.get("endpoints", []),
        "created_at": deployment.get("created_at", ""),
        "note": "Deployment created and started"
    }


@nosana_router.skill(tags=["deployment", "status"])
def get_deployment_status(deployment_id: str) -> dict:
    """
    Get status of a Nosana deployment.
    """
    nosana = _get_nosana()
    
    deployment = nosana.get_deployment(deployment_id)
    
    return {
        "deployment_id": deployment_id,
        "status": deployment.get("status", "unknown"),
        "name": deployment.get("name", ""),
        "endpoints": deployment.get("endpoints", []),
        "active_jobs": deployment.get("active_jobs", 0),
        "created_at": deployment.get("created_at", ""),
        "updated_at": deployment.get("updated_at", "")
    }


@nosana_router.skill(tags=["deployment", "control"])
def stop_deployment(deployment_id: str) -> dict:
    """
    Stop a running Nosana deployment.
    """
    nosana = _get_nosana()
    
    result = nosana.stop_deployment(deployment_id)
    
    return {
        "deployment_id": deployment_id,
        "status": result.get("status", "unknown"),
        "stopped": result.get("status") in ["STOPPED", "STOPPING"],
        "message": "Deployment stop initiated"
    }


@nosana_router.skill(tags=["deployment", "control"])
def start_deployment(deployment_id: str) -> dict:
    """
    Start a stopped Nosana deployment.
    """
    nosana = _get_nosana()
    
    result = nosana.start_deployment(deployment_id)
    
    return {
        "deployment_id": deployment_id,
        "status": result.get("status", "unknown"),
        "started": result.get("status") in ["RUNNING", "STARTING"],
        "message": "Deployment start initiated"
    }


@nosana_router.skill(tags=["deployment", "list"])
def list_deployments() -> dict:
    """
    List all Nosana deployments.
    """
    nosana = _get_nosana()
    
    result = nosana.list_deployments()
    
    if not result.get("success"):
        return result
    
    deployments = result.get("deployments", [])
    
    return {
        "total_deployments": len(deployments),
        "deployments": [
            {
                "deployment_id": d.get("id"),
                "name": d.get("name"),
                "status": d.get("status"),
                "active_jobs": d.get("active_jobs", 0),
                "created_at": d.get("created_at")
            }
            for d in deployments
        ]
    }


@nosana_router.reasoner(tags=["ai", "testing", "hardhat"])
async def run_hardhat_tests_on_nosana(
    repo_url: str,
    test_command: str = "npx hardhat test",
    timeout_minutes: int = 30
) -> dict:
    """
    Run Hardhat tests on Nosana compute.
    Clones repo, installs dependencies, runs tests.
    """
    nosana = _get_nosana()
    
    # Run tests using Nosana
    result = nosana.run_tests(
        repo_url=repo_url,
        test_command=test_command,
        timeout_minutes=timeout_minutes
    )
    
    if not result.get("success"):
        return result
    
    deployment_id = result.get("deployment_id")
    
    # Wait a bit for tests to start
    time.sleep(3)
    
    # Get deployment status
    status = nosana.get_deployment(deployment_id)
    
    # Use AI to analyze test setup
    analysis = await nosana_router.ai(
        system="You are a smart contract testing expert. Analyze this test deployment.",
        user=f"Repo: {repo_url}\nCommand: {test_command}\nStatus: {status}\nProvide insights.",
    )
    
    nosana_router.app.note(
        f"Running Hardhat tests on Nosana (deployment: {deployment_id})",
        tags=["nosana", "testing", "hardhat"]
    )
    
    return {
        "deployment_id": deployment_id,
        "repo_url": repo_url,
        "test_command": test_command,
        "status": status.get("status"),
        "deployment_details": result,
        "ai_analysis": analysis
    }


@nosana_router.skill(tags=["market", "info"])
def list_compute_markets(market_type: str = None) -> dict:
    """
    List available Nosana compute markets.
    """
    nosana = _get_nosana()
    
    result = nosana.list_markets(market_type=market_type, limit=20)
    
    if not result.get("success"):
        return result
    
    markets = result.get("markets", [])
    
    return {
        "total_markets": len(markets),
        "market_type_filter": market_type,
        "markets": [
            {
                "address": m.get("address"),
                "name": m.get("name"),
                "type": m.get("type"),
                "gpu_types": m.get("gpu_types", []),
                "price_per_second": m.get("nos_job_price_per_second")
            }
            for m in markets
        ]
    }


@nosana_router.skill(tags=["vault", "payment"])
def create_payment_vault() -> dict:
    """
    Create a payment vault for Nosana deployments.
    """
    nosana = _get_nosana()
    
    result = nosana.create_vault()
    
    return {
        "vault_address": result.get("vault"),
        "owner": result.get("owner"),
        "created_at": result.get("created_at", ""),
        "success": "vault" in result,
        "note": "Vault created. Fund it with SOL/NOS to run deployments."
    }


@nosana_router.skill(tags=["vault", "info"])
def list_payment_vaults() -> dict:
    """
    List all payment vaults.
    """
    nosana = _get_nosana()
    
    result = nosana.list_vaults()
    
    if not result.get("success"):
        return result
    
    vaults = result.get("vaults", [])
    
    return {
        "total_vaults": len(vaults),
        "vaults": [
            {
                "vault_address": v.get("vault"),
                "owner": v.get("owner"),
                "created_at": v.get("created_at")
            }
            for v in vaults
        ]
    }


@nosana_router.skill(tags=["workflow", "automation"])
def create_ci_pipeline_on_nosana(
    name: str,
    repo_url: str,
    commands: list[str],
    timeout_minutes: int = 30
) -> dict:
    """
    Create a CI/CD pipeline on Nosana compute.
    Clones repo, runs commands in container.
    """
    nosana = _get_nosana()
    
    # Prepare CI commands
    ci_commands = [
        f"git clone {repo_url} /workspace",
        "cd /workspace",
    ] + commands
    
    # Build job definition
    job_def = nosana.build_container_job(
        image="ubuntu:22.04",
        commands=ci_commands,
        work_dir="/workspace"
    )
    
    # Create deployment
    deployment = nosana.create_deployment(
        name=name,
        job_definition=job_def,
        timeout=timeout_minutes,
        strategy="SIMPLE"
    )
    
    if not deployment.get("success"):
        return deployment
    
    # Auto-start
    deployment_id = deployment["id"]
    nosana.start_deployment(deployment_id)
    
    return {
        "deployment_id": deployment_id,
        "name": name,
        "repo_url": repo_url,
        "status": "STARTING",
        "timeout_minutes": timeout_minutes,
        "commands_count": len(commands)
    }


@nosana_router.skill(tags=["solidity", "compilation"])
def compile_solidity_contract(
    contract_code: str,
    contract_name: str = "Contract",
    solc_version: str = "0.8.20"
) -> dict:
    """
    Compile Solidity contract (non-AI version).
    """
    nosana = _get_nosana()
    
    result = nosana.compile_solidity(
        contract_code=contract_code,
        contract_name=contract_name,
        solc_version=solc_version,
        timeout_minutes=10
    )
    
    return result


@nosana_router.skill(tags=["health", "nosana"])
def check_nosana_status() -> dict:
    """
    Check Nosana API health and configuration.
    """
    nosana = _get_nosana()
    
    health = nosana.health_check()
    
    # Try to get markets and vaults info
    markets_result = nosana.list_markets(limit=5)
    vaults_result = nosana.list_vaults()
    
    return {
        **health,
        "markets_available": markets_result.get("count", 0),
        "vaults_count": vaults_result.get("count", 0),
        "capabilities": [
            "Container deployments",
            "GPU compute (optional)",
            "Solidity compilation",
            "Hardhat testing",
            "Custom Docker images",
            "Port exposure for web services",
            "Market-based resource allocation",
            "Vault-based payment system"
        ]
    }

# Made with Bob
