"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export function MetricCard({
  label, value, trend, trendLabel, negative, onClick,
}: {
  label: string;
  value: string;
  trend?: "up" | "down" | "flat";
  trendLabel?: string;
  negative?: boolean;
  onClick?: () => void;
}) {
  const [displayValue, setDisplayValue] = useState(value);
  const [isAnimating, setIsAnimating] = useState(false);
  const prevValue = useRef(value);
  const cardRef = useRef<HTMLElement | null>(null);
  const setCardNode = (node: HTMLElement | null) => {
    cardRef.current = node;
  };

  // 数字变化动画
  useEffect(() => {
    if (prevValue.current !== value) {
      setIsAnimating(true);
      const timeout = setTimeout(() => {
        setDisplayValue(value);
        setIsAnimating(false);
        prevValue.current = value;
      }, 300);
      return () => clearTimeout(timeout);
    }
  }, [value]);

  // 鼠标跟随光效
  useEffect(() => {
    const card = cardRef.current;
    if (!card) return;

    const handleMouseMove = (event: Event) => {
      const e = event as MouseEvent;
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      card.style.setProperty("--mouse-x", `${x}px`);
      card.style.setProperty("--mouse-y", `${y}px`);
    };

    card.addEventListener("mousemove", handleMouseMove);
    return () => card.removeEventListener("mousemove", handleMouseMove);
  }, []);

  const className = cn(
    "glass-card rounded-xl p-4 text-left hover:border-primary/30 transition-all interactive-card",
    "relative overflow-hidden group"
  );

  const content = (
    <>
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
      <div className="relative z-10">
        <p className="font-label-caps text-on-surface-variant">{label}</p>
        <div className="flex items-baseline gap-2 mt-2">
          <span
            className={cn(
              "font-headline-lg transition-all duration-300",
              negative ? "text-error" : "text-on-background",
              isAnimating && "scale-105"
            )}
          >
            {displayValue}
          </span>
          {trend && trend !== "flat" && (
            <span
              className={cn(
                "text-[10px] font-semibold inline-flex items-center gap-0.5",
                trend === "up" ? (negative ? "text-error" : "text-emerald-700") : (negative ? "text-emerald-700" : "text-error")
              )}
            >
              <span className={cn(
                "inline-block transition-transform duration-300",
                trend === "up" ? "translate-y-[-1px]" : "translate-y-[1px]"
              )}>
                {trend === "up" ? "↗" : "↘"}
              </span>
              {trendLabel}
            </span>
          )}
        </div>
      </div>
      <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-primary/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
    </>
  );

  if (onClick) {
    return (
      <button ref={setCardNode} onClick={onClick} className={className}>
        {content}
      </button>
    );
  }

  return (
    <div ref={setCardNode} className={className}>
      {content}
    </div>
  );
}
