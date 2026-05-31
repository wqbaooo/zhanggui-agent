"use client";

import { useState } from "react";
import { CircleDot, AlertCircle, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useProject } from "@/lib/hooks/useProject";
import { fmtMoney } from "@/domain/calculations";
import { LifecycleMap } from "@/components/dashboard/LifecycleMap";
import { SectionPanels } from "@/components/dashboard/SectionPanels";
import { CreateProjectModal } from "@/components/dashboard/CreateProjectModal";
import { AiConsultant } from "@/components/dashboard/AiConsultant";

const PROJECT_ID = "xinyu-hengtai-dakou";

function TrendBadge({ value, label }: { value: number | null; label: string }) {
  if (value === null) return null;
  const isPositive = value > 0;
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] font-mono ${isPositive ? "text-emerald-600" : "text-red-500"}`}>
      {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {label} {Math.abs(value).toFixed(1)}%
    </span>
  );
}

export default function OverviewPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const { data: cockpit, isLoading, error } = useProject(PROJECT_ID);

  const hasProject = !!cockpit && !error;
  const ops = cockpit?.operations;
  const profile = cockpit?.profile;
  const stage = cockpit?.current_stage;
  const dataQuality = cockpit?.data_quality;

  const avgRevenue = ops?.total_revenue && ops?.days ? ops.total_revenue / ops.days : 0;
  const avgOrders = ops?.total_orders && ops?.days ? ops.total_orders / ops.days : 0;
  const foodCostRate = ops?.food_cost_rate ?? 0;
  const netProfit = ops?.net_profit ?? 0;
  const netProfitRate = ops?.total_revenue && ops.total_revenue > 0 ? (netProfit / ops.total_revenue) * 100 : 0;

  const alerts = ops?.alerts ?? [];
  const hasAlerts = alerts.length > 0;

  return (
    <div className="space-y-6 pb-24">
      {/* Status bar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <Card className={hasProject ? "md:col-span-3" : "md:col-span-3"}>
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <span className={`size-2 rounded-full ${hasProject ? "bg-emerald-500" : "bg-amber-500"}`} />
              <CardTitle className="text-sm">
                {hasProject ? String(profile?.name ?? "项目档案") : "项目档案 · 未创建"}
              </CardTitle>
              {stage && <span className="text-[10px] text-gray-400 font-mono ml-2">{String(stage)}</span>}
              <span className="text-[10px] text-gray-300 font-mono ml-auto">6 工具 · LangGraph · V2</span>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="text-xs text-gray-400 py-4">加载中...</div>
            ) : hasProject ? (
              <div className="flex items-center justify-between">
                <div className="grid grid-cols-4 gap-6 text-xs flex-1">
                  <div>
                    <span className="text-gray-300">日均营收</span>
                    <p className="text-sm font-bold text-gray-700 mt-0.5" style={{ fontFamily: "Antonio, sans-serif" }}>
                      {avgRevenue > 0 ? fmtMoney(avgRevenue) : "—"}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-300">日均订单</span>
                    <p className="text-sm font-bold text-gray-700 mt-0.5" style={{ fontFamily: "Antonio, sans-serif" }}>
                      {avgOrders > 0 ? `${Math.round(avgOrders)}单` : "—"}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-300">食品成本率</span>
                    <p className="text-sm font-bold text-gray-700 mt-0.5" style={{ fontFamily: "Antonio, sans-serif" }}>
                      {foodCostRate > 0 ? `${(foodCostRate * 100).toFixed(1)}%` : "—"}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-300">净利润率</span>
                    <p className="text-sm font-bold text-gray-700 mt-0.5" style={{ fontFamily: "Antonio, sans-serif" }}>
                      {netProfitRate !== 0 ? `${netProfitRate.toFixed(1)}%` : "—"}
                    </p>
                  </div>
                </div>
                <Button size="sm" onClick={() => setModalOpen(true)} className="ml-4">新项目</Button>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div className="text-xs text-gray-400">
                  <AlertCircle className="w-3.5 h-3.5 inline mr-1" />
                  创建项目后，数据将自动填入
                </div>
                <Button size="sm" onClick={() => setModalOpen(true)}>创建项目</Button>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">系统状态</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            <div className="flex justify-between"><span className="text-gray-400">知识库</span><span className="text-emerald-600 font-mono">1302 chunks</span></div>
            <div className="flex justify-between"><span className="text-gray-400">向量索引</span><span className="text-emerald-600 font-mono">在线</span></div>
            <div className="flex justify-between"><span className="text-gray-400">高德地图</span><span className="text-emerald-600 font-mono">已接入</span></div>
            <div className="flex justify-between"><span className="text-gray-400">联网搜索</span><span className="text-emerald-600 font-mono">已接入</span></div>
            <div className="flex justify-between"><span className="text-gray-400">财务引擎</span><span className="text-emerald-600 font-mono">已接入</span></div>
            <div className="flex justify-between"><span className="text-gray-400">加盟分析</span><span className="text-emerald-600 font-mono">已接入</span></div>
          </CardContent>
        </Card>
      </div>

      {/* Alerts */}
      {hasAlerts && (
        <Card className="border-amber-300/30 bg-amber-50/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-amber-800">经营预警</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {alerts.map((a: { level: string; message: string }, i: number) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className={`size-1.5 rounded-full ${a.level === "critical" ? "bg-red-500" : a.level === "warning" ? "bg-amber-500" : "bg-emerald-500"}`} />
                <span className="text-gray-600">{a.message}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Baseline comparison */}
      {hasProject && cockpit?.baseline_comparison && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card>
            <CardContent className="py-3 text-center">
              <p className="text-[10px] text-gray-400 font-mono">预测日营收</p>
              <p className="text-lg font-bold text-gray-700" style={{ fontFamily: "Antonio, sans-serif" }}>
                {cockpit.baseline_comparison.projected_daily_revenue
                  ? fmtMoney(cockpit.baseline_comparison.projected_daily_revenue)
                  : "—"}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="py-3 text-center">
              <p className="text-[10px] text-gray-400 font-mono">实际日营收</p>
              <p className="text-lg font-bold text-gray-700" style={{ fontFamily: "Antonio, sans-serif" }}>
                {cockpit.baseline_comparison.actual_daily_revenue
                  ? fmtMoney(cockpit.baseline_comparison.actual_daily_revenue)
                  : "—"}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="py-3 text-center">
              <p className="text-[10px] text-gray-400 font-mono">营收偏差</p>
              <p className="text-lg font-bold text-gray-700" style={{ fontFamily: "Antonio, sans-serif" }}>
                {cockpit.baseline_comparison.revenue_gap !== null
                  ? fmtMoney(cockpit.baseline_comparison.revenue_gap)
                  : "—"}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="py-3 text-center">
              <p className="text-[10px] text-gray-400 font-mono">数据质量</p>
              <p className="text-lg font-bold text-gray-700" style={{ fontFamily: "Antonio, sans-serif" }}>
                {dataQuality?.level === "weak" ? "弱" : dataQuality?.level === "usable" ? "可用" : "—"}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      <LifecycleMap />

      <SectionPanels onCreateProject={() => setModalOpen(true)} />

      <AiConsultant />

      <CreateProjectModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        projectId={PROJECT_ID}
      />
    </div>
  );
}
