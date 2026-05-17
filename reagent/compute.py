"""
Compute Abstraction Layer
Provides a unified interface for executing code across different backends:
- GitHub Codespaces (free tier, runs in user's GitHub)
- Nosana (premium tier, decentralized GPU compute)
- Local fallback (subprocess)
"""
import os
import asyncio
import subprocess
import logging
from enum import Enum
from typing import Optional, Dict, Any, Protocol, Set

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ComputeTier(str, Enum):
    """Available compute tiers."""
    CODESPACES = "codespaces"
    NOSANA = "nosana"
    LOCAL = "local"


class ComputeCapability(str, Enum):
    """Capabilities a compute backend can provide."""
    COMPILE = "compile"
    TEST = "test"
    GPU = "gpu"
    DEPLOY = "deploy"
    SHELL = "shell"


class ComputeResult(BaseModel):
    """Result from a compute execution."""
    exit_code: int
    stdout: str
    stderr: str
    success: bool
    backend: ComputeTier
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ComputeBackend(Protocol):
    """Protocol that every compute backend must implement."""

    @property
    def tier(self) -> ComputeTier: ...

    @property
    def capabilities(self) -> Set[ComputeCapability]: ...

    async def execute(
        self,
        command: str,
        cwd: str = "/workspace",
        env: Optional[Dict[str, str]] = None,
        timeout: int = 300,
    ) -> ComputeResult: ...

    async def upload_file(self, path: str, content: str) -> str:
        """Upload a file to the compute environment. Returns the path."""
        ...

    async def download_file(self, path: str) -> str:
        """Download a file from the compute environment. Returns content."""
        ...

    async def is_available(self) -> bool: ...


class CodespaceComputeBackend:
    """Compute backend using user's GitHub Codespace."""

    def __init__(self, client: Any, codespace_name: str):
        """
        Args:
            client: GitHubCodespacesClient instance
            codespace_name: Name of the Codespace to execute commands in
        """
        self._client = client
        self._codespace_name = codespace_name

    @property
    def tier(self) -> ComputeTier:
        return ComputeTier.CODESPACES

    @property
    def capabilities(self) -> Set[ComputeCapability]:
        return {ComputeCapability.COMPILE, ComputeCapability.TEST, ComputeCapability.DEPLOY, ComputeCapability.SHELL}

    async def execute(
        self,
        command: str,
        cwd: str = "/workspace",
        env: Optional[Dict[str, str]] = None,
        timeout: int = 300,
    ) -> ComputeResult:
        full_command = command
        if cwd and cwd != "/workspace":
            full_command = f"cd {cwd} && {command}"
        if env:
            env_prefix = " ".join(f"{k}={v}" for k, v in env.items())
            full_command = f"{env_prefix} {full_command}"

        result = await self._client.execute_command(self._codespace_name, full_command)
        return ComputeResult(
            exit_code=result.get("returncode", -1),
            stdout=result.get("stdout", ""),
            stderr=result.get("stderr", ""),
            success=result.get("success", False),
            backend=ComputeTier.CODESPACES,
            metadata={"codespace_name": self._codespace_name},
        )

    async def upload_file(self, path: str, content: str) -> str:
        import base64
        encoded = base64.b64encode(content.encode()).decode()
        command = f"echo '{encoded}' | base64 -d > {path}"
        await self.execute(command)
        return path

    async def download_file(self, path: str) -> str:
        result = await self.execute(f"cat {path}")
        return result.stdout

    async def is_available(self) -> bool:
        try:
            codespace = await self._client.get_codespace(self._codespace_name)
            return codespace.state == "Available"
        except Exception:
            return False


class NosanaComputeBackend:
    """Compute backend using Nosana decentralized compute network."""

    def __init__(self, client: Any):
        """
        Args:
            client: NosanaClient instance
        """
        self._client = client
        self._deployment_id: Optional[str] = None

    @property
    def tier(self) -> ComputeTier:
        return ComputeTier.NOSANA

    @property
    def capabilities(self) -> Set[ComputeCapability]:
        return {ComputeCapability.COMPILE, ComputeCapability.TEST, ComputeCapability.GPU, ComputeCapability.DEPLOY, ComputeCapability.SHELL}

    async def execute(
        self,
        command: str,
        cwd: str = "/workspace",
        env: Optional[Dict[str, str]] = None,
        timeout: int = 300,
    ) -> ComputeResult:
        """Execute via Nosana container deployment.

        Builds a job definition and creates a deployment, then polls for result.
        """
        import time as _time

        env_vars = env or {}
        if cwd and cwd != "/workspace":
            command = f"cd {cwd} && {command}"

        job = self._client.build_container_job(
            image="ubuntu:22.04",
            commands=[command],
            env_vars=env_vars,
            work_dir=cwd,
        )

        deployment = self._client.create_deployment(
            name=f"reagent-cmd-{int(_time.time())}",
            job_definition=job,
            strategy="SIMPLE",
        )
        self._deployment_id = deployment.get("id")

        # Start the deployment
        self._client.start_deployment(self._deployment_id)

        # Poll for completion
        max_wait = timeout
        poll_interval = 5
        elapsed = 0
        while elapsed < max_wait:
            status = self._client.get_deployment(self._deployment_id)
            state = status.get("status", "").lower()
            if state in ("completed", "stopped", "errored"):
                break
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        final = self._client.get_deployment(self._deployment_id)
        state = final.get("status", "unknown").lower()
        succeeded = state == "completed"

        # Cleanup
        try:
            self._client.archive_deployment(self._deployment_id)
        except Exception:
            pass

        return ComputeResult(
            exit_code=0 if succeeded else 1,
            stdout=str(final.get("result", "")),
            stderr="" if succeeded else str(final.get("error", state)),
            success=succeeded,
            backend=ComputeTier.NOSANA,
            metadata={"deployment_id": self._deployment_id},
        )

    async def upload_file(self, path: str, content: str) -> str:
        # Nosana jobs receive files via environment variables or embedded in commands
        import base64
        encoded = base64.b64encode(content.encode()).decode()
        await self.execute(f"echo '{encoded}' | base64 -d > {path}")
        return path

    async def download_file(self, path: str) -> str:
        result = await self.execute(f"cat {path}")
        return result.stdout

    async def is_available(self) -> bool:
        try:
            return self._client.health_check().get("status") != "error"
        except Exception:
            return False


class LocalComputeBackend:
    """Local fallback compute backend using subprocess."""

    @property
    def tier(self) -> ComputeTier:
        return ComputeTier.LOCAL

    @property
    def capabilities(self) -> Set[ComputeCapability]:
        return {ComputeCapability.COMPILE, ComputeCapability.TEST, ComputeCapability.SHELL}

    async def execute(
        self,
        command: str,
        cwd: str = "/workspace",
        env: Optional[Dict[str, str]] = None,
        timeout: int = 300,
    ) -> ComputeResult:
        full_env = {**os.environ, **(env or {})}
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd if os.path.isdir(cwd) else None,
                env=full_env,
                timeout=timeout,
            )
            return ComputeResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                success=result.returncode == 0,
                backend=ComputeTier.LOCAL,
            )
        except subprocess.TimeoutExpired:
            return ComputeResult(
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                success=False,
                backend=ComputeTier.LOCAL,
            )
        except Exception as e:
            return ComputeResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                success=False,
                backend=ComputeTier.LOCAL,
            )

    async def upload_file(self, path: str, content: str) -> str:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path

    async def download_file(self, path: str) -> str:
        with open(path, "r") as f:
            return f.read()

    async def is_available(self) -> bool:
        return True


class ComputeRouter:
    """Selects and manages the appropriate compute backend.

    Decision logic:
    1. If user has Codespaces connected AND task doesn't need GPU -> Codespaces
    2. If task needs GPU or user is premium -> Nosana
    3. If neither available -> local fallback
    """

    def __init__(self):
        self._codespaces_backend: Optional[CodespaceComputeBackend] = None
        self._nosana_backend: Optional[NosanaComputeBackend] = None
        self._local_backend: LocalComputeBackend = LocalComputeBackend()

    def set_codespaces_backend(self, backend: CodespaceComputeBackend) -> None:
        self._codespaces_backend = backend

    def set_nosana_backend(self, backend: NosanaComputeBackend) -> None:
        self._nosana_backend = backend

    def select_backend(
        self,
        required_capabilities: Optional[Set[ComputeCapability]] = None,
        user_tier: str = "free",
        github_connected: bool = False,
        nosana_connected: bool = False,
    ) -> Any:
        """Select the appropriate compute backend based on requirements and user tier.

        Args:
            required_capabilities: Set of capabilities needed for the task
            user_tier: "free" or "premium"
            github_connected: Whether user has GitHub Codespaces connected
            nosana_connected: Whether user has Nosana configured

        Returns:
            A ComputeBackend instance
        """
        caps = required_capabilities or set()
        needs_gpu = ComputeCapability.GPU in caps

        # GPU tasks always go to Nosana
        if needs_gpu:
            if self._nosana_backend:
                return self._nosana_backend
            logger.warning("GPU required but Nosana not available — falling back to local")

        # Free users with Codespaces connected -> Codespaces (zero cost)
        if user_tier == "free" and github_connected and self._codespaces_backend:
            return self._codespaces_backend

        # Premium users -> prefer Nosana
        if user_tier == "premium" and self._nosana_backend:
            return self._nosana_backend

        # Free user without Codespaces -> escalate to Nosana if available
        if user_tier == "free" and not github_connected and self._nosana_backend:
            return self._nosana_backend

        # Fallback: Codespaces if available, then local
        if self._codespaces_backend:
            return self._codespaces_backend

        return self._local_backend

    async def execute(
        self,
        command: str,
        required_capabilities: Optional[Set[ComputeCapability]] = None,
        user_tier: str = "free",
        github_connected: bool = False,
        nosana_connected: bool = False,
        **kwargs,
    ) -> ComputeResult:
        """Execute a command on the appropriate compute backend."""
        backend = self.select_backend(
            required_capabilities=required_capabilities,
            user_tier=user_tier,
            github_connected=github_connected,
            nosana_connected=nosana_connected,
        )
        return await backend.execute(command, **kwargs)


# Singleton
_compute_router: Optional[ComputeRouter] = None


def get_compute_router() -> ComputeRouter:
    global _compute_router
    if _compute_router is None:
        _compute_router = ComputeRouter()
    return _compute_router
