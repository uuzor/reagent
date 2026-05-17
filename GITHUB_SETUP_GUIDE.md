# GitHub Codespaces Integration - Complete Setup Guide

## Overview

This guide walks you through setting up GitHub Codespaces integration for Reagent, allowing users to run AI-powered smart contract development workflows in their own GitHub Codespaces.

## Prerequisites

1. **GitHub Account** with Codespaces access
2. **Python 3.11+**
3. **GitHub CLI** (`gh`) installed (optional, for command execution)
4. **OAuth App** registered on GitHub

## Step 1: Create GitHub OAuth App

### 1.1 Register OAuth App

1. Go to https://github.com/settings/developers
2. Click "New OAuth App"
3. Fill in details:
   - **Application name**: Reagent Smart Contract Agent
   - **Homepage URL**: https://your-domain.com
   - **Authorization callback URL**: https://your-domain.com/auth/github/callback
   - **Description**: AI-powered smart contract development in your Codespaces

4. Click "Register application"
5. Note down:
   - **Client ID**
   - **Client Secret** (generate if not shown)

### 1.2 Required Scopes

Your OAuth app needs these scopes:
- `codespace` - Create and manage Codespaces
- `repo` - Access repositories
- `workflow` - GitHub Actions (optional)
- `read:org` - Organization access (for org repos)

## Step 2: Environment Configuration

### 2.1 Create `.env` File

```bash
# GitHub OAuth Configuration
GITHUB_CLIENT_ID=your_client_id_here
GITHUB_CLIENT_SECRET=your_client_secret_here
GITHUB_REDIRECT_URI=https://your-domain.com/auth/github/callback

# Token Encryption
ENCRYPTION_KEY=your_32_byte_base64_encoded_key

# Optional: GitHub Personal Access Token (for testing)
GITHUB_TOKEN=ghp_your_personal_access_token
```

### 2.2 Generate Encryption Key

```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(f"ENCRYPTION_KEY={key.decode()}")
```

Or use command line:
```bash
python -c "from cryptography.fernet import Fernet; print(f'ENCRYPTION_KEY={Fernet.generate_key().decode()}')"
```

## Step 3: Install Dependencies

```bash
# Install required packages
pip install -r requirements.txt

# Verify installation
python -c "import aiohttp, cryptography; print('✓ Dependencies installed')"
```

### Required Packages

```txt
cryptography>=41.0.0  # Token encryption
PyGithub>=2.1.1       # GitHub API client
aiohttp>=3.9.0        # Async HTTP
```

## Step 4: Install GitHub CLI (Optional)

For command execution in Codespaces:

### macOS
```bash
brew install gh
```

### Linux
```bash
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh
```

### Windows
```powershell
winget install --id GitHub.cli
```

### Authenticate GitHub CLI
```bash
gh auth login
```

## Step 5: Test the Integration

### 5.1 Test GitHub API Connection

```python
import asyncio
from github_codespaces_full_client import GitHubCodespacesClient
import os

async def test_connection():
    token = os.getenv("GITHUB_TOKEN")
    
    async with GitHubCodespacesClient(token) as client:
        # List existing Codespaces
        result = await client.list_codespaces()
        print(f"✓ Connected! You have {result['total_count']} Codespaces")
        
        # List available machines
        machines = await client.list_machines("your-username", "your-repo")
        print(f"✓ Available machines: {len(machines)}")

asyncio.run(test_connection())
```

### 5.2 Test Codespace Creation

```python
import asyncio
from github_codespaces_full_client import (
    GitHubCodespacesClient,
    CodespaceCreateRequest,
    CodespaceState
)
import os

async def test_create_codespace():
    token = os.getenv("GITHUB_TOKEN")
    
    async with GitHubCodespacesClient(token) as client:
        # Create Codespace
        request = CodespaceCreateRequest(
            ref="main",
            machine="standardLinux32gb",
            display_name="Test Reagent Codespace",
            idle_timeout_minutes=30
        )
        
        print("Creating Codespace...")
        codespace = await client.create_codespace(
            "your-username",
            "your-repo",
            request
        )
        
        print(f"✓ Created: {codespace.name}")
        print(f"  URL: {codespace.web_url}")
        print(f"  State: {codespace.state}")
        
        # Wait for it to be ready
        print("Waiting for Codespace to start...")
        codespace = await client.wait_for_state(
            codespace.name,
            CodespaceState.AVAILABLE,
            timeout=300
        )
        
        print(f"✓ Codespace is ready!")
        print(f"  Open: {codespace.web_url}")
        
        # Cleanup
        input("Press Enter to stop and delete Codespace...")
        await client.stop_codespace(codespace.name)
        await client.delete_codespace(codespace.name)
        print("✓ Cleaned up")

asyncio.run(test_create_codespace())
```

## Step 6: Integrate with Reagent

### 6.1 Register Router

In `main.py`:

```python
from routers.github_codespace_router import github_router

# Register router
app.include_router(github_router)
```

### 6.2 Test API Endpoints

```bash
# Start Reagent server
python -m reagent.main

# In another terminal, test endpoints:

# Check integration status
curl http://localhost:8000/github/check_github_integration

# Connect GitHub (with OAuth code)
curl -X POST http://localhost:8000/github/connect_github \
  -H "Content-Type: application/json" \
  -d '{"code": "your_oauth_code", "user_id": "user123"}'

# Create workflow in Codespace
curl -X POST http://localhost:8000/github/create_codespace_workflow \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "requirements": "Build an ERC20 token with staking",
    "repository": "username/my-project",
    "branch": "main"
  }'
```

## Step 7: OAuth Flow Implementation

### 7.1 Frontend Integration

```javascript
// Redirect user to GitHub OAuth
function connectGitHub() {
  const clientId = 'your_client_id';
  const redirectUri = 'https://your-domain.com/auth/github/callback';
  const scope = 'codespace repo workflow';
  
  window.location.href = `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&scope=${scope}`;
}

// Handle callback
async function handleGitHubCallback() {
  const urlParams = new URLSearchParams(window.location.search);
  const code = urlParams.get('code');
  
  if (code) {
    // Send code to backend
    const response = await fetch('/github/connect_github', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        code: code,
        user_id: getCurrentUserId()
      })
    });
    
    const result = await response.json();
    if (result.success) {
      alert('GitHub connected successfully!');
    }
  }
}
```

### 7.2 Backend OAuth Exchange

```python
import aiohttp

async def exchange_code_for_token(code: str) -> str:
    """Exchange OAuth code for access token."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            'https://github.com/login/oauth/access_token',
            json={
                'client_id': os.getenv('GITHUB_CLIENT_ID'),
                'client_secret': os.getenv('GITHUB_CLIENT_SECRET'),
                'code': code
            },
            headers={'Accept': 'application/json'}
        ) as response:
            data = await response.json()
            return data['access_token']
```

## Step 8: Production Deployment

### 8.1 Security Checklist

- [ ] Use HTTPS for all endpoints
- [ ] Store tokens encrypted in database (not in-memory)
- [ ] Implement token rotation
- [ ] Add rate limiting
- [ ] Enable audit logging
- [ ] Use environment-specific secrets
- [ ] Implement CSRF protection
- [ ] Validate all user inputs
- [ ] Set up monitoring and alerts

### 8.2 Scaling Considerations

1. **Token Storage**: Use Redis or PostgreSQL with encryption
2. **Rate Limiting**: Implement per-user rate limits
3. **Monitoring**: Track Codespace creation/usage
4. **Cost Tracking**: Monitor user quota usage
5. **Cleanup**: Auto-delete old Codespaces
6. **Caching**: Cache machine types and repository info

### 8.3 Monitoring Setup

```python
# Add metrics
from prometheus_client import Counter, Histogram

codespace_created = Counter('codespaces_created_total', 'Total Codespaces created')
codespace_duration = Histogram('codespace_duration_seconds', 'Codespace lifetime')
workflow_success = Counter('workflows_success_total', 'Successful workflows')
workflow_failure = Counter('workflows_failure_total', 'Failed workflows')
```

## Step 9: User Documentation

### 9.1 User Guide

Create user-facing documentation:

```markdown
# Using Reagent with GitHub Codespaces

## Quick Start

1. Click "Connect GitHub" button
2. Authorize Reagent to access your Codespaces
3. Select a repository
4. Enter your smart contract requirements
5. Click "Create Workflow"
6. Your Codespace will be created automatically
7. Open the Codespace URL to see your development environment
8. Review and deploy the generated code

## Benefits

- **Your Environment**: Code runs in your GitHub account
- **Full Control**: Inspect and modify at any time
- **Secure**: No code leaves your GitHub
- **Integrated**: Direct commits to your repository
- **Free Tier**: 120 core-hours/month included
```

## Troubleshooting

### Common Issues

**1. "GitHub CLI not found"**
```bash
# Install GitHub CLI
brew install gh  # macOS
# or follow instructions above for other OS
```

**2. "Invalid token" error**
```bash
# Check token scopes
gh auth status

# Re-authenticate
gh auth login
```

**3. "Codespace creation failed"**
- Check repository permissions
- Verify Codespaces quota
- Check devcontainer.json syntax
- Review GitHub status page

**4. "Rate limit exceeded"**
- Wait for rate limit reset
- Use authenticated requests
- Implement exponential backoff

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Support

- **Documentation**: https://docs.github.com/en/codespaces
- **API Reference**: https://docs.github.com/en/rest/codespaces
- **GitHub CLI**: https://cli.github.com/manual/gh_codespace
- **Issues**: https://github.com/your-org/reagent/issues

## Next Steps

1. ✅ Complete setup
2. ✅ Test integration
3. ✅ Deploy to production
4. 📚 Create user documentation
5. 🎨 Build frontend UI
6. 📊 Set up monitoring
7. 🚀 Launch to users!