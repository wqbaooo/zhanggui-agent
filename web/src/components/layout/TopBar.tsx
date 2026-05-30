"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

export function TopBar() {
  return (
    <header className="sticky top-0 z-30 border-b border-cream-200/60 bg-cream-50/90 backdrop-blur-md px-6 py-3">
      <div className="flex items-center justify-between">
        <Link href="/overview" className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-hunter-800 flex items-center justify-center">
            <span className="text-xs font-bold text-cream-50" style={{ fontFamily: "Antonio, sans-serif" }}>掌</span>
          </div>
          <span className="text-sm font-bold tracking-tight text-hunter-800" style={{ fontFamily: "Antonio, sans-serif" }}>掌柜</span>
        </Link>

        <div className="flex items-center gap-3">
          <Link href="/franchise" className="text-[11px] text-gray-400 hover:text-gray-600">加盟分析</Link>
          <Link href="/investment" className="text-[11px] text-gray-400 hover:text-gray-600">投资测算</Link>
          <Link href="/operations" className="text-[11px] text-gray-400 hover:text-gray-600">运营</Link>
          <span className="w-px h-4 bg-cream-200" />
          <Link href="/overview">
            <Button size="sm" className="text-[11px]">
              新项目
            </Button>
          </Link>
        </div>
      </div>
    </header>
  );
}
