import os
from typing import Literal, Any, Dict

from deepagents import create_deep_agent
from tavily import TavilyClient  # pip install tavily-python
from langchain_core.messages import AIMessageChunk, ToolMessage
from dotenv import load_dotenv
load_dotenv()

tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
) -> Dict[str, Any]:
    """Simple web search tool for the agent."""
    return tavily.search(
        query,
        max_results=max_results,
        topic=topic,
        include_raw_content=include_raw_content,
    )

agent = create_deep_agent(
    model=os.getenv("GOOGLE_MODEL"),
    tools=[internet_search],
    system_prompt=(
        "You are an expert researcher. Use todos to plan. "
        "Use internet_search when needed. Provide a concise report."
    ),
)

inputs = {
    "messages": [
        {"role": "user", "content": "Compare LangGraph streaming modes and give a minimal example."}
    ]
}

# Stream BOTH "updates" (planning/state) and "messages" (tokens + tool calls/results)
for mode, chunk in agent.stream(inputs, stream_mode=["updates", "messages"]):
    if mode == "updates":
        # This is where you can see background state changing (e.g., todo list middleware updates).
        # Print it raw first; then you can filter keys you care about.
        print("\n[UPDATE]", chunk)

    elif mode == "messages":
        msg, meta = chunk  # (message_or_chunk, metadata)
        node = meta.get("langgraph_node", "unknown")

        # 1) Stream final answer tokens (and any other AI text tokens)
        if isinstance(msg, AIMessageChunk) and msg.content:
            print(msg.content, end="", flush=True)

        # 2) Stream tool results (ToolMessage)
        elif isinstance(msg, ToolMessage):
            print(f"\n\n[TOOL RESULT] node={node} tool={msg.name}\n{msg.content}\n")

        # 3) Detect tool-call chunks (provider-dependent; often present in AIMessageChunk metadata)
        # Many providers stream tool calls in partial chunks; best practice is to read meta + msg.additional_kwargs.
        tool_calls = getattr(msg, "tool_calls", None) or msg.additional_kwargs.get("tool_calls") if hasattr(msg, "additional_kwargs") else None
        if tool_calls:
            print(f"\n[TOOL CALLS] node={node} -> {tool_calls}\n")
