export function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-1.5 border-b border-muted-border/30 last:border-0">
      <span className="text-on-surface-variant text-xs">{label}</span>
      <span className="text-on-background font-medium text-xs">{value}</span>
    </div>
  );
}

export function Clause({ label, value, warn }: { label: string; value: string; warn: boolean }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-muted-border/30 last:border-0">
      <span className="text-on-surface-variant text-xs">{label}</span>
      <span className={warn ? "text-error font-medium text-xs" : "text-on-background text-xs"}>
        {warn && <span className="mr-1">⚠</span>}
        {value}
      </span>
    </div>
  );
}

export function Tag({ label }: { label: string }) {
  return (
    <span className="rounded-full border border-muted-border bg-surface-container-high/60 px-2.5 py-1 text-[10px] text-on-surface-variant font-mono">
      {label}
    </span>
  );
}
