"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const channels = [
  { name: "抖音团购", budget: 1500, spend: 1200, exposure: "1.2万", conversions: 18, revenue: 450, roi: "1:3.2", status: "active" },
  { name: "美团推广通", budget: 800, spend: 600, exposure: "8,500", conversions: 42, revenue: 1680, roi: "1:2.8", status: "active" },
  { name: "小红书种草", budget: 300, spend: 300, exposure: "2,400", conversions: 5, revenue: 125, roi: "1:2.4", status: "active" },
  { name: "抖音达人", budget: 1000, spend: 1000, exposure: "3.5万", conversions: 12, revenue: 360, roi: "1:2.8", status: "completed" },
  { name: "私域社群", budget: 0, spend: 0, exposure: "186人", conversions: 23, revenue: 860, roi: "∞", status: "active" },
];

export function MarketingROI() {
  const totalSpend = channels.reduce((s, c) => s + c.spend, 0);
  const totalRevenue = channels.reduce((s, c) => s + c.revenue, 0);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">营销效果 · 九江店</h2>
        <Badge variant="secondary">{channels.length} 渠道</Badge>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card className="p-4"><p className="text-xs text-muted-foreground">总投入</p><p className="text-2xl font-semibold mt-1">¥{totalSpend.toLocaleString()}</p></Card>
        <Card className="p-4"><p className="text-xs text-muted-foreground">营销带来营收</p><p className="text-2xl font-semibold mt-1">¥{totalRevenue.toLocaleString()}</p></Card>
        <Card className="p-4"><p className="text-xs text-muted-foreground">综合 ROI</p><p className="text-2xl font-semibold mt-1 text-green-700">1:{(totalRevenue / totalSpend).toFixed(1)}</p></Card>
      </div>

      <div className="space-y-2">
        {channels.map((c) => (
          <Card key={c.name} className="p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm">{c.name}</span>
                <Badge variant={c.status === "active" ? "default" : "secondary"} className="text-xs">{c.status === "active" ? "进行中" : "已完成"}</Badge>
              </div>
              <span className="text-sm font-medium text-green-700">ROI {c.roi}</span>
            </div>
            <div className="grid grid-cols-5 gap-4 text-xs text-muted-foreground">
              <div><span className="block text-foreground font-medium">¥{c.spend.toLocaleString()}</span>花费</div>
              <div><span className="block text-foreground font-medium">{c.exposure}</span>曝光</div>
              <div><span className="block text-foreground font-medium">{c.conversions}</span>转化</div>
              <div><span className="block text-foreground font-medium">¥{c.revenue.toLocaleString()}</span>营收</div>
              <div><span className="block text-foreground font-medium">¥{c.budget.toLocaleString()}</span>预算</div>
            </div>
          </Card>
        ))}
      </div>

      <Card className="p-4 bg-accent/30">
        <p className="text-sm font-medium mb-2">优化建议</p>
        <div className="text-sm text-muted-foreground space-y-1">
          <p>🔥 美团 ROI 持续领先，建议追加预算至 ¥1,200/月</p>
          <p>📈 私域零成本高转化，扩大群规模到 300 人</p>
          <p>💡 小红书转化偏低但品牌价值高，持续投入做搜索占位</p>
        </div>
      </Card>
    </div>
  );
}
