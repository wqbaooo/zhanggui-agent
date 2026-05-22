"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const weeklyData = [
  { day: "周一", revenue: 2200, orders: 58 },
  { day: "周二", revenue: 2400, orders: 63 },
  { day: "周三", revenue: 2750, orders: 70 },
  { day: "周四", revenue: 2620, orders: 67 },
  { day: "周五", revenue: 3150, orders: 82 },
  { day: "周六", revenue: 2980, orders: 78 },
  { day: "周日", revenue: 2840, orders: 73 },
];

const monthlyData = [
  { month: "1月", revenue: 78000, cost: 42000, profit: 36000 },
  { month: "2月", revenue: 65000, cost: 36000, profit: 29000 },
  { month: "3月", revenue: 82000, cost: 44000, profit: 38000 },
  { month: "4月", revenue: 88000, cost: 46000, profit: 42000 },
  { month: "5月", revenue: 85000, cost: 45000, profit: 40000 },
];

const maxRev = Math.max(...weeklyData.map((d) => d.revenue));

export function DataAnalytics() {
  const [range, setRange] = useState<"7d" | "30d" | "12m">("7d");

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">数据分析 · 九江店</h2>
        <div className="flex gap-2">
          {(["7d", "30d", "12m"] as const).map((r) => (
            <Button key={r} variant={range === r ? "default" : "outline"} size="sm" onClick={() => setRange(r)}>{r === "7d" ? "7天" : r === "30d" ? "30天" : "12月"}</Button>
          ))}
        </div>
      </div>

      {range === "7d" && (
        <>
          <Card className="p-4">
            <p className="text-sm font-medium mb-3">本周营收趋势</p>
            <div className="flex items-end gap-2 h-40">
              {weeklyData.map((d) => (
                <div key={d.day} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-xs font-medium">¥{d.revenue.toLocaleString()}</span>
                  <div className="w-full bg-primary rounded-t" style={{ height: `${(d.revenue / maxRev) * 120}px`, opacity: 0.7 + (d.revenue / maxRev) * 0.3 }} />
                  <span className="text-xs text-muted-foreground">{d.day}</span>
                </div>
              ))}
            </div>
          </Card>
          <div className="grid grid-cols-3 gap-3">
            <Card className="p-3"><p className="text-xs text-muted-foreground">日均营收</p><p className="text-lg font-semibold">¥{(weeklyData.reduce((s, d) => s + d.revenue, 0) / 7).toFixed(0)}</p></Card>
            <Card className="p-3"><p className="text-xs text-muted-foreground">日均订单</p><p className="text-lg font-semibold">{(weeklyData.reduce((s, d) => s + d.orders, 0) / 7).toFixed(0)} 单</p></Card>
            <Card className="p-3"><p className="text-xs text-muted-foreground">周末 vs 工作日</p><p className="text-lg font-semibold text-green-700">+18%</p></Card>
          </div>
        </>
      )}

      {range === "12m" && (
        <Card className="p-4">
          <p className="text-sm font-medium mb-3">月度 P&L</p>
          <div className="space-y-2">
            {monthlyData.map((m) => (
              <div key={m.month} className="flex items-center gap-3 text-sm">
                <span className="w-10 text-muted-foreground">{m.month}</span>
                <div className="flex-1 h-5 bg-muted rounded relative overflow-hidden">
                  <div className="absolute inset-y-0 left-0 bg-green-200 rounded" style={{ width: `${(m.profit / m.revenue) * 100}%` }} />
                  <div className="absolute inset-y-0 left-0 bg-red-200 rounded" style={{ width: `${(m.cost / m.revenue) * 100}%` }} />
                </div>
                <span className="text-xs w-20 text-right">净利 ¥{m.profit.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {range === "30d" && (
        <div className="flex items-center justify-center h-40 text-muted-foreground text-sm">30 天视图 — 选择日期范围后展示</div>
      )}
    </div>
  );
}
