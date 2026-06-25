"use client";

import { AlertTriangle, CheckCircle, ClipboardList, CloudSun, FileWarning, Radar } from "lucide-react";
import type { DynamicResultCard, StoreMemoryEvent } from "@/data/mock-agents";

const toneClass: Record<DynamicResultCard["tone"], string> = {
  green: "border-primary/20 bg-primary-container/50 text-primary",
  amber: "border-tertiary/25 bg-tertiary-container/60 text-tertiary",
  blue: "border-secondary/20 bg-secondary-container/60 text-secondary",
  red: "border-error/20 bg-error-container/60 text-error",
};

const typeIcon = {
  judgement: Radar,
  evidence: ClipboardList,
  forecast: CloudSun,
  action: CheckCircle,
  risk: FileWarning,
  chart: AlertTriangle,
};

export function DynamicResultCards({ cards }: { cards: DynamicResultCard[] }) {
  return (
    <section className="grid gap-3 lg:grid-cols-5">
      {cards.map((card) => {
        const Icon = typeIcon[card.type];
        return (
          <article key={card.id} className="glass-card interactive-card rounded-xl p-4">
            <div className="relative z-10 flex h-full flex-col">
              <div className="flex items-start justify-between gap-2">
                <div className={`rounded-lg border p-2 ${toneClass[card.tone]}`}>
                  <Icon className="h-4 w-4" />
                </div>
                {card.metric && (
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-mono ${toneClass[card.tone]}`}>
                    {card.metric}
                  </span>
                )}
              </div>
              <p className="mt-3 font-label-caps text-on-surface-variant">{card.eyebrow}</p>
              <h3 className="mt-1 text-sm font-semibold leading-snug text-on-background">{card.title}</h3>
              <p className="mt-2 text-[11px] leading-relaxed text-on-surface-variant">{card.summary}</p>
              <div className="mt-3 space-y-1.5">
                {card.bullets.map((bullet) => (
                  <div key={bullet} className="flex gap-2 text-[10px] leading-relaxed text-on-surface-variant">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/70" />
                    <span>{bullet}</span>
                  </div>
                ))}
              </div>
            </div>
          </article>
        );
      })}
    </section>
  );
}

export function StoreMemoryTimeline({ events }: { events: StoreMemoryEvent[] }) {
  return (
    <section id="memory" className="glass-card interactive-card scroll-mt-20 rounded-xl p-4">
      <div className="relative z-10 grid gap-4 lg:grid-cols-[260px_1fr]">
        <div>
          <p className="font-label-caps text-on-surface-variant">门店档案 Memory</p>
          <h2 className="mt-1 text-lg font-semibold text-on-background">每次判断都写回门店档案</h2>
          <p className="mt-2 text-xs leading-relaxed text-on-surface-variant">
            你真正贴过的流水、平台日报、合同文件和关键判断会沉淀下来。普通闲聊不会被强行变成任务。
          </p>
        </div>
        <div className="grid gap-2 md:grid-cols-2">
          {events.map((event) => (
            <article key={event.id} className="rounded-lg border border-muted-border/30 bg-surface-container-lowest p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-[10px] font-mono text-on-surface-variant">
                  {event.time}
                </span>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-mono ${
                  event.status === "recorded"
                    ? "bg-primary-container text-primary"
                    : event.status === "risk"
                      ? "bg-error-container text-error"
                      : "bg-tertiary-container text-tertiary"
                }`}>
                  {event.type}
                </span>
              </div>
              <h3 className="mt-3 text-sm font-semibold text-on-background">{event.title}</h3>
              <p className="mt-1 text-[11px] leading-relaxed text-on-surface-variant">{event.detail}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
