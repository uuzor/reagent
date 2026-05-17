"""Dynamic cost pricing agent.

Replaces hardcoded GPT-4o rates in graph/observability.py:71-74
with a pricing database supporting multiple models and providers.
"""

from typing import Optional

# Model pricing database (per 1M tokens, USD)
_MODEL_PRICING = {
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00, "provider": "openai"},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "provider": "openai"},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00, "provider": "openai"},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50, "provider": "openai"},

    # Anthropic
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00, "provider": "anthropic"},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00, "provider": "anthropic"},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00, "provider": "anthropic"},

    # Qwen (via OpenRouter/DashScope)
    "qwen-max": {"input": 0.80, "output": 2.40, "provider": "dashscope"},
    "qwen-plus": {"input": 0.40, "output": 1.20, "provider": "dashscope"},
    "qwen-turbo": {"input": 0.05, "output": 0.20, "provider": "dashscope"},
    "qwen-coder": {"input": 0.50, "output": 1.50, "provider": "openrouter"},

    # Other
    "llama-3-70b": {"input": 0.50, "output": 0.75, "provider": "openrouter"},
    "mistral-large": {"input": 2.00, "output": 6.00, "provider": "mistral"},
    "deepseek-coder": {"input": 0.14, "output": 0.28, "provider": "deepseek"},

    # Default fallback
    "default": {"input": 2.50, "output": 10.00, "provider": "unknown"},
}


def get_model_pricing(model_name: str) -> dict:
    """
    Get pricing for a specific model.

    Args:
        model_name: Model identifier (e.g., "gpt-4o", "qwen-max")

    Returns:
        Dict with "input" and "output" pricing per 1M tokens, plus "provider".
    """
    # Direct match
    if model_name in _MODEL_PRICING:
        return _MODEL_PRICING[model_name]

    # Partial match (e.g., "gpt-4o-2024-05-13" → "gpt-4o")
    for key, pricing in _MODEL_PRICING.items():
        if key in model_name.lower():
            return pricing

    # Provider-based fallback
    if "qwen" in model_name.lower():
        return _MODEL_PRICING["qwen-max"]
    if "claude" in model_name.lower():
        return _MODEL_PRICING["claude-sonnet-4-20250514"]
    if "gpt" in model_name.lower():
        return _MODEL_PRICING["gpt-4o"]
    if "llama" in model_name.lower():
        return _MODEL_PRICING["llama-3-70b"]

    return _MODEL_PRICING["default"]


def get_cost_summary(
    input_tokens: int,
    output_tokens: int,
    model_name: str = "default",
) -> dict:
    """
    Calculate cost for a given token usage.

    Args:
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens
        model_name: Model identifier

    Returns:
        Dict with input_cost, output_cost, total_cost, and pricing info.
    """
    pricing = get_model_pricing(model_name)

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return {
        "model": model_name,
        "provider": pricing["provider"],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost_usd": round(input_cost, 6),
        "output_cost_usd": round(output_cost, 6),
        "total_cost_usd": round(input_cost + output_cost, 6),
        "pricing_per_million": pricing,
    }
