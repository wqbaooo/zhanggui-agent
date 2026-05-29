"use client";

import { Zap } from "lucide-react";
import type { ProjectCockpit } from "@/lib/api";
import { BentoCard, MonoTag, Divider, Pill } from "../bento";

function getHeroData(cockpit: ProjectCockpit | null) {
  if (!cockpit) {
    return {
      headline: "I'M ANALYZING FOR YOU.",
      headlineRed: ["ANALYZING", "YOU"],
      subtitle: "正在连接你的经营数据...",
      tasks: [] as Array<{ id: string; title: string; urgent: boolean; done: boolean; target: string }>,
    };
  }

  const alerts = cockpit.operations.alerts || [];
  const actions = cockpit.next_actions || [];
  const hasHigh = alerts.some((a) => a.level === "high");

  let headline = "TODAY IS STABLE.";
  let headlineRed: string[] = [];
  let subtitle = "基于你录入的数据，我整理了今日待办与提醒。";

  if (hasHigh) {
    headline = "THERE'S A PROBLEM.";
    headlineRed = ["PROBLEM"];
    subtitle = alerts[0].message;
  } else if (alerts.length > 0) {
    headline = "SOMETHING NEEDS CONFIRMATION.";
    headlineRed = ["CONFIRMATION"];
    subtitle = alerts[0].message;
  } else if (cockpit.decision.decision === "go") {
    headline = "PROJECT IS ON TRACK.";
    headlineRed = ["ON TRACK"];
  }

  const tasks = [
    ...actions.filter((a) => a.priority === "high").map((a) => ({
      id: a.id, title: a.title, urgent: true, done: false, target: a.target,
    })),
    ...actions.filter((a) => a.priority !== "high").slice(0, 3).map((a) => ({
      id: a.id, title: a.title, urgent: false, done: false, target: a.target,
    })),
  ];

  return { headline, headlineRed, subtitle, tasks };
}

function renderHeadline(text: string, redWords: string[]) {
  const words = text.split(" ");
  return words.map((word, i) => {
    const isRed = redWords.includes(word.replace(/[.,!?]/g, ""));
    const clean = word.replace(/[.,!?]/g, "");
    return (
      <span key={i}>
        {isRed ? (
          <span className="text-[#D9261C]">{clean}</span>
        ) : (
          word
        )}
        {i < words.length - 1 ? " " : ""}
      </span>
    );
  });
}

export function HeroCard({
  cockpit,
  onNavigate,
}: {
  cockpit: ProjectCockpit | null;
  onNavigate: (view: string) => void;
}) {
  const data = getHeroData(cockpit);

  return (
    <BentoCard bg="cream" className="flex h-full flex-col">
      <MonoTag className="text-[#0F4C3A]">
        [ AGENT &middot; STATUS: ANALYZING ]
      </MonoTag>

      <h1 className="display-xl mt-4 text-[40px] sm:text-[54px] leading-[0.95]">
        {renderHeadline(data.headline, data.headlineRed)}
      </h1>

      <p className="mt-4 text-[15px] font-medium text-[#0A0A0A]/60 leading-relaxed" style={{ fontFamily: "Noto Sans SC, sans-serif" }}>
        {data.subtitle}
      </p>

      <Divider className="mt-5" />

      <div className="mt-4 flex-1 space-y-2">
        {data.tasks.length > 0 ? (
          data.tasks.map((task) => (
            <button
              key={task.id}
              onClick={() => onNavigate(task.target)}
              className="group flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition-colors hover:bg-[#0A0A0A]/[0.03]"
            >
              <span className="flex size-6 shrink-0 items-center justify-center rounded-[6px] bg-[#D9261C] text-[#F5EFE3]">
                <Zap className="size-3" />
              </span>
              <span className="min-w-0 flex-1 truncate text-[14px] font-semibold text-[#0A0A0A]/80">
                {task.title}
              </span>
              {task.urgent && <Pill variant="mint">今天该做</Pill>}
              <span className="mono-meta text-[#0F4C3A] opacity-0 transition-opacity group-hover:opacity-100">
                去处理 →
              </span>
            </button>
          ))
        ) : (
          <div className="flex h-full items-center justify-center">
            <p className="mono-meta text-[#0A0A0A]/30">[ 暂无待办 ]</p>
          </div>
        )}
      </div>
    </BentoCard>
  );
}
