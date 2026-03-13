"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Send, Loader2, Zap } from "lucide-react";

interface InputAreaProps {
  onSend: (message: string) => void;
  isLoading: boolean;
  disabled?: boolean;
}

export function InputArea({ onSend, isLoading, disabled }: InputAreaProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleSubmit = () => {
    if (input.trim() && !isLoading && !disabled) {
      onSend(input.trim());
      setInput("");
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="border-t border-neon-cyan/10 bg-surface-secondary/50 backdrop-blur-sm p-4">
      <div className="max-w-4xl mx-auto">
        <div className="relative">
          <div className="absolute inset-0 bg-gaming-gradient opacity-5 rounded-2xl blur-xl" />

          <div className="relative flex items-end gap-3 bg-surface-tertiary/80 rounded-2xl border border-neon-cyan/20 p-3 focus-within:border-neon-cyan/50 focus-within:shadow-inner-glow transition-all">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about games, movies, or TV shows..."
              disabled={disabled || isLoading}
              rows={1}
              className="flex-1 bg-transparent resize-none outline-none text-text-primary placeholder:text-text-muted min-h-[28px] max-h-[200px] text-base"
            />
            <button
              onClick={handleSubmit}
              disabled={!input.trim() || isLoading || disabled}
              className="flex-shrink-0 w-11 h-11 rounded-xl btn-gaming disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:transform-none disabled:hover:shadow-none flex items-center justify-center transition-all"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>

        <div className="flex items-center justify-center gap-2 mt-3">
          <Zap className="w-3 h-3 text-neon-cyan/40" />
          <p className="text-xs text-text-muted">
            Powered by <span className="text-neon-cyan/60 font-display">SUPER CHAT</span> • Games &amp; Movies only
          </p>
        </div>
      </div>
    </div>
  );
}
