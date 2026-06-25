"use client";

import { useEffect, useMemo, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, Area, AreaChart } from "recharts";
import { calculateInvestment, fmtMoney, generateCashFlowProjection, calculateSensitivity, calculateBreakevenAnalysis } from "@/domain/calculations";
import { assessInvestmentRisks } from "@/domain/riskRules";
import { useProjectData } from "@/lib/hooks/useProjectData";
import { MetricCard, AnimateIn, StaggerList } from "@/components/shared";
import { Row } from "@/components/shared/DataDisplay";
import { RiskList } from "@/components/shared/RiskList";
import { TrendingUp, PieChart, Calculator, AlertTriangle, Activity, Target } from "lucide-react";

const TABS = [
  { key: "overview", label: "总览", icon: Calculator },
  { key: "cashflow", label: "现金流", icon: Activity },
  { key: "sensitivity", label: "敏感性", icon: Target },
  { key: "scenarios", label: "情景", icon: TrendingUp },
  { key: "breakdown", label: "明细", icon: PieChart },
  { key: "risks", label: "风险", icon: AlertTriangle },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export function InvestmentView({ initialTab = "overview" }: { initialTab?: TabKey }) {
  const { investment: mockInvestment } = useProjectData();
  const result = useMemo(() => calculateInvestment(mockInvestment), [mockInvestment]);
  const risks = useMemo(() => assessInvestmentRisks(mockInvestment), [mockInvestment]);
  const cashflow = useMemo(() => generateCashFlowProjection(mockInvestment, 24), [mockInvestment]);
  const sensitivity = useMemo(() => calculateSensitivity(mockInvestment), [mockInvestment]);
  const breakeven = useMemo(() => calculateBreakevenAnalysis(mockInvestment), [mockInvestment]);
  const [activeTab, setActiveTab] = useState<TabKey>(initialTab);
  const [chartsReady, setChartsReady] = useState(false);

  useEffect(() => {
    const frame = requestAnimationFrame(() => setChartsReady(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  const scenarioData = [
    { name: "保守", profit: result.scenario.conservative.monthlyProfit, months: result.scenario.conservative.paybackMonths },
    { name: "中性", profit: result.scenario.neutral.monthlyProfit, months: result.scenario.neutral.paybackMonths },
    { name: "乐观", profit: result.scenario.optimistic.monthlyProfit, months: result.scenario.optimistic.paybackMonths },
  ];

  const costBreakdown = [
    { name: "装修", value: mockInvestment.renovationCost },
    { name: "设备", value: mockInvestment.equipmentCost },
    { name: "首批物料", value: mockInvestment.firstInventoryCost },
    { name: "证照", value: mockInvestment.licenseCost },
    { name: "开业营销", value: mockInvestment.openingMarketingCost },
    { name: "培训", value: mockInvestment.trainingCost },
    { name: "预备现金", value: mockInvestment.reserveCash },
    { name: "其他", value: mockInvestment.otherStartupCost },
  ];

  // 现金流图表数据
  const cashflowChartData = cashflow.map((m) => ({
    month: `${m.month}月`,
    revenue: m.revenue,
    profit: m.netProfit,
    cumulative: m.cumulativeProfit,
    balance: m.cashBalance,
    isBreakeven: m.isBreakeven,
  }));

  // 找到回本月
  const breakevenMonth = cashflow.find((m) => m.isBreakeven)?.month;

  // 敏感性数据 (龙卷风图)
  const tooltipStyle = {
    contentStyle: { background: "rgba(255,255,255,0.98)", border: "1px solid rgba(24,35,29,0.14)", borderRadius: 8, color: "#18231d", boxShadow: "0 12px 28px rgba(24,35,29,0.12)" },
  };

  return (
    <div className="h-full flex flex-col gap-3">
      <StaggerList staggerDelay={80} className="grid grid-cols-2 gap-3 md:grid-cols-5 shrink-0">
        <MetricCard label="初始投资" value={fmtMoney(result.totalInvestment)} />
        <MetricCard label="月固定成本" value={fmtMoney(result.monthlyFixedCost)} />
        <MetricCard label="月净利润" value={fmtMoney(result.monthlyNetProfit)} trend={result.monthlyNetProfit > 0 ? "up" : "down"} negative={result.monthlyNetProfit < 0} />
        <MetricCard label="回本周期" value={result.paybackMonths === Infinity ? "无法回本" : `${result.paybackMonths.toFixed(1)}月`} negative={result.paybackMonths > 18} />
        <MetricCard label="安全边际" value={`${(breakeven.safetyMargin * 100).toFixed(0)}%`} negative={breakeven.safetyMargin < 0.2} />
      </StaggerList>

      <AnimateIn delay={400} direction="up" className="flex-1 glass-card rounded-xl p-4 interactive-card flex flex-col min-h-0">
        <div className="flex gap-1 mb-3 shrink-0 relative z-10 overflow-x-auto">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button key={tab.key} onClick={() => setActiveTab(tab.key)} className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-mono whitespace-nowrap transition-all ${activeTab === tab.key ? "bg-agent-gold/20 text-agent-gold border border-agent-gold/30" : "text-on-surface-variant hover:text-on-background hover:bg-surface-container-high/40"}`}>
                <Icon className="w-3 h-3" />
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="flex-1 overflow-y-auto relative z-10 min-h-0 pr-1">
          {/* 总览 */}
          {activeTab === "overview" && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1 text-xs">
                  <Row label="日均保本额" value={fmtMoney(result.breakevenDailyRevenue)} />
                  <Row label="日均保本单数" value={result.breakevenDailyOrders === Infinity ? "∞" : `${Math.round(result.breakevenDailyOrders)}单`} />
                  <Row label="贡献毛利率" value={`${(breakeven.contributionMargin * 100).toFixed(1)}%`} />
                  <Row label="变动成本率" value={`${(result.monthlyVariableCostRate * 100).toFixed(1)}%`} />
                  <Row label="月营业额" value={fmtMoney(result.monthlyRevenue)} />
                  <Row label="月净利润" value={fmtMoney(result.monthlyNetProfit)} />
                </div>
                <div className="flex items-center justify-center">
                  <div className="text-center">
                    <p className="text-[10px] text-on-surface-variant/50 font-mono">能否回本</p>
                    <p className={`text-2xl font-bold mt-1 ${result.canRecover ? "text-emerald-700" : "text-error"}`}>{result.canRecover ? "可以" : "困难"}</p>
                    {result.paybackMonths !== Infinity && <p className="text-[10px] text-on-surface-variant/50 mt-1">{result.paybackMonths.toFixed(1)} 个月</p>}
                    {breakevenMonth && <p className="text-[9px] text-emerald-700/70 mt-0.5">第{breakevenMonth}月回本</p>}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 现金流预测 */}
          {activeTab === "cashflow" && (
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-[10px] text-on-surface-variant/50">
                <span>24个月现金流预测</span>
                {breakevenMonth && <span className="text-emerald-700">回本月: 第{breakevenMonth}月</span>}
              </div>
              <div className="h-48">
                {chartsReady ? (
                  <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                    <AreaChart data={cashflowChartData}>
                      <defs>
                        <linearGradient id="profitGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#166534" stopOpacity={0.2} />
                          <stop offset="95%" stopColor="#166534" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="balanceGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#2563eb" stopOpacity={0.18} />
                          <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="month" tick={{ fontSize: 9, fill: "#657267" }} axisLine={false} tickLine={false} interval={2} />
                      <YAxis tick={{ fontSize: 9, fill: "#657267" }} axisLine={false} tickLine={false} tickFormatter={(v) => `${(v / 10000).toFixed(0)}万`} width={35} />
                      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                      <Tooltip {...tooltipStyle} formatter={(v: any) => [fmtMoney(Number(v)), "金额"]} />
                      <Area type="monotone" dataKey="profit" stroke="#166534" fill="url(#profitGrad)" strokeWidth={1.5} name="profit" />
                      <Area type="monotone" dataKey="balance" stroke="#2563eb" fill="url(#balanceGrad)" strokeWidth={1.5} name="balance" />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full rounded-lg bg-surface-container-high/20" />
                )}
              </div>
              <div className="grid grid-cols-6 gap-1">
                {cashflow.filter((_, i) => i % 4 === 3 || i === 0).map((m) => (
                  <div key={m.month} className={`text-center p-1.5 rounded ${m.isBreakeven ? "bg-emerald-500/10 border border-emerald-500/20" : "bg-surface-container-high/30"}`}>
                    <p className="text-[8px] text-on-surface-variant/50">{m.month}月</p>
                    <p className={`text-[10px] font-bold ${m.netProfit < 0 ? "text-error" : "text-on-background"}`}>{fmtMoney(m.netProfit)}</p>
                    <p className="text-[7px] text-on-surface-variant/30">余额{fmtMoney(m.cashBalance)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 敏感性分析 */}
          {activeTab === "sensitivity" && (
            <div className="space-y-3">
              <p className="text-[10px] text-on-surface-variant/50">各变量变动±20%对月利润的影响</p>
              <div className="space-y-2">
                {sensitivity.map((s) => {
                  const maxImpact = Math.max(...sensitivity.map((x) => Math.abs(x.impactOnProfit)));
                  const barWidth = (Math.abs(s.impactOnProfit) / maxImpact) * 100;
                  return (
                    <div key={s.name} className="flex items-center gap-2">
                      <span className="text-[10px] text-on-surface-variant w-16 shrink-0 text-right">{s.label}</span>
                      <div className="flex-1 flex items-center gap-1">
                        <div className="flex-1 h-3 bg-surface-container-high/30 rounded-full overflow-hidden flex justify-end">
                          <div className={`h-full rounded-l-full ${s.impactOnProfit < 0 ? "bg-error/60" : "bg-emerald-500/60"}`} style={{ width: `${barWidth}%` }} />
                        </div>
                        <span className={`text-[9px] font-mono w-14 text-right ${s.impactOnProfit < 0 ? "text-error" : "text-emerald-700"}`}>
                          {s.impactOnProfit > 0 ? "+" : ""}{fmtMoney(s.impactOnProfit)}
                        </span>
                      </div>
                      <span className="text-[8px] text-on-surface-variant/30 w-12">
                        {s.impactOnPayback > 0 ? `+${s.impactOnPayback}月` : s.impactOnPayback < 0 ? `${s.impactOnPayback}月` : ""}
                      </span>
                    </div>
                  );
                })}
              </div>
              <div className="p-2.5 rounded-lg bg-surface-container-high/30">
                <p className="font-label-caps text-on-surface-variant text-[9px] mb-1">解读</p>
                <p className="text-[10px] text-on-surface-variant">
                  {sensitivity[0]?.label}对利润影响最大，变动±20%会导致月利润变化{fmtMoney(Math.abs(sensitivity[0]?.impactOnProfit || 0))}。
                  {sensitivity[0]?.impactOnPayback ? `回本周期变化${Math.abs(sensitivity[0].impactOnPayback)}个月。` : ""}
                </p>
              </div>
            </div>
          )}

          {/* 情景分析 */}
          {activeTab === "scenarios" && (
            <div className="h-full flex flex-col">
              <div className="h-52 min-h-0">
                {chartsReady ? (
                  <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                    <BarChart data={scenarioData}>
                      <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#657267" }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 10, fill: "#657267" }} axisLine={false} tickLine={false} tickFormatter={(v) => `${(v / 10000).toFixed(1)}万`} />
                      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                      <Tooltip {...tooltipStyle} formatter={(v: any) => [fmtMoney(Number(v)), "月利润"]} />
                      <Bar dataKey="profit" radius={[6, 6, 0, 0]}>
                        {scenarioData.map((entry, i) => <Cell key={i} fill={entry.profit < 0 ? "#dc2626" : entry.profit > 5000 ? "#166534" : "#f59e0b"} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full rounded-lg bg-surface-container-high/20" />
                )}
              </div>
              <div className="grid grid-cols-3 gap-2 mt-2 shrink-0">
                {scenarioData.map((s) => (
                  <div key={s.name} className="text-center p-2 rounded-lg bg-surface-container-high/30">
                    <p className="text-[10px] text-on-surface-variant/50">{s.name}</p>
                    <p className={`text-sm font-bold ${s.profit < 0 ? "text-error" : "text-on-background"}`}>{fmtMoney(s.profit)}</p>
                    <p className="text-[9px] text-on-surface-variant/40">{s.months > 0 ? `${s.months}月` : "无法回本"}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 成本明细 */}
          {activeTab === "breakdown" && (
            <div className="h-full flex flex-col">
              <div className="h-52 min-h-0">
                {chartsReady ? (
                  <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                    <BarChart data={costBreakdown} layout="vertical">
                      <XAxis type="number" tick={{ fontSize: 10, fill: "#657267" }} axisLine={false} tickLine={false} tickFormatter={(v) => `${(v / 10000).toFixed(1)}万`} />
                      <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "#657267" }} axisLine={false} tickLine={false} width={50} />
                      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                      <Tooltip {...tooltipStyle} formatter={(v: any) => [fmtMoney(Number(v)), "金额"]} />
                      <Bar dataKey="value" fill="#166534" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full rounded-lg bg-surface-container-high/20" />
                )}
              </div>
              <div className="grid grid-cols-3 gap-2 mt-2 shrink-0">
                {costBreakdown.map((c) => (
                  <div key={c.name} className="text-center p-1.5 rounded bg-surface-container-high/30">
                    <p className="text-[9px] text-on-surface-variant/50">{c.name}</p>
                    <p className="text-xs font-bold text-on-background">{fmtMoney(c.value)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 风险 */}
          {activeTab === "risks" && <RiskList risks={risks} />}
        </div>
      </AnimateIn>
    </div>
  );
}
