"""Nosana client for reagent — decentralized GPU/compute orchestration.

Provides on-demand container environments for:
- Smart contract compilation (solc, forge)
- Testing and simulation
- Heavy computation tasks
- CI/CD pipeline execution
- Code deployment to repositories

Based on Nosana Dashboard API v1.0.0
API Base URL: https://dashboard.k8s.prd.nos.ci/api
"""

import os
import requests
import time
import json
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta


class NosanaClient:
    """Client for Nosana decentralized compute network."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        """Initialize Nosana client.
        
        Args:
            api_key: Nosana API key (or use NOSANA_API_KEY env var)
            api_url: Nosana API URL (default: https://dashboard.k8s.prd.nos.ci/api)
        """
        self.api_key = api_key or os.getenv("NOSANA_API_KEY", "")
        self.api_url = api_url or os.getenv(
            "NOSANA_API_URL", 
            "https://dashboard.k8s.prd.nos.ci/api"
        )
        
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            })
        
        # Cache for markets and vaults
        self._markets_cache: Optional[List[Dict]] = None
        self._vaults_cache: Optional[List[Dict]] = None
        self._default_vault: Optional[str] = None

    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Nosana API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            data: Request body data
            params: Query parameters
            
        Returns:
            Response data as dictionary
        """
        url = f"{self.api_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "note": "API request failed - check API key and network connectivity"
            }

    # ==================== Market Management ====================

    def list_markets(
        self, 
        market_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """List available compute markets.
        
        Args:
            market_type: Filter by type (PREMIUM, COMMUNITY, OTHER)
            limit: Maximum number of results
            
        Returns:
            List of available markets with pricing and capabilities
        """
        params = {}
        if market_type:
            params["type"] = market_type
        if limit:
            params["limit"] = str(limit)
            
        result = self._make_request("GET", "/markets/", params=params)
        
        if isinstance(result, list):
            self._markets_cache = result
            return {
                "success": True,
                "markets": result,
                "count": len(result)
            }
        return result

    def get_market(self, market_id: str) -> Dict[str, Any]:
        """Get details of a specific market.
        
        Args:
            market_id: Market address/ID
            
        Returns:
            Market details including pricing and GPU types
        """
        return self._make_request("GET", f"/markets/{market_id}/")

    def get_default_market(self) -> Optional[str]:
        """Get a default market address for deployments.
        
        Returns:
            Market address or None if no markets available
        """
        if not self._markets_cache:
            result = self.list_markets(limit=10)
            if not result.get("success"):
                return None
        
        if self._markets_cache:
            # Prefer COMMUNITY markets for cost-effectiveness
            for market in self._markets_cache:
                if market.get("type") == "COMMUNITY":
                    return market.get("address")
            # Fallback to first available market
            return self._markets_cache[0].get("address")
        
        return None

    # ==================== Vault Management ====================

    def create_vault(self) -> Dict[str, Any]:
        """Create a new payment vault for deployments.
        
        Returns:
            Vault details including vault address
        """
        result = self._make_request("POST", "/deployments/vaults/create")
        
        if result.get("vault"):
            self._default_vault = result["vault"]
            
        return result

    def list_vaults(self) -> Dict[str, Any]:
        """List all vaults owned by the authenticated user.
        
        Returns:
            List of vaults with balances
        """
        result = self._make_request("GET", "/deployments/vaults/")
        
        if isinstance(result, list):
            self._vaults_cache = result
            if result and not self._default_vault:
                self._default_vault = result[0].get("vault")
            return {
                "success": True,
                "vaults": result,
                "count": len(result)
            }
        return result

    def get_vault(self, vault_address: str) -> Dict[str, Any]:
        """Get details of a specific vault.
        
        Args:
            vault_address: Vault address
            
        Returns:
            Vault details including balance
        """
        return self._make_request("GET", f"/deployments/vaults/{vault_address}/")

    def withdraw_from_vault(
        self, 
        vault_address: str,
        sol_amount: float = 0,
        nos_amount: float = 0
    ) -> Dict[str, Any]:
        """Withdraw funds from a vault.
        
        Args:
            vault_address: Vault address
            sol_amount: Amount of SOL to withdraw
            nos_amount: Amount of NOS to withdraw
            
        Returns:
            Transaction details
        """
        data = {}
        if sol_amount > 0:
            data["SOL"] = sol_amount
        if nos_amount > 0:
            data["NOS"] = nos_amount
            
        return self._make_request(
            "POST", 
            f"/deployments/vaults/{vault_address}/withdraw",
            data=data
        )

    def get_or_create_vault(self) -> Optional[str]:
        """Get existing vault or create a new one.
        
        Returns:
            Vault address or None on failure
        """
        if self._default_vault:
            return self._default_vault
            
        # Try to list existing vaults
        vaults_result = self.list_vaults()
        if vaults_result.get("success") and vaults_result.get("vaults"):
            return vaults_result["vaults"][0]["vault"]
        
        # Create new vault if none exist
        vault_result = self.create_vault()
        if vault_result.get("vault"):
            return vault_result["vault"]
            
        return None

    # ==================== Deployment Management ====================

    def create_deployment(
        self,
        name: str,
        job_definition: Dict[str, Any],
        market: Optional[str] = None,
        vault: Optional[str] = None,
        replicas: int = 1,
        timeout: int = 30,
        strategy: str = "SIMPLE",
        confidential: bool = False,
        schedule: Optional[str] = None,
        rotation_time: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a new deployment.
        
        Args:
            name: Deployment name
            job_definition: Job definition with container specs
            market: Market address (auto-selected if not provided)
            vault: Vault address (auto-created if not provided)
            replicas: Number of replicas (default: 1)
            timeout: Timeout in minutes (default: 30)
            strategy: Deployment strategy (SIMPLE, SIMPLE-EXTEND, SCHEDULED, INFINITE)
            confidential: Whether deployment is confidential
            schedule: Cron expression for SCHEDULED strategy
            rotation_time: Rotation time in seconds for INFINITE strategy
            
        Returns:
            Deployment details including deployment ID and status
        """
        # Auto-select market if not provided
        if not market:
            market = self.get_default_market()
            if not market:
                return {
                    "success": False,
                    "error": "No markets available. Please specify a market address."
                }
        
        # Auto-create vault if not provided
        if not vault:
            vault = self.get_or_create_vault()
            if not vault:
                return {
                    "success": False,
                    "error": "Failed to create vault. Please create one manually."
                }
        
        # Build deployment body
        deployment_body: Dict[str, Any] = {
            "name": name,
            "market": market,
            "vault": vault,
            "replicas": replicas,
            "timeout": timeout,
            "strategy": strategy,
            "job_definition": job_definition
        }
        
        if confidential:
            deployment_body["confidential"] = confidential
            
        # Add strategy-specific fields
        if strategy == "SCHEDULED" and schedule:
            deployment_body["schedule"] = schedule
        elif strategy == "INFINITE":
            if timeout < 60:
                return {
                    "success": False,
                    "error": "INFINITE strategy requires timeout >= 60 minutes"
                }
            if rotation_time:
                deployment_body["rotation_time"] = rotation_time
        
        result = self._make_request("POST", "/deployments/create", data=deployment_body)
        
        if result.get("id"):
            result["success"] = True
            
        return result

    def list_deployments(self) -> Dict[str, Any]:
        """List all deployments for the authenticated user.
        
        Returns:
            List of deployments with status
        """
        result = self._make_request("GET", "/deployments/")
        
        if isinstance(result, list):
            return {
                "success": True,
                "deployments": result,
                "count": len(result)
            }
        return result

    def get_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """Get details of a specific deployment.
        
        Args:
            deployment_id: Deployment ID
            
        Returns:
            Deployment details including status and endpoints
        """
        return self._make_request("GET", f"/deployments/{deployment_id}/")

    def start_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """Start a stopped deployment.
        
        Args:
            deployment_id: Deployment ID
            
        Returns:
            Updated deployment status
        """
        return self._make_request("POST", f"/deployments/{deployment_id}/start")

    def stop_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """Stop a running deployment.
        
        Args:
            deployment_id: Deployment ID
            
        Returns:
            Updated deployment status
        """
        return self._make_request("POST", f"/deployments/{deployment_id}/stop")

    def archive_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """Archive a deployment (permanent deletion).
        
        Args:
            deployment_id: Deployment ID
            
        Returns:
            Confirmation of archival
        """
        return self._make_request("POST", f"/deployments/{deployment_id}/archive")

    def create_revision(
        self, 
        deployment_id: str, 
        job_definition: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new revision for an existing deployment.
        
        Args:
            deployment_id: Deployment ID
            job_definition: Updated job definition
            
        Returns:
            New revision details
        """
        return self._make_request(
            "POST", 
            f"/deployments/{deployment_id}/create-revision",
            data=job_definition
        )

    # ==================== Job Definition Builders ====================

    def build_container_job(
        self,
        image: str,
        commands: Optional[List[str]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        work_dir: Optional[str] = None,
        expose_port: Optional[int] = None,
        gpu: bool = False
    ) -> Dict[str, Any]:
        """Build a container job definition.
        
        Args:
            image: Docker image (e.g., "ubuntu:22.04", "ethereum/solc:stable")
            commands: Commands to execute
            env_vars: Environment variables
            work_dir: Working directory
            expose_port: Port to expose (for web services)
            gpu: Whether GPU is required
            
        Returns:
            Job definition ready for deployment
        """
        job_def: Dict[str, Any] = {
            "version": "0.1",
            "type": "container",
            "ops": []
        }
        
        # Global settings
        if env_vars or work_dir or gpu:
            global_config: Dict[str, Any] = {}
            if env_vars:
                global_config["env"] = env_vars
            if work_dir:
                global_config["work_dir"] = work_dir
            if gpu:
                global_config["gpu"] = True
            job_def["global"] = global_config
        
        # Container operation
        container_op: Dict[str, Any] = {
            "type": "container/run",
            "id": "main",
            "args": {
                "image": image
            }
        }
        
        if commands:
            container_op["args"]["cmd"] = commands
            
        if expose_port:
            container_op["args"]["expose"] = {
                "port": expose_port,
                "type": "web"
            }
        
        job_def["ops"].append(container_op)
        
        return job_def

    def build_solidity_compile_job(
        self,
        contract_code: str,
        contract_name: str = "Contract",
        solc_version: str = "0.8.20"
    ) -> Dict[str, Any]:
        """Build a job definition for Solidity compilation.
        
        Args:
            contract_code: Solidity source code
            contract_name: Contract name
            solc_version: Solidity compiler version
            
        Returns:
            Job definition for compilation
        """
        # Escape contract code for shell
        escaped_code = contract_code.replace('"', '\\"').replace('$', '\\$')
        
        commands = [
            "sh", "-c",
            f'echo "{escaped_code}" > /tmp/{contract_name}.sol && '
            f'solc --version && '
            f'solc --optimize --bin --abi /tmp/{contract_name}.sol'
        ]
        
        return self.build_container_job(
            image=f"ethereum/solc:{solc_version}",
            commands=commands,
            work_dir="/tmp"
        )

    def build_hardhat_test_job(
        self,
        repo_url: str,
        test_command: str = "npx hardhat test"
    ) -> Dict[str, Any]:
        """Build a job definition for Hardhat testing.
        
        Args:
            repo_url: Git repository URL
            test_command: Test command to run
            
        Returns:
            Job definition for testing
        """
        commands = [
            "sh", "-c",
            f'git clone {repo_url} /workspace && '
            f'cd /workspace && '
            f'npm install && '
            f'{test_command}'
        ]
        
        return self.build_container_job(
            image="node:18",
            commands=commands,
            work_dir="/workspace"
        )

    # ==================== High-Level Operations ====================

    def compile_solidity(
        self,
        contract_code: str,
        contract_name: str = "Contract",
        solc_version: str = "0.8.20",
        timeout_minutes: int = 10
    ) -> Dict[str, Any]:
        """Compile Solidity contract on Nosana network.
        
        Args:
            contract_code: Solidity source code
            contract_name: Contract name
            solc_version: Solidity compiler version
            timeout_minutes: Compilation timeout
            
        Returns:
            Compilation result with bytecode and ABI
        """
        job_def = self.build_solidity_compile_job(
            contract_code, contract_name, solc_version
        )
        
        deployment = self.create_deployment(
            name=f"compile-{contract_name}-{int(time.time())}",
            job_definition=job_def,
            timeout=timeout_minutes,
            strategy="SIMPLE"
        )
        
        if not deployment.get("success"):
            return deployment
        
        # Auto-start deployment
        deployment_id = deployment["id"]
        start_result = self.start_deployment(deployment_id)
        
        return {
            "success": True,
            "deployment_id": deployment_id,
            "status": start_result.get("status", "STARTING"),
            "contract_name": contract_name,
            "solc_version": solc_version,
            "note": "Deployment started. Use get_deployment() to check status and retrieve results."
        }

    def run_tests(
        self,
        repo_url: str,
        test_command: str = "npx hardhat test",
        timeout_minutes: int = 30
    ) -> Dict[str, Any]:
        """Run tests on Nosana network.
        
        Args:
            repo_url: Git repository URL
            test_command: Test command
            timeout_minutes: Test timeout
            
        Returns:
            Test execution result
        """
        job_def = self.build_hardhat_test_job(repo_url, test_command)
        
        deployment = self.create_deployment(
            name=f"test-{int(time.time())}",
            job_definition=job_def,
            timeout=timeout_minutes,
            strategy="SIMPLE"
        )
        
        if not deployment.get("success"):
            return deployment
        
        deployment_id = deployment["id"]
        start_result = self.start_deployment(deployment_id)
        
        return {
            "success": True,
            "deployment_id": deployment_id,
            "status": start_result.get("status", "STARTING"),
            "repo_url": repo_url,
            "note": "Tests started. Use get_deployment() to check status and retrieve results."
        }

    def health_check(self) -> Dict[str, Any]:
        """Check if Nosana API is accessible.
        
        Returns:
            Health status and API information
        """
        try:
            markets = self.list_markets(limit=1)
            if markets.get("success"):
                return {
                    "success": True,
                    "status": "healthy",
                    "api_url": self.api_url,
                    "authenticated": bool(self.api_key),
                    "markets_available": markets.get("count", 0) > 0
                }
            else:
                return {
                    "success": False,
                    "status": "unhealthy",
                    "error": markets.get("error", "Unknown error"),
                    "api_url": self.api_url
                }
        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "error": str(e),
                "api_url": self.api_url
            }

# Made with Bob
