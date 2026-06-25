"use client";

import { useState } from "react";
import type { RiskLevel } from "@/domain/types";
import { useProjectData } from "@/lib/hooks/useProjectData";
import { RISK_BADGE } from "@/components/shared/badges";
import { AnimateIn, StaggerList } from "@/components/shared";

export function RisksView({ initialFilter = "all" }: { initialFilter?: RiskLevel | "all" }) {
  const { risks } = useProjectData();
  const [filter, setFilter] = useState<RiskLevel | "all">(initialFilter);
  const filtered = filter === "all" ? risks : risks.filter(r => r.severity === filter);

  return (
    <div className="h-full flex flex-col gap-3">
      <AnimateIn direction="up">
        <div className="flex items-center gap-3 shrink-0">
          <h2 className="font-headline-lg text-on-background">风险清单</h2>
          <span className="font-label-caps text-on-surface-variant">共 {risks.length} 条</span>
        </div>
      </AnimateIn>

      <AnimateIn delay={100} direction="up" className="flex-1 glass-card rounded-xl p-4 interactive-card flex flex-col min-h-0">
        <div className="flex gap-1 mb-3 shrink-0 relative z-10 overflow-x-auto">
          {(["all", "critical", "high", "medium", "low"] as const).map(l => (
            <button key={l} onClick={() => setFilter(l)} className={`px-2 py-1 rounded-md text-[10px] font-mono whitespace-nowrap transition-all hover:scale-105 ${filter === l ? "bg-agent-gold/20 text-agent-gold border border-agent-gold/30" : "text-on-surface-variant hover:text-on-background hover:bg-surface-container-high/40"}`}>
              {l === "all" ? "全部" : RISK_BADGE[l].label}
              {l !== "all" && <span className="ml-1 text-[8px] opacity-60">{risks.filter(r => r.severity === l).length}</span>}
            </button>
          ))}
        </div>

        <StaggerList staggerDelay={60} className="flex-1 overflow-y-auto relative z-10 min-h-0 pr-1 space-y-2">
          {filtered.map((r, index) => {
            const rb = RISK_BADGE[r.severity];
            return (
              <div key={`${r.id}-${index}`} className="p-3 rounded-lg bg-surface-container-high/30 border border-muted-border/20 hover:border-agent-gold/20 transition-all hover:scale-[1.01] hover:shadow-sm">
                <div className="flex items-start gap-2 mb-1">
                  <span className={`size-1.5 rounded-full shrink-0 mt-1.5 ${r.severity === "critical" || r.severity === "high" ? "bg-error" : r.severity === "medium" ? "bg-amber-500" : "bg-emerald-500"}`} />
                  <span className="text-xs font-medium text-on-background">{r.name}</span>
                  <span className={`ml-auto text-[8px] font-mono px-1.5 py-0.5 rounded ${rb.bg} ${rb.text}`}>{rb.label}</span>
                </div>
                <p className="text-[10px] text-on-surface-variant/60 ml-3.5">{r.evidence}</p>
                <p className="text-[10px] text-on-background ml-3.5 mt-0.5 font-medium">→ {r.suggestedAction}</p>
                <div className="ml-3.5 mt-1">
                  <span className={`text-[8px] font-mono px-1 py-0.5 rounded ${r.status === "verified" ? "bg-emerald-500/15 text-emerald-700" : r.status === "unverified" ? "bg-amber-500/15 text-amber-700" : "bg-surface-container-high/70 text-on-surface-variant"}`}>
                    {r.status === "verified" ? "已验证" : r.status === "unverified" ? "待验证" : r.status === "resolved" ? "已解决" : "暂缓"}
                  </span>
                </div>
              </div>
            );
          })}
        </StaggerList>
      </AnimateIn>
    </div>
  );
}
