"""
GitHub Codespaces Integration Router
API endpoints for connecting GitHub and running workflows in user's Codespaces.
"""
from agentfield import AgentRouter
from pydantic import BaseModel, Field
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import asyncio

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from github_codespace_client import (
        GitHubCodespaceClient,
        CodespaceOrchestrator,
        CodespaceConfig,
        CodespaceWorkflow,
        SecureTokenStore
    )
except ImportError:
    # Fallback if cryptography not installed
    GitHubCodespaceClient = None
    print("⚠️  GitHub Codespaces integration requires: pip install cryptography PyGithub aiohttp")


# Router for GitHub Codespaces integration
github_router = AgentRouter(prefix="github", tags=["github", "codespaces", "integration"])

# Global token store (in production, use Redis or database)
_token_store: Optional[SecureTokenStore] = None
_active_workflows: Dict[str, CodespaceWorkflow] = {}


def _get_token_store() -> SecureTokenStore:
    """Get or create token store."""
    global _token_store
    if _token_store is None:
        _token_store = SecureTokenStore()
    return _token_store


class GitHubConnectRequest(BaseModel):
    """Request to connect GitHub account."""
    code: str = Field(description="OAuth authorization code from GitHub")
    user_id: str = Field(description="User identifier")


class GitHubConnectResponse(BaseModel):
    """Response after connecting GitHub."""
    success: bool
    user_id: str
    message: str
    scopes: list[str] = []


class CreateWorkflowRequest(BaseModel):
    """Request to create workflow in Codespace."""
    user_id: str = Field(description="User identifier")
    requirements: str = Field(description="Contract requirements")
    repository: str = Field(description="GitHub repository (owner/repo)")
    branch: str = Field(default="main", description="Base branch")
    machine: str = Field(default="basicLinux32gb", description="Codespace machine type")


class WorkflowStatusResponse(BaseModel):
    """Workflow status response."""
    workflow_id: str
    status: str
    codespace_url: Optional[str] = None
    branch: str
    logs: list[str] = []


@github_router.skill(tags=["oauth", "connect"])
async def connect_github(request: GitHubConnectRequest) -> dict:
    """
    Connect user's GitHub account via OAuth.
    
    Flow:
    1. User clicks "Connect GitHub" → redirected to GitHub OAuth
    2. User authorizes → GitHub redirects back with code
    3. Exchange code for access token
    4. Store encrypted token
    
    Note: In production, implement full OAuth flow with client_id/secret
    """
    if GitHubCodespaceClient is None:
        return {
            "success": False,
            "error": "GitHub integration not available. Install: pip install cryptography PyGithub aiohttp"
        }
    
    # In production, exchange code for token via GitHub OAuth
    # For now, assume code is the token (for testing)
    github_token = request.code
    
    # Store encrypted token
    token_store = _get_token_store()
    token_store.encrypt_token(github_token, request.user_id)
    
    github_router.app.note(
        f"GitHub connected for user: {request.user_id}",
        tags=["github", "oauth"]
    )
    
    return {
        "success": True,
        "user_id": request.user_id,
        "message": "GitHub account connected successfully",
        "scopes": ["repo", "codespace", "workflow"]
    }


@github_router.reasoner(tags=["workflow", "create", "codespace"])
async def create_codespace_workflow(request: CreateWorkflowRequest) -> dict:
    """
    Create new workflow in user's GitHub Codespace.
    
    Steps:
    1. Get user's GitHub token
    2. Create Codespace in their repository
    3. Setup workflow configuration
    4. Return workflow ID and Codespace URL
    """
    if GitHubCodespaceClient is None:
        return {
            "success": False,
            "error": "GitHub integration not available"
        }
    
    # Get user's token
    token_store = _get_token_store()
    github_token = token_store.decrypt_token(request.user_id)
    
    if not github_token:
        return {
            "success": False,
            "error": "GitHub not connected. Please connect your GitHub account first."
        }
    
    # Create workflow
    import time
    workflow_id = f"wf_{int(time.time())}"
    workflow = CodespaceWorkflow(
        workflow_id=workflow_id,
        user_id=request.user_id,
        repository=request.repository,
        branch=f"reagent-{workflow_id}"
    )
    
    # Initialize GitHub client
    github_client = GitHubCodespaceClient(github_token)
    orchestrator = CodespaceOrchestrator(github_client)
    
    # Setup Codespace
    config = CodespaceConfig(
        repository=request.repository,
        branch=request.branch,
        machine=request.machine
    )
    
    try:
        workflow.execution_logs.append("🚀 Starting Codespace setup...")
        codespace_name = await orchestrator.setup_codespace(workflow, config)
        
        # Execute workflow via commits
        result = await orchestrator.execute_workflow_via_commits(
            workflow,
            requirements=request.requirements
        )
        
        # Store workflow
        _active_workflows[workflow_id] = workflow
        
        github_router.app.note(
            f"Codespace workflow created: {workflow_id}",
            tags=["github", "workflow", "codespace"]
        )
        
        return {
            "success": True,
            "workflow_id": workflow_id,
            "codespace_url": workflow.codespace_url,
            "codespace_name": codespace_name,
            "branch": workflow.branch,
            "repository": request.repository,
            "status": workflow.status,
            "message": "Codespace created! Open the URL to start development.",
            "logs": workflow.execution_logs
        }
        
    except Exception as e:
        workflow.status = "failed"
        workflow.execution_logs.append(f"❌ Error: {str(e)}")
        
        return {
            "success": False,
            "workflow_id": workflow_id,
            "error": str(e),
            "logs": workflow.execution_logs
        }


@github_router.skill(tags=["workflow", "status"])
def get_workflow_status(workflow_id: str) -> dict:
    """
    Get status of a workflow.
    Returns current status, logs, and Codespace URL.
    """
    workflow = _active_workflows.get(workflow_id)
    
    if not workflow:
        return {
            "success": False,
            "error": f"Workflow {workflow_id} not found"
        }
    
    return {
        "success": True,
        "workflow_id": workflow.workflow_id,
        "status": workflow.status,
        "codespace_url": workflow.codespace_url,
        "branch": workflow.branch,
        "repository": workflow.repository,
        "logs": workflow.execution_logs,
        "created_at": workflow.created_at,
        "completed_at": workflow.completed_at
    }


@github_router.skill(tags=["workflow", "list"])
def list_user_workflows(user_id: str) -> dict:
    """List all workflows for a user."""
    user_workflows = [
        {
            "workflow_id": wf.workflow_id,
            "status": wf.status,
            "repository": wf.repository,
            "codespace_url": wf.codespace_url
        }
        for wf in _active_workflows.values()
        if wf.user_id == user_id
    ]
    
    return {
        "success": True,
        "user_id": user_id,
        "workflows": user_workflows,
        "total": len(user_workflows)
    }


@github_router.skill(tags=["workflow", "stop"])
async def stop_workflow(workflow_id: str) -> dict:
    """
    Stop a running workflow and cleanup Codespace.
    """
    workflow = _active_workflows.get(workflow_id)
    
    if not workflow:
        return {
            "success": False,
            "error": f"Workflow {workflow_id} not found"
        }
    
    if GitHubCodespaceClient is None:
        return {
            "success": False,
            "error": "GitHub integration not available"
        }
    
    # Get user's token
    token_store = _get_token_store()
    github_token = token_store.decrypt_token(workflow.user_id)
    
    if not github_token:
        return {
            "success": False,
            "error": "GitHub token not found"
        }
    
    try:
        github_client = GitHubCodespaceClient(github_token)
        orchestrator = CodespaceOrchestrator(github_client)
        
        await orchestrator.cleanup_codespace(workflow)
        workflow.status = "stopped"
        
        return {
            "success": True,
            "workflow_id": workflow_id,
            "status": "stopped",
            "message": "Workflow stopped and Codespace cleaned up"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@github_router.skill(tags=["github", "disconnect"])
def disconnect_github(user_id: str) -> dict:
    """
    Disconnect GitHub account and revoke stored token.
    """
    token_store = _get_token_store()
    token_store.revoke_token(user_id)
    
    github_router.app.note(
        f"GitHub disconnected for user: {user_id}",
        tags=["github", "disconnect"]
    )
    
    return {
        "success": True,
        "user_id": user_id,
        "message": "GitHub account disconnected"
    }


@github_router.skill(tags=["health", "github"])
def check_github_integration() -> dict:
    """
    Check if GitHub integration is properly configured.
    """
    has_client_id = bool(os.getenv("GITHUB_CLIENT_ID"))
    has_client_secret = bool(os.getenv("GITHUB_CLIENT_SECRET"))
    has_encryption_key = bool(os.getenv("ENCRYPTION_KEY"))
    has_dependencies = GitHubCodespaceClient is not None
    
    return {
        "available": has_dependencies,
        "configured": has_client_id and has_client_secret,
        "encryption_enabled": has_encryption_key,
        "dependencies_installed": has_dependencies,
        "environment": {
            "GITHUB_CLIENT_ID": "✓" if has_client_id else "✗",
            "GITHUB_CLIENT_SECRET": "✓" if has_client_secret else "✗",
            "ENCRYPTION_KEY": "✓" if has_encryption_key else "✗"
        },
        "required_packages": [
            "cryptography",
            "PyGithub", 
            "aiohttp"
        ]
    }


# Example usage documentation
@github_router.skill(tags=["docs", "example"])
def get_usage_example() -> dict:
    """
    Get example usage of GitHub Codespaces integration.
    """
    return {
        "title": "GitHub Codespaces Integration - Quick Start",
        "steps": [
            {
                "step": 1,
                "action": "Connect GitHub",
                "endpoint": "POST /github/connect_github",
                "payload": {
                    "code": "oauth_code_from_github",
                    "user_id": "user123"
                }
            },
            {
                "step": 2,
                "action": "Create Workflow",
                "endpoint": "POST /github/create_codespace_workflow",
                "payload": {
                    "user_id": "user123",
                    "requirements": "Build an ERC20 token with staking",
                    "repository": "username/my-defi-project",
                    "branch": "main"
                }
            },
            {
                "step": 3,
                "action": "Check Status",
                "endpoint": "GET /github/get_workflow_status?workflow_id=wf_123"
            },
            {
                "step": 4,
                "action": "Open Codespace",
                "description": "Click the codespace_url from the response to open your development environment"
            }
        ],
        "benefits": [
            "Code runs in your own GitHub account",
            "Full control over execution environment",
            "Direct integration with your repositories",
            "Secure - no code leaves your GitHub",
            "Uses your GitHub Codespace quota"
        ]
    }


# Made with Bob