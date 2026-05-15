Skills
Deterministic functions for business logic, integrations, and data processing

Skill — deterministic function, no LLM needed
Deterministic functions for business logic that need the same infrastructure as reasoners -- without the AI.

This separation matters in production. When something breaks, you want to know whether the failure came from AI judgment or deterministic code. Skills are where you put systems-of-record access, calculations, API calls, and repeatable side effects.

Python
TypeScript
Go

from agentfield import Agent
from pydantic import BaseModel
app = Agent(node_id="inventory-service", version="1.0.0")
class StockQuery(BaseModel):
    sku: str
    warehouse: str = "us-east"
@app.skill(tags=["database", "inventory"])
async def check_stock(query: StockQuery) -> dict:
    """Fetch deterministic inventory state."""
    row = await db.execute(
        "SELECT sku, qty, reserved FROM stock WHERE sku = $1 AND warehouse = $2",
        query.sku, query.warehouse,
    )
    if not row:
        return {"sku": query.sku, "available": 0, "status": "not_found"}
    available = row["qty"] - row["reserved"]
    return {"sku": query.sku, "available": available, "status": "in_stock" if available > 0 else "out_of_stock"}
@app.skill(tags=["integrations", "shipping", "policy"])
async def fulfillable_quote(sku: str, dest: str, weight_kg: float) -> dict:
    stock = await check_stock(StockQuery(sku=sku))
    if stock["available"] <= 0:
        return {"sku": sku, "fulfillable": False, "reason": "out_of_stock"}
    rates = await fedex_client.rate_quote(origin="us-east", dest=dest, weight=weight_kg)
    return {"sku": sku, "fulfillable": True, "rates": rates, "currency": "USD"}
app.run()
# → POST /skills/check_stock  — auto-generated REST endpoint with input validation
# → POST /skills/fulfillable_quote  — discoverable by any agent in the fleet
What just happened

Skills handled deterministic state and policy logic without any model call
The second skill composed the first skill into a production-shaped workflow
Both skills inherited the same endpoint generation, discoverability, and execution tracking as reasoners
In Go, the same deterministic pattern is registered with RegisterReasoner and exposed under /reasoners/{name} instead of /skills/{name}
Example proof:


Python/TypeScript:
POST /skills/check_stock
POST /skills/fulfillable_quote
discoverable target: inventory-service.fulfillable_quote
Go:
POST /reasoners/check_stock
Skills vs Reasoners
Aspect	Reasoner	Skill
Purpose	AI-powered inference and generation	Deterministic business logic
LLM calls	Typically uses app.ai() or app.harness()	Typically no LLM calls
Output	May vary across runs	Same input always produces same output
Use cases	Classification, generation, analysis	API calls, database ops, calculations, formatting
Endpoint prefix	/reasoners/{name}	/skills/{name}
Both share the same execution infrastructure: workflow tracking, execution context, verifiable credentials, and cross-agent communication.

Patterns
Database integration skill
Skills are ideal for wrapping database queries with validation and consistent return shapes:

Python
TypeScript

from pydantic import BaseModel
from typing import Optional
class UserQuery(BaseModel):
    user_id: str
    fields: list[str] = ["name", "email"]
@app.skill(tags=["database", "users"])
async def get_user(query: UserQuery) -> dict:
    # Skills can be async for I/O operations
    user = await db.users.find_one({"_id": query.user_id})
    if not user:
        return {"error": "User not found", "user_id": query.user_id}
    return {k: user.get(k) for k in query.fields if k in user}
MCP tool auto-registration (Python)
The Python SDK can automatically discover MCP servers and register their tools as skills:

Python

app = Agent(
    node_id="mcp-bridge",
    enable_mcp=True,
)
# MCP tools are automatically discovered and registered as skills
# with the naming pattern: {server_alias}_{tool_name}
# Each tool gets a /skills/{skill_name} endpoint
Combining skills and reasoners
A common pattern is using skills for data retrieval and reasoners for AI analysis:

Python
TypeScript

@app.skill(tags=["data"])
async def fetch_metrics(service: str, window: str = "24h") -> dict:
    metrics = await monitoring_api.query(service, window)
    return {"service": service, "metrics": metrics}
@app.reasoner(tags=["analysis"])
async def diagnose(service: str) -> dict:
    # Skill handles data retrieval (deterministic)
    metrics = await fetch_metrics(service, window="1h")
    # Reasoner handles AI analysis (non-deterministic)
    diagnosis = await app.ai(
        system="You are an SRE diagnosing service issues.",
        user=f"Analyze metrics for {service}: {metrics}",
    )
    return {"service": service, "diagnosis": diagnosis}