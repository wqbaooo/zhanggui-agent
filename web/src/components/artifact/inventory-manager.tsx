"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const inventory = [
  { name: "章鱼粉", unit: "kg", stock: 3, minStock: 5, dailyUse: 2, supplier: "东海食品" },
  { name: "章鱼足", unit: "kg", stock: 8, minStock: 5, dailyUse: 3, supplier: "鲜达水产" },
  { name: "芝士碎", unit: "kg", stock: 2, minStock: 3, dailyUse: 1.2, supplier: "安佳代理" },
  { name: "天妇罗粉", unit: "kg", stock: 5, minStock: 4, dailyUse: 1.5, supplier: "东海食品" },
  { name: "照烧酱", unit: "瓶", stock: 12, minStock: 6, dailyUse: 2, supplier: "调味品批发" },
  { name: "一次性餐盒", unit: "个", stock: 150, minStock: 200, dailyUse: 60, supplier: "1688" },
  { name: "竹签", unit: "包", stock: 8, minStock: 5, dailyUse: 2, supplier: "1688" },
  { name: "包装袋", unit: "个", stock: 300, minStock: 200, dailyUse: 50, supplier: "本地印刷厂" },
];

export function InventoryManager() {
  const lowStock = inventory.filter((i) => i.stock < i.minStock);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">库存管理 · 九江店</h2>
        {lowStock.length > 0 && <Badge className="bg-red-100 text-red-800">{lowStock.length} 项低库存</Badge>}
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card className="p-4"><p className="text-xs text-muted-foreground">库存品类</p><p className="text-2xl font-semibold mt-1">{inventory.length}</p></Card>
        <Card className="p-4"><p className="text-xs text-muted-foreground">低库存预警</p><p className="text-2xl font-semibold mt-1 text-red-700">{lowStock.length}</p></Card>
        <Card className="p-4"><p className="text-xs text-muted-foreground">今日需补货</p><p className="text-2xl font-semibold mt-1">{inventory.filter(i => i.stock < i.dailyUse * 2).length}</p></Card>
      </div>

      <div className="space-y-1">
        <div className="grid grid-cols-7 text-xs text-muted-foreground px-3 py-1">
          <span className="col-span-2">物料</span><span>库存</span><span>安全线</span><span>日耗</span><span>状态</span><span>供应商</span>
        </div>
        {inventory.map((item) => {
          const status = item.stock < item.minStock ? "low" : item.stock < item.minStock * 2 ? "warning" : "ok";
          return (
            <Card key={item.name} className={`p-3 ${status === "low" ? "border-l-4 border-l-red-500" : ""}`}>
              <div className="grid grid-cols-7 text-sm items-center">
                <span className="col-span-2 font-medium">{item.name}</span>
                <span>{item.stock} {item.unit}</span>
                <span className="text-muted-foreground">{item.minStock} {item.unit}</span>
                <span className="text-muted-foreground">{item.dailyUse} {item.unit}/天</span>
                <span>
                  <Badge className={`text-xs ${
                    status === "low" ? "bg-red-100 text-red-800" : status === "warning" ? "bg-yellow-100 text-yellow-800" : "bg-green-100 text-green-800"
                  }`}>
                    {status === "low" ? "需补货" : status === "warning" ? "偏低" : "充足"}
                  </Badge>
                </span>
                <span className="text-xs text-muted-foreground">{item.supplier}</span>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
