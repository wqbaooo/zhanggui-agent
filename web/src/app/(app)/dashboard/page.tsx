"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight, Boxes, DollarSign, Truck,
} from "lucide-react";
import { Area, AreaChart, Pie, PieChart, Cell, ResponsiveContainer } from "recharts";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { Skeleton, LoadingSpinner } from "@/components/shared/Loading";
import {
  DEFAULT_PROJECT_ID, getOperationSummary, getForecast, getStaff, getOperations,
  type ForecastItem,
} from "@/lib/api";

import CountUp from "react-countup";

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [kpi, setKpi] = useState({
    total_revenue: 0, net_profit: 0, entry_count: 0, total_orders: 0,
    food_cost_rate: 0, labor_cost_rate: 0, takeout_ratio: 0, profit_ready: false,
  });
  const [trend, setTrend] = useState<Array<{ date: string; 营收: number }>>([]);
  const [forecast, setForecast] = useState<ForecastItem[]>([]);
  const [staffCount, setStaffCount] = useState(0);
  const [offline, setOffline] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [ops, fRes, staffRes, opsList] = await Promise.all([
        getOperationSummary(DEFAULT_PROJECT_ID, 7),
        getForecast(DEFAULT_PROJECT_ID),
        getStaff(DEFAULT_PROJECT_ID),
        getOperations(DEFAULT_PROJECT_ID, 7),
      ]);
      setKpi({
        total_revenue: ops.total_revenue,
        net_profit: ops.net_profit,
        entry_count: ops.entry_count,
        total_orders: ops.total_orders,
        food_cost_rate: ops.food_cost_rate,
        labor_cost_rate: ops.labor_cost_rate,
        takeout_ratio: ops.takeout_ratio,
        profit_ready: ops.profit_ready,
      });
      setForecast(fRes.forecast.filter((f) => f.action === "urgent").slice(0, 4));
      setStaffCount(staffRes.staff?.length || 0);
      const entries = opsList.entries?.slice(-7) || [];
      setTrend(entries.map((e: { date: string; revenue: number }) => ({ date: e.date.slice(5), 营收: e.revenue })));
      setOffline(false);
    } catch {
      setKpi({
        total_revenue: 0, net_profit: 0, entry_count: 0, total_orders: 0,
        food_cost_rate: 0, labor_cost_rate: 0, takeout_ratio: 0, profit_ready: false,
      });
      setTrend([]);
      setForecast([]);
      setStaffCount(0);
      setOffline(true);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const hasData = kpi.entry_count > 0;
  const profitRate = kpi.total_revenue > 0 ? (kpi.net_profit / kpi.total_revenue) * 100 : 0;
  const channelData = [
    { name: "堂食", value: 1 - kpi.takeout_ratio, color: "#e7c86f" },
    { name: "外卖", value: kpi.takeout_ratio, color: "#c85f19" },
  ];

  const currentModule = getModule("/dashboard");

  return (
    <ModulePage module={currentModule}>
      <div className="space-y-4">

        {/* 离线提示 */}
        {offline && (
          <div className="rounded-2xl border border-amber-200 bg-amber-50/80 p-3 text-center">
            <p className="text-xs text-amber-700">后端未连接，经营数据暂不可用；系统不会用模拟数字代替。</p>
          </div>
        )}

        {/* KPI 行 */}
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <KpiCard
            label="近7天营收" value={kpi.total_revenue} prefix="¥"
            sub={`${kpi.entry_count}天 · ${Math.round(kpi.total_revenue / Math.max(kpi.entry_count, 1))}/日`}
            tone="good" loading={loading}
          />
          <KpiCard
            label="净利" value={kpi.profit_ready ? kpi.net_profit : 0} prefix={kpi.profit_ready ? "¥" : ""}
            valueText={kpi.profit_ready ? undefined : "待核算"}
            sub={kpi.profit_ready ? `利润率 ${profitRate.toFixed(1)}%` : "成本未补齐"}
            tone={kpi.profit_ready ? (kpi.net_profit > 0 ? "good" : "risk") : "info"} loading={loading}
          />
          <KpiCard
            label="库存预警" value={forecast.length} suffix="项"
            sub={forecast.length > 0 ? forecast[0]?.name?.slice(0, 6) || "需补货" : "库存正常"}
            tone={forecast.length > 0 ? "risk" : "good"} loading={loading}
          />
          <KpiCard
            label="在岗员工" value={staffCount} suffix="人"
            sub="本月工资待核算"
            tone="info" loading={loading}
          />
        </div>

        {/* 趋势 + 渠道 */}
        <div className="grid gap-4 lg:grid-cols-3">
          {/* 7日营收趋势 */}
          <div className="lg:col-span-2 rounded-2xl border border-white/45 bg-white/42 p-4 backdrop-blur-xl">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-on-surface-variant">7 日营收趋势</p>
              <Link href="/sales" className="flex items-center gap-1 text-[10px] text-primary-fixed hover:underline">
                详情 <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
            {loading ? (
              <div className="mt-3 h-48 flex items-center justify-center"><LoadingSpinner /></div>
            ) : trend.length > 0 ? (
              <div className="mt-3 h-48">
                <ResponsiveContainer>
                  <AreaChart data={trend}>
                    <defs>
                      <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#d5a92d" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="#d5a92d" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="营收" stroke="#c85f19" strokeWidth={2} fill="url(#revGrad)" dot={{ fill: "#c85f19", r: 3 }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="mt-3 flex h-48 items-center justify-center rounded-xl border border-dashed border-stone-200 text-xs text-stone-500">
                还没有真实营业记录，请先去资料录入
              </div>
            )}
          </div>

          {/* 渠道分布 */}
          <div className="rounded-2xl border border-white/45 bg-white/42 p-4 backdrop-blur-xl">
            <p className="text-xs font-medium text-on-surface-variant">渠道分布</p>
            {loading ? (
              <div className="mt-3 h-48 flex items-center justify-center"><LoadingSpinner /></div>
            ) : (
              <div className="mt-3 flex items-center justify-center">
                <div className="h-36 w-36">
                  <ResponsiveContainer>
                    <PieChart>
                      <Pie data={channelData} cx="50%" cy="50%" innerRadius={32} outerRadius={64} dataKey="value" paddingAngle={4}>
                        {channelData.map((d, i) => <Cell key={i} fill={d.color} />)}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
            <div className="mt-2 flex justify-center gap-6">
              {channelData.map((d) => (
                <div key={d.name} className="flex items-center gap-1.5 text-xs">
                  <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: d.color }} />
                  <span className="text-on-surface-variant">{d.name}</span>
                  <span className="font-semibold text-on-background">{(d.value * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 库存预警 + 今日动作 */}
        <div className="grid gap-4 lg:grid-cols-2">
          {/* 库存预警 */}
          <div className="rounded-2xl border border-white/45 bg-white/42 p-4 backdrop-blur-xl">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-on-surface-variant">库存预警</p>
              <Link href="/inventory" className="flex items-center gap-1 text-[10px] text-primary-fixed hover:underline">
                全部 <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
            {loading ? (
              <div className="mt-3 space-y-2">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}</div>
            ) : forecast.length > 0 ? (
              <div className="mt-3 space-y-2">
                {forecast.map((item) => (
                  <div key={item.sku_id} className="flex items-center justify-between rounded-xl border border-red-200 bg-red-50/60 px-3 py-2.5">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="h-2 w-2 rounded-full bg-red-400 status-pulse shrink-0" />
                      <span className="text-sm font-medium text-on-background truncate">{item.name}</span>
                    </div>
                    <span className="text-xs text-red-600 shrink-0 ml-2">
                      {item.days_remaining != null ? `剩${Math.round(item.days_remaining)}天` : "即将断货"}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50/60 p-4 text-center">
                <p className="text-sm font-medium text-emerald-700">库存正常</p>
                <p className="mt-1 text-xs text-emerald-600">暂无紧急补货需求</p>
              </div>
            )}
          </div>

          {/* 今日动作建议 */}
          <div className="rounded-2xl border border-white/45 bg-white/42 p-4 backdrop-blur-xl">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-on-surface-variant">今日建议动作</p>
              <Link href="/overview" className="flex items-center gap-1 text-[10px] text-primary-fixed hover:underline">
                工作台 <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
            <div className="mt-3 space-y-2">
              {[
                { icon: DollarSign, title: "确认昨日日报", body: hasData ? `昨日营收 ¥${kpi.total_revenue > 0 ? Math.round(kpi.total_revenue / kpi.entry_count) : "?"}，确认后入库` : "先录入昨日经营数据", tone: "watch" },
                { icon: Boxes, title: forecast.length > 0 ? `采购 ${forecast[0]?.name || "耗材"}` : "检查库存", body: forecast.length > 0 ? `${forecast[0]?.name || ""} 即将断货，建议下单` : "当前库存充足，可以跳过", tone: forecast.length > 0 ? "risk" : "good" },
                { icon: Truck, title: "检查外卖活动", body: kpi.takeout_ratio > 0.45 ? "外卖占比偏高，检查满减是否亏损" : "外卖占比正常，维持现状", tone: kpi.takeout_ratio > 0.45 ? "watch" : "good" },
              ].map((action, i) => (
                <Link
                  key={i}
                  href={i === 0 ? "/operations/daily" : i === 1 ? "/inventory" : "/channels"}
                  className={`flex items-start gap-3 rounded-xl border px-3 py-2.5 transition-colors hover:bg-white/55 ${
                    action.tone === "risk" ? "border-red-200 bg-red-50/40" :
                    action.tone === "watch" ? "border-amber-200 bg-amber-50/40" :
                    "border-white/45 bg-white/35"
                  }`}
                >
                  <action.icon className={`h-4 w-4 shrink-0 mt-0.5 ${
                    action.tone === "risk" ? "text-red-500" : action.tone === "watch" ? "text-amber-500" : "text-emerald-500"
                  }`} />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-on-background">{action.title}</p>
                    <p className="mt-0.5 text-xs text-on-surface-variant">{action.body}</p>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </ModulePage>
  );
}

function KpiCard({
  label, value, valueText, prefix = "", suffix = "", sub, tone, loading,
}: {
  label: string; value: number; valueText?: string; prefix?: string; suffix?: string; sub: string; tone: "good" | "risk" | "watch" | "info"; loading: boolean;
}) {
  const dotClass = tone === "good" ? "bg-emerald-400" : tone === "risk" ? "bg-red-400" : tone === "watch" ? "bg-amber-400" : "bg-sky-400";
  return (
    <div className="rounded-2xl border border-white/45 bg-white/42 p-4 backdrop-blur-xl transition-transform hover:-translate-y-0.5">
      <p className="text-[10px] font-medium text-on-surface-variant">{label}</p>
      {loading ? (
        <Skeleton className="mt-1 h-7 w-24" />
      ) : (
        <p className="mt-1 text-xl font-bold text-on-background tabular-nums">
          {valueText ?? <CountUp end={value} prefix={prefix} suffix={suffix} separator="," duration={0.8} />}
        </p>
      )}
      <div className="mt-1 flex items-center gap-1.5">
        <span className={`h-1.5 w-1.5 rounded-full ${dotClass}`} />
        <p className="text-[10px] text-on-surface-variant">{sub}</p>
      </div>
    </div>
  );
}
