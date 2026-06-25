"use client";

import { useCallback, useEffect, useState } from "react";
import { TrendingDown, TrendingUp } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { DEFAULT_PROJECT_ID, getOperations, type DailyOperationEntry } from "@/lib/api";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";

const weekdayLabels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

export default function SalesPage() {
  const [entries, setEntries] = useState<DailyOperationEntry[]>([]);
  const [initialized, setInitialized] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const res = await getOperations(DEFAULT_PROJECT_ID, 30);
      setEntries(res.entries);
    } catch { /* offline */ }
    setInitialized(true);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

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

  // 日趋势
  const dailyTrend = entries
    .map((e) => ({ date: e.date.slice(5), 营收: e.revenue, 订单: e.orders, 食材成本: e.food_cost, 净利: e.revenue - e.food_cost - e.labor - e.rent_allocated - e.utility - e.other_cost - e.platform_fee - e.marketing_cost - e.inventory_loss }))
    .slice(-14);

  const totalRevenue = entries.reduce((s, e) => s + e.revenue, 0);
  const totalOrders = entries.reduce((s, e) => s + e.orders, 0);
  const avgOrderValue = totalOrders > 0 ? totalRevenue / totalOrders : 0;
  const weekendAvg = byWeekday.slice(5).reduce((s, d) => s + d.营收, 0) / 2;
  const weekdayAvg = byWeekday.slice(0, 5).reduce((s, d) => s + d.营收, 0) / 5;

  return (
    <ModulePage module={getModule("/sales")}>
      <div className="space-y-4">
        {!initialized && <div className="h-0.5 w-full animate-pulse rounded-full bg-primary/30" />}
        {initialized && entries.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/60 bg-white/35 p-8 text-center">
            <p className="text-sm font-medium text-on-background">还没有营业数据</p>
            <p className="mt-1 text-xs text-on-surface-variant">在首页录入日报后这里会出现趋势图</p>
          </div>
        ) : entries.length > 0 ? (
          <>

          {/* KPI 行 */}
          <div className="grid grid-cols-4 gap-2">
            <Kpi label="累计营收" value={`¥${(totalRevenue / 1000).toFixed(1)}k`} sub={`${entries.length}天`} />
            <Kpi label="日均营收" value={`¥${Math.round(totalRevenue / entries.length)}`} sub={`${totalOrders}单`} />
            <Kpi label="客单价" value={`¥${avgOrderValue.toFixed(0)}`} sub="人均" />
            <Kpi label="周末/平日" value={`${(weekendAvg / Math.max(weekdayAvg, 1) * 100).toFixed(0)}%`} sub={weekendAvg > weekdayAvg ? "周末更高" : "平日更高"} />
          </div>

          {/* 日营收趋势 */}
          <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <p className="text-xs font-medium text-on-surface-variant">日营收趋势（近14天）</p>
            <div className="mt-3 h-64">
              <ResponsiveContainer>
                <AreaChart data={dailyTrend}>
                  <defs>
                    <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#0F4C3A" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#0F4C3A" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.3)" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#6b7280" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#6b7280" }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: 16, border: "1px solid rgba(255,255,255,0.5)", background: "rgba(255,255,255,0.85)", backdropFilter: "blur(12px)", fontSize: 12 }} />
                  <Area type="monotone" dataKey="营收" stroke="#0F4C3A" strokeWidth={2} fill="url(#revenueGrad)" dot={{ r: 3, fill: "#0F4C3A" }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 周几对比 + 订单趋势 */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <p className="text-xs font-medium text-on-surface-variant">周几营收对比</p>
              <div className="mt-3 h-56">
                <ResponsiveContainer>
                  <BarChart data={byWeekday}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.3)" />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#6b7280" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: "#6b7280" }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ borderRadius: 16, border: "1px solid rgba(255,255,255,0.5)", background: "rgba(255,255,255,0.85)", backdropFilter: "blur(12px)", fontSize: 12 }} />
                    <Bar dataKey="营收" fill="#0F4C3A" radius={[6, 6, 0, 0]} maxBarSize={40} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <p className="text-xs font-medium text-on-surface-variant">日订单趋势</p>
              <div className="mt-3 h-56">
                <ResponsiveContainer>
                  <BarChart data={dailyTrend}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.3)" />
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#6b7280" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: "#6b7280" }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ borderRadius: 16, border: "1px solid rgba(255,255,255,0.5)", background: "rgba(255,255,255,0.85)", backdropFilter: "blur(12px)", fontSize: 12 }} />
                    <Bar dataKey="订单" fill="#c8a64e" radius={[6, 6, 0, 0]} maxBarSize={40} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

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
