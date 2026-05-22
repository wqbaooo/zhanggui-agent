"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";

const suggestions = [
  "分析这个铺位的优劣",
  "计算回本周期",
  "生成证照清单",
  "我的成本结构健康吗",
];

interface Message {
  role: "user" | "assistant";
  content: string;
}

export function FloatingAI() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "你好，我是开店顾问。有什么可以帮你？" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages]);

  async function send(text?: string) {
    const msg = text || input.trim();
    if (!msg || loading) return;
    setInput("");
    setLoading(true);
    setMessages((prev) => [...prev, { role: "user", content: msg }]);

    try {
      const res = await fetch("http://localhost:8000/api/chat/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg }),
      });
      const data = await res.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data.response }]);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "抱歉，请求失败" }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 w-12 h-12 rounded-full bg-primary text-primary-foreground shadow-lg hover:shadow-xl transition-shadow flex items-center justify-center z-50"
      >
        <span className="text-lg">?</span>
      </button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="right" className="w-[400px] sm:w-[480px] flex flex-col p-0">
          <SheetHeader className="px-4 pt-4 pb-2">
            <SheetTitle className="text-sm">开店顾问</SheetTitle>
          </SheetHeader>
          <div ref={scrollRef} className="flex-1 overflow-auto px-4 py-2 space-y-3">
            {messages.map((msg, i) => (
              <div key={i}>
                <p className="text-xs text-muted-foreground mb-0.5">
                  {msg.role === "user" ? "你" : "Agent"}
                </p>
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              </div>
            ))}
            {loading && <p className="text-xs text-muted-foreground animate-pulse">思考中…</p>}
          </div>
          <div className="px-3 py-2 border-t">
            <div className="flex flex-wrap gap-1.5 mb-2">
              {suggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-xs px-2 py-1 rounded-full bg-muted hover:bg-accent transition-colors text-muted-foreground"
                >
                  {s}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                placeholder="输入问题…"
                className="min-h-[36px] max-h-24 resize-none text-sm"
                rows={1}
              />
              <Button onClick={() => send()} disabled={loading || !input.trim()} size="sm">
                发送
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
