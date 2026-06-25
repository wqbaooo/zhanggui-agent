"use client";

import { cn } from "@/lib/utils";

export function RiskCard({
  title,
  level,
  status,
  description,
  impact,
  recommendation,
  onClick,
}: {
  title: string;
  level: "low" | "medium" | "high" | "critical";
  status: "active" | "resolved" | "ignored";
  description: string;
  impact: string;
  recommendation: string;
  onClick?: () => void;
}) {
  const levelConfig = {
    low: {
      bg: "bg-emerald-50",
      border: "border-emerald-200",
      text: "text-emerald-700",
      label: "低",
    },
    medium: {
      bg: "bg-amber-50",
      border: "border-amber-200",
      text: "text-amber-700",
      label: "中",
    },
    high: {
      bg: "bg-orange-50",
      border: "border-orange-200",
      text: "text-orange-700",
      label: "高",
    },
    critical: {
      bg: "bg-red-50",
      border: "border-red-200",
      text: "text-red-700",
      label: "极高",
    },
  };

  const config = levelConfig[level];

  const statusConfig = {
    active: { label: "待处理", color: "text-red-600" },
    resolved: { label: "已解决", color: "text-emerald-600" },
    ignored: { label: "已忽略", color: "text-on-surface-variant" },
  };

  const statusInfo = statusConfig[status];

  return (
    <div
      onClick={onClick}
      className={cn(
        "glass-card rounded-xl p-4 cursor-pointer",
        "hover:scale-[1.02] transition-all duration-300",
        "group relative overflow-hidden"
      )}
    >
      {/* 背景光效 */}
      <div className={cn(
        "absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500",
        config.bg
      )} />

      <div className="relative z-10 space-y-3">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className={cn(
                "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold",
                config.bg, config.text, config.border, "border"
              )}>
                {config.label}
              </span>
              <span className={cn("text-xs", statusInfo.color)}>
                {statusInfo.label}
              </span>
            </div>
            <h3 className="font-semibold text-on-background text-base leading-tight">
              {title}
            </h3>
          </div>
          <div className={cn(
            "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
            config.bg, "transition-transform duration-300 group-hover:scale-110"
          )}>
            <span className={cn("text-lg", config.text)}>⚠️</span>
          </div>
        </div>

        {/* Description */}
        <p className="text-sm text-on-surface-variant leading-relaxed">
          {description}
        </p>

        {/* Impact */}
        <div className="pt-2 border-t border-muted-border/20">
          <p className="text-xs font-label-caps text-on-surface-variant mb-1">
            影响
          </p>
          <p className="text-sm text-on-background">{impact}</p>
        </div>

        {/* Recommendation */}
        <div className="pt-2 border-t border-muted-border/20">
          <p className="text-xs font-label-caps text-on-surface-variant mb-1">
            建议
          </p>
          <p className="text-sm text-on-background">{recommendation}</p>
        </div>
      </div>

      {/* 底部装饰线 */}
      <div className={cn(
        "absolute bottom-0 left-0 right-0 h-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-500",
        "bg-gradient-to-r from-transparent to-transparent",
        level === "critical" && "via-red-400",
        level === "high" && "via-orange-400",
        level === "medium" && "via-amber-400",
        level === "low" && "via-emerald-400"
      )} />
    </div>
  );
}
