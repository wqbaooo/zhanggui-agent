"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface Permit {
  id: string;
  name: string;
  department: string;
  materials: string;
  days: number;
  cost: string;
  status: "pending" | "in_progress" | "done";
  notes: string;
}

const defaultPermits: Permit[] = [
  { id: "1", name: "营业执照（个体工商户）", department: "市场监管局", materials: "身份证、租赁合同、1寸照片", days: 7, cost: "免费", status: "pending", notes: "先签租赁合同再办" },
  { id: "2", name: "食品经营许可证", department: "市场监管局", materials: "营业执照、平面图、制度文件、健康证", days: 20, cost: "免费", status: "pending", notes: "装修完成后现场核查" },
  { id: "3", name: "健康证", department: "疾控中心/指定医院", materials: "身份证、1寸照片", days: 5, cost: "150元/人", status: "pending", notes: "每个员工都需办理" },
  { id: "4", name: "税务登记", department: "税务局", materials: "营业执照、身份证", days: 1, cost: "免费", status: "pending", notes: "拿到营业执照后30日内" },
  { id: "5", name: "消防备案", department: "消防大队", materials: "平面图、消防设施清单", days: 15, cost: "免费", status: "pending", notes: "面积<300㎡可备案" },
  { id: "6", name: "环保备案", department: "环保局", materials: "环评登记表", days: 7, cost: "免费", status: "pending", notes: "餐饮油烟需登记" },
  { id: "7", name: "银行开户", department: "商业银行", materials: "营业执照、公章、法人身份证", days: 3, cost: "100-300元/年", status: "pending", notes: "用于对公收款" },
];

const statusLabels: Record<string, { text: string; variant: "outline" | "secondary" | "default" }> = {
  pending: { text: "待办理", variant: "outline" },
  in_progress: { text: "办理中", variant: "secondary" },
  done: { text: "已完成", variant: "default" },
};

export function PermitChecklist() {
  const [permits, setPermits] = useState(defaultPermits);

  function cycleStatus(id: string) {
    setPermits((prev) =>
      prev.map((p) => {
        if (p.id !== id) return p;
        const next: Record<string, Permit["status"]> = { pending: "in_progress", in_progress: "done", done: "pending" };
        return { ...p, status: next[p.status] };
      })
    );
  }

  const doneCount = permits.filter((p) => p.status === "done").length;
  const totalDays = permits.reduce((s, p) => s + p.days, 0);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">证照办理 · 新余 · 小吃/现场制售</h2>
        <Badge variant="secondary">{doneCount}/{permits.length} 项完成</Badge>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">预计总耗时</p>
          <p className="text-xl font-semibold mt-1">{totalDays} 天</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">关键路径</p>
          <p className="text-sm font-medium mt-1">营业执照 → 食品许可</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">建议启动时间</p>
          <p className="text-sm font-medium mt-1">开业前 45 天</p>
        </Card>
      </div>

      <div className="space-y-2">
        {permits.map((p) => (
          <Card
            key={p.id}
            className={`p-4 cursor-pointer transition-colors hover:border-primary/30 ${
              p.status === "done" ? "opacity-60" : ""
            }`}
            onClick={() => cycleStatus(p.id)}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className={p.status === "done" ? "line-through text-muted-foreground" : ""}>
                    {p.name}
                  </span>
                  <Badge variant={statusLabels[p.status].variant} className="text-xs">
                    {statusLabels[p.status].text}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  办理部门：{p.department} · 预计 {p.days} 天 · 费用：{p.cost}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">材料：{p.materials}</p>
                {p.notes && <p className="text-xs text-muted-foreground/70 mt-0.5">💡 {p.notes}</p>}
              </div>
            </div>
          </Card>
        ))}
      </div>

      <p className="text-xs text-muted-foreground">点击卡片切换状态 · 实际流程以新余当地主管部门和商场管理方要求为准</p>
    </div>
  );
}
