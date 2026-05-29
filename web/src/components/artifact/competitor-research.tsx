"use client";

import { Camera, ClipboardList, MapPinned, Search, Store, Utensils } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const collectionTasks = [
  { icon: Store, title: "同层档口清单", detail: "店名、品类、排队情况、主推套餐、是否有团购。" },
  { icon: Utensils, title: "价格带与出餐", detail: "招牌价格、套餐结构、从点单到出餐的等待时间。" },
  { icon: Camera, title: "菜单与门头照片", detail: "正面拍清菜单、灯箱、动线遮挡、顾客停留点。" },
  { icon: Search, title: "线上口碑截图", detail: "美团/点评/抖音搜索结果、评分、差评关键词和销量口径。" },
];

const analysisFrames = [
  ["价格带", "章鱼烧不能只比同品类，要和烤冷面、炸鸡、寿司、串串等小吃档口争同一笔随手消费。"],
  ["速度带", "美食城小吃先看排队容忍度。高峰期出餐慢会直接丢单，Agent 会把等待时间转成产能上限。"],
  ["曝光位", "同层动线、灯箱朝向、排队外溢、收银口位置，比商场总客流更接近真实转化。"],
  ["复购点", "不是只看评分高低，而是找用户为什么回来：口味稳定、加料、套餐、会员券或社群提醒。"],
];

export function CompetitorResearch() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold">竞品调研 · 新余恒太城</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
            当前没有接入真实美团/点评/实地照片，因此不展示虚构竞品数量、月销量和评分。先把证据采回来，Agent 再输出可执行打法。
          </p>
        </div>
        <Badge variant="secondary">待采集证据</Badge>
      </div>

      <Card className="overflow-hidden p-0">
        <div className="grid lg:grid-cols-[0.92fr_1.08fr]">
          <div className="bg-[#101828] p-6 text-white">
            <MapPinned className="size-9 text-[#ffb45b]" />
            <h3 className="mt-4 text-xl font-semibold">美食城竞品不是“附近几家店”，而是同一条动线上的替代选择</h3>
            <p className="mt-3 text-sm leading-6 text-white/70">
              你接手的是已选铺位，竞品调研要服务开业 30 天动作：定价、套餐、出餐、门头、团购、私域和差评预案。
            </p>
            <div className="mt-6 rounded-lg border border-white/15 bg-white/8 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-white/50">Agent output after data</p>
              <p className="mt-2 text-sm leading-6 text-white/80">
                竞品热力图、价格带建议、高峰产能上限、替代品威胁、开业首周主推套餐。
              </p>
            </div>
          </div>
          <div className="grid gap-3 p-5 sm:grid-cols-2">
            {collectionTasks.map((task) => (
              <div key={task.title} className="rounded-lg border border-[var(--app-border)] bg-white p-4">
                <task.icon className="size-5 text-[#d95b00]" />
                <p className="mt-3 font-medium">{task.title}</p>
                <p className="mt-2 text-sm leading-5 text-muted-foreground">{task.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </Card>

      <div className="grid gap-3 md:grid-cols-4">
        {analysisFrames.map(([title, detail]) => (
          <Card key={title} className="p-4">
            <ClipboardList className="size-5 text-[#d95b00]" />
            <p className="mt-3 font-medium">{title}</p>
            <p className="mt-2 text-sm leading-5 text-muted-foreground">{detail}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
