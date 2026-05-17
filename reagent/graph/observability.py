"""Observability utilities for LangGraph workflows.

Phase 5: Cost tracking, structured logging, and LangSmith tracing integration.
"""

import logging
import time
from typing import Any, Dict, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


# ──────────────────────────────────────────────────────────────
# Structured logging
# ──────────────────────────────────────────────────────────────

workflow_logger = logging.getLogger("reagent.workflow")


def log_stage_event(
    event: str,
    workflow_id: str,
    stage: str,
    data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    """
    Log a workflow stage event with structured fields.

    Every log entry includes workflow_id for correlation.

    Args:
        event: "start", "complete", "error"
        workflow_id: Workflow identifier
        stage: Stage name
        data: Optional structured data payload
        error: Optional error message
    """
    extra = {
        "workflow_id": workflow_id,
        "stage": stage,
        "event": event,
    }
    if data:
        extra["data"] = data
    if error:
        extra["error"] = error

    if event == "error":
        workflow_logger.error(f"Workflow stage error: {stage}", extra=extra)
    elif event == "complete":
        workflow_logger.info(f"Workflow stage complete: {stage}", extra=extra)
    else:
        workflow_logger.debug(f"Workflow stage start: {stage}", extra=extra)


# ──────────────────────────────────────────────────────────────
# Cost tracking callback
# ──────────────────────────────────────────────────────────────

class CostTrackingCallback(BaseCallbackHandler):
    """
    LangChain callback that tracks AI API costs per workflow stage.

    Uses dynamic pricing from agents.pricing_agent to support multiple
    models and providers (OpenAI, Anthropic, Qwen, etc.).
    """

    def __init__(self, workflow_id: str = "", model_name: str = "default"):
        super().__init__()
        from agents.pricing_agent import get_model_pricing
        self.workflow_id = workflow_id
        self.model_name = model_name
        self.pricing = get_model_pricing(model_name)
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.stage_costs: Dict[str, Dict[str, float]] = {}
        self._current_stage: str = ""
        self._stage_start: float = 0.0

    def set_stage(self, stage: str) -> None:
        """Mark the beginning of a stage for cost attribution."""
        self._current_stage = stage
        self._stage_start = time.time()
        self.stage_costs.setdefault(stage, {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "duration_s": 0.0,
        })

    def on_llm_start(self, serialized: Dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        """Called when LLM invocation starts."""
        pass

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called when LLM invocation completes. Extracts token usage."""
        usage = response.llm_output.get("token_usage", {}) if response.llm_output else {}
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        cost = (
            (input_tokens / 1_000_000) * self.pricing["input"]
            + (output_tokens / 1_000_000) * self.pricing["output"]
        )
        self.total_cost_usd += cost

        if self._current_stage:
            stage_data = self.stage_costs[self._current_stage]
            stage_data["input_tokens"] += input_tokens
            stage_data["output_tokens"] += output_tokens
            stage_data["cost_usd"] += cost
            stage_data["duration_s"] += time.time() - self._stage_start

    def get_summary(self) -> Dict[str, Any]:
        """Get cost summary for the entire workflow."""
        return {
            "workflow_id": self.workflow_id,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "stage_costs": self.stage_costs,
        }


# ──────────────────────────────────────────────────────────────
# LangSmith tracing
# ──────────────────────────────────────────────────────────────

def enable_langsmith_tracing(project_name: str = "reagent") -> None:
    """
    Enable LangSmith tracing for the workflow.

    Set these environment variables before calling:
    - LANGCHAIN_TRACING_V2=true
    - LANGCHAIN_API_KEY=your_key
    - LANGCHAIN_PROJECT=reagent

    Args:
        project_name: LangSmith project name
    """
    import os
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", project_name)


def is_langsmith_enabled() -> bool:
    """Check if LangSmith tracing is configured."""
    import os
    return os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"
