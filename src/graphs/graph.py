from langgraph.graph import StateGraph, START, END

# Support both LangGraph Studio (relative imports) and FastAPI server (src-prefixed imports)
try:
    from state.state import MainGraphState
    from nodes.DomainIdentifierNode import DomainIdentifierAgent
    from nodes.ConvoNode import ConvoAgent
except ImportError:
    from src.state.state import MainGraphState
    from src.nodes.DomainIdentifierNode import DomainIdentifierAgent
    from src.nodes.ConvoNode import ConvoAgent


def route_after_domain_check(state: MainGraphState) -> str:
    """Route based on whether the query is gaming-related."""
    if state.get("Approval"):
        return "ConvoAgent"
    return END


# Build the graph structure
builder = StateGraph(MainGraphState)
builder.add_node("DomainIdentifierAgent", DomainIdentifierAgent)
builder.add_node("ConvoAgent", ConvoAgent)

builder.add_edge(START, "DomainIdentifierAgent")
builder.add_conditional_edges(
    "DomainIdentifierAgent",
    route_after_domain_check,
    ["ConvoAgent", END]
)
builder.add_edge("ConvoAgent", END)

# Export compiled graph - LangGraph Studio will inject its own checkpointer
Lumos_Super_Graph = builder.compile()
