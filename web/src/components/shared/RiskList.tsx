import { RISK_BADGE } from "@/components/shared/badges";
import type { RiskItem } from "@/domain/types";

export function RiskList({ risks, title }: { risks: RiskItem[]; title?: string }) {
  if (risks.length === 0) return null;

  return (
    <div className="glass-card rounded-xl p-5 interactive-card">
      {title && <p className="font-label-caps text-on-surface-variant mb-3">{title} · {risks.length}</p>}
      <div className="space-y-3">
        {risks.map((r) => {
          const rb = RISK_BADGE[r.severity];
          return (
            <div key={r.id} className="rounded-lg border border-muted-border/40 bg-surface-container-high/30 p-3 hover:border-agent-gold/20 transition-all">
              <div className="flex items-start gap-2 mb-1.5">
                <span className={`mt-0.5 size-1.5 rounded-full ${r.severity === "critical" || r.severity === "high" ? "bg-error" : r.severity === "medium" ? "bg-amber-500" : "bg-emerald-500"}`} />
                <span className="text-xs font-medium text-on-background">{r.name}</span>
                <span className={`ml-auto text-[9px] font-mono px-1.5 py-0.5 rounded-full ${rb.bg} ${rb.text}`}>{rb.label}</span>
              </div>
              <p className="text-[11px] text-on-surface-variant ml-4">{r.evidence}</p>
              <p className="text-[11px] text-on-background ml-4 mt-0.5 font-medium">→ {r.suggestedAction}</p>
              <div className="flex items-center gap-2 ml-4 mt-1.5">
                <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded-full ${r.status === "verified" ? "bg-emerald-500/15 text-emerald-700" : r.status === "unverified" ? "bg-amber-500/15 text-amber-700" : "bg-surface-container-high/70 text-on-surface-variant"}`}>
                  {r.status === "verified" ? "已验证" : r.status === "unverified" ? "待验证" : r.status === "resolved" ? "已解决" : "暂缓"}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
