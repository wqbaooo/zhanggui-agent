"use client";

import { useState } from "react";
import type { RiskItem, RiskLevel } from "@/domain/types";
import { mockRisks } from "@/data/mockProject";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { SectionHeader } from "@/components/shared/SectionHeader";
import { RiskList } from "@/components/shared/RiskList";
import { RISK_BADGE } from "@/components/shared/badges";

export function RisksView() {
  const risks: RiskItem[] = mockRisks;
  const [filter, setFilter] = useState<RiskLevel | "all">("all");
  const filtered = filter === "all" ? risks : risks.filter(r => r.severity === filter);

  return (
    <div className="space-y-6">
      <SectionHeader title="风险清单" subtitle={`共 ${risks.length} 条风险`} />

      <div className="flex gap-1.5">
        {(["all", "critical", "high", "medium", "low"] as const).map(l => (
          <button key={l} onClick={() => setFilter(l)} className={`rounded-full px-3 py-1 text-[10px] font-mono transition-colors ${filter === l ? "bg-hunter-800 text-cream-50" : "border border-cream-200 text-gray-400 hover:border-hunter-800 hover:text-hunter-800"}`}>
            {l === "all" ? "全部" : RISK_BADGE[l].label}
          </button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{filter === "all" ? "全部风险" : `${RISK_BADGE[filter].label}风险`}</CardTitle>
        </CardHeader>
        <CardContent>
          <RiskList risks={filtered} />
        </CardContent>
      </Card>
    </div>
  );
}
