/**
 * API client for communicating with the Super Chat backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Thread {
  id: string;
  user_id: string;
  title: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface Message {
  id: number;
  thread_id: string;
  user_id: string | null;
  role: "human" | "ai";
  content: string;
  message_id: string | null;
  created_at: string | null;
}

export interface ChatEvent {
  type: "token" | "message" | "done" | "error" | "progress";
  content?: string | Record<string, unknown>;
}

export interface CheckpointMessage {
  role: string;
  content: string;
}

export interface Checkpoint {
  checkpoint_id: string;
  thread_id: string;
  checkpoint_ns: string;
  parent_checkpoint_id: string | null;
  created_at: string | null;
  step: number;
  messages: CheckpointMessage[];
}

/**
 * Fetch all threads for a user.
 */
export async function fetchThreads(userId: string): Promise<Thread[]> {
  try {
    const response = await fetch(
      `${API_BASE}/api/threads?user_id=${encodeURIComponent(userId)}`
    );
    if (!response.ok) {
      throw new Error(`Failed to fetch threads: ${response.status} ${response.statusText}`);
    }
    return response.json();
  } catch (error) {
    if (error instanceof TypeError && error.message === "Failed to fetch") {
      throw new Error(
        `Cannot connect to backend API at ${API_BASE}. Make sure the backend server is running on port 8000.`
      );
    }
    throw error;
  }
}

/**
 * Create a new thread.
 */
export async function createThread(userId: string, title?: string): Promise<Thread> {
  const response = await fetch(`${API_BASE}/api/threads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, title }),
  });
  if (!response.ok) {
    throw new Error("Failed to create thread");
  }
  return response.json();
}

/**
 * Delete a thread.
 */
export async function deleteThreadApi(threadId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/threads/${threadId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error("Failed to delete thread");
  }
}

/**
 * Fetch messages for a thread.
 */
export async function fetchMessages(threadId: string): Promise<Message[]> {
  const response = await fetch(`${API_BASE}/api/threads/${threadId}/messages`);
  if (!response.ok) {
    throw new Error("Failed to fetch messages");
  }
  return response.json();
}

/**
 * Truncate messages in a thread, keeping only the first N messages.
 */
export async function truncateMessages(
  threadId: string,
  keepCount: number
): Promise<{ status: string; deleted_count: number }> {
  const response = await fetch(`${API_BASE}/api/threads/${threadId}/truncate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keep_count: keepCount }),
  });
  if (!response.ok) {
    throw new Error("Failed to truncate messages");
  }
  return response.json();
}

/**
 * Fetch checkpoint history for a thread (time travel).
 */
export async function fetchThreadHistory(threadId: string): Promise<Checkpoint[]> {
  const response = await fetch(`${API_BASE}/api/threads/${threadId}/history`);
  if (!response.ok) {
    throw new Error("Failed to fetch thread history");
  }
  return response.json();
}

/**
 * Send a chat message and receive streaming response via SSE.
 */
export async function* streamChat(
  message: string,
  threadId: string,
  userId: string,
): AsyncGenerator<ChatEvent, void, unknown> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: threadId, user_id: userId }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error("Chat request failed:", response.status, errorText);
    yield { type: "error", content: `Failed to send message: ${response.status}` };
    return;
  }

  yield* readSSEStream(response);
}

/**
 * Fork from a checkpoint (time travel) and send a message.
 */
export async function* streamFork(
  message: string,
  threadId: string,
  userId: string,
  checkpointId: string,
): AsyncGenerator<ChatEvent, void, unknown> {
  const response = await fetch(`${API_BASE}/api/chat/fork`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      thread_id: threadId,
      user_id: userId,
      checkpoint_id: checkpointId,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error("Fork request failed:", response.status, errorText);
    yield { type: "error", content: `Failed to fork: ${response.status}` };
    return;
  }

  yield* readSSEStream(response);
}

/**
 * Shared SSE stream reader.
 */
async function* readSSEStream(
  response: Response
): AsyncGenerator<ChatEvent, void, unknown> {
  const reader = response.body?.getReader();
  if (!reader) {
    yield { type: "error", content: "No response body" };
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        if (buffer.trim().startsWith("data: ")) {
          try {
            yield JSON.parse(buffer.trim().slice(6)) as ChatEvent;
          } catch {
            // ignore malformed trailing data
          }
        }
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const messages = buffer.split("\n\n");
      buffer = messages.pop() || "";

      for (const msg of messages) {
        const trimmed = msg.trim();
        if (!trimmed) continue;
        for (const line of trimmed.split("\n")) {
          if (line.startsWith("data: ")) {
            try {
              const event = JSON.parse(line.slice(6)) as ChatEvent;
              yield event;
              if (event.type === "done" || event.type === "error") return;
            } catch (e) {
              console.error("Failed to parse SSE data:", line, e);
            }
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
