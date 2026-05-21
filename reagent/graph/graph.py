"""Graph builder for the contract development workflow.

Constructs a LangGraph StateGraph from the stage nodes and conditional edges,
then compiles it with checkpointing support.

Phase 4: Unified graph with mode-based entry routing.
- mode="plan" → plan_node → END
- mode="code" → code_node → END
- mode="orchestrate" → full pipeline (ideation → coding → testing → ...)
"""

from langgraph.graph import StateGraph, END

from .state import ContractDevState
from .nodes.ideation_node import ideation_node
from .nodes.coding_node import coding_node
from .nodes.testing_node import testing_node
from .nodes.auditing_node import auditing_node
from .nodes.deployment_node import deployment_node
from .nodes.monitoring_node import monitoring_node
from .nodes.plan_node import plan_node
from .nodes.code_node import code_node
from .edges import (
    route_after_testing,
    route_after_auditing,
    route_after_deployment,
)


def _build_orchestrate_subgraph(graph: StateGraph) -> None:
    """Add the full orchestration pipeline nodes and edges."""
    graph.add_node("ideation", ideation_node)
    graph.add_node("coding", coding_node)
    graph.add_node("testing", testing_node)
    graph.add_node("auditing", auditing_node)
    graph.add_node("deployment", deployment_node)
    graph.add_node("monitoring", monitoring_node)

    graph.set_entry_point("ideation")
    graph.add_edge("ideation", "coding")
    graph.add_edge("coding", "testing")

    graph.add_conditional_edges(
        "testing",
        route_after_testing,
        {"auditing": "auditing", "coding": "coding", END: END},
    )

    graph.add_conditional_edges(
        "auditing",
        route_after_auditing,
        {"deployment": "deployment", "coding": "coding", END: END},
    )

    graph.add_conditional_edges(
        "deployment",
        route_after_deployment,
        {"monitoring": "monitoring", "coding": "coding", END: END},
    )

    graph.add_edge("monitoring", END)


def _build_plan_subgraph(graph: StateGraph) -> None:
    """Add the plan-only subgraph."""
    graph.add_node("plan", plan_node)
    graph.set_entry_point("plan")
    graph.add_edge("plan", END)


def _build_code_subgraph(graph: StateGraph) -> None:
    """Add the direct code generation subgraph."""
    graph.add_node("code", code_node)
    graph.set_entry_point("code")
    graph.add_edge("code", END)


def build_workflow_graph(mode: str = "orchestrate") -> StateGraph:
    """
    Build the contract development workflow graph for a given mode.

    Args:
        mode: "plan" (analysis only), "code" (direct generation),
              or "orchestrate" (full pipeline with feedback loops)

    Returns:
        StateGraph configured for the specified mode.
    """
    graph = StateGraph(ContractDevState)

    if mode == "plan":
        _build_plan_subgraph(graph)
    elif mode == "code":
        _build_code_subgraph(graph)
    else:
        _build_orchestrate_subgraph(graph)

    return graph


def create_compiled_graph(
    mode: str = "orchestrate",
    checkpointer=None,
    interrupt_after=None,
):
    """
    Create a compiled workflow graph with optional checkpointing.

    Args:
        mode: "plan", "code", or "orchestrate"
        checkpointer: LangGraph checkpointer (MemorySaver, SqliteSaver, etc.)
        interrupt_after: List of node names to interrupt after for human review

    Returns:
        Compiled LangGraph ready for invocation.
    """
    graph = build_workflow_graph(mode=mode)

    compile_kwargs = {}
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer
    if interrupt_after:
        compile_kwargs["interrupt_after"] = interrupt_after

    return graph.compile(**compile_kwargs)


def create_default_graph(mode: str = "orchestrate"):
    """
    Create a compiled graph with in-memory checkpointing (development mode).
    """
    from langgraph.checkpoint.memory import MemorySaver
    return create_compiled_graph(
        mode=mode,
        checkpointer=MemorySaver(),
        interrupt_after=["coding", "auditing"] if mode == "orchestrate" else None,
    )


def create_persistent_graph(
    mode: str = "orchestrate",
    db_path: str = ".langgraph.db",
):
    """
    Create a compiled graph with in-memory checkpointing.

    Note: SQLite persistence requires async context manager lifecycle
    (open/close) which is managed at the workflow execution level.
    For true persistence, use `create_compiled_graph` with an
    externally-managed `AsyncSqliteSaver`.

    Args:
        mode: "plan", "code", or "orchestrate"
        db_path: Reserved for future async SQLite integration

    Returns:
        Compiled LangGraph with in-memory checkpointing and human review gates.
    """
    from langgraph.checkpoint.memory import InMemorySaver

    return create_compiled_graph(
        mode=mode,
        checkpointer=InMemorySaver(),
        interrupt_after=["coding", "auditing"] if mode == "orchestrate" else None,
    )
