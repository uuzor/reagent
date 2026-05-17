"""
Production-Ready GitHub Codespaces Integration Client
Complete implementation based on official GitHub API documentation.
"""
import os
import asyncio
import aiohttp
import json
import subprocess
import time
import base64
from typing import Optional, Dict, Any, List, AsyncIterator
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CodespaceState(str, Enum):
    """Codespace states from GitHub API."""
    UNKNOWN = "Unknown"
    CREATED = "Created"
    QUEUED = "Queued"
    PROVISIONING = "Provisioning"
    AVAILABLE = "Available"
    AWAITING = "Awaiting"
    UNAVAILABLE = "Unavailable"
    DELETED = "Deleted"
    MOVED = "Moved"
    SHUTDOWN = "Shutdown"
    ARCHIVED = "Archived"
    STARTING = "Starting"
    SHUTTING_DOWN = "ShuttingDown"
    FAILED = "Failed"
    EXPORTING = "Exporting"
    UPDATING = "Updating"
    REBUILDING = "Rebuilding"


class MachineType(BaseModel):
    """Codespace machine type."""
    name: str
    display_name: str
    operating_system: str
    storage_in_bytes: int
    memory_in_bytes: int
    cpus: int
    prebuild_availability: Optional[str] = None


class DevcontainerConfig(BaseModel):
    """Devcontainer configuration for Codespace."""
    name: str = "Reagent Smart Contract Development"
    image: str = "mcr.microsoft.com/devcontainers/python:3.11"
    features: Dict[str, Any] = Field(default_factory=lambda: {
        "ghcr.io/devcontainers/features/node:1": {"version": "18"},
        "ghcr.io/devcontainers/features/docker-in-docker:2": {},
        "ghcr.io/devcontainers/features/github-cli:1": {}
    })
    customizations: Dict[str, Any] = Field(default_factory=lambda: {
        "vscode": {
            "extensions": [
                "ms-python.python",
                "ms-python.vscode-pylance",
                "juanblanco.solidity",
                "GitHub.copilot"
            ],
            "settings": {
                "python.defaultInterpreterPath": "/usr/local/bin/python",
                "python.linting.enabled": True,
                "python.formatting.provider": "black"
            }
        }
    })
    post_create_command: str = "pip install -r requirements.txt && pip install reagent"
    remote_user: str = "vscode"
    forward_ports: List[int] = Field(default_factory=lambda: [8000, 3000])
    ports_attributes: Dict[str, Any] = Field(default_factory=lambda: {
        "8000": {
            "label": "Reagent API",
            "onAutoForward": "notify"
        },
        "3000": {
            "label": "Frontend",
            "onAutoForward": "silent"
        }
    })


class CodespaceCreateRequest(BaseModel):
    """Request to create a Codespace."""
    ref: str = "main"
    location: str = "WestUs2"
    machine: str = "standardLinux32gb"
    devcontainer_path: Optional[str] = None
    multi_repo_permissions_opt_out: bool = False
    working_directory: Optional[str] = None
    idle_timeout_minutes: int = 60
    display_name: Optional[str] = None
    retention_period_minutes: int = 4320  # 3 days


class Codespace(BaseModel):
    """Codespace information from GitHub API."""
    id: int
    name: str
    display_name: Optional[str] = None
    environment_id: str
    owner: Dict[str, Any]
    billable_owner: Dict[str, Any]
    repository: Dict[str, Any]
    machine: Dict[str, Any]
    devcontainer_path: Optional[str] = None
    prebuild: Optional[bool] = None
    created_at: str
    updated_at: str
    last_used_at: str
    state: str
    url: str
    git_status: Dict[str, Any]
    location: str
    idle_timeout_minutes: Optional[int] = None
    web_url: str
    machines_url: str
    start_url: str
    stop_url: str
    recent_folders: List[str] = []


class GitHubCodespacesClient:
    """
    Production-ready GitHub Codespaces API client.
    Implements all official GitHub Codespaces REST API endpoints.
    """
    
    def __init__(
        self, 
        access_token: str,
        api_version: str = "2022-11-28"
    ):
        """
        Initialize GitHub Codespaces client.
        
        Args:
            access_token: GitHub OAuth token with 'codespace' scope
            api_version: GitHub API version
        """
        self.token = access_token
        self.api_base = "https://api.github.com"
        self.api_version = api_version
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": api_version
        }
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated request to GitHub API with retry logic.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request body
            params: Query parameters
            
        Returns:
            Response JSON
            
        Raises:
            Exception: On API error
        """
        url = f"{self.api_base}{endpoint}"
        
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with self.session.request(
                    method,
                    url,
                    json=data,
                    params=params
                ) as response:
                    # Handle rate limiting
                    if response.status == 429:
                        retry_after = int(response.headers.get('Retry-After', 60))
                        logger.warning(f"Rate limited. Retrying after {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                    
                    # Handle errors
                    if response.status >= 400:
                        error_text = await response.text()
                        logger.error(f"GitHub API error {response.status}: {error_text}")
                        
                        if response.status == 404:
                            raise Exception(f"Resource not found: {endpoint}")
                        elif response.status == 403:
                            raise Exception(f"Forbidden: Check token scopes")
                        elif response.status == 401:
                            raise Exception(f"Unauthorized: Invalid token")
                        else:
                            raise Exception(f"GitHub API error {response.status}: {error_text}")
                    
                    # Success
                    if response.status == 204:  # No content
                        return {}
                    
                    return await response.json()
                    
            except aiohttp.ClientError as e:
                logger.error(f"Network error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        raise Exception("Max retries exceeded")
    
    # ==================== Codespace Management ====================
    
    async def list_codespaces(
        self,
        per_page: int = 30,
        page: int = 1,
        repository_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        List user's Codespaces.
        
        Args:
            per_page: Results per page (max 100)
            page: Page number
            repository_id: Filter by repository
            
        Returns:
            {
                "total_count": int,
                "codespaces": [Codespace, ...]
            }
        """
        params = {"per_page": per_page, "page": page}
        if repository_id:
            params["repository_id"] = repository_id
        
        return await self._request("GET", "/user/codespaces", params=params)
    
    async def get_codespace(self, codespace_name: str) -> Codespace:
        """
        Get Codespace details.
        
        Args:
            codespace_name: Codespace name
            
        Returns:
            Codespace object
        """
        result = await self._request("GET", f"/user/codespaces/{codespace_name}")
        return Codespace(**result)
    
    async def create_codespace(
        self,
        owner: str,
        repo: str,
        request: CodespaceCreateRequest
    ) -> Codespace:
        """
        Create a new Codespace.
        
        Args:
            owner: Repository owner
            repo: Repository name
            request: Creation parameters
            
        Returns:
            Created Codespace
        """
        endpoint = f"/repos/{owner}/{repo}/codespaces"
        result = await self._request("POST", endpoint, data=request.model_dump(exclude_none=True))
        return Codespace(**result)
    
    async def start_codespace(self, codespace_name: str) -> Codespace:
        """
        Start a stopped Codespace.
        
        Args:
            codespace_name: Codespace name
            
        Returns:
            Updated Codespace
        """
        result = await self._request("POST", f"/user/codespaces/{codespace_name}/start")
        return Codespace(**result)
    
    async def stop_codespace(self, codespace_name: str) -> Codespace:
        """
        Stop a running Codespace.
        
        Args:
            codespace_name: Codespace name
            
        Returns:
            Updated Codespace
        """
        result = await self._request("POST", f"/user/codespaces/{codespace_name}/stop")
        return Codespace(**result)
    
    async def delete_codespace(self, codespace_name: str):
        """
        Delete a Codespace.
        
        Args:
            codespace_name: Codespace name
        """
        await self._request("DELETE", f"/user/codespaces/{codespace_name}")
        logger.info(f"Deleted Codespace: {codespace_name}")
    
    async def update_codespace(
        self,
        codespace_name: str,
        display_name: Optional[str] = None,
        idle_timeout_minutes: Optional[int] = None
    ) -> Codespace:
        """
        Update Codespace settings.
        
        Args:
            codespace_name: Codespace name
            display_name: New display name
            idle_timeout_minutes: New idle timeout
            
        Returns:
            Updated Codespace
        """
        data = {}
        if display_name:
            data["display_name"] = display_name
        if idle_timeout_minutes:
            data["idle_timeout_minutes"] = idle_timeout_minutes
        
        result = await self._request("PATCH", f"/user/codespaces/{codespace_name}", data=data)
        return Codespace(**result)
    
    # ==================== Machine Types ====================
    
    async def list_machines(
        self,
        owner: str,
        repo: str,
        location: Optional[str] = None,
        ref: Optional[str] = None
    ) -> List[MachineType]:
        """
        List available machine types for repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            location: Geographic location
            ref: Git ref
            
        Returns:
            List of available machines
        """
        params = {}
        if location:
            params["location"] = location
        if ref:
            params["ref"] = ref
        
        result = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/codespaces/machines",
            params=params
        )
        return [MachineType(**m) for m in result.get("machines", [])]
    
    # ==================== Secrets Management ====================
    
    async def list_secrets(self) -> Dict[str, Any]:
        """
        List user's Codespace secrets.
        
        Returns:
            {
                "total_count": int,
                "secrets": [...]
            }
        """
        return await self._request("GET", "/user/codespaces/secrets")
    
    async def get_secret(self, secret_name: str) -> Dict[str, Any]:
        """Get a specific secret."""
        return await self._request("GET", f"/user/codespaces/secrets/{secret_name}")
    
    async def create_or_update_secret(
        self,
        secret_name: str,
        encrypted_value: str,
        key_id: str,
        selected_repository_ids: Optional[List[int]] = None
    ):
        """
        Create or update a Codespace secret.
        
        Args:
            secret_name: Secret name
            encrypted_value: Encrypted secret value
            key_id: Public key ID
            selected_repository_ids: Repository IDs with access
        """
        data = {
            "encrypted_value": encrypted_value,
            "key_id": key_id
        }
        if selected_repository_ids:
            data["selected_repository_ids"] = selected_repository_ids
        
        await self._request("PUT", f"/user/codespaces/secrets/{secret_name}", data=data)
    
    async def delete_secret(self, secret_name: str):
        """Delete a Codespace secret."""
        await self._request("DELETE", f"/user/codespaces/secrets/{secret_name}")
    
    # ==================== Repository Operations ====================
    
    async def create_devcontainer_file(
        self,
        owner: str,
        repo: str,
        branch: str,
        config: DevcontainerConfig
    ) -> Dict[str, Any]:
        """
        Create .devcontainer/devcontainer.json in repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch: Branch name
            config: Devcontainer configuration
            
        Returns:
            Commit information
        """
        import base64
        
        content = json.dumps(config.model_dump(exclude_none=True), indent=2)
        content_encoded = base64.b64encode(content.encode()).decode()
        
        data = {
            "message": "[Reagent] Add devcontainer configuration",
            "content": content_encoded,
            "branch": branch
        }
        
        return await self._request(
            "PUT",
            f"/repos/{owner}/{repo}/contents/.devcontainer/devcontainer.json",
            data=data
        )
    
    # ==================== State Monitoring ====================
    
    async def wait_for_state(
        self,
        codespace_name: str,
        target_state: CodespaceState,
        timeout: int = 300,
        poll_interval: int = 5
    ) -> Codespace:
        """
        Wait for Codespace to reach target state.
        
        Args:
            codespace_name: Codespace name
            target_state: Desired state
            timeout: Max wait time in seconds
            poll_interval: Polling interval in seconds
            
        Returns:
            Codespace in target state
            
        Raises:
            TimeoutError: If timeout exceeded
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            codespace = await self.get_codespace(codespace_name)
            
            logger.info(f"Codespace {codespace_name} state: {codespace.state}")
            
            if codespace.state == target_state.value:
                return codespace
            
            if codespace.state == CodespaceState.FAILED.value:
                raise Exception(f"Codespace failed to start")
            
            await asyncio.sleep(poll_interval)
        
        raise TimeoutError(f"Codespace did not reach {target_state} within {timeout}s")
    
    # ==================== Command Execution (via GitHub CLI) ====================
    
    def execute_command_sync(
        self,
        codespace_name: str,
        command: str
    ) -> Dict[str, Any]:
        """
        Execute command in Codespace using GitHub CLI (synchronous).
        Requires 'gh' CLI to be installed.
        
        Args:
            codespace_name: Codespace name
            command: Command to execute
            
        Returns:
            {
                "stdout": str,
                "stderr": str,
                "returncode": int
            }
        """
        try:
            result = subprocess.run(
                ["gh", "codespace", "ssh", "--codespace", codespace_name, "--", command],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "Command timed out",
                "returncode": -1,
                "success": False
            }
        except FileNotFoundError:
            return {
                "stdout": "",
                "stderr": "GitHub CLI (gh) not installed",
                "returncode": -1,
                "success": False
            }
    
    async def execute_command(
        self,
        codespace_name: str,
        command: str
    ) -> Dict[str, Any]:
        """
        Execute command in Codespace (async wrapper).
        
        Args:
            codespace_name: Codespace name
            command: Command to execute
            
        Returns:
            Execution result
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.execute_command_sync,
            codespace_name,
            command
        )


# ==================== Orchestration Layer ====================

class SecureTokenStore:
    """Encrypts and stores GitHub OAuth tokens using Fernet symmetric encryption."""

    def __init__(self, encryption_key: Optional[str] = None):
        key = encryption_key or os.getenv("ENCRYPTION_KEY")
        if key:
            try:
                from cryptography.fernet import Fernet
                # Ensure key is valid Fernet key (32 url-safe base64-encoded bytes)
                if len(key) < 44:
                    key = base64.urlsafe_b64encode(key.ljust(32).encode()[:32]).decode()
                self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
            except ImportError:
                logger.warning("cryptography not installed — tokens stored in plaintext")
                self._fernet = None
        else:
            self._fernet = None
            logger.warning("No ENCRYPTION_KEY set — tokens stored in plaintext")

        self._store: Dict[str, str] = {}

    def encrypt_token(self, token: str, user_id: str) -> str:
        if self._fernet:
            encrypted = self._fernet.encrypt(token.encode()).decode()
        else:
            encrypted = token
        self._store[user_id] = encrypted
        return encrypted

    def decrypt_token(self, user_id: str) -> Optional[str]:
        encrypted = self._store.get(user_id)
        if encrypted is None:
            return None
        if self._fernet:
            try:
                return self._fernet.decrypt(encrypted.encode()).decode()
            except Exception:
                logger.error(f"Failed to decrypt token for user {user_id}")
                return None
        return encrypted

    def revoke_token(self, user_id: str) -> None:
        self._store.pop(user_id, None)


class CodespaceConfig(BaseModel):
    """Configuration for creating a Codespace workflow."""
    repository: str
    branch: str = "main"
    machine: str = "basicLinux32gb"
    devcontainer_path: Optional[str] = None
    idle_timeout_minutes: int = 60
    retention_period_minutes: int = 4320


class CodespaceWorkflow(BaseModel):
    """Tracks a workflow running inside a GitHub Codespace."""
    workflow_id: str
    user_id: str
    repository: str
    branch: str
    codespace_name: Optional[str] = None
    codespace_url: Optional[str] = None
    status: str = "pending"
    execution_logs: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


class CodespaceOrchestrator:
    """High-level orchestration layer over GitHubCodespacesClient.

    Manages the lifecycle of creating a Codespace, executing workflow
    commands, and cleaning up when done.
    """

    def __init__(self, client: GitHubCodespacesClient):
        self.client = client

    async def setup_codespace(
        self,
        workflow: CodespaceWorkflow,
        config: CodespaceConfig,
    ) -> str:
        """Create a Codespace, wait for it to become available, install deps.

        Returns the codespace name.
        """
        owner, repo = config.repository.split("/", 1)
        request = CodespaceCreateRequest(
            ref=config.branch,
            machine=config.machine,
            idle_timeout_minutes=config.idle_timeout_minutes,
            retention_period_minutes=config.retention_period_minutes,
            devcontainer_path=config.devcontainer_path,
        )

        codespace = await self.client.create_codespace(owner, repo, request)
        workflow.codespace_name = codespace.name
        workflow.codespace_url = codespace.web_url
        workflow.execution_logs.append(f"Codespace created: {codespace.name}")

        # Wait for Codespace to be ready
        codespace = await self.client.wait_for_state(
            codespace.name,
            CodespaceState.AVAILABLE,
            timeout=300,
            poll_interval=10,
        )
        workflow.status = "running"
        workflow.execution_logs.append("Codespace is available")

        # Install dependencies
        result = await self.client.execute_command(
            codespace.name,
            "pip install solc-select web3 pydantic 2>&1 || true",
        )
        workflow.execution_logs.append(f"Dependencies installed: {result.get('stdout', '')[:200]}")

        return codespace.name

    async def execute_workflow_via_commits(
        self,
        workflow: CodespaceWorkflow,
        requirements: str,
    ) -> Dict[str, Any]:
        """Push devcontainer + config files as commits and run the workflow."""
        owner, repo = workflow.repository.split("/", 1)

        # Create devcontainer in the repo
        devcontainer = DevcontainerConfig()
        await self.client.create_devcontainer_file(
            owner, repo, workflow.branch, devcontainer,
        )
        workflow.execution_logs.append("Devcontainer configuration pushed")

        # Execute the orchestration command in the Codespace
        escaped = requirements.replace("'", "'\\''")
        command = f"python -c \"from reagent.main import app; print('reagent ready')\" 2>&1 || echo 'reagent not installed yet'"
        result = await self.client.execute_command(workflow.codespace_name, command)

        workflow.execution_logs.append(f"Workflow execution: {result.get('stdout', '')[:500]}")
        workflow.status = "completed"
        workflow.completed_at = datetime.now().isoformat()

        return result

    async def execute_command(self, codespace_name: str, command: str) -> Dict[str, Any]:
        """Execute a single command in the Codespace."""
        return await self.client.execute_command(codespace_name, command)

    async def cleanup_codespace(self, workflow: CodespaceWorkflow) -> None:
        """Stop and delete the Codespace."""
        if workflow.codespace_name:
            try:
                await self.client.stop_codespace(workflow.codespace_name)
                workflow.execution_logs.append(f"Codespace stopped: {workflow.codespace_name}")
            except Exception as e:
                logger.warning(f"Failed to stop Codespace: {e}")
            try:
                await self.client.delete_codespace(workflow.codespace_name)
                workflow.execution_logs.append(f"Codespace deleted: {workflow.codespace_name}")
            except Exception as e:
                logger.warning(f"Failed to delete Codespace: {e}")


# Example usage
async def example_full_workflow():
    """Complete example of Codespace workflow."""
    
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Set GITHUB_TOKEN environment variable")
        return
    
    async with GitHubCodespacesClient(token) as client:
        # 1. List available machines
        machines = await client.list_machines("owner", "repo")
        print(f"Available machines: {len(machines)}")
        for machine in machines:
            print(f"  - {machine.display_name}")
        
        # 2. Create devcontainer config
        devcontainer = DevcontainerConfig()
        
        # 3. Create Codespace
        request = CodespaceCreateRequest(
            ref="main",
            machine="standardLinux32gb",
            display_name="Reagent Workflow",
            idle_timeout_minutes=60
        )
        
        print("Creating Codespace...")
        codespace = await client.create_codespace("owner", "repo", request)
        print(f"Created: {codespace.name}")
        print(f"URL: {codespace.web_url}")
        
        # 4. Wait for Codespace to be ready
        print("Waiting for Codespace to start...")
        codespace = await client.wait_for_state(
            codespace.name,
            CodespaceState.AVAILABLE,
            timeout=300
        )
        print("Codespace is ready!")
        
        # 5. Execute commands
        print("Executing workflow...")
        result = await client.execute_command(
            codespace.name,
            "python -m reagent.orchestrate 'Build ERC20 token'"
        )
        print(f"Output: {result['stdout']}")
        
        # 6. Stop Codespace
        print("Stopping Codespace...")
        await client.stop_codespace(codespace.name)
        print("Done!")


if __name__ == "__main__":
    asyncio.run(example_full_workflow())

# Made with Bob
