"use client";

import { Boxes, ClipboardList, PackageSearch, ScanLine } from "lucide-react";
import { Card } from "@/components/ui/card";

export function InventoryManager() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold">库存管理 · 新余恒太城大口章鱼烧</h2>
        <p className="mt-1 text-sm text-muted-foreground">等待接入真实盘点和供应商数据；当前不展示假库存。</p>
      </div>

      <Card className="p-6">
        <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
          <div className="rounded-xl bg-[#fffaf3] p-6">
            <Boxes className="size-10 text-[#d95b00]" />
            <h3 className="mt-4 text-xl font-semibold">库存的目标是控制断货和报损</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              章鱼烧这类小吃要按“日耗、保质期、总部供货周期、外卖包装”四个字段建账。
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {[
              [ScanLine, "每日盘点", "原料、半成品、包装物"],
              [ClipboardList, "安全库存", "最小库存和补货提前期"],
              [PackageSearch, "报损复盘", "损耗原因、金额、责任归因"],
            ].map(([Icon, title, text]) => (
              <div key={title as string} className="rounded-lg border border-[var(--app-border)] bg-white p-4">
                <Icon className="size-5 text-[#d95b00]" />
                <p className="mt-3 text-sm font-medium">{title as string}</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">{text as string}</p>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </div>
  );
}
