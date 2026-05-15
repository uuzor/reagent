Routers
Organize reasoners and skills into namespaced modules with AgentRouter

Router — namespace grouping for agent endpoints
Organize reasoners and skills into reusable, namespaced modules -- like FastAPI's APIRouter for agents.

Routers matter once an agent grows beyond a handful of functions. They do not just organize code. They shape the public callable surface of your agent by turning prefixes into namespaced function IDs.

Python
TypeScript

from agentfield import Agent, AgentRouter
users = AgentRouter(prefix="users", tags=["users"])
billing = AgentRouter(prefix="billing", tags=["billing"])
@users.reasoner()
async def analyze_behavior(user_id: str) -> dict:
    return await users.ai(
        system="Summarize this user's activity and churn risk.",
        user=user_id,
    )
@billing.skill()
def current_plan(user_id: str) -> dict:
    return {"user_id": user_id, "plan": "growth"}
app = Agent(node_id="user-agent")
app.include_router(users)
app.include_router(billing)
app.run()
# Callable targets: user-agent.users_analyze_behavior
#                   user-agent.billing_current_plan
What just happened

Two logical domains became one agent with a cleaner public API
Router prefixes became part of the callable function identity
The same router pattern can be reused across multiple agents or packages
Concrete target examples:


user-agent.users_analyze_behavior
user-agent.billing_current_plan
Patterns
Multi-module agent
Python
TypeScript

from agentfield import Agent, AgentRouter
# --- users module ---
users = AgentRouter(prefix="users", tags=["users"])
@users.skill()
async def get_profile(user_id: str) -> dict:
    return await db.users.find_one({"_id": user_id})
@users.reasoner()
async def summarize_activity(user_id: str) -> dict:
    profile = await get_profile(user_id)
    return await users.ai(
        system="Summarize this user's recent activity.",
        user=str(profile),
    )
# --- analytics module ---
analytics = AgentRouter(prefix="analytics", tags=["analytics"])
@analytics.skill()
async def page_views(path: str, days: int = 7) -> dict:
    return await metrics_db.aggregate(path, days)
@analytics.reasoner()
async def traffic_insights(path: str) -> dict:
    views = await page_views(path, days=30)
    return await analytics.ai(
        system="Analyze traffic patterns and suggest improvements.",
        user=str(views),
    )
# --- assemble ---
app = Agent(node_id="platform-api")
app.include_router(users)
app.include_router(analytics)
app.run()
Shared utility router
Python

# utils/text.py -- reusable across multiple agents
from agentfield import AgentRouter
text_utils = AgentRouter(prefix="text", tags=["utils"])
@text_utils.skill()
def word_count(text: str) -> dict:
    words = text.split()
    return {"count": len(words), "unique": len(set(words))}
@text_utils.skill()
def truncate(text: str, max_length: int = 100) -> dict:
    truncated = text[:max_length] + "..." if len(text) > max_length else text
    return {"text": truncated, "was_truncated": len(text) > max_length}

# agent_a.py
from agentfield import Agent
from utils.text import text_utils
app = Agent(node_id="agent-a")
app.include_router(text_utils)
app.run()

# agent_b.py -- same router, different agent
from agentfield import Agent
from utils.text import text_utils
app = Agent(node_id="agent-b")
app.include_router(text_utils)
app.run()
Go alternative: naming conventions
Since Go does not have AgentRouter, use consistent naming and tags:

Go

// Register "math" module functions with naming convention
a.RegisterReasoner("math_solve", solveFn,
    agent.WithReasonerTags("math", "utils"),
    agent.WithDescription("Solve a math equation"),
)
a.RegisterReasoner("math_add", addFn,
    agent.WithReasonerTags("math", "utils"),
    agent.WithDescription("Add two numbers"),
)
a.RegisterReasoner("math_multiply", multiplyFn,
    agent.WithReasonerTags("math", "utils"),
    agent.WithDescription("Multiply two numbers"),
)
// Callers use the same "agent.math_add" convention
result, err := a.Call(ctx, "calculator.math_add", map[string]any{"a": 2, "b": 3})