"use client";

import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

interface AnimatedButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  children: React.ReactNode;
}

export function AnimatedButton({
  variant = "primary",
  size = "md",
  loading = false,
  children,
  className,
  disabled,
  ...props
}: AnimatedButtonProps) {
  const variants = {
    primary: "bg-primary text-on-primary hover:bg-primary/90 active:bg-primary/80",
    secondary: "bg-surface text-on-surface hover:bg-surface-container-high active:bg-surface-container",
    ghost: "bg-transparent text-on-surface-variant hover:bg-surface-container-high active:bg-surface-container",
    danger: "bg-error text-on-error hover:bg-error/90 active:bg-error/80",
  };

  const sizes = {
    sm: "px-3 py-1.5 text-xs",
    md: "px-4 py-2 text-sm",
    lg: "px-6 py-3 text-base",
  };

  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium",
        "transition-all duration-300 ease-out",
        "transform hover:scale-[1.02] active:scale-[0.98]",
        "disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none",
        "relative overflow-hidden group",
        variants[variant],
        sizes[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {/* 背景光效 */}
      <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/20 to-white/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700" />

      <div className="relative z-10 flex items-center gap-2">
        {loading && <Loader2 className="w-4 h-4 animate-spin" />}
        {children}
      </div>
    </button>
  );
}

// 图标按钮
export function IconButton({
  icon,
  label,
  onClick,
  variant = "ghost",
  size = "md",
  className,
}: {
  icon: React.ReactNode;
  label?: string;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const variants = {
    primary: "bg-primary text-on-primary hover:bg-primary/90",
    secondary: "bg-surface text-on-surface hover:bg-surface-container-high",
    ghost: "bg-transparent text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface",
  };

  const sizes = {
    sm: "w-8 h-8",
    md: "w-10 h-10",
    lg: "w-12 h-12",
  };

  return (
    <button
      onClick={onClick}
      aria-label={label}
      className={cn(
        "inline-flex items-center justify-center rounded-lg",
        "transition-all duration-300 ease-out",
        "transform hover:scale-110 active:scale-95",
        variants[variant],
        sizes[size],
        className
      )}
    >
      {icon}
    </button>
  );
}