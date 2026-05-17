"""Adaptive retry agent.

Replaces the triple-declared MAX_RETRIES = 3 in edges.py, modes.py, orchestrator_router.py.
Agent classifies errors and decides retry counts based on severity and type.
"""

from enum import Enum
from pydantic import BaseModel, Field


class ErrorType(str, Enum):
    """Classification of error types."""
    TRANSIENT = "transient"       # Network timeout, rate limit — retryable
    COMPILATION = "compilation"   # Syntax error — retry may help with fixes
    STRUCTURAL = "structural"     # Logic error — needs code rewrite, not retry
    RESOURCE = "resource"         # Out of memory/disk — may succeed on retry
    PERMISSION = "permission"     # Auth/permission — won't self-resolve
    UNKNOWN = "unknown"


class RetryDecision(BaseModel):
    """Agent decision on retry behavior."""
    error_type: ErrorType = Field(description="Classification of the error")
    should_retry: bool = Field(description="Whether to retry")
    retry_count: int = Field(description="Recommended number of retries", ge=0, le=10)
    backoff_seconds: float = Field(description="Recommended backoff between retries", ge=0)
    reason: str = Field(description="Explanation of the retry decision")


def classify_error(error_message: str, stage: str = "") -> ErrorType:
    """
    Classify an error message into an error type.

    Uses pattern matching to determine if the error is transient,
    structural, or another category.
    """
    msg = error_message.lower()

    # Transient errors
    if any(kw in msg for kw in ["timeout", "timed out", "rate limit", "429", "connection refused", "econnrefused"]):
        return ErrorType.TRANSIENT

    # Compilation errors
    if any(kw in msg for kw in ["syntaxerror", "parse error", "compilation failed", "solc", "undeclared identifier"]):
        return ErrorType.COMPILATION

    # Resource errors
    if any(kw in msg for kw in ["out of memory", "oom", "disk full", "no space left", "ENOMEM"]):
        return ErrorType.RESOURCE

    # Permission errors
    if any(kw in msg for kw in ["permission denied", "unauthorized", "401", "403", "access denied"]):
        return ErrorType.PERMISSION

    # Structural errors (logic issues, test failures)
    if any(kw in msg for kw in ["assertion failed", "test failed", "assertionerror", "reentrancy", "overflow"]):
        return ErrorType.STRUCTURAL

    return ErrorType.UNKNOWN


def decide_retry_count(
    error_message: str,
    stage: str = "",
    previous_retries: int = 0,
    max_allowed: int = 5,
) -> RetryDecision:
    """
    Decide whether and how many times to retry based on error classification.

    Args:
        error_message: The error message to analyze
        stage: The workflow stage where the error occurred
        previous_retries: How many retries have already been attempted
        max_allowed: Maximum retries allowed (from ModeConfig)

    Returns:
        RetryDecision with error type, retry count, and backoff.
    """
    error_type = classify_error(error_message, stage)

    if error_type == ErrorType.TRANSIENT:
        # Transient errors benefit from exponential backoff retries
        remaining = min(max_allowed - previous_retries, 5)
        return RetryDecision(
            error_type=error_type,
            should_retry=remaining > 0,
            retry_count=remaining,
            backoff_seconds=2.0 ** previous_retries,  # Exponential backoff
            reason=f"Transient error ({error_message[:80]}), retrying with backoff",
        )

    elif error_type == ErrorType.COMPILATION:
        # Compilation errors may resolve if spec is refined
        remaining = min(max_allowed - previous_retries, 3)
        return RetryDecision(
            error_type=error_type,
            should_retry=remaining > 0,
            retry_count=remaining,
            backoff_seconds=1.0,
            reason=f"Compilation error, may resolve with spec refinement",
        )

    elif error_type == ErrorType.RESOURCE:
        # Resource errors may resolve if system recovers
        remaining = min(max_allowed - previous_retries, 2)
        return RetryDecision(
            error_type=error_type,
            should_retry=remaining > 0,
            retry_count=remaining,
            backoff_seconds=5.0,
            reason=f"Resource error, retrying after backoff",
        )

    elif error_type == ErrorType.STRUCTURAL:
        # Structural errors need code changes, not retries
        return RetryDecision(
            error_type=error_type,
            should_retry=False,
            retry_count=0,
            backoff_seconds=0,
            reason=f"Structural error, needs code rewrite not retry",
        )

    elif error_type == ErrorType.PERMISSION:
        # Permission errors won't self-resolve
        return RetryDecision(
            error_type=error_type,
            should_retry=False,
            retry_count=0,
            backoff_seconds=0,
            reason=f"Permission error, won't self-resolve",
        )

    # Unknown errors: conservative retry
    remaining = min(max_allowed - previous_retries, 2)
    return RetryDecision(
        error_type=error_type,
        should_retry=remaining > 0,
        retry_count=remaining,
        backoff_seconds=3.0,
        reason=f"Unknown error type, conservative retry",
    )
