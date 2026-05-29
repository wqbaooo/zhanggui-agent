"use client";

import { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";
import { apiPost } from "@/lib/api";

const QUICK = [
  { label: "找铺位", msg: "帮我找适合开店的铺位" },
  { label: "算回本", msg: "帮我算一下回本周期" },
  { label: "看竞品", msg: "分析一下周边竞品" },
  { label: "今天该做什么", msg: "今天我该优先做什么？" },
];

interface CommandBarProps {
  onMessage?: (msg: string, response: string) => void;
}

export function CommandBar({ onMessage }: CommandBarProps) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  async function send(text?: string) {
    const msg = text || input.trim();
    if (!msg || loading) return;
    setInput("");
    setLoading(true);
    try {
      const data = await apiPost<{ response: string }>("/api/chat/sync", { message: msg });
      onMessage?.(msg, data.response);
    } catch {
      onMessage?.(msg, "暂时无法连接后端。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="cmd-bar flex items-center gap-3 px-4 py-3">
        <span className="mono-tag text-[#0A0A0A]/30 shrink-0 hidden sm:block">
          [ ASK ]
        </span>
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder="问点什么..."
          className="flex-1 bg-transparent text-sm text-[#0A0A0A] outline-none placeholder:text-[#0A0A0A]/25"
          style={{ fontFamily: "Noto Sans SC, sans-serif" }}
          disabled={loading}
        />
        <button
          onClick={() => send()}
          disabled={loading || !input.trim()}
          className="flex size-8 shrink-0 items-center justify-center rounded-[8px] bg-[#0A0A0A] text-[#F5EFE3] transition-colors hover:bg-[#D9261C] disabled:opacity-30"
        >
          {loading ? (
            <div className="size-3 animate-spin rounded-full border-2 border-[#F5EFE3]/30 border-t-[#F5EFE3]" />
          ) : (
            <Send className="size-3.5" />
          )}
        </button>
      </div>
      <div className="mt-2 flex flex-wrap justify-center gap-1.5">
        {QUICK.map((q) => (
          <button
            key={q.label}
            onClick={() => send(q.msg)}
            disabled={loading}
            className="rounded-full border-[1.5px] border-[#F5EFE3]/15 px-3 py-1 mono-tag text-[#F5EFE3]/30 transition-all hover:border-[#F5EFE3]/30 hover:text-[#F5EFE3]/60 disabled:opacity-30"
          >
            {q.label}
          </button>
        ))}
      </div>
    </div>
  );
}
