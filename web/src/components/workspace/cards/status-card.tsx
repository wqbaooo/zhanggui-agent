"use client";

import type { ProjectCockpit } from "@/lib/api";
import { BentoCard, MonoTag, IllustrationBox } from "../bento";

export function StatusCard({ cockpit }: { cockpit: ProjectCockpit | null }) {
  const hasOps = cockpit?.data_quality.has_real_operations;
  const ops = cockpit?.operations;

  return (
    <BentoCard bg="green" className="flex h-full flex-col justify-between">
      <div>
        <div className="flex items-center justify-between">
          <MonoTag>[ 经营状态 ]</MonoTag>
          <div className="flex items-center gap-1.5">
            <div className="pulse-dot" />
            <span className="mono-tag text-[#7FE05A]">LIVE</span>
          </div>
        </div>

        <div className="mt-4">
          {hasOps && ops ? (
            <>
              <h2 className="display-lg text-[42px] text-[#F5EFE3]">
                OPERATING
              </h2>
              <p className="display-lg text-[42px] text-[#F5EFE3]/60">
                DAY {cockpit?.data_quality.operation_days || 0}
              </p>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div>
                  <MonoTag className="text-[#F5EFE3]/40">营收</MonoTag>
                  <p className="mono-num text-lg text-[#F5EFE3] mt-1">
                    {"\u00a5"}{Math.round(ops.total_revenue).toLocaleString()}
                  </p>
                </div>
                <div>
                  <MonoTag className="text-[#F5EFE3]/40">净利润</MonoTag>
                  <p className={"mono-num text-lg mt-1 " + (ops.net_profit >= 0 ? "text-[#7FE05A]" : "text-[#D9261C]")}>
                    {"\u00a5"}{Math.round(ops.net_profit).toLocaleString()}
                  </p>
                </div>
              </div>
            </>
          ) : (
            <>
              <h2 className="display-lg text-[42px] text-[#F5EFE3]">
                WAITING
              </h2>
              <p className="display-lg text-[42px] text-[#F5EFE3]/60">
                FOR DATA
              </p>
              <p className="mt-3 text-[12px] text-[#F5EFE3]/50 leading-relaxed">
                录入经营数据后，我会自动生成趋势分析与异常提醒。
              </p>
            </>
          )}
        </div>
      </div>

      <IllustrationBox label="经营趋势图" className="mt-4 h-[80px]" />
    </BentoCard>
  );
}
