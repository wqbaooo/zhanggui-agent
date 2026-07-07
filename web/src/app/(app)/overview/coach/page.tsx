"use client";

import { BookOpenCheck, ClipboardCheck, Store, TrendingUp, WalletCards, Wrench } from "lucide-react";

const takeoverStages = [
  { label: "第1天", title: "先盘清楚", body: "转让费、押金、库存、设备、合同、总部权限先验明白，别一接手就开始改菜单。", score: 72 },
  { label: "第2-3天", title: "建经营账", body: "把营业额、订单、食材、人工、房租摊销、平台扣费、满减、差评录成日报。", score: 44 },
  { label: "第4-7天", title: "找主要矛盾", body: "判断到底是流量不够、转化不行、毛利太低、出品不稳，还是总部限制太多。", score: 38 },
  { label: "第2周", title: "只改一个动作", body: "先改一个最可能赚钱的点：套餐、评价、排班、爆品、复购券，不要同时乱改。", score: 26 },
];

const coachModes = [
  { title: "问我怎么当老板", icon: Store, prompt: "我接手这家店后，今天最该盯哪三个数字？" },
  { title: "问我怎么管账", icon: WalletCards, prompt: "这家店一天营收多少才不亏？哪些成本最危险？" },
  { title: "问我怎么做外卖", icon: Wrench, prompt: "美团和淘宝闪购的满减、评价、套餐该怎么调？" },
  { title: "问我行业变化", icon: TrendingUp, prompt: "最近平台规则和同城玩法有什么会影响小店？" },
];

export default function BossCoachPage() {
  return (
    <div className="space-y-4">
      <div className="glass-card interactive-card rounded-xl p-5">
        <div className="relative z-10 flex items-start gap-3">
          <div className="rounded-lg border border-agent-gold/20 bg-agent-gold/10 p-2 text-agent-gold">
            <BookOpenCheck className="h-5 w-5" />
          </div>
          <div>
            <p className="font-label-caps text-on-surface-variant">情境教练 Agent</p>
            <h1 className="mt-1 text-2xl font-semibold text-on-background">接店教练</h1>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-on-surface-variant">
              这里不是开店课程，而是这家店的情境训练台：每天根据日报、差评、库存和 SOP 缺口，训练你先看账、再找主要矛盾，最后只改一个动作。
            </p>
          </div>
        </div>
      </div>

      <section className="glass-card interactive-card rounded-xl p-4">
        <div className="relative z-10">
          <div className="mb-4 flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4 text-primary" />
            <h2 className="text-lg font-semibold text-on-background">接手前两周作战图</h2>
          </div>
          <div className="grid gap-3 lg:grid-cols-4">
            {takeoverStages.map((stage, index) => (
              <div key={stage.title} className="group rounded-lg border border-muted-border/35 bg-surface-container-high/25 p-3 transition-all hover:-translate-y-0.5 hover:border-primary/30">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="rounded-full bg-primary-container px-2 py-0.5 text-[10px] font-mono text-primary">{stage.label}</span>
                  <span className="text-[10px] font-mono text-on-surface-variant">{stage.score}%</span>
                </div>
                <h3 className="text-sm font-semibold text-on-background">{stage.title}</h3>
                <p className="mt-2 min-h-16 text-xs leading-relaxed text-on-surface-variant">{stage.body}</p>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-container-high">
                  <div className="meter-fill h-full rounded-full bg-primary" style={{ width: `${stage.score}%`, animationDelay: `${index * 100}ms` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="grid gap-3 lg:grid-cols-4">
        {coachModes.map((mode) => {
          const Icon = mode.icon;
          return (
            <section key={mode.title} className="glass-card interactive-card rounded-xl p-4 transition-all hover:-translate-y-0.5">
              <div className="relative z-10">
                <Icon className="h-4 w-4 text-agent-gold" />
                <h2 className="mt-3 text-sm font-semibold text-on-background">{mode.title}</h2>
                <p className="mt-3 rounded-lg border border-agent-gold/20 bg-agent-gold/5 px-3 py-2 text-xs leading-relaxed text-agent-gold">
                  {mode.prompt}
                </p>
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
