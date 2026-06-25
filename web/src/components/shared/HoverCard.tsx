"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface HoverCardProps {
  children: React.ReactNode;
  className?: string;
  scale?: number;
  lift?: number;
}

export function HoverCard({
  children,
  className,
  scale = 1.02,
  lift = 4,
}: HoverCardProps) {
  return (
    <motion.div
      whileHover={{
        scale,
        y: -lift,
        transition: {
          type: "spring",
          stiffness: 400,
          damping: 25,
        },
      }}
      whileTap={{ scale: 0.98 }}
      className={cn("cursor-pointer", className)}
    >
      {children}
    </motion.div>
  );
}

export function PulseIndicator({
  status,
  size = "md",
  className,
}: {
  status: "success" | "warning" | "error" | "info";
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const colors = {
    success: "bg-emerald-500",
    warning: "bg-amber-500",
    error: "bg-red-500",
    info: "bg-blue-500",
  };

  const sizes = {
    sm: "w-2 h-2",
    md: "w-3 h-3",
    lg: "w-4 h-4",
  };

  return (
    <div className={cn("relative inline-flex", className)}>
      <span className={cn(
        "absolute inset-0 rounded-full animate-ping opacity-75",
        colors[status]
      )} />
      <span className={cn(
        "relative rounded-full",
        colors[status],
        sizes[size]
      )} />
    </div>
  );
}

export function ShimmerCard({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("glass-card rounded-xl p-4 overflow-hidden relative", className)}>
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent animate-shimmer pointer-events-none" />
      <div className="relative z-10">
        {children}
      </div>
    </div>
  );
}