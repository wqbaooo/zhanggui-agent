"use client";

import { useState, useRef, useEffect } from "react";
import { MessageCircle, SendHorizonal, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { apiPost } from "@/lib/api";

const suggestions = ["分析这个铺位的优劣", "计算回本周期", "生成证照清单", "我的成本结构健康吗"];

interface Message {
  role: "user" | "assistant";
  content: string;
}

export function FloatingAI() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([{ role: "assistant", content: "你好，我是开店顾问。有什么可以帮你？" }]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => { scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight); }, [messages]);

  async function send(text?: string) {
    const msg = text || input.trim();
    if (!msg || loading) return;
    setInput("");
    setLoading(true);
    setError("");
    setMessages((prev) => [...prev, { role: "user", content: msg }]);

    try {
      const data = await apiPost<{ response: string }>("/api/chat/sync", { message: msg });
      setMessages((prev) => [...prev, { role: "assistant", content: data.response }]);
    } catch {
      setError("无法连接后端服务。请确认已启动：python3 -m uvicorn server.main:app --port 8000");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button onClick={() => setOpen(true)} className="fixed bottom-5 right-5 z-50 flex size-12 items-center justify-center rounded-full bg-[#d95b00] text-white shadow-[0_16px_35px_rgba(217,91,0,0.32)] transition-transform hover:-translate-y-0.5 hover:shadow-[0_18px_42px_rgba(217,91,0,0.38)]">
        <MessageCircle className="size-5" />
      </button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="right" className="w-[400px] sm:w-[480px] flex flex-col p-0">
          <SheetHeader className="border-b px-4 py-4">
            <SheetTitle className="flex items-center gap-2 text-sm">
              <span className="flex size-7 items-center justify-center rounded-lg bg-[#fff1df] text-[#d95b00]"><Sparkles className="size-4" /></span>
              开店顾问
            </SheetTitle>
          </SheetHeader>
          <div ref={scrollRef} className="flex-1 overflow-auto px-4 py-2 space-y-3">
            {messages.map((msg, i) => (
              <div key={i}><p className="text-xs text-muted-foreground mb-0.5">{msg.role === "user" ? "你" : "Agent"}</p><p className="text-sm whitespace-pre-wrap">{msg.content}</p></div>
            ))}
            {loading && <p className="text-xs text-muted-foreground animate-pulse">思考中…</p>}
            {error && <p className="text-xs text-red-600 bg-red-50 p-2 rounded">{error}</p>}
          </div>
          <div className="px-3 py-2 border-t">
            <div className="flex flex-wrap gap-1.5 mb-2">
              {suggestions.map((s) => (<button key={s} onClick={() => send(s)} className="text-xs px-2 py-1 rounded-full bg-muted hover:bg-accent transition-colors text-muted-foreground">{s}</button>))}
            </div>
            <div className="flex gap-2">
              <Textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} placeholder="输入问题…" className="min-h-[36px] max-h-24 resize-none text-sm" rows={1} />
              <Button onClick={() => send()} disabled={loading || !input.trim()} size="sm">
                <SendHorizonal className="size-4" />
                发送
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
