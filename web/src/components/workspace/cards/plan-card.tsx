"use client";

import type { ProjectCockpit } from "@/lib/api";
import { BentoCard, MonoTag, MonoMeta } from "../bento";

export function PlanCard({
  cockpit,
  onOpen,
}: {
  cockpit: ProjectCockpit | null;
  onOpen: (sheet: string) => void;
}) {
  const profile = cockpit?.profile || {};
  const name = (profile.店铺名称 as string) || (profile.brand as string) || "未命名 项目";

  return (
    <BentoCard bg="red" interactive onClick={() => onOpen("project")} className="flex h-full flex-col justify-between">
      <div>
        <div className="mb-3 flex size-10 items-center justify-center rounded-[10px] border-2 border-[#F5EFE3]/40 bg-[#F5EFE3]/10">
          <span className="display-lg text-lg text-[#F5EFE3]">⌂</span>
        </div>
        <MonoTag>[ 开业计划 ]</MonoTag>
      </div>
      <div className="mt-auto">
        <h3 className="display-md text-2xl text-[#F5EFE3] mt-2">
          {name}
        </h3>
        <MonoMeta className="mt-2 block text-[#F5EFE3]/40">
          CREATED · 24 MAY
        </MonoMeta>
      </div>
    </BentoCard>
  );
}
