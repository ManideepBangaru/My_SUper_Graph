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
            (user_id, limit),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "user_id": row[1],
                "title": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
                "updated_at": row[4].isoformat() if row[4] else None,
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
            (thread_id, user_id, title or "New Chat"),
        )
        conn.commit()

        cursor = conn.execute(
            "SELECT id, user_id, title, created_at, updated_at FROM threads WHERE id = %s",
            (thread_id,),
        )
        row = cursor.fetchone()
        return {
            "id": row[0],
            "user_id": row[1],
            "title": row[2],
            "created_at": row[3].isoformat() if row[3] else None,
            "updated_at": row[4].isoformat() if row[4] else None,
        }


async def update_thread_title(thread_id: str, title: str) -> bool:
    """Update thread title (usually from first message)."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "UPDATE threads SET title = %s, updated_at = NOW() WHERE id = %s",
            (title, thread_id),
        )
        conn.commit()
        return cursor.rowcount > 0


async def delete_thread(thread_id: str) -> bool:
    """Delete a thread and its messages."""
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM message_history WHERE thread_id = %s",
            (thread_id,),
        )
        cursor = conn.execute(
            "DELETE FROM threads WHERE id = %s",
            (thread_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


async def get_thread_messages(thread_id: str, limit: int = 100) -> list[dict]:
    """Get messages for a specific thread."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, thread_id, user_id, role, content, message_id, created_at
            FROM message_history
            WHERE thread_id = %s
            ORDER BY created_at ASC
            LIMIT %s
            """,
            (thread_id, limit),
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
                "attachments": [],
                "created_at": row[6].isoformat() if row[6] else None,
            }
            for row in rows
        ]


async def touch_thread(thread_id: str) -> None:
    """Update thread's updated_at timestamp."""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE threads SET updated_at = NOW() WHERE id = %s",
            (thread_id,),
        )
        conn.commit()


async def truncate_thread_messages(thread_id: str, keep_count: int) -> int:
    """Keep only the first N messages in a thread, delete the rest."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            WITH messages_to_keep AS (
                SELECT id FROM message_history
                WHERE thread_id = %s
                ORDER BY created_at ASC
                LIMIT %s
            )
            DELETE FROM message_history
            WHERE thread_id = %s
              AND id NOT IN (SELECT id FROM messages_to_keep)
            """,
            (thread_id, keep_count, thread_id),
        )
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count
