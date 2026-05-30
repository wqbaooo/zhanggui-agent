import { RISK_BADGE } from "@/components/shared/badges";
import type { RiskItem } from "@/domain/types";

export function RiskList({ risks, title }: { risks: RiskItem[]; title?: string }) {
  if (risks.length === 0) return null;

  return (
    <div className="rounded-xl border border-cream-200 bg-white p-5">
      {title && <p className="text-[10px] text-gray-400 font-mono tracking-wider mb-3">{title} · {risks.length}</p>}
      <div className="space-y-3">
        {risks.map((r) => {
          const rb = RISK_BADGE[r.severity];
          return (
            <div key={r.id} className="rounded-lg border border-cream-200 p-3">
              <div className="flex items-start gap-2 mb-1.5">
                <span className={`mt-0.5 size-1.5 rounded-full ${rb.text === "text-red-400" ? "bg-red-500" : rb.text === "text-amber-400" ? "bg-amber-500" : "bg-emerald-500"}`} />
                <span className="text-xs font-medium text-gray-700">{r.name}</span>
                <span className={`ml-auto text-[9px] font-mono px-1.5 py-0.5 rounded-full ${rb.bg} ${rb.text}`}>{rb.label}</span>
              </div>
              <p className="text-[11px] text-gray-500 ml-4">{r.evidence}</p>
              <p className="text-[11px] text-gray-600 ml-4 mt-0.5 font-medium">→ {r.suggestedAction}</p>
              <div className="flex items-center gap-2 ml-4 mt-1.5">
                <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded-full ${r.status === "verified" ? "bg-emerald-50 text-emerald-600" : r.status === "unverified" ? "bg-amber-50 text-amber-600" : "bg-gray-100 text-gray-500"}`}>
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
