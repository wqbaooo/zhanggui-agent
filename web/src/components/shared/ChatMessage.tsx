"use client";

import { cn } from "@/lib/utils";

export function ChatMessage({
  role,
  content,
  timestamp,
}: {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}) {
  const isUser = role === "user";

  return (
    <div
      className={cn(
        "flex gap-3 animate-slide-in",
        isUser ? "justify-end animate-slide-in-right" : "justify-start animate-slide-in-left"
      )}
    >
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-primary to-agent-gold flex items-center justify-center text-white text-sm font-semibold animate-glow-pulse">
          掌
        </div>
      )}

      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-3 shadow-sm transition-all duration-300",
          "group relative overflow-hidden",
          isUser
            ? "bg-primary text-on-primary hover:shadow-lg"
            : "glass-card hover:shadow-md"
        )}
      >
        {/* 背景光效 - 仅助手消息 */}
        {!isUser && (
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
        )}

        <div className="relative z-10">
          <p className={cn(
            "text-sm leading-relaxed whitespace-pre-wrap",
            isUser ? "text-on-primary" : "text-on-background"
          )}>
            {content}
          </p>

          {timestamp && (
            <p className={cn(
              "text-xs mt-2 opacity-60",
              isUser ? "text-on-primary" : "text-on-surface-variant"
            )}>
              {timestamp}
            </p>
          )}
        </div>

        {/* 底部装饰线 */}
        <div className={cn(
          "absolute bottom-0 left-0 right-0 h-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-500",
          isUser
            ? "bg-gradient-to-r from-transparent via-on-primary/30 to-transparent"
            : "bg-gradient-to-r from-transparent via-primary/40 to-transparent"
        )} />
      </div>

      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-on-surface-variant flex items-center justify-center text-white text-sm font-semibold">
          你
        </div>
      )}
    </div>
  );
}