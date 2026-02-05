import os
import asyncio
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from utils.message_logger import MessageLogger
from state.state import MainGraphState
from nodes.DomainIdentifierNode import DomainIdentifierAgent
from nodes.ConvoNode import ConvoAgent

load_dotenv()


def route_after_domain_check(state: MainGraphState) -> str:
    """Route based on whether the query is gaming-related."""
    if state.get("Approval"):
        return "ConvoAgent"
    return END


async def main():
    async with AsyncPostgresSaver.from_conn_string(os.getenv("POSTGRES_URI")) as checkpointer:
        await checkpointer.setup()
        
        # Setup human-readable message history table
        message_logger = MessageLogger()
        await message_logger.setup()

        # Build the graph
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

        graph = builder.compile(checkpointer=checkpointer)

        config = {
            "configurable": {
                "thread_id": "1",
                "user_id": "1",
            }
        }
        
        async for chunk in graph.astream(
            {"messages": [{"role": "user", "content": "Hi! I want to know the story of God of War"}]},
            config,
            stream_mode=["updates","custom"],
        ):
            print(chunk)
        
        return graph


if __name__ == "__main__":
    asyncio.run(main())
