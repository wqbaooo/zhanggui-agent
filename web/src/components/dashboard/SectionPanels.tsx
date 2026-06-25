"use client";

import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface PanelProps {
  onCreateProject: () => void;
}

interface MetricItem {
  label: string;
  value: string;
  unit: string;
  status: "active" | "inactive" | "pending";
}

const modules: { title: string; metrics: MetricItem[] }[] = [
  {
    title: "全要素财务建模",
    metrics: [
      { label: "初始投资", value: "—", unit: "万元", status: "pending" },
      { label: "月固定成本", value: "—", unit: "万元", status: "pending" },
      { label: "日均保本额", value: "—", unit: "元", status: "pending" },
      { label: "现金安全月", value: "—", unit: "个月", status: "pending" },
    ],
  },
  {
    title: "选址评估",
    metrics: [
      { label: "商圈评分", value: "—", unit: "/100", status: "pending" },
      { label: "竞品密度", value: "—", unit: "家/500m", status: "pending" },
      { label: "租金压力", value: "—", unit: "%", status: "pending" },
      { label: "外卖适配", value: "—", unit: "/5", status: "pending" },
    ],
  },
];

export const SectionPanels: React.FC<PanelProps> = ({ onCreateProject }) => {
  return (
    <>
      {modules.map((mod) => (
        <Card key={mod.title} className="cursor-pointer" onClick={onCreateProject}>
          <CardContent className="py-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold text-on-background">{mod.title}</h3>
              <span className="text-[9px] font-mono text-amber-700 bg-amber-500/10 px-1.5 py-0.5 rounded">待录入数据</span>
            </div>
            <div className="grid grid-cols-4 gap-2">
              {mod.metrics.map((m) => (
                <div key={m.label} className="text-center">
                  <p className={cn("text-2xl font-semibold tabular-nums tracking-tight", m.status === "pending" ? "text-on-surface-variant/40" : "text-on-background")}>
                    {m.value}
                  </p>
                  <p className="mt-0.5 text-[9px] font-mono text-on-surface-variant">{m.label}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </>
  );
};
