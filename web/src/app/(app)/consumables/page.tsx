"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { Droplets, Package, Plus, Zap } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { Skeleton } from "@/components/shared/Loading";
import { DEFAULT_PROJECT_ID, getSkus, type SkuItem } from "@/lib/api";

const NumberFlow = dynamic(() => import("@number-flow/react"), { ssr: false });

// ── 模拟耗材 SKU ──
const MOCK_CONSUMABLES: SkuItem[] = [
  { id: "c-1", name: "6粒盒", category: "耗材", unit: "个", safety_stock: 200, current_stock: 85, unit_cost: 0.35, supplier: "本地批发", batch_cycle_days: 30, consumption_per_day: 28, last_purchase_date: "2026-05-20", next_purchase_est: "2026-06-20", status: "active", notes: "" },
  { id: "c-2", name: "4粒盒", category: "耗材", unit: "个", safety_stock: 150, current_stock: 42, unit_cost: 0.28, supplier: "本地批发", batch_cycle_days: 30, consumption_per_day: 18, last_purchase_date: "2026-05-20", next_purchase_est: "2026-06-20", status: "active", notes: "" },
  { id: "c-3", name: "9粒圆盒", category: "耗材", unit: "个", safety_stock: 100, current_stock: 60, unit_cost: 0.42, supplier: "本地批发", batch_cycle_days: 30, consumption_per_day: 10, last_purchase_date: "2026-05-18", next_purchase_est: "2026-06-18", status: "active", notes: "" },
  { id: "c-4", name: "塑料袋", category: "耗材", unit: "个", safety_stock: 500, current_stock: 180, unit_cost: 0.05, supplier: "本地批发", batch_cycle_days: 15, consumption_per_day: 65, last_purchase_date: "2026-05-25", next_purchase_est: "2026-06-09", status: "active", notes: "" },
  { id: "c-5", name: "打包袋", category: "耗材", unit: "个", safety_stock: 300, current_stock: 95, unit_cost: 0.08, supplier: "本地批发", batch_cycle_days: 20, consumption_per_day: 38, last_purchase_date: "2026-05-22", next_purchase_est: "2026-06-12", status: "active", notes: "" },
  { id: "c-6", name: "手套", category: "耗材", unit: "双", safety_stock: 200, current_stock: 130, unit_cost: 0.15, supplier: "本地批发", batch_cycle_days: 20, consumption_per_day: 12, last_purchase_date: "2026-05-28", next_purchase_est: "2026-06-18", status: "active", notes: "" },
  { id: "c-7", name: "小票纸", category: "耗材", unit: "卷", safety_stock: 10, current_stock: 4, unit_cost: 3.5, supplier: "本地批发", batch_cycle_days: 30, consumption_per_day: 0.5, last_purchase_date: "2026-05-15", next_purchase_est: "2026-06-15", status: "active", notes: "" },
  { id: "c-8", name: "清洁用品", category: "耗材", unit: "套", safety_stock: 5, current_stock: 2, unit_cost: 15, supplier: "本地批发", batch_cycle_days: 30, consumption_per_day: 0.2, last_purchase_date: "2026-05-10", next_purchase_est: "2026-06-10", status: "active", notes: "" },
];

interface UtilityEntry {
  month: string;
  water: number;
  electricity: number;
  notes: string;
}

const MOCK_UTILITIES: UtilityEntry[] = [
  { month: "2026-04", water: 180, electricity: 920, notes: "" },
  { month: "2026-05", water: 210, electricity: 1050, notes: "空调季开始" },
  { month: "2026-06", water: 195, electricity: 1120, notes: "" },
];

export default function ConsumablesPage() {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<SkuItem[]>([]);
  const [utilities, setUtilities] = useState<UtilityEntry[]>(MOCK_UTILITIES);
  const [editingUtility, setEditingUtility] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ water: 0, electricity: 0, notes: "" });
  const [offline, setOffline] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const res = await getSkus(DEFAULT_PROJECT_ID, "耗材");
      const skus = res.skus || [];
      setItems(skus.length > 0 ? skus : MOCK_CONSUMABLES);
      setOffline(false);
    } catch {
      setItems(MOCK_CONSUMABLES);
      setOffline(true);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const latestUtility = utilities[utilities.length - 1] || { water: 0, electricity: 0, notes: "" };
  const prevUtility = utilities.length > 1 ? utilities[utilities.length - 2] : null;

  const totalConsumableCost = useMemo(() =>
    items.reduce((sum, item) => sum + item.consumption_per_day * item.unit_cost * 30, 0),
  [items]);

  const startEdit = (month: string) => {
    const entry = utilities.find((u) => u.month === month);
    if (entry) {
      setEditForm({ water: entry.water, electricity: entry.electricity, notes: entry.notes });
      setEditingUtility(month);
    }
  };

  const saveUtility = () => {
    if (!editingUtility) return;
    setUtilities((prev) => prev.map((u) =>
      u.month === editingUtility ? { ...u, ...editForm } : u
    ));
    setEditingUtility(null);
  };

  const monthLabel = (ym: string) => {
    const [y, m] = ym.split("-");
    return `${y}年${parseInt(m)}月`;
  };

  const module = getModule("/consumables");

  return (
    <ModulePage module={module}>
      <div className="space-y-4">

        {offline && (
          <div className="rounded-2xl border border-amber-200 bg-amber-50/80 p-3 text-center">
            <p className="text-xs text-amber-700">后端未连接，展示模拟数据</p>
          </div>
        )}

        {/* ── 水电费卡片 ── */}
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-2xl border border-white/45 bg-white/42 p-4 backdrop-blur-xl">
            <div className="flex items-center gap-2">
              <Droplets className="h-4 w-4 text-sky-500" />
              <p className="text-[10px] font-medium text-on-surface-variant">本月水费</p>
            </div>
            {loading ? <Skeleton className="mt-2 h-7 w-20" /> : (
              <p className="mt-2 text-xl font-bold text-on-background tabular-nums">
                <NumberFlow value={latestUtility.water} format={{ style: "decimal", minimumFractionDigits: 0 }} prefix="¥" />
              </p>
            )}
            {prevUtility && (
              <p className="mt-1 text-[10px] text-on-surface-variant">
                上月 ¥{prevUtility.water}
                {latestUtility.water !== prevUtility.water && (
                  <span className={latestUtility.water > prevUtility.water ? "text-red-500 ml-1" : "text-emerald-500 ml-1"}>
                    {latestUtility.water > prevUtility.water ? "↑" : "↓"}{Math.abs(latestUtility.water - prevUtility.water)}
                  </span>
                )}
              </p>
            )}
          </div>

          <div className="rounded-2xl border border-white/45 bg-white/42 p-4 backdrop-blur-xl">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-amber-500" />
              <p className="text-[10px] font-medium text-on-surface-variant">本月电费</p>
            </div>
            {loading ? <Skeleton className="mt-2 h-7 w-20" /> : (
              <p className="mt-2 text-xl font-bold text-on-background tabular-nums">
                <NumberFlow value={latestUtility.electricity} format={{ style: "decimal", minimumFractionDigits: 0 }} prefix="¥" />
              </p>
            )}
            {prevUtility && (
              <p className="mt-1 text-[10px] text-on-surface-variant">
                上月 ¥{prevUtility.electricity}
                {latestUtility.electricity !== prevUtility.electricity && (
                  <span className={latestUtility.electricity > prevUtility.electricity ? "text-red-500 ml-1" : "text-emerald-500 ml-1"}>
                    {latestUtility.electricity > prevUtility.electricity ? "↑" : "↓"}{Math.abs(latestUtility.electricity - prevUtility.electricity)}
                  </span>
                )}
              </p>
            )}
          </div>

          <div className="rounded-2xl border border-white/45 bg-white/42 p-4 backdrop-blur-xl">
            <div className="flex items-center gap-2">
              <Package className="h-4 w-4 text-emerald-500" />
              <p className="text-[10px] font-medium text-on-surface-variant">预估月耗材成本</p>
            </div>
            <p className="mt-2 text-xl font-bold text-on-background tabular-nums">
              <NumberFlow value={Math.round(totalConsumableCost)} format={{ style: "decimal", minimumFractionDigits: 0 }} prefix="¥" />
            </p>
            <p className="mt-1 text-[10px] text-on-surface-variant">{items.length} 项耗材 · 按日消耗估算</p>
          </div>
        </div>

        {/* ── 水电费历史 ── */}
        <div className="rounded-2xl border border-white/45 bg-white/42 p-4 backdrop-blur-xl">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-medium text-on-surface-variant">水电费记录</p>
            <button
              onClick={() => {
                const ym = `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, "0")}`;
                if (!utilities.find((u) => u.month === ym)) {
                  setUtilities((prev) => [...prev, { month: ym, water: 0, electricity: 0, notes: "" }]);
                }
                startEdit(ym);
              }}
              className="flex items-center gap-1 rounded-full bg-primary-container px-2.5 py-1 text-[10px] font-medium text-primary-fixed hover:bg-primary-container/70 transition-colors"
            >
              <Plus className="h-3 w-3" /> 录入本月
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-white/45 text-on-surface-variant">
                  <th className="py-2 text-left font-medium">月份</th>
                  <th className="py-2 text-right font-medium">水费</th>
                  <th className="py-2 text-right font-medium">电费</th>
                  <th className="py-2 text-right font-medium">合计</th>
                  <th className="py-2 text-left font-medium hidden md:table-cell">备注</th>
                  <th className="py-2 text-right font-medium w-16"></th>
                </tr>
              </thead>
              <tbody>
                {utilities.map((u) => (
                  <tr key={u.month} className="border-b border-white/30 last:border-0">
                    {editingUtility === u.month ? (
                      <>
                        <td className="py-2 text-on-background font-medium">{monthLabel(u.month)}</td>
                        <td className="py-2 text-right">
                          <input type="number" value={editForm.water} onChange={(e) => setEditForm((p) => ({ ...p, water: Number(e.target.value) }))}
                            className="w-20 rounded-lg border border-primary/30 bg-primary-container/10 px-2 py-1 text-xs text-right outline-none focus:border-primary/50" />
                        </td>
                        <td className="py-2 text-right">
                          <input type="number" value={editForm.electricity} onChange={(e) => setEditForm((p) => ({ ...p, electricity: Number(e.target.value) }))}
                            className="w-20 rounded-lg border border-primary/30 bg-primary-container/10 px-2 py-1 text-xs text-right outline-none focus:border-primary/50" />
                        </td>
                        <td className="py-2 text-right font-semibold text-on-background">¥{editForm.water + editForm.electricity}</td>
                        <td className="py-2 hidden md:table-cell">
                          <input value={editForm.notes} onChange={(e) => setEditForm((p) => ({ ...p, notes: e.target.value }))}
                            className="w-full rounded-lg border border-primary/30 bg-primary-container/10 px-2 py-1 text-xs outline-none focus:border-primary/50" placeholder="备注" />
                        </td>
                        <td className="py-2 text-right">
                          <button onClick={saveUtility} className="rounded-full bg-primary px-2.5 py-1 text-[10px] font-semibold text-on-primary">保存</button>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="py-2 text-on-background font-medium">{monthLabel(u.month)}</td>
                        <td className="py-2 text-right text-on-surface-variant tabular-nums">¥{u.water}</td>
                        <td className="py-2 text-right text-on-surface-variant tabular-nums">¥{u.electricity}</td>
                        <td className="py-2 text-right font-semibold text-on-background tabular-nums">¥{u.water + u.electricity}</td>
                        <td className="py-2 text-on-surface-variant hidden md:table-cell">{u.notes || "-"}</td>
                        <td className="py-2 text-right">
                          <button onClick={() => startEdit(u.month)} className="text-[10px] text-primary-fixed hover:underline">编辑</button>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── 耗材消耗列表 ── */}
        <div className="rounded-2xl border border-white/45 bg-white/42 p-4 backdrop-blur-xl">
          <p className="text-xs font-medium text-on-surface-variant mb-3">耗材消耗追踪</p>
          {loading ? (
            <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}</div>
          ) : (
            <div className="space-y-2">
              {items.map((item) => {
                const stockRatio = item.current_stock / Math.max(item.safety_stock, 1);
                const isLow = stockRatio < 0.5;
                const isWarn = stockRatio < 1 && !isLow;
                return (
                  <div key={item.id} className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 transition-colors ${
                    isLow ? "border-red-200 bg-red-50/40" : isWarn ? "border-amber-200 bg-amber-50/30" : "border-white/45 bg-white/35"
                  }`}>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-on-background">{item.name}</span>
                        <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-mono ${
                          isLow ? "bg-red-100 text-red-600" : isWarn ? "bg-amber-100 text-amber-600" : "bg-emerald-100 text-emerald-600"
                        }`}>
                          {isLow ? "即将断货" : isWarn ? "偏低" : "充足"}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-3 text-[10px] text-on-surface-variant">
                        <span>库存 {item.current_stock}{item.unit} / 安全 {item.safety_stock}{item.unit}</span>
                        <span>日均消耗 {item.consumption_per_day}{item.unit}</span>
                        <span>单价 ¥{item.unit_cost}</span>
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="text-sm font-semibold text-on-background tabular-nums">¥{(item.consumption_per_day * item.unit_cost * 30).toFixed(0)}</p>
                      <p className="text-[9px] text-on-surface-variant">月预估</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </ModulePage>
  );
}
