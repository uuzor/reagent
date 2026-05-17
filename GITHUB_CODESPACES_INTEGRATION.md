# GitHub Codespaces Integration Design

## Overview

Enable users to connect their GitHub accounts and run Reagent agent workflows directly in their own GitHub Codespaces, providing isolated, secure execution environments with full GitHub integration.

## Architecture

```
User → Reagent API → GitHub OAuth → User's Codespace → Agent Execution → GitHub Repo
```

### Key Components

1. **GitHub OAuth Integration** - Authenticate users and get repository access
2. **Codespace Manager** - Create, manage, and execute code in Codespaces
3. **Agent Executor** - Run Reagent workflows in the Codespace environment
4. **GitHub API Client** - Interact with GitHub repositories and Codespaces API

## Implementation Plan

### Phase 1: GitHub OAuth & Repository Access

#### 1.1 GitHub OAuth Flow
```python
# User clicks "Connect GitHub"
# → Redirect to GitHub OAuth
# → User authorizes app
# → Callback with access token
# → Store token securely (encrypted)
```

**Required Scopes:**
- `repo` - Full repository access
- `codespace` - Codespace management
- `workflow` - GitHub Actions access
- `user:email` - User identification

#### 1.2 GitHub Client Extension
```python
class GitHubCodespaceClient:
    """Extended GitHub client with Codespace support."""
    
    def __init__(self, access_token: str):
        self.token = access_token
        self.api_base = "https://api.github.com"
        
    async def create_codespace(
        self, 
        repo: str, 
        branch: str = "main",
        machine: str = "basicLinux32gb"
    ) -> dict:
        """Create a new Codespace for the repository."""
        
    async def get_codespace(self, codespace_id: str) -> dict:
        """Get Codespace details."""
        
    async def execute_in_codespace(
        self, 
        codespace_id: str, 
        command: str
    ) -> dict:
        """Execute command in Codespace via SSH/API."""
        
    async def stop_codespace(self, codespace_id: str):
        """Stop a running Codespace."""
        
    async def delete_codespace(self, codespace_id: str):
        """Delete a Codespace."""
```

### Phase 2: Codespace Workflow Execution

#### 2.1 Workflow Execution Model
```python
class CodespaceWorkflow(BaseModel):
    """Workflow execution in user's Codespace."""
    workflow_id: str
    user_github_token: str
    repository: str  # "username/repo"
    branch: str = "reagent-workflow"
    codespace_id: Optional[str] = None
    status: str = "pending"  # pending, creating, running, completed, failed
    execution_logs: List[str] = []
```

#### 2.2 Codespace Orchestrator
```python
class CodespaceOrchestrator:
    """Orchestrate agent workflows in user's Codespace."""
    
    async def setup_codespace(self, workflow: CodespaceWorkflow) -> str:
        """
        1. Create Codespace in user's repo
        2. Install Reagent dependencies
        3. Clone workflow configuration
        4. Return Codespace ID
        """
        
    async def execute_workflow(
        self, 
        workflow: CodespaceWorkflow,
        requirements: str
    ) -> dict:
        """
        Execute full contract development workflow in Codespace:
        1. Run ideation in Codespace
        2. Generate code in Codespace
        3. Run tests in Codespace
        4. Audit in Codespace
        5. Deploy from Codespace
        6. Monitor from Codespace
        """
        
    async def stream_logs(self, codespace_id: str) -> AsyncIterator[str]:
        """Stream execution logs from Codespace."""
```

### Phase 3: Security & Isolation

#### 3.1 Token Management
```python
class SecureTokenStore:
    """Encrypted token storage."""
    
    def encrypt_token(self, token: str, user_id: str) -> str:
        """Encrypt GitHub token with user-specific key."""
        
    def decrypt_token(self, encrypted: str, user_id: str) -> str:
        """Decrypt GitHub token."""
        
    def revoke_token(self, user_id: str):
        """Revoke and delete stored token."""
```

#### 3.2 Sandboxing
- Each user gets their own Codespace
- Workflows run in isolated containers
- No access to other users' data
- Automatic cleanup after workflow completion

### Phase 4: API Endpoints

```python
# New router: github_codespace_router.py

@github_router.post("/connect")
async def connect_github(code: str) -> dict:
    """
    Exchange OAuth code for access token.
    Store encrypted token for user.
    """

@github_router.post("/workflows/create")
async def create_codespace_workflow(
    requirements: str,
    repository: str,
    branch: str = "main"
) -> dict:
    """
    Create new workflow in user's Codespace.
    Returns workflow_id and Codespace URL.
    """

@github_router.get("/workflows/{workflow_id}/status")
async def get_workflow_status(workflow_id: str) -> dict:
    """Get real-time workflow status and logs."""

@github_router.get("/workflows/{workflow_id}/logs")
async def stream_workflow_logs(workflow_id: str):
    """WebSocket endpoint for live log streaming."""

@github_router.post("/workflows/{workflow_id}/stop")
async def stop_workflow(workflow_id: str):
    """Stop running workflow and cleanup Codespace."""

@github_router.delete("/disconnect")
async def disconnect_github():
    """Revoke GitHub access and cleanup."""
```

## User Flow

### 1. Initial Setup
```
User → "Connect GitHub" button
     → GitHub OAuth page
     → Authorize Reagent
     → Redirect back with token
     → Token stored (encrypted)
     → User sees "Connected to GitHub" ✓
```

### 2. Create Workflow
```
User → Enter contract requirements
     → Select GitHub repository
     → Click "Run in My Codespace"
     → Reagent creates Codespace
     → Workflow starts executing
     → User sees live logs
     → Results pushed to GitHub repo
```

### 3. Monitor Execution
```
User → View workflow dashboard
     → See Codespace status
     → Stream live logs
     → View GitHub commits/PRs
     → Access Codespace directly (optional)
```

## Benefits

### For Users
✅ **Full Control** - Code runs in their own environment
✅ **Security** - No code leaves their GitHub account
✅ **Transparency** - Can inspect Codespace at any time
✅ **Integration** - Direct commits to their repo
✅ **Isolation** - Each workflow in separate Codespace
✅ **Cost Control** - Uses their GitHub Codespace quota

### For Reagent
✅ **Scalability** - No infrastructure costs for execution
✅ **Security** - No liability for user code
✅ **Compliance** - User data stays in their GitHub
✅ **Flexibility** - Users can customize Codespace config

## Technical Requirements

### Dependencies
```python
# requirements.txt additions
PyGithub>=2.1.1  # GitHub API client
cryptography>=41.0.0  # Token encryption
websockets>=12.0  # Log streaming
paramiko>=3.3.0  # SSH to Codespace (optional)
```

### Environment Variables
```bash
GITHUB_CLIENT_ID=your_oauth_app_client_id
GITHUB_CLIENT_SECRET=your_oauth_app_secret
GITHUB_REDIRECT_URI=https://your-app.com/auth/github/callback
ENCRYPTION_KEY=your_encryption_key_for_tokens
```

### GitHub App Configuration
1. Create GitHub OAuth App
2. Set redirect URI
3. Request required scopes
4. Enable Codespace API access

## Implementation Steps

### Step 1: GitHub OAuth (Week 1)
- [ ] Create GitHub OAuth app
- [ ] Implement OAuth flow
- [ ] Token encryption/storage
- [ ] User authentication

### Step 2: Codespace Management (Week 2)
- [ ] GitHub Codespace API client
- [ ] Create/start/stop Codespaces
- [ ] Execute commands in Codespace
- [ ] Log streaming

### Step 3: Workflow Integration (Week 3)
- [ ] Adapt orchestrator for Codespace execution
- [ ] Install Reagent in Codespace
- [ ] Execute workflow stages remotely
- [ ] Commit results to GitHub

### Step 4: UI & Monitoring (Week 4)
- [ ] Connect GitHub button
- [ ] Workflow dashboard
- [ ] Live log viewer
- [ ] Codespace status display

## Example Usage

```python
# User connects GitHub
await github_router.connect_github(oauth_code)

# Create workflow in user's Codespace
workflow = await github_router.create_codespace_workflow(
    requirements="Build an ERC20 token with staking",
    repository="user/my-defi-project",
    branch="main"
)

# Monitor execution
async for log in github_router.stream_workflow_logs(workflow["workflow_id"]):
    print(log)

# Results automatically committed to user's repo
# User can access Codespace at: workflow["codespace_url"]
```

## Security Considerations

1. **Token Encryption** - All GitHub tokens encrypted at rest
2. **Scope Limitation** - Request minimal required scopes
3. **Token Rotation** - Support token refresh
4. **Audit Logging** - Log all Codespace operations
5. **Rate Limiting** - Respect GitHub API limits
6. **Cleanup** - Auto-delete Codespaces after completion
7. **User Consent** - Clear permissions explanation

## Cost Model

### For Users
- Uses their GitHub Codespace quota (free tier: 120 core-hours/month)
- Can upgrade GitHub plan for more quota
- Pay only for what they use

### For Reagent
- No execution infrastructure costs
- Only API/orchestration costs
- Scales infinitely with users

## Future Enhancements

1. **Multi-Cloud Support** - AWS Cloud9, Azure DevSpaces
2. **Custom Devcontainers** - User-defined environments
3. **Collaborative Workflows** - Multiple users in same Codespace
4. **Workflow Templates** - Pre-configured Codespace setups
5. **CI/CD Integration** - Trigger workflows from GitHub Actions
6. **VS Code Extension** - Direct integration with VS Code

## Conclusion

GitHub Codespaces integration provides a secure, scalable, and user-controlled execution environment for Reagent workflows. Users maintain full control over their code and infrastructure while benefiting from Reagent's AI-powered orchestration.