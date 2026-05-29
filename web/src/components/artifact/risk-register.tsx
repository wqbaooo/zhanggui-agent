"use client";

import { AlertTriangle, FileWarning, Landmark, ReceiptText, ShieldAlert, Store, UsersRound } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const risks = [
  {
    icon: FileWarning,
    level: "致命",
    category: "转租合同",
    description: "房东同意、押金退还、设备归属、商场管理规则和品牌加盟约束必须同时成立。",
    action: "把三方确认、转租协议、设备清单、欠费声明和续租条件一次性补齐。",
  },
  {
    icon: UsersRound,
    level: "高",
    category: "人力模型",
    description: "原店请两个人导致利润被人工吃掉。你接手后要先算老板亲自守店模型，再决定是否请人。",
    action: "试营业 7 天记录高峰订单、出餐时间和单人可承接量。",
  },
  {
    icon: Store,
    level: "高",
    category: "商场转化",
    description: "恒太城人多不等于档口一定赚钱，关键是同层动线、曝光、排队和竞品替代。",
    action: "工作日/周末午晚高峰蹲点，记录路过、停留、购买和排队流失。",
  },
  {
    icon: ReceiptText,
    level: "中",
    category: "加盟约束",
    description: "加盟店不能像自营店随便改菜单、改价格、换供应链或换品类。",
    action: "向总部确认调价、加品、促销、外卖、物料采购和退出条款。",
  },
  {
    icon: Landmark,
    level: "中",
    category: "资金缓冲",
    description: "转租费和押金只是接店成本，试营业亏损、物料、维修、证照、营销都需要现金缓冲。",
    action: "用统一账本设置 7/30 天止损线，不用主观感觉判断是否继续加钱。",
  },
];

const levelClass: Record<string, string> = {
  致命: "border-red-200 bg-red-50 text-red-800",
  高: "border-orange-200 bg-orange-50 text-orange-800",
  中: "border-amber-200 bg-amber-50 text-amber-800",
};

export function RiskRegister() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold">风险登记 · 新余恒太城接店</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
            风险页只保留当前项目已知事实和必须验证的变量，不把“已缓解”“已审核”这类未确认状态写成结论。
          </p>
        </div>
        <Badge variant="secondary">{risks.length} 个重点风险</Badge>
      </div>

      <div className="grid gap-3 lg:grid-cols-5">
        {risks.map((risk) => (
          <Card key={risk.category} className="p-4">
            <div className="flex items-start justify-between gap-3">
              <risk.icon className="size-5 shrink-0 text-[#d95b00]" />
              <span className={`rounded border px-2 py-0.5 text-xs font-medium ${levelClass[risk.level]}`}>{risk.level}</span>
            </div>
            <p className="mt-4 font-medium">{risk.category}</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{risk.description}</p>
            <p className="mt-3 text-sm leading-6 text-[#7a4b16]">{risk.action}</p>
          </Card>
        ))}
      </div>

      <Card className="border-red-200 bg-red-50/70 p-5">
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 size-5 text-red-700" />
          <div>
            <p className="font-semibold text-red-900">止损线不是悲观，是创业纪律</p>
            <p className="mt-2 text-sm leading-6 text-red-800">
              接店后先用 7 天试营业验证单人产能和真实毛利，再用 30 天判断营销、复购和品类是否成立。连续记录不足时，Agent 不输出盈利承诺。
            </p>
          </div>
        </div>
      </Card>

      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <AlertTriangle className="size-4" />
        合同和证照问题需要以正式文件与当地主管部门意见为准。
      </div>
    </div>
  );
}
