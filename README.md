# reagent

Agents
The core container that hosts reasoners, skills, and connects to the AgentField control plane

Agent container — one file, multiple endpoints
The top-level container that turns your code into a discoverable, governed, production microservice.

Without Agent, you would wire an HTTP server, registration, routing, identity, tracing, memory access, and cross-agent calls separately. With Agent, that infrastructure boundary is the object you instantiate.

Python
TypeScript
Go

from agentfield import Agent, AIConfig
from pydantic import BaseModel
app = Agent(
    node_id="support-triage",                                    # unique ID in the network
    ai_config=AIConfig(model="anthropic/claude-sonnet-4-20250514"),
)
class TicketClassification(BaseModel):
    priority: str      # "critical" | "high" | "normal" | "low"
    department: str    # route to the right team
    summary: str       # one-line summary for the queue
@app.reasoner()  # AI-powered — gets an LLM client automatically
async def classify_ticket(subject: str, body: str, customer_id: str) -> TicketClassification:
    result = await app.ai(
        system="You triage customer support tickets.",
        user=f"Subject: {subject}\n\n{body}",
        schema=TicketClassification,  # validated, typed output
    )
    await app.memory.set(f"ticket:{customer_id}:last_priority", result.priority)
    return result
@app.skill()  # deterministic — no AI, just business logic
def escalation_policy(priority: str) -> dict:
    sla = {"critical": 15, "high": 60, "normal": 240, "low": 1440}
    return {"sla_minutes": sla.get(priority, 240)}
app.run()  # starts HTTP server + registers with control plane
# POST /reasoners/classify_ticket  →  AI classification
# POST /skills/escalation_policy   →  SLA lookup
What just happened

One Agent instance exposed both AI and deterministic operations
The reasoner got model access, validation, and workflow context automatically
The deterministic function became a separate callable endpoint without extra server code
In all three SDKs, deterministic endpoints can be registered separately from AI-powered reasoners
The memory write used the same execution context as the reasoner
Example generated surface:


Python/TypeScript:
POST /reasoners/classify_ticket
POST /skills/escalation_policy
target: support-triage.classify_ticket
Go equivalent:
POST /reasoners/classify_ticket
POST /skills/escalation_policy
What You Get
HTTP server with auto-generated REST endpoints for every reasoner and skill
Control plane registration with heartbeat, lease renewal, and graceful shutdown
Cryptographic identity via automatic DID registration and verifiable credentials
Cross-agent communication through the AgentField execution gateway
Built-in AI client for structured LLM output with any provider
Memory system for distributed state across workflows and sessions
CLI mode for local testing and interactive debugging
Constructor Parameters
SDK Reference
Patterns
Environment-based configuration
Python
TypeScript
Go

import os
from agentfield import Agent, AIConfig
app = Agent(
    node_id=os.getenv("AGENT_ID", "my-agent"),
    agentfield_server=os.getenv("AGENTFIELD_SERVER"),
    ai_config=AIConfig(
        model=os.getenv("LLM_MODEL", "openai/gpt-4o"),
    ),
    dev_mode=os.getenv("DEV_MODE", "false").lower() == "true",
)
Serverless deployment
Python
TypeScript
Go

from agentfield import Agent
app = Agent(
    node_id="serverless-agent",
    callback_url="https://my-function.vercel.app",
)
@app.reasoner()
async def process(data: dict) -> dict:
    return {"processed": True, **data}
# Export the FastAPI app for serverless platforms
# Vercel, Railway, etc. use this directly
Cross-agent communication
Python
TypeScript
Go

@app.reasoner()
async def orchestrate(task: str) -> dict:
    # Call another agent's reasoner through the control plane
    analysis = await app.call("analyzer-agent.analyze", text=task)
    summary = await app.call("summarizer-agent.summarize", data=analysis)
    return {"task": task, "result": summary}