# GitHub Codespaces API Research & Implementation Guide

## Official GitHub Codespaces API Documentation

### API Endpoints (REST API v3)

#### 1. Codespaces Management

**List Codespaces for User**
```
GET /user/codespaces
```
Response includes: id, name, state, machine, repository, git_status, etc.

**Get a Codespace**
```
GET /user/codespaces/{codespace_name}
```

**Create Codespace**
```
POST /repos/{owner}/{repo}/codespaces
```
Body:
```json
{
  "ref": "main",
  "location": "WestUs2",
  "machine": "standardLinux32gb",
  "devcontainer_path": ".devcontainer/devcontainer.json",
  "multi_repo_permissions_opt_out": false,
  "working_directory": "src",
  "idle_timeout_minutes": 60,
  "display_name": "My Codespace",
  "retention_period_minutes": 4320
}
```

**Start Codespace**
```
POST /user/codespaces/{codespace_name}/start
```

**Stop Codespace**
```
POST /user/codespaces/{codespace_name}/stop
```

**Delete Codespace**
```
DELETE /user/codespaces/{codespace_name}
```

#### 2. Codespace Secrets

**List Secrets**
```
GET /user/codespaces/secrets
```

**Create/Update Secret**
```
PUT /user/codespaces/secrets/{secret_name}
```

#### 3. Machine Types

**List Available Machines**
```
GET /repos/{owner}/{repo}/codespaces/machines
```

Response:
```json
{
  "machines": [
    {
      "name": "standardLinux32gb",
      "display_name": "4 cores, 8 GB RAM, 32 GB storage",
      "operating_system": "linux",
      "storage_in_bytes": 34359738368,
      "memory_in_bytes": 8589934592,
      "cpus": 4
    }
  ]
}
```

#### 4. Codespace Access

**Get Codespace Token**
```
GET /user/codespaces/{codespace_name}/token
```
Returns a token for accessing the Codespace via SSH or web.

### GitHub CLI Integration

The GitHub CLI (`gh`) provides Codespace commands:

```bash
# Create codespace
gh codespace create --repo owner/repo --branch main

# List codespaces
gh codespace list

# SSH into codespace
gh codespace ssh --codespace name

# Execute command
gh codespace ssh --codespace name -- command

# Port forward
gh codespace ports forward 3000:3000 --codespace name

# Stop codespace
gh codespace stop --codespace name

# Delete codespace
gh codespace delete --codespace name
```

### Codespace States

- `Unknown` - Initial state
- `Created` - Codespace created but not started
- `Queued` - Waiting to start
- `Provisioning` - Being provisioned
- `Available` - Running and ready
- `Awaiting` - Waiting for user action
- `Unavailable` - Not available
- `Deleted` - Deleted
- `Moved` - Moved to different region
- `Shutdown` - Stopped
- `Archived` - Archived
- `Starting` - Starting up
- `ShuttingDown` - Shutting down
- `Failed` - Failed to start
- `Exporting` - Being exported
- `Updating` - Being updated
- `Rebuilding` - Rebuilding container

### Devcontainer Configuration

Codespaces use `.devcontainer/devcontainer.json` for configuration:

```json
{
  "name": "Reagent Smart Contract Development",
  "image": "mcr.microsoft.com/devcontainers/python:3.11",
  "features": {
    "ghcr.io/devcontainers/features/node:1": {
      "version": "18"
    },
    "ghcr.io/devcontainers/features/docker-in-docker:2": {}
  },
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "juanblanco.solidity"
      ],
      "settings": {
        "python.defaultInterpreterPath": "/usr/local/bin/python"
      }
    }
  },
  "postCreateCommand": "pip install -r requirements.txt",
  "remoteUser": "vscode",
  "forwardPorts": [8000, 3000],
  "portsAttributes": {
    "8000": {
      "label": "API Server",
      "onAutoForward": "notify"
    }
  }
}
```

### OAuth Scopes Required

For Codespaces integration:
- `codespace` - Full Codespace access
- `repo` - Repository access
- `workflow` - GitHub Actions (optional)
- `read:org` - Organization access (for org repos)

### Rate Limits

- **REST API**: 5,000 requests/hour (authenticated)
- **Codespace Creation**: Limited by user's quota
- **Codespace Usage**: Based on GitHub plan
  - Free: 120 core-hours/month, 15 GB storage
  - Pro: 180 core-hours/month, 20 GB storage
  - Team: 180 core-hours/month per user
  - Enterprise: Custom

### WebSocket Connection

Codespaces support WebSocket connections for real-time communication:

```
wss://codespace-name.githubpreview.dev/
```

### SSH Access

SSH to Codespace:
```bash
ssh -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    codespace-name.githubpreview.dev
```

### Port Forwarding

Codespaces automatically forward ports. Access via:
```
https://codespace-name-port.githubpreview.dev
```

## Implementation Strategy

### Phase 1: Core API Client
1. Implement all REST API endpoints
2. Handle authentication with OAuth tokens
3. Implement retry logic and rate limiting
4. Add comprehensive error handling

### Phase 2: Codespace Lifecycle Management
1. Create with custom devcontainer
2. Monitor state transitions
3. Auto-start/stop based on usage
4. Cleanup on completion

### Phase 3: Command Execution
1. Use GitHub CLI for SSH access
2. Execute commands remotely
3. Stream output in real-time
4. Handle long-running processes

### Phase 4: Integration with Reagent
1. Setup Reagent in Codespace
2. Execute workflow stages
3. Commit results to repository
4. Monitor and log execution

## Security Considerations

1. **Token Storage**: Encrypt tokens at rest
2. **Token Rotation**: Support token refresh
3. **Scope Limitation**: Request minimal scopes
4. **Audit Logging**: Log all operations
5. **User Isolation**: Each user gets own Codespace
6. **Secret Management**: Use Codespace secrets for sensitive data
7. **Network Security**: Use HTTPS/WSS only
8. **Cleanup**: Auto-delete after completion

## Best Practices

1. **Devcontainer**: Always provide custom devcontainer.json
2. **Idle Timeout**: Set reasonable timeout (30-60 min)
3. **Machine Size**: Start with smallest, scale up if needed
4. **Retention**: Set retention period for debugging
5. **Monitoring**: Track Codespace state changes
6. **Error Handling**: Graceful degradation
7. **User Feedback**: Show progress and logs
8. **Cost Awareness**: Inform users of quota usage

## Example Workflow

```python
# 1. User connects GitHub
token = oauth_flow()

# 2. Create Codespace with custom devcontainer
codespace = create_codespace(
    repo="user/project",
    devcontainer={
        "image": "reagent/smart-contract-dev",
        "postCreateCommand": "pip install reagent"
    }
)

# 3. Wait for Codespace to be ready
wait_for_state(codespace, "Available")

# 4. Execute workflow
result = execute_via_gh_cli(
    codespace,
    "python -m reagent.orchestrate 'Build ERC20 token'"
)

# 5. Stream logs
for log in stream_logs(codespace):
    print(log)

# 6. Commit results
commit_to_repo(codespace, "Generated smart contract")

# 7. Cleanup
stop_codespace(codespace)
```

## Testing Strategy

1. **Unit Tests**: Mock GitHub API responses
2. **Integration Tests**: Use test repository
3. **E2E Tests**: Full workflow with real Codespace
4. **Load Tests**: Multiple concurrent Codespaces
5. **Error Tests**: Network failures, timeouts, etc.

## Monitoring & Observability

1. **Metrics**:
   - Codespace creation time
   - Workflow execution time
   - Success/failure rates
   - Quota usage per user

2. **Logging**:
   - API calls
   - State transitions
   - Errors and exceptions
   - User actions

3. **Alerts**:
   - Quota exceeded
   - Creation failures
   - Long-running workflows
   - Unusual activity

## Cost Optimization

1. **Auto-stop**: Stop after idle timeout
2. **Right-sizing**: Use appropriate machine size
3. **Cleanup**: Delete after completion
4. **Prebuilds**: Use prebuilt containers
5. **Caching**: Cache dependencies
6. **Monitoring**: Track usage patterns

## References

- [GitHub Codespaces API](https://docs.github.com/en/rest/codespaces)
- [GitHub CLI Codespaces](https://cli.github.com/manual/gh_codespace)
- [Devcontainer Spec](https://containers.dev/)
- [OAuth Apps](https://docs.github.com/en/developers/apps/building-oauth-apps)