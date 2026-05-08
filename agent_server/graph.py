"""LangGraph StateGraph definition for the campaign pipeline."""

from langgraph.graph import END, StateGraph

from agent_server.graph_nodes import (
    enrich_context,
    enrich_genie_node,
    generate_email,
    handle_error,
    process_input,
    query_genie_node,
    rank_and_select,
    retrieve_candidates,
)
from agent_server.graph_state import CampaignState


def _has_error(state: CampaignState) -> str:
    """Conditional edge: route to handle_error if an error exists."""
    return "handle_error" if state.get("error") else "ok"


def _route_source(state: CampaignState) -> str:
    """Route entry point based on source field."""
    source = state.get("source", "dashboard")
    if source == "genie":
        return "query_genie"
    return "process_input"


async def route_entry(state: CampaignState) -> dict:
    """No-op pass-through node used as the graph entry point for routing."""
    return {}


# ── Build the graph ──────────────────────────────────────────────────────────

builder = StateGraph(CampaignState)

# Add nodes
builder.add_node("route_entry", route_entry)
builder.add_node("query_genie", query_genie_node)
builder.add_node("enrich_genie", enrich_genie_node)
builder.add_node("process_input", process_input)
builder.add_node("retrieve_candidates", retrieve_candidates)
builder.add_node("rank_and_select", rank_and_select)
builder.add_node("enrich_context", enrich_context)
builder.add_node("generate_email", generate_email)
builder.add_node("handle_error", handle_error)

# Set entry point
builder.set_entry_point("route_entry")

# Route from entry point based on source
builder.add_conditional_edges("route_entry", _route_source, {
    "query_genie": "query_genie",
    "process_input": "process_input",
})

# Genie branch
builder.add_conditional_edges("query_genie", _has_error, {
    "ok": "enrich_genie",
    "handle_error": "handle_error",
})
builder.add_edge("enrich_genie", END)

# Existing dashboard/chat branch (unchanged logic)
builder.add_conditional_edges("process_input", _has_error, {
    "ok": "retrieve_candidates",
    "handle_error": "handle_error",
})
builder.add_edge("retrieve_candidates", "rank_and_select")
builder.add_conditional_edges("rank_and_select", _has_error, {
    "ok": "enrich_context",
    "handle_error": "handle_error",
})
builder.add_edge("enrich_context", "generate_email")
builder.add_edge("generate_email", END)
builder.add_edge("handle_error", END)

# Compile
campaign_graph = builder.compile()
