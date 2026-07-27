"use client";

import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

const markdownComponents: Components = {
  h1: ({ children }) => (
    <h1 className="mb-2 mt-4 text-lg font-semibold tracking-[-0.01em] text-stone-900 first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-2 mt-4 text-base font-semibold tracking-[-0.01em] text-stone-900 first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1.5 mt-3 text-[15px] font-semibold text-stone-900 first:mt-0">
      {children}
    </h3>
  ),
  p: ({ children }) => (
    <p className="my-2 leading-7 text-stone-700 first:mt-0 last:mb-0">{children}</p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-stone-900">{children}</strong>
  ),
  ul: ({ children }) => (
    <ul className="my-2.5 list-disc space-y-1.5 pl-5 text-stone-700 marker:text-octo-400">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-2.5 list-decimal space-y-1.5 pl-5 text-stone-700 marker:font-semibold marker:text-octo-500">{children}</ol>
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
        "flex items-start gap-3.5",
          isUser ? "justify-end" : "justify-start"
        )}
      >
      {!isUser && (
        <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-[14px] bg-gradient-to-br from-[#d64d17] to-[#ef6a24] text-sm font-semibold text-white shadow-[0_7px_18px_rgba(196,65,12,0.18)]">
          掌
        </div>
      )}

      <div
        className={cn(
          "group relative overflow-hidden px-5 py-4 transition-[transform,box-shadow,border-color] duration-200 ease-out",
          isUser
            ? "max-w-[68%] rounded-[22px] rounded-tr-[8px] bg-[#c94b18] text-white shadow-[0_8px_22px_rgba(155,55,18,0.16)] hover:-translate-y-0.5 hover:shadow-[0_12px_28px_rgba(155,55,18,0.20)]"
            : "max-w-[82%] rounded-[24px] rounded-tl-[8px] border border-white/90 bg-white/92 shadow-[0_12px_34px_rgba(67,48,36,0.09)] backdrop-blur-xl hover:border-octo-100 hover:shadow-[0_16px_42px_rgba(67,48,36,0.12)]"
        )}
      >
        <div>
          {isUser ? (
            <p className="whitespace-pre-wrap text-[15px] leading-7 text-white">
              {content}
            </p>
          ) : (
            <div className="text-[15px]">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {content}
              </ReactMarkdown>
            </div>
          )}

          {timestamp && (
            <p className={cn(
              "mt-2.5 text-[11px] tabular-nums",
              isUser ? "text-white/65" : "text-stone-400"
            )}>
              {timestamp}
            </p>
          )}
        </div>

      </div>
    </div>

    {!isUser && run && Boolean(
      run.consulted_modules?.length || run.conflict_count || run.gaps?.length
    ) && (
      <div className="ml-[3.15rem] mt-2 space-y-1.5 rounded-2xl border border-stone-200/70 bg-white/65 px-3.5 py-2.5 text-[11px] leading-5 text-stone-500 backdrop-blur-xl">
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
