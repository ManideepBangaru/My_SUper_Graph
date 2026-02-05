/**
 * API client for communicating with the Super Chat backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// File upload types
export interface UploadedFile {
  filename: string;
  key?: string;
  bucket?: string;
  size?: number;
  content_type?: string;
  error?: string;
}

export interface FileUploadResponse {
  uploaded: UploadedFile[];
  success_count: number;
  error_count: number;
}

export interface FileListItem {
  key: string;
  filename: string;
  size: number;
  last_modified: string;
}

/**
 * Upload files to S3.
 * Reports progress via callback.
 */
export async function uploadFiles(
  files: File[],
  userId: string,
  threadId: string,
  onProgress?: (progress: number) => void
): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append("user_id", userId);
  formData.append("thread_id", threadId);
  
  for (const file of files) {
    formData.append("files", file);
  }

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    
    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable && onProgress) {
        const progress = Math.round((event.loaded / event.total) * 100);
        onProgress(progress);
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const response = JSON.parse(xhr.responseText);
          resolve(response);
        } catch {
          reject(new Error("Failed to parse response"));
        }
      } else {
        reject(new Error(`Upload failed: ${xhr.status}`));
      }
    });

    xhr.addEventListener("error", () => {
      reject(new Error("Network error during upload"));
    });

    xhr.open("POST", `${API_BASE}/api/files/upload`);
    xhr.send(formData);
  });
}

/**
 * List files for a thread.
 */
export async function listFiles(
  userId: string,
  threadId: string
): Promise<FileListItem[]> {
  const response = await fetch(
    `${API_BASE}/api/files/${encodeURIComponent(userId)}/${encodeURIComponent(threadId)}`
  );
  if (!response.ok) {
    throw new Error("Failed to list files");
  }
  return response.json();
}

/**
 * Get presigned URL for file download.
 */
export async function getFileUrl(
  userId: string,
  threadId: string,
  filename: string
): Promise<{ url: string; expires_in: number }> {
  const response = await fetch(
    `${API_BASE}/api/files/${encodeURIComponent(userId)}/${encodeURIComponent(threadId)}/${encodeURIComponent(filename)}/url`
  );
  if (!response.ok) {
    throw new Error("Failed to get file URL");
  }
  return response.json();
}

/**
 * Delete a file.
 */
export async function deleteFile(
  userId: string,
  threadId: string,
  filename: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/api/files/${encodeURIComponent(userId)}/${encodeURIComponent(threadId)}/${encodeURIComponent(filename)}`,
    { method: "DELETE" }
  );
  if (!response.ok) {
    if (response.status === 403) {
      throw new Error("Permission denied: Cannot delete files from S3");
    }
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to delete file");
  }
}

/**
 * Get file processing status.
 */
export interface FileProcessingStatus {
  filename: string;
  processed: boolean;
  chunk_count: number;
  first_processed_at: string | null;
  last_processed_at: string | null;
}

export async function getFileProcessingStatus(
  userId: string,
  threadId: string,
  filename: string
): Promise<FileProcessingStatus> {
  const response = await fetch(
    `${API_BASE}/api/files/${encodeURIComponent(userId)}/${encodeURIComponent(threadId)}/${encodeURIComponent(filename)}/status`
  );
  if (!response.ok) {
    throw new Error("Failed to get file status");
  }
  return response.json();
}

export interface Thread {
  id: string;
  user_id: string;
  title: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface MessageAttachment {
  filename: string;
  size: number;
  s3_key?: string;
  content_type?: string;
}

export interface Message {
  id: number;
  thread_id: string;
  user_id: string | null;
  role: "human" | "ai";
  content: string;
  message_id: string | null;
  attachments: MessageAttachment[];
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
export async function createThread(
  userId: string,
  title?: string
): Promise<Thread> {
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
  const response = await fetch(
    `${API_BASE}/api/threads/${threadId}/messages`
  );
  if (!response.ok) {
    throw new Error("Failed to fetch messages");
  }
  return response.json();
}

/**
 * Truncate messages in a thread, keeping only the first N messages.
 * Used for time travel / message editing to clean up stale messages.
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
  const response = await fetch(
    `${API_BASE}/api/threads/${threadId}/history`
  );
  if (!response.ok) {
    throw new Error("Failed to fetch thread history");
  }
  return response.json();
}

/**
 * Send a chat message and receive streaming response via SSE.
 * Returns an async generator that yields ChatEvent objects.
 */
export async function* streamChat(
  message: string,
  threadId: string,
  userId: string,
  attachments?: MessageAttachment[]
): AsyncGenerator<ChatEvent, void, unknown> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      thread_id: threadId,
      user_id: userId,
      attachments: attachments || [],
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error("Chat request failed:", response.status, errorText);
    yield { type: "error", content: `Failed to send message: ${response.status}` };
    return;
  }

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
        // Process any remaining buffer
        if (buffer.trim()) {
          const remaining = buffer.trim();
          if (remaining.startsWith("data: ")) {
            try {
              const event = JSON.parse(remaining.slice(6)) as ChatEvent;
              yield event;
            } catch {
              console.error("Failed to parse remaining buffer:", remaining);
            }
          }
        }
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      // SSE messages are separated by double newlines
      const messages = buffer.split("\n\n");
      // Keep the last potentially incomplete message in buffer
      buffer = messages.pop() || "";

      for (const message of messages) {
        const trimmed = message.trim();
        if (!trimmed) continue;
        
        // Handle multi-line SSE format
        const lines = trimmed.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            try {
              const event = JSON.parse(data) as ChatEvent;
              yield event;
              if (event.type === "done" || event.type === "error") {
                return;
              }
            } catch (e) {
              console.error("Failed to parse SSE data:", data, e);
            }
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Fork from a checkpoint (time travel) and send a message.
 * Returns an async generator that yields ChatEvent objects.
 */
export async function* streamFork(
  message: string,
  threadId: string,
  userId: string,
  checkpointId: string,
  attachments?: MessageAttachment[]
): AsyncGenerator<ChatEvent, void, unknown> {
  const response = await fetch(`${API_BASE}/api/chat/fork`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      thread_id: threadId,
      user_id: userId,
      checkpoint_id: checkpointId,
      attachments: attachments || [],
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error("Fork request failed:", response.status, errorText);
    yield { type: "error", content: `Failed to fork: ${response.status}` };
    return;
  }

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
        if (buffer.trim()) {
          const remaining = buffer.trim();
          if (remaining.startsWith("data: ")) {
            try {
              const event = JSON.parse(remaining.slice(6)) as ChatEvent;
              yield event;
            } catch {
              console.error("Failed to parse remaining buffer:", remaining);
            }
          }
        }
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      const messages = buffer.split("\n\n");
      buffer = messages.pop() || "";

      for (const message of messages) {
        const trimmed = message.trim();
        if (!trimmed) continue;
        
        const lines = trimmed.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            try {
              const event = JSON.parse(data) as ChatEvent;
              yield event;
              if (event.type === "done" || event.type === "error") {
                return;
              }
            } catch (e) {
              console.error("Failed to parse SSE data:", data, e);
            }
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
