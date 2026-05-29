"use client";

import { AlertTriangle, Building2, ClipboardCheck, ReceiptText, Store } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export function ProjectOverview() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">大口章鱼烧 · 新余恒太城</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">转租费 ¥30,000 · 押金 ¥10,000 · 当前阶段：开业计划</p>
        </div>
        <Badge variant="secondary">准备接店</Badge>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        {[
          [Store, "铺位", "恒太城美食城", "已确定"],
          [ReceiptText, "投入", "¥40,000", "转租+押金"],
          [Building2, "品牌", "加盟大口章鱼烧", "需补总部约束"],
          [ClipboardCheck, "经营账本", "0 天", "待试营业录入"],
        ].map(([Icon, label, value, sub]) => (
          <Card key={label as string} className="p-4">
            <Icon className="size-5 text-[#d95b00]" />
            <p className="mt-3 text-xs text-muted-foreground">{label as string}</p>
            <p className="mt-1 text-lg font-semibold">{value as string}</p>
            <p className="text-xs text-muted-foreground">{sub as string}</p>
          </Card>
        ))}
      </div>

      <Card className="p-5">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 size-5 text-[#d95b00]" />
          <div>
            <p className="font-semibold">当前项目最重要的不是再找铺，而是把接店前的假设变成可验证账本</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              选址基本确定后，项目概览要围绕合同、转租条件、总部约束、试营业日账和开业 30 天执行来推进。这里不会再展示南昌/九江样例数据。
            </p>
          </div>
        </div>
      </Card>

      <div className="grid gap-3 md:grid-cols-3">
        {[
          ["接店前", "确认房东、转租协议、总部加盟约束、设备归属"],
          ["试营业", "连续记录 7 天营业额、订单、食材、人工、平台费"],
          ["开业后", "用 30/60/90 天复盘推进运营接管、复购增长、可复制模型"],
        ].map(([title, text]) => (
          <Card key={title} className="p-4">
            <p className="font-medium">{title}</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{text}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
