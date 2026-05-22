"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface Risk {
  id: string;
  category: string;
  description: string;
  severity: "critical" | "high" | "medium" | "low";
  probability: "high" | "medium" | "low";
  status: "monitoring" | "mitigated" | "accepted";
  mitigation: string;
}

const defaultRisks: Risk[] = [
  {
    id: "1", category: "市场风险", description: "章鱼烧品类季节性波动（暑期高校放假，客流下降 30%）",
    severity: "high", probability: "high", status: "monitoring",
    mitigation: "增加外卖占比 + 开发冬季热饮产品线（关东煮/热汤）",
  },
  {
    id: "2", category: "选址风险", description: "万达金街二楼曝光度不足，依赖商场引流",
    severity: "high", probability: "medium", status: "monitoring",
    mitigation: "强化抖音 POI 定位 + 美团外卖覆盖 3km + 一楼设指引牌",
  },
  {
    id: "3", category: "合同风险", description: "转让合同可能存在隐藏条款（押金退还条件、续租涨幅）",
    severity: "critical", probability: "medium", status: "mitigated",
    mitigation: "合同已交律师审核，押二付一，年涨幅 ≤5% 条款已写入",
  },
  {
    id: "4", category: "成本风险", description: "章鱼原料价格波动大（进口依赖度高），成本可能上升 20%",
    severity: "medium", probability: "medium", status: "monitoring",
    mitigation: "锁定 3 个月供应价 + 开发国产替代供应商 + 调整份量",
  },
  {
    id: "5", category: "运营风险", description: "新手操作不当导致出品不稳定，引发差评",
    severity: "medium", probability: "high", status: "mitigated",
    mitigation: "开业前练摊 30 天 + SOP 标准化 + 试营业 3 天收集反馈",
  },
  {
    id: "6", category: "竞争风险", description: "周边新开同类店铺，客流被分流",
    severity: "medium", probability: "low", status: "accepted",
    mitigation: "建立会员体系锁定老客 + 每月推新品保持新鲜感",
  },
  {
    id: "7", category: "资金风险", description: "开业前 3 个月可能亏损，账面资金不足",
    severity: "critical", probability: "medium", status: "monitoring",
    mitigation: "预留 3 个月运营资金（¥33,000）+ 设置止损线（连续 3 月亏本 → 暂停）",
  },
  {
    id: "8", category: "合规风险", description: "食品经营许可证现场核查不通过",
    severity: "high", probability: "low", status: "mitigated",
    mitigation: "装修前咨询市监局要求 + 参照同品类店铺设计厨房布局",
  },
];

const severityColors: Record<string, string> = {
  critical: "bg-red-100 text-red-800",
  high: "bg-orange-100 text-orange-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-green-100 text-green-800",
};

const statusColors: Record<string, string> = {
  monitoring: "bg-blue-100 text-blue-800",
  mitigated: "bg-green-100 text-green-800",
  accepted: "bg-gray-100 text-gray-800",
};

export function RiskRegister() {
  const [risks] = useState(defaultRisks);

  const criticalCount = risks.filter((r) => r.severity === "critical").length;
  const unmitigated = risks.filter((r) => r.status === "monitoring").length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">风险评估 · 大口章鱼烧</h2>
        <Badge variant="secondary">{risks.length} 项风险</Badge>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">致命风险</p>
          <p className="text-xl font-semibold mt-1 text-red-700">{criticalCount} 项</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">监控中</p>
          <p className="text-xl font-semibold mt-1 text-blue-700">{unmitigated} 项</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">已缓解</p>
          <p className="text-xl font-semibold mt-1 text-green-700">{risks.length - unmitigated} 项</p>
        </Card>
      </div>

      <div className="space-y-2">
        {risks.map((r) => (
          <Card key={r.id} className="p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <Badge className={`text-xs ${severityColors[r.severity]}`}>
                    {r.severity === "critical" ? "致命" : r.severity === "high" ? "高" : r.severity === "medium" ? "中" : "低"}
                  </Badge>
                  <Badge variant="outline" className="text-xs">{r.category}</Badge>
                  <Badge className={`text-xs ${statusColors[r.status]}`}>
                    {r.status === "monitoring" ? "监控中" : r.status === "mitigated" ? "已缓解" : "已接受"}
                  </Badge>
                </div>
                <p className="text-sm">{r.description}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  🛡️ 缓解措施：{r.mitigation}
                </p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Card className="p-4 border-red-200 bg-red-50/50">
        <p className="text-sm font-medium text-red-800 mb-2">止损线</p>
        <p className="text-sm text-red-700">
          连续 3 个月亏本 → 暂停运营 → 诊断原因 → 调整或转让
        </p>
      </Card>
    </div>
  );
}
