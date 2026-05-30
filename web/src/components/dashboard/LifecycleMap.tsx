"use client";

import React from "react";
import { Database, Globe, Calculator, MapPin, Search, FileText } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

type NodeStatus = "locked" | "ready" | "active";

interface MapNode {
  id: string;
  name: string;
  status: NodeStatus;
}

const PRE: MapNode[] = [
  { id: "01", name: "品类分析 · 预算规划", status: "ready" },
  { id: "02", name: "商圈扫描 · 竞品调研", status: "ready" },
  { id: "03", name: "加盟尽调 · 合同审核", status: "ready" },
  { id: "04", name: "财务建模 · 压力测试", status: "ready" },
  { id: "05", name: "证照合规 · 开业筹备", status: "locked" },
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
  { icon: MapPin, label: "高德选址", status: "POI/商圈/聚客" },
  { icon: Search, label: "加盟分析", status: "话术/成本/合规" },
  { icon: FileText, label: "爬虫数据", status: "美团/抖音" },
];

export const LifecycleMap: React.FC = () => {
  const countReady = PRE.filter(n => n.status !== "locked").length;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle>双生命周期路线</CardTitle>
        </div>
        <div className="flex items-center gap-6 text-xs text-gray-400">
          <span>开店前 <span className="text-hunter-800 font-bold font-mono">{countReady}/5</span> 就绪</span>
          <span>开店后 <span className="text-gray-300 font-mono">0/5</span></span>
        </div>
      </CardHeader>

      <CardContent>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Pre-opening */}
          <div className="space-y-3 relative">
            <div className="absolute left-[5px] top-2 bottom-2 w-px bg-gradient-to-b from-emerald-500 to-cream-200" />
            {PRE.map((node, _i) => (
              <div key={node.id} className="relative pl-6 flex items-center justify-between">
                <div className="absolute left-0 top-1/2 -translate-y-1/2 size-2.5 rounded-full border-2 z-10"
                  style={{
                    backgroundColor: node.status === "locked" ? "#edeae0" : "#fff",
                    borderColor: node.status === "locked" ? "#ded8c8" : "#255144",
                  }}
                />
                <span className="text-[11px] font-mono text-gray-400 w-5">{node.id}</span>
                <span className={`text-xs flex-1 ml-2 ${node.status === "locked" ? "text-gray-300" : "text-gray-600 font-medium"}`}>
                  {node.name}
                </span>
                <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${node.status === "locked" ? "bg-gray-100 text-gray-400" : "bg-emerald-50 text-emerald-700"}`}>
                  {node.status === "locked" ? "待激活" : "就绪"}
                </span>
              </div>
            ))}
          </div>

          {/* Post-opening */}
          <div className="space-y-3 relative opacity-50">
            <div className="absolute left-[5px] top-2 bottom-2 w-px border-l border-dashed border-gray-300" />
            {POST.map((node, _i) => (
              <div key={node.id} className="relative pl-6 flex items-center justify-between">
                <div className="absolute left-0 top-1/2 -translate-y-1/2 size-2.5 rounded-full border-2 bg-[#edeae0] border-[#ded8c8] z-10" />
                <span className="text-[11px] font-mono text-gray-300 w-5">{node.id}</span>
                <span className="text-xs flex-1 ml-2 text-gray-300">{node.name}</span>
                <span className="text-[9px] font-mono bg-gray-100 text-gray-400 px-1.5 py-0.5 rounded">待激活</span>
              </div>
            ))}
          </div>
        </div>

        {/* Tools row */}
        <div className="mt-6 pt-5 border-t border-cream-200 grid grid-cols-3 md:grid-cols-6 gap-3">
          {TOOLS.map((t) => (
            <div key={t.label} className="text-center">
              <div className="w-8 h-8 mx-auto rounded-lg bg-cream-100 flex items-center justify-center mb-1">
                <t.icon className="w-4 h-4 text-gray-500" />
              </div>
              <p className="text-[10px] text-gray-600 font-medium">{t.label}</p>
              <p className="text-[9px] text-gray-400 font-mono">{t.status}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};
