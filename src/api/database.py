"""
Database utilities for the FastAPI backend.
Provides async PostgreSQL connection management for threads and messages.
"""

import os
from contextlib import contextmanager
from typing import Optional

import psycopg
from dotenv import load_dotenv

load_dotenv()


def get_connection_string() -> str:
    """Get PostgreSQL connection string from environment."""
    conn_string = os.getenv("POSTGRES_URI")
    if not conn_string:
        raise ValueError("POSTGRES_URI environment variable is required")
    return conn_string


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = psycopg.connect(get_connection_string())
    try:
        yield conn
    finally:
        conn.close()


async def setup_tables() -> None:
    """Create necessary tables if they don't exist."""
    with get_db_connection() as conn:
        # Create threads table for tracking conversation threads
        conn.execute("""
            CREATE TABLE IF NOT EXISTS threads (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_threads_user 
            ON threads(user_id, updated_at DESC);
        """)
        
        # Create document_chunks table for storing processed PDF content
        conn.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id SERIAL PRIMARY KEY,
                thread_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                page_num INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                image_keys TEXT[],
                processing_status TEXT DEFAULT 'completed',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(thread_id, filename, page_num, chunk_index)
            );
            
            CREATE INDEX IF NOT EXISTS idx_doc_chunks_thread 
            ON document_chunks(thread_id);
            
            CREATE INDEX IF NOT EXISTS idx_doc_chunks_filename 
            ON document_chunks(thread_id, filename);
        """)
        conn.commit()


async def get_user_threads(user_id: str, limit: int = 50) -> list[dict]:
    """Get all threads for a user, ordered by most recent activity."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, user_id, title, created_at, updated_at
            FROM threads
            WHERE user_id = %s
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (user_id, limit)
        )
        rows = cursor.fetchall()
        
        return [
            {
                "id": row[0],
                "user_id": row[1],
                "title": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
                "updated_at": row[4].isoformat() if row[4] else None
            }
            for row in rows
        ]


async def create_thread(thread_id: str, user_id: str, title: Optional[str] = None) -> dict:
    """Create a new conversation thread."""
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO threads (id, user_id, title)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET updated_at = NOW()
            RETURNING id, user_id, title, created_at, updated_at
            """,
            (thread_id, user_id, title or "New Chat")
        )
        conn.commit()
        
        # Fetch the created/updated thread
        cursor = conn.execute(
            "SELECT id, user_id, title, created_at, updated_at FROM threads WHERE id = %s",
            (thread_id,)
        )
        row = cursor.fetchone()
        
        return {
            "id": row[0],
            "user_id": row[1],
            "title": row[2],
            "created_at": row[3].isoformat() if row[3] else None,
            "updated_at": row[4].isoformat() if row[4] else None
        }


async def update_thread_title(thread_id: str, title: str) -> bool:
    """Update thread title (usually from first message)."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE threads SET title = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (title, thread_id)
        )
        conn.commit()
        return cursor.rowcount > 0


async def delete_thread(thread_id: str) -> bool:
    """Delete a thread and its messages."""
    with get_db_connection() as conn:
        # Delete messages first
        conn.execute(
            "DELETE FROM message_history WHERE thread_id = %s",
            (thread_id,)
        )
        # Delete thread
        cursor = conn.execute(
            "DELETE FROM threads WHERE id = %s",
            (thread_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


async def get_thread_messages(thread_id: str, limit: int = 100) -> list[dict]:
    """Get messages for a specific thread, excluding internal system messages."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, thread_id, user_id, role, content, message_id, 
                   attachments, created_at
            FROM message_history
            WHERE thread_id = %s
              AND content NOT LIKE 'Gaming query: %%'
            ORDER BY created_at ASC
            LIMIT %s
            """,
            (thread_id, limit)
        )
        rows = cursor.fetchall()
        
        return [
            {
                "id": row[0],
                "thread_id": row[1],
                "user_id": row[2],
                "role": row[3],
                "content": row[4],
                "message_id": row[5],
                "attachments": row[6] if row[6] else [],
                "created_at": row[7].isoformat() if row[7] else None
            }
            for row in rows
        ]


async def touch_thread(thread_id: str) -> None:
    """Update thread's updated_at timestamp."""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE threads SET updated_at = NOW() WHERE id = %s",
            (thread_id,)
        )
        conn.commit()


async def truncate_thread_messages(thread_id: str, keep_count: int) -> int:
    """
    Keep only the first N messages in a thread, delete the rest.
    Used for time travel / message editing to clean up stale messages.
    
    Args:
        thread_id: The conversation thread identifier
        keep_count: Number of messages to keep (from the beginning)
        
    Returns:
        Number of messages deleted
    """
    with get_db_connection() as conn:
        # Get IDs of messages to keep (first N messages by created_at)
        # We need to exclude internal system messages from the count to match frontend behavior
        cursor = conn.execute(
            """
            WITH messages_to_keep AS (
                SELECT id FROM message_history
                WHERE thread_id = %s
                  AND content NOT LIKE 'Gaming query: %%'
                ORDER BY created_at ASC
                LIMIT %s
            )
            DELETE FROM message_history
            WHERE thread_id = %s
              AND id NOT IN (SELECT id FROM messages_to_keep)
            """,
            (thread_id, keep_count, thread_id)
        )
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count


# =============================================================================
# Document Chunks Functions
# =============================================================================

async def save_document_chunks(
    thread_id: str,
    user_id: str,
    filename: str,
    chunks: list[dict]
) -> int:
    """
    Save processed document chunks to the database.
    
    Args:
        thread_id: The conversation thread identifier
        user_id: The user identifier
        filename: Original filename of the document
        chunks: List of dicts with keys: page_num, chunk_index, content, image_keys
        
    Returns:
        Number of chunks saved
    """
    if not chunks:
        return 0
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Insert each chunk individually (psycopg3 executemany is on cursor)
        for chunk in chunks:
            # Get image_keys and ensure it's a list
            image_keys = chunk.get("image_keys", [])
            if image_keys is None:
                image_keys = []
            
            cursor.execute(
                """
                INSERT INTO document_chunks 
                    (thread_id, user_id, filename, page_num, chunk_index, content, image_keys)
                VALUES (%s, %s, %s, %s, %s, %s, %s::text[])
                ON CONFLICT (thread_id, filename, page_num, chunk_index) 
                DO UPDATE SET 
                    content = EXCLUDED.content,
                    image_keys = EXCLUDED.image_keys,
                    created_at = NOW()
                """,
                (
                    thread_id,
                    user_id,
                    filename,
                    chunk["page_num"],
                    chunk["chunk_index"],
                    chunk["content"],
                    image_keys,
                )
            )
        
        conn.commit()
        return len(chunks)


async def get_document_chunks(thread_id: str, filename: Optional[str] = None) -> list[dict]:
    """
    Get all document chunks for a thread, optionally filtered by filename.
    
    Args:
        thread_id: The conversation thread identifier
        filename: Optional filename to filter by
        
    Returns:
        List of chunk dicts with page_num, chunk_index, content, image_keys, filename
    """
    with get_db_connection() as conn:
        if filename:
            cursor = conn.execute(
                """
                SELECT filename, page_num, chunk_index, content, image_keys
                FROM document_chunks
                WHERE thread_id = %s AND filename = %s
                ORDER BY filename, page_num, chunk_index
                """,
                (thread_id, filename)
            )
        else:
            cursor = conn.execute(
                """
                SELECT filename, page_num, chunk_index, content, image_keys
                FROM document_chunks
                WHERE thread_id = %s
                ORDER BY filename, page_num, chunk_index
                """,
                (thread_id,)
            )
        
        rows = cursor.fetchall()
        
        return [
            {
                "filename": row[0],
                "page_num": row[1],
                "chunk_index": row[2],
                "content": row[3],
                "image_keys": row[4] if row[4] else [],
            }
            for row in rows
        ]


async def delete_document_chunks(thread_id: str, filename: Optional[str] = None) -> int:
    """
    Delete document chunks for a thread, optionally filtered by filename.
    
    Args:
        thread_id: The conversation thread identifier
        filename: Optional filename to filter by (deletes all if not provided)
        
    Returns:
        Number of chunks deleted
    """
    with get_db_connection() as conn:
        if filename:
            cursor = conn.execute(
                "DELETE FROM document_chunks WHERE thread_id = %s AND filename = %s",
                (thread_id, filename)
            )
        else:
            cursor = conn.execute(
                "DELETE FROM document_chunks WHERE thread_id = %s",
                (thread_id,)
            )
        
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count


async def get_processing_status(thread_id: str, filename: str) -> dict:
    """
    Check if a file has been processed and get its status.
    
    Args:
        thread_id: The conversation thread identifier
        filename: The filename to check
        
    Returns:
        Dict with processed (bool), chunk_count (int), and status info
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT COUNT(*), MIN(created_at), MAX(created_at)
            FROM document_chunks
            WHERE thread_id = %s AND filename = %s
            """,
            (thread_id, filename)
        )
        row = cursor.fetchone()
        
        chunk_count = row[0] if row else 0
        
        return {
            "processed": chunk_count > 0,
            "chunk_count": chunk_count,
            "first_processed_at": row[1].isoformat() if row and row[1] else None,
            "last_processed_at": row[2].isoformat() if row and row[2] else None,
        }
