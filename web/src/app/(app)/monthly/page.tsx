"use client";

import { useCallback, useEffect, useState } from "react";
import ReactEChartsCore from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { DEFAULT_PROJECT_ID, getMonthly, type MonthlySummary } from "@/lib/api";

echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer]);

const MONTH_NAMES = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];

export default function MonthlyPage() {
  const [data, setData] = useState<MonthlySummary | null>(null);
  const [initialized, setInitialized] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoadError(null);
    try {
      const res = await getMonthly(DEFAULT_PROJECT_ID);
      setData(res);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "加载失败，请检查后端服务");
    }
    setInitialized(true);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const months = data?.months ?? [];
  const hasData = months.length > 0;

  // MoM growth for months with revenue
  const monthsWithRevenue = months.filter((m) => m.revenue !== null);
  const lastTwoRevenue = monthsWithRevenue.slice(-2);
  const momPct = lastTwoRevenue.length >= 2 && lastTwoRevenue[0].revenue! > 0
    ? ((lastTwoRevenue[1].revenue! - lastTwoRevenue[0].revenue!) / lastTwoRevenue[0].revenue! * 100).toFixed(1)
    : null;

  // 不同指标并列展示，仅用于看经营规模与历史盈利基线，不计算伪同比。
  const barOption = {
    tooltip: {
      trigger: "axis" as const,
      axisPointer: { type: "shadow" as const },
      backgroundColor: "rgba(255,255,255,0.92)",
      borderColor: "rgba(0,0,0,0.08)",
      borderWidth: 1,
      borderRadius: 12,
      textStyle: { color: "#1a1a1a", fontSize: 12 },
      formatter: (params: Array<Record<string, unknown>>) => {
        const p0 = params[0] as { name: string; value: number; marker: string };
        const p1 = params[1] as { name: string; value: number; marker: string } | undefined;
        const m = months.find((x) => MONTH_NAMES[x.month - 1] === p0.name);
        const currentProfit = m?.net_profit;
        return `${p0.name}<br/>
          ${p0.marker} ${data?.current_year ?? "本年"}营业额 ¥${p0.value?.toLocaleString() ?? "—"}<br/>
          ${p1?.marker ?? ""} ${data?.baseline_year ?? "上年"}净利润 ¥${p1?.value?.toLocaleString() ?? "—"}<br/>
          ${currentProfit != null ? `本年净利润 ¥${currentProfit.toLocaleString()}` : "指标不同，不计算同比"}`;
      },
    },
    legend: { data: ["本年营业额", "上年净利润"], bottom: 0, textStyle: { fontSize: 11, color: "#6b7280" } },
    grid: { left: 8, right: 16, top: 8, bottom: 36, containLabel: true },
    dataZoom: [
      { type: "inside", start: 0, end: 100 },
    ],
    xAxis: {
      type: "category" as const,
      data: months.map((m) => MONTH_NAMES[m.month - 1]),
      axisLine: { lineStyle: { color: "#e5e7eb" } },
      axisTick: { show: false },
      axisLabel: { fontSize: 11, color: "#6b7280" },
    },
    yAxis: {
      type: "value" as const,
      axisLabel: { fontSize: 10, color: "#6b7280", formatter: (v: number) => v >= 10000 ? `${(v / 10000).toFixed(0)}万` : `${v}` },
      splitLine: { lineStyle: { color: "rgba(0,0,0,0.06)" } },
    },
    series: [
      {
        name: "本年营业额",
        type: "bar",
        data: months.map((m) => m.revenue ?? "-"),
        itemStyle: { color: "#0F4C3A", borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 24,
        barGap: "20%",
      },
      {
        name: "上年净利润",
        type: "bar",
        data: months.map((m) => m.last_year_profit),
        itemStyle: { color: "rgba(200,166,78,0.6)", borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 24,
      },
    ],
  };

  // YTD cumulative line
  const ytdOption = () => {
    let cumThis = 0;
    let cumLast = 0;
    const thisYear: number[] = [];
    const lastYear: number[] = [];
    for (const m of months) {
      if (m.revenue !== null) cumThis += m.revenue;
      cumLast += m.last_year_profit;
      thisYear.push(cumThis);
      lastYear.push(cumLast);
    }
    return {
      tooltip: {
        trigger: "axis" as const,
        backgroundColor: "rgba(255,255,255,0.92)",
        borderColor: "rgba(0,0,0,0.08)",
        borderWidth: 1,
        borderRadius: 12,
        textStyle: { color: "#1a1a1a", fontSize: 12 },
      formatter: (params: Array<Record<string, unknown>>) => {
        const p0 = params[0] as { name: string; value: number; seriesName: string; marker: string };
        return `${p0.seriesName}<br/>¥${p0.value?.toLocaleString() ?? "—"}`;
      },
      },
      legend: { data: ["本年累计营业额", "上年累计净利润"], bottom: 0, textStyle: { fontSize: 11, color: "#6b7280" } },
      grid: { left: 8, right: 16, top: 8, bottom: 32, containLabel: true },
      xAxis: {
        type: "category" as const,
        data: months.map((m) => MONTH_NAMES[m.month - 1]),
        axisLabel: { fontSize: 11, color: "#6b7280" },
      },
      yAxis: {
        type: "value" as const,
        axisLabel: { fontSize: 10, color: "#6b7280", formatter: (v: number) => v >= 10000 ? `${(v / 10000).toFixed(0)}万` : `${v}` },
        splitLine: { lineStyle: { color: "rgba(0,0,0,0.06)" } },
      },
      series: [
        { name: "本年累计营业额", type: "line", data: thisYear, smooth: true, lineStyle: { color: "#0F4C3A", width: 2 }, itemStyle: { color: "#0F4C3A" }, symbol: "circle", symbolSize: 5 },
        { name: "上年累计净利润", type: "line", data: lastYear, smooth: true, lineStyle: { color: "#c8a64e", width: 2, type: "dashed" }, itemStyle: { color: "#c8a64e" }, symbol: "circle", symbolSize: 5 },
      ],
    };
  };

  // Monthly profit margin line + bar
  const profitMarginOption = () => {
    const profitValues = months.map((m) => m.estimated_profit);
    const marginValues = months.map((m) => m.revenue && m.revenue > 0 ? ((m.estimated_profit ?? 0) / m.revenue * 100) : null);
    return {
      tooltip: {
        trigger: "axis" as const,
        backgroundColor: "rgba(255,255,255,0.92)",
        borderColor: "rgba(0,0,0,0.08)",
        borderWidth: 1,
        borderRadius: 12,
        textStyle: { color: "#1a1a1a", fontSize: 12 },
        formatter: (params: Array<Record<string, unknown>>) => {
          const p = params[0] as { name: string; value: number; seriesName: string; marker: string };
          if (p.seriesName === "已确认净利") return `${p.name}<br/>${p.marker} ¥${p.value?.toLocaleString() ?? "—"}`;
          return `${p.name}<br/>${p.marker} ${p.value != null ? Number(p.value).toFixed(1) + "%" : "—"}`;
        },
      },
      legend: { data: ["已确认净利", "利润率"], bottom: 0, textStyle: { fontSize: 11, color: "#6b7280" } },
      grid: { left: 8, right: 16, top: 8, bottom: 32, containLabel: true },
      xAxis: {
        type: "category" as const,
        data: months.map((m) => MONTH_NAMES[m.month - 1]),
        axisLabel: { fontSize: 11, color: "#6b7280" },
      },
      yAxis: [
        { type: "value" as const, name: "元", axisLabel: { fontSize: 10, color: "#6b7280", formatter: (v: number) => v >= 10000 ? `${(v / 10000).toFixed(0)}万` : `${v}` }, splitLine: { lineStyle: { color: "rgba(0,0,0,0.06)" } } },
        { type: "value" as const, name: "%", axisLabel: { fontSize: 10, color: "#6b7280", formatter: (v: number) => `${v}%` }, splitLine: { show: false } },
      ],
      series: [
        { name: "已确认净利", type: "bar", data: profitValues, yAxisIndex: 0, itemStyle: { color: "#0F4C3A", borderRadius: [4, 4, 0, 0] }, barMaxWidth: 28 },
        { name: "利润率", type: "line", data: marginValues, yAxisIndex: 1, smooth: true, lineStyle: { color: "#D9261C", width: 2 }, itemStyle: { color: "#D9261C" }, symbol: "circle", symbolSize: 5 },
      ],
    };
  };

  return (
    <ModulePage module={getModule("/monthly")}>
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
        {initialized && !hasData && (
          <div className="rounded-2xl border border-dashed border-white/60 bg-white/35 p-8 text-center">
            <p className="text-sm font-medium text-on-background">还没有月度数据</p>
            <p className="mt-1 text-xs text-on-surface-variant">录入月度营业款后可查看今年 vs 去年对比</p>
          </div>
        )}
        {hasData && (
          <>
            {/* KPI */}
            <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
              <Kpi label={`${data!.current_year ?? "本年"}累计营业额`} value={`¥${(data!.ytd_revenue / 10000).toFixed(1)}万`} sub={`${data!.months_with_revenue}个月`} />
              <Kpi label={`${data!.baseline_year ?? "上年"}累计净利润`} value={`¥${(data!.ytd_last_profit / 10000).toFixed(1)}万`} sub="历史盈利基线" />
              <Kpi label="月均营收" value={`¥${data!.avg_monthly_revenue.toLocaleString()}`} sub={data!.months_with_revenue > 0 ? "有数据月份" : ""} />
              <Kpi label="估算月固定成本" value={`¥${data!.estimated_monthly_cost.toLocaleString()}`} sub={`租金¥${data!.rent} + 人工¥${data!.labor} + 水电¥${data!.utility_avg}`} />
              <Kpi label="月环比" value={momPct ? `${Number(momPct) > 0 ? "+" : ""}${momPct}%` : "—"} sub="最近两月" />
            </div>

            {/* Year vs Year bar chart */}
            <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <p className="text-xs font-medium text-on-surface-variant">本年营业额与上年净利润基线（不同指标，不计算同比）</p>
              <div className="mt-3 h-80">
                <ReactEChartsCore echarts={echarts} option={barOption} style={{ height: "100%" }} notMerge />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {/* YTD cumulative */}
              <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
                <p className="text-xs font-medium text-on-surface-variant">累计经营规模与历史盈利基线</p>
                <div className="mt-3 h-64">
                  <ReactEChartsCore echarts={echarts} option={ytdOption()} style={{ height: "100%" }} notMerge />
                </div>
              </div>

              {/* Profit margin */}
              <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
                <p className="text-xs font-medium text-on-surface-variant">本年已确认净利润与利润率</p>
                <div className="mt-3 h-64">
                  <ReactEChartsCore echarts={echarts} option={profitMarginOption()} style={{ height: "100%" }} notMerge />
                </div>
              </div>
            </div>

            {/* Data table */}
            <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <p className="text-xs font-medium text-on-surface-variant">月度明细</p>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-white/60 text-left text-on-surface-variant">
                      <th className="py-2 pr-3 font-medium">月份</th>
                      <th className="py-2 pr-3 font-medium text-right">本年营业额</th>
                      <th className="py-2 pr-3 font-medium text-right">上年净利润</th>
                      <th className="py-2 pr-3 font-medium text-right">净利润同比</th>
                      <th className="py-2 pr-3 font-medium text-right">日均</th>
                      <th className="py-2 font-medium text-right">本年已确认净利</th>
                    </tr>
                  </thead>
                  <tbody>
                    {months.map((m) => (
                      <tr key={m.month} className="border-b border-white/30 text-on-background">
                        <td className="py-2 pr-3 font-medium">{MONTH_NAMES[m.month - 1]}</td>
                        <td className="py-2 pr-3 text-right">{m.revenue != null ? `¥${m.revenue.toLocaleString()}` : <span className="text-on-surface-variant">—</span>}</td>
                        <td className="py-2 pr-3 text-right">¥{m.last_year_profit.toLocaleString()}</td>
                        <td className={`py-2 pr-3 text-right ${m.yoy_pct != null ? (m.yoy_pct > 0 ? "text-emerald-600" : "text-red-500") : "text-on-surface-variant"}`}>
                          {m.yoy_pct != null ? `${m.yoy_pct > 0 ? "+" : ""}${m.yoy_pct}%` : "—"}
                        </td>
                        <td className="py-2 pr-3 text-right">{m.daily_avg != null ? `¥${m.daily_avg.toLocaleString()}` : "—"}</td>
                        <td className={`py-2 text-right ${m.estimated_profit != null ? (m.estimated_profit > 0 ? "text-emerald-600" : "text-red-500") : "text-on-surface-variant"}`}>
                          {m.estimated_profit != null ? `¥${m.estimated_profit.toLocaleString()}` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
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
