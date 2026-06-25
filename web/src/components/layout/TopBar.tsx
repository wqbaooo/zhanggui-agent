"use client";

import Link from "next/link";
import { FileText, Sparkles } from "lucide-react";
import { storeIdentity } from "@/data/agent-store-os";

export function TopBar() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-white/45 bg-white/45 shadow-sm backdrop-blur-2xl lg:bg-white/30">
      <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-3 px-4 py-2 md:px-6">
        <Link href="/overview" className="flex min-w-0 items-baseline gap-2 lg:hidden">
          <span className="text-lg font-semibold text-on-background">掌柜 Agent</span>
          <span className="hidden truncate text-xs text-on-surface-variant sm:inline">{storeIdentity.name}</span>
        </Link>

        <div className="hidden min-w-0 items-center gap-2 lg:flex">
          <span className="inline-flex h-2 w-2 rounded-full bg-emerald-400 status-pulse" />
          <span className="text-xs text-on-surface-variant">工作台已连接</span>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <Link
            href="/overview"
            className="hidden items-center gap-1.5 rounded-full border border-white/55 bg-white/45 px-3 py-1.5 text-[10px] font-medium text-on-surface-variant transition-colors hover:border-primary/40 hover:text-on-background sm:flex"
          >
            <Sparkles className="h-3.5 w-3.5" />
            问掌柜
          </Link>
          <Link
            href="/capture"
            className="flex items-center gap-1.5 rounded-full bg-on-background px-3 py-1.5 text-[10px] font-semibold text-inverse-on-surface shadow-lg shadow-black/10 transition-transform hover:-translate-y-0.5"
          >
            <FileText className="h-3.5 w-3.5" />
            资料入库
          </Link>
        </div>
      </div>
    </header>
  );
}
