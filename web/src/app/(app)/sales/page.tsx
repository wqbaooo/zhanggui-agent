"use client";

import { useCallback, useEffect, useState } from "react";
import ReactEChartsCore from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { CloudRain, Sun, Store, Wallet } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { DEFAULT_PROJECT_ID, getOperations, getWeather, type DailyOperationEntry, type WeatherForecast } from "@/lib/api";
import { calcEntryNetProfit, sumEntries } from "@/domain/calculations";

echarts.use([BarChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer]);

const weekdayLabels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
type RangeKey = 7 | 14 | 30;

function movingAvg(data: number[], windowSize: number): (number | null)[] {
  return data.map((_, i) => {
    const start = Math.max(0, i - windowSize + 1);
    const slice = data.slice(start, i + 1);
    return Math.round(slice.reduce((s, v) => s + v, 0) / slice.length);
  });
}

const weatherLabel: Record<string, string> = {
  sunny: "晴", cloudy: "多云", overcast: "阴",
  light_rain: "小雨", heavy_rain: "大雨", thunderstorm: "雷雨",
  snow: "雪", fog: "雾",
};

function isRainy(w: string) { return w.includes("rain") || w === "thunderstorm"; }

export default function SalesPage() {
  const [entries, setEntries] = useState<DailyOperationEntry[]>([]);
  const [forecast, setForecast] = useState<WeatherForecast[]>([]);
  const [initialized, setInitialized] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [range, setRange] = useState<RangeKey>(14);

  const fetchData = useCallback(async () => {
    setLoadError(null);
    try {
      const ops = await getOperations(DEFAULT_PROJECT_ID, 30);
      setEntries(ops.entries);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "加载失败，请检查后端服务");
    } finally {
      setInitialized(true);
    }

    try {
      const weather = await getWeather();
      setForecast(weather.forecast);
    } catch {
      setForecast([]);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filtered = entries.slice(-range);

  // 建立日期 → 天气 映射
  const weatherMap = new Map(forecast.map((f) => [f.date, f]));

  // 按周几聚合
  const byWeekday = weekdayLabels.map((day, idx) => {
    const matches = entries.filter((e) => {
      const d = new Date(e.date + "T00:00:00");
      return !isNaN(d.getTime()) && d.getDay() === (idx + 1) % 7;
    });
    const days = matches.length;
    return {
      name: day,
      营收: days > 0 ? Math.round(matches.reduce((s, e) => s + e.revenue, 0) / days) : 0,
      订单: days > 0 ? Math.round(matches.reduce((s, e) => s + e.orders, 0) / days) : 0,
      天数: days,
    };
  });

  // 天气影响统计
  const rainyDays = filtered.filter((e) => {
    const w = weatherMap.get(e.date);
    return w && isRainy(w.weather);
  });
  const sunnyDays = filtered.filter((e) => {
    const w = weatherMap.get(e.date);
    return w && !isRainy(w.weather);
  });
  const rainyAvg = rainyDays.length > 0 ? Math.round(rainyDays.reduce((s, e) => s + e.revenue, 0) / rainyDays.length) : 0;
  const sunnyAvg = sunnyDays.length > 0 ? Math.round(sunnyDays.reduce((s, e) => s + e.revenue, 0) / sunnyDays.length) : 0;
  const weatherImpact = sunnyAvg > 0 ? ((rainyAvg - sunnyAvg) / sunnyAvg * 100) : null;

  // 日趋势
  const dates = filtered.map((e) => e.date.slice(5));
  const revenues = filtered.map((e) => e.revenue);
  const orders = filtered.map((e) => e.orders);
  const profits = filtered.map((e) => Math.round(calcEntryNetProfit(e)));
  const revenueMA = movingAvg(revenues, 3);
  const weatherColors = filtered.map((e) => {
    const w = weatherMap.get(e.date);
    return w && isRainy(w.weather) ? "#64748b" : "#0F4C3A";
  });

  const totalRevenue = sumEntries(filtered, "revenue");
  const totalOrders = sumEntries(filtered, "orders");
  const avgOrderValue = totalOrders > 0 ? totalRevenue / totalOrders : 0;
  const weekendAvg = byWeekday.slice(5).reduce((s, d) => s + d.营收, 0) / 2;
  const weekdayAvg = byWeekday.slice(0, 5).reduce((s, d) => s + d.营收, 0) / 5;

  // 周度对比 (本周 vs 上周)
  const today = new Date();
  const thisMonday = new Date(today); thisMonday.setDate(today.getDate() - (today.getDay() + 6) % 7);
  const lastMonday = new Date(thisMonday); lastMonday.setDate(thisMonday.getDate() - 7);
  const formatDate = (d: Date) => d.toISOString().slice(0, 10);
  const thisWeek = entries.filter((e) => e.date >= formatDate(thisMonday) && e.date <= formatDate(today));
  const lastWeek = entries.filter((e) => e.date >= formatDate(lastMonday) && e.date < formatDate(thisMonday));
  const thisWeekRev = sumEntries(thisWeek, "revenue");
  const lastWeekRev = sumEntries(lastWeek, "revenue");
  const thisWeekOrders = sumEntries(thisWeek, "orders");
  const lastWeekOrders = sumEntries(lastWeek, "orders");
  const wowRevPct = lastWeekRev > 0 ? ((thisWeekRev - lastWeekRev) / lastWeekRev * 100) : null;
  const wowOrdersPct = lastWeekOrders > 0 ? ((thisWeekOrders - lastWeekOrders) / lastWeekOrders * 100) : null;

  // 渠道对账聚合
  const channelMap = new Map<string, { orders: number; original: number; actual: number; actualKnown: boolean }>();
  let hasChannelData = false;
  filtered.forEach((e) => {
    e.channel_breakdown?.forEach((c) => {
      hasChannelData = true;
      const cur = channelMap.get(c.channel) || { orders: 0, original: 0, actual: 0, actualKnown: false };
      cur.orders += c.orders;
      cur.original += c.original_amount;
      if (c.actual_revenue != null) {
        cur.actual += c.actual_revenue;
        cur.actualKnown = true;
      }
      channelMap.set(c.channel, cur);
    });
  });
  const channelList = hasChannelData
    ? Array.from(channelMap.entries()).map(([channel, v]) => ({
        channel,
        ...v,
        discountRate: v.actualKnown && v.original > 0 ? (v.original - v.actual) / v.original : null,
      }))
    : [];

  // 支付方式聚合
  const paymentMap = new Map<string, { orders: number; amount: number }>();
  let hasPaymentData = false;
  filtered.forEach((e) => {
    e.payment_methods?.forEach((p) => {
      hasPaymentData = true;
      const cur = paymentMap.get(p.method) || { orders: 0, amount: 0 };
      cur.orders += p.orders;
      cur.amount += p.amount;
      paymentMap.set(p.method, cur);
    });
  });
  const paymentList = hasPaymentData
    ? Array.from(paymentMap.entries()).map(([method, v]) => ({ method, ...v })).sort((a, b) => b.amount - a.amount)
    : [];

  // ECharts: 营收趋势 + 天气标注
  const revenueOption = {
    tooltip: {
      trigger: "axis" as const,
      backgroundColor: "rgba(255,255,255,0.92)",
      borderColor: "rgba(0,0,0,0.08)",
      borderWidth: 1,
      borderRadius: 12,
      textStyle: { color: "#1a1a1a", fontSize: 12 },
      formatter: (params: Array<Record<string, unknown>>) => {
        const p0 = params[0] as { name: string; value: number };
        const p1 = params[1] as { value: number } | undefined;
        const p2 = params[2] as { value: number } | undefined;
        const w = forecast.find((f) => f.date.slice(5) === p0.name);
        const wx = w ? `${weatherLabel[w.weather] || ""} ${w.temp_low}~${w.temp_high}°C` : "";
        return `${p0.name} ${wx}<br/>
          营收 ¥${p0.value?.toLocaleString() ?? "—"}<br/>
          3日均线 ¥${p1?.value?.toLocaleString() ?? "—"}<br/>
          净利 ¥${p2?.value?.toLocaleString() ?? "—"}`;
      },
    },
    legend: { data: ["营收", "3日均线", "净利"], bottom: 0, textStyle: { fontSize: 11, color: "#6b7280" } },
    grid: { left: 8, right: 16, top: 8, bottom: 60, containLabel: true },
    dataZoom: [
      { type: "slider", start: 0, end: 100, height: 20, bottom: 0, borderColor: "transparent", backgroundColor: "rgba(0,0,0,0.04)", fillerColor: "rgba(15,76,58,0.15)", handleStyle: { color: "#0F4C3A" }, textStyle: { fontSize: 10, color: "#6b7280" } },
      { type: "inside", start: 0, end: 100 },
    ],
    xAxis: {
      type: "category" as const,
      data: dates,
      axisLabel: { fontSize: 10, color: "#6b7280", rotate: dates.length > 14 ? 30 : 0 },
    },
    yAxis: {
      type: "value" as const,
      axisLabel: { fontSize: 10, color: "#6b7280", formatter: (v: number) => `¥${v}` },
      splitLine: { lineStyle: { color: "rgba(0,0,0,0.06)" } },
    },
    series: [
      {
        name: "营收",
        type: "line",
        data: revenues,
        smooth: true,
        lineStyle: { color: "#0F4C3A", width: 2 },
        symbol: "circle",
        symbolSize: (v: number, params: { dataIndex: number }) => {
          const w = weatherMap.get(filtered[params.dataIndex]?.date);
          return w && isRainy(w.weather) ? 8 : 5;
        },
        itemStyle: {
          color: (params: { dataIndex: number }) => weatherColors[params.dataIndex],
          borderColor: (params: { dataIndex: number }) => {
            const w = weatherMap.get(filtered[params.dataIndex]?.date);
            return w && isRainy(w.weather) ? "#94a3b8" : "#0F4C3A";
          },
          borderWidth: 1,
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(15,76,58,0.2)" },
            { offset: 1, color: "rgba(15,76,58,0)" },
          ]),
        },
      },
      {
        name: "3日均线",
        type: "line",
        data: revenueMA,
        smooth: true,
        lineStyle: { color: "#c8a64e", width: 1.5, type: "dashed" },
        itemStyle: { color: "#c8a64e" },
        symbol: "none",
      },
      {
        name: "净利",
        type: "line",
        data: profits,
        smooth: true,
        lineStyle: { color: "#D9261C", width: 1 },
        itemStyle: { color: "#D9261C" },
        symbol: "none",
      },
    ],
  };

  // 周几对比
  const weekdayOption = {
    tooltip: {
      trigger: "axis" as const,
      backgroundColor: "rgba(255,255,255,0.92)",
      borderColor: "rgba(0,0,0,0.08)",
      borderRadius: 12,
      textStyle: { color: "#1a1a1a", fontSize: 12 },
    },
    grid: { left: 8, right: 8, top: 8, bottom: 24, containLabel: true },
    xAxis: {
      type: "category" as const,
      data: byWeekday.map((d) => d.name),
      axisLabel: { fontSize: 10, color: "#6b7280" },
    },
    yAxis: {
      type: "value" as const,
      axisLabel: { fontSize: 10, color: "#6b7280", formatter: (v: number) => `¥${v}` },
      splitLine: { lineStyle: { color: "rgba(0,0,0,0.06)" } },
    },
    series: [{
      name: "日均营收",
      type: "bar",
      data: byWeekday.map((d) => d.营收),
      itemStyle: { color: "#0F4C3A", borderRadius: [4, 4, 0, 0] },
      barMaxWidth: 32,
    }],
  };

  // 渠道占比
  const channelPieOption = channelList.length > 0 ? {
    tooltip: { trigger: "item" as const, backgroundColor: "rgba(255,255,255,0.92)", borderColor: "rgba(0,0,0,0.08)", borderRadius: 12, textStyle: { color: "#1a1a1a", fontSize: 12 }, formatter: "{b}<br/>实收 ¥{c}<br/>占比 {d}%" },
    legend: { orient: "vertical" as const, right: 0, top: "center", textStyle: { fontSize: 10, color: "#6b7280" }, itemWidth: 10, itemHeight: 10 },
    color: ["#0F4C3A", "#c8a64e", "#D9261C", "#64748b", "#0ea5e9"],
    series: [{
      type: "pie" as const,
      radius: ["45%", "72%"],
      center: ["35%", "50%"],
      avoidLabelOverlap: false,
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 12, fontWeight: "bold" } },
      data: channelList.map((c) => ({ name: c.channel, value: Math.round(c.actualKnown ? c.actual : c.original) })),
    }],
  } : null;

  // 支付方式
  const paymentBarOption = paymentList.length > 0 ? {
    tooltip: { trigger: "axis" as const, axisPointer: { type: "shadow" }, backgroundColor: "rgba(255,255,255,0.92)", borderColor: "rgba(0,0,0,0.08)", borderRadius: 12, textStyle: { color: "#1a1a1a", fontSize: 12 }, formatter: (params: Array<Record<string, unknown>>) => {
      const p = params[0] as { name: string; value: number };
      const item = paymentList.find((x) => x.method === p.name);
      return `${p.name}<br/>金额 ¥${p.value?.toLocaleString() ?? "—"}<br/>订单 ${item?.orders ?? "—"}`;
    }},
    grid: { left: 8, right: 16, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: "value" as const, axisLabel: { fontSize: 10, color: "#6b7280", formatter: (v: number) => `¥${v}` }, splitLine: { lineStyle: { color: "rgba(0,0,0,0.06)" } } },
    yAxis: { type: "category" as const, data: paymentList.map((p) => p.method), axisLabel: { fontSize: 10, color: "#6b7280" } },
    series: [{ type: "bar" as const, data: paymentList.map((p) => Math.round(p.amount)), itemStyle: { color: "#0F4C3A", borderRadius: [0, 4, 4, 0] }, barMaxWidth: 18 }],
  } : null;

  // 订单趋势
  const orderOption = {
    tooltip: {
      trigger: "axis" as const,
      backgroundColor: "rgba(255,255,255,0.92)",
      borderColor: "rgba(0,0,0,0.08)",
      borderRadius: 12,
      textStyle: { color: "#1a1a1a", fontSize: 12 },
    },
    grid: { left: 8, right: 8, top: 8, bottom: 24, containLabel: true },
    xAxis: {
      type: "category" as const,
      data: dates,
      axisLabel: { fontSize: 10, color: "#6b7280", rotate: dates.length > 14 ? 30 : 0 },
    },
    yAxis: {
      type: "value" as const,
      axisLabel: { fontSize: 10, color: "#6b7280" },
      splitLine: { lineStyle: { color: "rgba(0,0,0,0.06)" } },
    },
    series: [{
      name: "订单",
      type: "bar",
      data: orders,
      itemStyle: { color: "#c8a64e", borderRadius: [4, 4, 0, 0] },
      barMaxWidth: 24,
    }],
  };

  return (
    <ModulePage module={getModule("/sales")}>
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
        {initialized && entries.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/60 bg-white/35 p-8 text-center">
            <p className="text-sm font-medium text-on-background">还没有营业数据</p>
            <p className="mt-1 text-xs text-on-surface-variant">在首页录入日报后这里会出现趋势图</p>
          </div>
        ) : filtered.length > 0 ? (
          <>
          {/* KPI 行 */}
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <Kpi label="累计营收" value={`¥${(totalRevenue / 1000).toFixed(1)}k`} sub={`${filtered.length}天`} />
            <Kpi label="日均营收" value={`¥${Math.round(totalRevenue / filtered.length)}`} sub={`${totalOrders}单`} />
            <Kpi label="客单价" value={`¥${avgOrderValue.toFixed(0)}`} sub="均价" />
            <Kpi label="周末/平日" value={`${(weekendAvg / Math.max(weekdayAvg, 1) * 100).toFixed(0)}%`} sub={weekendAvg > weekdayAvg ? "周末更高" : "平日更高"} />
          </div>

          {/* 天气影响 */}
          {rainyDays.length > 0 || sunnyDays.length > 0 ? (
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              <div className="rounded-2xl border border-white/45 bg-white/42 px-3 py-2.5 flex items-center gap-2">
                <Sun className="h-4 w-4 text-amber-500" />
                <div>
                  <p className="text-[10px] text-on-surface-variant">晴天日均</p>
                  <p className="text-sm font-bold text-on-background">¥{sunnyAvg}{sunnyDays.length > 0 ? ` (${sunnyDays.length}天)` : ""}</p>
                </div>
              </div>
              <div className="rounded-2xl border border-white/45 bg-white/42 px-3 py-2.5 flex items-center gap-2">
                <CloudRain className="h-4 w-4 text-slate-500" />
                <div>
                  <p className="text-[10px] text-on-surface-variant">雨天日均</p>
                  <p className="text-sm font-bold text-on-background">¥{rainyAvg}{rainyDays.length > 0 ? ` (${rainyDays.length}天)` : ""}</p>
                </div>
              </div>
              <div className="rounded-2xl border border-white/45 bg-white/42 px-3 py-2.5">
                <p className="text-[10px] text-on-surface-variant">雨天影响</p>
                <p className={`text-sm font-bold ${weatherImpact != null && weatherImpact < -10 ? "text-red-500" : "text-on-background"}`}>
                  {weatherImpact != null ? `${weatherImpact > 0 ? "+" : ""}${weatherImpact}%` : "—"}
                </p>
              </div>
              <div className="rounded-2xl border border-white/45 bg-white/42 px-3 py-2.5">
                <p className="text-[10px] text-on-surface-variant">天气数据</p>
                <p className="text-sm font-bold text-on-background">{forecast.length > 0 ? `${forecast.length}天` : "无"}</p>
              </div>
            </div>
          ) : null}

          {/* 周度对比 */}
          {thisWeek.length > 0 && lastWeek.length > 0 ? (
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              <div className="rounded-2xl border border-white/45 bg-white/42 px-3 py-2.5">
                <p className="text-[10px] text-on-surface-variant">本周营收</p>
                <p className="text-sm font-bold text-on-background">¥{(thisWeekRev / 1000).toFixed(1)}k</p>
                <p className="text-[10px] text-on-surface-variant">{thisWeek.length}天</p>
              </div>
              <div className="rounded-2xl border border-white/45 bg-white/42 px-3 py-2.5">
                <p className="text-[10px] text-on-surface-variant">上周营收</p>
                <p className="text-sm font-bold text-on-background">¥{(lastWeekRev / 1000).toFixed(1)}k</p>
                <p className="text-[10px] text-on-surface-variant">{lastWeek.length}天</p>
              </div>
              <div className="rounded-2xl border border-white/45 bg-white/42 px-3 py-2.5">
                <p className="text-[10px] text-on-surface-variant">周环比营收</p>
                <p className={`text-sm font-bold ${wowRevPct != null ? (wowRevPct >= 0 ? "text-emerald-600" : "text-red-500") : "text-on-background"}`}>
                  {wowRevPct != null ? `${wowRevPct > 0 ? "+" : ""}${wowRevPct.toFixed(1)}%` : "—"}
                </p>
              </div>
              <div className="rounded-2xl border border-white/45 bg-white/42 px-3 py-2.5">
                <p className="text-[10px] text-on-surface-variant">周环比订单</p>
                <p className={`text-sm font-bold ${wowOrdersPct != null ? (wowOrdersPct >= 0 ? "text-emerald-600" : "text-red-500") : "text-on-background"}`}>
                  {wowOrdersPct != null ? `${wowOrdersPct > 0 ? "+" : ""}${wowOrdersPct.toFixed(1)}%` : "—"}
                </p>
              </div>
            </div>
          ) : null}

          {/* 天数切换 */}
          <div className="flex gap-1">
            {([7, 14, 30] as RangeKey[]).map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`rounded-lg px-3 py-1 text-xs font-medium transition-colors ${
                  range === r ? "bg-primary text-on-primary" : "bg-white/35 text-on-surface-variant hover:bg-white/55"
                }`}
              >
                {r}天
              </button>
            ))}
          </div>

          {/* 日营收趋势 + 天气标注 */}
          <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <div className="flex items-center gap-2">
              <p className="text-xs font-medium text-on-surface-variant">日营收趋势 + 3日均线</p>
              <span className="flex items-center gap-1 text-[10px] text-on-surface-variant">
                <span className="h-2 w-2 rounded-full bg-slate-400" />雨天
                <span className="h-2 w-2 rounded-full bg-[#0F4C3A]" />晴/多云
              </span>
            </div>
            <div className="mt-3 h-72">
              <ReactEChartsCore echarts={echarts} option={revenueOption} style={{ height: "100%" }} notMerge />
            </div>
          </div>

          {/* 周几对比 + 订单趋势 */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <p className="text-xs font-medium text-on-surface-variant">周几营收对比</p>
              <div className="mt-3 h-56">
                <ReactEChartsCore echarts={echarts} option={weekdayOption} style={{ height: "100%" }} notMerge />
              </div>
            </div>

            <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <p className="text-xs font-medium text-on-surface-variant">日订单趋势</p>
              <div className="mt-3 h-56">
                <ReactEChartsCore echarts={echarts} option={orderOption} style={{ height: "100%" }} notMerge />
              </div>
            </div>
          </div>

          {/* 渠道对账 */}
          {channelList.length > 0 && channelPieOption && (
            <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <div className="mb-3 flex items-center gap-2">
                <Store className="h-4 w-4 text-primary" />
                <p className="text-sm font-bold text-on-background">渠道对账</p>
                <span className="ml-auto text-[10px] text-on-surface-variant">原价 → 优惠 → 实收</span>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="h-56">
                  <ReactEChartsCore echarts={echarts} option={channelPieOption} style={{ height: "100%" }} notMerge />
                </div>
                <div className="space-y-2">
                  {channelList.map((c) => (
                    <div key={c.channel} className="flex items-center justify-between rounded-xl bg-white/50 px-3 py-2">
                      <div>
                        <p className="text-xs font-semibold text-on-background">{c.channel}</p>
                        <p className="text-[10px] text-on-surface-variant">{c.orders} 单</p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs font-bold text-on-background">{c.actualKnown ? `¥${Math.round(c.actual).toLocaleString()}` : "实收待拆分"}</p>
                        <p className="text-[10px] text-amber-600">{c.discountRate != null ? `-${Math.round(c.discountRate * 100)}%` : "订单金额"}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* 支付方式 */}
          {paymentList.length > 0 && paymentBarOption && (
            <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <div className="mb-3 flex items-center gap-2">
                <Wallet className="h-4 w-4 text-primary" />
                <p className="text-sm font-bold text-on-background">支付方式</p>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="h-56">
                  <ReactEChartsCore echarts={echarts} option={paymentBarOption} style={{ height: "100%" }} notMerge />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {paymentList.map((p) => (
                    <div key={p.method} className="rounded-xl bg-white/50 px-3 py-2">
                      <p className="text-[10px] text-on-surface-variant">{p.method}</p>
                      <p className="text-sm font-bold text-on-background">¥{Math.round(p.amount).toLocaleString()}</p>
                      <p className="text-[10px] text-on-surface-variant">{p.orders} 单</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
        ) : null}
      </div>
    </ModulePage>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-2xl border border-white/45 bg-white/42 px-3 py-2.5">
      <p className="text-[10px] text-on-surface-variant">{label}</p>
      <p className="mt-0.5 text-lg font-bold text-on-background">{value}</p>
      <p className="text-[10px] text-on-surface-variant">{sub}</p>
    </div>
  );
}
