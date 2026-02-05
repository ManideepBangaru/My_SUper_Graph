from typing import TypedDict, List, Annotated, Optional

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages


def add_to_conversation(existing: List[str], new: List[str]) -> List[str]:
    """Reducer to accumulate conversation history strings."""
    return (existing or []) + (new or [])


# State schema for the graph (input + accumulated state)
class MainGraphState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    conversation_history: Annotated[List[str], add_to_conversation]
    document_context: Optional[List[dict]]  # Processed PDF chunks for context
    cached_images: Optional[dict]  # Cached base64 images keyed by "filename:page_num"
    Approval: Optional[bool]
