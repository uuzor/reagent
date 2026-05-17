"""Context relevance scoring agent.

Replaces the hardcoded relevance_score = 1.0 default in context.py:30.
Agent scores context entries based on relevance to current stage and workflow goals.
"""

from typing import Optional

# Stage relevance keywords — what each stage cares about
_STAGE_KEYWORDS = {
    "ideation": ["requirements", "features", "standards", "blockchain", "token", "erc", "use case", "market"],
    "coding": ["implementation", "solidity", "function", "contract", "modifier", "library", "openzeppelin", "inheritance"],
    "testing": ["test", "assert", "coverage", "edge case", "unit", "integration", "gas", "benchmark"],
    "auditing": ["vulnerability", "security", "reentrancy", "overflow", "access control", "audit", "risk", "exploit"],
    "deployment": ["deploy", "network", "gas", "address", "constructor", "verify", "etherscan", "mainnet"],
    "monitoring": ["monitor", "event", "alert", "log", "dashboard", "health", "uptime", "incident"],
}

# Keyword weight multipliers for different sources
_SOURCE_WEIGHTS = {
    "user_input": 1.5,
    "stage_output": 1.0,
    "error_recovery": 2.0,
    "market_research": 0.5,
    "preference": 1.2,
    "project_context": 1.0,
}


def score_context_relevance(
    content: str,
    source: str,
    current_stage: str,
    workflow_goals: Optional[list[str]] = None,
) -> float:
    """
    Score a context entry's relevance to the current stage.

    Args:
        content: The context entry content
        source: Where the entry came from (ContextSource value)
        current_stage: Current workflow stage
        workflow_goals: List of high-priority goal keywords

    Returns:
        Relevance score between 0.0 and 3.0 (higher = more relevant).
    """
    content_lower = content.lower()
    stage_keywords = _STAGE_KEYWORDS.get(current_stage, [])

    # Count stage-relevant keyword matches
    keyword_matches = sum(1 for kw in stage_keywords if kw in content_lower)
    keyword_score = keyword_matches / max(len(stage_keywords), 1)

    # Source weight
    source_weight = _SOURCE_WEIGHTS.get(source, 1.0)

    # Goal boost
    goal_boost = 0.0
    if workflow_goals:
        goal_matches = sum(1 for g in workflow_goals if g.lower() in content_lower)
        goal_boost = (goal_matches / max(len(workflow_goals), 1)) * 0.5

    # Final score: keyword relevance * source weight + goal boost
    score = min(keyword_score * source_weight + goal_boost + 0.3, 3.0)
    return round(score, 2)


def calculate_context_budget(
    model: str = "default",
    remaining_tokens: int = 4000,
    context_overhead_ratio: float = 0.15,
) -> int:
    """
    Calculate how many context entries fit in the remaining token budget.

    Args:
        model: Model identifier
        remaining_tokens: Tokens remaining in context window
        context_overhead_ratio: Fraction of remaining tokens for context (0.1-0.3)

    Returns:
        Maximum number of context entries to include.
    """
    # Average entry is ~50 tokens
    avg_entry_tokens = 50

    # Budget for context entries
    context_budget = int(remaining_tokens * context_overhead_ratio)

    # Number of entries that fit
    max_entries = context_budget // avg_entry_tokens

    # Clamp between 5 and 50
    return max(5, min(max_entries, 50))
