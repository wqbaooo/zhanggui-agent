"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Calculator, FileWarning, HomeIcon, MapPin, MessageSquareWarning, ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";

const TABS = [
  { key: "/overview", label: "总览", icon: HomeIcon },
  { key: "/franchise", label: "加盟分析", icon: ShieldAlert },
  { key: "/investment", label: "投资测算", icon: Calculator },
  { key: "/location", label: "选址判断", icon: MapPin },
  { key: "/operations", label: "运营", icon: BarChart3 },
  { key: "/risks", label: "风险清单", icon: FileWarning },
  { key: "/feedback", label: "反馈", icon: MessageSquareWarning },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <>
      <nav className="hidden w-[148px] shrink-0 border-r border-cream-200 px-3 py-4 lg:flex lg:flex-col gap-0.5">
        {TABS.map((t) => {
          const active = pathname.startsWith(t.key) || (t.key === "/overview" && pathname === "/");
          return (
            <Link
              key={t.key}
              href={t.key}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-2 text-[11px] font-medium transition-colors",
                active
                  ? "bg-hunter-800/6 text-hunter-800"
                  : "text-gray-400 hover:text-hunter-800 hover:bg-cream-100"
              )}
            >
              <t.icon className="size-3.5" />
              {t.label}
            </Link>
          );
        })}
      </nav>

      <div className="fixed bottom-0 left-0 right-0 z-30 flex border-t border-cream-200 bg-cream-50/95 backdrop-blur-sm px-2 py-1.5 lg:hidden overflow-x-auto">
        {TABS.map((t) => {
          const active = pathname.startsWith(t.key);
          return (
            <Link
              key={t.key}
              href={t.key}
              className={cn(
                "flex flex-1 shrink-0 flex-col items-center gap-0.5 rounded-lg py-1.5 text-[9px]",
                active ? "text-hunter-800 font-semibold" : "text-gray-400"
              )}
            >
              <t.icon className="size-3.5" />
              <span className="font-mono text-[8px]">{t.label}</span>
            </Link>
          );
        })}
      </div>
    </>
  );
}
