"use client";

import { BadgeCheck, CalendarDays, CircleDollarSign, MessageSquareText, RadioTower, ReceiptText, Repeat2, Video } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const channels = [
  {
    icon: Video,
    title: "抖音同城",
    status: "内容先行",
    detail: "先拍制作过程、出餐特写、试吃反馈和商场动线，不预设曝光数字；有核销后再判断是否投流。",
  },
  {
    icon: ReceiptText,
    title: "美团/点评",
    status: "开业入口",
    detail: "重点不是满减越大越好，而是菜单图、团购结构、评价承接和差评处理速度。",
  },
  {
    icon: MessageSquareText,
    title: "私域社群",
    status: "复购底座",
    detail: "把到店顾客沉淀为可触达用户，用新品试吃、集章和工作日低峰券拉复购。",
  },
  {
    icon: BadgeCheck,
    title: "商场资源",
    status: "低成本放大",
    detail: "争取美食城入口海报、商场社群、开业广播、楼层导视和联合活动曝光。",
  },
];

const timeline = [
  ["D-14", "账号、门店 POI、菜单图、团购结构和开业物料全部建好。"],
  ["D-7", "试拍 5 条短视频，准备 2 套开业套餐，确认总部是否允许改价和赠品。"],
  ["D-3", "亲友试吃和软开业，记录出餐时间、差评点、顾客最常问的问题。"],
  ["D-Day", "只做可承接的活动，避免排队过长、出餐崩盘和品质失控。"],
  ["D+7", "按流水、核销、复购、评价、损耗复盘，不用感觉判断渠道好坏。"],
  ["D+30", "决定下月是加投、改菜单、调班，还是换品类备选。"],
];

const metrics = [
  { icon: CircleDollarSign, label: "投放预算", value: "待设上限", hint: "先设止损，不先承诺 ROI" },
  { icon: Repeat2, label: "复购动作", value: "待建档", hint: "从社群/会员/集章开始" },
  { icon: RadioTower, label: "渠道归因", value: "待接入", hint: "抖音、美团、私域分开记账" },
];

export function MarketingPlan() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold">开业营销作战图 · 新余恒太城</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
            这里不写“预期曝光”“预期复购”这类没有数据支撑的结果。Agent 先帮你搭建可执行动作和记账口径，试营业后按真实核销与流水调优。
          </p>
        </div>
        <Badge variant="secondary">开业前 30 天</Badge>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        {metrics.map((item) => (
          <Card key={item.label} className="p-4">
            <item.icon className="size-5 text-[#d95b00]" />
            <p className="mt-3 text-xs text-muted-foreground">{item.label}</p>
            <p className="mt-1 text-lg font-semibold">{item.value}</p>
            <p className="text-xs text-muted-foreground">{item.hint}</p>
          </Card>
        ))}
      </div>

      <div className="grid gap-3 lg:grid-cols-4">
        {channels.map((channel) => (
          <Card key={channel.title} className="p-4">
            <div className="flex items-start justify-between gap-3">
              <channel.icon className="size-5 shrink-0 text-[#d95b00]" />
              <Badge variant="outline" className="text-xs">{channel.status}</Badge>
            </div>
            <p className="mt-4 font-medium">{channel.title}</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{channel.detail}</p>
          </Card>
        ))}
      </div>

      <Card className="p-5">
        <div className="flex items-center gap-2">
          <CalendarDays className="size-5 text-[#d95b00]" />
          <p className="font-semibold">30 天时间线</p>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {timeline.map(([day, text]) => (
            <div key={day} className="flex gap-3 rounded-lg bg-[#fbfcfd] p-3 ring-1 ring-[var(--app-border)]">
              <span className="flex h-7 min-w-14 items-center justify-center rounded bg-[#fff1df] text-xs font-semibold text-[#d95b00]">{day}</span>
              <p className="text-sm leading-6 text-muted-foreground">{text}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
