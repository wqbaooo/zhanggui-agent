"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Store } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { DEFAULT_PROJECT_ID, getStaff, getSkus, type StaffMember, type SkuItem } from "@/lib/api";

const defaultCostParams = [
  { key: "rent_monthly", label: "月租金", value: "¥6,000", hint: "含商场管理费" },
  { key: "labor_monthly", label: "月人工", value: "¥4,800", hint: "1名员工" },
  { key: "platform_fee_rate", label: "平台费率", value: "20%", hint: "美团+淘宝闪购均值" },
  { key: "target_profit", label: "保底月净利", value: "¥10,000", hint: "保本后目标" },
  { key: "growth_profit", label: "增长月净利", value: "¥15,000", hint: "冲刺目标" },
];

export default function SettingsPage() {
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [skuCount, setSkuCount] = useState(0);
  const [saved, setSaved] = useState<Record<string, string>>({});
  const [initialized, setInitialized] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [sRes, skuRes] = await Promise.all([
        getStaff(DEFAULT_PROJECT_ID),
        getSkus(DEFAULT_PROJECT_ID),
      ]);
      setStaff(sRes.staff.filter((s) => s.status === "在岗"));
      setSkuCount(skuRes.total);
    } catch { /* offline */ }
    setInitialized(true);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSave = (key: string, value: string) => {
    setSaved((prev) => ({ ...prev, [key]: value }));
    setTimeout(() => setSaved((prev) => { const next = { ...prev }; delete next[key]; return next; }), 1500);
  };

  return (
    <ModulePage module={getModule("/settings")}>
        <div className="space-y-4">
          {!initialized && <div className="h-0.5 w-full animate-pulse rounded-full bg-primary/30" />}

          {/* 成本参数 */}
          <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <p className="text-xs font-medium text-on-surface-variant">成本参数</p>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {defaultCostParams.map((param) => (
                <div key={param.key} className="flex items-center gap-3 rounded-xl bg-white/55 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-on-background">{param.label}</p>
                    <p className="text-xs text-on-surface-variant">{param.hint}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      defaultValue={param.value}
                      className="w-24 rounded-xl border border-white/50 bg-white/70 px-3 py-1.5 text-sm text-right font-bold text-on-background outline-none focus:border-primary/50"
                      onBlur={(e) => handleSave(param.key, e.target.value)}
                    />
                    {saved[param.key] && <Check className="h-4 w-4 text-emerald-500" />}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 员工概览 */}
          <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <p className="text-xs font-medium text-on-surface-variant">员工配置</p>
            {staff.length > 0 ? (
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {staff.map((s) => (
                  <div key={s.id} className="flex items-center justify-between rounded-xl bg-white/55 px-4 py-3">
                    <div>
                      <p className="text-sm font-semibold text-on-background">{s.name}</p>
                      <p className="text-xs text-on-surface-variant">{s.role} · 时薪 ¥{s.hourly_wage}{s.monthly_base > 0 ? ` · 底薪 ¥${s.monthly_base}` : ""}</p>
                    </div>
                    <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700">{s.status}</span>
                  </div>
                ))}
              </div>
            ) : initialized ? (
              <p className="mt-3 text-sm text-on-surface-variant">还没有员工数据</p>
            ) : null}
          </div>

          {/* 商品配置 */}
          <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <p className="text-xs font-medium text-on-surface-variant">商品配置</p>
            <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
              <StatCell label="SKU 总数" value={`${skuCount}`} />
              <StatCell label="产品梯队" value="4 类" />
              <StatCell label="在岗员工" value={`${staff.length}人`} />
              <StatCell label="经营天数" value="14天" />
            </div>
          </div>

        </div>
    </ModulePage>
  );
}

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/45 bg-white/55 p-3 text-center">
      <p className="text-xs text-on-surface-variant">{label}</p>
      <p className="mt-1 text-xl font-bold text-on-background">{value}</p>
    </div>
  );
}
