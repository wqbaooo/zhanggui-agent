"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown, Sparkles, Crown, Briefcase, Users, Package, TrendingUp, AlertTriangle, CheckCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { navGroups, storeIdentity } from "@/data/agent-store-os";
import { DEFAULT_PROJECT_ID, getBusinessFacts, type BusinessFact } from "@/lib/api";

const AGENT_BUSINESS_STATUS = [
  { key: "store_manager", label: "店长", icon: Briefcase, activeTask: false, pendingHref: "", greeting: "" },
  { key: "accountant", label: "会计", icon: Users, activeTask: false, pendingHref: "/finance/workspace#pending", greeting: "" },
  { key: "warehouse", label: "仓管", icon: Package, activeTask: false, pendingHref: "/inventory#pending", greeting: "" },
  { key: "operations", label: "运营", icon: TrendingUp, activeTask: false, pendingHref: "/channels#pending", greeting: "" },
];

function ownerForPendingFact(fact: BusinessFact) {
  if ((fact.affects_inventory_items || []).length > 0 || ["purchase", "stock_in", "inventory_count"].includes(fact.fact_type)) {
    return "warehouse";
  }
  if (["platform", "campaign", "review"].includes(fact.fact_type)) return "operations";
  return "accountant";
}

export function SidebarNav() {
  const pathname = usePathname();
  const [financeDate, setFinanceDate] = useState("");
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(
    () => new Set(),
  );
  const [pendingByAgent, setPendingByAgent] = useState<Record<string, number>>({});
  const agentBusinessStatus = AGENT_BUSINESS_STATUS.map((agent) => ({
    ...agent,
    pending: pendingByAgent[agent.key] || 0,
  }));

  useEffect(() => {
    let active = true;
    getBusinessFacts(DEFAULT_PROJECT_ID, "need_review")
      .then(({ facts }) => {
        if (!active) return;
        const next: Record<string, number> = {};
        facts.forEach((fact) => {
          const owner = ownerForPendingFact(fact);
          next[owner] = (next[owner] || 0) + 1;
        });
        setPendingByAgent(next);
      })
      .catch(() => {
        if (active) setPendingByAgent({});
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const date = new URLSearchParams(window.location.search).get("date") || "";
    setFinanceDate(date);
  }, [pathname]);

  const toggleGroup = (label: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  };

  const handlePendingClick = (e: React.MouseEvent, key: string) => {
    e.stopPropagation();
    const group = navGroups.find((g) => {
      const agent = agentBusinessStatus.find((a) => `💰 ${a.label}` === g.label || `🏪 ${a.label}` === g.label || `📦 ${a.label}` === g.label || `📈 ${a.label}` === g.label);
      return agent?.key === key;
    });
    if (group && collapsedGroups.has(group.label)) {
      setCollapsedGroups((prev) => {
        const next = new Set(prev);
        next.delete(group.label);
        return next;
      });
    }
  };

  const getAgentStatus = (label: string) => {
    return agentBusinessStatus.find((a) => `💰 ${a.label}` === label || `🏪 ${a.label}` === label || `📦 ${a.label}` === label || `📈 ${a.label}` === label);
  };

  const totalPending = agentBusinessStatus.reduce((sum, a) => sum + a.pending, 0);
  const chiefGroup = navGroups.find((g) => g.label === "👨‍💼 掌柜");
  const teamGroups = navGroups.filter((g) => g.label !== "👨‍💼 掌柜");

  return (
    <aside className="hidden h-screen w-60 shrink-0 border-r border-slate-200 bg-white lg:flex lg:flex-col">
      {/* 第一层：品牌区 */}
      <div className="border-b border-slate-100 px-4 py-3.5">
        <Link href="/overview" className="group flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-octo-50 text-octo-700 ring-1 ring-octo-100">
            <Sparkles className="h-4.5 w-4.5" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-bold text-slate-950">掌柜 Agent</p>
            <p className="truncate text-[10px] leading-tight text-slate-500">新余恒太城 · 单店经营系统</p>
          </div>
        </Link>
        <div className="mt-2 flex items-center gap-1.5">
          <span className="inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400 status-pulse" />
          <span className="truncate text-[10px] text-slate-500">{storeIdentity.name} · 经营中</span>
        </div>
      </div>

      {/* 第二层：掌柜专属区 */}
      <div className="border-b border-slate-100 px-2 py-3">
        <div className="flex items-center gap-1.5 px-2 py-1">
          <Crown className="h-3 w-3 text-octo-700" />
          <span className="text-[10px] font-semibold tracking-[0.12em] text-octo-800">掌柜 · 总调度</span>
        </div>
        <div className="space-y-0.5">
          {chiefGroup?.items.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`group relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "bg-octo-700 text-white"
                    : "text-slate-700 hover:bg-octo-50 hover:text-octo-800"
                }`}
              >
                <Icon className="h-3.5 w-3.5 shrink-0" />
                <span className="flex-1 truncate">{item.label}</span>
                {item.label === "今日待确认" && totalPending > 0 && (
                    <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
                      {totalPending}
                    </span>
                )}
                {active && (
                  <motion.div
                    layoutId="navActiveIndicator"
                    className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-white/70"
                  />
                )}
              </Link>
            );
          })}
        </div>
      </div>

      {/* 第三层：数字团队区 */}
      <div className="flex-1 space-y-1 overflow-y-auto px-2 py-3">
        <div className="flex items-center justify-between px-2 pb-1">
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-500">
            专业模块
          </span>
          {totalPending > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700">
              <AlertTriangle className="h-2.5 w-2.5" />
              {totalPending} 项待处理
            </span>
          )}
        </div>

        {teamGroups.map((group) => {
          const isCollapsed = collapsedGroups.has(group.label);
          const status = getAgentStatus(group.label);

          return (
            <div key={group.label} className="border-b border-slate-100 pb-1 last:border-0">
              <div className="flex items-center gap-1">
                <button
                  onClick={() => toggleGroup(group.label)}
                  className="flex flex-1 items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-50 hover:text-slate-950"
                >
                  <span className="flex-1 text-left">{group.label.replace(/^[^\s]+\s/, "")}</span>
                  <motion.div
                    animate={{ rotate: isCollapsed ? 0 : 180 }}
                    transition={{ duration: 0.2, ease: "easeInOut" }}
                  >
                    <ChevronDown className="h-3 w-3" />
                  </motion.div>
                </button>
                {status && status.pending > 0 && (
                  <Link
                    href={status.pendingHref}
                    onClick={(e) => handlePendingClick(e, status.key)}
                    className="mr-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-amber-500 text-[9px] font-bold text-white hover:bg-amber-600"
                  >
                    {status.pending}
                  </Link>
                )}
                {status && status.activeTask && (
                  <span className="mr-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-emerald-50 text-[9px] font-medium text-emerald-700">
                    <CheckCircle className="h-2.5 w-2.5" />
                  </span>
                )}
              </div>
              <AnimatePresence initial={false}>
                {!isCollapsed && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2, ease: "easeInOut" }}
                    className="overflow-hidden"
                  >
                    <div className="space-y-0.5 pb-1">
                      {group.items.map((item) => {
                        const Icon = item.icon;
                        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                        return (
                          <Link
                            key={item.href}
                            href={item.href.startsWith("/finance/") && financeDate ? `${item.href}?date=${financeDate}` : item.href}
                            className={`group relative flex items-center gap-2.5 rounded-lg px-3 py-1.5 text-[13px] transition-colors ${
                              active
                                ? "bg-octo-50 font-semibold text-octo-800"
                                : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                            }`}
                          >
                            {active && (
                              <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r-full bg-octo-600" />
                            )}
                            <Icon className={`h-3.5 w-3.5 shrink-0 ${active ? "text-octo-700" : "text-slate-400 group-hover:text-slate-600"}`} />
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
      </div>

      {/* 底部：提示 */}
      <div className="border-t border-slate-100 p-3">
        <div className="flex items-center gap-2 rounded-lg bg-octo-50 px-3 py-2 text-[10px] text-octo-800">
          <Sparkles className="h-3 w-3" />
          <span>多模态入口 · 人工确认后写入</span>
        </div>
      </div>
    </aside>
  );
}
