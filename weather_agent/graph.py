"""LangGraph wiring: plan -> (fetch -> render) | stop."""

from __future__ import annotations

from .pipeline import AgentState, Pipeline, route_after_plan


def build_graph(pipeline: Pipeline):
    """Compile the agent as a LangGraph state machine.

    plan ──► fetch ──► render ──► END
      └────► END   (off-topic question, or no city given)
    """
    from langgraph.graph import END, StateGraph  # imported lazily so the core stays dependency-light

    graph = StateGraph(AgentState)
    graph.add_node("plan", pipeline.plan)
    graph.add_node("fetch", pipeline.fetch)
    graph.add_node("render", pipeline.render)

    graph.set_entry_point("plan")
    graph.add_conditional_edges("plan", route_after_plan, {"fetch": "fetch", "stop": END})
    graph.add_edge("fetch", "render")
    graph.add_edge("render", END)
    return graph.compile()
