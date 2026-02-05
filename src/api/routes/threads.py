"""
Thread management routes for conversation history.
"""

import os
from typing import Optional, List, Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.api.database import (
    get_user_threads,
    create_thread,
    delete_thread,
    get_thread_messages,
    update_thread_title,
    truncate_thread_messages,
)
from src.graphs.graph import builder

load_dotenv()

router = APIRouter(prefix="/api/threads", tags=["threads"])


class CreateThreadRequest(BaseModel):
    user_id: str
    title: Optional[str] = None


class UpdateThreadRequest(BaseModel):
    title: str


class ThreadResponse(BaseModel):
    id: str
    user_id: str
    title: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class MessageAttachment(BaseModel):
    """File attachment metadata."""
    filename: str
    size: int
    s3_key: Optional[str] = None
    content_type: Optional[str] = None


class MessageResponse(BaseModel):
    id: int
    thread_id: str
    user_id: Optional[str]
    role: str
    content: str
    message_id: Optional[str]
    attachments: list[MessageAttachment] = []
    created_at: Optional[str]


class CheckpointMessage(BaseModel):
    """Simplified message representation for checkpoint history."""
    role: str
    content: str


class TruncateMessagesRequest(BaseModel):
    """Request to truncate messages for time travel / editing."""
    keep_count: int


class CheckpointResponse(BaseModel):
    """Response model for a single checkpoint in history."""
    checkpoint_id: str
    thread_id: str
    checkpoint_ns: str
    parent_checkpoint_id: Optional[str]
    created_at: Optional[str]
    step: int
    messages: List[CheckpointMessage]


@router.get("", response_model=list[ThreadResponse])
async def list_threads(
    user_id: str = Query(..., description="User ID to fetch threads for"),
    limit: int = Query(50, ge=1, le=100)
):
    """List all conversation threads for a user."""
    threads = await get_user_threads(user_id, limit)
    return threads


@router.post("", response_model=ThreadResponse)
async def create_new_thread(request: CreateThreadRequest):
    """Create a new conversation thread."""
    thread_id = str(uuid4())
    thread = await create_thread(thread_id, request.user_id, request.title)
    return thread


@router.get("/{thread_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    thread_id: str,
    limit: int = Query(100, ge=1, le=500)
):
    """Get all messages for a specific thread."""
    messages = await get_thread_messages(thread_id, limit)
    return messages


@router.patch("/{thread_id}")
async def update_thread(thread_id: str, request: UpdateThreadRequest):
    """Update thread title."""
    success = await update_thread_title(thread_id, request.title)
    if not success:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"status": "updated"}


@router.delete("/{thread_id}")
async def remove_thread(thread_id: str):
    """Delete a thread and all its messages."""
    success = await delete_thread(thread_id)
    if not success:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"status": "deleted"}


@router.post("/{thread_id}/truncate")
async def truncate_messages(thread_id: str, request: TruncateMessagesRequest):
    """
    Truncate messages in a thread, keeping only the first N messages.
    Used for time travel / message editing to clean up stale messages.
    """
    if request.keep_count < 0:
        raise HTTPException(status_code=400, detail="keep_count must be non-negative")
    
    deleted_count = await truncate_thread_messages(thread_id, request.keep_count)
    return {"status": "truncated", "deleted_count": deleted_count}


@router.get("/{thread_id}/history", response_model=List[CheckpointResponse])
async def get_thread_history(
    thread_id: str,
    limit: int = Query(50, ge=1, le=100, description="Maximum number of checkpoints to return")
):
    """
    Get the checkpoint history for a thread (time travel).
    Returns a list of checkpoints with their states, ordered from newest to oldest.
    """
    postgres_uri = os.getenv("POSTGRES_URI")
    if not postgres_uri:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        async with AsyncPostgresSaver.from_conn_string(postgres_uri) as checkpointer:
            await checkpointer.setup()
            
            graph = builder.compile(checkpointer=checkpointer)
            
            config = {"configurable": {"thread_id": thread_id}}
            
            checkpoints = []
            step = 0
            
            # Iterate through state history
            async for state_snapshot in graph.aget_state_history(config):
                if step >= limit:
                    break
                
                # Extract messages from state
                messages = []
                state_values = state_snapshot.values
                if state_values and "messages" in state_values:
                    for msg in state_values["messages"]:
                        role = getattr(msg, "type", "unknown")
                        content = getattr(msg, "content", str(msg))
                        messages.append(CheckpointMessage(role=role, content=content))
                
                # Build checkpoint response
                checkpoint_config = state_snapshot.config.get("configurable", {})
                parent_config = state_snapshot.parent_config
                parent_checkpoint_id = None
                if parent_config:
                    parent_checkpoint_id = parent_config.get("configurable", {}).get("checkpoint_id")
                
                checkpoint = CheckpointResponse(
                    checkpoint_id=checkpoint_config.get("checkpoint_id", ""),
                    thread_id=checkpoint_config.get("thread_id", thread_id),
                    checkpoint_ns=checkpoint_config.get("checkpoint_ns", ""),
                    parent_checkpoint_id=parent_checkpoint_id,
                    created_at=state_snapshot.metadata.get("created_at") if state_snapshot.metadata else None,
                    step=step,
                    messages=messages
                )
                checkpoints.append(checkpoint)
                step += 1
            
            return checkpoints
            
    except Exception as e:
        import traceback
        print(f"History error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")
