"use client";

import { MessageSquareText, Repeat2, Star, UsersRound } from "lucide-react";
import { Card } from "@/components/ui/card";

export function CustomerFeedback() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold">会员与复购 · 新余恒太城大口章鱼烧</h2>
        <p className="mt-1 text-sm text-muted-foreground">这个模块不会再伪造评价。接入真实评价和会员数据后，才做 RFM、差评处理和召回。</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Card className="p-6">
          <div className="flex size-12 items-center justify-center rounded-xl bg-[#fff1df] text-[#d95b00]">
            <Repeat2 className="size-6" />
          </div>
          <h3 className="mt-4 text-xl font-semibold">复购增长不是看几条好评，而是看顾客回来没有</h3>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            开业后 30 天内先收集评价关键词、套餐核销、私域入群和二次消费记录。Agent 会把差评原因、复购触发点和召回动作合成一张增长清单。
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            {[
              [Star, "评价信号", "口味/出餐/价格/位置"],
              [UsersRound, "顾客沉淀", "入群、关注、加企微"],
              [MessageSquareText, "召回动作", "优惠券、上新、套餐提醒"],
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
          <p className="text-sm font-semibold">接入后会输出</p>
          <div className="mt-4 space-y-3">
            {["差评 24 小时处理清单", "高复购套餐识别", "沉睡顾客召回策略", "门店口碑关键词趋势"].map((item, index) => (
              <div key={item} className="flex gap-3 rounded-lg bg-[#fbfcfd] p-3 ring-1 ring-[var(--app-border)]">
                <span className="flex size-6 shrink-0 items-center justify-center rounded bg-[#fff1df] text-xs text-[#d95b00]">{index + 1}</span>
                <span className="text-sm">{item}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
