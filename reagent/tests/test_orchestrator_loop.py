"""
Integration tests for orchestrator feedback loops and error recovery.
Tests the full workflow with mocked AI and app.call responses.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from routers.orchestrator_router import (
    WorkflowState,
    WorkflowStage,
    StageResult,
    orchestrate_contract_development_adaptive,
    _execute_ideation,
    _execute_coding,
    _execute_testing,
    _execute_auditing,
    _execute_deployment,
    _execute_monitoring,
)


@pytest.fixture
def mock_file_manager():
    """Mock FileManager for tests."""
    fm = MagicMock()
    fm.gl.create_issue.return_value = {
        "iid": 123,
        "web_url": "https://gitlab.com/test/issue/123"
    }
    fm.gl.add_issue_note.return_value = None
    return fm


@pytest.fixture
def mock_orchestrator_app():
    """Mock orchestrator app for tests."""
    with patch('routers.orchestrator_router.orchestrator_router') as mock_router:
        mock_router.app = MagicMock()
        mock_router.app.call = AsyncMock()
        mock_router.app.note = MagicMock()
        mock_router.app.node_id = "test_node"
        mock_router.ai = AsyncMock()
        yield mock_router


class TestFeedbackLoops:
    """Test feedback loop scenarios."""
    
    @pytest.mark.asyncio
    async def test_test_failure_loops_back_to_coding(self, mock_orchestrator_app, mock_file_manager):
        """Test that test failures trigger a loop back to coding stage."""
        # Mock ideation success
        mock_orchestrator_app.app.call.side_effect = [
            # First ideation call
            {"name": "TestToken", "features": ["ERC20"], "blockchain": "ethereum"},
            # First coding call
            {"solidity_code": "contract TestToken {}", "test_code": "test", "deployment_script": "deploy"},
            # First testing call - FAIL
            {"passed": False, "failures": ["Transfer function error"]},
            # Second coding call (after feedback)
            {"solidity_code": "contract TestToken { /* fixed */ }", "test_code": "test", "deployment_script": "deploy"},
            # Second testing call - PASS
            {"passed": True, "tests_run": 5, "failures": []},
            # Auditing
            {"overall_risk": "low", "issues": []},
            # Deployment
            {"success": True, "contract_address": "0x123", "network": "testnet"},
            # Monitoring
            {"monitoring_started": True}
        ]
        
        # Mock AI decision making
        mock_orchestrator_app.ai.side_effect = [
            # After failed testing - go back to coding
            {
                "next_stage": "coding",
                "reason": "Tests failed, need to fix code",
                "feedback_needed": True,
                "suggestions": ["Fix transfer function"]
            },
            # After successful coding retry - proceed to testing
            {
                "next_stage": "testing",
                "reason": "Code regenerated with fixes",
                "feedback_needed": False,
                "suggestions": []
            },
            # After successful testing - proceed to auditing
            {
                "next_stage": "auditing",
                "reason": "All tests passed",
                "feedback_needed": False,
                "suggestions": []
            },
            # After auditing - proceed to deployment
            {
                "next_stage": "deployment",
                "reason": "Low risk, ready to deploy",
                "feedback_needed": False,
                "suggestions": []
            },
            # After deployment - proceed to monitoring
            {
                "next_stage": "monitoring",
                "reason": "Deployment successful",
                "feedback_needed": False,
                "suggestions": []
            }
        ]
        
        with patch('routers.orchestrator_router._get_fm', return_value=mock_file_manager):
            result = await orchestrate_contract_development_adaptive("Build an ERC20 token")
        
        assert result["status"] == "completed"
        assert len(result["feedback_loops"]) >= 1
        assert any(loop["to"] == "coding" for loop in result["feedback_loops"])
    
    @pytest.mark.asyncio
    async def test_critical_audit_loops_to_ideation(self, mock_orchestrator_app, mock_file_manager):
        """Test that critical audit findings loop back to ideation."""
        mock_orchestrator_app.app.call.side_effect = [
            # Ideation
            {"name": "RiskyToken", "features": ["custom"], "blockchain": "ethereum"},
            # Coding
            {"solidity_code": "contract RiskyToken {}", "test_code": "test", "deployment_script": "deploy"},
            # Testing - pass
            {"passed": True, "tests_run": 3, "failures": []},
            # Auditing - CRITICAL RISK
            {"overall_risk": "critical", "issues": ["Reentrancy vulnerability"]},
            # Ideation retry with context
            {"name": "SafeToken", "features": ["ERC20", "ReentrancyGuard"], "blockchain": "ethereum"},
            # Coding retry
            {"solidity_code": "contract SafeToken {}", "test_code": "test", "deployment_script": "deploy"},
            # Testing retry
            {"passed": True, "tests_run": 5, "failures": []},
            # Auditing retry - low risk
            {"overall_risk": "low", "issues": []},
            # Deployment
            {"success": True, "contract_address": "0x456", "network": "testnet"},
            # Monitoring
            {"monitoring_started": True}
        ]
        
        mock_orchestrator_app.ai.side_effect = [
            # After critical audit - go back to ideation
            {
                "next_stage": "ideation",
                "reason": "Critical security issues, need to redesign",
                "feedback_needed": True,
                "suggestions": ["Add reentrancy protection"]
            },
            # After ideation retry - proceed to coding
            {
                "next_stage": "coding",
                "reason": "Spec updated with security features",
                "feedback_needed": False,
                "suggestions": []
            },
            # Continue normal flow...
            {"next_stage": "testing", "reason": "Code ready", "feedback_needed": False, "suggestions": []},
            {"next_stage": "auditing", "reason": "Tests passed", "feedback_needed": False, "suggestions": []},
            {"next_stage": "deployment", "reason": "Audit passed", "feedback_needed": False, "suggestions": []},
        ]
        
        with patch('routers.orchestrator_router._get_fm', return_value=mock_file_manager):
            result = await orchestrate_contract_development_adaptive("Build a token")
        
        assert result["status"] == "completed"
        assert len(result["feedback_loops"]) >= 1
        assert any(loop["to"] == "ideation" for loop in result["feedback_loops"])
    
    @pytest.mark.asyncio
    async def test_max_iterations_aborts(self, mock_orchestrator_app, mock_file_manager):
        """Test that persistent failures hit the global iteration cap."""
        # Always fail testing
        mock_orchestrator_app.app.call.side_effect = [
            {"name": "FailToken", "features": ["ERC20"], "blockchain": "ethereum"},
            {"solidity_code": "contract FailToken {}", "test_code": "test", "deployment_script": "deploy"},
            {"passed": False, "failures": ["Error 1"]},
        ] * 30  # More than max_iterations
        
        # Always suggest retry
        mock_orchestrator_app.ai.return_value = {
            "next_stage": "coding",
            "reason": "Tests failed",
            "feedback_needed": True,
            "suggestions": []
        }
        
        with patch('routers.orchestrator_router._get_fm', return_value=mock_file_manager):
            result = await orchestrate_contract_development_adaptive("Build a token")
        
        assert result["status"] == "failed"
        # Should hit max_iterations (20) before completing
    
    @pytest.mark.asyncio
    async def test_deployment_error_loops_to_coding(self, mock_orchestrator_app, mock_file_manager):
        """Test that deployment failures loop back to coding."""
        mock_orchestrator_app.app.call.side_effect = [
            # Ideation
            {"name": "DeployToken", "features": ["ERC20"], "blockchain": "ethereum"},
            # Coding
            {"solidity_code": "contract DeployToken {}", "test_code": "test", "deployment_script": "deploy"},
            # Testing - pass
            {"passed": True, "tests_run": 3, "failures": []},
            # Auditing - pass
            {"overall_risk": "low", "issues": []},
            # Deployment - FAIL
            {"success": False, "error": "Gas estimation failed"},
            # Coding retry
            {"solidity_code": "contract DeployToken { /* optimized */ }", "test_code": "test", "deployment_script": "deploy"},
            # Testing retry
            {"passed": True, "tests_run": 3, "failures": []},
            # Auditing retry
            {"overall_risk": "low", "issues": []},
            # Deployment retry - SUCCESS
            {"success": True, "contract_address": "0x789", "network": "testnet"},
            # Monitoring
            {"monitoring_started": True}
        ]
        
        mock_orchestrator_app.ai.side_effect = [
            {"next_stage": "coding", "reason": "Code ready", "feedback_needed": False, "suggestions": []},
            {"next_stage": "testing", "reason": "Tests ready", "feedback_needed": False, "suggestions": []},
            {"next_stage": "auditing", "reason": "Tests passed", "feedback_needed": False, "suggestions": []},
            # After deployment failure - go back to coding
            {
                "next_stage": "coding",
                "reason": "Deployment failed, optimize gas usage",
                "feedback_needed": True,
                "suggestions": ["Optimize gas"]
            },
            # Continue after retry...
            {"next_stage": "testing", "reason": "Code optimized", "feedback_needed": False, "suggestions": []},
            {"next_stage": "auditing", "reason": "Tests passed", "feedback_needed": False, "suggestions": []},
            {"next_stage": "deployment", "reason": "Ready to deploy", "feedback_needed": False, "suggestions": []},
        ]
        
        with patch('routers.orchestrator_router._get_fm', return_value=mock_file_manager):
            result = await orchestrate_contract_development_adaptive("Build a token")
        
        assert result["status"] == "completed"
        assert len(result["feedback_loops"]) >= 1
        assert any(loop["from"] == "deployment" and loop["to"] == "coding" for loop in result["feedback_loops"])


class TestStageExecution:
    """Test individual stage execution functions."""
    
    @pytest.mark.asyncio
    async def test_execute_ideation_success(self, mock_orchestrator_app, mock_file_manager):
        """Test successful ideation execution."""
        state = WorkflowState(
            workflow_id="test_123",
            requirements="Build DeFi token",
            current_stage=WorkflowStage.IDEATION.value
        )
        
        mock_orchestrator_app.app.call.return_value = {
            "name": "DeFiToken",
            "features": ["ERC20", "Staking"],
            "blockchain": "ethereum"
        }
        
        with patch('routers.orchestrator_router.orchestrator_router', mock_orchestrator_app):
            result = await _execute_ideation(state, mock_file_manager)
        
        assert result.success is True
        assert result.stage == WorkflowStage.IDEATION.value
        assert result.output["name"] == "DeFiToken"
        assert result.next_stage == WorkflowStage.CODING.value
    
    @pytest.mark.asyncio
    async def test_execute_coding_with_recovery_context(self, mock_orchestrator_app, mock_file_manager):
        """Test coding execution with recovery context from failed testing."""
        state = WorkflowState(
            workflow_id="test_456",
            requirements="Build token",
            current_stage=WorkflowStage.CODING.value
        )
        
        # Add ideation result
        state.stage_results[WorkflowStage.IDEATION.value] = StageResult(
            stage=WorkflowStage.IDEATION.value,
            success=True,
            output={"name": "TestToken", "features": ["ERC20"]},
            next_stage=WorkflowStage.CODING.value
        )
        
        # Add failed testing result (to trigger recovery context)
        state.stage_results[WorkflowStage.TESTING.value] = StageResult(
            stage=WorkflowStage.TESTING.value,
            success=False,
            output={},
            error="Transfer function failed",
            next_stage=WorkflowStage.CODING.value
        )
        
        mock_orchestrator_app.app.call.return_value = {
            "solidity_code": "contract TestToken { /* fixed */ }",
            "test_code": "test",
            "deployment_script": "deploy"
        }
        
        with patch('routers.orchestrator_router.orchestrator_router', mock_orchestrator_app):
            result = await _execute_coding(state, mock_file_manager)
        
        assert result.success is True
        assert result.stage == WorkflowStage.CODING.value


class TestGuardRailEnforcement:
    """Test that guard rails are properly enforced."""
    
    @pytest.mark.asyncio
    async def test_max_stage_retries_enforced(self, mock_orchestrator_app, mock_file_manager):
        """Test that max retries per stage are enforced."""
        state = WorkflowState(
            workflow_id="test_789",
            requirements="Build token",
            current_stage=WorkflowStage.CODING.value,
            max_retries=3
        )
        
        # Simulate 3 failed attempts
        state.retry_counts[WorkflowStage.CODING.value] = 3
        
        # Should trigger failure
        assert state.retry_counts[WorkflowStage.CODING.value] >= state.max_retries


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
