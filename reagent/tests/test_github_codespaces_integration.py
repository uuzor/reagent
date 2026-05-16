"""
Real integration tests for GitHub Codespaces.
These tests make actual API calls to GitHub.

Requirements:
- Set GITHUB_TOKEN environment variable with a valid token
- Token must have 'codespace' and 'repo' scopes
- Tests will create/delete real Codespaces (uses your quota)

Run with: pytest tests/test_github_codespaces_integration.py -v -s
"""
import pytest
import os
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from github_codespaces_full_client import (
    GitHubCodespacesClient,
    CodespaceState,
    CodespaceCreateRequest,
    DevcontainerConfig
)


# Skip all tests if GITHUB_TOKEN not set
pytestmark = pytest.mark.skipif(
    not os.getenv("GITHUB_TOKEN"),
    reason="GITHUB_TOKEN not set. Set it to run integration tests."
)


@pytest.fixture
def github_token():
    """Get GitHub token from environment."""
    return os.getenv("GITHUB_TOKEN")


@pytest.fixture
def test_repo():
    """
    Test repository in format 'owner/repo'.
    Override with GITHUB_TEST_REPO environment variable.
    """
    return os.getenv("GITHUB_TEST_REPO", "your-username/test-repo")


class TestGitHubCodespacesIntegration:
    """Real integration tests with GitHub API."""
    
    @pytest.mark.asyncio
    async def test_list_codespaces_real(self, github_token):
        """Test listing real Codespaces from your account."""
        async with GitHubCodespacesClient(github_token) as client:
            result = await client.list_codespaces()
            
            print(f"\n✓ Found {result['total_count']} Codespaces")
            
            assert "total_count" in result
            assert "codespaces" in result
            assert isinstance(result["codespaces"], list)
            
            # Print details of existing Codespaces
            for cs in result["codespaces"]:
                print(f"  - {cs['name']}: {cs['state']} ({cs['repository']['full_name']})")
    
    @pytest.mark.asyncio
    async def test_list_machines_real(self, github_token, test_repo):
        """Test listing real machine types for a repository."""
        owner, repo = test_repo.split("/")
        
        async with GitHubCodespacesClient(github_token) as client:
            machines = await client.list_machines(owner, repo)
            
            print(f"\n✓ Found {len(machines)} machine types")
            
            assert len(machines) > 0
            
            # Print available machines
            for machine in machines:
                print(f"  - {machine.name}: {machine.display_name}")
                print(f"    CPUs: {machine.cpus}, RAM: {machine.memory_in_bytes / (1024**3):.1f}GB")
    
    @pytest.mark.asyncio
    async def test_create_and_delete_codespace_real(self, github_token, test_repo):
        """
        Test creating and deleting a real Codespace.
        WARNING: This uses your Codespace quota!
        """
        owner, repo = test_repo.split("/")
        
        async with GitHubCodespacesClient(github_token) as client:
            # Create Codespace
            print(f"\n📦 Creating Codespace in {test_repo}...")
            
            request = CodespaceCreateRequest(
                ref="main",
                machine="basicLinux32gb",  # Use smallest machine
                display_name="Reagent Integration Test",
                idle_timeout_minutes=5  # Auto-stop after 5 min
            )
            
            codespace = await client.create_codespace(owner, repo, request)
            
            print(f"✓ Created: {codespace.name}")
            print(f"  State: {codespace.state}")
            print(f"  URL: {codespace.web_url}")
            
            assert codespace.name is not None
            assert codespace.id > 0
            
            try:
                # Wait for it to be available (optional, can be slow)
                if os.getenv("WAIT_FOR_CODESPACE", "false").lower() == "true":
                    print("⏳ Waiting for Codespace to start...")
                    codespace = await client.wait_for_state(
                        codespace.name,
                        CodespaceState.AVAILABLE,
                        timeout=300,
                        poll_interval=10
                    )
                    print(f"✓ Codespace is {codespace.state}")
                
                # Get Codespace details
                fetched = await client.get_codespace(codespace.name)
                assert fetched.name == codespace.name
                print(f"✓ Verified Codespace exists")
                
            finally:
                # Always cleanup
                print(f"🧹 Cleaning up...")
                
                # Stop first
                try:
                    await client.stop_codespace(codespace.name)
                    print(f"✓ Stopped Codespace")
                except Exception as e:
                    print(f"⚠️  Could not stop: {e}")
                
                # Then delete
                await client.delete_codespace(codespace.name)
                print(f"✓ Deleted Codespace")
    
    @pytest.mark.asyncio
    async def test_list_secrets_real(self, github_token):
        """Test listing real Codespace secrets."""
        async with GitHubCodespacesClient(github_token) as client:
            secrets = await client.list_secrets()
            
            print(f"\n✓ Found {secrets['total_count']} secrets")
            
            assert "total_count" in secrets
            assert "secrets" in secrets
    
    @pytest.mark.asyncio
    async def test_error_handling_invalid_repo(self, github_token):
        """Test error handling with invalid repository."""
        async with GitHubCodespacesClient(github_token) as client:
            with pytest.raises(Exception) as exc_info:
                await client.list_machines("nonexistent", "repo")
            
            print(f"\n✓ Correctly raised error: {exc_info.value}")
            assert "not found" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_devcontainer_config_creation(self, github_token, test_repo):
        """Test creating devcontainer configuration in repository."""
        owner, repo = test_repo.split("/")
        
        # Only run if explicitly enabled (modifies repo)
        if os.getenv("TEST_DEVCONTAINER_CREATION", "false").lower() != "true":
            pytest.skip("Set TEST_DEVCONTAINER_CREATION=true to run this test")
        
        async with GitHubCodespacesClient(github_token) as client:
            config = DevcontainerConfig(
                name="Test Devcontainer",
                post_create_command="echo 'Test setup complete'"
            )
            
            print(f"\n📝 Creating devcontainer config in {test_repo}...")
            
            result = await client.create_devcontainer_file(
                owner,
                repo,
                "test-devcontainer-branch",
                config
            )
            
            print(f"✓ Created devcontainer config")
            print(f"  Commit: {result.get('commit', {}).get('sha', 'N/A')}")
            
            assert "commit" in result or "content" in result


class TestCommandExecution:
    """Test command execution in Codespaces."""
    
    @pytest.mark.asyncio
    async def test_execute_command_real(self, github_token):
        """
        Test executing a real command in a Codespace.
        Requires an existing Codespace and GitHub CLI installed.
        """
        # Skip if no Codespace name provided
        codespace_name = os.getenv("TEST_CODESPACE_NAME")
        if not codespace_name:
            pytest.skip("Set TEST_CODESPACE_NAME to test command execution")
        
        # Skip if GitHub CLI not installed
        import subprocess
        try:
            subprocess.run(["gh", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("GitHub CLI (gh) not installed")
        
        async with GitHubCodespacesClient(github_token) as client:
            print(f"\n🚀 Executing command in {codespace_name}...")
            
            result = await client.execute_command(
                codespace_name,
                "echo 'Hello from Codespace!'"
            )
            
            print(f"✓ Command executed")
            print(f"  Output: {result['stdout']}")
            print(f"  Success: {result['success']}")
            
            assert result["success"] is True
            assert "Hello from Codespace" in result["stdout"]


class TestWorkflowScenario:
    """Test complete workflow scenarios."""
    
    @pytest.mark.asyncio
    async def test_full_workflow_scenario(self, github_token, test_repo):
        """
        Test a complete workflow: create, wait, execute, cleanup.
        WARNING: This is a long-running test that uses quota!
        """
        # Only run if explicitly enabled
        if os.getenv("TEST_FULL_WORKFLOW", "false").lower() != "true":
            pytest.skip("Set TEST_FULL_WORKFLOW=true to run this test")
        
        owner, repo = test_repo.split("/")
        
        async with GitHubCodespacesClient(github_token) as client:
            print(f"\n🎬 Starting full workflow test...")
            
            # 1. Create Codespace
            print("1️⃣  Creating Codespace...")
            request = CodespaceCreateRequest(
                ref="main",
                machine="basicLinux32gb",
                display_name="Full Workflow Test",
                idle_timeout_minutes=10
            )
            
            codespace = await client.create_codespace(owner, repo, request)
            print(f"   ✓ Created: {codespace.name}")
            
            try:
                # 2. Wait for it to be ready
                print("2️⃣  Waiting for Codespace to start...")
                codespace = await client.wait_for_state(
                    codespace.name,
                    CodespaceState.AVAILABLE,
                    timeout=300,
                    poll_interval=10
                )
                print(f"   ✓ Codespace is ready!")
                
                # 3. Execute a command (if GitHub CLI available)
                try:
                    print("3️⃣  Executing test command...")
                    result = await client.execute_command(
                        codespace.name,
                        "pwd && ls -la"
                    )
                    print(f"   ✓ Command output:\n{result['stdout']}")
                except Exception as e:
                    print(f"   ⚠️  Could not execute command: {e}")
                
                # 4. Stop Codespace
                print("4️⃣  Stopping Codespace...")
                await client.stop_codespace(codespace.name)
                print(f"   ✓ Stopped")
                
            finally:
                # 5. Cleanup
                print("5️⃣  Cleaning up...")
                await client.delete_codespace(codespace.name)
                print(f"   ✓ Deleted")
            
            print("\n✅ Full workflow test completed successfully!")


def print_test_info():
    """Print information about running integration tests."""
    print("\n" + "="*70)
    print("GitHub Codespaces Integration Tests")
    print("="*70)
    print("\nThese tests make REAL API calls to GitHub!")
    print("\nRequired:")
    print("  - GITHUB_TOKEN environment variable")
    print("  - Token with 'codespace' and 'repo' scopes")
    print("\nOptional:")
    print("  - GITHUB_TEST_REPO (default: your-username/test-repo)")
    print("  - WAIT_FOR_CODESPACE=true (wait for Codespace to start)")
    print("  - TEST_CODESPACE_NAME (for command execution tests)")
    print("  - TEST_DEVCONTAINER_CREATION=true (creates files in repo)")
    print("  - TEST_FULL_WORKFLOW=true (runs complete workflow)")
    print("\nWarning:")
    print("  - Tests will create/delete real Codespaces")
    print("  - This uses your GitHub Codespace quota")
    print("  - Free tier: 120 core-hours/month")
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    print_test_info()
    pytest.main([__file__, "-v", "-s"])

# Made with Bob
