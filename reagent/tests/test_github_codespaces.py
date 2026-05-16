"""
Comprehensive tests for GitHub Codespaces integration.
Tests the full client with mocked GitHub API responses.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from github_codespaces_full_client import (
    GitHubCodespacesClient,
    CodespaceState,
    MachineType,
    DevcontainerConfig,
    CodespaceCreateRequest,
    Codespace
)


@pytest.fixture
def mock_token():
    """Mock GitHub token."""
    return "ghp_test_token_123456789"


@pytest.fixture
def mock_codespace_data():
    """Mock Codespace data from GitHub API."""
    return {
        "id": 123456,
        "name": "test-codespace-abc123",
        "display_name": "Test Codespace",
        "environment_id": "env123",
        "owner": {"login": "testuser"},
        "billable_owner": {"login": "testuser"},
        "repository": {
            "id": 789,
            "name": "test-repo",
            "full_name": "testuser/test-repo"
        },
        "machine": {
            "name": "standardLinux32gb",
            "display_name": "4 cores, 8 GB RAM",
            "cpus": 4,
            "memory_in_bytes": 8589934592
        },
        "devcontainer_path": ".devcontainer/devcontainer.json",
        "prebuild": False,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "last_used_at": "2024-01-01T00:00:00Z",
        "state": "Available",
        "url": "https://api.github.com/user/codespaces/test-codespace-abc123",
        "git_status": {
            "ahead": 0,
            "behind": 0,
            "has_unpushed_changes": False,
            "has_uncommitted_changes": False
        },
        "location": "WestUs2",
        "idle_timeout_minutes": 60,
        "web_url": "https://test-codespace-abc123.github.dev",
        "machines_url": "https://api.github.com/repos/testuser/test-repo/codespaces/machines",
        "start_url": "https://api.github.com/user/codespaces/test-codespace-abc123/start",
        "stop_url": "https://api.github.com/user/codespaces/test-codespace-abc123/stop",
        "recent_folders": []
    }


@pytest.fixture
def mock_machine_data():
    """Mock machine type data."""
    return {
        "machines": [
            {
                "name": "basicLinux32gb",
                "display_name": "2 cores, 4 GB RAM, 32 GB storage",
                "operating_system": "linux",
                "storage_in_bytes": 34359738368,
                "memory_in_bytes": 4294967296,
                "cpus": 2,
                "prebuild_availability": "ready"
            },
            {
                "name": "standardLinux32gb",
                "display_name": "4 cores, 8 GB RAM, 32 GB storage",
                "operating_system": "linux",
                "storage_in_bytes": 34359738368,
                "memory_in_bytes": 8589934592,
                "cpus": 4,
                "prebuild_availability": "ready"
            }
        ]
    }


class TestGitHubCodespacesClient:
    """Test GitHub Codespaces client."""
    
    @pytest.mark.asyncio
    async def test_client_initialization(self, mock_token):
        """Test client initialization."""
        client = GitHubCodespacesClient(mock_token)
        
        assert client.token == mock_token
        assert client.api_base == "https://api.github.com"
        assert "Authorization" in client.headers
        assert client.headers["Authorization"] == f"Bearer {mock_token}"
    
    @pytest.mark.asyncio
    async def test_context_manager(self, mock_token):
        """Test async context manager."""
        async with GitHubCodespacesClient(mock_token) as client:
            assert client.session is not None
        
        # Session should be closed after exit
        assert client.session.closed
    
    @pytest.mark.asyncio
    async def test_list_codespaces(self, mock_token, mock_codespace_data):
        """Test listing Codespaces."""
        async with GitHubCodespacesClient(mock_token) as client:
            # Mock the request
            with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = {
                    "total_count": 1,
                    "codespaces": [mock_codespace_data]
                }
                
                result = await client.list_codespaces()
                
                assert result["total_count"] == 1
                assert len(result["codespaces"]) == 1
                assert result["codespaces"][0]["name"] == "test-codespace-abc123"
                
                # Verify request was made correctly
                mock_request.assert_called_once_with(
                    "GET",
                    "/user/codespaces",
                    params={"per_page": 30, "page": 1}
                )
    
    @pytest.mark.asyncio
    async def test_get_codespace(self, mock_token, mock_codespace_data):
        """Test getting a specific Codespace."""
        async with GitHubCodespacesClient(mock_token) as client:
            with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_codespace_data
                
                codespace = await client.get_codespace("test-codespace-abc123")
                
                assert isinstance(codespace, Codespace)
                assert codespace.name == "test-codespace-abc123"
                assert codespace.state == "Available"
                assert codespace.web_url == "https://test-codespace-abc123.github.dev"
    
    @pytest.mark.asyncio
    async def test_create_codespace(self, mock_token, mock_codespace_data):
        """Test creating a Codespace."""
        async with GitHubCodespacesClient(mock_token) as client:
            with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_codespace_data
                
                request = CodespaceCreateRequest(
                    ref="main",
                    machine="standardLinux32gb",
                    display_name="Test Codespace"
                )
                
                codespace = await client.create_codespace("testuser", "test-repo", request)
                
                assert isinstance(codespace, Codespace)
                assert codespace.name == "test-codespace-abc123"
                
                # Verify request
                mock_request.assert_called_once()
                call_args = mock_request.call_args
                assert call_args[0][0] == "POST"
                assert "/repos/testuser/test-repo/codespaces" in call_args[0][1]
    
    @pytest.mark.asyncio
    async def test_start_codespace(self, mock_token, mock_codespace_data):
        """Test starting a Codespace."""
        async with GitHubCodespacesClient(mock_token) as client:
            with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_codespace_data
                
                codespace = await client.start_codespace("test-codespace-abc123")
                
                assert codespace.state == "Available"
                mock_request.assert_called_once_with(
                    "POST",
                    "/user/codespaces/test-codespace-abc123/start"
                )
    
    @pytest.mark.asyncio
    async def test_stop_codespace(self, mock_token, mock_codespace_data):
        """Test stopping a Codespace."""
        async with GitHubCodespacesClient(mock_token) as client:
            with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
                stopped_data = mock_codespace_data.copy()
                stopped_data["state"] = "Shutdown"
                mock_request.return_value = stopped_data
                
                codespace = await client.stop_codespace("test-codespace-abc123")
                
                assert codespace.state == "Shutdown"
    
    @pytest.mark.asyncio
    async def test_delete_codespace(self, mock_token):
        """Test deleting a Codespace."""
        async with GitHubCodespacesClient(mock_token) as client:
            with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = {}
                
                await client.delete_codespace("test-codespace-abc123")
                
                mock_request.assert_called_once_with(
                    "DELETE",
                    "/user/codespaces/test-codespace-abc123"
                )
    
    @pytest.mark.asyncio
    async def test_list_machines(self, mock_token, mock_machine_data):
        """Test listing available machine types."""
        async with GitHubCodespacesClient(mock_token) as client:
            with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_machine_data
                
                machines = await client.list_machines("testuser", "test-repo")
                
                assert len(machines) == 2
                assert all(isinstance(m, MachineType) for m in machines)
                assert machines[0].name == "basicLinux32gb"
                assert machines[1].cpus == 4
    
    @pytest.mark.asyncio
    async def test_wait_for_state_success(self, mock_token, mock_codespace_data):
        """Test waiting for Codespace to reach target state."""
        async with GitHubCodespacesClient(mock_token) as client:
            with patch.object(client, 'get_codespace', new_callable=AsyncMock) as mock_get:
                # Simulate state transition: Starting -> Available
                starting_data = mock_codespace_data.copy()
                starting_data["state"] = "Starting"
                available_data = mock_codespace_data.copy()
                available_data["state"] = "Available"
                
                mock_get.side_effect = [
                    Codespace(**starting_data),
                    Codespace(**available_data)
                ]
                
                codespace = await client.wait_for_state(
                    "test-codespace-abc123",
                    CodespaceState.AVAILABLE,
                    timeout=30,
                    poll_interval=1
                )
                
                assert codespace.state == "Available"
                assert mock_get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_wait_for_state_timeout(self, mock_token, mock_codespace_data):
        """Test timeout when waiting for state."""
        async with GitHubCodespacesClient(mock_token) as client:
            with patch.object(client, 'get_codespace', new_callable=AsyncMock) as mock_get:
                # Always return Starting state
                starting_data = mock_codespace_data.copy()
                starting_data["state"] = "Starting"
                mock_get.return_value = Codespace(**starting_data)
                
                with pytest.raises(TimeoutError):
                    await client.wait_for_state(
                        "test-codespace-abc123",
                        CodespaceState.AVAILABLE,
                        timeout=2,
                        poll_interval=1
                    )
    
    @pytest.mark.asyncio
    async def test_wait_for_state_failed(self, mock_token, mock_codespace_data):
        """Test handling of failed Codespace."""
        async with GitHubCodespacesClient(mock_token) as client:
            with patch.object(client, 'get_codespace', new_callable=AsyncMock) as mock_get:
                failed_data = mock_codespace_data.copy()
                failed_data["state"] = "Failed"
                mock_get.return_value = Codespace(**failed_data)
                
                with pytest.raises(Exception, match="failed to start"):
                    await client.wait_for_state(
                        "test-codespace-abc123",
                        CodespaceState.AVAILABLE,
                        timeout=30
                    )
    
    @pytest.mark.asyncio
    async def test_error_handling_404(self, mock_token):
        """Test handling of 404 errors."""
        async with GitHubCodespacesClient(mock_token) as client:
            with patch.object(client.session, 'request') as mock_request:
                mock_response = AsyncMock()
                mock_response.status = 404
                mock_response.text = AsyncMock(return_value="Not found")
                mock_request.return_value.__aenter__.return_value = mock_response
                
                with pytest.raises(Exception, match="Resource not found"):
                    await client._request("GET", "/user/codespaces/nonexistent")
    
    @pytest.mark.asyncio
    async def test_error_handling_rate_limit(self, mock_token, mock_codespace_data):
        """Test handling of rate limit (429)."""
        async with GitHubCodespacesClient(mock_token) as client:
            with patch.object(client.session, 'request') as mock_request:
                # First call: rate limited
                rate_limit_response = AsyncMock()
                rate_limit_response.status = 429
                rate_limit_response.headers = {'Retry-After': '1'}
                
                # Second call: success
                success_response = AsyncMock()
                success_response.status = 200
                success_response.json = AsyncMock(return_value=mock_codespace_data)
                
                mock_request.return_value.__aenter__.side_effect = [
                    rate_limit_response,
                    success_response
                ]
                
                result = await client._request("GET", "/user/codespaces")
                
                assert result == mock_codespace_data
                assert mock_request.call_count == 2


class TestDevcontainerConfig:
    """Test Devcontainer configuration."""
    
    def test_default_config(self):
        """Test default devcontainer configuration."""
        config = DevcontainerConfig()
        
        assert config.name == "Reagent Smart Contract Development"
        assert "python" in config.image
        # Check for full feature keys
        assert any("node" in key for key in config.features.keys())
        assert any("docker-in-docker" in key for key in config.features.keys())
        assert config.remote_user == "vscode"
        assert 8000 in config.forward_ports
    
    def test_custom_config(self):
        """Test custom devcontainer configuration."""
        config = DevcontainerConfig(
            name="Custom Dev Environment",
            image="custom/image:latest",
            forward_ports=[3000, 5000]
        )
        
        assert config.name == "Custom Dev Environment"
        assert config.image == "custom/image:latest"
        assert config.forward_ports == [3000, 5000]
    
    def test_config_serialization(self):
        """Test devcontainer config can be serialized to JSON."""
        config = DevcontainerConfig()
        config_dict = config.model_dump(exclude_none=True)
        
        assert "name" in config_dict
        assert "image" in config_dict
        assert "features" in config_dict
        
        # Should be valid JSON
        json_str = json.dumps(config_dict)
        assert json_str is not None


class TestCodespaceModels:
    """Test Pydantic models."""
    
    def test_codespace_state_enum(self):
        """Test CodespaceState enum."""
        assert CodespaceState.AVAILABLE.value == "Available"
        assert CodespaceState.STARTING.value == "Starting"
        assert CodespaceState.FAILED.value == "Failed"
    
    def test_codespace_create_request(self):
        """Test CodespaceCreateRequest model."""
        request = CodespaceCreateRequest(
            ref="main",
            machine="standardLinux32gb",
            display_name="Test"
        )
        
        assert request.ref == "main"
        assert request.machine == "standardLinux32gb"
        assert request.idle_timeout_minutes == 60  # default
    
    def test_machine_type_model(self):
        """Test MachineType model."""
        machine = MachineType(
            name="standardLinux32gb",
            display_name="4 cores, 8 GB RAM",
            operating_system="linux",
            storage_in_bytes=34359738368,
            memory_in_bytes=8589934592,
            cpus=4
        )
        
        assert machine.cpus == 4
        assert machine.memory_in_bytes == 8589934592


class TestCommandExecution:
    """Test command execution functionality."""
    
    def test_execute_command_sync_success(self, mock_token):
        """Test successful command execution."""
        client = GitHubCodespacesClient(mock_token)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="Hello World",
                stderr="",
                returncode=0
            )
            
            result = client.execute_command_sync(
                "test-codespace",
                "echo 'Hello World'"
            )
            
            assert result["success"] is True
            assert result["stdout"] == "Hello World"
            assert result["returncode"] == 0
    
    def test_execute_command_sync_failure(self, mock_token):
        """Test failed command execution."""
        client = GitHubCodespacesClient(mock_token)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="",
                stderr="Command not found",
                returncode=1
            )
            
            result = client.execute_command_sync(
                "test-codespace",
                "nonexistent-command"
            )
            
            assert result["success"] is False
            assert result["returncode"] == 1
            assert "Command not found" in result["stderr"]
    
    def test_execute_command_gh_not_installed(self, mock_token):
        """Test when GitHub CLI is not installed."""
        client = GitHubCodespacesClient(mock_token)
        
        with patch('subprocess.run', side_effect=FileNotFoundError):
            result = client.execute_command_sync(
                "test-codespace",
                "echo test"
            )
            
            assert result["success"] is False
            assert "not installed" in result["stderr"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
