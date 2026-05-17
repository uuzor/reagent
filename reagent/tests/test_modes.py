"""Tests for the mode switching system."""
import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from modes import ExecutionMode, ModeConfig


class TestExecutionMode:
    def test_plan_mode(self):
        assert ExecutionMode.PLAN.value == "plan"

    def test_orchestrate_mode(self):
        assert ExecutionMode.ORCHESTRATE.value == "orchestrate"

    def test_code_mode(self):
        assert ExecutionMode.CODE.value == "code"


class TestModeConfig:
    def test_default_is_orchestrate(self):
        config = ModeConfig()
        assert config.mode == ExecutionMode.ORCHESTRATE

    def test_plan_config(self):
        config = ModeConfig(mode=ExecutionMode.PLAN)
        assert config.mode == ExecutionMode.PLAN
        assert config.plan_depth == "detailed"

    def test_code_config(self):
        config = ModeConfig(mode=ExecutionMode.CODE)
        assert config.mode == ExecutionMode.CODE
        assert config.code_include_tests is True
        assert config.code_include_deployment is False
        assert config.code_target_blockchain == "ethereum"

    def test_custom_code_config(self):
        config = ModeConfig(
            mode=ExecutionMode.CODE,
            code_target_blockchain="polygon",
            code_include_tests=False,
            code_include_deployment=True,
        )
        assert config.code_target_blockchain == "polygon"
        assert config.code_include_tests is False
        assert config.code_include_deployment is True

    def test_orchestrate_config(self):
        config = ModeConfig(mode=ExecutionMode.ORCHESTRATE)
        assert config.max_iterations == 20
        assert config.max_retries_per_stage == 3

    def test_mode_from_string(self):
        """Test that mode can be created from string value."""
        config = ModeConfig(mode=ExecutionMode("plan"))
        assert config.mode == ExecutionMode.PLAN

        config2 = ModeConfig(mode=ExecutionMode("code"))
        assert config2.mode == ExecutionMode.CODE

    def test_invalid_mode_raises(self):
        """Invalid mode string should raise ValueError."""
        with pytest.raises(ValueError):
            ModeConfig(mode=ExecutionMode("invalid"))

    def test_compute_tier_preference(self):
        config = ModeConfig()
        assert config.preferred_compute_tier == "codespaces"

        config_premium = ModeConfig(preferred_compute_tier="nosana")
        assert config_premium.preferred_compute_tier == "nosana"
