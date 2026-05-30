"use client";

import { useMemo } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { calculateInvestment, fmtMoney } from "@/domain/calculations";
import { assessOperationRisks, assessPermissionRisks, assessFulfillmentRisks, assessBreakevenAlert } from "@/domain/riskRules";
import { mockOperations, mockInvestment, mockPermissions, mockFulfillment, mockActions } from "@/data/mockProject";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { SectionHeader } from "@/components/shared/SectionHeader";
import { MetricCard } from "@/components/shared/MetricCard";
import { RiskList } from "@/components/shared/RiskList";
import { PermBadge, FulfillBadge, PermSmallBadge } from "@/components/shared/badges";

export function OperationsView() {
  const records = mockOperations;
  const risks = useMemo(() => assessOperationRisks(mockOperations, mockInvestment), []);
  const permRisks = useMemo(() => assessPermissionRisks(mockPermissions), []);
  const ffRisks = useMemo(() => assessFulfillmentRisks(mockFulfillment), []);
  const breakeven = useMemo(() => assessBreakevenAlert(mockOperations, mockInvestment), []);
  const allOpsRisks = useMemo(() => [...risks, ...permRisks, ...ffRisks], [risks, permRisks, ffRisks]);
  const recent = records.slice(-7);
  const avgRevenue = recent.reduce((s, r) => s + r.revenue, 0) / recent.length;
  const avgOrders = recent.reduce((s, r) => s + r.orders, 0) / recent.length;
  const avgMargin = recent.reduce((s, r) => {
    const margin = r.revenue > 0 ? (r.revenue - r.materialCost - r.packagingCost - r.platformCommission - r.lossAmount) / r.revenue : 0;
    return s + margin;
  }, 0) / recent.length;
  const totalProfit = recent.reduce((s, r) => {
    const cogs = r.materialCost + r.packagingCost + r.platformCommission + r.deliverySubsidy + r.discountCost + r.lossAmount;
    return s + (r.revenue - cogs - r.laborCost - r.rentAllocated - r.utilitiesAllocated - r.marketingCost);
  }, 0);
  const avgDeliveryRatio = recent.reduce((s, r) => s + r.deliveryOrders, 0) / Math.max(recent.reduce((s, r) => s + r.orders, 0), 1);
  const avgLaborCostRate = recent.reduce((s, r) => s + (r.revenue > 0 ? r.laborCost / r.revenue : 0), 0) / recent.length;
  const result = calculateInvestment(mockInvestment);
  const belowBreakevenDays = recent.filter(r => r.revenue < result.breakevenDailyRevenue).length;
  const healthLevel = belowBreakevenDays >= 5 ? "red" : belowBreakevenDays >= 3 ? "yellow" : "green";

  const trendData = recent.map(r => ({ date: r.date.slice(5), revenue: r.revenue, orders: r.orders }));
  const channelData = [
    { name: "堂食", value: 1 - avgDeliveryRatio, color: "#1b3b32" },
    { name: "外卖", value: avgDeliveryRatio, color: "#c5a880" },
  ];

  return (
    <div className="space-y-6">
      <SectionHeader title="运营驾驶舱" subtitle={`近 ${recent.length} 天经营数据`} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <MetricCard label="日均营收" value={fmtMoney(avgRevenue)} trend={avgRevenue > 3000 ? "up" : "down"} trendLabel="vs 预期" />
        <MetricCard label="日均订单" value={`${Math.round(avgOrders)}单`} />
        <MetricCard label="平均毛利率" value={`${(avgMargin * 100).toFixed(1)}%`} trend={avgMargin > 0.55 ? "up" : "down"} negative={avgMargin < 0.55} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>7 日营收趋势</CardTitle>
            <CardDescription>每日营业额与订单量变化</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#edeae0" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#9aa6a2" }} />
                <YAxis yAxisId="left" tick={{ fontSize: 11, fill: "#9aa6a2" }} tickFormatter={(v: number) => `${(v / 1000).toFixed(1)}k`} />
                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                <Tooltip formatter={(value: any, name: any) => [String(name) === "revenue" ? fmtMoney(Number(value)) : `${value}单`, String(name) === "revenue" ? "营收" : "订单"]} />
                <Line yAxisId="left" type="monotone" dataKey="revenue" stroke="#1b3b32" strokeWidth={2} dot={{ fill: "#1b3b32", r: 4 }} name="revenue" />
                <Line yAxisId="left" type="monotone" dataKey="orders" stroke="#c5a880" strokeWidth={2} strokeDasharray="5 5" dot={{ fill: "#c5a880", r: 4 }} name="orders" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>收入渠道分布</CardTitle>
            <CardDescription>堂食 vs 外卖占比</CardDescription>
          </CardHeader>
          <CardContent className="flex items-center justify-center">
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={channelData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" paddingAngle={4}>
                  {channelData.map((d, i) => <Cell key={i} fill={d.color} />)}
                </Pie>
                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                <Tooltip formatter={(value: any) => `${(Number(value) * 100).toFixed(0)}%`} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex gap-6 text-xs ml-4">
              {channelData.map(d => (
                <div key={d.name} className="flex items-center gap-1.5">
                  <span className="size-2.5 rounded-sm" style={{ backgroundColor: d.color }} />
                  <span className="text-gray-600">{d.name} {(d.value * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>每日经营明细</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-cream-200 text-gray-400">
                  <th className="py-2 text-left font-medium">日期</th>
                  <th className="py-2 text-right font-medium">营收</th>
                  <th className="py-2 text-right font-medium">订单</th>
                  <th className="py-2 text-right font-medium">毛利</th>
                  <th className="py-2 text-right font-medium">差评</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => (
                  <tr key={r.date} className="border-b border-cream-100 last:border-0">
                    <td className="py-2 text-gray-600">{r.date.slice(5)}</td>
                    <td className="py-2 text-right text-gray-700">{fmtMoney(r.revenue)}</td>
                    <td className="py-2 text-right text-gray-700">{r.orders}</td>
                    <td className="py-2 text-right text-gray-700">{r.revenue > 0 ? ((r.revenue - r.materialCost - r.packagingCost - r.platformCommission - r.lossAmount) / r.revenue * 100).toFixed(0) : 0}%</td>
                    <td className={"py-2 text-right " + (r.badReviews >= 3 ? "text-red-500" : "text-gray-500")}>{r.badReviews}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <RiskList risks={allOpsRisks} title="运营风险" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div className="rounded-xl border border-cream-200 bg-white p-3.5">
          <p className="text-gray-400">堂食占比</p>
          <p className="text-lg font-bold text-gray-800 mt-1" style={{ fontFamily: "Antonio, sans-serif" }}>{((1 - avgDeliveryRatio) * 100).toFixed(0)}%</p>
        </div>
        <div className="rounded-xl border border-cream-200 bg-white p-3.5">
          <p className="text-gray-400">外卖占比</p>
          <p className={"text-lg font-bold mt-1 " + (avgDeliveryRatio > 0.6 ? "text-amber-600" : "text-gray-800")} style={{ fontFamily: "Antonio, sans-serif" }}>{(avgDeliveryRatio * 100).toFixed(0)}%</p>
        </div>
        <div className="rounded-xl border border-cream-200 bg-white p-3.5">
          <p className="text-gray-400">人工成本率</p>
          <p className={"text-lg font-bold mt-1 " + (avgLaborCostRate > 0.25 ? "text-red-600" : "text-gray-800")} style={{ fontFamily: "Antonio, sans-serif" }}>{(avgLaborCostRate * 100).toFixed(1)}%</p>
        </div>
        <div className="rounded-xl border border-cream-200 bg-white p-3.5">
          <p className="text-gray-400">Prime Cost</p>
          <p className="text-lg font-bold text-gray-800 mt-1" style={{ fontFamily: "Antonio, sans-serif" }}>{((avgMargin + avgLaborCostRate) * 100).toFixed(0)}%</p>
        </div>
      </div>

      <div className={healthLevel === "red" ? "rounded-xl border-2 border-red-400/30 bg-red-50/30 p-5" : healthLevel === "yellow" ? "rounded-xl border-2 border-amber-400/30 bg-amber-50/30 p-5" : "rounded-xl border-2 border-emerald-400/30 bg-emerald-50/30 p-5"}>
        <div className="flex items-center gap-2 mb-3">
          <span className={"size-2 rounded-full " + (healthLevel === "red" ? "bg-red-500" : healthLevel === "yellow" ? "bg-amber-500" : "bg-emerald-500")} />
          <span className="text-[10px] text-gray-500 font-mono tracking-wider">
            经营诊断：{healthLevel === "red" ? "红色预警" : healthLevel === "yellow" ? "黄色预警" : "正常"}
          </span>
        </div>
        <p className="text-xs text-gray-600 leading-relaxed">
          {healthLevel === "red" ? `连续 ${belowBreakevenDays} 天未达保本线。主要偏差：${avgOrders < mockInvestment.averageDailyOrders * 0.8 ? "订单数不足" : "毛利率偏低"}。` : healthLevel === "yellow" ? `有 ${belowBreakevenDays} 天未达保本线。建议检查毛利率与订单结构。` : "当前经营指标正常。"}
        </p>
        {breakeven.cause.length > 0 && (
          <div className="mt-2 text-[11px] text-gray-500 space-y-0.5">
            {breakeven.cause.map((c, i) => <p key={i}>· {c}</p>)}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-cream-200 bg-white p-5">
        <p className="text-[10px] text-gray-400 font-mono tracking-wider mb-3">经营权限矩阵</p>
        <div className="space-y-2">
          {Object.values(mockPermissions).map((p) => (
            <div key={p.key} className="flex items-center gap-3 rounded-lg border border-cream-200 px-3 py-2">
              <span className="text-xs text-gray-600 w-20 shrink-0">{p.label}</span>
              <PermBadge status={p.status} />
              <span className="text-[11px] text-gray-400 flex-1">{p.note}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-cream-200 bg-white p-5">
        <p className="text-[10px] text-gray-400 font-mono tracking-wider mb-3">总部支持兑现度</p>
        <div className="space-y-2">
          {Object.values(mockFulfillment).map((f) => (
            <div key={f.key} className="flex items-center gap-3 rounded-lg border border-cream-200 px-3 py-2">
              <span className="text-xs text-gray-600 w-24 shrink-0">{f.label}</span>
              <FulfillBadge status={f.status} />
              <span className="text-[11px] text-gray-400 flex-1">{f.reality}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-cream-200 bg-white p-5">
        <p className="text-[10px] text-gray-400 font-mono tracking-wider mb-3">运营动作建议</p>
        <p className="text-[11px] text-gray-400 mb-3">每条建议标注所需权限与合同约束</p>
        <div className="space-y-3">
          {mockActions.map((a, i) => (
            <div key={i} className="rounded-lg border border-cream-200 p-3">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-xs font-medium text-gray-700">{a.title}</span>
                <PermSmallBadge perm={a.requiredPermission} />
              </div>
              <p className="text-[11px] text-gray-500">原因：{a.reason}</p>
              <p className="text-[11px] text-gray-400">合同约束：{a.contractConstraint}</p>
              <p className="text-[11px] text-gray-500">下一步：{a.nextStep}</p>
              {a.alternativeAction && <p className="text-[11px] text-amber-600 mt-1">替代：{a.alternativeAction}</p>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
