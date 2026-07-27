"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, Menu, Search, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { navGroups, storeIdentity } from "@/data/agent-store-os";

export function TopBar() {
  const pathname = usePathname();
  const [showMobileNav, setShowMobileNav] = useState(false);
  const [search, setSearch] = useState("");

  const routeTitles: Record<string, string> = {
    "/overview": "掌柜台",
    "/overview/actions": "今日推进",
    "/overview/coach": "接店教练",
    "/capture": "资料与待确认",
    "/capture/history": "录入历史",
    "/dashboard": "经营参谋",
    "/sales": "营业日报",
    "/profit": "财务",
    "/monthly": "月度账单",
    "/channels": "渠道外卖",
    "/products": "商品菜单",
    "/inventory": "库存台账",
    "/consumables": "水电耗材",
    "/calendar": "天气商圈",
    "/reports": "经营复盘",
    "/alerts": "预警中心",
    "/sop": "SOP 作业库",
    "/training": "员工训练",
    "/workflow": "店铺动线",
    "/documents": "店铺档案",
    "/settings": "店铺设置",
  };
  const pageTitle = routeTitles[pathname] ?? "掌柜台";

  return (
    <>
    <header className="sticky top-0 z-50 w-full border-b border-slate-200 bg-white/95 backdrop-blur-xl">
      <div className="flex h-14 w-full items-center justify-between gap-3 px-3 md:px-5">
        {/* 左侧：页面标题 */}
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={() => setShowMobileNav(true)}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-700 lg:hidden"
            aria-label="打开功能导航"
          >
            <Menu className="h-4 w-4" />
          </button>
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold text-slate-900">{pageTitle}</h1>
            <p className="hidden truncate text-[10px] text-slate-400 sm:block lg:hidden">{storeIdentity.name}</p>
          </div>
          <div className="hidden items-center gap-1.5 lg:flex">
            <span className="inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400 status-pulse" />
            <span className="text-[10px] text-slate-400">Agent 在线 · 数据工作区已连接</span>
          </div>
        </div>

        <div className="relative hidden w-[min(32vw,28rem)] shrink-0 lg:block">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="搜索功能、数据或资料"
            className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 text-xs text-slate-800 outline-none transition focus:border-cyan-400 focus:bg-white focus:ring-2 focus:ring-cyan-100"
          />
          {search.trim() && (
            <div className="absolute left-0 right-0 top-full z-50 mt-2 overflow-hidden rounded-lg border border-slate-200 bg-white p-1 shadow-xl">
              {navGroups.flatMap((group) => group.items).filter((item) => item.label.includes(search.trim())).slice(0, 6).map((item) => {
                const Icon = item.icon;
                return (
                  <Link key={item.href} href={item.href} onClick={() => setSearch("")} className="flex items-center gap-2 rounded-md px-3 py-2 text-xs text-slate-700 hover:bg-cyan-50 hover:text-cyan-800">
                    <Icon className="h-3.5 w-3.5" />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {/* 右侧：快速录入 + 日期 */}
        <div className="flex shrink-0 items-center gap-2">
          <span className="hidden text-[10px] text-slate-400 xl:block">
            {new Date().toLocaleDateString("zh-CN", { month: "long", day: "numeric", weekday: "short" })}
          </span>
          <Link href="/alerts" className="hidden h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition hover:bg-slate-50 hover:text-slate-800 sm:flex" aria-label="预警中心">
            <Bell className="h-4 w-4" />
          </Link>

          <Link
            href="/overview#store-agent-chat"
            className="flex h-9 items-center gap-1.5 rounded-lg bg-amber-400 px-3 text-[11px] font-semibold text-slate-950 transition-colors hover:bg-amber-300"
          >
            <Sparkles className="h-3 w-3" />
            问掌柜
          </Link>
        </div>
      </div>
    </header>

      <AnimatePresence>
        {showMobileNav && (
          <>
            <motion.button
              type="button"
              aria-label="关闭功能导航"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 top-0 z-40 bg-slate-950/35 lg:hidden"
              onClick={() => setShowMobileNav(false)}
            />
            <motion.aside
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="fixed inset-y-0 left-0 z-50 flex w-[min(88vw,340px)] flex-col bg-white shadow-2xl lg:hidden"
            >
              <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
                <div>
                  <p className="text-sm font-bold text-slate-950">掌柜 Agent</p>
                  <p className="mt-0.5 text-[10px] text-slate-500">{storeIdentity.name}</p>
                </div>
                <button type="button" onClick={() => setShowMobileNav(false)} className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600" aria-label="关闭导航">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <nav className="flex-1 overflow-y-auto p-3" aria-label="全部功能">
                {navGroups.map((group) => (
                  <section key={group.label} className="mb-4 last:mb-0">
                    <p className="px-2 pb-1.5 text-[11px] font-semibold text-slate-500">{group.label}</p>
                    <div className="grid gap-1">
                      {group.items.map((item) => {
                        const Icon = item.icon;
                        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                        return (
                          <Link key={item.href} href={item.href} onClick={() => setShowMobileNav(false)} className={`flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm ${active ? "bg-cyan-50 font-semibold text-cyan-800" : "text-slate-700 hover:bg-slate-50"}`}>
                            <Icon className="h-4 w-4 shrink-0" />
                            {item.label}
                          </Link>
                        );
                      })}
                    </div>
                  </section>
                ))}
              </nav>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
