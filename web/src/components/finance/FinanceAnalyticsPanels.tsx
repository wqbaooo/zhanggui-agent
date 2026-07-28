"use client";

import { useEffect, useMemo, useState } from "react";
import ReactEChartsCore from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { motion, useReducedMotion } from "framer-motion";
import { BarChart, LineChart, SankeyChart } from "echarts/charts";
import { AriaComponent, GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import {
  Activity, AlertTriangle, ArrowLeftRight, BarChart3, BrainCircuit, CircleDollarSign, MessageCircle,
  ReceiptText, ShieldCheck, TrendingUp, WalletCards,
} from "lucide-react";
import type { DailyFinanceSnapshotV1, FinanceAgentInsightsV1, FinanceAnalyticsV1, FinanceOverviewV1 } from "@/lib/api";

echarts.use([
  BarChart, LineChart, SankeyChart, AriaComponent,
  GridComponent, LegendComponent, TooltipComponent, CanvasRenderer,
]);

type AskHandler = (question: string) => void;

const CHANNEL_MARKS = [
  { match: "客如云", mark: "客", className: "bg-sky-100 text-sky-800" },
  { match: "美团", mark: "美", className: "bg-amber-100 text-amber-900" },
  { match: "淘宝", mark: "淘", className: "bg-orange-100 text-orange-800" },
  { match: "京东", mark: "京", className: "bg-red-100 text-red-800" },
  { match: "抖音", mark: "抖", className: "bg-stone-900 text-white" },
  { match: "现金", mark: "现", className: "bg-emerald-100 text-emerald-800" },
];

const STATUS_TONES: Record<string, string> = {
  completed: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  awaiting_arrival: "bg-sky-50 text-sky-800 ring-sky-200",
  awaiting_reconciliation: "bg-amber-50 text-amber-900 ring-amber-200",
  needs_information: "bg-stone-100 text-stone-700 ring-stone-200",
};

function yuan(value: number | null | undefined, fallback = "待核算") {
  return value == null
    ? fallback
    : `¥${(value / 100).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function yuanAxis(value: number) {
  if (Math.abs(value) >= 10_000) return `¥${(value / 10_000).toFixed(1)}万`;
  return `¥${Math.round(value).toLocaleString("zh-CN")}`;
}

function channelMark(channel: string) {
  return CHANNEL_MARKS.find((item) => channel.includes(item.match))
    ?? { mark: channel.slice(0, 1), className: "bg-stone-100 text-stone-700" };
}

function SectionHeader({ icon: Icon, title, detail }: {
  icon: React.ElementType;
  title: string;
  detail: string;
  question: string;
  onAsk: AskHandler;
}) {
  return <div className="flex items-start justify-between gap-4">
    <div className="min-w-0">
      <div className="flex items-center gap-2.5"><Icon className="h-[17px] w-[17px] shrink-0 text-octo-700" /><h2 className="text-[15px] font-semibold tracking-[-0.01em] text-stone-950">{title}</h2></div>
      <p className="mt-1.5 text-[13px] leading-5 text-stone-500">{detail}</p>
    </div>
  </div>;
}

function EmptyChart({ text }: { text: string }) {
  return <div className="grid min-h-56 place-items-center rounded-lg border border-dashed border-stone-300 bg-stone-50 px-5 text-center text-xs leading-5 text-stone-500">{text}</div>;
}

function MetricTile({ label, value, note, formula, tone = "stone" }: {
  label: string;
  value: string;
  note: string;
  formula?: string;
  tone?: "stone" | "emerald" | "amber" | "sky";
  onActivate?: () => void;
}) {
  const reduceMotion = useReducedMotion();
  const tones = {
    stone: "bg-stone-400",
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
    sky: "bg-sky-500",
  };
  const body = <>
    <div className="flex items-center gap-2"><span className={`h-1.5 w-1.5 rounded-full ${tones[tone]}`} /><span className="text-xs font-medium text-stone-600">{label}</span></div>
    <p className="mt-2.5 truncate text-xl font-semibold tracking-[-0.02em] tabular-nums text-stone-950">{value}</p>
    <p className="mt-1.5 text-xs leading-5 text-stone-500">{note}</p>
    {formula && <div className="pointer-events-none absolute inset-x-3 top-[calc(100%-2px)] z-30 translate-y-1 rounded-lg border border-stone-200 bg-stone-900 px-3 py-2 text-left text-xs leading-5 text-white opacity-0 shadow-xl transition duration-150 group-hover:translate-y-0 group-hover:opacity-100">口径：{formula}</div>}
  </>;
  const shared = "group relative min-w-0 border-r border-stone-200 px-5 py-4 text-left last:border-r-0";
  return <motion.div initial={reduceMotion ? false : { opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .25, ease: [0.22, 1, 0.36, 1] }} className={shared}>{body}</motion.div>;
}

export function FinanceIntelligenceDashboard({ analytics, snapshot, overview, agentInsights, voucherCount, onAsk }: {
  analytics: FinanceAnalyticsV1;
  snapshot: DailyFinanceSnapshotV1;
  overview: FinanceOverviewV1;
  agentInsights: FinanceAgentInsightsV1 | null;
  voucherCount: number;
  onAsk: AskHandler;
}) {
  const reduceMotion = useReducedMotion();
  const dates = analytics.daily_series.map((item) => item.business_date.slice(5));
  const recordedDays = analytics.daily_series.filter((item) => item.state !== "missing").length;
  const coverage = Math.round(recordedDays / Math.max(analytics.daily_series.length, 1) * 100);
  const profitConfirmed = analytics.kpis.net_profit_minor != null;
  const profitMinor = analytics.kpis.net_profit_minor ?? analytics.kpis.provisional_net_profit_minor;
  const pendingRows = analytics.settlement_timeline.filter((item) => item.status !== "completed");
  const pendingMinor = analytics.kpis.pending_collection_minor;
  const scope = analytics.period_start === analytics.period_end ? analytics.period_end : `${analytics.period_start} 至 ${analytics.period_end}`;
  const missingLabels: Record<string, string> = { daily_close: "完整日结", food_cost: "食材实际耗用", labor: "人工成本", other_cost: "其他经营费用", packaging_cost: "包装耗用", rent: "房租", utility: "水电燃气" };
  const missing = analytics.missing_inputs.map((item) => missingLabels[item] || item);
  const trendOption = {
    aria: { enabled: true, description: "按天展示营业收入与店铺资金流出，缺失日保持空白。" },
    animationDuration: 680, animationEasing: "cubicOut" as const,
    tooltip: { trigger: "axis" as const, backgroundColor: "rgba(255,255,255,.97)", borderColor: "#e7e5e4", textStyle: { color: "#292524", fontSize: 12 }, valueFormatter: (value: number | null) => value == null ? "未录入" : `¥${value.toLocaleString("zh-CN")}` },
    legend: { top: 0, right: 0, itemWidth: 12, itemHeight: 8, textStyle: { color: "#78716c", fontSize: 10 } },
    grid: { left: 10, right: 12, top: 42, bottom: 20, containLabel: true },
    xAxis: { type: "category" as const, data: dates, boundaryGap: false, axisLine: { lineStyle: { color: "#d6d3d1" } }, axisLabel: { color: "#78716c", fontSize: 10, interval: dates.length > 18 ? 2 : 0 } },
    yAxis: { type: "value" as const, axisLabel: { color: "#78716c", fontSize: 10, formatter: yuanAxis }, splitLine: { lineStyle: { color: "#f0eeec" } } },
    series: [
      { name: "营业收入", type: "line" as const, smooth: .25, connectNulls: false, symbol: "circle", symbolSize: 6, data: analytics.daily_series.map((item) => item.merchant_net_minor == null ? null : item.merchant_net_minor / 100), lineStyle: { color: "#13795b", width: 2.5 }, itemStyle: { color: "#13795b" }, areaStyle: { color: "rgba(19,121,91,.09)" } },
      { name: "店铺资金流出", type: "line" as const, smooth: .2, connectNulls: false, symbolSize: 5, data: analytics.daily_series.map((item) => item.store_outflow_minor == null ? null : item.store_outflow_minor / 100), lineStyle: { color: "#c26a2e", width: 2 }, itemStyle: { color: "#c26a2e" } },
    ],
  };
  const channelOption = {
    aria: { enabled: true, description: "各营业渠道期间收入对比。" },
    animationDuration: 640, animationEasing: "cubicOut" as const,
    tooltip: { trigger: "axis" as const, axisPointer: { type: "shadow" as const }, valueFormatter: (value: number) => `¥${value.toLocaleString("zh-CN")}` },
    grid: { left: 8, right: 18, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: "value" as const, axisLabel: { color: "#78716c", fontSize: 10, formatter: yuanAxis }, splitLine: { lineStyle: { color: "#f0eeec" } } },
    yAxis: { type: "category" as const, inverse: true, data: analytics.channel_breakdown.map((item) => item.channel), axisLabel: { color: "#57534e", fontSize: 11, width: 90, overflow: "truncate" as const } },
    series: [{ type: "bar" as const, data: analytics.channel_breakdown.map((item, index) => ({ value: item.amount_minor / 100, itemStyle: { color: ["#9a3412", "#c26735", "#d99a22", "#23785a", "#3b82a0", "#7c6f64"][index % 6], borderRadius: [0, 5, 5, 0] } })), barMaxWidth: 18 }],
  };
  const settlementByStatus = [
    { key: "completed", label: "已到账", color: "#23785a" },
    { key: "awaiting_arrival", label: "平台结算中", color: "#3b82a0" },
    { key: "awaiting_reconciliation", label: "待对账", color: "#d99a22" },
    { key: "needs_information", label: "缺资料", color: "#a8a29e" },
  ];
  const settlementChannels = Array.from(new Set(analytics.settlement_timeline.map((item) => item.channel)));
  const settlementOption = {
    aria: { enabled: true, description: "各平台已到账、结算中、待对账和缺资料金额。" },
    animationDuration: 680, animationEasing: "cubicOut" as const,
    tooltip: { trigger: "axis" as const, axisPointer: { type: "shadow" as const }, valueFormatter: (value: number) => `¥${value.toLocaleString("zh-CN")}` },
    legend: { top: 0, left: 0, itemWidth: 12, itemHeight: 8, textStyle: { color: "#78716c", fontSize: 10 } },
    grid: { left: 8, right: 12, top: 40, bottom: 8, containLabel: true },
    xAxis: { type: "value" as const, axisLabel: { color: "#78716c", fontSize: 10, formatter: yuanAxis }, splitLine: { lineStyle: { color: "#f0eeec" } } },
    yAxis: { type: "category" as const, data: settlementChannels, axisLabel: { color: "#57534e", fontSize: 10, width: 90, overflow: "truncate" as const } },
    series: settlementByStatus.map((status) => ({ name: status.label, type: "bar" as const, stack: "settlement", barMaxWidth: 18, itemStyle: { color: status.color }, data: settlementChannels.map((channel) => analytics.settlement_timeline.filter((item) => item.channel === channel && item.status === status.key).reduce((sum, item) => sum + item.amount_minor, 0) / 100) })),
  };
  const signals = [
    { tone: profitConfirmed ? "good" : "warn", title: profitConfirmed ? "净利润可确认" : "净利润尚不可确认", body: profitConfirmed ? `期间净利润 ${yuan(profitMinor)}，可按已闭环成本口径使用。` : `目前 ${yuan(profitMinor)} 只是已录收支差额，尚缺${missing.slice(0, 3).join("、") || "成本资料"}。` },
    { tone: pendingMinor > 0 ? "warn" : "good", title: pendingMinor > 0 ? `${pendingRows.length}笔资金尚未闭环` : "平台到账无关键待办", body: pendingMinor > 0 ? `${yuan(pendingMinor)} 仍在平台钱包、绑定卡或对账链路。` : "当前已登记平台款未发现新的未闭环项。" },
    { tone: analytics.missing_days.length ? "warn" : "good", title: analytics.missing_days.length ? `${analytics.missing_days.length}天营业资料空缺` : "期间资料日期连续", body: analytics.missing_days.length ? `空缺日：${analytics.missing_days.slice(0, 4).join("、")}${analytics.missing_days.length > 4 ? "…" : ""}，系统没有按0元计算。` : "所选范围每个自然日都有财务事实或关账记录。" },
  ];
  return <div className="space-y-4">
    {agentInsights && <section className="finance-surface overflow-hidden">
      <div className="flex items-start justify-between gap-5 border-b border-stone-200 px-6 py-5">
        <div><div className="flex items-center gap-2 text-octo-800"><BrainCircuit className="h-5 w-5" /><span className="text-xs font-semibold">财务 Agent · {agentInsights.as_of}</span></div><h2 className="mt-2 text-lg font-semibold tracking-[-.02em] text-stone-950">{agentInsights.daily_brief.headline}</h2><p className="mt-1 text-xs leading-5 text-stone-500">{agentInsights.daily_brief.summary}</p></div>
        {agentInsights.learned_focus.length > 0 && <div className="max-w-sm text-right"><p className="text-[10px] font-semibold uppercase tracking-wider text-stone-400">近期关注</p><div className="mt-2 flex flex-wrap justify-end gap-1.5">{agentInsights.learned_focus.slice(0, 3).map((item) => <span key={item.topic} title={`最近提及 ${item.count} 次`} className="rounded-full bg-stone-100 px-2.5 py-1 text-[10px] text-stone-600">{item.label}</span>)}</div></div>}
      </div>
      {agentInsights.daily_brief.items.length > 0 ? <div className="grid grid-cols-3 divide-x divide-stone-200">{agentInsights.daily_brief.items.map((item, index) => {
        const tones = item.severity === "critical" ? "bg-rose-500" : item.severity === "warning" ? "bg-amber-500" : "bg-sky-500";
        return <motion.button key={item.id} type="button" onClick={() => onAsk(item.action_query)} initial={reduceMotion ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .28, delay: index * .05, ease: [0.22, 1, 0.36, 1] }} className="group min-w-0 px-5 py-5 text-left transition hover:bg-stone-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-octo-500"><div className="flex items-center gap-2"><span className={`h-2 w-2 rounded-full ${tones}`} /><span className="text-[10px] font-semibold text-stone-500">{item.topic_label}</span>{item.preference_boosted && <span className="rounded-full bg-octo-50 px-2 py-0.5 text-[9px] text-octo-700">你近期常问</span>}</div><h3 className="mt-3 text-sm font-semibold text-stone-950">{item.title}</h3><p className="mt-1.5 line-clamp-2 text-xs leading-5 text-stone-600">{item.summary}</p><p className="mt-3 border-t border-stone-100 pt-3 text-[10px] leading-4 text-stone-500">{item.why_now}</p><span className="mt-3 inline-flex items-center gap-1 text-[11px] font-semibold text-octo-700">让财务 Agent 核对 <span className="transition-transform group-hover:translate-x-0.5">→</span></span></motion.button>;
      })}</div> : <div className="px-6 py-8 text-center text-sm text-stone-500">所选截止日没有识别到新的高优先级财务待办。</div>}
    </section>}
    <section className="finance-surface overflow-hidden">
      <div className="grid grid-cols-[minmax(0,1.2fr)_repeat(4,minmax(150px,.55fr))]">
        <div className="relative overflow-hidden border-r border-stone-200 px-6 py-5">
          <div className="absolute -right-10 -top-12 h-36 w-36 rounded-full bg-octo-100/60 blur-3xl" />
          <div className="relative"><div className="flex items-center gap-2 text-octo-800"><BrainCircuit className="h-5 w-5" /><span className="text-xs font-semibold">实时财务判断</span></div><p className="mt-3 text-xl font-semibold tracking-[-.025em] text-stone-950">{profitConfirmed ? `期间净利润 ${yuan(profitMinor)}` : "收支已可见，净利润仍需补齐成本"}</p><p className="mt-2 max-w-xl text-xs leading-5 text-stone-600">{profitConfirmed ? "成本资料已闭环，可继续检查渠道和资金效率。" : `已识别 ${missing.length} 类关键缺口，下方分析只使用已知事实。`}</p><button type="button" onClick={() => onAsk(`请以 ${scope} 为口径，综合解读营业收入、渠道结构、资金到账、成本、利润和凭证完整性，按影响大小给出三个行动。`)} className="mt-4 inline-flex min-h-9 items-center gap-2 rounded-lg bg-octo-700 px-3.5 text-xs font-semibold text-white shadow-sm transition hover:bg-octo-800"><MessageCircle className="h-3.5 w-3.5" />让 Agent 综合解读</button></div>
        </div>
        {[{ label: "营业收入", value: yuan(analytics.kpis.merchant_net_minor), note: "销售发生" }, { label: "已知经营成本", value: yuan(analytics.kpis.known_operating_cost_minor), note: profitConfirmed ? "已闭环" : "尚未完整" }, { label: "待进店铺账户", value: yuan(analytics.kpis.pending_collection_minor), note: `${pendingRows.length}笔待跟进` }, { label: "日期覆盖率", value: `${coverage}%`, note: `${recordedDays}/${analytics.daily_series.length}天有记录` }].map((item) => <div key={item.label} className="flex min-w-0 flex-col justify-center border-r border-stone-100 px-4 py-5 last:border-r-0"><span className="text-[11px] font-medium text-stone-500">{item.label}</span><strong className="mt-2 truncate text-lg font-semibold tabular-nums tracking-[-.02em] text-stone-950">{item.value}</strong><span className="mt-1 text-[10px] text-stone-400">{item.note}</span></div>)}
      </div>
    </section>
    <section className="grid grid-cols-3 gap-3">
      {signals.map((item, index) => <motion.button key={item.title} type="button" initial={reduceMotion ? false : { opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * .06 }} onClick={() => onAsk(`基于 ${scope} 解释：${item.title}。${item.body}`)} className="finance-surface group flex min-w-0 items-start gap-3 p-4 text-left transition hover:border-octo-200 hover:bg-octo-50/25"><span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${item.tone === "good" ? "bg-emerald-500" : "bg-amber-500"}`} /><span className="min-w-0"><strong className="text-[13px] font-semibold text-stone-900">{item.title}</strong><span className="mt-1 block text-xs leading-5 text-stone-500">{item.body}</span></span><MessageCircle className="ml-auto h-4 w-4 shrink-0 text-stone-300 transition group-hover:text-octo-700" /></motion.button>)}
    </section>
    <section className="grid grid-cols-[minmax(0,1.35fr)_minmax(360px,.65fr)] gap-4">
      <div className="finance-surface min-w-0 p-5"><SectionHeader icon={TrendingUp} title="营业收入与资金流出" detail="按事实日期展示；空缺保持空白，不用0元补齐趋势。" question="" onAsk={onAsk} /><div className="mt-3 h-72" role="img" aria-label="营业收入与资金流出趋势"><ReactEChartsCore echarts={echarts} option={trendOption} style={{ height: "100%" }} notMerge /></div></div>
      <div className="finance-surface min-w-0 p-5"><SectionHeader icon={BarChart3} title="渠道收入结构" detail="看清销售来源，不把后续到账再计一次收入。" question="" onAsk={onAsk} /><div className="mt-3 h-72" role="img" aria-label="渠道收入结构图">{analytics.channel_breakdown.length ? <ReactEChartsCore echarts={echarts} option={channelOption} style={{ height: "100%" }} notMerge /> : <EmptyChart text="当前范围还没有可分析的渠道收入。" />}</div></div>
    </section>
    <section className="grid grid-cols-[minmax(0,1fr)_minmax(320px,.52fr)] gap-4">
      <div className="finance-surface min-w-0 p-5"><SectionHeader icon={Activity} title="平台资金闭环情况" detail="按平台区分已到账、结算中、待对账与缺资料金额。" question="" onAsk={onAsk} /><div className="mt-3 h-64" role="img" aria-label="平台资金闭环图">{settlementChannels.length ? <ReactEChartsCore echarts={echarts} option={settlementOption} style={{ height: "100%" }} notMerge /> : <EmptyChart text="当前范围没有平台结算记录。" />}</div></div>
      <div className="finance-surface p-5"><SectionHeader icon={ShieldCheck} title="数据与口径" detail="每个结论都保留完整性和凭证状态。" question="" onAsk={onAsk} /><div className="mt-4 space-y-3 text-xs"><div className="flex items-center justify-between border-b border-stone-100 pb-3"><span className="text-stone-500">原始凭证</span><strong className="text-stone-900">{voucherCount}份</strong></div><div className="flex items-center justify-between border-b border-stone-100 pb-3"><span className="text-stone-500">最新事实日</span><strong className="text-stone-900">{snapshot.latest_data_date || "暂无"}</strong></div><div className="flex items-center justify-between border-b border-stone-100 pb-3"><span className="text-stone-500">店铺可控资金</span><strong className="text-stone-900">{yuan(analytics.kpis.store_controlled_minor)}</strong></div><div className="flex items-center justify-between border-b border-stone-100 pb-3"><span className="text-stone-500">实际银行余额</span><strong className={snapshot.as_of.actual_bank_balance_minor == null ? "text-amber-700" : "text-stone-900"}>{snapshot.as_of.actual_bank_balance_minor == null ? "待导入流水" : yuan(snapshot.as_of.actual_bank_balance_minor)}</strong></div><div className="rounded-lg bg-stone-50 p-3 leading-5 text-stone-600">{overview.profit_status === "confirmed" ? "利润口径已闭环。" : `当前利润结论为不完整，尚缺：${missing.join("、") || "成本资料"}。`}</div></div></div>
    </section>
  </div>;
}

export function FinanceFundsAnalytics({ analytics, onAsk }: { analytics: FinanceAnalyticsV1; onAsk: AskHandler }) {
  const [activeFlowIndex, setActiveFlowIndex] = useState(0);
  useEffect(() => { setActiveFlowIndex(0); }, [analytics.period_start, analytics.period_end]);
  const flowEdges = useMemo(() => analytics.fund_flow_edges.map((item, edgeIndex) => {
    const statusLabel = item.status === "completed" ? "资金移动已完成" : item.status === "awaiting_arrival" ? "已到平台钱包，尚未进入银行账户" : item.status === "awaiting_reconciliation" ? "已到平台绑定卡，待核对工商银行" : "资金位置或凭证待补充";
    const nextAction = item.status === "completed" ? "无需操作，可继续核对原始凭证。" : item.status === "awaiting_arrival" ? "根据平台账期等待到账，到账后补记结果。" : item.status === "awaiting_reconciliation" ? "导入工商银行流水，按金额和日期核销。" : "补充原图、账户或资金当前位置。";
    return { ...item, edgeIndex, statusLabel, nextAction };
  }), [analytics.fund_flow_edges]);
  const activeFlow = flowEdges[activeFlowIndex] ?? null;
  const flowOption = flowEdges.length ? {
    aria: { enabled: true, description: `资金从营业收入、账户流向当前位置和支出去向，共 ${analytics.fund_flow_edges.length} 条路径。` },
    animationDuration: 680,
    animationEasing: "cubicOut" as const,
    tooltip: {
      trigger: "item" as const,
      backgroundColor: "rgba(255,255,255,.96)", borderColor: "#e7e5e4", textStyle: { color: "#292524", fontSize: 12 },
      extraCssText: "box-shadow:0 12px 34px rgba(41,37,36,.12);border-radius:10px;padding:12px 14px;line-height:1.65",
      formatter: (params: { dataType?: string; data?: { source?: string; target?: string; value?: number; statusLabel?: string; evidenceCount?: number; nextAction?: string }; name?: string }) => {
        if (params.dataType === "edge") return `<b>${params.data?.source} → ${params.data?.target}</b><br/><span style="font-size:16px;font-weight:700">${yuan((params.data?.value ?? 0) * 100)}</span><br/>${params.data?.statusLabel ?? ""}<br/>原始凭证 ${params.data?.evidenceCount ?? 0} 份<br/><span style="color:#9a3412">下一步：${params.data?.nextAction ?? ""}</span>`;
        return params.name ?? "";
      },
    },
    series: [{
      type: "sankey" as const,
      left: 22, right: 172, top: 18, bottom: 18,
      nodeWidth: 20, nodeGap: 20, draggable: false, layoutIterations: 48,
      emphasis: { focus: "adjacency" as const, lineStyle: { opacity: .72 } },
      blur: { lineStyle: { opacity: .06 } },
      data: analytics.fund_flow_nodes.map((item) => ({
        name: item.name,
        itemStyle: { color: item.kind === "channel" ? "#9a3412" : item.kind === "pending" ? "#d99a22" : item.kind === "personal" ? "#78716c" : "#23785a", borderColor: "rgba(255,255,255,.9)", borderWidth: 1 },
      })),
      links: flowEdges.map((item) => ({
        source: item.source, target: item.target, value: item.amount_minor / 100,
        edgeIndex: item.edgeIndex, statusLabel: item.statusLabel, evidenceCount: item.evidence_ids.length, nextAction: item.nextAction,
        lineStyle: { color: "gradient", opacity: item.edgeIndex === activeFlowIndex ? .52 : .24, curveness: .52 },
      })),
      lineStyle: { color: "gradient", opacity: .26, curveness: .52 },
      label: { color: "#44403c", fontSize: 12, fontWeight: 500, lineHeight: 18, width: 154, overflow: "truncate" as const },
    }],
  } : null;
  const flowEvents = {
    mouseover: (params: { dataType?: string; data?: { edgeIndex?: number } }) => {
      if (params.dataType === "edge" && typeof params.data?.edgeIndex === "number") setActiveFlowIndex(params.data.edgeIndex);
    },
    click: (params: { dataType?: string; data?: { edgeIndex?: number } }) => {
      if (params.dataType === "edge" && typeof params.data?.edgeIndex === "number") setActiveFlowIndex(params.data.edgeIndex);
    },
  };

  const cashOption = {
    aria: { enabled: true, description: "未来 7、14、30 天预计到账、必须付款与预计余额。" },
    animationDuration: 520,
    animationEasing: "cubicOut" as const,
    tooltip: { trigger: "axis" as const, backgroundColor: "rgba(255,255,255,.96)", borderColor: "#e7e5e4", textStyle: { color: "#292524", fontSize: 12 }, valueFormatter: (value: number) => `¥${value.toLocaleString("zh-CN")}` },
    legend: { bottom: 0, itemWidth: 12, itemHeight: 8, textStyle: { color: "#78716c", fontSize: 10 } },
    grid: { left: 8, right: 8, top: 16, bottom: 36, containLabel: true },
    xAxis: { type: "category" as const, data: analytics.cash_forecast.horizons.map((item) => `${item.days}天`), axisLine: { lineStyle: { color: "#d6d3d1" } }, axisLabel: { color: "#78716c", fontSize: 10 } },
    yAxis: { type: "value" as const, axisLabel: { color: "#78716c", fontSize: 10, formatter: yuanAxis }, splitLine: { lineStyle: { color: "#f0eeec" } } },
    series: [
      { name: "预计到账", type: "bar" as const, data: analytics.cash_forecast.horizons.map((item) => item.expected_inflow_minor / 100), itemStyle: { color: "#0f766e", borderRadius: [4, 4, 0, 0] }, barMaxWidth: 22 },
      { name: "必须付款", type: "bar" as const, data: analytics.cash_forecast.horizons.map((item) => item.required_outflow_minor / 100), itemStyle: { color: "#e7a23b", borderRadius: [4, 4, 0, 0] }, barMaxWidth: 22 },
      { name: "预计余额", type: "line" as const, data: analytics.cash_forecast.horizons.map((item) => item.ending_minor / 100), smooth: true, symbolSize: 7, lineStyle: { color: "#292524", width: 2 }, itemStyle: { color: "#292524" } },
    ],
  };

  return <div className="space-y-4">
    <section className="finance-surface overflow-visible">
      <div className="grid sm:grid-cols-2 xl:grid-cols-4">
        <MetricTile label="期间营业收入" value={yuan(analytics.kpis.merchant_net_minor)} note="销售发生口径，不代表已经到账" formula="各渠道当日实际销售收入合计；与平台钱包、银行卡到账分开" tone="emerald" onActivate={() => onAsk(`拆解 ${analytics.period_start} 至 ${analytics.period_end} 的营业收入来源，并说明哪些尚未到账。`)} />
        <MetricTile label="店铺可控资金账面值" value={yuan(analytics.kpis.store_controlled_minor)} note="按已登记资金轨迹计算，并非银行实时余额" formula="店铺控制账户期初金额 + 已确认流入 - 已确认流出" tone="sky" onActivate={() => onAsk(`解释截至 ${analytics.period_end} 店铺可控资金账面值由哪些账户和流水构成。`)} />
        <MetricTile label="待进入店铺可控账户" value={yuan(analytics.kpis.pending_collection_minor)} note="平台或绑定卡已持有，店铺工商卡尚未收到" formula="已确认属于店铺、但当前位置仍为平台钱包或暂代收账户的金额" tone="amber" onActivate={() => onAsk(`列出截至 ${analytics.period_end} 尚未进入店铺可控账户的每笔资金。`)} />
        <MetricTile label="个人资金流出" value={yuan(analytics.kpis.personal_outflow_minor, "¥0.00")} note="单独核算，不进入店铺成本和利润" formula="招商银行个人账户发生、且业务范围被确认属于个人的支出" onActivate={() => onAsk(`列出 ${analytics.period_start} 至 ${analytics.period_end} 的个人资金流出，并确认没有混入店铺损益。`)} />
      </div>
    </section>

    <section className="finance-surface min-w-0 overflow-hidden">
      <div className="flex items-start justify-between gap-5 border-b border-stone-100 px-5 py-4">
        <SectionHeader icon={ArrowLeftRight} title="资金流通路径" detail="从销售发生、平台结算到工商银行或支出去向；悬停任意路径查看金额、凭证和下一步。" question="" onAsk={onAsk} />
        <button type="button" onClick={() => onAsk(`解释 ${analytics.period_start} 至 ${analytics.period_end} 的整体资金路径，按已完成、等待到账、待对账和资料缺口分组。`)} className="inline-flex min-h-9 shrink-0 items-center gap-2 rounded-lg border border-stone-200 bg-white px-3 text-xs font-semibold text-stone-700 transition hover:border-octo-200 hover:bg-octo-50 hover:text-octo-800"><MessageCircle className="h-3.5 w-3.5" />让 Agent 解读全图</button>
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)_320px]">
        <div className="h-[390px] min-w-0 p-4" role="img" aria-label="店铺资金流通路径图">
          {flowOption ? <ReactEChartsCore echarts={echarts} option={flowOption} onEvents={flowEvents} style={{ height: "100%" }} notMerge /> : <EmptyChart text="本期还没有可绘制的资金路径。录入销售、到账或支出后，这里会自动串起来。" />}
        </div>
        <aside className="flex min-w-0 flex-col justify-between border-l border-stone-100 bg-[#fbfaf8] p-5" aria-live="polite">
          {activeFlow ? <>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[.12em] text-stone-400">当前路径分析</p>
              <p className="mt-3 text-[15px] font-semibold leading-6 text-stone-950">{activeFlow.source}<span className="mx-2 text-octo-500">→</span>{activeFlow.target}</p>
              <p className="mt-3 text-2xl font-semibold tabular-nums tracking-[-.03em] text-stone-950">{yuan(activeFlow.amount_minor)}</p>
              <div className="mt-4 space-y-3 border-t border-stone-200 pt-4 text-xs leading-5">
                <div><span className="text-stone-400">当前状态</span><p className="font-medium text-stone-800">{activeFlow.statusLabel}</p></div>
                <div><span className="text-stone-400">原始凭证</span><p className="font-medium text-stone-800">{activeFlow.evidence_ids.length} 份已关联</p></div>
                <div><span className="text-stone-400">建议动作</span><p className="font-medium text-octo-800">{activeFlow.nextAction}</p></div>
              </div>
            </div>
            <button type="button" onClick={() => onAsk(`分析资金路径“${activeFlow.source} → ${activeFlow.target}”，金额 ${yuan(activeFlow.amount_minor)}，当前状态是“${activeFlow.statusLabel}”，已关联 ${activeFlow.evidence_ids.length} 份凭证。请说明资金是否可控、是否影响收入或利润、以及我下一步要做什么。`)} className="finance-button-primary mt-5 w-full justify-center"><MessageCircle className="h-4 w-4" />问 Agent 这条资金</button>
          </> : <p className="text-xs text-stone-500">悬停一条资金路径查看详情。</p>}
        </aside>
      </div>
    </section>

    <section className="grid gap-4">
      <div className="finance-surface min-w-0 p-5">
        <SectionHeader icon={ShieldCheck} title="未来资金安全" detail={analytics.cash_forecast.status === "partial" ? "未来收付尚未登记完整，图表只展示已知项。" : "按已登记的预计到账、必须付款和安全备用金计算。"} question={`按 ${analytics.period_end} 已登记资料，未来 7、14、30 天资金链有什么风险，还缺哪些资料？`} onAsk={onAsk} />
        <div className="mt-4 h-72" role="img" aria-label="未来七天十四天三十天资金安全图"><ReactEChartsCore echarts={echarts} option={cashOption} style={{ height: "100%" }} notMerge /></div>
      </div>
    </section>

  </div>;
}

export function FinanceSettlementAnalytics({ analytics, onAsk }: { analytics: FinanceAnalyticsV1; onAsk: AskHandler }) {
  const settlementRows = [...analytics.settlement_timeline].reverse().slice(0, 12);
  return <section className="finance-surface p-5">
    <SectionHeader icon={WalletCards} title="平台结算进度" detail="发生日、预计钱包日、当前位置和到账状态同时展示；无明确规则的平台不猜测日期。" question={`检查 ${analytics.period_start} 至 ${analytics.period_end} 平台结算，哪些已到钱包、哪些前老板代收、哪些需要补凭证？`} onAsk={onAsk} />
    {settlementRows.length === 0 ? <div className="mt-4"><EmptyChart text="本期还没有平台营业收入记录。" /></div> : <div className="mt-4 grid gap-2 lg:grid-cols-2">
      {settlementRows.map((item) => {
        const mark = channelMark(item.channel);
        return <article key={item.id} className="flex min-w-0 items-start gap-3 rounded-lg border border-stone-200 p-3">
          <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg text-xs font-bold ${mark.className}`}>{mark.mark}</span>
          <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-bold text-stone-900">{item.channel} · {item.business_date}</p><strong className="text-sm tabular-nums text-stone-950">{yuan(item.amount_minor)}</strong></div><p className="mt-1 truncate text-[11px] text-stone-600">{item.current_location}</p><div className="mt-2 flex flex-wrap items-center gap-2"><span className={`rounded-full px-2 py-1 text-[10px] font-semibold ring-1 ring-inset ${STATUS_TONES[item.status]}`}>{item.status_label}</span><span className="text-[10px] text-stone-500">{item.expected_wallet_date ? `预计到平台钱包 ${item.expected_wallet_date}${item.withdrawal_mode === "manual" ? " · 需手动提现" : ""}` : item.expected_bank_date ? `预计到平台绑定卡 ${item.expected_bank_date}` : "结算日以平台账单为准"}</span>{item.evidence_id && <span className="inline-flex items-center gap-1 text-[10px] text-emerald-700"><ReceiptText className="h-3 w-3" />已关联凭证</span>}</div></div>
        </article>;
      })}
    </div>}
  </section>;
}

export function FinanceProfitAnalytics({ analytics, onAsk }: { analytics: FinanceAnalyticsV1; onAsk: AskHandler }) {
  const dates = analytics.daily_series.map((item) => item.business_date.slice(5));
  const toYuanOrNull = (value: number | null) => value == null ? null : value / 100;
  const trendOption = {
    aria: { enabled: true, description: "每日营业收入、会计已确认销售收入和店铺资金流出趋势，未录入日期保持空缺。" },
    animationDuration: 520,
    animationEasing: "cubicOut" as const,
    tooltip: { trigger: "axis" as const, backgroundColor: "rgba(255,255,255,.96)", borderColor: "#e7e5e4", textStyle: { color: "#292524", fontSize: 12 }, valueFormatter: (value: number | null) => value == null ? "未录入" : `¥${value.toLocaleString("zh-CN")}` },
    legend: { bottom: 0, itemWidth: 12, itemHeight: 8, textStyle: { color: "#78716c", fontSize: 10 } },
    grid: { left: 8, right: 10, top: 16, bottom: 42, containLabel: true },
    xAxis: { type: "category" as const, data: dates, axisLabel: { color: "#78716c", fontSize: 10, rotate: dates.length > 14 ? 35 : 0 }, axisLine: { lineStyle: { color: "#d6d3d1" } } },
    yAxis: { type: "value" as const, axisLabel: { color: "#78716c", fontSize: 10, formatter: yuanAxis }, splitLine: { lineStyle: { color: "#f0eeec" } } },
    series: [
      { name: "营业收入", type: "line" as const, connectNulls: false, smooth: .2, symbolSize: 6, data: analytics.daily_series.map((item) => toYuanOrNull(item.merchant_net_minor)), lineStyle: { color: "#0f766e", width: 2 }, itemStyle: { color: "#0f766e" }, areaStyle: { color: "rgba(15,118,110,.08)" } },
      { name: "会计已确认销售收入", type: "line" as const, connectNulls: false, symbolSize: 5, data: analytics.daily_series.map((item) => toYuanOrNull(item.accounting_revenue_minor)), lineStyle: { color: "#0284c7", width: 1.5, type: "dashed" as const }, itemStyle: { color: "#0284c7" } },
      { name: "店铺资金流出", type: "bar" as const, data: analytics.daily_series.map((item) => toYuanOrNull(item.store_outflow_minor)), itemStyle: { color: "rgba(214,165,37,.58)", borderRadius: [3, 3, 0, 0] }, barMaxWidth: 16 },
    ],
  };

  const expenseOption = analytics.expense_breakdown.length ? {
    aria: { enabled: true, description: "已确认进入店铺损益的成本费用结构。" },
    tooltip: { trigger: "axis" as const, axisPointer: { type: "shadow" as const }, valueFormatter: (value: number) => `¥${value.toLocaleString("zh-CN")}` },
    grid: { left: 8, right: 18, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: "value" as const, axisLabel: { color: "#78716c", fontSize: 10, formatter: yuanAxis }, splitLine: { lineStyle: { color: "#f0eeec" } } },
    yAxis: { type: "category" as const, inverse: true, data: analytics.expense_breakdown.map((item) => item.label), axisLabel: { color: "#57534e", fontSize: 10, width: 92, overflow: "truncate" as const } },
    series: [{ type: "bar" as const, data: analytics.expense_breakdown.map((item) => item.amount_minor / 100), barMaxWidth: 18, itemStyle: { color: "#d6a525", borderRadius: [0, 4, 4, 0] } }],
  } : null;

  const confirmedProfit = analytics.profit_bridge.status === "confirmed";
  const resultLabel = confirmedProfit ? "已确认净利润" : "已录收支差额";
  const bridgeRows = [
    ...analytics.profit_bridge.rows,
    {
      key: "result",
      label: resultLabel,
      amount_minor: analytics.profit_bridge.net_profit_minor ?? analytics.profit_bridge.provisional_net_profit_minor,
    },
  ];
  let running = 0;
  const bridgeBase: number[] = [];
  const bridgeValues: number[] = [];
  bridgeRows.forEach((item, index) => {
    const value = item.amount_minor / 100;
    if (index === 0) {
      running = value; bridgeBase.push(0); bridgeValues.push(value); return;
    }
    if (index === bridgeRows.length - 1) {
      bridgeBase.push(0); bridgeValues.push(value); return;
    }
    running += value;
    bridgeBase.push(Math.max(running, 0));
    bridgeValues.push(Math.abs(value));
  });
  const bridgeOption = {
    aria: { enabled: true, description: `营业收入逐项扣除已记录成本，得到${resultLabel}。` },
    animationDuration: 520,
    animationEasing: "cubicOut" as const,
    tooltip: { trigger: "axis" as const, axisPointer: { type: "shadow" as const }, formatter: (params: Array<{ seriesName: string; dataIndex: number }>) => { const item = bridgeRows[params[0]?.dataIndex ?? 0]; return `${item.label}<br/><b>${yuan(item.amount_minor)}</b>`; } },
    grid: { left: 8, right: 8, top: 8, bottom: 46, containLabel: true },
    xAxis: { type: "category" as const, data: bridgeRows.map((item) => item.label), axisLabel: { color: "#78716c", fontSize: 9, interval: 0, rotate: 28 } },
    yAxis: { type: "value" as const, axisLabel: { color: "#78716c", fontSize: 10, formatter: yuanAxis }, splitLine: { lineStyle: { color: "#f0eeec" } } },
    series: [
      { name: "基底", type: "bar" as const, stack: "bridge", silent: true, data: bridgeBase, itemStyle: { color: "transparent" }, emphasis: { itemStyle: { color: "transparent" } } },
      { name: "金额", type: "bar" as const, stack: "bridge", data: bridgeValues.map((value, index) => ({ value, itemStyle: { color: index === 0 ? "#0f766e" : index === bridgeValues.length - 1 ? "#292524" : "#d6a525", borderRadius: [4, 4, 0, 0] } })), barMaxWidth: 30 },
    ],
  };

  const profitValue = analytics.kpis.net_profit_minor ?? analytics.kpis.provisional_net_profit_minor;
  const missingLabels: Record<string, string> = {
    daily_close: "完整日结", food_cost: "食材实际耗用", labor: "人工成本", other_cost: "其他经营费用",
    packaging_cost: "包装耗用", rent: "房租", utility: "水电燃气",
  };
  const missingCostLabels = analytics.missing_inputs.map((item) => missingLabels[item] || item);
  return <div className="space-y-4">
    {!confirmedProfit && <motion.section initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-3 rounded-xl border border-amber-200 bg-amber-50/70 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-start gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-amber-100 text-amber-800"><AlertTriangle className="h-4 w-4" /></span><div><p className="text-xs font-bold text-amber-950">当前不能确认净利润</p><p className="mt-1 text-[11px] leading-5 text-amber-800">尚缺：{missingCostLabels.join("、") || "成本资料"}。下方差额只反映已录收入减已录成本。</p></div></div>
      <button type="button" onClick={() => onAsk(`说明 ${analytics.period_start} 至 ${analytics.period_end} 为什么还不能确认净利润，并按影响大小列出需要补齐的资料。`)} className="inline-flex min-h-9 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-amber-300 bg-white px-3 text-[11px] font-semibold text-amber-900 transition hover:border-amber-500"><MessageCircle className="h-3.5 w-3.5" />问如何补齐</button>
    </motion.section>}
    <section className="finance-surface p-5">
      <div className="grid sm:grid-cols-2 xl:grid-cols-5">
        <MetricTile label="期间营业收入" value={yuan(analytics.kpis.merchant_net_minor)} note="销售发生口径，不代表资金已到账" formula="各渠道实际销售收入合计" tone="emerald" onActivate={() => onAsk(`拆解 ${analytics.period_start} 至 ${analytics.period_end} 的营业收入来源。`)} />
        <MetricTile label="会计已确认销售收入" value={yuan(analytics.profit_bridge.rows[0]?.amount_minor ?? 0)} note="已满足会计确认条件的销售收入" formula="已生成并过账的销售收入分录合计" tone="sky" onActivate={() => onAsk(`解释期间营业收入与会计已确认销售收入为何可能不同。`)} />
        <MetricTile label="已确认经营成本" value={yuan(analytics.kpis.known_operating_cost_minor, "¥0.00")} note="仅包含已有可靠资料并进入损益的成本" formula="已过账的食材耗用、人工、房租、水电等经营成本" tone="amber" onActivate={() => onAsk(`拆解 ${analytics.period_start} 至 ${analytics.period_end} 已确认经营成本。`)} />
        <MetricTile label={resultLabel} value={yuan(profitValue)} note={confirmedProfit ? "成本资料已闭环，可作为净利润" : "非净利润，只是已录收入减已录成本"} formula={confirmedProfit ? "会计营业收入 - 全部已确认经营成本" : "已录营业收入 - 当前已录经营成本；缺失成本尚未扣除"} tone={confirmedProfit ? "emerald" : "stone"} onActivate={() => onAsk(`解释 ${analytics.period_start} 至 ${analytics.period_end} 的${resultLabel}及全部缺口。`)} />
        <MetricTile label="进货入库（资产）" value={yuan(analytics.kpis.inventory_purchase_minor, "¥0.00")} note="形成库存，实际耗用时才进入经营成本" formula="已完成入库的采购金额；不直接计入当期费用" onActivate={() => onAsk(`说明期间进货入库如何影响现金、库存和利润。`)} />
      </div>
    </section>

    <section className="finance-surface p-5">
      <SectionHeader icon={BarChart3} title="收入与资金流出趋势" detail="空白日期表示尚未录入，图表不用 0 元替代缺失数据。" question={`分析 ${analytics.period_start} 至 ${analytics.period_end} 的营业收入、会计已确认销售收入和店铺资金流出趋势，哪几天需要补资料？`} onAsk={onAsk} />
      <div className="mt-4 h-72" role="img" aria-label="店铺收入与资金流出日趋势图"><ReactEChartsCore echarts={echarts} option={trendOption} style={{ height: "100%" }} notMerge /></div>
    </section>

    <section className="grid gap-4 xl:grid-cols-2">
      <div className="finance-surface min-w-0 p-5">
        <SectionHeader icon={WalletCards} title="已确认成本结构" detail="只展示已进入店铺损益的成本；个人消费、进货入库、还本和转账都不混进来。" question={`解释 ${analytics.period_start} 至 ${analytics.period_end} 的成本结构，哪些是经营成本，哪些只是资金流出？`} onAsk={onAsk} />
        <div className="mt-4 h-64" role="img" aria-label="店铺已确认成本结构图">{expenseOption ? <ReactEChartsCore echarts={echarts} option={expenseOption} style={{ height: "100%" }} notMerge /> : <EmptyChart text="本期还没有已确认进入损益的成本。进货仍可能已记入库存，不在此图中当作费用。" />}</div>
      </div>
      <div className="finance-surface min-w-0 p-5">
        <SectionHeader icon={CircleDollarSign} title="利润形成过程" detail={confirmedProfit ? "从营业收入逐项扣除完整成本，得到已确认净利润。" : "成本未闭环，最后一列是已录收支差额，不是净利润。"} question={`解释 ${analytics.period_start} 至 ${analytics.period_end} 的利润形成过程，为什么现在还不能确认最终利润？`} onAsk={onAsk} />
        <div className="mt-4 h-64" role="img" aria-label="店铺利润形成瀑布图"><ReactEChartsCore echarts={echarts} option={bridgeOption} style={{ height: "100%" }} notMerge /></div>
      </div>
    </section>
  </div>;
}
