"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Send, X } from "lucide-react";
import { motion } from "framer-motion";
import { API_BASE, DEFAULT_PROJECT_ID, type BusinessFact } from "@/lib/api";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

function buildFactContext(fact: BusinessFact): string {
  const parts = [
    "我正在处理一条待确认经营事实，请帮我分析并处理：",
    `- 编号：${fact.id}`,
    `- 标题：${fact.title || fact.description || fact.fact_type}`,
    `- 类型：${fact.fact_type}`,
    `- 金额：¥${fact.amount}`,
    `- 日期：${fact.date}`,
    `- 来源：${fact.source_type || fact.platform}`,
  ];
  if (fact.evidence_image_url) {
    parts.push(`- 原图链接：${API_BASE}${fact.evidence_image_url}（请提醒老板对照原图核对）`);
  }
  if (fact.anomaly_reason) {
    parts.push(`- 异常原因：${fact.anomaly_reason}`);
  }
  if (fact.missing_fields && fact.missing_fields.length > 0) {
    parts.push(`- 缺失字段：${fact.missing_fields.join("、")}`);
  }
  parts.push("", "请先用 list_pending_facts 确认这条事实存在，然后用 get_fact_detail 查看详情，再告诉我该怎么处理。");
  return parts.join("\n");
}

export function FactChatPanel({
  fact,
  onClose,
  onResolved,
}: {
  fact: BusinessFact;
  onClose: () => void;
  onResolved?: () => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);
  const sessionId = `fact-review:${DEFAULT_PROJECT_ID}:${fact.id}`;

  const sendToAgent = useCallback(async (content: string) => {
    setIsStreaming(true);
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 60_000);
    try {
      const res = await fetch(`${API_BASE}/api/chat/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: content,
          project_id: DEFAULT_PROJECT_ID,
          session_id: sessionId,
        }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        throw new Error(payload?.detail || `服务返回 ${res.status}`);
      }
      const data = await res.json();
      const response = String(data.response || "").trim();
      if (!response) throw new Error("Agent 没有返回内容");
      setMessages((prev) => [...prev, {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: response,
      }]);
      onResolved?.();
    } catch (err) {
      const msg = err instanceof DOMException && err.name === "AbortError"
        ? "处理超过 60 秒，已停止等待。你可以重新发送。"
        : err instanceof Error ? err.message : "请求失败";
      setMessages((prev) => [...prev, {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: `处理失败：${msg}`,
      }]);
    } finally {
      window.clearTimeout(timeout);
      setIsStreaming(false);
    }
  }, [onResolved, sessionId]);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    const context = buildFactContext(fact);
    setMessages([{ id: `init-${Date.now()}`, role: "user", content: context }]);
    void sendToAgent(context);
  }, [fact, sendToAgent]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    const value = input.trim();
    if (!value || isStreaming) return;
    setMessages((prev) => [...prev, { id: `user-${Date.now()}`, role: "user", content: value }]);
    setInput("");
    void sendToAgent(value);
  }, [input, isStreaming, sendToAgent]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ y: 30, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 30, opacity: 0 }}
        className="flex h-[85vh] w-full max-w-2xl flex-col rounded-t-3xl bg-[#fbf7ef] sm:h-[80vh] sm:rounded-3xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-stone-200 px-4 py-3">
          <div className="min-w-0">
            <p className="text-sm font-bold text-stone-950">对话处理</p>
            <p className="truncate text-xs text-stone-500">
              {fact.title || fact.fact_type} · ¥{fact.amount} · {fact.date}
            </p>
          </div>
          <button onClick={onClose} className="rounded-full p-1.5 text-stone-400 hover:bg-stone-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3">
          {messages.map((msg) => (
            <div key={msg.id} className={`mb-3 flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm leading-5 ${
                  msg.role === "user"
                    ? "bg-stone-900 text-white"
                    : "bg-white text-stone-800 ring-1 ring-stone-100"
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          {isStreaming && (
            <div className="flex justify-start">
              <div className="rounded-2xl bg-white px-3 py-2 ring-1 ring-stone-100">
                <Loader2 className="h-4 w-4 animate-spin text-stone-400" />
              </div>
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="border-t border-stone-200 px-3 py-3">
          <div className="flex items-center gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder='说点什么，比如"这笔金额不对"或"确认入账"'
              disabled={isStreaming}
              className="flex-1 rounded-full border border-stone-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-amber-300"
            />
            <button
              type="submit"
              disabled={isStreaming || !input.trim()}
              className="flex h-10 w-10 items-center justify-center rounded-full bg-stone-900 text-white disabled:opacity-40"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  );
}
