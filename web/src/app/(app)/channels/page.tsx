"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Smartphone, Truck, Zap } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { DEFAULT_PROJECT_ID, getOperations, type DailyOperationEntry } from "@/lib/api";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const CHANNEL_COLORS = ["#ffd100", "#ff6600", "#fe2c55", "#0F4C3A", "#c8a64e"];
const PLATFORM_META: Record<string, { label: string; icon: typeof Truck; color: string }> = {
  meituan: { label: "美团", icon: Truck, color: "#ffd100" },
  taobao: { label: "淘宝闪购", icon: Zap, color: "#ff6600" },
  douyin: { label: "抖音团购", icon: Smartphone, color: "#fe2c55" },
};

export default function ChannelsPage() {
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

  // 外卖 vs 堂食
  const totalTakeout = entries.reduce((s, e) => s + (e.takeout_orders || 0), 0);
  const totalOrders = entries.reduce((s, e) => s + e.orders, 0);
  const dineIn = totalOrders - totalTakeout;
  const takeoutRatio = totalOrders > 0 ? totalTakeout / totalOrders : 0;
  const totalPlatformFee = entries.reduce((s, e) => s + (e.platform_fee || 0), 0);
  const totalMarketing = entries.reduce((s, e) => s + (e.marketing_cost || 0), 0);
  const totalTakeoutRevenue = entries.reduce((s, e) => s + (e.takeout_orders || 0) * (e.revenue / Math.max(e.orders, 1)), 0);

  // 订单来源饼图
  const sourcePie = [
    { name: "堂食", value: Math.max(0, dineIn), color: "#0F4C3A" },
    { name: "外卖", value: Math.max(0, totalTakeout), color: "#c8a64e" },
  ];

  // 外卖日趋势
  const dailyTakeout = entries.slice(-14).map((e) => ({
    date: e.date.slice(5),
    外卖单: e.takeout_orders || 0,
    平台费: Math.round(e.platform_fee || 0),
    营销: Math.round(e.marketing_cost || 0),
  }));

  // 外卖成本拆解
  const costBreakdown = [
    { name: "平台佣金", value: Math.round(totalPlatformFee) },
    { name: "营销活动", value: Math.round(totalMarketing) },
  ].filter((c) => c.value > 0);

  // 渠道模拟数据（假设按 50/30/20 分配）
  const channelSplit = [
    { name: "美团", value: Math.round(totalTakeout * 0.5), color: "#ffd100" },
    { name: "淘宝闪购", value: Math.round(totalTakeout * 0.3), color: "#ff6600" },
    { name: "抖音", value: Math.round(totalTakeout * 0.2), color: "#fe2c55" },
  ];

  const hasTakeoutData = totalTakeout > 0;

  return (
    <ModulePage module={getModule("/channels")}>
      <div className="space-y-4">
        {!initialized && <div className="h-0.5 w-full animate-pulse rounded-full bg-primary/30" />}
        {initialized && entries.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/60 bg-white/35 p-8 text-center">
            <p className="text-sm font-medium text-on-background">还没有经营数据</p>
            <p className="mt-1 text-xs text-on-surface-variant">在首页录入包含外卖订单的日报后出现渠道分析</p>
          </div>
        ) : initialized && !hasTakeoutData ? (
          <div className="rounded-2xl border border-dashed border-white/60 bg-white/35 p-8 text-center">
            <Truck className="mx-auto h-8 w-8 text-on-surface-variant/40" />
            <p className="mt-3 text-sm font-medium text-on-background">暂无外卖数据</p>
            <p className="mt-1 text-xs text-on-surface-variant">录入日报时填写外卖订单数和平台费</p>
          </div>
        ) : hasTakeoutData ? (
          <>

          {/* KPI */}
          <div className="grid grid-cols-4 gap-2">
            <Kpi label="外卖占比" value={`${(takeoutRatio * 100).toFixed(0)}%`} sub={`${totalTakeout} 单`} tone={takeoutRatio > 0.45 ? "watch" : "good"} />
            <Kpi label="平台费累计" value={`¥${totalPlatformFee.toFixed(0)}`} sub="佣金+服务费" tone="watch" />
            <Kpi label="营销投入" value={`¥${totalMarketing.toFixed(0)}`} sub="满减/推广" tone="info" />
            <Kpi label="外卖营收估算" value={`¥${(totalTakeoutRevenue / 1000).toFixed(1)}k`} sub="不含平台费" tone="good" />
          </div>

          <div className="grid gap-4 md:grid-cols-2">

            {/* 堂食 vs 外卖 */}
            <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <p className="text-xs font-medium text-on-surface-variant">订单来源</p>
              <div className="mt-3 flex items-center gap-6">
                <div className="h-44 w-44">
                  <ResponsiveContainer>
                    <PieChart>
                      <Pie data={sourcePie} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} innerRadius={45} strokeWidth={0}>
                        {sourcePie.map((s, i) => (<Cell key={i} fill={s.color} />))}
                      </Pie>
                      <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid rgba(255,255,255,0.5)", background: "rgba(255,255,255,0.85)", backdropFilter: "blur(12px)", fontSize: 12 }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="space-y-2">
                  {sourcePie.map((s) => (
                    <div key={s.name} className="flex items-center gap-2">
                      <span className="h-3 w-3 rounded-full" style={{ backgroundColor: s.color }} />
                      <span className="text-sm text-on-background">{s.name}</span>
                      <span className="text-sm font-semibold text-on-background">{s.value}单</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 外卖成本拆解 */}
            <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <p className="text-xs font-medium text-on-surface-variant">外卖成本拆解</p>
              {costBreakdown.length > 0 ? (
                <div className="mt-3 flex items-center gap-6">
                  <div className="h-44 w-44">
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie data={costBreakdown} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} innerRadius={45} strokeWidth={0}>
                          {costBreakdown.map((_, i) => (<Cell key={i} fill={CHANNEL_COLORS[i + 3]} />))}
                        </Pie>
                        <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid rgba(255,255,255,0.5)", background: "rgba(255,255,255,0.85)", backdropFilter: "blur(12px)", fontSize: 12 }} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="space-y-2">
                    {costBreakdown.map((c) => (
                      <div key={c.name} className="flex items-center gap-2">
                        <span className="text-sm text-on-background">{c.name}</span>
                        <span className="text-sm font-semibold text-on-background">¥{c.value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="mt-3 text-xs text-on-surface-variant">暂无平台费数据</p>
              )}
            </div>

            {/* 外卖日趋势 */}
            <div className="rounded-2xl border border-white/45 bg-white/42 p-4 md:col-span-2">
              <p className="text-xs font-medium text-on-surface-variant">外卖日趋势（近14天）</p>
              <div className="mt-3 h-56">
                <ResponsiveContainer>
                  <BarChart data={dailyTakeout}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.3)" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#6b7280" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ borderRadius: 16, border: "1px solid rgba(255,255,255,0.5)", background: "rgba(255,255,255,0.85)", backdropFilter: "blur(12px)", fontSize: 12 }} />
                    <Bar dataKey="外卖单" fill="#c8a64e" radius={[6, 6, 0, 0]} maxBarSize={30} />
                    <Bar dataKey="平台费" fill="#D9261C" radius={[6, 6, 0, 0]} maxBarSize={30} />
                    <Bar dataKey="营销" fill="#64748b" radius={[6, 6, 0, 0]} maxBarSize={30} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* 渠道分布估算 */}
            <div className="rounded-2xl border border-white/45 bg-white/42 p-4 md:col-span-2">
              <p className="text-xs font-medium text-on-surface-variant">渠道分布估算（按 5:3:2 假设）</p>
              <div className="mt-3 grid grid-cols-3 gap-3">
                {channelSplit.map((ch) => (
                  <div key={ch.name} className="rounded-2xl bg-white/55 p-4 text-center">
                    <p className="text-xs text-on-surface-variant">{ch.name}</p>
                    <p className="mt-2 text-2xl font-bold text-on-background">{ch.value}</p>
                    <p className="mt-1 text-xs text-on-surface-variant">单</p>
                    <div className="mt-2 h-2 rounded-full bg-white/70">
                      <div className="h-2 rounded-full" style={{ width: `${(ch.value / Math.max(totalTakeout, 1)) * 100}%`, backgroundColor: ch.color }} />
                    </div>
                  </div>
                ))}
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
