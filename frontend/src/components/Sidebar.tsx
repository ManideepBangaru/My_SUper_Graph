"use client";

import { useState } from "react";
import {
  Plus,
  MessageSquare,
  Trash2,
  ChevronLeft,
  RefreshCw,
} from "lucide-react";
import type { Thread } from "@/lib/api";

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  threads: Thread[];
  currentThreadId: string | null;
  onSelectThread: (threadId: string) => void;
  onNewChat: () => void;
  onDeleteThread: (threadId: string) => void;
  onRefresh: () => void;
}

export function Sidebar({
  isOpen,
  onToggle,
  threads,
  currentThreadId,
  onSelectThread,
  onNewChat,
  onDeleteThread,
  onRefresh,
}: SidebarProps) {
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleDelete = async (e: React.MouseEvent, threadId: string) => {
    e.stopPropagation();
    setDeletingId(threadId);
    await onDeleteThread(threadId);
    setDeletingId(null);
  };

  // Group threads by date
  const groupedThreads = groupThreadsByDate(threads);

  return (
    <>
      {/* Backdrop for mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-20 md:hidden"
          onClick={onToggle}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          sidebar-transition fixed md:relative z-30
          h-full bg-surface-secondary/95 backdrop-blur-md
          border-r border-neon-cyan/10
          flex flex-col
          ${isOpen ? "w-72" : "w-0 md:w-0"}
          overflow-hidden
        `}
      >
        {/* Header */}
        <div className="p-3 border-b border-neon-cyan/10 flex gap-2">
          <button
            onClick={onNewChat}
            className="flex-1 flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-tertiary hover:bg-neon-cyan/10 border border-neon-cyan/20 hover:border-neon-cyan/40 transition-all text-sm"
          >
            <Plus className="w-4 h-4 text-neon-cyan" />
            <span className="text-text-primary">New Chat</span>
          </button>
          <button
            onClick={onToggle}
            className="p-2 rounded-lg hover:bg-surface-tertiary transition-all"
          >
            <ChevronLeft className="w-5 h-5 text-text-muted" />
          </button>
        </div>

        {/* Threads List */}
        <div className="flex-1 overflow-y-auto py-2">
          {Object.entries(groupedThreads).map(([dateLabel, dateThreads]) => (
            <div key={dateLabel} className="px-2 mb-2">
              <p className="px-3 py-2 text-xs font-display font-medium text-neon-cyan/60 uppercase tracking-widest">
                {dateLabel}
              </p>
              {dateThreads.map((thread) => (
                <ThreadItem
                  key={thread.id}
                  thread={thread}
                  isActive={thread.id === currentThreadId}
                  isDeleting={thread.id === deletingId}
                  onClick={() => onSelectThread(thread.id)}
                  onDelete={(e) => handleDelete(e, thread.id)}
                />
              ))}
            </div>
          ))}

          {threads.length === 0 && (
            <div className="px-4 py-8 text-center">
              <MessageSquare className="w-8 h-8 mx-auto mb-3 text-text-muted" />
              <p className="text-sm text-text-secondary">No conversations yet</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-neon-cyan/10">
          <button
            onClick={onRefresh}
            className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-tertiary transition-all text-sm"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </aside>
    </>
  );
}

interface ThreadItemProps {
  thread: Thread;
  isActive: boolean;
  isDeleting: boolean;
  onClick: () => void;
  onDelete: (e: React.MouseEvent) => void;
}

function ThreadItem({
  thread,
  isActive,
  isDeleting,
  onClick,
  onDelete,
}: ThreadItemProps) {
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setShowMenu(true)}
      onMouseLeave={() => setShowMenu(false)}
      className={`
        group relative flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer
        transition-all duration-200
        ${isActive 
          ? "bg-neon-cyan/10 border border-neon-cyan/30 shadow-inner-glow" 
          : "hover:bg-surface-tertiary border border-transparent hover:border-neon-cyan/10"
        }
        ${isDeleting ? "opacity-50 pointer-events-none" : ""}
      `}
    >
      <MessageSquare className={`w-4 h-4 flex-shrink-0 ${isActive ? "text-neon-cyan" : "text-text-muted"}`} />
      <span className={`flex-1 text-sm truncate ${isActive ? "text-neon-cyan font-medium" : "text-text-primary"}`}>
        {thread.title || "New Chat"}
      </span>

      {/* Delete button */}
      {showMenu && !isDeleting && (
        <button
          onClick={onDelete}
          className="p-1.5 rounded-md bg-surface-tertiary hover:bg-red-500/20 text-text-muted hover:text-red-400 transition-all"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}

/**
 * Group threads by relative date (Today, Yesterday, Previous 7 Days, etc.)
 */
function groupThreadsByDate(threads: Thread[]): Record<string, Thread[]> {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
  const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
  const lastMonth = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);

  const groups: Record<string, Thread[]> = {};

  for (const thread of threads) {
    const date = thread.updated_at
      ? new Date(thread.updated_at)
      : thread.created_at
        ? new Date(thread.created_at)
        : now;

    let label: string;
    if (date >= today) {
      label = "Today";
    } else if (date >= yesterday) {
      label = "Yesterday";
    } else if (date >= lastWeek) {
      label = "This Week";
    } else if (date >= lastMonth) {
      label = "This Month";
    } else {
      label = "Archive";
    }

    if (!groups[label]) {
      groups[label] = [];
    }
    groups[label].push(thread);
  }

  return groups;
}
