"use client";

import { History, GitBranch, ChevronRight, X, Clock, MessageSquare } from "lucide-react";
import type { Checkpoint } from "@/lib/api";

interface TimelinePanelProps {
  checkpoints: Checkpoint[];
  selectedCheckpoint: Checkpoint | null;
  isLoading: boolean;
  onSelectCheckpoint: (checkpoint: Checkpoint | null) => void;
  onFork: (message: string, checkpointId: string) => void;
  onClose: () => void;
}

export function TimelinePanel({
  checkpoints,
  selectedCheckpoint,
  isLoading,
  onSelectCheckpoint,
  onFork,
  onClose,
}: TimelinePanelProps) {
  return (
    <div className="w-80 border-l border-neon-cyan/10 bg-surface-secondary/50 backdrop-blur-sm flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-neon-cyan/10">
        <div className="flex items-center gap-2">
          <History className="w-5 h-5 text-neon-cyan" />
          <h2 className="font-display font-semibold text-sm gradient-text">TIME TRAVEL</h2>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-surface-tertiary/50 transition-colors"
        >
          <X className="w-4 h-4 text-text-secondary" />
        </button>
      </div>

      {/* Instructions */}
      <div className="px-4 py-3 border-b border-neon-cyan/10 bg-neon-cyan/5">
        <p className="text-xs text-text-secondary">
          Select a checkpoint to preview past states. Click <GitBranch className="w-3 h-3 inline" /> to fork and continue from that point.
        </p>
      </div>

      {/* Checkpoint List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="flex items-center gap-2 text-text-secondary">
              <Clock className="w-4 h-4 animate-spin" />
              <span className="text-sm">Loading history...</span>
            </div>
          </div>
        ) : checkpoints.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-center px-4">
            <History className="w-8 h-8 text-text-muted mb-2" />
            <p className="text-sm text-text-secondary">No checkpoints yet</p>
            <p className="text-xs text-text-muted mt-1">
              Send messages to create history
            </p>
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {checkpoints.map((checkpoint, index) => (
              <CheckpointItem
                key={checkpoint.checkpoint_id}
                checkpoint={checkpoint}
                isSelected={selectedCheckpoint?.checkpoint_id === checkpoint.checkpoint_id}
                isLatest={index === 0}
                onSelect={() => onSelectCheckpoint(
                  selectedCheckpoint?.checkpoint_id === checkpoint.checkpoint_id 
                    ? null 
                    : checkpoint
                )}
                onFork={onFork}
              />
            ))}
          </div>
        )}
      </div>

      {/* Selected Checkpoint Actions */}
      {selectedCheckpoint && (
        <div className="p-4 border-t border-neon-cyan/10 bg-surface-tertiary/30">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-2 h-2 rounded-full bg-magenta animate-pulse" />
            <span className="text-xs text-magenta font-medium">Previewing checkpoint</span>
          </div>
          <button
            onClick={() => onSelectCheckpoint(null)}
            className="w-full py-2 px-3 rounded-lg border border-neon-cyan/20 text-sm text-text-secondary
                     hover:bg-neon-cyan/10 hover:border-neon-cyan/40 hover:text-neon-cyan transition-all"
          >
            Return to current state
          </button>
        </div>
      )}
    </div>
  );
}

interface CheckpointItemProps {
  checkpoint: Checkpoint;
  isSelected: boolean;
  isLatest: boolean;
  onSelect: () => void;
  onFork: (message: string, checkpointId: string) => void;
}

function CheckpointItem({
  checkpoint,
  isSelected,
  isLatest,
  onSelect,
  onFork,
}: CheckpointItemProps) {
  // Get the last message for preview
  const lastMessage = checkpoint.messages[checkpoint.messages.length - 1];
  const messageCount = checkpoint.messages.length;
  
  // Get a preview of the conversation
  const getPreview = () => {
    if (!lastMessage) return "Empty state";
    const preview = lastMessage.content.slice(0, 60);
    return preview.length < lastMessage.content.length ? `${preview}...` : preview;
  };

  const handleFork = (e: React.MouseEvent) => {
    e.stopPropagation();
    // For now, prompt for message (could be enhanced with a modal)
    const message = window.prompt("Enter your message to continue from this checkpoint:");
    if (message?.trim()) {
      onFork(message, checkpoint.checkpoint_id);
    }
  };

  return (
    <div
      onClick={onSelect}
      className={`
        group relative p-3 rounded-lg cursor-pointer transition-all
        ${isSelected 
          ? "bg-neon-cyan/10 border border-neon-cyan/30" 
          : "hover:bg-surface-tertiary/50 border border-transparent"
        }
      `}
    >
      {/* Timeline connector */}
      <div className="absolute left-6 top-full w-px h-1 bg-surface-tertiary" />
      
      <div className="flex items-start gap-3">
        {/* Step indicator */}
        <div className={`
          flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-mono
          ${isLatest 
            ? "bg-gaming-gradient text-surface" 
            : isSelected 
              ? "bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/30"
              : "bg-surface-tertiary text-text-secondary"
          }
        `}>
          {isLatest ? "•" : checkpoint.step}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-medium ${isLatest ? "text-neon-cyan" : "text-text-secondary"}`}>
              {isLatest ? "Current" : `Step ${checkpoint.step}`}
            </span>
            <div className="flex items-center gap-1 text-xs text-text-muted">
              <MessageSquare className="w-3 h-3" />
              <span>{messageCount}</span>
            </div>
          </div>
          
          <p className="text-xs text-text-secondary line-clamp-2 leading-relaxed">
            {getPreview()}
          </p>

          {lastMessage && (
            <span className={`
              inline-block mt-1 px-1.5 py-0.5 rounded text-[10px] font-medium
              ${lastMessage.role === "human" 
                ? "bg-purple-neon/20 text-purple-neon" 
                : "bg-neon-cyan/20 text-neon-cyan"
              }
            `}>
              {lastMessage.role === "human" ? "User" : "AI"}
            </span>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {!isLatest && (
            <button
              onClick={handleFork}
              className="p-1.5 rounded-lg bg-magenta/10 hover:bg-magenta/20 text-magenta transition-colors"
              title="Fork from this checkpoint"
            >
              <GitBranch className="w-3.5 h-3.5" />
            </button>
          )}
          <ChevronRight className={`w-4 h-4 transition-transform ${isSelected ? "rotate-90 text-neon-cyan" : "text-text-muted"}`} />
        </div>
      </div>
    </div>
  );
}
