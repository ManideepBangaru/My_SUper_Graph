"""
MessageLogger - Stores conversation messages in human-readable format in PostgreSQL.

This complements LangGraph's binary checkpointing by providing a queryable
message_history table that can be viewed directly in pgAdmin or any SQL client.
"""

import json
import os
from datetime import datetime
from typing import Optional

import psycopg
from dotenv import load_dotenv

load_dotenv()


class MessageLogger:
    """
    Logs messages to a human-readable PostgreSQL table.
    
    Usage:
        logger = MessageLogger()
        await logger.log_message(
            thread_id="1",
            role="human",
            content="Hello, how are you?",
            user_id="user_123",
            attachments=[{"filename": "doc.pdf", "size": 12345}]
        )
    """
    
    def __init__(self, conn_string: Optional[str] = None):
        self.conn_string = conn_string or os.getenv("POSTGRES_URI")
        if not self.conn_string:
            raise ValueError("POSTGRES_URI environment variable is required")
    
    async def setup(self) -> None:
        """Create the message_history table if it doesn't exist."""
        with psycopg.connect(self.conn_string) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS message_history (
                    id SERIAL PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    user_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    message_id TEXT,
                    attachments JSONB DEFAULT '[]',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                
                -- Index for fast lookups by thread
                CREATE INDEX IF NOT EXISTS idx_message_history_thread 
                ON message_history(thread_id, created_at);
                
                -- Index for user-specific queries
                CREATE INDEX IF NOT EXISTS idx_message_history_user 
                ON message_history(user_id, created_at);
            """)
            conn.commit()
    
    async def log_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        user_id: Optional[str] = None,
        message_id: Optional[str] = None,
        attachments: Optional[list[dict]] = None
    ) -> None:
        """
        Log a single message to the message_history table.
        
        Args:
            thread_id: The conversation thread identifier
            role: Message role ('human' or 'ai')
            content: The actual message text
            user_id: Optional user identifier
            message_id: Optional unique message ID from LangChain
            attachments: Optional list of file attachments [{filename, size, s3_key}]
        """
        attachments_json = json.dumps(attachments or [])
        
        with psycopg.connect(self.conn_string) as conn:
            conn.execute(
                """
                INSERT INTO message_history (thread_id, user_id, role, content, message_id, attachments)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (thread_id, user_id, role, content, message_id, attachments_json)
            )
            conn.commit()
    
    async def get_thread_messages(self, thread_id: str, limit: int = 100) -> list[dict]:
        """
        Retrieve messages for a specific thread.
        
        Args:
            thread_id: The conversation thread identifier
            limit: Maximum number of messages to return
            
        Returns:
            List of message dictionaries ordered by creation time
        """
        with psycopg.connect(self.conn_string) as conn:
            cursor = conn.execute(
                """
                SELECT id, thread_id, user_id, role, content, message_id, attachments, created_at
                FROM message_history
                WHERE thread_id = %s
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
    
    async def get_user_messages(self, user_id: str, limit: int = 100) -> list[dict]:
        """
        Retrieve all messages for a specific user across all threads.
        
        Args:
            user_id: The user identifier
            limit: Maximum number of messages to return
            
        Returns:
            List of message dictionaries ordered by creation time
        """
        with psycopg.connect(self.conn_string) as conn:
            cursor = conn.execute(
                """
                SELECT id, thread_id, user_id, role, content, message_id, attachments, created_at
                FROM message_history
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, limit)
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
