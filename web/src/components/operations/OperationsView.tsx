"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { calculateInvestment, fmtMoney, calcDailyMetrics, calcRevenuePerSqm, calcRevenuePerStaff } from "@/domain/calculations";
import { useProjectData } from "@/lib/hooks/useProjectData";
import type { PermissionItem, FulfillmentItem } from "@/domain/types";
import { MetricCard, AnimateIn, StaggerList, LoadingSpinner } from "@/components/shared";
import { PermBadge, FulfillBadge, PermSmallBadge } from "@/components/shared/badges";
import { ClipboardList, ShieldCheck, Handshake, Zap, AlertTriangle, Smartphone } from "lucide-react";

const TABS = [
  { key: "table", label: "明细", icon: ClipboardList },
  { key: "diagnosis", label: "诊断", icon: AlertTriangle },
  { key: "platforms", label: "平台", icon: Smartphone },
  { key: "permissions", label: "权限", icon: ShieldCheck },
  { key: "fulfillment", label: "兑现", icon: Handshake },
  { key: "actions", label: "建议", icon: Zap },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export function OperationsView({ initialTab = "table" }: { initialTab?: TabKey }) {
  const { operations: records, investment: mockInvestment, permissions, fulfillment, actions, cockpit, isApiConnected, isLoading } = useProjectData();
  const [activeTab, setActiveTab] = useState<TabKey>(initialTab);
  const [chartsReady, setChartsReady] = useState(false);

  useEffect(() => {
    const frame = requestAnimationFrame(() => setChartsReady(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (records.length === 0) {
    return <EmptyOperationsState isApiConnected={isApiConnected} missing={cockpit?.data_quality?.missing ?? []} />;
  }

  const recent = records.slice(-7);
  const avgRevenue = recent.reduce((s: number, r: { revenue: number }) => s + r.revenue, 0) / recent.length;
  const avgOrders = recent.reduce((s: number, r: { orders: number }) => s + r.orders, 0) / recent.length;
  const avgMargin = recent.reduce((s: number, r: { revenue: number; materialCost: number; packagingCost: number; platformCommission: number; lossAmount: number }) => {
    const margin = r.revenue > 0 ? (r.revenue - r.materialCost - r.packagingCost - r.platformCommission - r.lossAmount) / r.revenue : 0;
    return s + margin;
  }, 0) / recent.length;
  const avgDeliveryRatio = recent.reduce((s: number, r: { deliveryOrders: number; orders: number }) => s + r.deliveryOrders, 0) / Math.max(recent.reduce((s: number, r: { orders: number }) => s + r.orders, 0), 1);
  const avgLaborCostRate = recent.reduce((s: number, r: { revenue: number; laborCost: number }) => s + (r.revenue > 0 ? r.laborCost / r.revenue : 0), 0) / recent.length;
  const result = calculateInvestment(mockInvestment);
  const belowBreakevenDays = recent.filter((r: { revenue: number }) => r.revenue < result.breakevenDailyRevenue).length;
  const healthLevel = belowBreakevenDays >= 5 ? "red" : belowBreakevenDays >= 3 ? "yellow" : "green";

  const trendData = recent.map((r: { date: string; revenue: number; orders: number }) => ({ date: r.date.slice(5), revenue: r.revenue, orders: r.orders }));
  const channelData = [
    { name: "堂食", value: 1 - avgDeliveryRatio, color: "#166534" },
    { name: "外卖", value: avgDeliveryRatio, color: "#2563eb" },
  ];

  const tooltipStyle = {
    contentStyle: { background: "rgba(255,255,255,0.98)", border: "1px solid rgba(24,35,29,0.14)", borderRadius: 8, color: "#18231d", boxShadow: "0 12px 28px rgba(24,35,29,0.12)" },
  };

  return (
    <div className="h-full flex flex-col gap-3">
      {/* Metrics */}
      <StaggerList staggerDelay={80} className="grid grid-cols-2 gap-3 md:grid-cols-4 shrink-0">
        <MetricCard label="日均营收" value={fmtMoney(avgRevenue)} trend={avgRevenue > 3000 ? "up" : "down"} trendLabel="vs 预期" />
        <MetricCard label="日均订单" value={`${Math.round(avgOrders)}单`} />
        <MetricCard label="毛利率" value={`${(avgMargin * 100).toFixed(1)}%`} trend={avgMargin > 0.55 ? "up" : "down"} negative={avgMargin < 0.55} />
        <MetricCard label="Prime Cost" value={`${((avgMargin + avgLaborCostRate) * 100).toFixed(0)}%`} />
      </StaggerList>

      {/* Charts + Tab Panel */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-5 gap-3 min-h-0">
        {/* Charts */}
        <div className="lg:col-span-3 flex flex-col gap-3 min-h-0">
          <AnimateIn delay={300} direction="up">
            <div className="glass-card rounded-xl p-4 interactive-card flex-1 flex flex-col min-h-0">
              <h3 className="font-label-caps text-on-surface-variant mb-2 shrink-0 relative z-10">7日营收趋势</h3>
              <div className="relative z-10 h-56 min-h-0">
                {chartsReady ? (
                  <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                    <LineChart data={trendData}>
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#657267" }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 10, fill: "#657267" }} axisLine={false} tickLine={false} tickFormatter={(v) => `${(Number(v) / 1000).toFixed(0)}k`} width={40} />
                      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                      <Tooltip {...tooltipStyle} formatter={(value: any, name: any) => [String(name) === "revenue" ? fmtMoney(Number(value)) : `${value}单`, String(name) === "revenue" ? "营收" : "订单"]} />
                      <Line type="monotone" dataKey="revenue" stroke="#166534" strokeWidth={2} dot={false} name="revenue" isAnimationActive animationDuration={800} />
                      <Line type="monotone" dataKey="orders" stroke="#2563eb" strokeWidth={1.5} strokeDasharray="4 4" dot={false} name="orders" isAnimationActive animationDuration={800} animationBegin={200} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full rounded-lg bg-surface-container-high/20" />
                )}
              </div>
            </div>
          </AnimateIn>
          <AnimateIn delay={500} direction="up">
            <div className="glass-card rounded-xl p-4 interactive-card shrink-0">
              <div className="flex items-center gap-6 relative z-10">
                <div className="flex-1">
                  <h3 className="font-label-caps text-on-surface-variant mb-2">渠道分布</h3>
                  <div className="flex gap-4">
                    {channelData.map(d => (
                      <div key={d.name} className="flex items-center gap-1.5">
                        <span className="size-2.5 rounded-sm" style={{ backgroundColor: d.color }} />
                        <span className="text-xs text-on-surface-variant">{d.name} {(d.value * 100).toFixed(0)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="w-20 h-20">
                  {chartsReady ? (
                    <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                      <PieChart>
                        <Pie data={channelData} cx="50%" cy="50%" innerRadius={20} outerRadius={35} dataKey="value" paddingAngle={4} isAnimationActive animationDuration={800}>
                          {channelData.map((d, i) => <Cell key={i} fill={d.color} />)}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full rounded-full bg-surface-container-high/20" />
                  )}
                </div>
              </div>
            </div>
          </AnimateIn>
        </div>

        {/* Tab Panel */}
        <div className="lg:col-span-2 glass-card rounded-xl p-4 interactive-card flex flex-col min-h-0">
          <div className="flex gap-1 mb-3 shrink-0 relative z-10 overflow-x-auto">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-mono whitespace-nowrap transition-all ${
                    activeTab === tab.key ? "bg-agent-gold/20 text-agent-gold border border-agent-gold/30" : "text-on-surface-variant hover:text-on-background hover:bg-surface-container-high/40"
                  }`}
                >
                  <Icon className="w-3 h-3" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          <div className="flex-1 overflow-y-auto relative z-10 min-h-0 pr-1">
            {activeTab === "table" && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-muted-border/30 text-on-surface-variant">
                      <th className="py-1.5 text-left font-medium">日期</th>
                      <th className="py-1.5 text-right font-medium">营收</th>
                      <th className="py-1.5 text-right font-medium">订单</th>
                      <th className="py-1.5 text-right font-medium">毛利</th>
                      <th className="py-1.5 text-right font-medium">差评</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.map((r: { date: string; revenue: number; orders: number; materialCost: number; packagingCost: number; platformCommission: number; lossAmount: number; badReviews: number }, idx) => (
                      <tr key={r.date} className="border-b border-muted-border/15 last:border-0 hover:bg-surface-container-high/30 transition-colors animate-slide-in-left" style={{ animationDelay: `${idx * 50}ms` }}>
                        <td className="py-1.5 text-on-surface-variant">{r.date.slice(5)}</td>
                        <td className="py-1.5 text-right text-on-background">{fmtMoney(r.revenue)}</td>
                        <td className="py-1.5 text-right text-on-background">{r.orders}</td>
                        <td className="py-1.5 text-right text-on-background">{r.revenue > 0 ? ((r.revenue - r.materialCost - r.packagingCost - r.platformCommission - r.lossAmount) / r.revenue * 100).toFixed(0) : 0}%</td>
                        <td className={"py-1.5 text-right " + (r.badReviews >= 3 ? "text-error" : "text-on-surface-variant")}>{r.badReviews}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {activeTab === "diagnosis" && (() => {
              const latest = records[records.length - 1];
              const m = calcDailyMetrics(latest);
              const monthlyRevenue = recent.reduce((s: number, r: { revenue: number }) => s + r.revenue, 0) * (30 / recent.length);
              const sqm = 35; // 从 location 数据获取
              const staff = 5; // 默认5人
              const sqmMetric = calcRevenuePerSqm(monthlyRevenue, sqm);
              const staffMetric = calcRevenuePerStaff(monthlyRevenue, staff);

              const metrics = [
                { name: "食材成本率", value: m.foodCostRate.label, status: m.foodCostRate.status, target: "30-35%" },
                { name: "人工成本率", value: m.laborCostRate.label, status: m.laborCostRate.status, target: "18-25%" },
                { name: "租金占比", value: m.rentCostRate.label, status: m.rentCostRate.status, target: "10-15%" },
                { name: "Prime Cost", value: m.primeCost.primeCostRate ? `${(m.primeCost.primeCostRate * 100).toFixed(1)}%` : "--", status: m.primeCost.status, target: "<65%" },
                { name: "三大成本率", value: m.threeCostRate.label, status: m.threeCostRate.status, target: "<70%" },
                { name: "净利润率", value: m.netProfitRate.label, status: m.netProfitRate.status, target: "8-15%" },
                { name: "综合成本率", value: m.totalCostRate.label, status: m.totalCostRate.status, target: "<85%" },
                { name: "坪效", value: sqmMetric.label, status: sqmMetric.status, target: "2000-8000" },
                { name: "人效", value: staffMetric.label, status: staffMetric.status, target: "2-5万" },
                { name: "外卖占比", value: m.deliveryRatio.label, status: m.deliveryRatio.status, target: "20-40%" },
                { name: "平台佣金率", value: m.commissionRate.label, status: m.commissionRate.status, target: "<20%" },
                { name: "外卖单均利润", value: m.deliveryProfit.label, status: m.deliveryProfit.status, target: ">3元" },
                { name: "损耗率", value: m.wasteRate.label, status: m.wasteRate.status, target: "<3%" },
                { name: "差评率", value: m.badReviewRate.label, status: m.badReviewRate.status, target: "<3%" },
                { name: "复购率", value: m.repeatRate.label, status: m.repeatRate.status, target: ">30%" },
              ];

              return (
                <AnimateIn direction="up" className="space-y-2">
                  <div className={`p-2.5 rounded-lg border ${healthLevel === "red" ? "border-error/20 bg-error/5" : healthLevel === "yellow" ? "border-amber-500/20 bg-amber-500/5" : "border-emerald-500/20 bg-emerald-500/5"}`}>
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={`size-2 rounded-full ${healthLevel === "red" ? "bg-error" : healthLevel === "yellow" ? "bg-amber-500" : "bg-emerald-500"} ${healthLevel !== "green" ? "animate-pulse" : ""}`} />
                      <span className="font-label-caps text-on-surface-variant text-[9px]">{healthLevel === "red" ? "红色预警" : healthLevel === "yellow" ? "黄色预警" : "经营正常"}</span>
                      <span className="ml-auto text-[10px] text-on-surface-variant/50">净利润 {fmtMoney(m.netProfit)}/天</span>
                    </div>
                  </div>
                  <StaggerList staggerDelay={30} className="grid grid-cols-3 gap-1.5">
                    {metrics.map((item) => (
                      <div key={item.name} className="p-1.5 rounded bg-surface-container-high/30 hover:bg-surface-container-high/50 transition-colors cursor-default">
                        <p className="text-[8px] text-on-surface-variant/50 truncate">{item.name}</p>
                        <p className={`text-xs font-bold ${item.status === "healthy" ? "text-on-background" : item.status === "warning" ? "text-amber-700" : "text-error"}`}>{item.value}</p>
                        <p className="text-[7px] text-on-surface-variant/30">目标{item.target}</p>
                      </div>
                    ))}
                  </StaggerList>
                </AnimateIn>
              );
            })()}

            {activeTab === "platforms" && (
              <PendingPanel
                title="平台数据待接入"
                body="当前只展示你已录入的日账汇总，不展示美团、淘宝闪购、抖音的虚构订单、评分或 ROI。后续可以从手工录入、导表、截图 OCR 开始接入。"
              />
            )}

            {activeTab === "permissions" && (
              <StaggerList staggerDelay={50} className="space-y-1.5">
                {(Object.values(permissions) as PermissionItem[]).map((p) => (
                  <div key={p.key} className="flex items-center gap-2 p-2 rounded-lg bg-surface-container-high/30 hover:bg-surface-container-high/50 transition-all hover:scale-[1.01]">
                    <span className="text-[10px] text-on-surface-variant w-16 shrink-0">{p.label}</span>
                    <PermBadge status={p.status} />
                    <span className="text-[9px] text-on-surface-variant/50 truncate flex-1">{p.note}</span>
                  </div>
                ))}
              </StaggerList>
            )}

            {activeTab === "fulfillment" && (
              <StaggerList staggerDelay={50} className="space-y-1.5">
                {(Object.values(fulfillment) as FulfillmentItem[]).map((f) => (
                  <div key={f.key} className="flex items-center gap-2 p-2 rounded-lg bg-surface-container-high/30 hover:bg-surface-container-high/50 transition-all hover:scale-[1.01]">
                    <span className="text-[10px] text-on-surface-variant w-20 shrink-0">{f.label}</span>
                    <FulfillBadge status={f.status} />
                    <span className="text-[9px] text-on-surface-variant/50 truncate flex-1">{f.reality}</span>
                  </div>
                ))}
              </StaggerList>
            )}

            {activeTab === "actions" && (
              <StaggerList staggerDelay={60} className="space-y-2">
                {actions.map((a, i) => (
                  <div key={i} className="p-2.5 rounded-lg bg-surface-container-high/30 hover:bg-surface-container-high/50 transition-all hover:scale-[1.01] hover:shadow-sm">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-medium text-on-background">{a.title}</span>
                      <PermSmallBadge perm={a.requiredPermission} />
                    </div>
                    <p className="text-[10px] text-on-surface-variant/60">{a.reason}</p>
                    {a.alternativeAction && <p className="text-[10px] text-amber-700 mt-0.5">替代：{a.alternativeAction}</p>}
                  </div>
                ))}
              </StaggerList>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyOperationsState({ isApiConnected, missing }: { isApiConnected: boolean; missing: string[] }) {
  return (
    <div className="h-full grid grid-cols-1 gap-3 lg:grid-cols-5">
      <div className="lg:col-span-3 glass-card interactive-card rounded-xl p-5">
        <div className="relative z-10">
          <p className="font-label-caps text-on-surface-variant">经营账本</p>
          <h2 className="mt-2 text-xl font-semibold text-on-background">还没有真实经营流水</h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-on-surface-variant">
            运营页现在只读取当前门店的真实 API 数据。先回到工作台命令栏录入今天的营收、订单、食材成本、人工、外卖单和差评，确认后这里会自动出现趋势、指标网格和日账明细。
          </p>
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <MetricCard label="日均营收" value="—" trendLabel="待录入" />
            <MetricCard label="日均订单" value="—" trendLabel="待录入" />
            <MetricCard label="净利润率" value="—" trendLabel="待计算" />
            <MetricCard label="Prime Cost" value="—" trendLabel="待计算" />
          </div>
        </div>
      </div>
      <div className="lg:col-span-2 glass-card interactive-card rounded-xl p-5">
        <div className="relative z-10">
          <p className="font-label-caps text-on-surface-variant">数据状态</p>
          <div className="mt-3 rounded-lg border border-muted-border/30 bg-surface-container-high/25 p-3">
            <p className="text-sm font-medium text-on-background">{isApiConnected ? "后端已连接" : "后端未连接"}</p>
            <p className="mt-1 text-xs leading-relaxed text-on-surface-variant">
              {isApiConnected ? "未录入的数据不会用演示数据替代。" : "请先启动后端 API，再写入经营流水。"}
            </p>
          </div>
          {missing.length > 0 && (
            <div className="mt-4 space-y-1.5">
              <p className="font-label-caps text-on-surface-variant">待补齐</p>
              {missing.slice(0, 5).map((item) => (
                <div key={item} className="rounded-lg bg-surface-container-high/25 px-3 py-2 text-xs text-on-surface-variant">
                  {item}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PendingPanel({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
      <p className="text-xs font-medium text-on-background">{title}</p>
      <p className="mt-1 text-[10px] leading-relaxed text-on-surface-variant/70">{body}</p>
    </div>
  );
}
