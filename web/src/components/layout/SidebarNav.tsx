"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown, Home, Settings, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { navGroups, storeIdentity } from "@/data/agent-store-os";

export function SidebarNav() {
  const pathname = usePathname();
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(
    () => new Set(navGroups.filter((group) => group.label !== "每日闭环").map((group) => group.label)),
  );

  const toggleGroup = (label: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  };

  return (
    <aside className="hidden h-screen w-64 shrink-0 border-r border-orange-100/60 bg-[#FAF7F2]/80 p-3 backdrop-blur-2xl lg:flex lg:flex-col">
      {/* 产品与当前门店 */}
      <Link
        href="/overview"
        className="group rounded-2xl border border-orange-100/80 bg-gradient-to-br from-white to-orange-50/40 p-3.5 transition-all hover:border-orange-200 hover:shadow-md hover:shadow-orange-100/50"
      >
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-orange-400 to-orange-600 text-white shadow-sm">
            <Home className="h-4.5 w-4.5" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-bold text-stone-800">掌柜 Agent</p>
            <p className="truncate text-[10px] leading-tight text-stone-500">AI 单店经营系统</p>
          </div>
        </div>
        <div className="mt-2 flex items-center gap-1.5">
          <span className="inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400 status-pulse" />
          <span className="truncate text-[10px] text-stone-400">{storeIdentity.name}</span>
        </div>
      </Link>

      {/* 导航分组 */}
      <nav className="mt-4 flex-1 space-y-1 overflow-y-auto pr-1">
        {navGroups.map((group) => {
          const isCollapsed = collapsedGroups.has(group.label);
          const isHomeGroup = group.label === "每日闭环";
          if (isHomeGroup) {
            return (
              <div key={group.label} className="mb-2">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`group relative flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium transition-all ${
                        active
                          ? "bg-gradient-to-r from-orange-500 to-orange-600 text-white shadow-md shadow-orange-200"
                          : "text-stone-600 hover:bg-orange-50 hover:text-orange-700"
                      }`}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      <span>{item.label}</span>
                      {active && (
                        <motion.div
                          layoutId="navActiveIndicator"
                          className="absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full bg-white/40"
                        />
                      )}
                    </Link>
                  );
                })}
              </div>
            );
          }

          return (
            <div key={group.label} className="mb-1">
              <button
                onClick={() => toggleGroup(group.label)}
                className="flex w-full items-center gap-1.5 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-stone-400 transition-colors hover:text-stone-600"
              >
                <span className="flex-1 text-left">{group.label}</span>
                <ChevronDown
                  className={`h-3 w-3 transition-transform ${isCollapsed ? "rotate-180" : ""}`}
                />
              </button>
              <AnimatePresence initial={false}>
                {!isCollapsed && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="space-y-0.5 pb-1">
                      {group.items.map((item) => {
                        const Icon = item.icon;
                        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                        return (
                          <Link
                            key={item.href}
                            href={item.href}
                            className={`group relative flex items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] transition-all ${
                              active
                                ? "bg-orange-50 font-medium text-orange-700"
                                : "text-stone-500 hover:bg-stone-100/60 hover:text-stone-700"
                            }`}
                          >
                            {active && (
                              <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-orange-500" />
                            )}
                            <Icon className={`h-3.5 w-3.5 shrink-0 ${active ? "text-orange-500" : "text-stone-400 group-hover:text-stone-500"}`} />
                            <span className="truncate">{item.label}</span>
                          </Link>
                        );
                      })}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </nav>

      {/* 底部：设置 + Agent 状态 */}
      <div className="mt-3 space-y-1.5 border-t border-orange-100/60 pt-3">
        <Link
          href="/settings"
          className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] text-stone-500 transition-colors hover:bg-stone-100/60 hover:text-stone-700"
        >
          <Settings className="h-3.5 w-3.5 text-stone-400" />
          <span>店铺设置</span>
        </Link>
        <div className="flex items-center gap-2 rounded-xl bg-orange-50/60 px-3 py-2 text-[10px] text-orange-600">
          <Sparkles className="h-3 w-3" />
          <span>多模态入口 · 人工确认后写入</span>
        </div>
      </div>
    </aside>
  );
}
