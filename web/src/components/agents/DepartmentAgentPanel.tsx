"use client";

import type { DepartmentAgent, DepartmentAgentStatus } from "@/data/mock-agents";

const statusCopy: Record<DepartmentAgentStatus, string> = {
  idle: "待命",
  running: "运行中",
  done: "已完成",
  blocked: "阻塞",
};

const statusClass: Record<DepartmentAgentStatus, string> = {
  idle: "border-muted-border/35 bg-surface-container-high/25 text-on-surface-variant",
  running: "border-secondary/20 bg-secondary-container/55 text-secondary",
  done: "border-primary/20 bg-primary-container/65 text-primary",
  blocked: "border-error/20 bg-error-container/55 text-error",
};

export function DepartmentAgentPanel({ agents }: { agents: DepartmentAgent[] }) {
  const activeAgents = agents.filter((agent) => agent.status !== "idle");
  const idleAgents = agents.filter((agent) => agent.status === "idle");

  return (
    <section className="glass-card interactive-card rounded-xl p-4">
      <div className="relative z-10">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="font-label-caps text-on-surface-variant">自动流转</p>
            <h2 className="mt-1 text-lg font-semibold text-on-background">运行队列</h2>
          </div>
          <span className="rounded-full border border-muted-border/35 bg-surface-container-high/35 px-3 py-1 text-xs text-on-surface-variant">
            {activeAgents.length} 个模块有动作
          </span>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-2">
            {activeAgents.map((agent) => {
            const Icon = agent.icon;
            return (
              <div
                key={agent.id}
                className="grid gap-3 rounded-lg border border-muted-border/30 bg-surface-container-lowest p-3 md:grid-cols-[180px_1fr_auto]"
              >
                <div className="flex items-center gap-3">
                  <div className="rounded-lg border border-primary/15 bg-primary-container/45 p-2 text-primary-fixed">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-on-background">{agent.name}</p>
                    <p className="mt-0.5 text-[11px] text-on-surface-variant">{agent.role}</p>
                  </div>
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="h-2 min-w-24 flex-1 overflow-hidden rounded-full bg-surface-container-high">
                    <div className="meter-fill h-full rounded-full bg-primary" style={{ width: `${agent.confidence}%` }} />
                    </div>
                    <span className="font-mono text-[10px] text-on-surface-variant">{agent.confidence}%</span>
                  </div>
                  <p className="mt-2 truncate text-xs text-on-background">{agent.nextAction}</p>
                </div>
                <span className={`h-fit rounded-full border px-2 py-1 text-[10px] font-mono ${statusClass[agent.status]}`}>
                  {statusCopy[agent.status]}
                </span>
              </div>
            );
          })}
          </div>

          <div className="rounded-lg border border-muted-border/30 bg-surface-container-lowest p-3">
            <p className="font-label-caps text-on-surface-variant">待数据</p>
            <div className="mt-3 space-y-2">
              {idleAgents.slice(0, 4).map((agent) => {
                const Icon = agent.icon;
                return (
                  <div key={agent.id} className="flex items-center justify-between gap-3 rounded-md bg-surface-container-high/35 px-2 py-2">
                    <div className="flex min-w-0 items-center gap-2">
                      <Icon className="h-3.5 w-3.5 shrink-0 text-on-surface-variant" />
                      <span className="truncate text-xs text-on-background">{agent.name}</span>
                    </div>
                    <span className="shrink-0 text-[10px] text-on-surface-variant">{agent.inputs[0]}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
