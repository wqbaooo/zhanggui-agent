"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ProjectOverview } from "@/components/project/project-overview";
import { FinanceTool } from "@/components/artifact/finance-tool";
import { SiteAnalysis } from "@/components/artifact/site-analysis";
import { FloatingAI } from "@/components/chat/floating-ai";

type Mode = "home" | "explore" | "prepare" | "operate";
type NavItem = "项目概览" | "选址分析" | "竞品调研" | "财务测算" | "证照办理" | "设备采购" | "开业营销" | "风险评估";

const navItems: NavItem[] = ["项目概览", "选址分析", "竞品调研", "财务测算", "证照办理", "设备采购", "开业营销", "风险评估"];

export default function Home() {
  const [mode, setMode] = useState<Mode>("home");
  const [activeNav, setActiveNav] = useState<NavItem>("项目概览");

  if (mode === "prepare") {
    return (
      <div className="flex h-screen bg-background">
        <aside className="w-64 border-r flex flex-col p-4">
          <button
            onClick={() => setMode("home")}
            className="text-sm text-muted-foreground hover:text-foreground mb-6 text-left"
          >
            ← 返回首页
          </button>
          <h2 className="font-semibold mb-4">大口章鱼烧 · 南昌红谷滩</h2>
          <nav className="space-y-1 text-sm">
            {navItems.map((item) => (
              <button
                key={item}
                onClick={() => setActiveNav(item)}
                className={`block w-full text-left px-2 py-1.5 rounded transition-colors ${
                  activeNav === item
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {item}
              </button>
            ))}
          </nav>
          <div className="mt-auto text-xs text-muted-foreground">
            <p>阶段 2/4 · 选址筹备</p>
            <div className="w-full bg-muted rounded-full h-1.5 mt-2">
              <div className="bg-primary h-1.5 rounded-full w-[58%]" />
            </div>
          </div>
        </aside>
        <main className="flex-1 flex flex-col">
          <div className="flex-1 overflow-auto">
            {activeNav === "项目概览" && (
              <div className="p-6">
                <ProjectOverview />
              </div>
            )}
            {activeNav === "选址分析" && <SiteAnalysis />}
            {activeNav === "财务测算" && <FinanceTool />}
            {!["项目概览", "选址分析", "财务测算"].includes(activeNav) && (
              <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                {activeNav} — 即将上线
              </div>
            )}
          </div>
        </main>
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
            <p className="text-muted-foreground text-sm">
              餐饮创业智能顾问 — 从想法验证到运营增长，全生命周期陪伴
            </p>
          </div>

          <div className="grid gap-4">
            <Card
              className="p-6 cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => setMode("explore")}
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-medium">我还没想好做什么</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    填写基本信息，几分钟获得一份可行性报告，帮你判断该不该干
                  </p>
                </div>
                <Badge variant="secondary" className="shrink-0">探索</Badge>
              </div>
            </Card>

            <Card
              className="p-6 cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => setMode("prepare")}
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-medium">我正在筹备开店</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    选址分析、财务测算、证照清单 — 一个工作台全部搞定
                  </p>
                </div>
                <Badge variant="secondary" className="shrink-0">筹备</Badge>
              </div>
            </Card>

            <Card className="p-6 opacity-50">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-medium">我已有店铺在运营</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    经营看板、收支记账、菜单优化 — 日常运营工具（即将推出）
                  </p>
                </div>
                <Badge variant="outline" className="shrink-0">即将推出</Badge>
              </div>
            </Card>
          </div>

          <p className="text-center text-xs text-muted-foreground">
            基于 LangGraph/ReAct · DeepSeek 驱动 · 高德地图商圈数据
          </p>
        </div>
      </main>
      <FloatingAI />
    </>
  );
}
