"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, DollarSign, Percent, TrendingDown } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { DEFAULT_PROJECT_ID, getOperationSummary, getOperations, type DailyOperationEntry, type OperationSummary } from "@/lib/api";
import {
  Area, AreaChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const COST_COLORS = ["#D9261C", "#c8a64e", "#64748b", "#0ea5e9", "#84cc16", "#8b5cf6", "#f59e0b"];
const PROFIT_COLORS = ["#0F4C3A", "#D9261C"];

export default function ProfitPage() {
  const [summary, setSummary] = useState<OperationSummary | null>(null);
  const [entries, setEntries] = useState<DailyOperationEntry[]>([]);
  const [initialized, setInitialized] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [sum, ops] = await Promise.all([
        getOperationSummary(DEFAULT_PROJECT_ID, 30),
        getOperations(DEFAULT_PROJECT_ID, 30),
      ]);
      setSummary(sum);
      setEntries(ops.entries);
    } catch { /* offline */ }
    setInitialized(true);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const hasData = summary && summary.entry_count > 0;

  // 成本饼图数据
  const costPie = hasData ? [
    { name: "食材成本", value: Math.round(summary.food_cost_rate * 100) },
    { name: "人工", value: Math.round((summary.labor_cost_rate || 0) * 100) },
    { name: "房租", value: entries.reduce((s, e) => s + e.rent_allocated, 0) / Math.max(summary.total_revenue, 1) * 100 },
    { name: "平台费", value: Math.round(summary.total_orders > 0 ? (entries.reduce((s, e) => s + e.platform_fee, 0) / summary.total_revenue) * 100 : 0) },
    { name: "营销", value: entries.reduce((s, e) => s + e.marketing_cost, 0) / Math.max(summary.total_revenue, 1) * 100 },
    { name: "水电", value: entries.reduce((s, e) => s + e.utility, 0) / Math.max(summary.total_revenue, 1) * 100 },
    { name: "其他", value: entries.reduce((s, e) => s + e.other_cost + e.inventory_loss, 0) / Math.max(summary.total_revenue, 1) * 100 },
  ].filter((c) => c.value > 0).map((c) => ({ ...c, value: Math.round(c.value) })) : [];

  // 盈亏饼图
  const profitPie = hasData ? [
    { name: "净利", value: Math.max(0, Math.round(summary.net_profit)) },
    { name: "总成本", value: Math.max(0, Math.round(summary.total_cost)) },
  ] : [];

  // 日利润趋势
  const dailyProfit = entries.slice(-14).map((e) => {
    const cost = e.food_cost + e.labor + e.rent_allocated + e.utility + e.other_cost + e.platform_fee + e.marketing_cost + e.inventory_loss;
    const profit = e.revenue - cost;
    return {
      date: e.date.slice(5),
      营收: e.revenue,
      成本: Math.round(cost),
      净利: Math.round(profit),
    };
  });

  // 日均到盈亏平衡
  const breakEvenDaily = hasData && summary.total_revenue > 0
    ? Math.round((summary.total_cost / summary.entry_count))
    : null;
  const actualDaily = hasData ? Math.round(summary.total_revenue / summary.entry_count) : 0;

  return (
    <ModulePage module={getModule("/profit")}>
      <div className="space-y-4">
        {!initialized && <div className="h-0.5 w-full animate-pulse rounded-full bg-primary/30" />}
        {initialized && !hasData && (
          <div className="rounded-2xl border border-dashed border-white/60 bg-white/35 p-8 text-center">
            <p className="text-sm font-medium text-on-background">还没有经营数据</p>
            <p className="mt-1 text-xs text-on-surface-variant">在首页录入日报后这里会显示利润拆解</p>
          </div>
        )}
        {hasData && (
          <>

          {/* 顶部 KPI */}
          <div className="grid grid-cols-4 gap-2">
            <Kpi label="总营收" value={`¥${(summary.total_revenue / 1000).toFixed(1)}k`} sub={`${summary.entry_count}天`} tone="info" />
            <Kpi label="净利" value={`¥${(summary.net_profit / 1000).toFixed(1)}k`} sub={`${(summary.net_profit / Math.max(summary.total_revenue, 1) * 100).toFixed(0)}%`} tone={summary.net_profit > 0 ? "good" : "risk"} />
            <Kpi label="食材率" value={`${(summary.food_cost_rate * 100).toFixed(0)}%`} sub={summary.food_cost_rate > 0.38 ? "偏高" : "正常"} tone={summary.food_cost_rate > 0.38 ? "watch" : "good"} />
            <Kpi label="客单利润" value={`¥${(summary.net_profit / Math.max(summary.total_orders, 1)).toFixed(1)}`} sub="每单" tone="info" />
          </div>

          <div className="grid gap-4 md:grid-cols-2">

            {/* 利润趋势 */}
            <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <p className="text-xs font-medium text-on-surface-variant">营收 vs 成本 vs 净利</p>
              <div className="mt-3 h-64">
                <ResponsiveContainer>
                  <AreaChart data={dailyProfit}>
                    <defs>
                      <linearGradient id="profitGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#0F4C3A" stopOpacity={0.2} /><stop offset="100%" stopColor="#0F4C3A" stopOpacity={0} /></linearGradient>
                      <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#D9261C" stopOpacity={0.15} /><stop offset="100%" stopColor="#D9261C" stopOpacity={0} /></linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.3)" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#6b7280" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} axisLine={false} tickLine={false} width={50} />
                    <Tooltip contentStyle={{ borderRadius: 16, border: "1px solid rgba(255,255,255,0.5)", background: "rgba(255,255,255,0.85)", backdropFilter: "blur(12px)", fontSize: 12 }} />
                    <Area type="monotone" dataKey="营收" stroke="#0F4C3A" strokeWidth={2} fill="url(#profitGrad)" dot={false} />
                    <Area type="monotone" dataKey="成本" stroke="#D9261C" strokeWidth={1.5} fill="url(#costGrad)" dot={false} />
                    <Area type="monotone" dataKey="净利" stroke="#c8a64e" strokeWidth={2} fill="none" dot={{ r: 3, fill: "#c8a64e" }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* 保本线 */}
            <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <p className="text-xs font-medium text-on-surface-variant">保本分析</p>
              <div className="mt-3 space-y-3">
                <div className="flex items-center justify-between rounded-xl bg-white/55 px-4 py-3">
                  <span className="text-sm text-on-background">日均盈亏平衡线</span>
                  <span className="text-lg font-bold text-on-background">¥{breakEvenDaily ?? "-"}</span>
                </div>
                <div className="flex items-center justify-between rounded-xl bg-white/55 px-4 py-3">
                  <span className="text-sm text-on-background">当前日均营收</span>
                  <span className={`text-lg font-bold ${actualDaily >= (breakEvenDaily ?? Infinity) ? "text-emerald-600" : "text-red-600"}`}>¥{actualDaily}</span>
                </div>
                {breakEvenDaily && (
                  <div className="rounded-xl bg-white/55 p-3">
                    <div className="flex items-center justify-between text-xs text-on-surface-variant">
                      <span>保本进度</span>
                      <span>{Math.min(100, Math.round(actualDaily / breakEvenDaily * 100))}%</span>
                    </div>
                    <div className="mt-1.5 h-2.5 rounded-full bg-white/70">
                      <div className="h-2.5 rounded-full bg-emerald-500 transition-all duration-700" style={{ width: `${Math.min(100, actualDaily / breakEvenDaily * 100)}%` }} />
                    </div>
                  </div>
                )}
                {!breakEvenDaily && <p className="text-xs text-on-surface-variant">需要更多数据</p>}
              </div>
            </div>

            {/* 成本结构饼图 */}
            <div className="rounded-2xl border border-white/45 bg-white/42 p-4 md:col-span-2">
              <p className="text-xs font-medium text-on-surface-variant">成本结构占比</p>
              <div className="mt-3 flex flex-col items-center gap-6 md:flex-row">
                <div className="h-56 w-56">
                  {costPie.length > 0 ? (
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie data={costPie} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} innerRadius={55} strokeWidth={0}>
                          {costPie.map((_, i) => (<Cell key={i} fill={COST_COLORS[i % COST_COLORS.length]} />))}
                        </Pie>
                        <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid rgba(255,255,255,0.5)", background: "rgba(255,255,255,0.85)", backdropFilter: "blur(12px)", fontSize: 12 }} formatter={(v: unknown) => `${v}%`} />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : <p className="text-xs text-on-surface-variant">无数据</p>}
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {costPie.map((c, i) => (
                    <div key={c.name} className="flex items-center gap-2 rounded-lg bg-white/45 px-3 py-1.5">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: COST_COLORS[i % COST_COLORS.length] }} />
                      <span className="text-xs text-on-background">{c.name}</span>
                      <span className="text-xs font-semibold text-on-background">{c.value}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

          </div>
        </>
        )}
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
