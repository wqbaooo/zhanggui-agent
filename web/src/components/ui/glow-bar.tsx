"use client";

interface GlowBarProps {
  value: number;
  max?: number;
  className?: string;
  color?: string;
}

export function GlowBar({ value, max = 100, className, color }: GlowBarProps) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const bg = color || "linear-gradient(90deg, var(--color-octo-500), var(--color-sauce-500), var(--color-octo-500))";
  return (
    <div className={`h-2 w-full overflow-hidden rounded-full bg-stone-200/60 ${className || ""}`}>
      <div
        className="relative h-full rounded-full"
        style={{
          width: `${pct}%`,
          background: bg,
          backgroundSize: "200% 100%",
          animation: "glow-slide 1.6s linear infinite",
          transition: "width 500ms cubic-bezier(0.16, 1, 0.3, 1)",
        }}
      />
      <style>{`@keyframes glow-slide{0%{background-position:200% 0}100%{background-position:-200% 0}}`}</style>
    </div>
  );
}
