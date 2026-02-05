"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { User, Gamepad2, Pencil, Check, X, FileText } from "lucide-react";
import type { MessageAttachment } from "@/lib/api";

interface MessageBubbleProps {
  role: "human" | "ai";
  content: string;
  attachments?: MessageAttachment[];
  isStreaming?: boolean;
  progressStatus?: string | null;
  messageIndex?: number;
  canEdit?: boolean;
  onEdit?: (newContent: string, messageIndex: number) => void;
}

// Format file size for display
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function MessageBubble({
  role,
  content,
  attachments,
  isStreaming,
  progressStatus,
  messageIndex = 0,
  canEdit = false,
  onEdit,
}: MessageBubbleProps) {
  const isUser = role === "human";
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState(content);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const hasAttachments = attachments && attachments.length > 0;

  // Focus textarea when entering edit mode
  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.setSelectionRange(
        textareaRef.current.value.length,
        textareaRef.current.value.length
      );
    }
  }, [isEditing]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [editedContent, isEditing]);

  const handleStartEdit = () => {
    setEditedContent(content);
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setEditedContent(content);
    setIsEditing(false);
  };

  const handleSaveEdit = () => {
    if (editedContent.trim() && editedContent !== content && onEdit) {
      onEdit(editedContent.trim(), messageIndex);
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSaveEdit();
    } else if (e.key === "Escape") {
      handleCancelEdit();
    }
  };

  return (
    <div className={`group flex flex-col gap-2 message-enter ${isUser ? "items-end" : "items-start"}`}>
      {/* File Attachments - displayed above the message */}
      {hasAttachments && (
        <div className={`flex flex-wrap gap-2 ${isUser ? "mr-14" : "ml-14"}`}>
          {attachments.map((file, idx) => (
            <div
              key={`${file.filename}-${idx}`}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs
                bg-surface-secondary border border-neon-cyan/30 text-text-primary
                hover:border-neon-cyan/50 transition-colors"
            >
              <FileText className="w-4 h-4 flex-shrink-0 text-neon-cyan" />
              <span className="max-w-[150px] truncate font-medium">
                {file.filename}
              </span>
              <span className="text-text-secondary">
                {formatFileSize(file.size)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Message row with avatars */}
      <div className={`flex gap-4 w-full ${isUser ? "justify-end" : ""}`}>
        {/* Avatar for AI */}
        {!isUser && (
          <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-gaming-gradient flex items-center justify-center">
            <Gamepad2 className="w-5 h-5 text-surface" />
          </div>
        )}

        {/* Edit button for user messages (left side) */}
        {isUser && canEdit && !isEditing && (
          <button
            onClick={handleStartEdit}
            className="self-center opacity-0 group-hover:opacity-100 p-2 rounded-lg 
                     bg-surface-tertiary/50 hover:bg-surface-tertiary border border-transparent
                     hover:border-neon-cyan/20 transition-all"
            title="Edit message"
          >
            <Pencil className="w-4 h-4 text-text-secondary hover:text-neon-cyan" />
          </button>
        )}

        {/* Message content */}
        <div
          className={`max-w-[80%] md:max-w-[70%] rounded-2xl px-5 py-4 ${
            isUser
              ? isEditing
                ? "bg-surface-secondary border-2 border-neon-cyan/50"
                : "bg-gradient-to-br from-neon-cyan to-purple-neon text-surface font-medium rounded-br-md"
              : "bg-surface-secondary border border-surface-tertiary text-text-primary rounded-bl-md"
          }`}
        >
          {isUser ? (
            isEditing ? (
              <div className="flex flex-col gap-2">
                <textarea
                  ref={textareaRef}
                  value={editedContent}
                  onChange={(e) => setEditedContent(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="w-full bg-transparent text-text-primary resize-none outline-none min-h-[60px]"
                  placeholder="Edit your message..."
                />
                <div className="flex items-center justify-end gap-2 pt-2 border-t border-surface-tertiary">
                  <button
                    onClick={handleCancelEdit}
                    className="p-1.5 rounded-lg hover:bg-surface-tertiary transition-colors"
                    title="Cancel (Esc)"
                  >
                    <X className="w-4 h-4 text-text-secondary" />
                  </button>
                  <button
                    onClick={handleSaveEdit}
                    disabled={!editedContent.trim() || editedContent === content}
                    className="p-1.5 rounded-lg bg-neon-cyan/20 hover:bg-neon-cyan/30 
                             disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    title="Save and regenerate (Enter)"
                  >
                    <Check className="w-4 h-4 text-neon-cyan" />
                  </button>
                </div>
              </div>
            ) : (
              content ? <p className="whitespace-pre-wrap">{content}</p> : null
            )
          ) : (
            <div className="prose prose-invert">
              {content ? (
                <>
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeHighlight]}
                  >
                    {content}
                  </ReactMarkdown>
                  {isStreaming && <StreamingCursor />}
                </>
              ) : isStreaming ? (
                <StreamingStatus progressStatus={progressStatus} />
              ) : null}
            </div>
          )}
        </div>

        {/* Avatar for User */}
        {isUser && (
          <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-surface-tertiary border border-neon-cyan/20 flex items-center justify-center">
            <User className="w-5 h-5 text-neon-cyan" />
          </div>
        )}
      </div>
    </div>
  );
}

function StreamingStatus({ progressStatus }: { progressStatus?: string | null }) {
  return (
    <div className="flex items-center gap-1.5 py-2">
      <span className="typing-dot w-2 h-2 rounded-full" />
      <span className="typing-dot w-2 h-2 rounded-full" />
      <span className="typing-dot w-2 h-2 rounded-full" />
      <span className="ml-2 text-xs text-neon-cyan/60 font-display">
        {progressStatus || "PROCESSING"}
      </span>
    </div>
  );
}

function StreamingCursor() {
  return (
    <span className="inline-block w-2 h-5 bg-neon-cyan ml-0.5 animate-pulse" />
  );
}
