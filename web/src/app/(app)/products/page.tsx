"use client";

import { useCallback, useEffect, useState } from "react";
import { Boxes, ChefHat, Package, Utensils } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { DEFAULT_PROJECT_ID, getSkus, type SkuItem } from "@/lib/api";

const productTiers = [
  { label: "基础盘", items: ["原味章鱼烧", "肉松章鱼烧"], color: "border-emerald-200 bg-emerald-50" },
  { label: "差异款", items: ["藤椒章鱼烧", "玉米奶酪章鱼烧"], color: "border-amber-200 bg-amber-50" },
  { label: "高客单", items: ["双拼章鱼烧", "全家福章鱼烧"], color: "border-purple-200 bg-purple-50" },
  { label: "复杂款", items: ["咸蛋黄章鱼烧", "芝士培根章鱼烧"], color: "border-rose-200 bg-rose-50" },
];

export default function ProductsPage() {
  const [ingredients, setIngredients] = useState<SkuItem[]>([]);
  const [packaging, setPackaging] = useState<SkuItem[]>([]);
  const [initialized, setInitialized] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const res = await getSkus(DEFAULT_PROJECT_ID);
      setIngredients(res.skus.filter((s) => s.category === "食材"));
      setPackaging(res.skus.filter((s) => s.category === "包装" || s.category === "耗材"));
    } catch { /* offline */ }
    setInitialized(true);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <ModulePage module={getModule("/products")}>
        <div className="space-y-4">
          {!initialized && <div className="h-0.5 w-full animate-pulse rounded-full bg-primary/30" />}

          {/* 产品梯队 */}
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {productTiers.map((tier) => (
              <div key={tier.label} className={`rounded-2xl border p-4 ${tier.color}`}>
                <p className="text-xs font-medium uppercase tracking-wide opacity-70">{tier.label}</p>
                <div className="mt-2 space-y-1">
                  {tier.items.map((item) => (
                    <p key={item} className="text-sm font-semibold text-on-background">{item}</p>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* 原料消耗 */}
          <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <div className="flex items-center gap-2">
              <ChefHat className="h-4 w-4 text-on-surface-variant" />
              <p className="text-xs font-medium text-on-surface-variant">原料消耗与库存</p>
            </div>
            {ingredients.length > 0 ? (
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {ingredients.map((sku) => (
                  <div key={sku.id} className="flex items-center justify-between rounded-xl bg-white/55 px-4 py-3">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-on-background">{sku.name}</p>
                      <p className="text-xs text-on-surface-variant">日均消耗 {sku.consumption_per_day}{sku.unit} · 单位 ¥{sku.unit_cost}</p>
                    </div>
                    <div className="text-right">
                      <p className={`text-sm font-bold ${sku.status === "断货" || sku.status === "严重不足" ? "text-red-600" : sku.status === "偏低" ? "text-amber-600" : "text-emerald-600"}`}>{sku.current_stock}{sku.unit}</p>
                      <p className="text-[10px] text-on-surface-variant">{sku.status}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : initialized ? (
              <p className="mt-3 text-sm text-on-surface-variant">还没有录入食材 SKU，去进货库存页添加</p>
            ) : null}
          </div>

          {/* 包装耗材 */}
          <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <div className="flex items-center gap-2">
              <Package className="h-4 w-4 text-on-surface-variant" />
              <p className="text-xs font-medium text-on-surface-variant">包装与耗材</p>
            </div>
            {packaging.length > 0 ? (
              <div className="mt-3 grid gap-2 md:grid-cols-3">
                {packaging.map((sku) => (
                  <div key={sku.id} className="flex items-center justify-between rounded-xl bg-white/55 px-4 py-3">
                    <div>
                      <p className="text-sm font-semibold text-on-background">{sku.name}</p>
                      <p className="text-xs text-on-surface-variant">单位 ¥{sku.unit_cost}</p>
                    </div>
                    <p className="text-sm font-bold text-on-background">{sku.current_stock}{sku.unit}</p>
                  </div>
                ))}
              </div>
            ) : initialized ? (
              <p className="mt-3 text-sm text-on-surface-variant">还没有录入包装耗材 SKU</p>
            ) : null}
          </div>

        </div>
    </ModulePage>
  );
}
