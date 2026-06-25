"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Boxes, DollarSign, History, PackageCheck, Plus, RefreshCw, TrendingDown } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { DEFAULT_PROJECT_ID, getSkus, getForecast, getPurchases, createSku, createPurchase, type SkuItem, type ForecastItem, type PurchaseRecord } from "@/lib/api";

const categories = ["全部", "食材", "包装", "耗材", "清洁", "其他"] as const;
const statusMap: Record<string, { label: string; cls: string }> = {
  "正常": { label: "充足", cls: "bg-emerald-100 text-emerald-700" },
  "偏低": { label: "偏低", cls: "bg-amber-100 text-amber-700" },
  "严重不足": { label: "告急", cls: "bg-orange-100 text-orange-700" },
  "断货": { label: "断货", cls: "bg-red-100 text-red-700" },
};

export default function InventoryPage() {
  const [skus, setSkus] = useState<SkuItem[]>([]);
  const [forecast, setForecast] = useState<ForecastItem[]>([]);
  const [purchases, setPurchases] = useState<PurchaseRecord[]>([]);
  const [activeCat, setActiveCat] = useState<string>("全部");
  const [tab, setTab] = useState<"stock" | "forecast" | "history">("stock");
  const [newName, setNewName] = useState("");
  const [newCat, setNewCat] = useState("食材");
  const [newUnit, setNewUnit] = useState("kg");
  const [newSafety, setNewSafety] = useState("");
  const [showAdd, setShowAdd] = useState(false);

  const [initialized, setInitialized] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [skuRes, fRes, pRes] = await Promise.all([
        getSkus(DEFAULT_PROJECT_ID),
        getForecast(DEFAULT_PROJECT_ID),
        getPurchases(DEFAULT_PROJECT_ID, 10),
      ]);
      setSkus(skuRes.skus);
      setForecast(fRes.forecast);
      setPurchases(pRes.purchases);
    } catch { /* */ }
    setInitialized(true);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleAddSku = useCallback(async () => {
    if (!newName.trim()) return;
    await createSku({ name: newName.trim(), category: newCat, unit: newUnit, safety_stock: Number(newSafety) || 0 }, DEFAULT_PROJECT_ID);
    setNewName(""); setNewSafety(""); setShowAdd(false);
    fetchData();
  }, [newName, newCat, newUnit, newSafety, fetchData]);

  const filtered = activeCat === "全部" ? skus : skus.filter((s) => s.category === activeCat);
  const urgentForecast = forecast.filter((f) => f.action === "urgent");
  const recommendForecast = forecast.filter((f) => f.action === "recommend");

  return (
    <ModulePage module={getModule("/inventory")}>
        <div className="space-y-4">
          {!initialized && <div className="h-0.5 w-full animate-pulse rounded-full bg-primary/30" />}
          {/* Tabs */}
          <div className="flex gap-1 rounded-2xl bg-white/55 p-1">
            {(["stock", "forecast", "history"] as const).map((t) => (
              <button key={t} type="button" onClick={() => setTab(t)} className={`flex-1 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${tab === t ? "bg-on-background text-inverse-on-surface" : "text-on-surface-variant hover:text-on-background"}`}>
                {t === "stock" ? "现货库存" : t === "forecast" ? "补货预测" : "进货记录"}
              </button>
            ))}
          </div>

          {tab === "stock" && (
            <>
              {/* Category filter */}
              <div className="flex flex-wrap gap-1.5">
                {categories.map((cat) => (
                  <button key={cat} type="button" onClick={() => setActiveCat(cat)} className={`rounded-full px-3 py-1 text-xs transition-colors ${activeCat === cat ? "bg-on-background text-inverse-on-surface" : "border border-white/45 bg-white/55 text-on-surface-variant hover:bg-white/80"}`}>{cat}</button>
                ))}
                <button type="button" onClick={() => setShowAdd(!showAdd)} className="ml-auto inline-flex items-center gap-1 rounded-full bg-primary px-3 py-1 text-xs font-medium text-on-primary">
                  <Plus className="h-3 w-3" /> 加 SKU
                </button>
              </div>

              {showAdd && (
                <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-white/45 bg-white/55 p-3">
                  <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="品名" className="min-w-0 flex-1 rounded-xl border border-white/50 bg-white/70 px-3 py-1.5 text-sm outline-none focus:border-primary/50" />
                  <select value={newCat} onChange={(e) => setNewCat(e.target.value)} className="rounded-xl border border-white/50 bg-white/70 px-2 py-1.5 text-sm outline-none">
                    {["食材", "包装", "耗材", "清洁", "其他"].map((c) => (<option key={c}>{c}</option>))}
                  </select>
                  <select value={newUnit} onChange={(e) => setNewUnit(e.target.value)} className="rounded-xl border border-white/50 bg-white/70 px-2 py-1.5 text-sm outline-none">
                    {["kg", "g", "个", "包", "箱", "卷", "袋", "瓶", "双", "桶", "张"].map((u) => (<option key={u}>{u}</option>))}
                  </select>
                  <input value={newSafety} onChange={(e) => setNewSafety(e.target.value)} placeholder="安全库存" type="number" className="w-20 rounded-xl border border-white/50 bg-white/70 px-3 py-1.5 text-sm outline-none focus:border-primary/50" />
                  <button type="button" onClick={handleAddSku} disabled={!newName.trim()} className="rounded-xl bg-primary px-3 py-1.5 text-sm font-semibold text-on-primary disabled:opacity-50">确认</button>
                </div>
              )}

              {/* SKU grid */}
              {initialized && filtered.length === 0 && (
                <p className="rounded-2xl bg-white/45 p-4 text-sm text-on-surface-variant">还没添加任何 SKU。</p>
              )}
              {filtered.length > 0 && (
                <div className="grid gap-3 md:grid-cols-2">
                  {filtered.map((sku) => (
                    <div key={sku.id} className="rounded-2xl border border-white/45 bg-white/55 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-on-background">{sku.name}</p>
                          <p className="mt-0.5 text-xs text-on-surface-variant">{sku.category} · {sku.unit_cost > 0 ? `¥${sku.unit_cost}/${sku.unit}` : "待填成本"}</p>
                        </div>
                        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${statusMap[sku.status]?.cls || "bg-slate-100 text-slate-700"}`}>{statusMap[sku.status]?.label || sku.status}</span>
                      </div>
                      <div className="mt-3 flex items-center gap-3 text-xs text-on-surface-variant">
                        <span>库存 <span className="font-semibold text-on-background">{sku.current_stock}{sku.unit}</span></span>
                        <span>安全 <span className="font-semibold text-on-background">{sku.safety_stock}{sku.unit}</span></span>
                        {sku.consumption_per_day > 0 && <span>日均消耗 {sku.consumption_per_day}{sku.unit}</span>}
                      </div>
                      {sku.supplier && <p className="mt-1 text-xs text-on-surface-variant">供应商：{sku.supplier}</p>}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {tab === "forecast" && (
            <div className="space-y-4">
              {urgentForecast.length > 0 && (
                <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-red-600" />
                    <p className="text-sm font-semibold text-red-800">需要紧急补货</p>
                  </div>
                  <div className="mt-3 space-y-2">
                    {urgentForecast.map((f) => (
                      <div key={f.sku_id} className="flex items-center justify-between gap-3 rounded-xl bg-white/80 px-3 py-2.5">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-red-800">{f.name}</p>
                          <p className="mt-0.5 text-xs text-red-600">剩 {f.current_stock}{f.unit}，安全库存 {f.safety_stock}{f.unit}</p>
                        </div>
                        {f.recommend_qty != null && <span className="shrink-0 rounded-full bg-red-600 px-3 py-1 text-xs font-semibold text-white">建议补 {f.recommend_qty}{f.unit}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {recommendForecast.length > 0 && (
                <div>
                  <p className="text-sm font-semibold text-on-background">建议补货</p>
                  <div className="mt-2 grid gap-2 md:grid-cols-2">
                    {recommendForecast.map((f) => (
                      <div key={f.sku_id} className="flex items-center justify-between gap-3 rounded-2xl border border-white/45 bg-white/55 p-3">
                        <div className="min-w-0"><p className="truncate text-sm font-semibold text-on-background">{f.name}</p><p className="mt-0.5 text-xs text-on-surface-variant">可撑 {f.days_remaining} 天</p></div>
                        {f.recommend_qty != null && <span className="shrink-0 rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">建议补 {f.recommend_qty}{f.unit}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {initialized && urgentForecast.length === 0 && recommendForecast.length === 0 && (
                <p className="rounded-2xl bg-white/45 p-4 text-sm text-on-surface-variant">所有 SKU 库存充足，或还没有消耗数据。先添加 SKU 并设置日均消耗。</p>
              )}
            </div>
          )}

          {tab === "history" && (
            <div className="space-y-3">
              {initialized && purchases.length === 0 && (
                <p className="rounded-2xl bg-white/45 p-4 text-sm text-on-surface-variant">还没有进货记录。</p>
              )}
              {purchases.length > 0 && (
                purchases.map((p) => (
                  <div key={p.id} className="rounded-2xl border border-white/45 bg-white/55 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-on-background">{p.date}</p>
                        <p className="mt-0.5 text-xs text-on-surface-variant">{p.supplier || "未填写供应商"}</p>
                      </div>
                      <span className="rounded-full bg-white/70 px-2 py-0.5 text-xs font-medium text-on-background">¥{p.total_cost.toFixed(0)}</span>
                    </div>
                    <div className="mt-2 space-y-1">
                      {p.items.map((item, i) => (
                        <div key={i} className="flex items-center justify-between gap-3 text-xs text-on-surface-variant">
                          <span>{item.name}</span>
                          <span>{item.quantity} × ¥{item.unit_cost} = ¥{item.subtotal.toFixed(0)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
    </ModulePage>
  );
}
