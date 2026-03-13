from langgraph.graph import StateGraph, START, END

# Support both LangGraph Studio (relative imports) and FastAPI server (src-prefixed imports)
try:
    from state.state import MainGraphState
    from nodes.GateNode import GateAgent
    from nodes.GamesNode import GamesAgent
    from nodes.MoviesNode import MoviesAgent
except ImportError:
    from src.state.state import MainGraphState
    from src.nodes.GateNode import GateAgent
    from src.nodes.GamesNode import GamesAgent
    from src.nodes.MoviesNode import MoviesAgent


def route_after_gate(state: MainGraphState) -> str:
    """Route to the appropriate domain agent, or END if out-of-domain."""
    domain = state.get("domain")
    if domain == "games":
        return "GamesAgent"
    if domain == "movies":
        return "MoviesAgent"
    return END


# Build the graph
builder = StateGraph(MainGraphState)
builder.add_node("GateAgent", GateAgent)
builder.add_node("GamesAgent", GamesAgent)
builder.add_node("MoviesAgent", MoviesAgent)

builder.add_edge(START, "GateAgent")
builder.add_conditional_edges(
    "GateAgent",
    route_after_gate,
    ["GamesAgent", "MoviesAgent", END],
)
builder.add_edge("GamesAgent", END)
builder.add_edge("MoviesAgent", END)

# Export compiled graph — LangGraph Studio injects its own checkpointer
Lumos_Super_Graph = builder.compile()
