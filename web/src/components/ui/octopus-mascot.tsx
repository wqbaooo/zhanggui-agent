interface OctopusMascotProps {
  size?: number;
  className?: string;
  variant?: "wave" | "think" | "alert";
}

export function OctopusMascot({ size = 48, className, variant = "wave" }: OctopusMascotProps) {
  const eyeOffset = variant === "alert" ? 0 : variant === "think" ? 1 : 0;
  const mouthPath = variant === "alert" ? "M30 40 Q36 36 42 40" : variant === "think" ? "M32 40 L40 40" : "M30 39 Q36 43 42 39";

  return (
    <svg width={size} height={size} viewBox="0 0 72 72" fill="none" className={className} aria-hidden="true">
      <defs>
        <radialGradient id="octo-body" cx="0.4" cy="0.3" r="0.7">
          <stop offset="0%" stopColor="#ff8235" />
          <stop offset="100%" stopColor="#e85d04" />
        </radialGradient>
      </defs>
      <ellipse cx="36" cy="34" rx="22" ry="20" fill="url(#octo-body)" />
      <path d="M16 38 Q12 50 16 56 Q18 52 20 50 Q18 46 22 42 Z" fill="url(#octo-body)" />
      <path d="M24 46 Q20 56 24 62 Q26 58 28 56 Q26 52 30 48 Z" fill="url(#octo-body)" />
      <path d="M36 48 Q32 60 36 64 Q40 60 36 48 Z" fill="url(#octo-body)" />
      <path d="M48 46 Q52 56 48 62 Q46 58 44 56 Q46 52 42 48 Z" fill="url(#octo-body)" />
      <path d="M56 38 Q60 50 56 56 Q54 52 52 50 Q54 46 50 42 Z" fill="url(#octo-body)" />
      <circle cx="28" cy="30" r="4" fill="#fff" />
      <circle cx="44" cy="30" r="4" fill="#fff" />
      <circle cx={28 + eyeOffset} cy="30" r="2" fill="#1c1917" />
      <circle cx={44 + eyeOffset} cy="30" r="2" fill="#1c1917" />
      <path d={mouthPath} stroke="#1c1917" strokeWidth="1.5" strokeLinecap="round" fill="none" />
      {variant === "wave" && <circle cx="58" cy="22" r="3" fill="#fff" opacity="0.8" />}
    </svg>
  );
}
