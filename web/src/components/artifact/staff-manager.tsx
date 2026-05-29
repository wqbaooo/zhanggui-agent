"use client";

import { Clock3, UserCheck, UsersRound, WalletCards } from "lucide-react";
import { Card } from "@/components/ui/card";

export function StaffManager() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold">人员排班 · 新余恒太城大口章鱼烧</h2>
        <p className="mt-1 text-sm text-muted-foreground">等待录入真实班次和工资；不会用假员工计算人力成本率。</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Card className="p-6">
          <UsersRound className="size-10 text-[#d95b00]" />
          <h3 className="mt-4 text-xl font-semibold">先验证老板亲自守店，再判断是否请人</h3>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            章鱼烧档口的人工判断不能只看“忙不忙”。要按订单峰值、出餐时间、排队流失和人工工资拆成两套账：老板自营模型与请人经营模型。
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            {[
              [Clock3, "高峰产能", "每小时可出多少单"],
              [WalletCards, "人工成本", "工资/营业额/毛利占比"],
              [UserCheck, "可复制性", "离开老板本人是否仍赚钱"],
            ].map(([Icon, title, text]) => (
              <div key={title as string} className="rounded-lg border border-[var(--app-border)] bg-[#fbfcfd] p-4">
                <Icon className="size-5 text-[#d95b00]" />
                <p className="mt-3 text-sm font-medium">{title as string}</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">{text as string}</p>
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-6">
          <p className="text-sm font-semibold">需要录入</p>
          <div className="mt-4 space-y-3 text-sm">
            {["每天营业时段", "每小时订单峰值", "是否亲自守店", "兼职/全职工资", "排队流失或差评记录"].map((item, index) => (
              <div key={item} className="flex items-center gap-3 rounded-lg bg-[#fbfcfd] p-3 ring-1 ring-[var(--app-border)]">
                <span className="flex size-6 items-center justify-center rounded bg-[#fff1df] text-xs text-[#d95b00]">{index + 1}</span>
                {item}
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
