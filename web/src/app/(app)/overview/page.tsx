"use client";

import { useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { useProject } from "@/lib/hooks/useProject";
import { fmtMoney } from "@/domain/calculations";
import { CreateProjectModal } from "@/components/dashboard/CreateProjectModal";

const PROJECT_ID = "xinyu-hengtai-dakou";

export default function OverviewPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const { data: cockpit, isLoading } = useProject(PROJECT_ID);

  if (isLoading) {
    return <div className="flex items-center justify-center h-96 text-gray-300 text-sm font-mono">加载中...</div>;
  }

  const stage = cockpit?.current_stage;
  const stages = cockpit?.stages ?? [];
  const ops = cockpit?.operations;
  const dq = cockpit?.data_quality;
  const decision = cockpit?.decision;
  const nextActions = cockpit?.next_actions ?? [];
  const integrations = cockpit?.integrations ?? [];
  const alerts = ops?.alerts ?? [];
  const recentOps = cockpit?.recent_operations ?? [];

  const avgRevenue = ops?.days && ops.total_revenue ? ops.total_revenue / ops.days : 0;
  const avgOrders = ops?.days && ops.total_orders ? ops.total_orders / ops.days : 0;
  const foodCostRate = ops?.food_cost_rate ?? 0;
  const netProfit = ops?.net_profit ?? 0;
  const takeoutRatio = ops?.takeout_ratio ?? 0;
  const hasOps = (ops?.entry_count ?? 0) > 0;

  const trendData = recentOps.map((r: { date: string; revenue: number }) => ({
    date: r.date.slice(5),
    revenue: r.revenue,
  }));

  const missingCount = dq?.missing?.length ?? 0;
  const pendingIntegrations = integrations.filter((i: { status: string }) => i.status === "pending_auth").length;

  return (
    <div className="pb-24">
      {/* Bento Grid */}
      <div className="grid grid-cols-6 gap-3">

        {/* Row 1: Big metrics */}
        <div className="col-span-2 rounded-xl border border-cream-200 bg-white p-4">
          <p className="text-[10px] text-gray-400 font-mono">日均营收</p>
          <p className="text-2xl font-bold text-gray-800 mt-1" style={{ fontFamily: "Antonio, sans-serif" }}>
            {hasOps ? fmtMoney(avgRevenue) : "—"}
          </p>
          {hasOps && <p className="text-[10px] text-gray-400 font-mono mt-1">{Math.round(avgOrders)}单/日</p>}
        </div>

        <div className="col-span-2 rounded-xl border border-cream-200 bg-white p-4">
          <p className="text-[10px] text-gray-400 font-mono">净利润率</p>
          <p className={`text-2xl font-bold mt-1 ${netProfit < 0 ? "text-red-500" : "text-gray-800"}`} style={{ fontFamily: "Antonio, sans-serif" }}>
            {hasOps ? `${(netProfit / Math.max(ops!.total_revenue, 1) * 100).toFixed(1)}%` : "—"}
          </p>
          {hasOps && <p className="text-[10px] text-gray-400 font-mono mt-1">食品成本 {((foodCostRate) * 100).toFixed(1)}%</p>}
        </div>

        <div className="col-span-2 rounded-xl border border-cream-200 bg-white p-4">
          <p className="text-[10px] text-gray-400 font-mono">数据质量</p>
          <p className="text-2xl font-bold text-gray-800 mt-1" style={{ fontFamily: "Antonio, sans-serif" }}>
            {dq?.level === "weak" ? "弱" : dq?.level === "usable" ? "可用" : "—"}
          </p>
          <p className="text-[10px] text-gray-400 font-mono mt-1">{missingCount} 项待补齐</p>
        </div>

        {/* Row 2: Trend chart + Decision */}
        <div className="col-span-4 rounded-xl border border-cream-200 bg-white p-4">
          <p className="text-[10px] text-gray-400 font-mono mb-3">7 日营收趋势</p>
          {trendData.length > 1 ? (
            <ResponsiveContainer width="100%" height={120}>
              <LineChart data={trendData}>
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#9aa6a2" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: "#9aa6a2" }} axisLine={false} tickLine={false} tickFormatter={(v: string | number) => `${(Number(v) / 1000).toFixed(0)}k`} />
                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                <Tooltip formatter={(v: any) => [fmtMoney(Number(v)), "营收"]} />
                <Line type="monotone" dataKey="revenue" stroke="#1b3b32" strokeWidth={2} dot={{ fill: "#1b3b32", r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[120px] flex items-center justify-center text-xs text-gray-300 font-mono">暂无经营数据</div>
          )}
        </div>

        <div className="col-span-2 rounded-xl border border-cream-200 bg-white p-4 flex flex-col justify-between">
          <div>
            <p className="text-[10px] text-gray-400 font-mono">当前阶段</p>
            <p className="text-lg font-bold text-hunter-800 mt-1" style={{ fontFamily: "Antonio, sans-serif" }}>{String(stage ?? "—")}</p>
          </div>
          <div>
            <p className="text-[10px] text-gray-400 font-mono">决策状态</p>
            <p className="text-sm font-bold text-gray-600 mt-0.5">{String(decision?.decision ?? "—")}</p>
            {decision?.primary_contradiction && (
              <p className="text-[10px] text-gray-400 mt-0.5">{decision.primary_contradiction}</p>
            )}
          </div>
        </div>

        {/* Row 3: Lifecycle stages */}
        <div className="col-span-3 rounded-xl border border-cream-200 bg-white p-4">
          <p className="text-[10px] text-gray-400 font-mono mb-3">阶段进度</p>
          <div className="space-y-1.5">
            {stages.map((s: { label: string; status: string }, i: number) => (
              <div key={i} className="flex items-center gap-2">
                <span className={`size-2 rounded-full shrink-0 ${s.status === "done" ? "bg-emerald-500" : s.status === "current" ? "bg-amber-500" : "bg-gray-200"}`} />
                <span className={`text-xs ${s.status === "pending" ? "text-gray-300" : "text-gray-600"}`}>{s.label}</span>
                {s.status === "current" && <span className="text-[9px] font-mono text-amber-600 ml-auto">当前</span>}
              </div>
            ))}
          </div>
        </div>

        {/* Row 3: Next actions */}
        <div className="col-span-3 rounded-xl border border-cream-200 bg-white p-4">
          <p className="text-[10px] text-gray-400 font-mono mb-3">下一步操作</p>
          <div className="space-y-2">
            {nextActions.length > 0 ? nextActions.slice(0, 5).map((a: { title: string; priority: string; target: string }) => (
              <div key={a.title} className="flex items-start gap-2">
                <span className={`size-1.5 rounded-full shrink-0 mt-1.5 ${a.priority === "high" ? "bg-red-500" : a.priority === "medium" ? "bg-amber-500" : "bg-gray-300"}`} />
                <div className="min-w-0">
                  <p className="text-xs text-gray-600 font-medium">{a.title}</p>
                  <p className="text-[10px] text-gray-400 font-mono">{a.target}</p>
                </div>
              </div>
            )) : (
              <p className="text-xs text-gray-300 font-mono">暂无待办</p>
            )}
          </div>
        </div>

        {/* Row 4: Integrations + Missing data */}
        <div className="col-span-3 rounded-xl border border-cream-200 bg-white p-4">
          <p className="text-[10px] text-gray-400 font-mono mb-3">数据源接入</p>
          <div className="grid grid-cols-2 gap-2">
            {integrations.slice(0, 6).map((i: { id: string; name: string; status_label: string; status: string }) => (
              <div key={i.id} className="flex items-center gap-2">
                <span className={`size-1.5 rounded-full shrink-0 ${i.status === "active" ? "bg-emerald-500" : i.status === "pending_auth" ? "bg-amber-500" : "bg-gray-300"}`} />
                <span className="text-xs text-gray-600 truncate">{i.name}</span>
                <span className="text-[9px] font-mono text-gray-400 ml-auto truncate">{i.status_label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="col-span-3 rounded-xl border border-cream-200 bg-white p-4">
          <p className="text-[10px] text-gray-400 font-mono mb-3">待补齐数据</p>
          <div className="space-y-1.5">
            {dq?.missing?.slice(0, 5).map((m: string, i: number) => (
              <div key={i} className="flex items-center gap-2">
                <span className="text-[10px] text-gray-400">•</span>
                <span className="text-xs text-gray-500">{m}</span>
              </div>
            )) ?? <p className="text-xs text-gray-300 font-mono">暂无缺失</p>}
          </div>
        </div>

        {/* Row 5: Alerts + Summary */}
        {alerts.length > 0 && (
          <div className="col-span-6 rounded-xl border border-amber-300/30 bg-amber-50/30 p-4">
            <p className="text-[10px] text-gray-400 font-mono mb-2">经营预警</p>
            <div className="space-y-1">
              {alerts.map((a: { level: string; message: string }, i: number) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className={`size-1.5 rounded-full ${a.level === "critical" ? "bg-red-500" : a.level === "warning" ? "bg-amber-500" : "bg-emerald-500"}`} />
                  <span className="text-gray-600">{a.message}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Decision summary */}
        {decision?.summary && (
          <div className="col-span-6 rounded-xl border border-cream-200 bg-white p-4">
            <p className="text-[10px] text-gray-400 font-mono mb-2">系统判断</p>
            <p className="text-xs text-gray-600">{decision.summary}</p>
          </div>
        )}
      </div>

      {/* Create Project Button */}
      <div className="mt-6 flex justify-center">
        <button
          onClick={() => setModalOpen(true)}
          className="text-xs text-gray-400 hover:text-hunter-800 font-mono transition-colors"
        >
          {cockpit ? "创建新项目" : "创建项目开始使用"}
        </button>
      </div>

      <CreateProjectModal isOpen={modalOpen} onClose={() => setModalOpen(false)} projectId={PROJECT_ID} />
    </div>
  );
}
