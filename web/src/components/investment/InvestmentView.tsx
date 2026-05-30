"use client";

import { useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { calculateInvestment, fmtMoney } from "@/domain/calculations";
import { assessInvestmentRisks } from "@/domain/riskRules";
import { mockInvestment } from "@/data/mockProject";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { SectionHeader } from "@/components/shared/SectionHeader";
import { MetricCard } from "@/components/shared/MetricCard";
import { Row } from "@/components/shared/DataDisplay";
import { RiskList } from "@/components/shared/RiskList";

export function InvestmentView() {
  const result = useMemo(() => calculateInvestment(mockInvestment), []);
  const risks = useMemo(() => assessInvestmentRisks(mockInvestment), []);

  const scenarioData = [
    { name: "保守", profit: result.scenario.conservative.monthlyProfit, months: result.scenario.conservative.paybackMonths },
    { name: "中性", profit: result.scenario.neutral.monthlyProfit, months: result.scenario.neutral.paybackMonths },
    { name: "乐观", profit: result.scenario.optimistic.monthlyProfit, months: result.scenario.optimistic.paybackMonths },
  ];

  const costBreakdown = [
    { name: "加盟费", value: mockInvestment.franchiseFee },
    { name: "保证金", value: mockInvestment.deposit },
    { name: "装修", value: mockInvestment.renovationCost },
    { name: "设备", value: mockInvestment.equipmentCost },
    { name: "首批物料", value: mockInvestment.firstInventoryCost },
    { name: "其他", value: mockInvestment.otherStartupCost },
  ];

  return (
    <div className="space-y-6">
      <SectionHeader title="投资测算" subtitle="基于真实成本结构的回本分析" />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <MetricCard label="初始投资" value={fmtMoney(result.totalInvestment)} />
        <MetricCard label="月固定成本" value={fmtMoney(result.monthlyFixedCost)} />
        <MetricCard label="月净利润" value={fmtMoney(result.monthlyNetProfit)} trend={result.monthlyNetProfit > 0 ? "up" : "down"} negative={result.monthlyNetProfit < 0} />
        <MetricCard label="日均保本额" value={fmtMoney(result.breakevenDailyRevenue)} />
        <MetricCard label="日均保本单数" value={result.breakevenDailyOrders === Infinity ? "∞" : `${Math.round(result.breakevenDailyOrders)}单`} />
        <MetricCard label="回本周期" value={result.paybackMonths === Infinity ? "无法回本" : `${result.paybackMonths.toFixed(1)}月`} trend={result.paybackMonths > 18 ? "up" : "down"} trendLabel="vs 行业均值" negative={result.paybackMonths > 18} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>三情景月利润对比</CardTitle>
            <CardDescription>保守 / 中性 / 乐观情景下的月净利润（元）</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={scenarioData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#edeae0" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#66736f" }} />
                <YAxis tick={{ fontSize: 11, fill: "#9aa6a2" }} tickFormatter={(v: number) => `${(v / 10000).toFixed(1)}万`} />
                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                <Tooltip formatter={(value: any) => [fmtMoney(Number(value)), "月利润"]} />
                <Bar dataKey="profit" radius={[6, 6, 0, 0]}>
                  {scenarioData.map((entry, i) => (
                    <Cell key={i} fill={entry.profit < 0 ? "#D9261C" : entry.profit > 5000 ? "#255144" : "#c5a880"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>初始投资构成</CardTitle>
            <CardDescription>各项启动成本分布（元）</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={costBreakdown} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#edeae0" />
                <XAxis type="number" tick={{ fontSize: 11, fill: "#9aa6a2" }} tickFormatter={(v: number) => `${(v / 10000).toFixed(1)}万`} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: "#66736f" }} width={60} />
                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                <Tooltip formatter={(value: any) => [fmtMoney(Number(value)), "金额"]} />
                <Bar dataKey="value" fill="#1b3b32" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <Row label="加盟费" value={fmtMoney(mockInvestment.franchiseFee)} />
        <Row label="保证金" value={fmtMoney(mockInvestment.deposit)} />
        <Row label="装修费" value={fmtMoney(mockInvestment.renovationCost)} />
        <Row label="设备费" value={fmtMoney(mockInvestment.equipmentCost)} />
        <Row label="首批物料" value={fmtMoney(mockInvestment.firstInventoryCost)} />
        <Row label="其他启动" value={fmtMoney(mockInvestment.otherStartupCost)} />
      </div>

      <RiskList risks={risks} title="投资风险" />
    </div>
  );
}
