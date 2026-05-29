"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type CardBg = "cream" | "green" | "red" | "mint" | "black" | "cream-2";

interface BentoCardProps {
  children: ReactNode;
  className?: string;
  bg?: CardBg;
  interactive?: boolean;
  onClick?: () => void;
}

const BG: Record<CardBg, string> = {
  cream: "bg-[#F5EFE3] text-[#0A0A0A]",
  green: "bg-[#0F4C3A] text-[#F5EFE3]",
  red: "bg-[#D9261C] text-[#F5EFE3]",
  mint: "bg-[#7FE05A] text-[#0A0A0A]",
  black: "bg-[#0A0A0A] text-[#F5EFE3]",
  "cream-2": "bg-[#EDE4D2] text-[#0A0A0A]",
};

export function BentoCard({
  children,
  className,
  bg = "cream",
  interactive = false,
  onClick,
}: BentoCardProps) {
  const cls = cn(
    "rounded-[20px] p-[18px] overflow-hidden transition-transform duration-150",
    BG[bg],
    interactive && "cursor-pointer select-none hover:-translate-y-px active:scale-[0.985]",
    className
  );

  if (onClick) {
    return (
      <div
        role="button"
        tabIndex={0}
        className={cls}
        onClick={onClick}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onClick();
          }
        }}
      >
        {children}
      </div>
    );
  }

  return <div className={cls}>{children}</div>;
}

export function MonoTag({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={cn("mono-tag opacity-60", className)}>
      {children}
    </span>
  );
}

export function MonoMeta({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={cn("mono-meta opacity-40", className)}>
      {children}
    </span>
  );
}

export function Divider({ className }: { className?: string }) {
  return <div className={cn("divider-black", className)} />;
}

export function Pill({
  children,
  className,
  variant = "default",
}: {
  children: ReactNode;
  className?: string;
  variant?: "default" | "mint" | "red" | "green";
}) {
  const bg = {
    default: "bg-[#0A0A0A] text-[#F5EFE3]",
    mint: "bg-[#7FE05A] text-[#0A0A0A]",
    red: "bg-[#D9261C] text-[#F5EFE3]",
    green: "bg-[#0F4C3A] text-[#F5EFE3]",
  }[variant];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 mono-tag",
        bg,
        className
      )}
    >
      {children}
    </span>
  );
}

export function IllustrationBox({
  label,
  className,
}: {
  label: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-center rounded-xl border-2 border-dashed border-current/20 mono-meta opacity-40",
        className
      )}
    >
      [ {label} ]
    </div>
  );
}
