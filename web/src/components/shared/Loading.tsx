"use client";

import { cn } from "@/lib/utils";

export function LoadingSpinner({
  size = "md",
  className,
}: {
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const sizes = {
    sm: "w-4 h-4",
    md: "w-8 h-8",
    lg: "w-12 h-12",
  };

  return (
    <div className={cn("flex items-center justify-center", className)}>
      <div className={cn(
        "relative",
        sizes[size]
      )}>
        {/* 外圈 */}
        <div className="absolute inset-0 rounded-full border-2 border-primary/20" />
        {/* 旋转圈 */}
        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-primary animate-spin" />
      </div>
    </div>
  );
}

export function Skeleton({
  className,
  variant = "rect",
}: {
  className?: string;
  variant?: "rect" | "circle" | "text";
}) {
  const variants = {
    rect: "rounded-lg",
    circle: "rounded-full",
    text: "rounded h-4",
  };

  return (
    <div
      className={cn(
        "bg-gradient-to-r from-surface-container via-surface-container-high to-surface-container bg-[length:200%_100%] animate-shimmer",
        variants[variant],
        className
      )}
    />
  );
}

export function MetricCardSkeleton() {
  return (
    <div className="glass-card rounded-xl p-4 space-y-3">
      <Skeleton variant="text" className="w-20" />
      <Skeleton variant="text" className="w-24 h-6" />
    </div>
  );
}

export function ChartSkeleton() {
  return (
    <div className="glass-card rounded-xl p-4 space-y-4">
      <Skeleton variant="text" className="w-32" />
      <Skeleton variant="rect" className="w-full h-48" />
    </div>
  );
}

export function ChatMessageSkeleton() {
  return (
    <div className="flex gap-3">
      <Skeleton variant="circle" className="w-8 h-8 flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <Skeleton variant="rect" className="w-3/4 h-20" />
      </div>
    </div>
  );
}

export function RiskCardSkeleton() {
  return (
    <div className="glass-card rounded-xl p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 space-y-2">
          <Skeleton variant="text" className="w-16 h-5" />
          <Skeleton variant="text" className="w-3/4 h-5" />
        </div>
        <Skeleton variant="circle" className="w-8 h-8" />
      </div>
      <Skeleton variant="text" className="w-full h-4" />
      <Skeleton variant="text" className="w-full h-4" />
      <Skeleton variant="text" className="w-2/3 h-4" />
    </div>
  );
}