Reasoners
AI-powered functions with automatic workflow tracking, schema generation, and execution context

Reasoner — LLM-backed function with structured output
AI-powered functions that turn LLM calls into typed, tracked, auditable API endpoints.

The real production problem is not “how do I call a model?” It is “which parts of this workflow need AI judgment, and which parts need deterministic control?” Reasoners are where that boundary lives.

They are not just LLM wrappers. A reasoner combines AI analysis with your routing, validation, escalation, and side effects, then runs that workflow with full execution context and auditability.

Python
TypeScript
Go

from agentfield import Agent, AIConfig
from pydantic import BaseModel
app = Agent(
    node_id="support-triage",
    ai_config=AIConfig(model="anthropic/claude-sonnet-4-20250514"),
)
class TriageDecision(BaseModel):
    priority: str
    team: str
    escalate: bool
    reasoning: str
@app.reasoner(tags=["support", "triage"])
async def triage_ticket(subject: str, body: str, account_tier: str) -> dict:
    decision = await app.ai(
        system="You triage support tickets for urgency, routing, and escalation risk.",
        user=f"Tier: {account_tier}\nSubject: {subject}\n\n{body}",
        schema=TriageDecision,
    )
    if decision.escalate:
        await app.call("escalation.create_case",
            subject=subject, priority=decision.priority, reasoning=decision.reasoning)
    app.note(
        f"Triage decision priority={decision.priority} team={decision.team}",
        ["triage", decision.priority],
    )
    return decision.model_dump()
What just happened

AI produced a typed triage decision instead of free-form text
Your code handled the escalation side effect deterministically
The reasoner emitted an execution note for observability
AgentField attached execution IDs, workflow context, and an HTTP target automatically
Example target and result shape:


{
  "target": "support-triage.triage_ticket",
  "execution_id": "exec_a1b2c3",
  "result": {
    "priority": "critical",
    "team": "support-engineering",
    "escalate": true,
    "reasoning": "Enterprise customer reporting data loss"
  }
}
What You Get
Automatic REST endpoints generated from function signatures and type hints
Workflow tracking with execution IDs, parent-child relationships, and DAG building
Schema generation from type annotations (Python) or explicit schemas (TypeScript, Go)
Execution context with run ID, session, memory access, and cross-agent call propagation
Verifiable credentials for every execution when DID is enabled
Pydantic model conversion (Python) for automatic input validation
Patterns
Execution context injection (Python)
When your reasoner function declares an execution_context parameter, the SDK automatically injects it:

Python
TypeScript
Go

from agentfield.execution_context import ExecutionContext
@app.reasoner()
async def traced_operation(data: str, execution_context: ExecutionContext = None) -> dict:
    print(f"Run ID: {execution_context.run_id}")
    print(f"Execution ID: {execution_context.execution_id}")
    print(f"Depth: {execution_context.depth}")
    # Child context propagates to downstream calls
    return {"data": data, "run_id": execution_context.run_id}
Pydantic input validation (Python)
Reasoners automatically convert incoming JSON to Pydantic models when type hints are used:

Python

from pydantic import BaseModel, Field
class AnalysisRequest(BaseModel):
    text: str = Field(..., min_length=1)
    language: str = Field(default="en", pattern="^[a-z]{2}$")
    max_tokens: int = Field(default=500, ge=1, le=4096)
@app.reasoner(tags=["analysis"])
async def analyze(request: AnalysisRequest) -> dict:
    # request is already validated -- invalid input returns 422
    result = await app.ai(
        system=f"Analyze in {request.language}.",
        user=request.text,
    )
    return result
CLI-accessible reasoners (Go)
The Go SDK supports running reasoners directly from the command line:

Go

a.RegisterReasoner("greet", func(ctx context.Context, input map[string]any) (any, error) {
    name, _ := input["name"].(string)
    return map[string]any{"message": fmt.Sprintf("Hello, %s!", name)}, nil
},
    agent.WithCLI(),
    agent.WithDefaultCLI(),
    agent.WithDescription("Greet a user by name"),
)
// Run with: go run main.go greet --name Alice
// Or start server: go run main.go serve
a.Run(context.Background())
Registration Options
Python @app.reasoner() decorator
Parameter	Type	Default	Description
path	str | None	"/reasoners/{fn_name}"	Custom API endpoint path
name	str | None	function name	Explicit registration ID
tags	list[str] | None	None	Organizational tags for discovery and policy
vc_enabled	bool | None	None	Override agent-level VC generation
require_realtime_validation	bool	False	Force control-plane verification
The standalone @reasoner decorator (from agentfield.decorators) adds track_workflow and description parameters and is used for module-level reasoners outside the agent decorator pattern.

TypeScript agent.reasoner() options
Parameter	Type	Default	Description
tags	string[]	undefined	Organizational tags
description	string	undefined	Human-readable description
inputSchema	any	undefined	JSON Schema for input validation
outputSchema	any	undefined	JSON Schema for output documentation
trackWorkflow	boolean	undefined	Enable workflow tracking
requireRealtimeValidation	boolean	undefined	Force control-plane verification
Go RegisterReasoner() options
Option	Description
WithDescription(desc)	Human-readable description for help and discovery
WithReasonerTags(tags...)	Tags for organization and tag-based authorization
WithInputSchema(json.RawMessage)	Override auto-generated input schema
WithOutputSchema(json.RawMessage)	Override default output schema
WithVCEnabled(bool)	Override agent-level VC generation
WithCLI()	Make this reasoner accessible from the CLI
WithDefaultCLI()	Set as the default CLI handler
WithCLIFormatter(func)	Custom output formatter for CLI mode
WithRequireRealtimeValidation()	Force control-plane verification
SDK Reference
Operation	Python	TypeScript	Go
Register	@app.reasoner()	agent.reasoner(name, handler, opts?)	a.RegisterReasoner(name, handler, opts...)
Handler signature	async def fn(arg: Type) -> Type	(ctx: ReasonerContext) => Promise<T>	func(ctx, input map[string]any) (any, error)
Access input	Function parameters	ctx.input	input map
Access AI	await app.ai(...)	await ctx.ai(...)	a.AI(ctx, ...)
Cross-agent call	await app.call(target, input)	await ctx.call(target, input)	a.Call(ctx, target, input)
Access memory	app.memory.set(key, val)	ctx.memory.set(key, val)	a.Memory().Set(ctx, key, val)
Get execution context	execution_context parameter	ctx.executionId, ctx.runId	agent.ExecutionContextFrom(ctx)