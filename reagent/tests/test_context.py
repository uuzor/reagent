"""Tests for the context injection (mind building) system."""
import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from context import AgentContext, ContextEntry, ContextSource


class TestContextEntry:
    def test_create_entry(self):
        entry = ContextEntry(
            source=ContextSource.USER_INPUT,
            content="Build an ERC20 token",
            stage="ideation",
        )
        assert entry.source == ContextSource.USER_INPUT
        assert entry.content == "Build an ERC20 token"
        assert entry.stage == "ideation"
        assert entry.relevance_score == 1.0


class TestAgentContext:
    def setup_method(self):
        self.ctx = AgentContext(workflow_id="wf_test")

    def test_initial_state(self):
        assert self.ctx.workflow_id == "wf_test"
        assert len(self.ctx.entries) == 0
        assert self.ctx.active_recovery is None
        assert self.ctx.user_tier == "free"

    def test_add_entry(self):
        self.ctx.add_entry(ContextSource.USER_INPUT, "Build ERC20", stage="ideation")
        assert len(self.ctx.entries) == 1
        assert self.ctx.entries[0].source == ContextSource.USER_INPUT

    def test_multiple_entries(self):
        self.ctx.add_entry(ContextSource.USER_INPUT, "reqs")
        self.ctx.add_entry(ContextSource.STAGE_OUTPUT, "spec done", stage="ideation")
        self.ctx.add_entry(ContextSource.MARKET_RESEARCH, "bullish", stage="ideation")
        assert len(self.ctx.entries) == 3

    def test_set_recovery_context(self):
        self.ctx.set_recovery_context("compilation failed", "coding")
        assert self.ctx.active_recovery is not None
        assert "coding" in self.ctx.active_recovery
        assert "compilation failed" in self.ctx.active_recovery
        # Also adds an entry
        assert any(e.source == ContextSource.ERROR_RECOVERY for e in self.ctx.entries)

    def test_clear_recovery_context(self):
        self.ctx.set_recovery_context("error", "testing")
        assert self.ctx.active_recovery is not None
        self.ctx.clear_recovery_context()
        assert self.ctx.active_recovery is None


class TestBuildInjectionPrompt:
    def test_empty_context(self):
        ctx = AgentContext(workflow_id="wf_empty")
        prompt = ctx.build_injection_prompt()
        assert prompt == ""

    def test_with_project_context(self):
        ctx = AgentContext(
            workflow_id="wf_test",
            project_context={"blockchain": "ethereum", "solidity_version": "0.8.20"},
        )
        prompt = ctx.build_injection_prompt()
        assert "Project Context" in prompt
        assert "ethereum" in prompt
        assert "0.8.20" in prompt

    def test_with_user_preferences(self):
        ctx = AgentContext(
            workflow_id="wf_test",
            user_preferences={"style": "minimal", "testing": "comprehensive"},
        )
        prompt = ctx.build_injection_prompt()
        assert "User Preferences" in prompt
        assert "minimal" in prompt

    def test_with_recovery(self):
        ctx = AgentContext(workflow_id="wf_test")
        ctx.set_recovery_context("test failed", "testing")
        prompt = ctx.build_injection_prompt()
        assert "Active Recovery" in prompt
        assert "test failed" in prompt

    def test_with_entries(self):
        ctx = AgentContext(workflow_id="wf_test")
        ctx.add_entry(ContextSource.USER_INPUT, "Build ERC20", stage="ideation")
        ctx.add_entry(ContextSource.STAGE_OUTPUT, "Spec generated", stage="ideation")
        prompt = ctx.build_injection_prompt()
        assert "Context History" in prompt
        assert "user_input" in prompt
        assert "stage_output" in prompt

    def test_max_entries_limit(self):
        ctx = AgentContext(workflow_id="wf_test")
        for i in range(30):
            ctx.add_entry(ContextSource.STAGE_OUTPUT, f"entry {i}")
        prompt = ctx.build_injection_prompt(max_entries=10)
        # Should not contain all 30 entries
        assert prompt.count("entry") <= 12  # 10 entries + possible header lines


class TestSerialization:
    def test_to_dict_and_from_dict(self):
        ctx = AgentContext(
            workflow_id="wf_test",
            user_id="user123",
            project_context={"chain": "polygon"},
            user_preferences={"style": "gas-optimized"},
            user_tier="premium",
            github_connected=True,
        )
        ctx.add_entry(ContextSource.USER_INPUT, "Build token")
        ctx.set_recovery_context("audit failed", "auditing")

        data = ctx.to_dict()
        restored = AgentContext.from_dict(data)

        assert restored.workflow_id == "wf_test"
        assert restored.user_id == "user123"
        assert restored.project_context["chain"] == "polygon"
        assert restored.user_preferences["style"] == "gas-optimized"
        assert restored.user_tier == "premium"
        assert restored.github_connected is True
        assert len(restored.entries) == 2  # user_input + error_recovery
        assert restored.active_recovery is not None

    def test_round_trip_preserves_all_fields(self):
        ctx = AgentContext(
            workflow_id="wf_roundtrip",
            nosana_connected=True,
        )
        ctx.add_entry(ContextSource.MARKET_RESEARCH, "DeFi trends up", stage="ideation", relevance_score=0.8)

        data = ctx.to_dict()
        restored = AgentContext.from_dict(data)

        assert restored.nosana_connected is True
        assert restored.entries[0].relevance_score == 0.8
        assert restored.entries[0].source == ContextSource.MARKET_RESEARCH
