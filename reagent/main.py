"""reagent — AgentField agent node.

When you build a multi-reasoner system, REWRITE this file and the reasoners
package per the agentfield-multi-reasoner-builder skill's scaffold-recipe.
This template ships with one minimal entry reasoner so the scaffold runs
end-to-end on day one.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from agentfield import Agent, AIConfig

from reasoners import reasoners_router
from routers import (
    ideation_router,
    coding_router,
    testing_router,
    auditing_router,
    deployment_router,
    monitoring_router,
    orchestrator_router,
    github_router,
    compute_router,
    events_router,
    plan_router,
    code_router,
)
from routers.nosana_router import nosana_router

# Load local environment values from .env for development/runtime convenience.
load_dotenv(Path(__file__).resolve().parent / ".env")

def get_provider() -> str:
    explicit_provider = os.getenv("AI_PROVIDER")
    if explicit_provider:
        return explicit_provider
    if os.getenv("OPENROUTER_API_KEY"):
        return "openrouter"
    if os.getenv("QWEN_API_KEY"):
        return "qwen"
    return "openai"

def normalize_model_spec(model: str | None, provider: str) -> str | None:
    if not model:
        return None
    if model.startswith(f"{provider}/"):
        return model
    known_providers = {"openai", "openrouter", "qwen", "anthropic", "cohere", "huggingface", "google", "mistral", "aleph-alpha", "azure"}
    if "/" in model:
        prefix = model.split("/", 1)[0]
        if prefix in known_providers:
            return model
    return f"{provider}/{model}"


def parse_fallback_models(fallback_models: str | None, provider: str) -> list[str]:
    if not fallback_models:
        return []
    models = [m.strip() for m in fallback_models.split(",") if m.strip()]
    return [normalize_model_spec(m, provider) if "/" not in m else m for m in models]


provider = get_provider()
model = os.getenv("AI_MODEL")
if provider == "openrouter":
    model = normalize_model_spec(
        model or os.getenv("OPENROUTER_DEFAULT_MODEL", "poolside/laguna-m.1:free"),
        provider,
    )
elif provider == "qwen":
    model = normalize_model_spec(model or "qwen2.5-72b-instruct", provider)
else:
    model = normalize_model_spec(model or "gpt-4", provider)

api_key = (
    os.getenv("AI_API_KEY")
    or os.getenv("OPENROUTER_API_KEY")
    or os.getenv("OPENAI_API_KEY")
    or os.getenv("OPENAI_ADMIN_KEY")
    or os.getenv("QWEN_API_KEY")
)

fallback_models = parse_fallback_models(os.getenv("AI_FALLBACK_MODELS"), provider)
retry_attempts = int(os.getenv("AI_RATE_LIMIT_MAX_RETRIES", "5"))
retry_delay = float(os.getenv("AI_RATE_LIMIT_RETRY_DELAY", "1.0"))

timeout = int(os.getenv("AI_TIMEOUT", "600"))

enable_rate_limit_retry = os.getenv("AI_ENABLE_RATE_LIMIT_RETRY", "true").lower() in {"1", "true", "yes"}

print("[reagent] AI provider:", provider)
print("[reagent] AI model:", model)
print("[reagent] AI fallback models:", fallback_models)
print("[reagent] AI api_base:", os.getenv("AI_API_BASE", "https://openrouter.ai/api/v1") if provider == "openrouter" else os.getenv("AI_API_BASE"))
print("[reagent] AI timeout:", timeout)
print("[reagent] rate limit retry:", enable_rate_limit_retry, "retries:", retry_attempts)
print("[reagent] GitLab:", "configured" if os.getenv("GITLAB_TOKEN") else "not configured (GITLAB_TOKEN not set)")

app = Agent(
    node_id=os.getenv("AGENT_NODE_ID", "reagent"),
    agentfield_server=(
        os.getenv("AGENTFIELD_SERVER") or os.getenv("AGENTFIELD_CONTROL_PLANE_URL") or "http://localhost:8080"
    ),
    version="1.0.0",
    ai_config=AIConfig(
        api_base=os.getenv("AI_API_BASE", "https://openrouter.ai/api/v1") if provider == "openrouter" else os.getenv("AI_API_BASE"),
        api_key=api_key,
        model=model,
        fallback_models=fallback_models,
        enable_rate_limit_retry=enable_rate_limit_retry,
        rate_limit_max_retries=retry_attempts,
        rate_limit_base_delay=retry_delay,
        timeout=timeout,
        litellm_params={
            "drop_params": True,
        },
    ),
    dev_mode=True,
)

app.include_router(reasoners_router)
app.include_router(ideation_router)
app.include_router(coding_router)
app.include_router(testing_router)
app.include_router(auditing_router)
app.include_router(deployment_router)
app.include_router(monitoring_router)
app.include_router(orchestrator_router)
app.include_router(nosana_router)
app.include_router(github_router)
app.include_router(compute_router)
app.include_router(events_router)
app.include_router(plan_router)
app.include_router(code_router)

if __name__ == "__main__":
    # app.run() auto-detects CLI vs server mode (sdk/python/agentfield/agent.py:4194).
    # auto_port=False keeps the port deterministic so the README curl works.
    print(os.getenv("PORT", "8001"))
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8001")), auto_port=False)


