from typing import TypedDict, List, Annotated, Optional

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages


def add_to_conversation(existing: List[str], new: List[str]) -> List[str]:
    """Reducer to accumulate conversation history strings."""
    return (existing or []) + (new or [])


class MainGraphState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    conversation_history: Annotated[List[str], add_to_conversation]
    domain: Optional[str]  # "games", "movies", or "none"
