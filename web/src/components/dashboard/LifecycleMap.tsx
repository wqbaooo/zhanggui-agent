"use client";

import React from "react";
import { Database, Globe, Calculator, Store, Search, FileText } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

type NodeStatus = "locked" | "ready" | "active";

interface MapNode {
  id: string;
  name: string;
  status: NodeStatus;
}

const PRE: MapNode[] = [
  { id: "01", name: "转租合同 · 设备库存", status: "ready" },
  { id: "02", name: "总部权限 · 交接兑现", status: "ready" },
  { id: "03", name: "接手成本 · 回本压力", status: "ready" },
  { id: "04", name: "日账模板 · 平台接入", status: "ready" },
  { id: "05", name: "试营业动作 · 风险止损", status: "locked" },
];

const POST: MapNode[] = [
  { id: "06", name: "经营健康度监控", status: "locked" },
  { id: "07", name: "现金流与利润分析", status: "locked" },
  { id: "08", name: "外卖渠道损益核算", status: "locked" },
  { id: "09", name: "供应链损耗与排班", status: "locked" },
  { id: "10", name: "总部承诺兑现追踪", status: "locked" },
];

const TOOLS = [
  { icon: Database, label: "知识库检索", status: "1302 chunks" },
  { icon: Globe, label: "联网搜索", status: "DuckDuckGo" },
  { icon: Calculator, label: "财务测算", status: "保本/回本/敏感" },
  { icon: Store, label: "接店盘点", status: "合同/设备/库存" },
  { icon: Search, label: "接店风控", status: "权限/成本/合规" },
  { icon: FileText, label: "爬虫数据", status: "美团/抖音" },
];

export const LifecycleMap: React.FC = () => {
  const countReady = PRE.filter(n => n.status !== "locked").length;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle>接店执行路线</CardTitle>
        </div>
        <div className="flex items-center gap-6 text-xs text-on-surface-variant">
          <span>当前阶段 <span className="font-mono font-semibold text-on-background">{countReady}/5</span> 就绪</span>
          <span>后续优化 <span className="font-mono text-on-surface-variant/70">0/5</span></span>
        </div>
      </CardHeader>

      <CardContent>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Current path */}
          <div className="space-y-3 relative">
            <div className="absolute left-[5px] top-2 bottom-2 w-px bg-gradient-to-b from-emerald-500 to-cream-200" />
            {PRE.map((node) => (
              <div key={node.id} className="relative pl-6 flex items-center justify-between">
                <div className="absolute left-0 top-1/2 -translate-y-1/2 size-2.5 rounded-full border-2 z-10"
                  style={{
                    backgroundColor: node.status === "locked" ? "#edeae0" : "#fff",
                    borderColor: node.status === "locked" ? "#ded8c8" : "#255144",
                  }}
                />
                <span className="text-[11px] font-mono text-on-surface-variant/70 w-5">{node.id}</span>
                <span className={`text-xs flex-1 ml-2 ${node.status === "locked" ? "text-on-surface-variant/55" : "text-on-background font-medium"}`}>
                  {node.name}
                </span>
                <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${node.status === "locked" ? "bg-surface-container-high/70 text-on-surface-variant/70" : "bg-emerald-500/10 text-emerald-700"}`}>
                  {node.status === "locked" ? "待激活" : "就绪"}
                </span>
              </div>
            ))}
          </div>

          {/* Next path */}
          <div className="space-y-3 relative opacity-50">
            <div className="absolute left-[5px] top-2 bottom-2 w-px border-l border-dashed border-muted-border/60" />
            {POST.map((node) => (
              <div key={node.id} className="relative pl-6 flex items-center justify-between">
                <div className="absolute left-0 top-1/2 -translate-y-1/2 size-2.5 rounded-full border-2 bg-surface-container-high border-muted-border/50 z-10" />
                <span className="text-[11px] font-mono text-on-surface-variant/40 w-5">{node.id}</span>
                <span className="text-xs flex-1 ml-2 text-on-surface-variant/50">{node.name}</span>
                <span className="text-[9px] font-mono bg-surface-container-high/70 text-on-surface-variant/55 px-1.5 py-0.5 rounded">待激活</span>
              </div>
            ))}
          </div>
        </div>

        {/* Tools row */}
        <div className="mt-6 pt-5 border-t border-muted-border/20 grid grid-cols-3 md:grid-cols-6 gap-3">
          {TOOLS.map((t) => (
            <div key={t.label} className="text-center">
              <div className="w-8 h-8 mx-auto rounded-lg bg-surface-container-high/60 flex items-center justify-center mb-1">
                <t.icon className="w-4 h-4 text-on-surface-variant" />
              </div>
              <p className="text-[10px] text-on-background font-medium">{t.label}</p>
              <p className="text-[9px] text-on-surface-variant font-mono">{t.status}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};
