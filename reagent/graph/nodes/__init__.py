"""Graph nodes for the contract development workflow.

Each node wraps an existing stage function from the orchestrator or stage routers.
Nodes return partial state updates that LangGraph merges into the running state.
"""
