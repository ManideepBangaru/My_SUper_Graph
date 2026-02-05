"use client";

import { useRef, useEffect } from "react";
import { MessageBubble } from "./MessageBubble";
import { InputArea } from "./InputArea";
import { Menu, Gamepad2, Sparkles, Swords, Trophy, Map, History } from "lucide-react";
import type { ChatMessage } from "@/hooks/useChat";
import type { MessageAttachment } from "@/lib/api";

interface ChatWindowProps {
  messages: ChatMessage[];
  isLoading: boolean;
  progressStatus: string | null;
  isPreviewingCheckpoint: boolean;
  onSendMessage: (message: string, attachments?: MessageAttachment[]) => void;
  onEditMessage: (newContent: string, messageIndex: number) => void;
  onToggleSidebar: () => void;
  sidebarOpen: boolean;
  userId: string;
  threadId: string | null;
  onThreadCreated?: (threadId: string) => void;
}

export function ChatWindow({
  messages,
  isLoading,
  progressStatus,
  isPreviewingCheckpoint,
  onSendMessage,
  onEditMessage,
  onToggleSidebar,
  sidebarOpen,
  userId,
  threadId,
  onThreadCreated,
}: ChatWindowProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="flex items-center justify-between p-4 border-b border-neon-cyan/10 bg-surface-secondary/50 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          {!sidebarOpen && (
            <button
              onClick={onToggleSidebar}
              className="p-2 rounded-lg border border-neon-cyan/20 hover:bg-neon-cyan/10 hover:border-neon-cyan/40 transition-all"
            >
              <Menu className="w-5 h-5 text-neon-cyan" />
            </button>
          )}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gaming-gradient flex items-center justify-center">
              <Gamepad2 className="w-6 h-6 text-surface" />
            </div>
            <div>
              <h1 className="font-display font-bold text-lg">
                <span className="gradient-text">SUPER CHAT</span>
                <span className="text-text-muted text-sm font-normal ml-2">// Gaming AI</span>
              </h1>
            </div>
          </div>
        </div>
      </header>

      {/* Checkpoint Preview Banner */}
      {isPreviewingCheckpoint && (
        <div className="px-4 py-2 bg-magenta/10 border-b border-magenta/20">
          <div className="max-w-4xl mx-auto flex items-center gap-2 text-sm text-magenta">
            <History className="w-4 h-4" />
            <span className="font-medium">Previewing past checkpoint</span>
            <span className="text-magenta/60">— Use the timeline to fork or return to current state</span>
          </div>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <EmptyState onSuggestionClick={onSendMessage} />
        ) : (
          <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
            {messages.map((message, index) => (
              <MessageBubble
                key={message.id}
                role={message.role}
                content={message.content}
                attachments={message.attachments}
                isStreaming={message.isStreaming}
                progressStatus={message.isStreaming ? progressStatus : null}
                messageIndex={index}
                canEdit={message.role === "human" && !isLoading && !isPreviewingCheckpoint}
                onEdit={onEditMessage}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <InputArea 
        onSend={onSendMessage} 
        isLoading={isLoading} 
        userId={userId}
        threadId={threadId}
        onThreadCreated={onThreadCreated}
      />
    </div>
  );
}

function EmptyState({ onSuggestionClick }: { onSuggestionClick: (msg: string) => void }) {
  const suggestions = [
    {
      icon: Swords,
      title: "Battle Strategies",
      description: "How do I beat the final boss in Elden Ring?",
      gradient: "from-red-500 to-orange-500",
    },
    {
      icon: Trophy,
      title: "Game Recommendations",
      description: "What RPGs should I play if I loved The Witcher 3?",
      gradient: "from-yellow-500 to-amber-500",
    },
    {
      icon: Map,
      title: "Lore & Story",
      description: "Explain the timeline of the Zelda series",
      gradient: "from-green-500 to-emerald-500",
    },
    {
      icon: Sparkles,
      title: "Tips & Builds",
      description: "Best stealth build for Skyrim?",
      gradient: "from-blue-500 to-cyan-500",
    },
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full px-4 text-center">
      {/* Hero Section */}
      <div className="mb-8">
        <div className="w-20 h-20 rounded-2xl bg-gaming-gradient flex items-center justify-center">
          <Gamepad2 className="w-10 h-10 text-surface" />
        </div>
      </div>
      
      <h2 className="font-display text-3xl font-bold mb-2">
        <span className="gradient-text">WELCOME TO SUPER CHAT</span>
      </h2>
      <p className="text-text-secondary max-w-md mb-8 text-lg">
        Your AI-powered gaming companion. Ask me about strategies, lore, recommendations, and more!
      </p>

      {/* Suggestion Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl w-full">
        {suggestions.map((suggestion, index) => (
          <button
            key={index}
            onClick={() => onSuggestionClick(suggestion.description)}
            className="group p-4 rounded-xl bg-surface-secondary/50 border border-neon-cyan/10 
                     hover:border-neon-cyan/30 hover:bg-surface-tertiary/50 
                     transition-all duration-300 text-left
                     hover:shadow-inner-glow"
          >
            <div className="flex items-start gap-3">
              <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${suggestion.gradient} 
                            flex items-center justify-center flex-shrink-0
                            group-hover:shadow-lg transition-shadow`}>
                <suggestion.icon className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="font-display font-semibold text-sm text-neon-cyan mb-1">
                  {suggestion.title}
                </h3>
                <p className="text-xs text-text-secondary leading-relaxed">
                  {suggestion.description}
                </p>
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Powered by text */}
      <p className="mt-8 text-xs text-text-muted flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-neon-cyan animate-pulse" />
        Powered by LangGraph Multi-Agent System
      </p>
    </div>
  );
}
