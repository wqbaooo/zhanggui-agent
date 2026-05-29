"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { DEFAULT_PROJECT_ID, getOperationSummary, type OperationSummary } from "@/lib/api";

function money(value: number) {
  return `¥${Math.round(value).toLocaleString()}`;
}

export function OperationDashboard() {
  const [summary, setSummary] = useState<OperationSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getOperationSummary(DEFAULT_PROJECT_ID, 7)
      .then(setSummary)
      .catch(() => setError("后端暂未启动，启动 API 后这里会显示真实经营数据。"));
  }, []);

  const latest = summary?.latest_entry;
  const grossProfit = latest
    ? latest.revenue - latest.food_cost - latest.platform_fee - latest.marketing_cost - latest.inventory_loss
    : 0;
  const grossRate = latest?.revenue ? Math.round((grossProfit / latest.revenue) * 100) : 0;

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-lg font-semibold">经营看板 · 新余恒太城大口章鱼烧</h2>

      {error ? (
        <Card className="p-4 border-l-4 border-l-yellow-500 text-sm">{error}</Card>
      ) : null}

      {!summary || summary.entry_count === 0 ? (
        <Card className="p-5">
          <p className="text-sm font-medium">还没有录入营业数据</p>
          <p className="text-sm text-muted-foreground mt-1">
            开店前先录入转租费、押金、租金和试营业数据；开店后每天记录营业额、订单、食材、人工、外卖扣点和活动成本。
          </p>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-3">
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">最近一日营业额</p>
              <p className="text-2xl font-semibold mt-1">{money(latest?.revenue || 0)}</p>
              <p className="text-xs text-muted-foreground mt-1">{latest?.date || "暂无日期"}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">最近一日订单</p>
              <p className="text-2xl font-semibold mt-1">{latest?.orders || 0} 单</p>
              <p className="text-xs text-muted-foreground mt-1">客单价 {money(summary.avg_order_value)}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">最近一日毛利预估</p>
              <p className="text-2xl font-semibold mt-1">{money(grossProfit)}</p>
              <p className="text-xs text-muted-foreground mt-1">毛利率 {grossRate}%</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">7 日净利润</p>
              <p className={`text-2xl font-semibold mt-1 ${summary.net_profit >= 0 ? "text-green-700" : "text-red-700"}`}>
                {money(summary.net_profit)}
              </p>
              <p className="text-xs text-muted-foreground mt-1">食材率 {(summary.food_cost_rate * 100).toFixed(1)}%</p>
            </Card>
          </div>

          <div>
            <h3 className="text-sm font-medium mb-3">渠道与成本信号</h3>
            <div className="grid grid-cols-4 gap-3">
              <Card className="p-3">
                <p className="text-xs font-medium">外卖占比</p>
                <p className="text-lg font-semibold mt-1">{(summary.takeout_ratio * 100).toFixed(1)}%</p>
                <p className="text-xs text-muted-foreground">必须单独算平台扣点</p>
              </Card>
              <Card className="p-3">
                <p className="text-xs font-medium">平台/营销</p>
                <p className="text-lg font-semibold mt-1">{money((latest?.platform_fee || 0) + (latest?.marketing_cost || 0))}</p>
                <p className="text-xs text-muted-foreground">最近一日</p>
              </Card>
              <Card className="p-3">
                <p className="text-xs font-medium">人工</p>
                <p className="text-lg font-semibold mt-1">{money(latest?.labor || 0)}</p>
                <p className="text-xs text-muted-foreground">区分亲自守店/请人</p>
              </Card>
              <Card className="p-3">
                <p className="text-xs font-medium">租金摊销</p>
                <p className="text-lg font-semibold mt-1">{money(latest?.rent_allocated || 0)}</p>
                <p className="text-xs text-muted-foreground">看真实日盈亏</p>
              </Card>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium mb-3">预警中心</h3>
            <div className="space-y-2">
              {summary.alerts.length === 0 ? (
                <Card className="p-3 text-sm text-muted-foreground">当前没有触发预警；持续录入后会按食材率、亏损、外卖成本自动判断。</Card>
              ) : summary.alerts.map((alert, index) => (
                <Card key={`${alert.level}-${index}`} className={`p-3 border-l-4 ${alert.level === "high" ? "border-l-red-500" : "border-l-yellow-500"}`}>
                  <p className="text-sm">{alert.message}</p>
                </Card>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
