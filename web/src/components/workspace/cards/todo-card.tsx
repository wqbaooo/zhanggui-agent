"use client";

import type { ProjectCockpit } from "@/lib/api";
import { BentoCard, MonoTag } from "../bento";

export function TodoCard({
  cockpit,
  onNavigate,
}: {
  cockpit: ProjectCockpit | null;
  onNavigate: (view: string) => void;
}) {
  const actions = cockpit?.next_actions || [];
  const count = actions.length;
  const top5 = actions.slice(0, 5);

  return (
    <BentoCard bg="cream" className="flex h-full flex-col">
      <div className="flex items-center justify-between">
        <MonoTag className="text-[#0F4C3A]">[ 待办 &middot; 今日 ]</MonoTag>
        <button className="mono-meta text-[#0F4C3A] hover:underline">
          全部 →
        </button>
      </div>

      <div className="mt-3 flex items-baseline gap-2">
        <span className="display-xl text-[48px] text-[#D9261C]">{count}</span>
        <span className="mono-meta text-[#0A0A0A]/30">件事</span>
      </div>

      <div className="mt-auto flex flex-wrap gap-1.5">
        {top5.map((a) => {
          const urgent = a.priority === "high";
          return (
            <button
              key={a.id}
              onClick={() => onNavigate(a.target)}
              className={
                "inline-flex items-center gap-1.5 rounded-full border-[1.5px] px-3 py-1 text-[11px] font-semibold transition-all " +
                (urgent
                  ? "bg-[#D9261C] text-[#F5EFE3] border-[#D9261C]"
                  : "bg-[#F5EFE3] text-[#0A0A0A] border-[#0A0A0A]/20 hover:border-[#0A0A0A]/40")
              }
            >
              <span className={"size-1.5 rounded-full " + (urgent ? "bg-[#F5EFE3]" : "bg-[#0A0A0A]/30")} />
              {a.title}
            </button>
          );
        })}
        {count === 0 && (
          <p className="mono-meta text-[#0A0A0A]/25">[ 暂无待办 ]</p>
        )}
      </div>
    </BentoCard>
  );
}
