"""
Context Injection System (Mind Building)
Provides structured, accumulating context that persists across stages
and can be injected into every AI call. This replaces the ad-hoc
recovery_context pattern with a rich, typed context system.
"""
import time
from enum import Enum
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field


class ContextSource(str, Enum):
    """Where a context entry came from."""
    USER_INPUT = "user_input"
    STAGE_OUTPUT = "stage_output"
    ERROR_RECOVERY = "error_recovery"
    MARKET_RESEARCH = "market_research"
    PREFERENCE = "preference"
    PROJECT_CONTEXT = "project_context"


class ContextEntry(BaseModel):
    """A single piece of accumulated context."""
    source: ContextSource
    content: str
    stage: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)
    relevance_score: float = 1.0


class AgentContext(BaseModel):
    """Accumulated 'mind' of the agent for a workflow.

    Grows over time as stages execute, errors occur, and user provides input.
    Injected into every AI call via router.ai().
    """
    workflow_id: str
    user_id: Optional[str] = None
    entries: List[ContextEntry] = Field(default_factory=list)
    project_context: Dict[str, Any] = Field(default_factory=dict)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    active_recovery: Optional[str] = None

    # Compute tier info
    user_tier: str = "free"
    github_connected: bool = False
    nosana_connected: bool = False

    def add_entry(
        self,
        source: ContextSource,
        content: str,
        stage: Optional[str] = None,
        relevance_score: float = 1.0,
    ) -> None:
        """Add a context entry."""
        self.entries.append(ContextEntry(
            source=source,
            content=content,
            stage=stage,
            relevance_score=relevance_score,
        ))

    def set_recovery_context(self, error: str, stage: str) -> None:
        """Set recovery context from a failure."""
        self.active_recovery = f"[{stage} failure]: {error}"
        self.add_entry(ContextSource.ERROR_RECOVERY, self.active_recovery, stage)

    def clear_recovery_context(self) -> None:
        """Clear recovery context after successful retry."""
        self.active_recovery = None

    def build_injection_prompt(self, max_entries: int = 20) -> str:
        """Build a condensed prompt injection from accumulated context.

        Selects the most relevant recent entries and formats them
        for inclusion in AI system/user prompts.
        """
        if not self.entries and not self.project_context and not self.user_preferences and not self.active_recovery:
            return ""

        parts = []

        # Project context
        if self.project_context:
            parts.append("## Project Context")
            for key, value in self.project_context.items():
                parts.append(f"- {key}: {value}")

        # User preferences
        if self.user_preferences:
            parts.append("\n## User Preferences")
            for key, value in self.user_preferences.items():
                parts.append(f"- {key}: {value}")

        # Active recovery context (highest priority)
        if self.active_recovery:
            parts.append("\n## Active Recovery")
            parts.append(self.active_recovery)

        # Recent context entries (sorted by relevance, then recency)
        if self.entries:
            parts.append("\n## Context History")
            # Take last max_entries, prioritizing high relevance
            sorted_entries = sorted(
                self.entries[-max_entries * 2:],
                key=lambda e: (e.relevance_score, e.timestamp),
                reverse=True,
            )[:max_entries]

            for entry in sorted_entries:
                stage_label = f" [{entry.stage}]" if entry.stage else ""
                parts.append(f"- [{entry.source.value}]{stage_label}: {entry.content[:200]}")

        return "\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentContext":
        """Deserialize from persistence."""
        return cls(**data)
