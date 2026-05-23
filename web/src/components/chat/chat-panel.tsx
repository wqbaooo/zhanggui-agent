"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { apiStream } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
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
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages]);

  async function send() {
    if (!input.trim() || streaming) return;
    const text = input.trim();
    setInput("");
    setStreaming(true);
    setError("");

    const userMsg: Message = { role: "user", content: text };
    const assistantMsg: Message = { role: "assistant", content: "", tools: [] };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    try {
      await apiStream(
        "/api/chat",
        { message: text, project_id: projectId },
        (chunk) => {
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1].content += chunk;
            return updated;
          });
        },
        (name, id) => {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            last.tools = [...(last.tools || []), { name, status: "running" }];
            return updated;
          });
        },
        (name, output) => {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            last.tools = (last.tools || []).map((t) =>
              t.name === name ? { ...t, status: "done" as const, output } : t
            );
            return updated;
          });
        }
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "未知错误";
      setError(`连接后端失败：${msg}。请确认已启动 python3 -m uvicorn server.main:app --port 8000`);
    } finally {
      setStreaming(false);
    }
  }

  return (
    <div className={className}>
      {error && (
        <div className="px-3 py-2 text-xs text-red-600 bg-red-50 border-b">{error}</div>
      )}
      {messages.length > 0 && (
        <div ref={scrollRef} className="max-h-64 overflow-auto px-4 py-3 space-y-3 border-t">
          {messages.map((msg, i) => (
            <div key={i} className={`text-sm ${msg.role === "user" ? "text-foreground" : "text-muted-foreground"}`}>
              {msg.tools?.map((t, j) => (
                <div key={j} className="flex items-center gap-2 text-xs py-0.5">
                  <span className={t.status === "running" ? "animate-pulse" : ""}>{t.status === "running" ? "⟳" : "✓"}</span>
                  <span className="text-muted-foreground">{t.status === "running" ? `调用 ${t.name}` : `完成 ${t.name}`}</span>
                </div>
              ))}
              {msg.content && <p className="whitespace-pre-wrap">{msg.content}</p>}
            </div>
          ))}
        </div>
      )}
      <div className="flex gap-2 p-3">
        <Textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} placeholder="输入问题…" className="min-h-[40px] max-h-24 resize-none text-sm" rows={1} />
        <Button onClick={send} disabled={streaming || !input.trim()} size="sm" className="shrink-0">{streaming ? "…" : "发送"}</Button>
      </div>
    </div>
  );
}
