"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileText, Sparkles } from "lucide-react";
import { navGroups, storeIdentity } from "@/data/agent-store-os";

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <aside className="hidden h-screen w-64 shrink-0 border-r border-white/45 bg-white/42 p-4 shadow-sm backdrop-blur-2xl lg:flex lg:flex-col">
      <Link href="/overview" className="rounded-[24px] border border-white/45 bg-white/45 p-4 transition-colors hover:bg-white/65">
        <p className="text-lg font-semibold text-on-background">掌柜 Agent</p>
        <p className="mt-1 text-[11px] leading-relaxed text-on-surface-variant">{storeIdentity.name}</p>
      </Link>

      <nav className="mt-5 flex-1 space-y-5 overflow-y-auto pr-1">
        {navGroups.map((group) => (
          <section key={group.label}>
            <p className="px-2 text-[11px] font-medium text-on-surface-variant">{group.label}</p>
            <div className="mt-2 space-y-1">
              {group.items.map((item) => {
                const Icon = item.icon;
                const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-2 rounded-2xl px-3 py-2.5 text-sm transition-all ${
                      active
                        ? "bg-on-background text-inverse-on-surface shadow-lg shadow-black/10"
                        : "text-on-surface-variant hover:bg-white/55 hover:text-on-background"
                    }`}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="truncate">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </section>
        ))}
      </nav>

      <div className="mt-4 space-y-2">
        <Link
          href="/overview"
          className="flex items-center justify-center gap-2 rounded-2xl border border-white/55 bg-white/45 px-3 py-2.5 text-xs font-medium text-on-surface-variant hover:bg-white/70 hover:text-on-background"
        >
          <Sparkles className="h-4 w-4" />
          问掌柜
        </Link>
        <Link
          href="/capture"
          className="flex items-center justify-center gap-2 rounded-2xl bg-on-background px-3 py-2.5 text-xs font-semibold text-inverse-on-surface shadow-lg shadow-black/10"
        >
          <FileText className="h-4 w-4" />
          资料入库
        </Link>
      </div>
    </aside>
  );
}
