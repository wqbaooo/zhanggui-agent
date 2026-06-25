"use client";

import { Zap } from "lucide-react";
import { MOCK_COCKPIT } from "@/data/mock-cockpit";

export default function BossActionsPage() {
  const actions = MOCK_COCKPIT.next_actions;

  return (
    <div className="space-y-4">
      <div className="glass-card interactive-card rounded-xl p-5">
        <div className="relative z-10">
          <p className="font-label-caps text-on-surface-variant">老板室 Agent</p>
          <h1 className="mt-1 text-2xl font-semibold text-on-background">下一步动作</h1>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-on-surface-variant">
            这里只放今天真正要推进的动作。每条动作都要能落到负责人、目标和优先级，避免 AI 只给建议不推动执行。
          </p>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        {actions.map((action) => (
          <section key={action.id} className="glass-card interactive-card rounded-xl p-4">
            <div className="relative z-10">
              <div className="flex items-start gap-3">
                <div className="rounded-lg border border-agent-gold/20 bg-agent-gold/10 p-2 text-agent-gold">
                  <Zap className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-sm font-semibold text-on-background">{action.title}</h2>
                    <span className="rounded-full bg-surface-container-high/60 px-2 py-0.5 text-[9px] font-mono text-on-surface-variant">
                      {action.priority}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-on-surface-variant">目标：{action.target}</p>
                  <p className="mt-2 text-[11px] leading-relaxed text-on-surface-variant/70">
                    来源：{action.source} · 状态：{action.status}
                  </p>
                </div>
              </div>
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
