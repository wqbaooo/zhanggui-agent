"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Entry {
  date: string;
  revenue: number;
  foodCost: number;
  labor: number;
  rent: number;
  utility: number;
  other: number;
}

const demoEntries: Entry[] = [
  { date: "5/22", revenue: 2840, foodCost: 1050, labor: 400, rent: 270, utility: 80, other: 120 },
  { date: "5/21", revenue: 2620, foodCost: 980, labor: 400, rent: 270, utility: 80, other: 100 },
  { date: "5/20", revenue: 3150, foodCost: 1180, labor: 400, rent: 270, utility: 80, other: 150 },
  { date: "5/19", revenue: 2200, foodCost: 830, labor: 400, rent: 270, utility: 80, other: 90 },
  { date: "5/18", revenue: 2980, foodCost: 1100, labor: 400, rent: 270, utility: 80, other: 130 },
  { date: "5/17", revenue: 2750, foodCost: 1020, labor: 400, rent: 270, utility: 80, other: 110 },
  { date: "5/16", revenue: 2400, foodCost: 900, labor: 400, rent: 270, utility: 80, other: 95 },
];

export function IncomeJournal() {
  const [view, setView] = useState<"daily" | "monthly">("daily");

  const totalRevenue = demoEntries.reduce((s, e) => s + e.revenue, 0);
  const totalCost = demoEntries.reduce((s, e) => s + e.foodCost + e.labor + e.rent + e.utility + e.other, 0);
  const totalProfit = totalRevenue - totalCost;
  const margin = ((totalProfit / totalRevenue) * 100).toFixed(1);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">收支记账 · 九江店</h2>
        <div className="flex gap-2">
          <Button variant={view === "daily" ? "default" : "outline"} size="sm" onClick={() => setView("daily")}>日视图</Button>
          <Button variant={view === "monthly" ? "default" : "outline"} size="sm" onClick={() => setView("monthly")}>月汇总</Button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card className="p-4"><p className="text-xs text-muted-foreground">7 日总营收</p><p className="text-2xl font-semibold mt-1">¥{totalRevenue.toLocaleString()}</p></Card>
        <Card className="p-4"><p className="text-xs text-muted-foreground">7 日总成本</p><p className="text-2xl font-semibold mt-1">¥{totalCost.toLocaleString()}</p></Card>
        <Card className="p-4"><p className="text-xs text-muted-foreground">7 日净利润</p><p className={`text-2xl font-semibold mt-1 ${totalProfit >= 0 ? "text-green-700" : "text-red-700"}`}>¥{totalProfit.toLocaleString()}<span className="text-sm ml-1">({margin}%)</span></p></Card>
      </div>

      <div className="space-y-1">
        <div className="grid grid-cols-7 text-xs text-muted-foreground px-3 py-1">
          <span>日期</span><span className="text-right">营收</span><span className="text-right">食材</span><span className="text-right">人工</span><span className="text-right">租金</span><span className="text-right">杂费</span><span className="text-right">净利</span>
        </div>
        {demoEntries.map((e) => {
          const profit = e.revenue - e.foodCost - e.labor - e.rent - e.utility - e.other;
          return (
            <Card key={e.date} className="p-2 hover:bg-muted/30 transition-colors">
              <div className="grid grid-cols-7 text-sm items-center">
                <span className="font-medium">{e.date}</span>
                <span className="text-right">¥{e.revenue.toLocaleString()}</span>
                <span className="text-right text-muted-foreground">¥{e.foodCost}</span>
                <span className="text-right text-muted-foreground">¥{e.labor}</span>
                <span className="text-right text-muted-foreground">¥{e.rent}</span>
                <span className="text-right text-muted-foreground">¥{e.utility + e.other}</span>
                <span className={`text-right font-medium ${profit >= 0 ? "text-green-700" : ""}`}>¥{profit.toLocaleString()}</span>
              </div>
            </Card>
          );
        })}
      </div>

      <Card className="p-4 bg-accent/30">
        <p className="text-sm font-medium mb-2">月 P&L 预估</p>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="space-y-1">
            <div className="flex justify-between"><span className="text-muted-foreground">月营收</span><span>¥{(totalRevenue / 7 * 30).toFixed(0)}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">食材成本</span><span>¥{(totalCost * 0.65 / 7 * 30).toFixed(0)}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">固定成本</span><span>¥{(totalCost * 0.35 / 7 * 30).toFixed(0)}</span></div>
          </div>
          <div className="space-y-1">
            <div className="flex justify-between"><span className="text-muted-foreground">月净利</span><span className="font-medium">¥{(totalProfit / 7 * 30).toFixed(0)}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">日均营收</span><span>¥{(totalRevenue / 7).toFixed(0)}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">食材成本率</span><span>{(demoEntries.reduce((s,e) => s + e.foodCost, 0) / totalRevenue * 100).toFixed(1)}%</span></div>
          </div>
        </div>
      </Card>
    </div>
  );
}
