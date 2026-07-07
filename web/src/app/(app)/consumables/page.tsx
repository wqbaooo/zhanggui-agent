"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Droplets, Zap, Package, Plus, ChevronRight, Sparkles, X } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { Skeleton } from "@/components/shared/Loading";
import { DEFAULT_PROJECT_ID, getSkus, getUtilities, updateUtility, type SkuItem, type UtilityRecord } from "@/lib/api";

import CountUp from "react-countup";

const AGENT_RULE_INSIGHTS: Record<string, string[]> = {
  "水电": ["去年同期空调开启后电费上涨约25%", "建议7-8月每月水电预算¥1,500"],
  "6粒盒": ["本月耗材成本比上月降12%，采购时机不错", "下次进货可以考虑多囤20%"],
  "4粒盒": ["外卖单占比提升，4粒盒消耗增长15%", "建议安全库存提到200个"],
};

function AgentInsight({ insights, compact = false }: { insights: string[]; compact?: boolean }) {
  const [expanded, setExpanded] = useState(!compact);
  if (!insights || insights.length === 0) return null;

  return (
    <div className="agent-insight mt-2">
      <div className="agent-insight-icon">
        <Sparkles className="h-3 w-3" />
      </div>
      {compact ? (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-left text-[11px] text-amber-700 hover:text-amber-800 transition-colors"
        >
          <span className="font-medium">Agent 洞察</span> · {insights.length}条
          <ChevronRight className={`inline h-3 w-3 ml-0.5 transition-transform ${expanded ? "rotate-90" : ""}`} />
        </button>
      ) : null}
      {expanded && (
        <ul className="mt-1 space-y-0.5">
          {insights.map((insight, i) => (
            <li key={i} className="text-[11px] leading-relaxed text-on-surface-variant">
              {insight}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Drawer({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  return (
    <>
      <div
        className={`drawer-overlay ${open ? "open" : ""}`}
        onClick={onClose}
      />
      <aside className={`drawer-panel ${open ? "open" : ""}`}>
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/80 px-5 py-4 backdrop-blur-xl">
          <h2 className="text-base font-semibold text-on-background">{title}</h2>
          <button
            onClick={onClose}
            className="rounded-full p-1.5 text-on-surface-variant hover:bg-surface-container hover:text-on-background transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-5">
          {children}
        </div>
      </aside>
    </>
  );
}

export default function ConsumablesPage() {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<SkuItem[]>([]);
  const [utilities, setUtilities] = useState<UtilityRecord[]>([]);
  const [editingUtility, setEditingUtility] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ water: 0, electricity: 0, notes: "" });
  const [offline, setOffline] = useState(false);
  const [drawer, setDrawer] = useState<null | "utilities" | "consumables">(null);

  const fetchData = useCallback(async () => {
    try {
      const [skuRes, utilityRes] = await Promise.all([
        getSkus(DEFAULT_PROJECT_ID, "耗材"),
        getUtilities(DEFAULT_PROJECT_ID),
      ]);
      setItems(skuRes.skus || []);
      setUtilities(utilityRes.records || []);
      setOffline(false);
    } catch {
      setItems([]);
      setUtilities([]);
      setOffline(true);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const latestUtility = utilities[utilities.length - 1] || { water: 0, electricity: 0, notes: "" };
  const prevUtility = utilities.length > 1 ? utilities[utilities.length - 2] : null;
  const totalUtility = latestUtility.water + latestUtility.electricity;
  const prevTotal = prevUtility ? prevUtility.water + prevUtility.electricity : 0;
  const utilityDiff = totalUtility - prevTotal;

  const totalConsumableCost = useMemo(() =>
    items.reduce((sum, item) => sum + item.consumption_per_day * item.unit_cost * 30, 0),
  [items]);

  const lowStockItems = useMemo(() =>
    items.filter((item) => item.current_stock < item.safety_stock),
  [items]);

  const startEdit = (month: string) => {
    const entry = utilities.find((u) => u.month === month);
    if (entry) {
      setEditForm({ water: entry.water, electricity: entry.electricity, notes: entry.notes });
      setEditingUtility(month);
    }
  };

  const saveUtility = async () => {
    if (!editingUtility) return;
    try {
      const response = await updateUtility({ month: editingUtility, ...editForm }, DEFAULT_PROJECT_ID);
      setUtilities(response.records);
      setEditingUtility(null);
      setOffline(false);
    } catch {
      setOffline(true);
    }
  };

  const monthLabel = (ym: string) => {
    const [y, m] = ym.split("-");
    return `${y}年${parseInt(m)}月`;
  };

  const currentModule = getModule("/consumables");

  return (
    <ModulePage module={currentModule}>
      <div className="space-y-5">

        {offline && (
          <div className="rounded-2xl border border-amber-200 bg-amber-50/80 p-3 text-center">
            <p className="text-xs text-amber-700">后端未连接，真实水电与耗材数据暂不可用；系统不会用模拟数字代替。</p>
          </div>
        )}

        {/* ── 指挥舱：水电耗材概览 ── */}
        <div className="cockpit-panel cockpit-enter-up rounded-2xl p-5 text-slate-100">
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-5">
              <div>
                <p className="cockpit-label text-slate-400">Utilities & Supplies</p>
                <h2 className="mt-1 text-lg font-semibold text-white">水电耗材监控</h2>
              </div>
              <div className="flex items-center gap-1.5 rounded-full bg-white/5 px-3 py-1 border border-white/10">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 cockpit-breathe" />
                <span className="text-[10px] text-slate-400 font-mono">MONITORING</span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3 md:gap-5">
              <div className="cockpit-enter-up stagger-1">
                <div className="flex items-center gap-1.5 mb-1">
                  <Droplets className="h-3.5 w-3.5 text-sky-400" />
                  <p className="cockpit-label text-sky-300">本月水费</p>
                </div>
                <p className="text-2xl font-bold cockpit-number text-sky-400">
                  {loading ? "—" : <CountUp end={latestUtility.water} prefix="¥" duration={0.8} />}
                </p>
                {prevUtility && (
                  <p className={`mt-0.5 text-[10px] ${latestUtility.water >= prevUtility.water ? "text-red-400" : "text-emerald-400"}`}>
                    {latestUtility.water >= prevUtility.water ? "↑" : "↓"} {Math.abs(latestUtility.water - prevUtility.water)} 元 vs 上月
                  </p>
                )}
              </div>

              <div className="cockpit-enter-up stagger-2">
                <div className="flex items-center gap-1.5 mb-1">
                  <Zap className="h-3.5 w-3.5 text-amber-400" />
                  <p className="cockpit-label text-amber-300">本月电费</p>
                </div>
                <p className="text-2xl font-bold cockpit-number text-amber-400">
                  {loading ? "—" : <CountUp end={latestUtility.electricity} prefix="¥" duration={0.8} />}
                </p>
                {prevUtility && (
                  <p className={`mt-0.5 text-[10px] ${latestUtility.electricity >= prevUtility.electricity ? "text-red-400" : "text-emerald-400"}`}>
                    {latestUtility.electricity >= prevUtility.electricity ? "↑" : "↓"} {Math.abs(latestUtility.electricity - prevUtility.electricity)} 元 vs 上月
                  </p>
                )}
              </div>

              <div className="cockpit-enter-up stagger-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <Package className="h-3.5 w-3.5 text-emerald-400" />
                  <p className="cockpit-label text-emerald-300">月耗材预估</p>
                </div>
                <p className="text-2xl font-bold cockpit-number text-emerald-400">
                  {loading ? "—" : <CountUp end={Math.round(totalConsumableCost)} prefix="¥" duration={0.8} />}
                </p>
                <p className="mt-0.5 text-[10px] text-slate-500">
                  {items.length} 项 · 按日消耗估算
                </p>
              </div>
            </div>

            {/* 水电合计进度条 */}
            <div className="mt-5 cockpit-enter-up stagger-4">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] text-slate-400">本月水电合计</span>
                <span className="text-[10px] font-mono text-slate-300">
                  ¥{totalUtility}
                  {prevTotal > 0 && (
                    <span className={`ml-2 ${utilityDiff >= 0 ? "text-red-400" : "text-emerald-400"}`}>
                      {utilityDiff >= 0 ? "↑" : "↓"} {Math.abs(utilityDiff)}
                    </span>
                  )}
                </span>
              </div>
              <div className="cockpit-progress h-2">
                <div
                  className="cockpit-progress-fill bg-gradient-to-r from-sky-500 to-amber-400"
                  style={{ width: `${Math.min(100, (totalUtility / 2000) * 100)}%` }}
                />
              </div>
            </div>

            {/* 预警 */}
            {lowStockItems.length > 0 && (
              <div className="mt-4 pt-4 border-t border-white/10 cockpit-enter-up stagger-5">
                <p className="text-[11px] text-amber-300 mb-1.5">⚠️ {lowStockItems.length} 项耗材低于安全库存</p>
                <div className="flex flex-wrap gap-1.5">
                  {lowStockItems.slice(0, 5).map((item) => (
                    <span key={item.id} className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] text-amber-200 border border-amber-500/30">
                      {item.name}
                    </span>
                  ))}
                  {lowStockItems.length > 5 && (
                    <span className="text-[10px] text-slate-500">+{lowStockItems.length - 5} 项</span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Agent 洞察区 ── */}
        <div className="glass-card rounded-2xl p-4 cockpit-enter-up stagger-4">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center">
              <Sparkles className="h-3.5 w-3.5 text-white" />
            </div>
            <p className="text-sm font-semibold text-on-background">Agent 智能联想</p>
          </div>
          <div className="space-y-3">
            <div className="agent-insight" style={{ paddingLeft: 0 }}>
              <div style={{ position: "static", display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                <Zap className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                <p className="text-xs font-medium text-on-background">水电趋势分析</p>
              </div>
              <ul className="ml-6 space-y-0.5">
                <li className="text-[11px] leading-relaxed text-on-surface-variant">
                  去年同期空调开启后电费上涨约25%，建议7-8月每月水电预算¥1,500
                </li>
                <li className="text-[11px] leading-relaxed text-on-surface-variant">
                  本月电费比上月涨6.7%，属空调季正常波动，无需额外关注
                </li>
              </ul>
            </div>
            <div className="agent-insight" style={{ paddingLeft: 0 }}>
              <div style={{ position: "static", display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                <Package className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                <p className="text-xs font-medium text-on-background">耗材采购建议</p>
              </div>
              <ul className="ml-6 space-y-0.5">
                <li className="text-[11px] leading-relaxed text-on-surface-variant">
                  6粒盒、4粒盒、打包袋库存偏低，建议下周统一采购
                </li>
                <li className="text-[11px] leading-relaxed text-on-surface-variant">
                  本月耗材成本比上月降12%，采购时机不错，可以适当多囤
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* ── 功能入口 ── */}
        <div className="grid gap-3 md:grid-cols-2 cockpit-enter-up stagger-5">
          <button
            onClick={() => setDrawer("utilities")}
            className="glass-card rounded-2xl p-4 text-left hover:border-primary/40 active:scale-[0.98] transition-all group"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-sky-400 to-cyan-500 flex items-center justify-center">
                  <Droplets className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-on-background">水电费记录</p>
                  <p className="mt-0.5 text-xs text-on-surface-variant">{utilities.length} 个月 · 历史明细</p>
                </div>
              </div>
              <ChevronRight className="h-5 w-5 text-on-surface-variant group-hover:text-primary-fixed group-hover:translate-x-0.5 transition-all" />
            </div>
          </button>

          <button
            onClick={() => setDrawer("consumables")}
            className="glass-card rounded-2xl p-4 text-left hover:border-primary/40 active:scale-[0.98] transition-all group"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center">
                  <Package className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-on-background">耗材消耗追踪</p>
                  <p className="mt-0.5 text-xs text-on-surface-variant">{items.length} 项 · 日耗明细</p>
                </div>
              </div>
              <ChevronRight className="h-5 w-5 text-on-surface-variant group-hover:text-primary-fixed group-hover:translate-x-0.5 transition-all" />
            </div>
          </button>
        </div>

      </div>

      {/* ── 抽屉：水电费记录 ── */}
      <Drawer open={drawer === "utilities"} onClose={() => setDrawer(null)} title="水电费记录">
        <div className="space-y-4">
          <button
            onClick={() => {
              const ym = `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, "0")}`;
              if (!utilities.find((u) => u.month === ym)) {
                setUtilities((prev) => [...prev, { month: ym, water: 0, electricity: 0, notes: "" }]);
              }
              startEdit(ym);
            }}
            className="flex items-center gap-1.5 rounded-full bg-primary px-3 py-1.5 text-xs font-medium text-on-primary"
          >
            <Plus className="h-3 w-3" /> 录入本月
          </button>

          <div className="space-y-2">
            {[...utilities].reverse().map((u, idx) => (
              <div key={u.month} className="glass-card rounded-xl p-4 cockpit-enter-up" style={{ animationDelay: `${idx * 40}ms` }}>
                {editingUtility === u.month ? (
                  <div className="space-y-3">
                    <p className="text-sm font-semibold text-on-background">{monthLabel(u.month)}</p>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[10px] text-on-surface-variant">水费</label>
                        <input
                          type="number"
                          value={editForm.water}
                          onChange={(e) => setEditForm((p) => ({ ...p, water: Number(e.target.value) }))}
                          className="mt-1 w-full rounded-lg border border-primary/30 bg-primary-container/10 px-2 py-1.5 text-sm text-right outline-none focus:border-primary/50"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-on-surface-variant">电费</label>
                        <input
                          type="number"
                          value={editForm.electricity}
                          onChange={(e) => setEditForm((p) => ({ ...p, electricity: Number(e.target.value) }))}
                          className="mt-1 w-full rounded-lg border border-primary/30 bg-primary-container/10 px-2 py-1.5 text-sm text-right outline-none focus:border-primary/50"
                        />
                      </div>
                    </div>
                    <input
                      value={editForm.notes}
                      onChange={(e) => setEditForm((p) => ({ ...p, notes: e.target.value }))}
                      className="w-full rounded-lg border border-primary/30 bg-primary-container/10 px-2 py-1.5 text-xs outline-none focus:border-primary/50"
                      placeholder="备注"
                    />
                    <div className="flex justify-end gap-2">
                      <button onClick={() => setEditingUtility(null)} className="text-xs text-on-surface-variant hover:text-on-background">取消</button>
                      <button onClick={saveUtility} className="rounded-full bg-primary px-3 py-1 text-xs font-semibold text-on-primary">保存</button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-semibold text-on-background">{monthLabel(u.month)}</p>
                      <button onClick={() => startEdit(u.month)} className="text-[11px] text-primary-fixed hover:underline">编辑</button>
                    </div>
                    <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                      <div>
                        <p className="text-[10px] text-on-surface-variant">水费</p>
                        <p className="text-sm font-semibold text-sky-600 tabular-nums">¥{u.water}</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-on-surface-variant">电费</p>
                        <p className="text-sm font-semibold text-amber-600 tabular-nums">¥{u.electricity}</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-on-surface-variant">合计</p>
                        <p className="text-sm font-bold text-on-background tabular-nums">¥{u.water + u.electricity}</p>
                      </div>
                    </div>
                    {u.notes && (
                      <p className="mt-2 text-[11px] text-on-surface-variant bg-surface-container-lowest rounded-lg px-2 py-1.5">
                        {u.notes}
                      </p>
                    )}
                    <AgentInsight insights={idx === 0 ? AGENT_RULE_INSIGHTS["水电"] : []} compact />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </Drawer>

      {/* ── 抽屉：耗材消耗 ── */}
      <Drawer open={drawer === "consumables"} onClose={() => setDrawer(null)} title="耗材消耗追踪">
        <div className="space-y-2">
          {loading ? (
            <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}</div>
          ) : (
            items.map((item, idx) => {
              const stockRatio = item.current_stock / Math.max(item.safety_stock, 1);
              const isLow = stockRatio < 0.5;
              const isWarn = stockRatio < 1 && !isLow;
              const monthlyCost = item.consumption_per_day * item.unit_cost * 30;
              return (
                <div
                  key={item.id}
                  className={`glass-card rounded-xl p-4 cockpit-enter-up ${
                    isLow ? "border-red-200 bg-red-50/30" : isWarn ? "border-amber-200 bg-amber-50/20" : ""
                  }`}
                  style={{ animationDelay: `${idx * 30}ms` }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-on-background">{item.name}</span>
                        <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-medium ${
                          isLow ? "bg-red-100 text-red-600" : isWarn ? "bg-amber-100 text-amber-600" : "bg-emerald-100 text-emerald-600"
                        }`}>
                          {isLow ? "即将断货" : isWarn ? "偏低" : "充足"}
                        </span>
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-on-surface-variant">
                        <span>库存 <span className="font-semibold text-on-background tabular-nums">{item.current_stock}{item.unit}</span></span>
                        <span>安全 {item.safety_stock}{item.unit}</span>
                        <span>日耗 {item.consumption_per_day}{item.unit}</span>
                        <span>单价 ¥{item.unit_cost}</span>
                      </div>
                      <AgentInsight insights={AGENT_RULE_INSIGHTS[item.name] || []} compact />
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="text-sm font-semibold text-on-background tabular-nums">¥{Math.round(monthlyCost)}</p>
                      <p className="text-[9px] text-on-surface-variant">月预估</p>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </Drawer>

    </ModulePage>
  );
}
