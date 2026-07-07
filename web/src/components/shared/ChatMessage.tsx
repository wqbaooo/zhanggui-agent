"use client";

import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

const markdownComponents: Components = {
  h1: ({ children }) => (
    <h1 className="text-lg font-semibold text-stone-900 mt-4 mb-2 first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-base font-semibold text-stone-900 mt-4 mb-2 first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-[15px] font-semibold text-stone-900 mt-3 mb-1.5 first:mt-0">
      {children}
    </h3>
  ),
  p: ({ children }) => (
    <p className="my-2 leading-7 text-stone-800">{children}</p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-stone-900">{children}</strong>
  ),
  ul: ({ children }) => (
    <ul className="my-2 pl-5 list-disc space-y-1 text-stone-700">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-2 pl-5 list-decimal space-y-1 text-stone-700">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="leading-6">{children}</li>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-octo-400 bg-octo-50/60 rounded-r-lg py-2 px-3 my-2 text-stone-700 italic">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="border-stone-200 my-4" />,
  a: ({ href, children }) => (
    <a href={href} className="text-octo-600 hover:underline" target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
  code: ({ className, children }) => {
    const isInline = !className;
    if (isInline) {
      return (
        <code className="bg-stone-100 text-octo-700 px-1.5 py-0.5 rounded text-xs font-mono">
          {children}
        </code>
      );
    }
    return (
      <code className="block bg-stone-900 text-stone-100 rounded-xl p-3 my-2 text-xs font-mono overflow-x-auto">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="bg-stone-900 text-stone-100 rounded-xl p-3 my-2 text-xs font-mono overflow-x-auto">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto rounded-lg border border-stone-200">
      <table className="w-full text-xs border-collapse">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="bg-stone-100 px-2 py-1.5 text-left font-semibold text-stone-700 border-b border-stone-200">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-2 py-1.5 border-b border-stone-100 text-stone-700">
      {children}
    </td>
  ),
};

export function ChatMessage({
  role,
  content,
  timestamp,
  run,
}: {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
  run?: {
    consulted_modules?: string[];
    conflict_count?: number;
    gaps?: string[];
  };
}) {
  const isUser = role === "user";

  return (
    <div
      className={cn(
        "animate-slide-in",
        isUser ? "animate-slide-in-right" : "animate-slide-in-left"
      )}
    >
      <div
        className={cn(
          "flex gap-3",
          isUser ? "justify-end" : "justify-start"
        )}
      >
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-primary to-agent-gold flex items-center justify-center text-white text-sm font-semibold animate-glow-pulse">
          掌
        </div>
      )}

      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-3 shadow-sm transition-all duration-300",
          "group relative overflow-hidden",
          isUser
            ? "bg-primary text-on-primary hover:shadow-lg"
            : "glass-card hover:shadow-md"
        )}
      >
        {!isUser && (
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
        )}

        <div className="relative z-10">
          {isUser ? (
            <p className="text-sm leading-relaxed whitespace-pre-wrap text-on-primary">
              {content}
            </p>
          ) : (
            <div className="text-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {content}
              </ReactMarkdown>
            </div>
          )}

          {timestamp && (
            <p className={cn(
              "text-xs mt-3 opacity-60",
              isUser ? "text-on-primary" : "text-stone-500"
            )}>
              {timestamp}
            </p>
          )}
        </div>

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

    {!isUser && run && (run.consulted_modules?.length || run.conflict_count || run.gaps?.length) && (
      <div className="ml-11 mt-1.5 space-y-1.5 rounded-2xl border border-stone-200/70 bg-white/60 px-3 py-2 text-[11px] leading-5 text-stone-500 backdrop-blur-sm">
        {run.consulted_modules && run.consulted_modules.length > 0 && (
          <div className="flex flex-wrap items-center gap-1">
            <span className="font-medium text-stone-500">本轮核对：</span>
            {run.consulted_modules.map((module) => (
              <span key={module} className="rounded-full bg-stone-100 px-2 py-0.5 text-stone-600">
                {module}
              </span>
            ))}
          </div>
        )}
        {run.conflict_count && run.conflict_count > 0 && (
          <p className="text-red-600">
            发现 {run.conflict_count} 处数据或采购规则冲突，需核对后再执行。
          </p>
        )}
        {run.gaps && run.gaps.length > 0 && (
          <p className="text-octo-700">
            还缺：{run.gaps.join("；")}
          </p>
        )}
      </div>
    )}
    </div>
  );
}
