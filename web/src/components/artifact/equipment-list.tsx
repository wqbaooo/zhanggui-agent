"use client";

import { ClipboardCheck, FileText, Gauge, PlugZap, ShieldCheck, Wrench } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const auditItems = [
  { icon: Wrench, title: "设备归属", detail: "转租费是否包含章鱼烧炉、冷柜、收银机、操作台、展示柜，逐项写进交接清单。" },
  { icon: Gauge, title: "可用状态", detail: "开机、加热、制冷、排烟、漏电保护都要现场测试，不能只看外观。" },
  { icon: PlugZap, title: "水电排烟", detail: "确认商场档口电量、上下水、排烟和消防要求能支撑高峰出餐。" },
  { icon: FileText, title: "总部要求", detail: "加盟品牌如果要求指定设备或指定物料，先确认哪些不能替换。" },
];

const handoverChecklist = [
  "设备型号、数量、照片、购买凭证或维修记录",
  "耗材与原料库存是否随店转让，临期品单独列出",
  "收银机、外卖平台、团购后台、二维码收款的账号归属",
  "水电费、物业费、商场扣点和押金是否有历史欠款",
  "损坏设备谁负责维修，交接后发现暗病如何处理",
];

export function EquipmentList() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold">设备与交接 · 大口章鱼烧</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
            这家店是转租接手，设备页面优先做交接审计，而不是假设你重新采购一整套设备。真实价格和维修成本要现场录入后再计算。
          </p>
        </div>
        <Badge variant="secondary">接店前核验</Badge>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        {auditItems.map((item) => (
          <Card key={item.title} className="p-4">
            <item.icon className="size-5 text-[#d95b00]" />
            <p className="mt-3 font-medium">{item.title}</p>
            <p className="mt-2 text-sm leading-5 text-muted-foreground">{item.detail}</p>
          </Card>
        ))}
      </div>

      <Card className="p-5">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="size-5 text-[#d95b00]" />
          <p className="font-semibold">交接清单</p>
        </div>
        <div className="mt-4 space-y-3">
          {handoverChecklist.map((item, index) => (
            <div key={item} className="flex gap-3 rounded-lg bg-[#fbfcfd] p-3 ring-1 ring-[var(--app-border)]">
              <span className="flex size-6 shrink-0 items-center justify-center rounded bg-[#fff1df] text-xs font-semibold text-[#d95b00]">{index + 1}</span>
              <span className="text-sm leading-6 text-muted-foreground">{item}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card className="border-[#fed7aa] bg-[#fff7ed] p-4">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-0.5 size-5 text-[#d95b00]" />
          <p className="text-sm leading-6 text-[#9a3412]">
            Agent 会在录入设备清单后输出“可继续用 / 必须维修 / 建议替换 / 总部不允许替换”四类结论，并把缺口自动带入开业预算。
          </p>
        </div>
      </Card>
    </div>
  );
}
