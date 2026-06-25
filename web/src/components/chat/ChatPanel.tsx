"use client";

import { useState, useRef, useEffect } from "react";
import { ChatMessage, AnimateIn, AnimatedButton } from "@/components/shared";

export function ChatPanel({
  onSendMessage,
  messages,
}: {
  onSendMessage?: (msg: string) => void;
  messages?: Array<{ role: "user" | "assistant"; content: string; timestamp?: string }>;
}) {
  const [input, setInput] = useState("");
  const [localMessages, setLocalMessages] = useState<Array<{ role: "user" | "assistant"; content: string; timestamp?: string }>>(
    messages || []
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [localMessages]);

  const handleSend = () => {
    if (!input.trim()) return;

    const newMsg = {
      role: "user" as const,
      content: input,
      timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
    };

    setLocalMessages((prev) => [...prev, newMsg]);
    setInput("");

    if (onSendMessage) {
      onSendMessage(input);
    }

    // Simulate assistant response
    setTimeout(() => {
      setLocalMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "收到，我来帮你分析一下...",
          timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    }, 1000);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto space-y-4 p-4">
        {localMessages.length === 0 ? (
          <AnimateIn delay={100}>
            <div className="text-center py-12 text-on-surface-variant/60">
              <p className="text-sm">开始和掌柜聊聊你的经营问题</p>
            </div>
          </AnimateIn>
        ) : (
          localMessages.map((msg, idx) => (
            <ChatMessage
              key={idx}
              role={msg.role}
              content={msg.content}
              timestamp={msg.timestamp}
            />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t border-muted-border/20">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入你的问题..."
            className="flex-1 px-4 py-2 rounded-lg bg-surface-container-high/30 border border-muted-border/30 text-sm text-on-background placeholder:text-on-surface-variant/50 focus:outline-none focus:border-agent-gold/50 transition-all"
          />
          <AnimatedButton
            variant="primary"
            size="md"
            onClick={handleSend}
            disabled={!input.trim()}
          >
            发送
          </AnimatedButton>
        </div>
      </div>
    </div>
  );
}