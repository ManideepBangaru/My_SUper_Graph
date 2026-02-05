"use client";

import { useState, useCallback } from "react";
import { Sidebar } from "@/components/Sidebar";
import { ChatWindow } from "@/components/ChatWindow";
import { TimelinePanel } from "@/components/TimelinePanel";
import { useChat } from "@/hooks/useChat";

// For demo purposes, use a fixed user ID
const USER_ID = "user_demo";

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const {
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
    selectCheckpoint,
    forkFromCheckpoint,
    toggleTimeline,
  } = useChat(USER_ID);

  const handleNewChat = useCallback(async () => {
    await createNewThread();
  }, [createNewThread]);

  const handleThreadCreatedFromUpload = useCallback(async (threadId: string) => {
    selectThread(threadId);
    await refreshThreads();
  }, [selectThread, refreshThreads]);

  return (
    <div className="flex h-screen overflow-hidden bg-surface cyber-grid hex-pattern">
      {/* Ambient glow effects */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-neon-cyan/5 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-magenta/5 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-purple-neon/3 rounded-full blur-3xl" />
      </div>

      {/* Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        threads={threads}
        currentThreadId={currentThreadId}
        onSelectThread={selectThread}
        onNewChat={handleNewChat}
        onDeleteThread={deleteThread}
        onRefresh={refreshThreads}
      />

      {/* Main Chat Area */}
      <main className="flex-1 flex min-w-0 relative z-10">
        <div className="flex-1 flex flex-col">
          <ChatWindow
            messages={messages}
            isLoading={isLoading}
            progressStatus={progressStatus}
            isPreviewingCheckpoint={selectedCheckpoint !== null}
            onSendMessage={sendMessage}
            onEditMessage={editMessage}
            onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
            sidebarOpen={sidebarOpen}
            userId={USER_ID}
            threadId={currentThreadId}
            onThreadCreated={handleThreadCreatedFromUpload}
          />
        </div>
        
        {/* Time Travel Panel */}
        {showTimeline && (
          <TimelinePanel
            checkpoints={checkpoints}
            selectedCheckpoint={selectedCheckpoint}
            isLoading={isHistoryLoading}
            onSelectCheckpoint={selectCheckpoint}
            onFork={forkFromCheckpoint}
            onClose={toggleTimeline}
          />
        )}
      </main>
    </div>
  );
}
