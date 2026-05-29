"use client";

import { Megaphone, MousePointerClick, ReceiptText, TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/card";

const required = [
  ["渠道花费", "抖音/美团/小红书/私域每日投入"],
  ["核销收入", "团购、外卖、到店套餐分开记录"],
  ["订单归因", "顾客从哪个渠道看到、下单、复购"],
];

export function MarketingROI() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold">营销效果 · 新余恒太城大口章鱼烧</h2>
        <p className="mt-1 text-sm text-muted-foreground">等待接入真实渠道数据；未接入前不展示虚假 ROI。</p>
      </div>

      <Card className="overflow-hidden rounded-xl border border-[var(--app-border)] bg-white p-0">
        <div className="grid md:grid-cols-[1fr_340px]">
          <div className="p-6">
            <div className="flex size-12 items-center justify-center rounded-xl bg-[#fff1df] text-[#d95b00]">
              <Megaphone className="size-6" />
            </div>
            <h3 className="mt-4 text-xl font-semibold">营销 ROI 需要先建立归因口径</h3>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              外卖满减、团购核销、达人探店和私域复购不能混在一起算。这里会先沉淀渠道花费和核销收入，再由 Agent 判断该加预算、停投还是换套餐。
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              {[
                ["外卖", "扣点/满减/包装费"],
                ["团购", "核销价/到店转化"],
                ["私域", "入群/复购/召回"],
              ].map(([title, text]) => (
                <div key={title} className="rounded-lg border border-[var(--app-border)] bg-[#fbfcfd] p-4">
                  <p className="font-medium">{title}</p>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">{text}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="border-t bg-[#fbfcfd] p-6 md:border-l md:border-t-0">
            <p className="text-sm font-semibold">需要补齐</p>
            <div className="mt-4 space-y-3">
              {required.map(([title, text], index) => (
                <div key={title} className="flex gap-3 rounded-lg bg-white p-3 ring-1 ring-[var(--app-border)]">
                  <span className="flex size-6 shrink-0 items-center justify-center rounded bg-[#fff1df] text-xs font-semibold text-[#d95b00]">{index + 1}</span>
                  <div>
                    <p className="text-sm font-medium">{title}</p>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">{text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-3 md:grid-cols-3">
        {[
          [MousePointerClick, "投前", "先设计可追踪套餐和渠道口令"],
          [ReceiptText, "投中", "每日记录花费、核销和订单毛利"],
          [TrendingUp, "投后", "7 天后自动输出加投/停投建议"],
        ].map(([Icon, title, text]) => (
          <Card key={title as string} className="p-4">
            <Icon className="size-5 text-[#d95b00]" />
            <p className="mt-3 font-medium">{title as string}</p>
            <p className="mt-1 text-sm text-muted-foreground">{text as string}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
