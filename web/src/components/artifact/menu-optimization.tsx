"use client";

import { ChartNoAxesCombined, CookingPot, FileSpreadsheet, Utensils } from "lucide-react";
import { Card } from "@/components/ui/card";

export function MenuOptimization() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold">菜单优化 · 新余恒太城大口章鱼烧</h2>
        <p className="mt-1 text-sm text-muted-foreground">菜单矩阵必须基于真实销量和成本。未录入菜单数据前，不生成假“明星产品”。</p>
      </div>

      <Card className="p-6">
        <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
          <div>
            <Utensils className="size-10 text-[#d95b00]" />
            <h3 className="mt-4 text-xl font-semibold">菜单优化要从单品毛利和复购开始</h3>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              章鱼烧加盟店不能随意改品类时，菜单优化重点是套餐组合、加料、饮品搭配、外卖包装和出餐速度，而不是盲目上新品。
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              {[
                [CookingPot, "单品成本", "原料、包装、平台费"],
                [ChartNoAxesCombined, "销量趋势", "堂食/外卖/团购拆开"],
                [FileSpreadsheet, "菜单矩阵", "明星、走量、潜力、下架"],
              ].map(([Icon, title, text]) => (
                <div key={title as string} className="rounded-lg border border-[var(--app-border)] bg-[#fbfcfd] p-4">
                  <Icon className="size-5 text-[#d95b00]" />
                  <p className="mt-3 text-sm font-medium">{title as string}</p>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">{text as string}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-xl bg-[#fffaf3] p-5">
            <p className="text-sm font-semibold">Agent 会优先判断</p>
            <ul className="mt-4 space-y-3 text-sm text-[#536078]">
              <li>1. 总部是否允许调价、加料、加品类</li>
              <li>2. 外卖套餐是否吃掉毛利</li>
              <li>3. 高峰期出餐是否拖慢转化</li>
              <li>4. 哪些单品适合做引流，哪些必须保利润</li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
}
