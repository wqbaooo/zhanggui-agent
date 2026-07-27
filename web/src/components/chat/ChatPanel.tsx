"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Loader2,
  MessageSquarePlus,
  Plus,
  Send,
  Sparkles,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { ChatMessage } from "@/components/shared";
import { useAIChat } from "@/lib/hooks/useAIChat";
import { storeIdentity } from "@/data/agent-store-os";
import { cn } from "@/lib/utils";

export function ChatPanel({
  variant = "fullpage",
  onClose,
}: {
  variant?: "fullpage" | "modal";
  onClose?: () => void;
}) {
  const router = useRouter();
  const {
    messages,
    isStreaming,
    error: chatError,
    sendMessage,
    sessions,
    activeSessionId,
    setActiveSession,
    createNewSession,
    deleteSession,
    activeSession,
    runtimeStatus,
  } = useAIChat();

  const [input, setInput] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (!input.trim() || isStreaming) return;
      sendMessage(input.trim());
      setInput("");
    },
    [input, isStreaming, sendMessage]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit(e as unknown as React.FormEvent);
      }
    },
    [handleSubmit]
  );

  const formatTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "";
    }
  };

  const formatDate = (iso: string) => {
    try {
      const d = new Date(iso);
      const today = new Date();
      const isToday = d.toDateString() === today.toDateString();
      if (isToday) return "今天";
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      if (d.toDateString() === yesterday.toDateString()) return "昨天";
      return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
    } catch {
      return "";
    }
  };

  const handleBack = useCallback(() => {
    if (onClose) {
      onClose();
    } else {
      router.push("/overview");
    }
  }, [onClose, router]);

  const containerClass =
    variant === "modal"
      ? "h-full w-full"
      : "h-[calc(100dvh-6rem)] min-h-[620px] w-full rounded-[28px] border border-white/90 bg-white/80 shadow-[0_20px_70px_rgba(55,40,28,0.10)]";

  return (
    <div className={cn("flex min-h-0 overflow-hidden", containerClass)}>
      <AnimatePresence initial={false}>
        {sidebarOpen && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 280, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 32 }}
            className="shrink-0 overflow-hidden border-r border-stone-200/70 bg-[rgba(250,248,245,0.88)] backdrop-blur-2xl"
          >
            <div className="flex h-full flex-col p-4">
              <button
                onClick={createNewSession}
                className="flex h-11 items-center gap-2 rounded-2xl border border-stone-200/80 bg-white/90 px-3.5 text-sm font-semibold text-stone-800 shadow-[0_4px_18px_rgba(68,48,36,0.06)] transition-[transform,border-color,box-shadow,background-color] duration-200 ease-out hover:-translate-y-0.5 hover:border-octo-200 hover:bg-white hover:shadow-[0_8px_24px_rgba(68,48,36,0.09)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-octo-300"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-octo-50 text-octo-600">
                  <Plus className="h-4 w-4" />
                </span>
                新建对话
              </button>

              <div className="mt-4 flex-1 space-y-1 overflow-y-auto pr-1">
                {sessions.length === 0 ? (
                  <p className="px-3 py-4 text-xs text-stone-400">还没有对话记录</p>
                ) : (
                  sessions.map((session) => {
                    const isActive = session.id === activeSessionId;
                    return (
                      <div
                        key={session.id}
                        className={cn(
                          "group relative flex min-h-14 items-center gap-2.5 rounded-2xl px-3 py-2.5 cursor-pointer transition-[background-color,color,transform] duration-200 ease-out",
                          isActive
                            ? "bg-white text-octo-800 shadow-[0_5px_18px_rgba(78,48,31,0.07)]"
                            : "text-stone-600 hover:translate-x-0.5 hover:bg-white/65"
                        )}
                        onClick={() => setActiveSession(session.id)}
                      >
                        {isActive && (
                          <span className="absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-full bg-octo-500" />
                        )}
                        <MessageSquarePlus
                          className={cn(
                            "h-4 w-4 shrink-0",
                            isActive ? "text-octo-500" : "text-stone-400"
                          )}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[13px] font-semibold">{session.title}</p>
                          <p className="mt-0.5 truncate text-[11px] text-stone-400">
                            {formatDate(session.updatedAt)} · {formatTime(session.updatedAt)}
                          </p>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteSession(session.id);
                          }}
                            aria-label={`删除对话：${session.title}`}
                            className="rounded-lg p-1.5 opacity-0 transition-all hover:bg-red-50 hover:text-red-500 group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-200"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    );
                  })
                )}
              </div>

              <div className="mt-3 border-t border-stone-200/60 pt-3">
                <button
                  onClick={handleBack}
                    className="flex h-10 w-full items-center gap-2 rounded-xl px-3 text-[13px] text-stone-500 transition-colors hover:bg-white/70 hover:text-stone-800"
                >
                  {onClose ? (
                    <>
                      <X className="h-3.5 w-3.5" />
                      返回掌柜台
                    </>
                  ) : (
                    <>
                      <ArrowLeft className="h-3.5 w-3.5" />
                      返回掌柜台
                    </>
                  )}
                </button>
              </div>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col bg-[#fbfaf8]">
        <header className="flex min-h-[76px] shrink-0 items-center gap-3 border-b border-stone-200/60 bg-white/82 px-5 backdrop-blur-2xl">
          {variant === "modal" && (
            <button
              onClick={handleBack}
              aria-label="关闭对话"
              className="rounded-xl p-2 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label={sidebarOpen ? "收起历史对话" : "展开历史对话"}
            className="rounded-xl p-2 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-octo-200"
          >
            {sidebarOpen ? (
              <ChevronLeft className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>

          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[15px] bg-gradient-to-br from-[#d64d17] to-[#ef6a24] text-white shadow-[0_7px_18px_rgba(197,71,20,0.20)]">
              <Sparkles className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <p className="truncate text-[15px] font-semibold tracking-[-0.01em] text-stone-900">
                {activeSession?.title || "掌柜对话"}
              </p>
              <p className={cn(
                "mt-0.5 flex items-center gap-1.5 truncate text-[11px]",
                runtimeStatus && !runtimeStatus.active ? "text-amber-700" : "text-stone-500"
              )}>
                <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", runtimeStatus?.active ? "bg-emerald-500" : "bg-amber-500")} />
                {storeIdentity.name} · {runtimeStatus?.active
                  ? runtimeStatus.label
                  : runtimeStatus
                    ? `${runtimeStatus.label} · 当前使用${runtimeStatus.fallback || "掌柜可信运行时"}`
                    : "正在确认 Agent 运行状态"}
              </p>
            </div>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={createNewSession}
              className="inline-flex h-10 items-center gap-1.5 rounded-2xl border border-stone-200 bg-white/80 px-3.5 text-xs font-semibold text-stone-600 shadow-sm transition-[transform,border-color,color,box-shadow] duration-200 hover:-translate-y-0.5 hover:border-octo-200 hover:text-octo-700 hover:shadow-md"
            >
              <Plus className="h-3.5 w-3.5" />
              新对话
            </button>
          </div>
        </header>

        <div className="relative min-h-0 flex-1 overflow-y-auto bg-[radial-gradient(circle_at_50%_0%,rgba(255,255,255,0.98),rgba(250,246,239,0.72)_42%,rgba(247,243,237,0.92)_100%)] scroll-smooth">
          <div className="pointer-events-none absolute inset-x-[12%] top-0 h-32 rounded-full bg-white/70 blur-3xl" />
          <div className="relative mx-auto w-full max-w-[880px] px-7 py-8 xl:px-10 xl:py-10">
            {messages.length === 0 ? (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
                className="flex min-h-[420px] flex-col items-center justify-center py-16 text-center"
              >
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-octo-400 to-octo-600 text-white shadow-lg shadow-octo-200/50">
                  <Sparkles className="h-7 w-7" />
                </div>
                <h2 className="mt-5 text-xl font-semibold text-stone-900">你好，老板</h2>
                <p className="mt-2 max-w-[440px] text-sm leading-6 text-stone-500">
                  经营问题直接告诉我；账单、截图和库存照片统一进入资料与待确认。
                </p>
                <div className="mt-6 grid w-full max-w-[520px] grid-cols-1 gap-2 sm:grid-cols-2">
                  {[
                    "今天营业截图帮我看看",
                    "外卖单变少了怎么办",
                    "章鱼粉快没了要补多少",
                    "下周排班怎么排合理",
                  ].map((prompt, i) => (
                    <button
                      key={i}
                      onClick={() => setInput(prompt)}
                      className="rounded-xl border border-stone-200 bg-white/80 px-3 py-2.5 text-left text-[13px] text-stone-700 transition-all hover:border-octo-200 hover:bg-octo-50/50 hover:text-octo-800"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </motion.div>
            ) : (
              <div className="space-y-5">
                {messages.map((message) => (
                  <ChatMessage
                    key={message.id}
                    role={message.role}
                    content={message.content}
                    timestamp={formatTime(message.timestamp)}
                    run={message.run}
                  />
                ))}
                {chatError && (
                  <p role="alert" className="text-center text-xs text-red-600">
                    {chatError}
                  </p>
                )}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        <div className="shrink-0 border-t border-stone-200/60 bg-white/76 px-6 py-4 backdrop-blur-2xl">
          <div className="mx-auto w-full max-w-[880px]">
            <form
              onSubmit={handleSubmit}
              className="rounded-[24px] border border-stone-200/90 bg-white/95 shadow-[0_14px_38px_rgba(68,48,36,0.09)] transition-[border-color,box-shadow,transform] duration-200 ease-out focus-within:-translate-y-0.5 focus-within:border-octo-200 focus-within:shadow-[0_18px_48px_rgba(68,48,36,0.13),0_0_0_3px_rgba(234,88,12,0.07)]"
            >
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="问经营问题，或描述今天发生的事…"
                rows={1}
                className="max-h-40 min-h-[54px] w-full resize-none bg-transparent px-5 py-4 text-[15px] leading-6 text-stone-900 outline-none placeholder:text-stone-400"
              />
              <div className="flex items-center justify-between gap-2 px-3.5 pb-3">
                <div className="flex items-center">
                  <button
                    type="button"
                    onClick={() => router.push("/capture")}
                    className="inline-flex h-9 items-center gap-1.5 rounded-xl px-2.5 text-xs font-medium text-stone-500 transition-colors hover:bg-stone-100 hover:text-stone-800"
                  >
                    <Upload className="h-3.5 w-3.5" />
                    <span>录入资料</span>
                  </button>
                </div>
                <button
                  type="submit"
                  disabled={!input.trim() || isStreaming}
                  className="inline-flex h-10 items-center gap-1.5 rounded-[14px] bg-[#d4511c] px-4 text-xs font-semibold text-white shadow-[0_6px_16px_rgba(196,65,12,0.18)] transition-[transform,background-color,box-shadow] duration-200 hover:-translate-y-0.5 hover:bg-[#bd4314] hover:shadow-[0_9px_20px_rgba(196,65,12,0.24)] disabled:cursor-not-allowed disabled:bg-stone-200 disabled:text-stone-400 disabled:shadow-none"
                >
                  {isStreaming ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Send className="h-3.5 w-3.5" />
                  )}
                  交给掌柜
                </button>
              </div>
            </form>
            <p className="mt-2.5 text-center text-[10px] text-stone-400">
              AI 给出的建议仅供参考，重要决策请结合实际情况判断
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
