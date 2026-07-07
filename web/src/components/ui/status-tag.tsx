import type { ReactNode } from "react";

type StatusType = "success" | "warning" | "danger" | "expiry" | "info" | "neutral";

interface StatusTagProps {
  type: StatusType;
  children: ReactNode;
  emoji?: string | null;
  className?: string;
}

const STATUS_CONFIG: Record<StatusType, { bg: string; border: string; text: string; dot: string; defaultEmoji: string }> = {
  success: { bg: "bg-nori-50", border: "border-nori-200", text: "text-nori-700", dot: "bg-nori-500", defaultEmoji: "✅" },
  warning: { bg: "bg-sauce-50", border: "border-sauce-200", text: "text-sauce-700", dot: "bg-sauce-500", defaultEmoji: "⚠️" },
  danger: { bg: "bg-red-50", border: "border-red-200", text: "text-red-700", dot: "bg-red-500", defaultEmoji: "🔴" },
  expiry: { bg: "bg-octo-50", border: "border-octo-200", text: "text-octo-700", dot: "bg-octo-500", defaultEmoji: "⏰" },
  info: { bg: "bg-sky-50", border: "border-sky-200", text: "text-sky-700", dot: "bg-sky-500", defaultEmoji: "💡" },
  neutral: { bg: "bg-stone-100", border: "border-stone-200", text: "text-stone-600", dot: "bg-stone-400", defaultEmoji: "•" },
};

export function StatusTag({ type, children, emoji, className }: StatusTagProps) {
  const cfg = STATUS_CONFIG[type];
  const icon = emoji !== undefined ? emoji : cfg.defaultEmoji;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${cfg.bg} ${cfg.border} ${cfg.text} ${className || ""}`}>
      {emoji === null ? null : <span className="text-[10px]">{icon}</span>}
      {children}
    </span>
  );
}
