"use client";

import { Camera, MapPinned, Store, UsersRound } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export function SiteAnalysis() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">选址诊断 · 新余恒太城美食城</h2>
          <p className="mt-1 text-sm text-muted-foreground">铺位已基本确定，下一步是验证租金、人流转化和同层竞品。</p>
        </div>
        <Badge variant="secondary">待实地验证</Badge>
      </div>

      <Card className="overflow-hidden p-0">
        <div className="grid lg:grid-cols-[1.15fr_0.85fr]">
          <div className="relative min-h-[280px] bg-[#eef2f6] p-6">
            <div className="absolute inset-6 rounded-xl border border-dashed border-[#cbd5e1] bg-white/70" />
            <div className="relative z-10 flex h-full flex-col justify-between">
              <div>
                <MapPinned className="size-10 text-[#d95b00]" />
                <h3 className="mt-4 text-xl font-semibold">恒太城商场内部点位需要现场数据</h3>
                <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
                  商场内铺位不能只看高德 POI。必须拍同层动线、排队情况、竞品菜单和高峰 30 分钟转化。
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                {[
                  [Store, "同层竞品"],
                  [UsersRound, "高峰人流"],
                  [Camera, "铺位照片"],
                ].map(([Icon, label]) => (
                  <div key={label as string} className="rounded-lg bg-white p-3 shadow-sm">
                    <Icon className="size-5 text-[#d95b00]" />
                    <p className="mt-2 text-sm font-medium">{label as string}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="p-6">
            <p className="text-sm font-semibold">验收清单</p>
            <div className="mt-4 space-y-3">
              {[
                "工作日/周末午晚高峰各蹲点 30 分钟",
                "拍下同层所有小吃档口菜单和价格",
                "确认租金是固定、抽成还是保底+抽成",
                "记录上一家为什么转租、设备归属和水电费",
              ].map((item, index) => (
                <div key={item} className="flex gap-3 rounded-lg bg-[#fbfcfd] p-3 ring-1 ring-[var(--app-border)]">
                  <span className="flex size-6 shrink-0 items-center justify-center rounded bg-[#fff1df] text-xs text-[#d95b00]">{index + 1}</span>
                  <span className="text-sm">{item}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
