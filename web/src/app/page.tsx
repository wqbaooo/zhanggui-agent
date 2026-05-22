"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ProjectOverview } from "@/components/project/project-overview";
import { FinanceTool } from "@/components/artifact/finance-tool";
import { SiteAnalysis } from "@/components/artifact/site-analysis";
import { CompetitorResearch } from "@/components/artifact/competitor-research";
import { PermitChecklist } from "@/components/artifact/permit-checklist";
import { EquipmentList } from "@/components/artifact/equipment-list";
import { MarketingPlan } from "@/components/artifact/marketing-plan";
import { RiskRegister } from "@/components/artifact/risk-register";
import { OperationDashboard } from "@/components/artifact/operation-dashboard";
import { MenuOptimization } from "@/components/artifact/menu-optimization";
import { IncomeJournal } from "@/components/artifact/income-journal";
import { DataAnalytics } from "@/components/artifact/data-analytics";
import { MarketingROI } from "@/components/artifact/marketing-roi";
import { CustomerFeedback } from "@/components/artifact/customer-feedback";
import { InventoryManager } from "@/components/artifact/inventory-manager";
import { StaffManager } from "@/components/artifact/staff-manager";
import { ExploreWizard } from "@/components/artifact/explore-wizard";
import { FloatingAI } from "@/components/chat/floating-ai";

type Mode = "home" | "explore" | "prepare" | "operate";
type NavItem = "项目概览" | "选址分析" | "竞品调研" | "财务测算" | "证照办理" | "设备采购" | "开业营销" | "风险评估";
type OpNavItem = "经营看板" | "收支记账" | "数据分析" | "营销效果" | "客户反馈" | "库存管理" | "人员管理" | "菜单优化" | "预警中心";

const navItems: NavItem[] = ["项目概览", "选址分析", "竞品调研", "财务测算", "证照办理", "设备采购", "开业营销", "风险评估"];
const opNavItems: OpNavItem[] = ["经营看板", "收支记账", "数据分析", "营销效果", "客户反馈", "库存管理", "人员管理", "菜单优化", "预警中心"];

export default function Home() {
  const [mode, setMode] = useState<Mode>("home");
  const [activeNav, setActiveNav] = useState<NavItem>("项目概览");
  const [activeOpNav, setActiveOpNav] = useState<OpNavItem>("经营看板");

  if (mode === "explore") {
    return <ExploreWizard onBack={() => setMode("home")} />;
  }

  if (mode === "operate") {
    const content = (() => {
      switch (activeOpNav) {
        case "经营看板": return <OperationDashboard />;
        case "收支记账": return <IncomeJournal />;
        case "数据分析": return <DataAnalytics />;
        case "营销效果": return <MarketingROI />;
        case "客户反馈": return <CustomerFeedback />;
        case "库存管理": return <InventoryManager />;
        case "人员管理": return <StaffManager />;
        case "菜单优化": return <MenuOptimization />;
        case "预警中心": return <OperationDashboard />;
      }
    })();

    return (
      <div className="flex h-screen bg-background">
        <aside className="w-64 border-r flex flex-col p-4">
          <button onClick={() => setMode("home")} className="text-sm text-muted-foreground hover:text-foreground mb-6 text-left">← 返回首页</button>
          <h2 className="font-semibold mb-4">大口章鱼烧 · 九江店</h2>
          <nav className="space-y-1 text-sm">
            {opNavItems.map((item) => (
              <button key={item} onClick={() => setActiveOpNav(item)} className={`block w-full text-left px-2 py-1.5 rounded transition-colors ${activeOpNav === item ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground"}`}>{item}</button>
            ))}
          </nav>
          <div className="mt-auto text-xs text-muted-foreground">
            <p>已运营 731 天</p>
            <div className="w-full bg-muted rounded-full h-1.5 mt-2"><div className="bg-green-500 h-1.5 rounded-full w-[85%]" /></div>
            <p className="mt-1">经营健康度 85%</p>
          </div>
        </aside>
        <main className="flex-1 overflow-auto">{content}</main>
        <FloatingAI />
      </div>
    );
  }

  if (mode === "prepare") {
    const content = (() => {
      switch (activeNav) {
        case "项目概览": return <ProjectOverview />;
        case "选址分析": return <SiteAnalysis />;
        case "竞品调研": return <CompetitorResearch />;
        case "财务测算": return <FinanceTool />;
        case "证照办理": return <PermitChecklist />;
        case "设备采购": return <EquipmentList />;
        case "开业营销": return <MarketingPlan />;
        case "风险评估": return <RiskRegister />;
      }
    })();

    return (
      <div className="flex h-screen bg-background">
        <aside className="w-64 border-r flex flex-col p-4">
          <button onClick={() => setMode("home")} className="text-sm text-muted-foreground hover:text-foreground mb-6 text-left">← 返回首页</button>
          <h2 className="font-semibold mb-4">大口章鱼烧 · 南昌红谷滩</h2>
          <nav className="space-y-1 text-sm">
            {navItems.map((item) => (
              <button key={item} onClick={() => setActiveNav(item)} className={`block w-full text-left px-2 py-1.5 rounded transition-colors ${activeNav === item ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground"}`}>{item}</button>
            ))}
          </nav>
          <div className="mt-auto text-xs text-muted-foreground">
            <p>阶段 2/4 · 选址筹备</p>
            <div className="w-full bg-muted rounded-full h-1.5 mt-2"><div className="bg-primary h-1.5 rounded-full w-[58%]" /></div>
          </div>
        </aside>
        <main className="flex-1 overflow-auto"><div className="min-h-full">{content}</div></main>
        <FloatingAI />
      </div>
    );
  }

  return (
    <>
      <main className="min-h-screen bg-background flex items-center justify-center p-6">
        <div className="max-w-2xl w-full space-y-8">
          <div className="text-center space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight">开店 Agent</h1>
            <p className="text-muted-foreground text-sm">餐饮创业智能顾问 — 从想法验证到运营增长，全生命周期陪伴</p>
          </div>
          <div className="grid gap-4">
            <Card className="p-6 cursor-pointer hover:border-primary/50 transition-colors" onClick={() => setMode("explore")}>
              <div className="flex items-start justify-between"><div><h3 className="font-medium">我还没想好做什么</h3><p className="text-sm text-muted-foreground mt-1">3 步填写信息，AI 生成可行性报告，帮你判断该不该干</p></div><Badge variant="secondary" className="shrink-0">探索</Badge></div>
            </Card>
            <Card className="p-6 cursor-pointer hover:border-primary/50 transition-colors" onClick={() => setMode("prepare")}>
              <div className="flex items-start justify-between"><div><h3 className="font-medium">我正在筹备开店</h3><p className="text-sm text-muted-foreground mt-1">选址分析、财务测算、8 模块工作台 — 筹备阶段全搞定</p></div><Badge variant="secondary" className="shrink-0">筹备</Badge></div>
            </Card>
            <Card className="p-6 cursor-pointer hover:border-primary/50 transition-colors" onClick={() => setMode("operate")}>
              <div className="flex items-start justify-between"><div><h3 className="font-medium">我已有店铺在运营</h3><p className="text-sm text-muted-foreground mt-1">经营看板、收支记账、菜单优化 — 像咨询公司一样看数据</p></div><Badge variant="secondary" className="shrink-0">运营</Badge></div>
            </Card>
          </div>
          <p className="text-center text-xs text-muted-foreground">基于 LangGraph/ReAct · DeepSeek 驱动 · 高德地图商圈数据</p>
        </div>
      </main>
      <FloatingAI />
    </>
  );
}
