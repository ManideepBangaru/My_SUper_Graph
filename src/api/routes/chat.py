"""
Chat routes with SSE streaming support.
"""

import asyncio
import json
import os
from typing import AsyncGenerator, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from pydantic import BaseModel

from src.api.database import create_thread, get_document_chunks, touch_thread, update_thread_title
from src.graphs.graph import builder
from src.utils.message_logger import MessageLogger

load_dotenv()

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Message logger for storing attachments with user messages
message_logger = MessageLogger()


class Attachment(BaseModel):
    """File attachment metadata."""
    filename: str
    size: int
    s3_key: Optional[str] = None
    content_type: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    thread_id: str
    user_id: str
    attachments: list[Attachment] = []


class ForkRequest(BaseModel):
    """Request to fork from a specific checkpoint and continue with a new message."""
    message: str
    thread_id: str
    user_id: str
    checkpoint_id: str  # The checkpoint to fork from
    attachments: list[Attachment] = []  # Attachments to include with the forked message


async def stream_graph_response(
    message: str,
    thread_id: str,
    user_id: str,
    attachments: list[dict] = None
) -> AsyncGenerator[bytes, None]:
    """
    Stream the graph response using SSE.
    Uses astream with updates mode to capture node outputs reliably.
    Preserves cached_images from previous state to avoid re-fetching from S3.
    """
    # Log the user message with attachments BEFORE invoking the graph
    # This ensures attachments are stored and we don't duplicate in ConvoNode
    await message_logger.log_message(
        thread_id=thread_id,
        user_id=user_id,
        role="human",
        content=message,
        attachments=attachments or []
    )
    
    # Get PostgreSQL connection string for checkpointer
    postgres_uri = os.getenv("POSTGRES_URI")
    if not postgres_uri:
        yield f"data: {json.dumps({'type': 'error', 'content': 'Database not configured'})}\n\n".encode()
        return
    
    try:
        # Compile graph with async PostgreSQL checkpointer
        async with AsyncPostgresSaver.from_conn_string(postgres_uri) as checkpointer:
            await checkpointer.setup()
            
            graph = builder.compile(checkpointer=checkpointer)
            
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": user_id,
                }
            }
            
            # Fetch document context for this thread
            doc_chunks = await get_document_chunks(thread_id)
            
            # Get current state to retrieve cached images (if any exist from previous invocations)
            current_state = await graph.aget_state(config)
            cached_images = None
            if current_state and current_state.values:
                cached_images = current_state.values.get("cached_images")
                if cached_images:
                    print(f"[chat.py] Found cached images for thread {thread_id}, will reuse")
            
            # Create input with user message, document context, and cached images
            input_state = {
                "messages": [HumanMessage(content=message)],
                "document_context": doc_chunks if doc_chunks else None,
                "cached_images": cached_images,  # Pass through cached images
            }
            
            # Track sent message contents to avoid duplicates
            sent_contents = set()
            
            # Stream with BOTH "updates" and "custom" modes to capture custom stream writer events
            async for stream_mode, chunk in graph.astream(
                input_state, 
                config, 
                stream_mode=["updates", "custom"]
            ):
                # Handle custom stream writer events (Progress messages from nodes)
                if stream_mode == "custom":
                    # chunk is the dict passed to writer(), e.g. {"Progress": "..."}
                    event_data = json.dumps({'type': 'progress', 'content': chunk})
                    yield f"data: {event_data}\n\n".encode()
                    continue
                
                # Handle node updates (existing logic)
                if stream_mode == "updates":
                    # chunk is a dict: {node_name: node_output}
                    for node_name, node_output in chunk.items():
                        if not isinstance(node_output, dict):
                            continue
                        
                        # Check for messages in the node output
                        messages = node_output.get("messages", [])
                        for msg in messages:
                            # Check if it's an AI message
                            is_ai = (
                                isinstance(msg, AIMessage) or 
                                (hasattr(msg, "type") and msg.type == "ai")
                            )
                            if is_ai:
                                content = msg.content if hasattr(msg, "content") else str(msg)
                                
                                # Only send if we haven't sent this exact content
                                if content and content not in sent_contents:
                                    sent_contents.add(content)
                                    # Simulate streaming by sending in chunks with small delay
                                    words = content.split(" ")
                                    for i, word in enumerate(words):
                                        token = word if i == len(words) - 1 else word + " "
                                        event_data = json.dumps({'type': 'token', 'content': token})
                                        yield f"data: {event_data}\n\n".encode()
                                        # Small delay for visual streaming effect
                                        await asyncio.sleep(0.02)
            
            # Update thread timestamp
            await touch_thread(thread_id)
            
            # Signal completion
            yield f"data: {json.dumps({'type': 'done'})}\n\n".encode()
            
    except Exception as e:
        import traceback
        print(f"Chat error: {str(e)}\n{traceback.format_exc()}")
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n".encode()


@router.post("")
async def chat(request: ChatRequest):
    """
    Send a message and receive a streaming response via SSE.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    # Ensure thread exists
    await create_thread(request.thread_id, request.user_id)
    
    # Update thread title with first message (truncated)
    title = request.message[:50] + "..." if len(request.message) > 50 else request.message
    await update_thread_title(request.thread_id, title)
    
    # Convert attachments to dict format for logging
    attachments_data = [att.model_dump() for att in request.attachments] if request.attachments else None
    
    return StreamingResponse(
        stream_graph_response(
            message=request.message,
            thread_id=request.thread_id,
            user_id=request.user_id,
            attachments=attachments_data
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


async def stream_fork_response(
    message: str,
    thread_id: str,
    user_id: str,
    checkpoint_id: str,
    attachments: list[dict] = None
) -> AsyncGenerator[bytes, None]:
    """
    Fork from a specific checkpoint and stream the response.
    This implements time travel by continuing from a past state.
    Preserves cached_images from the checkpoint state.
    """
    # Log the user message with attachments BEFORE invoking the graph
    await message_logger.log_message(
        thread_id=thread_id,
        user_id=user_id,
        role="human",
        content=message,
        attachments=attachments or []
    )
    
    postgres_uri = os.getenv("POSTGRES_URI")
    if not postgres_uri:
        yield f"data: {json.dumps({'type': 'error', 'content': 'Database not configured'})}\n\n".encode()
        return
    
    try:
        async with AsyncPostgresSaver.from_conn_string(postgres_uri) as checkpointer:
            await checkpointer.setup()
            
            graph = builder.compile(checkpointer=checkpointer)
            
            # Config with specific checkpoint_id to fork from
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "checkpoint_id": checkpoint_id,  # This tells LangGraph to start from this checkpoint
                }
            }
            
            # Fetch document context for this thread
            doc_chunks = await get_document_chunks(thread_id)
            
            # Get state from the checkpoint to retrieve cached images
            checkpoint_state = await graph.aget_state(config)
            cached_images = None
            if checkpoint_state and checkpoint_state.values:
                cached_images = checkpoint_state.values.get("cached_images")
                if cached_images:
                    print(f"[chat.py] Found cached images in checkpoint {checkpoint_id}, will reuse")
            
            # Create input with user message, document context, and cached images
            input_state = {
                "messages": [HumanMessage(content=message)],
                "document_context": doc_chunks if doc_chunks else None,
                "cached_images": cached_images,  # Pass through cached images from checkpoint
            }
            
            # Track sent message contents to avoid duplicates
            sent_contents = set()
            
            # Stream with BOTH "updates" and "custom" modes
            async for stream_mode, chunk in graph.astream(
                input_state, 
                config, 
                stream_mode=["updates", "custom"]
            ):
                # Handle custom stream writer events (Progress messages from nodes)
                if stream_mode == "custom":
                    event_data = json.dumps({'type': 'progress', 'content': chunk})
                    yield f"data: {event_data}\n\n".encode()
                    continue
                
                # Handle node updates
                if stream_mode == "updates":
                    for node_name, node_output in chunk.items():
                        if not isinstance(node_output, dict):
                            continue
                        
                        messages = node_output.get("messages", [])
                        for msg in messages:
                            is_ai = (
                                isinstance(msg, AIMessage) or 
                                (hasattr(msg, "type") and msg.type == "ai")
                            )
                            if is_ai:
                                content = msg.content if hasattr(msg, "content") else str(msg)
                                
                                if content and content not in sent_contents:
                                    sent_contents.add(content)
                                    words = content.split(" ")
                                    for i, word in enumerate(words):
                                        token = word if i == len(words) - 1 else word + " "
                                        event_data = json.dumps({'type': 'token', 'content': token})
                                        yield f"data: {event_data}\n\n".encode()
                                        await asyncio.sleep(0.02)
            
            await touch_thread(thread_id)
            yield f"data: {json.dumps({'type': 'done'})}\n\n".encode()
            
    except Exception as e:
        import traceback
        print(f"Fork error: {str(e)}\n{traceback.format_exc()}")
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n".encode()


@router.post("/fork")
async def fork_from_checkpoint(request: ForkRequest):
    """
    Fork from a specific checkpoint (time travel) and send a new message.
    This allows users to go back to a previous state and explore an alternate path.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    if not request.checkpoint_id:
        raise HTTPException(status_code=400, detail="Checkpoint ID is required")
    
    # Convert attachments to dict format for logging
    attachments_data = [att.model_dump() for att in request.attachments] if request.attachments else None
    
    return StreamingResponse(
        stream_fork_response(
            message=request.message,
            thread_id=request.thread_id,
            user_id=request.user_id,
            checkpoint_id=request.checkpoint_id,
            attachments=attachments_data
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
