"use client";

import { useCallback, useEffect, useState } from "react";
import ReactEChartsCore from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { DEFAULT_PROJECT_ID, getOperations, type DailyOperationEntry } from "@/lib/api";
import { sumEntries } from "@/domain/calculations";

echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer]);

export default function ChannelsPage() {
  const [entries, setEntries] = useState<DailyOperationEntry[]>([]);
  const [initialized, setInitialized] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoadError(null);
    try {
      const res = await getOperations(DEFAULT_PROJECT_ID, 30);
      setEntries(res.entries);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "加载失败，请检查后端服务");
    }
    setInitialized(true);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // 渠道营收（优先用新字段，无数据则为0）
  const dineInRev = sumEntries(entries, "dine_in_revenue");
  const deliveryRev = sumEntries(entries, "delivery_revenue");
  const dineInOrders = sumEntries(entries, "dine_in_orders");
  const deliveryOrders = sumEntries(entries, "delivery_orders");
  const totalOrders = sumEntries(entries, "orders");

  const platformFee = sumEntries(entries, "platform_fee");
  const marketingCost = sumEntries(entries, "marketing_cost");
  const packagingCost = sumEntries(entries, "packaging_cost");

  const deliveryRatio = totalOrders > 0 ? deliveryOrders / totalOrders : 0;
  const deliveryProfit = deliveryRev - platformFee - marketingCost - packagingCost;

  const totalRev = sumEntries(entries, "revenue");
  const totalFood = sumEntries(entries, "food_cost");
  const totalLabor = sumEntries(entries, "labor");
  const totalRent = sumEntries(entries, "rent_allocated");
  const totalUtility = sumEntries(entries, "utility");

  const dineInRatio = totalRev > 0 ? dineInRev / totalRev : 0;
  const deliveryRatioRev = totalRev > 0 ? deliveryRev / totalRev : 0;

  const dineInAllocatedCost = (totalFood + totalLabor + totalRent + totalUtility) * dineInRatio;
  const deliveryAllocatedCost = (totalFood + totalLabor + totalRent + totalUtility) * deliveryRatioRev;

  const dineInProfit = dineInRev - dineInAllocatedCost;
  const deliveryNetProfit = deliveryRev - platformFee - marketingCost - packagingCost - deliveryAllocatedCost;

  const dineInProfitPerOrder = dineInOrders > 0 ? dineInProfit / dineInOrders : 0;
  const deliveryProfitPerOrder = deliveryOrders > 0 ? deliveryNetProfit / deliveryOrders : 0;
  const dineInMargin = dineInRev > 0 ? dineInProfit / dineInRev : 0;
  const deliveryMargin = deliveryRev > 0 ? deliveryNetProfit / deliveryRev : 0;

  // 数据来源检测：有真实 delivery_revenue 说明有外卖数据源
  const hasRealDelivery = entries.some((e) => (e.delivery_revenue || 0) > 0);

  const hasData = entries.length > 0;

  // 外卖日趋势（无真实 delivery_revenue 时显示0，不推导）
  const dailyChannels = entries.slice(-14).map((e) => ({
    date: e.date.slice(5),
    外卖营收: e.delivery_revenue || 0,
    平台费: Math.round(e.platform_fee || 0),
    营销: Math.round(e.marketing_cost || 0),
    包装: Math.round(e.packaging_cost || 0),
  }));

  // 渠道对比柱状图
  const channelBarOption = {
    tooltip: {
      trigger: "axis" as const,
      backgroundColor: "rgba(255,255,255,0.92)",
      borderColor: "rgba(0,0,0,0.08)",
      borderRadius: 12,
      textStyle: { color: "#1a1a1a", fontSize: 12 },
    },
    grid: { left: 8, right: 16, top: 8, bottom: 36, containLabel: true },
    xAxis: {
      type: "category" as const,
      data: ["堂食", "外卖"],
      axisLabel: { fontSize: 11, color: "#6b7280" },
    },
    yAxis: {
      type: "value" as const,
      axisLabel: { fontSize: 10, color: "#6b7280", formatter: (v: number) => `¥${v}` },
      splitLine: { lineStyle: { color: "rgba(0,0,0,0.06)" } },
    },
    series: [
      {
        name: "营收",
        type: "bar",
        data: [Math.round(dineInRev), Math.round(deliveryRev)],
        itemStyle: { color: (p: { dataIndex: number }) => p.dataIndex === 0 ? "#0F4C3A" : "#c8a64e", borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 60,
        label: { show: true, position: "top" as const, fontSize: 11, color: "#1a1a1a", formatter: (p: { value: number }) => `¥${p.value?.toLocaleString() ?? ""}` },
      },
    ],
  };

  // 外卖成本趋势
  const costTrendOption = {
    tooltip: {
      trigger: "axis" as const,
      backgroundColor: "rgba(255,255,255,0.92)",
      borderColor: "rgba(0,0,0,0.08)",
      borderRadius: 12,
      textStyle: { color: "#1a1a1a", fontSize: 12 },
    },
    legend: { data: ["平台费", "营销", "包装"], bottom: 0, textStyle: { fontSize: 11, color: "#6b7280" } },
    grid: { left: 8, right: 16, top: 8, bottom: 36, containLabel: true },
    xAxis: {
      type: "category" as const,
      data: dailyChannels.map((d) => d.date),
      axisLabel: { fontSize: 10, color: "#6b7280" },
    },
    yAxis: {
      type: "value" as const,
      axisLabel: { fontSize: 10, color: "#6b7280", formatter: (v: number) => `¥${v}` },
      splitLine: { lineStyle: { color: "rgba(0,0,0,0.06)" } },
    },
    series: [
      { name: "平台费", type: "bar", stack: "cost", data: dailyChannels.map((d) => d.平台费), itemStyle: { color: "#D9261C" }, barMaxWidth: 30 },
      { name: "营销", type: "bar", stack: "cost", data: dailyChannels.map((d) => d.营销), itemStyle: { color: "#64748b" } },
      { name: "包装", type: "bar", stack: "cost", data: dailyChannels.map((d) => d.包装), itemStyle: { color: "#f59e0b" } },
    ],
  };

  return (
    <ModulePage module={getModule("/channels")}>
      <div className="space-y-4">
        {!initialized && <div className="h-0.5 w-full animate-pulse rounded-full bg-primary/30" />}
        {loadError && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-red-800">⚠️ {loadError}</p>
              <button onClick={fetchData} className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white">重试</button>
            </div>
          </div>
        )}
        {initialized && !hasData ? (
          <div className="rounded-2xl border border-dashed border-white/60 bg-white/35 p-8 text-center">
            <p className="text-sm font-medium text-on-background">还没有经营数据</p>
            <p className="mt-1 text-xs text-on-surface-variant">录入含外卖订单的日报后这里会出现渠道分析</p>
          </div>
        ) : hasData ? (
          <>
          {/* KPI */}
          <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
            <Kpi label="外卖占比" value={`${(deliveryRatio * 100).toFixed(0)}%`} sub={`${deliveryOrders}单`} tone={deliveryRatio > 0.45 ? "watch" : "good"} />
            <Kpi label="外卖营收" value={`¥${(deliveryRev / 1000).toFixed(1)}k`} sub={hasRealDelivery ? "真实数据" : "估算"} tone={hasRealDelivery ? "good" : "info"} />
            <Kpi label="到手利润" value={`¥${(deliveryProfit / 1000).toFixed(1)}k`} sub={deliveryRev > 0 ? `${(deliveryProfit / deliveryRev * 100).toFixed(0)}%` : "—"} tone={deliveryProfit > 0 ? "good" : "risk"} />
            <Kpi label="平台费率" value={`${deliveryRev > 0 ? (platformFee / deliveryRev * 100).toFixed(1) : 0}%`} sub="佣金+服务费" tone={platformFee / Math.max(deliveryRev, 1) > 0.20 ? "risk" : "watch"} />
            <Kpi label="包装成本" value={`¥${packagingCost.toFixed(0)}`} sub={`${deliveryOrders > 0 ? (packagingCost / deliveryOrders).toFixed(1) : 0}/单`} tone="info" />
          </div>

          {/* 渠道利润对比 */}
          <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-on-surface-variant">渠道利润对比</p>
              <span className="text-[10px] text-on-surface-variant">共享成本按营收比例分摊</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-emerald-50/50 p-3 ring-1 ring-emerald-100">
                <p className="text-[11px] font-medium text-emerald-700">堂食</p>
                <p className="mt-1 text-lg font-bold tabular-nums text-stone-950">¥{dineInProfit.toFixed(0)}</p>
                <p className="text-[10px] text-stone-500">利润率 {(dineInMargin * 100).toFixed(0)}%</p>
                <div className="mt-2 space-y-1 text-[10px] text-stone-600">
                  <div className="flex justify-between"><span>营收</span><span className="tabular-nums">¥{dineInRev.toFixed(0)}</span></div>
                  <div className="flex justify-between"><span>订单</span><span className="tabular-nums">{dineInOrders}单</span></div>
                  <div className="flex justify-between"><span>单均利润</span><span className="font-semibold tabular-nums text-emerald-700">¥{dineInProfitPerOrder.toFixed(1)}</span></div>
                </div>
              </div>
              <div className="rounded-xl bg-amber-50/50 p-3 ring-1 ring-amber-100">
                <p className="text-[11px] font-medium text-amber-700">外卖</p>
                <p className="mt-1 text-lg font-bold tabular-nums text-stone-950">¥{deliveryNetProfit.toFixed(0)}</p>
                <p className="text-[10px] text-stone-500">利润率 {(deliveryMargin * 100).toFixed(0)}%</p>
                <div className="mt-2 space-y-1 text-[10px] text-stone-600">
                  <div className="flex justify-between"><span>营收</span><span className="tabular-nums">¥{deliveryRev.toFixed(0)}</span></div>
                  <div className="flex justify-between"><span>订单</span><span className="tabular-nums">{deliveryOrders}单</span></div>
                  <div className="flex justify-between"><span>单均利润</span><span className="font-semibold tabular-nums text-amber-700">¥{deliveryProfitPerOrder.toFixed(1)}</span></div>
                </div>
              </div>
            </div>
            {dineInOrders > 0 && deliveryOrders > 0 && (
              <div className="mt-3 rounded-xl bg-white/55 p-2.5 text-center text-xs">
                {dineInProfitPerOrder > deliveryProfitPerOrder
                  ? <span className="text-emerald-700">堂食单均利润高 ¥{(dineInProfitPerOrder - deliveryProfitPerOrder).toFixed(1)}，优先推堂食引流</span>
                  : <span className="text-amber-700">外卖单均利润高 ¥{(deliveryProfitPerOrder - dineInProfitPerOrder).toFixed(1)}，可加大外卖投放</span>}
              </div>
            )}
          </div>

          {/* 平台明细缺失提示 */}
          <div className="rounded-2xl border border-dashed border-stone-200 bg-stone-50/50 p-3">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-stone-100 text-stone-500">
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" /></svg>
              </span>
              <p className="text-xs font-medium text-stone-700">平台利润明细（美团/抖音/淘宝闪购）需要上传各平台后台截图</p>
            </div>
            <p className="mt-1.5 pl-8 text-[10px] text-stone-500">当前外卖数据为合并值。上传截图后 AI 会按平台拆分营收、佣金和订单，生成单平台利润对比。</p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">

            {/* 堂食 vs 外卖 */}
            <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <p className="text-xs font-medium text-on-surface-variant">堂食 vs 外卖营收</p>
              <div className="mt-3 flex items-center gap-4">
                <div className="flex-1">
                  <div className="h-48">
                    <ReactEChartsCore echarts={echarts} option={channelBarOption} style={{ height: "100%" }} notMerge />
                  </div>
                </div>
                <div className="space-y-3 text-xs">
                  <div className="rounded-lg bg-white/55 px-3 py-2">
                    <p className="text-on-surface-variant">堂食订单</p>
                    <p className="font-bold text-on-background">{dineInOrders}单</p>
                  </div>
                  <div className="rounded-lg bg-white/55 px-3 py-2">
                    <p className="text-on-surface-variant">外卖订单</p>
                    <p className="font-bold text-on-background">{deliveryOrders}单</p>
                  </div>
                  <div className="rounded-lg bg-white/55 px-3 py-2">
                    <p className="text-on-surface-variant">外卖单均</p>
                    <p className="font-bold text-on-background">¥{deliveryOrders > 0 ? (deliveryRev / deliveryOrders).toFixed(0) : 0}</p>
                  </div>
                </div>
              </div>
            </div>

            {/* 外卖到手利润 */}
            <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <p className="text-xs font-medium text-on-surface-variant">外卖到手利润拆解</p>
              <div className="mt-3 space-y-3">
                <div className="flex items-center justify-between rounded-xl bg-white/55 px-4 py-2.5">
                  <span className="text-sm text-on-background">外卖营收</span>
                  <span className="text-sm font-bold text-on-background">¥{deliveryRev.toFixed(0)}</span>
                </div>
                <div className="flex items-center justify-between rounded-xl bg-red-50/60 px-4 py-2.5">
                  <span className="text-sm text-red-700">平台佣金</span>
                  <span className="text-sm font-bold text-red-700">-¥{platformFee.toFixed(0)}</span>
                </div>
                <div className="flex items-center justify-between rounded-xl bg-red-50/60 px-4 py-2.5">
                  <span className="text-sm text-red-700">营销活动</span>
                  <span className="text-sm font-bold text-red-700">-¥{marketingCost.toFixed(0)}</span>
                </div>
                <div className="flex items-center justify-between rounded-xl bg-red-50/60 px-4 py-2.5">
                  <span className="text-sm text-red-700">包装成本</span>
                  <span className="text-sm font-bold text-red-700">-¥{packagingCost.toFixed(0)}</span>
                </div>
                <div className={`flex items-center justify-between rounded-xl px-4 py-2.5 ${deliveryProfit >= 0 ? "bg-emerald-50/60" : "bg-red-100/60"}`}>
                  <span className={`text-sm font-semibold ${deliveryProfit >= 0 ? "text-emerald-700" : "text-red-700"}`}>到手利润</span>
                  <span className={`text-sm font-bold ${deliveryProfit >= 0 ? "text-emerald-700" : "text-red-700"}`}>¥{deliveryProfit.toFixed(0)}</span>
                </div>
              </div>
            </div>

            {/* 外卖成本趋势 */}
            <div className="rounded-2xl border border-white/45 bg-white/42 p-4 md:col-span-2">
              <p className="text-xs font-medium text-on-surface-variant">外卖成本日趋势（近14天）</p>
              <div className="mt-3 h-64">
                <ReactEChartsCore echarts={echarts} option={costTrendOption} style={{ height: "100%" }} notMerge />
              </div>
            </div>

          </div>
        </>
        ) : null}
      </div>
    </ModulePage>
  );
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub: string; tone: "good" | "watch" | "risk" | "info" }) {
  const dot = tone === "good" ? "bg-emerald-400" : tone === "risk" ? "bg-red-400" : tone === "watch" ? "bg-amber-400" : "bg-blue-400";
  return (
    <div className="rounded-2xl border border-white/45 bg-white/42 px-3 py-2.5">
      <p className="text-[10px] text-on-surface-variant">{label}</p>
      <p className="mt-0.5 text-lg font-bold text-on-background">{value}</p>
      <div className="mt-0.5 flex items-center gap-1">
        <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
        <p className="text-[10px] text-on-surface-variant">{sub}</p>
      </div>
    </div>
  );
}
