"use client";

import { Card } from "@/components/ui/card";

interface MenuItem {
  name: string;
  price: number;
  cost: number;
  margin: number;
  weeklySales: number;
  trend: "up" | "down" | "stable";
}

const menuItems: MenuItem[] = [
  { name: "经典章鱼烧（6颗）", price: 25, cost: 9, margin: 64, weeklySales: 210, trend: "up" },
  { name: "芝士章鱼烧", price: 30, cost: 12, margin: 60, weeklySales: 145, trend: "up" },
  { name: "双拼套餐（章鱼烧+饮品）", price: 38, cost: 16, margin: 58, weeklySales: 98, trend: "stable" },
  { name: "大份章鱼烧（10颗）", price: 38, cost: 14, margin: 63, weeklySales: 65, trend: "down" },
  { name: "章鱼小丸子（儿童版）", price: 15, cost: 5, margin: 67, weeklySales: 42, trend: "stable" },
  { name: "炸鱿鱼须", price: 18, cost: 8, margin: 56, weeklySales: 35, trend: "down" },
];

const quadrantLabel: Record<string, string> = { Stars: "明星", Puzzles: "潜力", Plowhorses: "走量", Dogs: "瘦狗" };
const quadrantColor: Record<string, string> = {
  Stars: "bg-green-100 text-green-800",
  Puzzles: "bg-yellow-100 text-yellow-800",
  Plowhorses: "bg-blue-100 text-blue-800",
  Dogs: "bg-gray-100 text-gray-800",
};

export function MenuOptimization() {
  const avgMargin = menuItems.reduce((s, i) => s + i.margin, 0) / menuItems.length;
  const avgSales = menuItems.reduce((s, i) => s + i.weeklySales, 0) / menuItems.length;

  function getQuadrant(item: MenuItem) {
    if (item.margin > avgMargin && item.weeklySales > avgSales) return "Stars";
    if (item.margin > avgMargin && item.weeklySales <= avgSales) return "Puzzles";
    if (item.margin <= avgMargin && item.weeklySales > avgSales) return "Plowhorses";
    return "Dogs";
  }

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-lg font-semibold">菜单优化 · 大口章鱼烧 九江店</h2>

      <div className="grid grid-cols-3 gap-3">
        {menuItems.map((item) => {
          const q = getQuadrant(item);
          return (
            <Card key={item.name} className="p-3">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium truncate">{item.name}</p>
                <span className={`text-xs px-1.5 py-0.5 rounded ${quadrantColor[q]}`}>
                  {quadrantLabel[q]}
                </span>
              </div>
              <div className="space-y-1 text-xs text-muted-foreground">
                <div className="flex justify-between"><span>售价</span><span>¥{item.price}</span></div>
                <div className="flex justify-between"><span>成本</span><span>¥{item.cost}</span></div>
                <div className="flex justify-between"><span>毛利</span><span className="font-medium text-green-700">{item.margin}%</span></div>
                <div className="flex justify-between">
                  <span>周销量</span>
                  <span>{item.weeklySales} 单 {item.trend === "up" ? "↑" : item.trend === "down" ? "↓" : "→"}</span>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      <Card className="p-4 bg-accent/30">
        <p className="text-sm font-medium mb-2">优化建议</p>
        <div className="text-sm text-muted-foreground space-y-1">
          <p>⭐ 经典章鱼烧：明星产品，保持品质 + 加大抖音曝光</p>
          <p>💡 芝士章鱼烧：潜力产品，做为主推新品（利润率好）</p>
          <p>📦 大份章鱼烧：走量但趋势下降，考虑调价或改包装</p>
          <p>⚠️ 炸鱿鱼须：低毛利低销量，考虑下架或替换</p>
        </div>
      </Card>
    </div>
  );
}
