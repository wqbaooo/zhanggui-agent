"use client";

import { useCallback, useEffect, useState } from "react";
import ReactEChartsCore from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { ChefHat, Package, ReceiptText, Sparkles } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { DEFAULT_PROJECT_ID, getOperationSummary, type OperationSummary } from "@/lib/api";
import { apiGet } from "@/lib/api";

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);

interface MenuItem {
  sku_id: string;
  name: string;
  category: string;
  unit_cost: number;
  current_stock: number;
  safety_stock: number;
  daily_consumption: number;
  monthly_consumption: number;
  monthly_cost: number;
  stock_days: number;
  status: string;
}

export default function ProductsPage() {
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [summary, setSummary] = useState<OperationSummary | null>(null);
  const [initialized, setInitialized] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [analysisRes, operationSummary] = await Promise.all([
        apiGet<{ items: MenuItem[]; total: number }>(
          `/api/projects/${DEFAULT_PROJECT_ID}/skus/menu-analysis`,
        ),
        getOperationSummary(DEFAULT_PROJECT_ID, 30),
      ]);
      setMenuItems(analysisRes.items);
      setSummary(operationSummary);
    } catch { /* offline */ }
    setInitialized(true);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const ingredients = menuItems.filter((s) => s.category === "食材");
  const packaging = menuItems.filter((s) => s.category === "包装" || s.category === "耗材");
  const totalMonthlyCost = menuItems.reduce((s, m) => s + m.monthly_cost, 0);

  // 月度成本排行图
  const costBarOption = ingredients.length > 0 ? {
    tooltip: {
      trigger: "axis" as const,
      backgroundColor: "rgba(255,255,255,0.92)",
      borderColor: "rgba(0,0,0,0.08)",
      borderRadius: 12,
      textStyle: { color: "#1a1a1a", fontSize: 12 },
      formatter: (params: Array<Record<string, unknown>>) => {
        const p = params[0] as { name: string; value: number };
        const item = ingredients.find((i) => i.name === p.name);
        return `${p.name}<br/>月消耗 ${item?.monthly_consumption ?? "-"}${item ? "" : ""}<br/>月成本 ¥${p.value?.toLocaleString() ?? ""}<br/>可维持 ${item?.stock_days ?? "-"}天`;
      },
    },
    grid: { left: 120, right: 16, top: 8, bottom: 24, containLabel: true },
    xAxis: {
      type: "value" as const,
      axisLabel: { fontSize: 10, color: "#6b7280", formatter: (v: number) => `¥${v}` },
      splitLine: { lineStyle: { color: "rgba(0,0,0,0.06)" } },
    },
    yAxis: {
      type: "category" as const,
      data: ingredients.map((i) => i.name),
      axisLabel: { fontSize: 11, color: "#6b7280" },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [{
      name: "月成本",
      type: "bar",
      data: ingredients.map((i) => ({
        value: i.monthly_cost,
        itemStyle: {
          color: i.monthly_cost > 2000 ? "#D9261C" : i.monthly_cost > 1000 ? "#c8a64e" : "#0F4C3A",
          borderRadius: [0, 4, 4, 0],
        },
      })),
      barMaxWidth: 20,
      label: { show: true, position: "right" as const, fontSize: 10, color: "#6b7280", formatter: (p: { value: number }) => `¥${p.value}` },
    }],
  } : null;

  return (
    <ModulePage module={getModule("/products")}>
      <div className="space-y-4">
        {!initialized && <div className="h-0.5 w-full animate-pulse rounded-full bg-primary/30" />}

        <section className="rounded-3xl border border-stone-200 bg-white/85 p-5 shadow-sm">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <ReceiptText className="h-4 w-4 text-octo-600" />
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500">真实商品经营</p>
              </div>
              <h1 className="mt-2 text-xl font-bold text-stone-950">卖了什么，贡献了多少，再关联怎么做</h1>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-stone-600">
                商品销量来自客如云，物料成本来自配方与生产记录。当前只展示已经识别的商品，不再用预设“爆品梯队”冒充真实结论。
              </p>
            </div>
            <span className="w-fit rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
              {summary?.product_sales.length ? "已有部分商品明细" : "等待商品销售明细"}
            </span>
          </div>

          {summary?.product_sales.length ? (
            <div className="mt-5 grid gap-3 md:grid-cols-3">
              {summary.product_sales.map((product, index) => (
                <div key={product.name} className="rounded-2xl border border-stone-200 bg-stone-50/75 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs font-semibold text-stone-400">#{index + 1}</span>
                    <span className="text-xs text-stone-500">{product.quantity} 份</span>
                  </div>
                  <p className="mt-3 text-base font-bold text-stone-950">{product.name}</p>
                  <p className="mt-1 text-xl font-bold tabular-nums text-octo-700">¥{product.amount.toLocaleString()}</p>
                  <p className="mt-2 text-[11px] leading-5 text-stone-500">
                    单份收入约 ¥{(product.amount / Math.max(product.quantity, 1)).toFixed(1)} · BOM与贡献利润待完整商品明细
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-5 rounded-2xl border border-dashed border-stone-300 p-6 text-center text-sm text-stone-500">
              上传客如云“商品销售统计”完整截图后开始建立商品基准。
            </div>
          )}
        </section>

        <section className="grid gap-3 md:grid-cols-3">
          <ProductLoopCard title="销售事实" body="每个商品的份数、金额、退款和销售时段" status="已开始" />
          <ProductLoopCard title="制作标准" body="四粒/六粒/九粒、配方、锅次、盒型和制作时间" status="待补完整商品表" />
          <ProductLoopCard title="盈利判断" body="售价减去食材、包装、渠道和制作成本" status="成本补齐后计算" />
        </section>

        <div className="flex items-center gap-2 pt-2">
          <Sparkles className="h-4 w-4 text-stone-400" />
          <h2 className="text-sm font-bold text-stone-900">商品关联物料</h2>
          <span className="text-xs text-stone-400">用于成本和断货核验，不代表商品本身</span>
        </div>

        {/* 食材成本分析 */}
        {ingredients.length > 0 && costBarOption ? (
          <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <div className="flex items-center gap-2">
              <ChefHat className="h-4 w-4 text-on-surface-variant" />
              <p className="text-xs font-medium text-on-surface-variant">物料消耗成本估算</p>
            </div>
            <div className="mt-3 h-72">
              <ReactEChartsCore echarts={echarts} option={costBarOption} style={{ height: "100%" }} notMerge />
            </div>
          </div>
        ) : null}

        {/* 库存明细 */}
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <div className="flex items-center gap-2">
              <ChefHat className="h-4 w-4 text-on-surface-variant" />
              <p className="text-xs font-medium text-on-surface-variant">原料库存明细</p>
            </div>
            {ingredients.length > 0 ? (
              <div className="mt-3 space-y-2">
                {ingredients.map((sku) => (
                  <div key={sku.sku_id} className="flex items-center justify-between rounded-xl bg-white/55 px-3 py-2.5">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-on-background">{sku.name}</p>
                      <p className="text-xs text-on-surface-variant">日耗 {sku.daily_consumption} · 月成本 ¥{sku.monthly_cost}</p>
                    </div>
                    <div className="text-right shrink-0 ml-2">
                      <p className={`text-sm font-bold ${sku.status === "断货" || sku.status === "严重不足" ? "text-red-600" : sku.status === "偏低" ? "text-amber-600" : "text-emerald-600"}`}>
                        {sku.current_stock}
                      </p>
                      <p className="text-[10px] text-on-surface-variant">{sku.status} · {sku.stock_days}天</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>

          <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <div className="flex items-center gap-2">
              <Package className="h-4 w-4 text-on-surface-variant" />
              <p className="text-xs font-medium text-on-surface-variant">包装耗材</p>
            </div>
            {packaging.length > 0 ? (
              <div className="mt-3 space-y-2">
                {packaging.map((sku) => (
                  <div key={sku.sku_id} className="flex items-center justify-between rounded-xl bg-white/55 px-3 py-2.5">
                    <div>
                      <p className="text-sm font-semibold text-on-background">{sku.name}</p>
                      <p className="text-xs text-on-surface-variant">单位 ¥{sku.unit_cost} · 日耗 {sku.daily_consumption}</p>
                    </div>
                    <p className={`text-sm font-bold ${sku.status === "断货" ? "text-red-600" : "text-on-background"}`}>
                      {sku.current_stock}{sku.status === "正常" ? "" : ` · ${sku.status}`}
                    </p>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>

        {/* 月度成本汇总 */}
        {totalMonthlyCost > 0 && (
          <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <p className="text-xs font-medium text-on-surface-variant">月度物料成本估算</p>
            <div className="mt-2 flex items-baseline gap-3">
              <p className="text-2xl font-bold text-on-background">¥{totalMonthlyCost.toLocaleString()}</p>
              <p className="text-sm text-on-surface-variant">{menuItems.length} 项 SKU · {ingredients.length} 食材 + {packaging.length} 耗材</p>
            </div>
          </div>
        )}
      </div>
    </ModulePage>
  );
}

function ProductLoopCard({ title, body, status }: { title: string; body: string; status: string }) {
  return (
    <article className="rounded-2xl border border-stone-200 bg-white/75 p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-bold text-stone-950">{title}</p>
        <span className="shrink-0 rounded-full bg-stone-100 px-2 py-1 text-[10px] font-medium text-stone-600">{status}</span>
      </div>
      <p className="mt-2 text-xs leading-5 text-stone-500">{body}</p>
    </article>
  );
}
