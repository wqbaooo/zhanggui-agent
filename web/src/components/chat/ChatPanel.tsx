"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  Camera,
  ChevronLeft,
  ChevronRight,
  Loader2,
  MessageSquarePlus,
  Mic,
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
      : "h-[calc(100vh-3.5rem)] -mx-4 -my-4 md:-mx-6 md:-my-6";

  return (
    <div className={cn("flex overflow-hidden", containerClass)}>
      <AnimatePresence initial={false}>
        {sidebarOpen && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 260, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="shrink-0 border-r border-stone-200/80 bg-[#FAF7F2]/80 backdrop-blur-xl overflow-hidden"
          >
            <div className="flex h-full flex-col p-3">
              <button
                onClick={createNewSession}
                className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-octo-500 to-octo-600 px-3 py-2.5 text-sm font-semibold text-white shadow-sm shadow-octo-200/60 transition-all hover:shadow-md hover:shadow-octo-200"
              >
                <Plus className="h-4 w-4" />
                新建对话
              </button>

              <div className="mt-4 flex-1 space-y-0.5 overflow-y-auto pr-1">
                {sessions.length === 0 ? (
                  <p className="px-3 py-4 text-xs text-stone-400">还没有对话记录</p>
                ) : (
                  sessions.map((session) => {
                    const isActive = session.id === activeSessionId;
                    return (
                      <div
                        key={session.id}
                        className={cn(
                          "group relative flex items-center gap-2 rounded-xl px-2.5 py-2 cursor-pointer transition-all",
                          isActive
                            ? "bg-octo-50 text-octo-700"
                            : "text-stone-600 hover:bg-stone-100/70"
                        )}
                        onClick={() => setActiveSession(session.id)}
                      >
                        {isActive && (
                          <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-octo-500" />
                        )}
                        <MessageSquarePlus
                          className={cn(
                            "h-3.5 w-3.5 shrink-0",
                            isActive ? "text-octo-500" : "text-stone-400"
                          )}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[13px] font-medium">{session.title}</p>
                          <p className="truncate text-[10px] text-stone-400">
                            {formatDate(session.updatedAt)} · {formatTime(session.updatedAt)}
                          </p>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteSession(session.id);
                          }}
                          className="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-red-50 hover:text-red-500 transition-all"
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
                  className="flex items-center gap-2 rounded-xl px-2.5 py-2 text-[13px] text-stone-500 transition-colors hover:bg-stone-100/70 hover:text-stone-700 w-full"
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

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-stone-200/60 bg-white/60 px-4 py-3 backdrop-blur-xl">
          {variant === "modal" && (
            <button
              onClick={handleBack}
              className="rounded-lg p-1.5 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-600"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="rounded-lg p-1.5 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-600"
          >
            {sidebarOpen ? (
              <ChevronLeft className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>

          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-octo-500 to-octo-600 text-white shadow-sm">
              <Sparkles className="h-4 w-4" />
            </span>
            <div>
              <p className="text-sm font-semibold text-stone-900">
                {activeSession?.title || "掌柜对话"}
              </p>
              <p className="text-[10px] text-stone-500">
                {storeIdentity.name} · 结合经营档案分析
              </p>
            </div>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={createNewSession}
              className="inline-flex items-center gap-1.5 rounded-full border border-stone-200 bg-white/80 px-3 py-1.5 text-xs font-medium text-stone-600 transition-colors hover:border-octo-200 hover:text-octo-700"
            >
              <Plus className="h-3.5 w-3.5" />
              新对话
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto bg-gradient-to-b from-[#fffdf8] via-[#fefaf3] to-[#fdf6ea]">
          <div className="mx-auto w-full max-w-[720px] px-4 py-6">
            {messages.length === 0 ? (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
                className="flex flex-col items-center justify-center py-16 text-center"
              >
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-octo-400 to-octo-600 text-white shadow-lg shadow-octo-200/50">
                  <Sparkles className="h-7 w-7" />
                </div>
                <h2 className="mt-5 text-xl font-semibold text-stone-900">你好，老板</h2>
                <p className="mt-2 max-w-[440px] text-sm leading-6 text-stone-500">
                  把经营问题、截图、单据、库存、员工情况发给我，我结合这家店的经营档案帮你分析和安排。
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

        <div className="border-t border-stone-200/60 bg-white/80 px-4 py-3 backdrop-blur-xl">
          <div className="mx-auto w-full max-w-[720px]">
            <form
              onSubmit={handleSubmit}
              className="rounded-[1.4rem] border border-stone-200 bg-white shadow-[0_12px_40px_rgba(120,88,55,0.12)]"
            >
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="问经营问题、安排任务，或直接发文字和资料…"
                rows={1}
                className="max-h-40 min-h-[52px] w-full resize-none bg-transparent px-4 py-3.5 text-sm leading-6 text-stone-900 outline-none placeholder:text-stone-400"
              />
              <div className="flex items-center justify-between gap-2 px-3 pb-2.5">
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    className="inline-flex h-9 items-center gap-1.5 rounded-full px-2.5 text-xs text-stone-500 transition-colors hover:bg-stone-100 hover:text-stone-700"
                  >
                    <Upload className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">文件</span>
                  </button>
                  <button
                    type="button"
                    className="inline-flex h-9 items-center gap-1.5 rounded-full px-2.5 text-xs text-stone-500 transition-colors hover:bg-stone-100 hover:text-stone-700"
                  >
                    <Camera className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">拍照</span>
                  </button>
                  <button
                    type="button"
                    className="inline-flex h-9 items-center gap-1.5 rounded-full px-2.5 text-xs text-stone-500 transition-colors hover:bg-stone-100 hover:text-stone-700"
                  >
                    <Mic className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">语音</span>
                  </button>
                </div>
                <button
                  type="submit"
                  disabled={!input.trim() || isStreaming}
                  className="inline-flex h-9 items-center gap-1.5 rounded-full bg-octo-500 px-4 text-xs font-semibold text-white shadow-sm shadow-octo-200/60 transition-all hover:bg-octo-600 disabled:cursor-not-allowed disabled:bg-stone-200 disabled:text-stone-400 disabled:shadow-none"
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
            <p className="mt-2 text-center text-[10px] text-stone-400">
              AI 给出的建议仅供参考，重要决策请结合实际情况判断
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
