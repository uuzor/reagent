# Nosana Integration Documentation

## Overview

Nosana is a decentralized GPU/compute network that provides on-demand container environments for running computationally intensive tasks. This integration enables Reagent to leverage Nosana's infrastructure for smart contract compilation, testing, and other compute-heavy operations.

**API Base URL:** `https://dashboard.k8s.prd.nos.ci/api`

## Architecture

### Deployment-Based System

Nosana uses a **deployment-based architecture** rather than simple job execution:

1. **Markets** - Compute resource pools with different pricing and capabilities
2. **Vaults** - Payment accounts funded with SOL/NOS tokens
3. **Deployments** - Long-running container environments
4. **Revisions** - Updates to deployment configurations
5. **Jobs** - Individual task executions within deployments

### Workflow

```
1. Select Market → 2. Create/Select Vault → 3. Create Deployment → 
4. Start Deployment → 5. Monitor Jobs → 6. Stop Deployment
```

## Features

### Core Capabilities

- **Container Deployments** - Run any Docker image
- **GPU Support** - Optional GPU acceleration
- **Port Exposure** - Expose web services and APIs
- **Multiple Strategies**:
  - `SIMPLE` - One-time execution
  - `SIMPLE-EXTEND` - Extendable execution
  - `SCHEDULED` - Cron-based scheduling
  - `INFINITE` - Long-running services with rotation

### Smart Contract Operations

1. **Solidity Compilation** - Compile contracts using official solc images
2. **Hardhat Testing** - Run full test suites in isolated environments
3. **Foundry Support** - Execute forge tests and builds
4. **Security Auditing** - Run Slither, Mythril, and other tools

## Client Usage

### Initialization

```python
from nosana_client import NosanaClient

# Initialize with API key
nosana = NosanaClient(
    api_key="your_api_key",  # or set NOSANA_API_KEY env var
    api_url="https://dashboard.k8s.prd.nos.ci/api"  # optional
)

# Check health
health = nosana.health_check()
print(health)
```

### Market Management

```python
# List available markets
markets = nosana.list_markets(market_type="COMMUNITY", limit=10)

for market in markets["markets"]:
    print(f"{market['name']}: {market['type']}")
    print(f"  GPU Types: {market['gpu_types']}")
    print(f"  Price: {market['nos_job_price_per_second']} NOS/sec")

# Get specific market
market = nosana.get_market("market_address")

# Get default market (auto-selected)
default_market = nosana.get_default_market()
```

### Vault Management

```python
# Create a new vault
vault = nosana.create_vault()
print(f"Vault Address: {vault['vault']}")

# List vaults
vaults = nosana.list_vaults()

# Get or create vault (convenience method)
vault_address = nosana.get_or_create_vault()

# Withdraw from vault
result = nosana.withdraw_from_vault(
    vault_address="vault_address",
    sol_amount=0.1,
    nos_amount=100
)
```

### Deployment Management

```python
# Build a container job definition
job_def = nosana.build_container_job(
    image="ubuntu:22.04",
    commands=["echo 'Hello'", "date"],
    env_vars={"MY_VAR": "value"},
    work_dir="/workspace",
    expose_port=8080,  # Optional
    gpu=False
)

# Create deployment
deployment = nosana.create_deployment(
    name="my-deployment",
    job_definition=job_def,
    market="market_address",  # Optional, auto-selected
    vault="vault_address",    # Optional, auto-created
    replicas=1,
    timeout=30,  # minutes
    strategy="SIMPLE"
)

print(f"Deployment ID: {deployment['id']}")
print(f"Status: {deployment['status']}")

# Start deployment
nosana.start_deployment(deployment['id'])

# Get deployment status
status = nosana.get_deployment(deployment['id'])
print(f"Status: {status['status']}")
print(f"Endpoints: {status['endpoints']}")

# Stop deployment
nosana.stop_deployment(deployment['id'])

# Archive deployment (permanent deletion)
nosana.archive_deployment(deployment['id'])

# List all deployments
deployments = nosana.list_deployments()
```

### High-Level Operations

#### Compile Solidity Contract

```python
contract_code = """
pragma solidity ^0.8.0;

contract SimpleStorage {
    uint256 public value;
    
    function setValue(uint256 _value) public {
        value = _value;
    }
}
"""

result = nosana.compile_solidity(
    contract_code=contract_code,
    contract_name="SimpleStorage",
    solc_version="0.8.20",
    timeout_minutes=10
)

print(f"Deployment ID: {result['deployment_id']}")
print(f"Status: {result['status']}")
# Check deployment for compilation results
```

#### Run Hardhat Tests

```python
result = nosana.run_tests(
    repo_url="https://github.com/user/project.git",
    test_command="npx hardhat test",
    timeout_minutes=30
)

print(f"Deployment ID: {result['deployment_id']}")
print(f"Status: {result['status']}")
```

### Job Definition Builders

#### Container Job

```python
job_def = nosana.build_container_job(
    image="node:18",
    commands=[
        "npm install",
        "npm test"
    ],
    env_vars={
        "NODE_ENV": "test",
        "API_KEY": "secret"
    },
    work_dir="/app",
    expose_port=3000,
    gpu=False
)
```

#### Solidity Compilation Job

```python
job_def = nosana.build_solidity_compile_job(
    contract_code=contract_code,
    contract_name="MyContract",
    solc_version="0.8.20"
)
```

#### Hardhat Test Job

```python
job_def = nosana.build_hardhat_test_job(
    repo_url="https://github.com/user/project.git",
    test_command="npx hardhat test --network hardhat"
)
```

## Router Integration

The `nosana_router` provides AgentField endpoints for Nosana operations:

### Reasoners (AI-Powered)

```python
# Compile contract with AI analysis
result = await nosana_router.compile_contract_on_nosana(
    contract_code=code,
    contract_name="MyContract",
    solc_version="0.8.20"
)

# Run Hardhat tests with AI insights
result = await nosana_router.run_hardhat_tests_on_nosana(
    repo_url="https://github.com/user/project.git",
    test_command="npx hardhat test",
    timeout_minutes=30
)
```

### Skills (Deterministic)

```python
# Create deployment
deployment = nosana_router.create_deployment(
    name="my-deployment",
    image="ubuntu:22.04",
    commands=["echo 'Hello'"],
    timeout_minutes=30,
    gpu_required=False
)

# Get deployment status
status = nosana_router.get_deployment_status(deployment_id)

# Start/stop deployment
nosana_router.start_deployment(deployment_id)
nosana_router.stop_deployment(deployment_id)

# List deployments
deployments = nosana_router.list_deployments()

# List markets
markets = nosana_router.list_compute_markets(market_type="COMMUNITY")

# Create vault
vault = nosana_router.create_payment_vault()

# List vaults
vaults = nosana_router.list_payment_vaults()

# Create CI pipeline
pipeline = nosana_router.create_ci_pipeline_on_nosana(
    name="ci-pipeline",
    repo_url="https://github.com/user/project.git",
    commands=["npm install", "npm test"],
    timeout_minutes=30
)

# Compile Solidity (non-AI)
result = nosana_router.compile_solidity_contract(
    contract_code=code,
    contract_name="MyContract",
    solc_version="0.8.20"
)

# Health check
health = nosana_router.check_nosana_status()
```

## Configuration

### Environment Variables

```bash
# Required
NOSANA_API_KEY=your_api_key_here

# Optional
NOSANA_API_URL=https://dashboard.k8s.prd.nos.ci/api
```

### Getting API Key

1. Visit [Nosana Dashboard](https://dashboard.nosana.io)
2. Create an account or sign in
3. Navigate to API Keys section
4. Generate a new API key
5. Add to `.env` file

### Getting Credits

For hackathons, use the credit link:
https://www.theaibuilders.dev/nosanacredits

## API Reference

### Markets

- `GET /api/markets/` - List markets
- `GET /api/markets/{id}/` - Get market details

### Vaults

- `POST /deployments/vaults/create` - Create vault
- `GET /deployments/vaults/` - List vaults
- `GET /deployments/vaults/{vault}/` - Get vault details
- `POST /deployments/vaults/{vault}/withdraw` - Withdraw funds

### Deployments

- `POST /deployments/create` - Create deployment
- `GET /deployments/` - List deployments
- `GET /deployments/{id}/` - Get deployment details
- `POST /deployments/{id}/start` - Start deployment
- `POST /deployments/{id}/stop` - Stop deployment
- `POST /deployments/{id}/archive` - Archive deployment
- `POST /deployments/{id}/create-revision` - Create revision

## Job Definition Structure

```json
{
  "version": "0.1",
  "type": "container",
  "global": {
    "image": "ubuntu:22.04",
    "env": {
      "VAR": "value"
    },
    "work_dir": "/workspace",
    "gpu": false
  },
  "ops": [
    {
      "type": "container/run",
      "id": "main",
      "args": {
        "image": "ubuntu:22.04",
        "cmd": ["echo", "Hello"],
        "expose": {
          "port": 8080,
          "type": "web"
        }
      }
    }
  ]
}
```

## Deployment Strategies

### SIMPLE

One-time execution, stops after completion:

```python
deployment = nosana.create_deployment(
    name="simple-job",
    job_definition=job_def,
    timeout=30,
    strategy="SIMPLE"
)
```

### SIMPLE-EXTEND

Can be extended before timeout:

```python
deployment = nosana.create_deployment(
    name="extendable-job",
    job_definition=job_def,
    timeout=30,
    strategy="SIMPLE-EXTEND"
)
```

### SCHEDULED

Runs on a cron schedule:

```python
deployment = nosana.create_deployment(
    name="scheduled-job",
    job_definition=job_def,
    timeout=30,
    strategy="SCHEDULED",
    schedule="0 */6 * * *"  # Every 6 hours
)
```

### INFINITE

Long-running with automatic rotation:

```python
deployment = nosana.create_deployment(
    name="infinite-service",
    job_definition=job_def,
    timeout=120,  # Must be >= 60 minutes
    strategy="INFINITE",
    rotation_time=3000  # Rotate every 50 minutes
)
```

## Error Handling

```python
result = nosana.create_deployment(...)

if not result.get("success"):
    error = result.get("error")
    if "Unauthorized" in error:
        print("Invalid API key")
    elif "Insufficient funds" in error:
        print("Vault needs funding")
    elif "No markets available" in error:
        print("No compute resources available")
    else:
        print(f"Error: {error}")
```

## Best Practices

1. **Reuse Vaults** - Create once, use for multiple deployments
2. **Select Appropriate Markets** - COMMUNITY for cost, PREMIUM for reliability
3. **Set Reasonable Timeouts** - Balance cost vs. completion time
4. **Monitor Deployments** - Check status regularly
5. **Clean Up** - Archive deployments when done
6. **Use Strategies Wisely** - SIMPLE for one-off tasks, INFINITE for services
7. **Handle Errors** - Always check `success` field in responses

## Limitations

- Requires funded vault for deployments
- Market availability varies by region
- GPU markets may have limited capacity
- Deployment creation requires valid market and vault
- Some operations require authentication

## Testing

Run the test suite:

```bash
cd reagent
python test_nosana.py
```

Tests include:
- Health check
- Market listing
- Vault management
- Job definition building
- Deployment creation (requires credits)

## Support

- **Documentation**: https://docs.nosana.io
- **Dashboard**: https://dashboard.nosana.io
- **Discord**: Join Nosana community
- **Hackathon Credits**: https://www.theaibuilders.dev/nosanacredits

## Integration Status

✅ **Completed:**
- Market discovery and selection
- Vault creation and management
- Deployment lifecycle (create, start, stop, archive)
- Container job definitions
- Solidity compilation
- Hardhat testing
- Health checks
- AgentField router integration

🔄 **In Progress:**
- Result retrieval from deployments
- Advanced job definitions (volumes, health checks)
- Revision management

📋 **Planned:**
- Foundry/Forge integration
- Security audit tool integration (Slither, Mythril)
- Real-time log streaming
- Deployment monitoring and alerts

---

**Last Updated:** 2026-05-16  
**API Version:** 1.0.0  
**Client Version:** 2.0.0