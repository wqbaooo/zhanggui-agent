"use client";

import { BentoCard, MonoTag } from "../bento";

export function WeatherCard() {
  return (
    <BentoCard bg="green" className="flex h-full items-center justify-between">
      <div className="flex-1">
        <MonoTag>[ LOCATION &middot; WEATHER ]</MonoTag>
        <h3 className="display-md text-xl text-[#F5EFE3] mt-2">
          新余 &middot; XINYU
        </h3>
        <p className="text-[11px] text-[#F5EFE3]/50 mt-1">
          天气适宜 / 客流预期正常
        </p>
      </div>

      <div className="flex items-center gap-4">
        <div className="sun-icon" />
        <span className="display-xl text-[64px] text-[#F5EFE3]">
          28&deg;
        </span>
      </div>
    </BentoCard>
  );
}
