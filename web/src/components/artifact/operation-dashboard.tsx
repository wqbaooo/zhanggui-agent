"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const alerts = [
  { id: "1", text: "食材成本连续 2 周上升至 42%（30日均值 38%），建议检查章鱼进货渠道", severity: "high", time: "2 小时前" },
  { id: "2", text: "周五晚市人力不足，过去 3 周此时段产能缺口 30%，建议加 1 名兼职", severity: "medium", time: "昨天" },
  { id: "3", text: "小红书新增 2 条差评，涉及出餐速度和口味一致性", severity: "high", time: "昨天" },
  { id: "4", text: "库存：章鱼粉剩余不足 3 天用量，需补货", severity: "medium", time: "3 小时前" },
];

export function OperationDashboard() {
  return (
    <div className="p-6 space-y-6">
      <h2 className="text-lg font-semibold">经营看板 · 大口章鱼烧 九江店</h2>

      <div className="grid grid-cols-4 gap-3">
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">今日营业额</p>
          <p className="text-2xl font-semibold mt-1">¥2,840</p>
          <p className="text-xs text-green-700 mt-1">↑ 8% vs 上周同天</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">订单数</p>
          <p className="text-2xl font-semibold mt-1">73 单</p>
          <p className="text-xs text-muted-foreground mt-1">客单价 ¥38.9</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">毛利预估</p>
          <p className="text-2xl font-semibold mt-1">¥1,562</p>
          <p className="text-xs text-muted-foreground mt-1">毛利率 55%</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">本周趋势</p>
          <p className="text-2xl font-semibold mt-1">↑</p>
          <p className="text-xs text-muted-foreground mt-1">周一→周五 稳步上升</p>
        </Card>
      </div>

      <div>
        <h3 className="text-sm font-medium mb-3">营销渠道效果</h3>
        <div className="grid grid-cols-4 gap-3">
          {[
            { channel: "抖音", metric: "1.2万 曝光", sub: "团购核销 18 单", roi: "ROI 1:3.2" },
            { channel: "美团", metric: "42 单外卖", sub: "评分 4.6", roi: "佣金 ¥226" },
            { channel: "小红书", metric: "3 篇笔记", sub: "收藏 156", roi: "自然流量" },
            { channel: "私域", metric: "186 群成员", sub: "复购率 32%", roi: "零成本" },
          ].map((c) => (
            <Card key={c.channel} className="p-3">
              <p className="text-xs font-medium">{c.channel}</p>
              <p className="text-lg font-semibold mt-1">{c.metric}</p>
              <p className="text-xs text-muted-foreground">{c.sub}</p>
              <p className="text-xs text-green-700 mt-0.5">{c.roi}</p>
            </Card>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium mb-3">预警中心</h3>
        <div className="space-y-2">
          {alerts.map((a) => (
            <Card key={a.id} className={`p-3 border-l-4 ${a.severity === "high" ? "border-l-red-500" : "border-l-yellow-500"}`}>
              <div className="flex items-center justify-between">
                <p className="text-sm">{a.text}</p>
                <span className="text-xs text-muted-foreground shrink-0 ml-4">{a.time}</span>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
