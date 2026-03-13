"""
Chat routes with SSE streaming support.
"""

import asyncio
import json
import os
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from pydantic import BaseModel

from src.api.database import create_thread, touch_thread, update_thread_title
from src.graphs.graph import builder
from src.utils.message_logger import MessageLogger

load_dotenv()

router = APIRouter(prefix="/api/chat", tags=["chat"])

message_logger = MessageLogger()


class ChatRequest(BaseModel):
    message: str
    thread_id: str
    user_id: str


class ForkRequest(BaseModel):
    message: str
    thread_id: str
    user_id: str
    checkpoint_id: str


async def stream_graph_response(
    message: str,
    thread_id: str,
    user_id: str,
) -> AsyncGenerator[bytes, None]:
    """Stream the graph response using SSE."""
    # Send a keepalive immediately so the client knows the stream is open
    # while the backend warms up (DB connect, graph compile, LLM cold start)
    yield f"data: {json.dumps({'type': 'progress', 'content': {'Progress': 'Connecting ...'}})}\n\n".encode()

    await message_logger.log_message(
        thread_id=thread_id,
        user_id=user_id,
        role="human",
        content=message,
    )

    postgres_uri = os.getenv("POSTGRES_URI")
    if not postgres_uri:
        yield f"data: {json.dumps({'type': 'error', 'content': 'Database not configured'})}\n\n".encode()
        return

    try:
        async with AsyncPostgresSaver.from_conn_string(postgres_uri) as checkpointer:
            await checkpointer.setup()

            graph = builder.compile(checkpointer=checkpointer)

            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": user_id,
                }
            }

            input_state = {"messages": [HumanMessage(content=message)]}

            sent_contents: set[str] = set()

            async for stream_mode, chunk in graph.astream(
                input_state,
                config,
                stream_mode=["updates", "custom"],
            ):
                if stream_mode == "custom":
                    yield f"data: {json.dumps({'type': 'progress', 'content': chunk})}\n\n".encode()
                    continue

                if stream_mode == "updates":
                    for node_name, node_output in chunk.items():
                        if not isinstance(node_output, dict):
                            continue
                        for msg in node_output.get("messages", []):
                            is_ai = isinstance(msg, AIMessage) or (
                                hasattr(msg, "type") and msg.type == "ai"
                            )
                            if is_ai:
                                content = msg.content if hasattr(msg, "content") else str(msg)
                                if content and content not in sent_contents:
                                    sent_contents.add(content)
                                    words = content.split(" ")
                                    for i, word in enumerate(words):
                                        token = word if i == len(words) - 1 else word + " "
                                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n".encode()
                                        await asyncio.sleep(0.02)

            await touch_thread(thread_id)
            yield f"data: {json.dumps({'type': 'done'})}\n\n".encode()

    except Exception as e:
        import traceback
        print(f"Chat error: {str(e)}\n{traceback.format_exc()}")
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n".encode()


@router.post("")
async def chat(request: ChatRequest):
    """Send a message and receive a streaming response via SSE."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    await create_thread(request.thread_id, request.user_id)

    title = request.message[:50] + "..." if len(request.message) > 50 else request.message
    await update_thread_title(request.thread_id, title)

    return StreamingResponse(
        stream_graph_response(
            message=request.message,
            thread_id=request.thread_id,
            user_id=request.user_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def stream_fork_response(
    message: str,
    thread_id: str,
    user_id: str,
    checkpoint_id: str,
) -> AsyncGenerator[bytes, None]:
    """Fork from a specific checkpoint and stream the response."""
    yield f"data: {json.dumps({'type': 'progress', 'content': {'Progress': 'Connecting ...'}})}\n\n".encode()

    await message_logger.log_message(
        thread_id=thread_id,
        user_id=user_id,
        role="human",
        content=message,
    )

    postgres_uri = os.getenv("POSTGRES_URI")
    if not postgres_uri:
        yield f"data: {json.dumps({'type': 'error', 'content': 'Database not configured'})}\n\n".encode()
        return

    try:
        async with AsyncPostgresSaver.from_conn_string(postgres_uri) as checkpointer:
            await checkpointer.setup()

            graph = builder.compile(checkpointer=checkpointer)

            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "checkpoint_id": checkpoint_id,
                }
            }

            input_state = {"messages": [HumanMessage(content=message)]}

            sent_contents: set[str] = set()

            async for stream_mode, chunk in graph.astream(
                input_state,
                config,
                stream_mode=["updates", "custom"],
            ):
                if stream_mode == "custom":
                    yield f"data: {json.dumps({'type': 'progress', 'content': chunk})}\n\n".encode()
                    continue

                if stream_mode == "updates":
                    for node_name, node_output in chunk.items():
                        if not isinstance(node_output, dict):
                            continue
                        for msg in node_output.get("messages", []):
                            is_ai = isinstance(msg, AIMessage) or (
                                hasattr(msg, "type") and msg.type == "ai"
                            )
                            if is_ai:
                                content = msg.content if hasattr(msg, "content") else str(msg)
                                if content and content not in sent_contents:
                                    sent_contents.add(content)
                                    words = content.split(" ")
                                    for i, word in enumerate(words):
                                        token = word if i == len(words) - 1 else word + " "
                                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n".encode()
                                        await asyncio.sleep(0.02)

            await touch_thread(thread_id)
            yield f"data: {json.dumps({'type': 'done'})}\n\n".encode()

    except Exception as e:
        import traceback
        print(f"Fork error: {str(e)}\n{traceback.format_exc()}")
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n".encode()


@router.post("/fork")
async def fork_from_checkpoint(request: ForkRequest):
    """Fork from a specific checkpoint (time travel) and send a new message."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if not request.checkpoint_id:
        raise HTTPException(status_code=400, detail="Checkpoint ID is required")

    return StreamingResponse(
        stream_fork_response(
            message=request.message,
            thread_id=request.thread_id,
            user_id=request.user_id,
            checkpoint_id=request.checkpoint_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
