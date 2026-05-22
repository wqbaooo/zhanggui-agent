"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

interface Equipment {
  id: string;
  name: string;
  qty: number;
  estPrice: number;
  actualPrice: number | null;
  status: "pending" | "ordered" | "received";
}

const defaultEquipment: Equipment[] = [
  { id: "1", name: "章鱼烧烤盘（6孔）", qty: 2, estPrice: 3500, actualPrice: 3200, status: "ordered" },
  { id: "2", name: "商用冷冻柜 300L", qty: 1, estPrice: 2800, actualPrice: null, status: "pending" },
  { id: "3", name: "收银机 + 小票打印机", qty: 1, estPrice: 1800, actualPrice: null, status: "pending" },
  { id: "4", name: "不锈钢操作台 1.5m", qty: 2, estPrice: 1200, actualPrice: null, status: "pending" },
  { id: "5", name: "排烟罩 + 风机", qty: 1, estPrice: 2500, actualPrice: null, status: "pending" },
  { id: "6", name: "展示柜（前厅）", qty: 1, estPrice: 1800, actualPrice: null, status: "pending" },
  { id: "7", name: "电子秤 + 温度计", qty: 2, estPrice: 300, actualPrice: null, status: "pending" },
  { id: "8", name: "一次性餐具（首批）", qty: 500, estPrice: 800, actualPrice: 500, status: "ordered" },
];

const statusLabels: Record<string, { text: string; variant: "outline" | "secondary" | "default" }> = {
  pending: { text: "待采购", variant: "outline" },
  ordered: { text: "已下单", variant: "secondary" },
  received: { text: "已到货", variant: "default" },
};

export function EquipmentList() {
  const [equipment, setEquipment] = useState(defaultEquipment);

  function cycle(id: string) {
    setEquipment((prev) =>
      prev.map((e) => {
        if (e.id !== id) return e;
        const next: Record<string, Equipment["status"]> = { pending: "ordered", ordered: "received", received: "pending" };
        return { ...e, status: next[e.status] };
      })
    );
  }

  const totalEst = equipment.reduce((s, e) => s + e.estPrice * e.qty, 0);
  const totalActual = equipment.reduce((s, e) => s + (e.actualPrice || e.estPrice) * e.qty, 0);
  const spent = equipment.filter((e) => e.status !== "pending").reduce((s, e) => s + (e.actualPrice || e.estPrice) * e.qty, 0);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">设备采购 · 大口章鱼烧</h2>
        <Badge variant="secondary">{equipment.filter((e) => e.status === "received").length}/{equipment.length} 到货</Badge>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">预算总计</p>
          <p className="text-xl font-semibold mt-1">¥{totalEst.toLocaleString()}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">已花费</p>
          <p className="text-xl font-semibold mt-1">¥{spent.toLocaleString()}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">预估 vs 实际</p>
          <p className={`text-xl font-semibold mt-1 ${totalActual < totalEst ? "text-green-700" : "text-red-700"}`}>
            {totalActual < totalEst ? "↓" : "↑"} ¥{Math.abs(totalEst - totalActual).toLocaleString()}
          </p>
        </Card>
      </div>

      <div className="space-y-2">
        {equipment.map((e) => (
          <Card
            key={e.id}
            className="p-3 cursor-pointer hover:border-primary/30 transition-colors"
            onClick={() => cycle(e.id)}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium w-40">{e.name}</span>
                <span className="text-xs text-muted-foreground">×{e.qty}</span>
                <span className="text-xs text-muted-foreground">
                  预估 ¥{(e.estPrice * e.qty).toLocaleString()}
                  {e.actualPrice && (
                    <span className={e.actualPrice < e.estPrice ? "text-green-700 ml-1" : "text-red-700 ml-1"}>
                      → 实际 ¥{(e.actualPrice * e.qty).toLocaleString()}
                    </span>
                  )}
                </span>
              </div>
              <Badge variant={statusLabels[e.status].variant} className="text-xs">
                {statusLabels[e.status].text}
              </Badge>
            </div>
          </Card>
        ))}
      </div>

      <p className="text-xs text-muted-foreground">点击切换采购状态 · 核心设备买新，辅助淘二手，比价 ≥ 3 家</p>
    </div>
  );
}
