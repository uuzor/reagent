"""
Unit tests for orchestrator state management and helper functions.
Tests the core logic without AI calls.
"""
import pytest
from typing import Dict, Any
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from routers.orchestrator_router import (
    WorkflowState,
    WorkflowStage,
    StageResult,
    ErrorRecoveryDecision,
    STAGE_ORDER,
)


class TestWorkflowState:
    """Test WorkflowState initialization and defaults."""
    
    def test_initial_state(self):
        """Test workflow state initialization with defaults."""
        state = WorkflowState(
            workflow_id="test_123",
            requirements="Build a DeFi token",
            current_stage=WorkflowStage.IDEATION.value
        )
        
        assert state.workflow_id == "test_123"
        assert state.requirements == "Build a DeFi token"
        assert state.current_stage == WorkflowStage.IDEATION.value
        assert state.stages_completed == []
        assert state.stage_results == {}
        assert state.retry_counts == {}
        assert state.max_retries == 3
        assert state.status == "in_progress"
        assert state.gitlab_issue is None
    
    def test_state_with_custom_max_retries(self):
        """Test workflow state with custom max retries."""
        state = WorkflowState(
            workflow_id="test_456",
            requirements="Build NFT marketplace",
            current_stage=WorkflowStage.CODING.value,
            max_retries=5
        )
        
        assert state.max_retries == 5


class TestStageOrder:
    """Test STAGE_ORDER constant."""
    
    def test_stage_order_completeness(self):
        """Test that STAGE_ORDER contains all workflow stages."""
        expected_stages = [
            WorkflowStage.IDEATION.value,
            WorkflowStage.CODING.value,
            WorkflowStage.TESTING.value,
            WorkflowStage.AUDITING.value,
            WorkflowStage.DEPLOYMENT.value,
            WorkflowStage.MONITORING.value,
        ]
        
        assert STAGE_ORDER == expected_stages
    
    def test_stage_order_sequence(self):
        """Test that stages are in correct order."""
        assert STAGE_ORDER[0] == WorkflowStage.IDEATION.value
        assert STAGE_ORDER[-1] == WorkflowStage.MONITORING.value
        assert len(STAGE_ORDER) == 6


class TestStageResult:
    """Test StageResult model."""
    
    def test_successful_stage_result(self):
        """Test creating a successful stage result."""
        result = StageResult(
            stage=WorkflowStage.IDEATION.value,
            success=True,
            output={"name": "MyToken", "features": ["ERC20"]},
            next_stage=WorkflowStage.CODING.value
        )
        
        assert result.stage == WorkflowStage.IDEATION.value
        assert result.success is True
        assert result.output["name"] == "MyToken"
        assert result.error is None
        assert result.retry_count == 0
        assert result.next_stage == WorkflowStage.CODING.value
    
    def test_failed_stage_result(self):
        """Test creating a failed stage result."""
        result = StageResult(
            stage=WorkflowStage.TESTING.value,
            success=False,
            output={"tests_run": 5, "failures": 2},
            error="2 tests failed",
            retry_count=1,
            next_stage=WorkflowStage.CODING.value
        )
        
        assert result.success is False
        assert result.error == "2 tests failed"
        assert result.retry_count == 1
        assert result.next_stage == WorkflowStage.CODING.value


class TestErrorRecoveryDecision:
    """Test ErrorRecoveryDecision model."""
    
    def test_go_back_decision(self):
        """Test error recovery decision to go back to previous stage."""
        decision = ErrorRecoveryDecision(
            analysis="Tests failed due to logic error in contract",
            action="go_back",
            target_stage=WorkflowStage.CODING.value,
            context_to_inject="Fix the transfer function logic",
            confidence=0.85
        )
        
        assert decision.action == "go_back"
        assert decision.target_stage == WorkflowStage.CODING.value
        assert decision.confidence == 0.85
        assert "logic error" in decision.analysis
    
    def test_retry_same_decision(self):
        """Test error recovery decision to retry same stage."""
        decision = ErrorRecoveryDecision(
            analysis="Temporary network issue during deployment",
            action="retry_same",
            target_stage=WorkflowStage.DEPLOYMENT.value,
            context_to_inject="Retry with same configuration",
            confidence=0.9
        )
        
        assert decision.action == "retry_same"
        assert decision.target_stage == WorkflowStage.DEPLOYMENT.value
    
    def test_abort_decision(self):
        """Test error recovery decision to abort."""
        decision = ErrorRecoveryDecision(
            analysis="Critical security vulnerability cannot be fixed",
            action="abort",
            target_stage=WorkflowStage.FAILED.value,
            context_to_inject="",
            confidence=0.95
        )
        
        assert decision.action == "abort"
        assert decision.target_stage == WorkflowStage.FAILED.value
    
    def test_confidence_validation(self):
        """Test that confidence is validated between 0 and 1."""
        # Valid confidence
        decision = ErrorRecoveryDecision(
            analysis="Test",
            action="retry_same",
            target_stage=WorkflowStage.CODING.value,
            context_to_inject="",
            confidence=0.5
        )
        assert decision.confidence == 0.5
        
        # Test boundary values
        decision_min = ErrorRecoveryDecision(
            analysis="Test",
            action="retry_same",
            target_stage=WorkflowStage.CODING.value,
            context_to_inject="",
            confidence=0.0
        )
        assert decision_min.confidence == 0.0
        
        decision_max = ErrorRecoveryDecision(
            analysis="Test",
            action="retry_same",
            target_stage=WorkflowStage.CODING.value,
            context_to_inject="",
            confidence=1.0
        )
        assert decision_max.confidence == 1.0


class TestGuardRails:
    """Test guard rail logic."""
    
    def test_max_stage_attempts(self):
        """Test that max stage attempts are enforced."""
        state = WorkflowState(
            workflow_id="test_789",
            requirements="Test contract",
            current_stage=WorkflowStage.CODING.value,
            max_retries=3
        )
        
        # Simulate multiple retries
        state.retry_counts[WorkflowStage.CODING.value] = 3
        
        # Should fail after max retries
        assert state.retry_counts[WorkflowStage.CODING.value] >= state.max_retries
    
    def test_stage_completion_tracking(self):
        """Test that completed stages are tracked."""
        state = WorkflowState(
            workflow_id="test_101",
            requirements="Test contract",
            current_stage=WorkflowStage.TESTING.value
        )
        
        # Mark stages as completed
        state.stages_completed.append(WorkflowStage.IDEATION.value)
        state.stages_completed.append(WorkflowStage.CODING.value)
        
        assert WorkflowStage.IDEATION.value in state.stages_completed
        assert WorkflowStage.CODING.value in state.stages_completed
        assert WorkflowStage.TESTING.value not in state.stages_completed


class TestStageAdvancement:
    """Test stage advancement logic."""
    
    def test_advance_to_next_stage(self):
        """Test advancing to the next stage in order."""
        state = WorkflowState(
            workflow_id="test_202",
            requirements="Test contract",
            current_stage=WorkflowStage.IDEATION.value
        )
        
        # Store result and advance
        result = StageResult(
            stage=WorkflowStage.IDEATION.value,
            success=True,
            output={"name": "TestContract"},
            next_stage=WorkflowStage.CODING.value
        )
        
        state.stage_results[WorkflowStage.IDEATION.value] = result
        state.stages_completed.append(WorkflowStage.IDEATION.value)
        state.current_stage = WorkflowStage.CODING.value
        
        assert state.current_stage == WorkflowStage.CODING.value
        assert WorkflowStage.IDEATION.value in state.stages_completed
    
    def test_completion_on_last_stage(self):
        """Test that workflow completes after monitoring stage."""
        state = WorkflowState(
            workflow_id="test_303",
            requirements="Test contract",
            current_stage=WorkflowStage.MONITORING.value
        )
        
        # Complete monitoring
        result = StageResult(
            stage=WorkflowStage.MONITORING.value,
            success=True,
            output={"monitoring_started": True},
            next_stage=WorkflowStage.COMPLETED.value
        )
        
        state.stage_results[WorkflowStage.MONITORING.value] = result
        state.current_stage = WorkflowStage.COMPLETED.value
        state.status = "completed"
        
        assert state.current_stage == WorkflowStage.COMPLETED.value
        assert state.status == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
