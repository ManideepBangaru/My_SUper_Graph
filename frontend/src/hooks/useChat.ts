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
  Checkpoint,
} from "@/lib/api";

export interface ChatMessage {
  id: string;
  role: "human" | "ai";
  content: string;
  isStreaming?: boolean;
}

export function useChat(userId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
  const [progressStatus, setProgressStatus] = useState<string | null>(null);
  // Prevents loadMessages from overwriting in-progress streaming state
  const isStreamingRef = useRef(false);

  // Time travel state
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [selectedCheckpoint, setSelectedCheckpoint] = useState<Checkpoint | null>(null);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [showTimeline, setShowTimeline] = useState(false);

  useEffect(() => {
    refreshThreads();
  }, [userId]);

  useEffect(() => {
    if (!currentThreadId) {
      setMessages([]);
      return;
    }
    // Skip DB load while streaming — streaming state owns the messages right now
    if (!isStreamingRef.current) {
      loadMessages(currentThreadId);
    }
  }, [currentThreadId]);

  const refreshThreads = useCallback(async () => {
    try {
      const fetched = await fetchThreads(userId);
      setThreads(fetched);
    } catch (error) {
      console.error("Failed to fetch threads:", error);
    }
  }, [userId]);

  const loadMessages = async (threadId: string) => {
    try {
      const fetched = await fetchMessages(threadId);
      setMessages(
        fetched.map((msg: Message) => ({
          id: `db-${msg.id}`,
          role: msg.role,
          content: msg.content,
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

  const selectCheckpoint = useCallback(
    (checkpoint: Checkpoint | null) => {
      setSelectedCheckpoint(checkpoint);
      if (checkpoint) {
        setMessages(
          checkpoint.messages.map((msg, idx) => ({
            id: `checkpoint-${checkpoint.checkpoint_id}-${idx}`,
            role: msg.role === "human" ? "human" : "ai",
            content: msg.content,
          }))
        );
      } else if (currentThreadId) {
        loadMessages(currentThreadId);
      }
    },
    [currentThreadId]
  );

  const forkFromCheckpoint = useCallback(
    async (content: string, checkpointId: string) => {
      if (!content.trim() || isLoading || !currentThreadId) return;

      isStreamingRef.current = true;
      setSelectedCheckpoint(null);

      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "human",
        content,
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      const aiMessageId = `ai-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        { id: aiMessageId, role: "ai", content: "", isStreaming: true },
      ]);

      try {
        for await (const event of streamFork(content, currentThreadId, userId, checkpointId)) {
          if (event.type === "progress") {
            const p = event.content as Record<string, string>;
            setProgressStatus(p?.Progress || JSON.stringify(p));
          } else if (event.type === "token") {
            const token = typeof event.content === "string" ? event.content : "";
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMessageId ? { ...msg, content: msg.content + token } : msg
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
            const err = typeof event.content === "string" ? event.content : "Something went wrong";
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMessageId
                  ? { ...msg, content: `Error: ${err}`, isStreaming: false }
                  : msg
              )
            );
          }
        }
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
        isStreamingRef.current = false;
        setIsLoading(false);
        setProgressStatus(null);
      }
    },
    [currentThreadId, isLoading, userId, loadHistory, refreshThreads]
  );

  const toggleTimeline = useCallback(() => {
    setShowTimeline((prev) => {
      const next = !prev;
      if (next && currentThreadId) loadHistory();
      return next;
    });
  }, [currentThreadId, loadHistory]);

  const editMessage = useCallback(
    async (newContent: string, messageIndex: number) => {
      if (!newContent.trim() || isLoading || !currentThreadId) return;

      try {
        await truncateMessages(currentThreadId, messageIndex);
      } catch (error) {
        console.error("Failed to truncate messages:", error);
      }

      let history = checkpoints;
      if (history.length === 0) {
        try {
          history = await fetchThreadHistory(currentThreadId);
          setCheckpoints(history);
        } catch (error) {
          console.error("Failed to load history for edit:", error);
        }
      }

      const targetCheckpoint = history.find((cp) => cp.messages.length === messageIndex);

      if (targetCheckpoint) {
        setMessages(messages.slice(0, messageIndex));
        await forkFromCheckpoint(newContent, targetCheckpoint.checkpoint_id);
      } else {
        setMessages(messages.slice(0, messageIndex));

        const userMessage: ChatMessage = {
          id: `user-${Date.now()}`,
          role: "human",
          content: newContent,
        };
        setMessages((prev) => [...prev, userMessage]);
        setIsLoading(true);

        const aiMessageId = `ai-${Date.now()}`;
        setMessages((prev) => [
          ...prev,
          { id: aiMessageId, role: "ai", content: "", isStreaming: true },
        ]);

        try {
          for await (const event of streamChat(newContent, currentThreadId, userId)) {
            if (event.type === "progress") {
              const p = event.content as Record<string, string>;
              setProgressStatus(p?.Progress || JSON.stringify(p));
            } else if (event.type === "token") {
              const token = typeof event.content === "string" ? event.content : "";
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === aiMessageId ? { ...msg, content: msg.content + token } : msg
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
              const err = typeof event.content === "string" ? event.content : "Something went wrong";
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === aiMessageId
                    ? { ...msg, content: `Error: ${err}`, isStreaming: false }
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
    async (content: string) => {
      if (!content.trim() || isLoading) return;

      // Mark as streaming BEFORE any setState that could trigger useEffect
      isStreamingRef.current = true;

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

      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "human",
        content,
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      const aiMessageId = `ai-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        { id: aiMessageId, role: "ai", content: "", isStreaming: true },
      ]);

      try {
        for await (const event of streamChat(content, threadId, userId)) {
          if (event.type === "progress") {
            const p = event.content as Record<string, string>;
            setProgressStatus(p?.Progress || JSON.stringify(p));
          } else if (event.type === "token") {
            const token = typeof event.content === "string" ? event.content : "";
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMessageId ? { ...msg, content: msg.content + token } : msg
              )
            );
          } else if (event.type === "message") {
            const msgContent = typeof event.content === "string" ? event.content : "";
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMessageId
                  ? { ...msg, content: msgContent, isStreaming: false }
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
            const err = typeof event.content === "string" ? event.content : "Something went wrong";
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMessageId
                  ? { ...msg, content: `Error: ${err}`, isStreaming: false }
                  : msg
              )
            );
          }
        }
        await refreshThreads();
      } catch (error) {
        console.error("Failed to send message:", error);
        setProgressStatus(null);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === aiMessageId
              ? { ...msg, content: "Failed to get response. Please try again.", isStreaming: false }
              : msg
          )
        );
      } finally {
        isStreamingRef.current = false;
        setIsLoading(false);
        setProgressStatus(null);
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
