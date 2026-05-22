"use client";

import { useRef, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface Message {
  role: "user" | "assistant";
  content: string;
  thinking?: string[];
  tools?: { name: string; status: "running" | "done"; output?: string }[];
}

interface ChatPanelProps {
  projectId?: string;
  className?: string;
}

export function ChatPanel({ projectId, className }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages]);

  async function send() {
    if (!input.trim() || streaming) return;
    const text = input.trim();
    setInput("");
    setStreaming(true);

    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);

    const assistantMsg: Message = { role: "assistant", content: "", thinking: [], tools: [] };
    setMessages((prev) => [...prev, assistantMsg]);

    try {
      const res = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, project_id: projectId }),
      });

      const reader = res.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          const match = line.match(/^[02]:/);
          if (!match) continue;

          try {
            const jsonStr = line.slice(2);
            const data = JSON.parse(jsonStr);

            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last.role !== "assistant") return prev;

              if (match[0] === "0") {
                last.content += data;
              } else if (Array.isArray(data) && data[0]) {
                const d = data[0];
                if (d.toolName && !d.output) {
                  last.tools = [...(last.tools || []), { name: d.toolName, status: "running" }];
                }
                if (d.toolName && d.output) {
                  last.tools = (last.tools || []).map((t) =>
                    t.name === d.toolName ? { ...t, status: "done" as const, output: d.output } : t
                  );
                }
              }
              return updated;
            });
          } catch {
            // skip malformed sse frames
          }
        }
      }
    } catch (err) {
      console.error("Stream error:", err);
    } finally {
      setStreaming(false);
    }
  }

  return (
    <div className={className}>
      {messages.length > 0 && (
        <div ref={scrollRef} className="max-h-64 overflow-auto px-4 py-3 space-y-3 border-t">
          {messages.map((msg, i) => (
            <div key={i} className={`text-sm ${msg.role === "user" ? "text-foreground" : "text-muted-foreground"}`}>
              {msg.thinking?.map((t, j) => (
                <p key={j} className="text-xs text-muted-foreground/60 italic">{t}</p>
              ))}
              {msg.tools?.map((t, j) => (
                <div key={j} className="flex items-center gap-2 text-xs py-0.5">
                  <span className={t.status === "running" ? "animate-pulse" : ""}>
                    {t.status === "running" ? "⟳" : "✓"}
                  </span>
                  <span className="text-muted-foreground">
                    {t.status === "running" ? `正在调用 ${t.name}` : `已完成 ${t.name}`}
                  </span>
                </div>
              ))}
              {msg.content && <p className="whitespace-pre-wrap">{msg.content}</p>}
            </div>
          ))}
        </div>
      )}
      <div className="flex gap-2 p-3">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder="输入问题，如：帮我分析这个铺位的优劣"
          className="min-h-[40px] max-h-24 resize-none text-sm"
          rows={1}
        />
        <Button onClick={send} disabled={streaming || !input.trim()} size="sm" className="shrink-0">
          {streaming ? "…" : "发送"}
        </Button>
      </div>
    </div>
  );
}
