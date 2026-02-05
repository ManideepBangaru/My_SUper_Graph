"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  fetchThreads,
  createThread,
  deleteThreadApi,
  fetchMessages,
  fetchThreadHistory,
  truncateMessages,
  streamChat,
  streamFork,
  Thread,
  Message,
  MessageAttachment,
  Checkpoint,
} from "@/lib/api";

export interface ChatMessage {
  id: string;
  role: "human" | "ai";
  content: string;
  attachments?: MessageAttachment[];
  isStreaming?: boolean;
}

export function useChat(userId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
  const [progressStatus, setProgressStatus] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  
  // Time travel state
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [selectedCheckpoint, setSelectedCheckpoint] = useState<Checkpoint | null>(null);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [showTimeline, setShowTimeline] = useState(false);

  // Fetch threads on mount
  useEffect(() => {
    refreshThreads();
  }, [userId]);

  // Load messages when thread changes
  useEffect(() => {
    if (currentThreadId) {
      loadMessages(currentThreadId);
    } else {
      setMessages([]);
    }
  }, [currentThreadId]);

  const refreshThreads = useCallback(async () => {
    try {
      const fetchedThreads = await fetchThreads(userId);
      setThreads(fetchedThreads);
    } catch (error) {
      console.error("Failed to fetch threads:", error);
      // Show user-friendly error message
      if (error instanceof Error) {
        console.error(error.message);
      }
    }
  }, [userId]);

  const loadMessages = async (threadId: string) => {
    try {
      const fetchedMessages = await fetchMessages(threadId);
      setMessages(
        fetchedMessages.map((msg: Message) => ({
          // Use database id (guaranteed unique) as the key
          id: `db-${msg.id}`,
          role: msg.role,
          content: msg.content,
          attachments: msg.attachments || [],
        }))
      );
    } catch (error) {
      console.error("Failed to load messages:", error);
    }
  };

  const createNewThread = useCallback(async () => {
    try {
      const thread = await createThread(userId);
      setThreads((prev) => [thread, ...prev]);
      setCurrentThreadId(thread.id);
      setMessages([]);
    } catch (error) {
      console.error("Failed to create thread:", error);
    }
  }, [userId]);

  const selectThread = useCallback((threadId: string) => {
    setCurrentThreadId(threadId);
  }, []);

  const deleteThread = useCallback(
    async (threadId: string) => {
      try {
        await deleteThreadApi(threadId);
        setThreads((prev) => prev.filter((t) => t.id !== threadId));
        if (currentThreadId === threadId) {
          setCurrentThreadId(null);
          setMessages([]);
        }
      } catch (error) {
        console.error("Failed to delete thread:", error);
      }
    },
    [currentThreadId]
  );

  // Time travel: Load checkpoint history for current thread
  const loadHistory = useCallback(async () => {
    if (!currentThreadId) return;
    
    setIsHistoryLoading(true);
    try {
      const history = await fetchThreadHistory(currentThreadId);
      setCheckpoints(history);
    } catch (error) {
      console.error("Failed to load history:", error);
    } finally {
      setIsHistoryLoading(false);
    }
  }, [currentThreadId]);

  // Time travel: Select a checkpoint to preview
  const selectCheckpoint = useCallback((checkpoint: Checkpoint | null) => {
    setSelectedCheckpoint(checkpoint);
    
    // If a checkpoint is selected, show its messages
    if (checkpoint) {
      const checkpointMessages: ChatMessage[] = checkpoint.messages.map((msg, idx) => ({
        id: `checkpoint-${checkpoint.checkpoint_id}-${idx}`,
        role: msg.role === "human" ? "human" : "ai",
        content: msg.content,
      }));
      setMessages(checkpointMessages);
    } else if (currentThreadId) {
      // If deselected, reload current messages
      loadMessages(currentThreadId);
    }
  }, [currentThreadId]);

  // Time travel: Fork from a checkpoint and send a new message
  const forkFromCheckpoint = useCallback(
    async (content: string, checkpointId: string, attachments?: MessageAttachment[]) => {
      if (!content.trim() || isLoading || !currentThreadId) return;

      // Clear the selected checkpoint since we're forking
      setSelectedCheckpoint(null);
      
      // Add user message with attachments
      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "human",
        content,
        attachments: attachments || [],
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      // Add placeholder for AI response
      const aiMessageId = `ai-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        { id: aiMessageId, role: "ai", content: "", isStreaming: true },
      ]);

      try {
        // Stream the forked response with attachments
        for await (const event of streamFork(content, currentThreadId, userId, checkpointId, attachments)) {
          if (event.type === "progress") {
            const progressData = event.content as Record<string, string>;
            setProgressStatus(progressData?.Progress || JSON.stringify(progressData));
          } else if (event.type === "token") {
            const tokenContent = typeof event.content === 'string' ? event.content : "";
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMessageId
                  ? { ...msg, content: msg.content + tokenContent }
                  : msg
              )
            );
          } else if (event.type === "done") {
            setProgressStatus(null);
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMessageId ? { ...msg, isStreaming: false } : msg
              )
            );
          } else if (event.type === "error") {
            setProgressStatus(null);
            const errorContent = typeof event.content === 'string' ? event.content : "Something went wrong";
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMessageId
                  ? { ...msg, content: `Error: ${errorContent}`, isStreaming: false }
                  : msg
              )
            );
          }
        }

        // Refresh history after forking
        await loadHistory();
        await refreshThreads();
      } catch (error) {
        console.error("Failed to fork:", error);
        setProgressStatus(null);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === aiMessageId
              ? { ...msg, content: "Failed to get response. Please try again.", isStreaming: false }
              : msg
          )
        );
      } finally {
        setIsLoading(false);
        setProgressStatus(null);
      }
    },
    [currentThreadId, isLoading, userId, loadHistory, refreshThreads]
  );

  // Toggle timeline visibility
  const toggleTimeline = useCallback(() => {
    setShowTimeline((prev) => {
      const newValue = !prev;
      // Load history when opening timeline
      if (newValue && currentThreadId) {
        loadHistory();
      }
      return newValue;
    });
  }, [currentThreadId, loadHistory]);

  // Edit a user message and regenerate the response
  const editMessage = useCallback(
    async (newContent: string, messageIndex: number) => {
      if (!newContent.trim() || isLoading || !currentThreadId) return;

      // Get the original message's attachments to preserve them
      const originalMessage = messages[messageIndex];
      const originalAttachments = originalMessage?.attachments || [];

      // First, truncate messages in the database to clean up stale messages
      // This ensures that when we reload, we only see messages up to the edit point
      try {
        await truncateMessages(currentThreadId, messageIndex);
      } catch (error) {
        console.error("Failed to truncate messages:", error);
        // Continue anyway - UI will still work, just reload might show old messages
      }

      // Find the checkpoint that corresponds to the state just before this message
      // We need to load history first if not already loaded
      let history = checkpoints;
      if (history.length === 0) {
        try {
          history = await fetchThreadHistory(currentThreadId);
          setCheckpoints(history);
        } catch (error) {
          console.error("Failed to load history for edit:", error);
        }
      }

      // Count how many messages we need to keep (messages before the edited one)
      // The edited message is at messageIndex, so we want the state with messageIndex messages
      const targetMessageCount = messageIndex;

      // Find the checkpoint with the right number of messages (state just before edited message)
      // Checkpoints are ordered newest to oldest, so we look for one with targetMessageCount messages
      let targetCheckpoint = history.find(cp => cp.messages.length === targetMessageCount);
      
      if (targetCheckpoint) {
        // We found the exact checkpoint - fork from it
        // Truncate messages to show only up to the edited message point
        const truncatedMessages = messages.slice(0, messageIndex);
        setMessages(truncatedMessages);
        
        // Now fork from that checkpoint with the new content and original attachments
        await forkFromCheckpoint(newContent, targetCheckpoint.checkpoint_id, originalAttachments);
      } else {
        // No exact checkpoint found - use a simpler approach:
        // Truncate the UI messages and send as a regular message
        // This happens when we don't have granular checkpoints
        
        // Truncate messages to before the edited message
        const truncatedMessages = messages.slice(0, messageIndex);
        setMessages(truncatedMessages);
        
        // Add the new user message with original attachments
        const userMessage: ChatMessage = {
          id: `user-${Date.now()}`,
          role: "human",
          content: newContent,
          attachments: originalAttachments,
        };
        setMessages((prev) => [...prev, userMessage]);
        setIsLoading(true);

        // Add placeholder for AI response
        const aiMessageId = `ai-${Date.now()}`;
        setMessages((prev) => [
          ...prev,
          { id: aiMessageId, role: "ai", content: "", isStreaming: true },
        ]);

        try {
          // Stream chat with original attachments preserved
          for await (const event of streamChat(newContent, currentThreadId, userId, originalAttachments)) {
            if (event.type === "progress") {
              const progressData = event.content as Record<string, string>;
              setProgressStatus(progressData?.Progress || JSON.stringify(progressData));
            } else if (event.type === "token") {
              const tokenContent = typeof event.content === 'string' ? event.content : "";
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === aiMessageId
                    ? { ...msg, content: msg.content + tokenContent }
                    : msg
                )
              );
            } else if (event.type === "done") {
              setProgressStatus(null);
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === aiMessageId ? { ...msg, isStreaming: false } : msg
                )
              );
            } else if (event.type === "error") {
              setProgressStatus(null);
              const errorContent = typeof event.content === 'string' ? event.content : "Something went wrong";
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === aiMessageId
                    ? { ...msg, content: `Error: ${errorContent}`, isStreaming: false }
                    : msg
                )
              );
            }
          }
          await loadHistory();
          await refreshThreads();
        } catch (error) {
          console.error("Failed to regenerate:", error);
          setProgressStatus(null);
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === aiMessageId
                ? { ...msg, content: "Failed to get response. Please try again.", isStreaming: false }
                : msg
            )
          );
        } finally {
          setIsLoading(false);
          setProgressStatus(null);
        }
      }
    },
    [currentThreadId, isLoading, userId, messages, checkpoints, forkFromCheckpoint, loadHistory, refreshThreads]
  );

  const sendMessage = useCallback(
    async (content: string, attachments?: MessageAttachment[]) => {
      if (!content.trim() || isLoading) return;

      // Create thread if none exists
      let threadId = currentThreadId;
      if (!threadId) {
        try {
          const thread = await createThread(userId);
          setThreads((prev) => [thread, ...prev]);
          setCurrentThreadId(thread.id);
          threadId = thread.id;
        } catch (error) {
          console.error("Failed to create thread:", error);
          return;
        }
      }

      // Add user message with attachments
      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "human",
        content,
        attachments: attachments || [],
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      // Add placeholder for AI response
      const aiMessageId = `ai-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        { id: aiMessageId, role: "ai", content: "", isStreaming: true },
      ]);

      try {
        // Stream the response with attachments
        for await (const event of streamChat(content, threadId, userId, attachments)) {
          if (event.type === "progress") {
            // Handle progress events from custom stream writer
            const progressData = event.content as Record<string, string>;
            setProgressStatus(progressData?.Progress || JSON.stringify(progressData));
          } else if (event.type === "token") {
            const tokenContent = typeof event.content === 'string' ? event.content : "";
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMessageId
                  ? { ...msg, content: msg.content + tokenContent }
                  : msg
              )
            );
          } else if (event.type === "message") {
            // Full message received (fallback for non-streaming)
            const messageContent = typeof event.content === 'string' ? event.content : "";
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMessageId
                  ? { ...msg, content: messageContent, isStreaming: false }
                  : msg
              )
            );
          } else if (event.type === "done") {
            setProgressStatus(null); // Clear progress on completion
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMessageId ? { ...msg, isStreaming: false } : msg
              )
            );
          } else if (event.type === "error") {
            setProgressStatus(null); // Clear progress on error
            const errorContent = typeof event.content === 'string' ? event.content : "Something went wrong";
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMessageId
                  ? {
                      ...msg,
                      content: `Error: ${errorContent}`,
                      isStreaming: false,
                    }
                  : msg
              )
            );
          }
        }

        // Refresh threads to update title
        await refreshThreads();
      } catch (error) {
        console.error("Failed to send message:", error);
        setProgressStatus(null); // Clear progress on failure
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === aiMessageId
              ? {
                  ...msg,
                  content: "Failed to get response. Please try again.",
                  isStreaming: false,
                }
              : msg
          )
        );
      } finally {
        setIsLoading(false);
        setProgressStatus(null); // Ensure progress is cleared
      }
    },
    [currentThreadId, isLoading, userId, refreshThreads]
  );

  return {
    messages,
    isLoading,
    progressStatus,
    currentThreadId,
    threads,
    sendMessage,
    editMessage,
    createNewThread,
    selectThread,
    deleteThread,
    refreshThreads,
    // Time travel
    checkpoints,
    selectedCheckpoint,
    isHistoryLoading,
    showTimeline,
    loadHistory,
    selectCheckpoint,
    forkFromCheckpoint,
    toggleTimeline,
  };
}
