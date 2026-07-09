"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import ReactEChartsCore from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import {
  ArrowRight,
  Calculator,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  HelpCircle,
  PackageSearch,
  Receipt,
  ShoppingBag,
  Utensils,
  AlertTriangle,
  Wallet,
} from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import {
  DEFAULT_PROJECT_ID,
  getConsumptionVariance,
  getForecast,
  getOperationSummary,
  getOperations,
  getProjectCockpit,
  getPurchases,
  getMoneyView,
  type ConsumptionVariance,
  type DailyOperationEntry,
  type ForecastItem,
  type MoneyView,
  type OperationSummary,
  type PurchaseRecord,
} from "@/lib/api";
import {
  calcEntryNetProfit,
  calcEntryTotalCost,
  calcCostBreakdown,
  calcBreakEvenAnalysis,
  type BreakEvenResult,
} from "@/domain/calculations";

echarts.use([BarChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

const COST_COLORS = ["#D9261C", "#F97316", "#c8a64e", "#64748b", "#0ea5e9", "#84cc16", "#8b5cf6", "#f59e0b"];
const STATUS_COLORS: Record<string, string> = {
  ok: "#10b981",
  no_bom: "#94a3b8",
  no_sales: "#94a3b8",
  over_consumption: "#ef4444",
  under_consumption: "#f59e0b",
  missing_opening_count: "#94a3b8",
  missing_count: "#94a3b8",
};
const STATUS_LABELS: Record<string, string> = {
  ok: "正常",
  no_bom: "暂不可核验",
  no_sales: "无销量",
  over_consumption: "消耗偏高",
  under_consumption: "消耗偏低",
  missing_opening_count: "缺期初盘点",
  missing_count: "缺盘点",
};
const REAL_FIXTURE_DATE = "2026-07-04";

export default function ProfitPage() {
  const [summary, setSummary] = useState<OperationSummary | null>(null);
  const [entries, setEntries] = useState<DailyOperationEntry[]>([]);
  const [variance, setVariance] = useState<ConsumptionVariance | null>(null);
  const [forecast, setForecast] = useState<ForecastItem[]>([]);
  const [profile, setProfile] = useState<Record<string, unknown>>({});
  const [purchases, setPurchases] = useState<PurchaseRecord[]>([]);
  const [moneyView, setMoneyView] = useState<MoneyView | null>(null);
  const [initialized, setInitialized] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoadError(null);
    try {
      const [sum, ops, fRes, cockpit, purchaseRes, moneyRes] = await Promise.all([
        getOperationSummary(DEFAULT_PROJECT_ID, 30),
        getOperations(DEFAULT_PROJECT_ID, 30),
        getForecast(DEFAULT_PROJECT_ID),
        getProjectCockpit(DEFAULT_PROJECT_ID, 30),
        getPurchases(DEFAULT_PROJECT_ID, 30),
        getMoneyView(DEFAULT_PROJECT_ID, REAL_FIXTURE_DATE),
      ]);
      setSummary(sum);
      setEntries(ops.entries);
      setForecast(fRes.forecast.filter((f) => f.action === "urgent" || f.action === "recommend").slice(0, 4));
      setProfile(cockpit.profile || {});
      setPurchases(purchaseRes.purchases || []);
      setMoneyView(moneyRes);
      if (ops.entries.length > 0) {
        const sorted = [...ops.entries].sort((a, b) => a.date.localeCompare(b.date));
        const start = sorted[0].date;
        const end = sorted[sorted.length - 1].date;
        try {
          const v = await getConsumptionVariance(DEFAULT_PROJECT_ID, start, end);
          setVariance(v);
        } catch {
          setVariance(null);
        }
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "加载失败，请检查后端服务");
    }
    setInitialized(true);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const hasData = summary && summary.entry_count > 0;
  const sortedEntries = useMemo(() => [...entries].sort((a, b) => a.date.localeCompare(b.date)), [entries]);
  const periodStart = sortedEntries[0]?.date ?? "";
  const periodEnd = sortedEntries[sortedEntries.length - 1]?.date ?? "";

  const profitReady = Boolean(summary?.profit_ready);
  const transferFee = Number(profile.transfer_fee || 0);
  const monthlyRent = Number(profile.monthly_rent || 0);
  const garbageFee = Number(profile.monthly_garbage_fee || 0);
  const paidPurchases = purchases
    .filter((purchase) => purchase.payment_status.includes("已付"))
    .reduce((sum, purchase) => sum + (purchase.paid_amount || purchase.total_cost), 0);
  const pendingPurchases = purchases
    .filter((purchase) => purchase.fulfillment_status === "ordered")
    .reduce((sum, purchase) => sum + (purchase.paid_amount || purchase.total_cost), 0);
  const breakEvenData: BreakEvenResult | null = hasData && profitReady
    ? calcBreakEvenAnalysis(entries, summary.entry_count)
    : null;

  // 日结对账数据
  const reconciliation = useMemo(() => sortedEntries.map((e) => ({
    date: e.date,
    original: e.original_amount ?? e.revenue,
    actual: e.actual_revenue ?? e.revenue,
    discount: e.merchant_discount ?? 0,
    refund: e.refund_amount ?? 0,
    refundOrders: e.refund_orders ?? 0,
    orders: e.orders,
    itemsSold: e.items_sold ?? e.orders,
    customers: e.customers ?? null,
    aovBefore: e.avg_order_value_before_discount ?? (e.orders > 0 ? (e.original_amount ?? e.revenue) / e.orders : 0),
    aovAfter: e.avg_order_value_after_discount ?? (e.orders > 0 ? (e.actual_revenue ?? e.revenue) / e.orders : 0),
    dineInOrders: e.dine_in_orders,
    deliveryOrders: e.delivery_orders,
  })), [sortedEntries]);

  const totals = useMemo(() => {
    if (reconciliation.length === 0) return null;
    return reconciliation.reduce((acc, cur) => ({
      original: acc.original + cur.original,
      actual: acc.actual + cur.actual,
      discount: acc.discount + cur.discount,
      refund: acc.refund + cur.refund,
      orders: acc.orders + cur.orders,
      itemsSold: acc.itemsSold + cur.itemsSold,
      refundOrders: acc.refundOrders + cur.refundOrders,
    }), { original: 0, actual: 0, discount: 0, refund: 0, orders: 0, itemsSold: 0, refundOrders: 0 });
  }, [reconciliation]);

  // 利润拆解
  const costPie = hasData && profitReady ? calcCostBreakdown(entries, summary.total_revenue) : [];
  const dailyProfit = sortedEntries.map((e) => ({
    date: e.date.slice(5),
    营收: e.actual_revenue ?? e.revenue,
    成本: profitReady ? Math.round(calcEntryTotalCost(e)) : null,
    净利: profitReady ? Math.round(calcEntryNetProfit(e)) : null,
  }));

  const costPieOption = costPie.length > 0 ? {
    tooltip: { trigger: "item" as const, backgroundColor: "rgba(255,255,255,0.92)", borderColor: "rgba(0,0,0,0.08)", borderRadius: 12, textStyle: { color: "#1a1a1a", fontSize: 12 }, formatter: "{b}: {c}%" },
    legend: { orient: "vertical" as const, right: 0, top: "center", textStyle: { fontSize: 10, color: "#6b7280" }, itemWidth: 10, itemHeight: 10 },
    series: [{
      type: "pie" as const,
      radius: ["45%", "75%"],
      center: ["35%", "50%"],
      avoidLabelOverlap: false,
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: "bold" } },
      data: costPie.map((c, i) => ({ ...c, itemStyle: { color: COST_COLORS[i % COST_COLORS.length] } })),
    }],
  } : null;

  const profitTrendOption = {
    tooltip: { trigger: "axis" as const, backgroundColor: "rgba(255,255,255,0.92)", borderColor: "rgba(0,0,0,0.08)", borderRadius: 12, textStyle: { color: "#1a1a1a", fontSize: 12 } },
    legend: { data: profitReady ? ["营收", "成本", "净利"] : ["营收"], bottom: 0, textStyle: { fontSize: 11, color: "#6b7280" } },
    grid: { left: 8, right: 16, top: 8, bottom: 32, containLabel: true },
    xAxis: { type: "category" as const, data: dailyProfit.map((d) => d.date), axisLabel: { fontSize: 10, color: "#6b7280" } },
    yAxis: { type: "value" as const, axisLabel: { fontSize: 10, color: "#6b7280", formatter: (v: number) => `¥${v}` }, splitLine: { lineStyle: { color: "rgba(0,0,0,0.06)" } } },
    series: [
      { name: "营收", type: "line" as const, data: dailyProfit.map((d) => d.营收), smooth: true, lineStyle: { color: "#0F4C3A", width: 2 }, itemStyle: { color: "#0F4C3A" }, symbol: "none", areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: "rgba(15,76,58,0.15)" }, { offset: 1, color: "rgba(15,76,58,0)" }]) } },
      ...(profitReady ? [
        { name: "成本", type: "line" as const, data: dailyProfit.map((d) => d.成本), smooth: true, lineStyle: { color: "#D9261C", width: 1.5 }, itemStyle: { color: "#D9261C" }, symbol: "none" },
        { name: "净利", type: "line" as const, data: dailyProfit.map((d) => d.净利), smooth: true, lineStyle: { color: "#c8a64e", width: 2 }, itemStyle: { color: "#c8a64e" }, symbol: "circle", symbolSize: 5 },
      ] : []),
    ],
  };

  // 渠道聚合
  const channelAggregated = useMemo(() => {
    const map = new Map<string, { orders: number; original: number; actual: number; actualKnown: boolean }>();
    let hasData = false;
    sortedEntries.forEach((e) => {
      e.channel_breakdown?.forEach((c) => {
        hasData = true;
        const cur = map.get(c.channel) || { orders: 0, original: 0, actual: 0, actualKnown: false };
        cur.orders += c.orders;
        cur.original += c.original_amount;
        if (c.actual_revenue != null) {
          cur.actual += c.actual_revenue;
          cur.actualKnown = true;
        }
        map.set(c.channel, cur);
      });
    });
    if (!hasData) return null;
    return Array.from(map.entries()).map(([channel, v]) => ({
      channel,
      ...v,
      discountRate: v.actualKnown && v.original > 0 ? (v.original - v.actual) / v.original : null,
    }));
  }, [sortedEntries]);

  // 支付聚合
  const paymentAggregated = useMemo(() => {
    const map = new Map<string, { orders: number; amount: number }>();
    let hasData = false;
    sortedEntries.forEach((e) => {
      e.payment_methods?.forEach((p) => {
        hasData = true;
        const cur = map.get(p.method) || { orders: 0, amount: 0 };
        cur.orders += p.orders;
        cur.amount += p.amount;
        map.set(p.method, cur);
      });
    });
    if (!hasData) return null;
    return Array.from(map.entries()).map(([method, v]) => ({ method, ...v })).sort((a, b) => b.amount - a.amount);
  }, [sortedEntries]);

  // 明日动作
  const actions = useMemo(() => {
    const list: Array<{ icon: React.ElementType; title: string; body: string; tone: "good" | "watch" | "risk"; href: string }> = [];
    if (!summary) return list;

    if (!summary.profit_ready) {
      list.push({
        icon: Calculator,
        title: "补齐成本后才能算真实利润",
        body: "当前已确认三天实收；仍缺食材、包装、人工、房租和水电日摊销。",
        tone: "watch",
        href: "/capture",
      });
    } else if (breakEvenData) {
      if (!breakEvenData.is_profitable) {
        list.push({ icon: AlertTriangle, title: "日均未过保本线", body: `实际日均 ¥${breakEvenData.daily_revenue.toLocaleString()}，保本 ¥${breakEvenData.daily_breakeven_revenue?.toLocaleString() ?? "—"}，差距 ¥${Math.abs(breakEvenData.gap_to_breakeven ?? 0).toLocaleString()}`, tone: "risk", href: "/dashboard" });
      } else {
        list.push({ icon: CheckCircle2, title: "已过保本线", body: `日均盈余 ¥${(breakEvenData.gap_to_breakeven ?? 0).toLocaleString()}，继续观察变动成本率`, tone: "good", href: "/dashboard" });
      }
    }

    // 食材率
    if (summary.food_cost_rate > 0.38) {
      list.push({ icon: Utensils, title: "食材成本率偏高", body: `当前 ${(summary.food_cost_rate * 100).toFixed(1)}%，建议核对采购价、损耗和份量`, tone: "watch", href: "/inventory" });
    }

    // 库存预警
    if (forecast.length > 0) {
      list.push({ icon: PackageSearch, title: `补货：${forecast[0].name}`, body: forecast[0].days_remaining != null ? `预计剩 ${Math.round(forecast[0].days_remaining)} 天` : "库存预警，建议下单", tone: "risk", href: "/inventory" });
    }

    // 渠道
    const takeoutRatio = summary.takeout_ratio ?? 0;
    if (takeoutRatio > 0.45) {
      list.push({ icon: ShoppingBag, title: "外卖占比偏高", body: `外卖占比 ${(takeoutRatio * 100).toFixed(0)}%，检查满减/抽佣是否侵蚀利润`, tone: "watch", href: "/channels" });
    }

    // 库存差异
    if (variance) {
      if (variance.verification_coverage < 0.3) {
        list.push({ icon: HelpCircle, title: "库存差异暂不可核验", body: "缺少 BOM 或商品销量明细，无法判断实际消耗是否合理，建议补充配方", tone: "watch", href: "/inventory" });
      } else if (variance.total_variance_value > 50) {
        list.push({ icon: PackageSearch, title: "库存差异金额偏大", body: `差异金额 ¥${variance.total_variance_value.toFixed(0)}，建议盘点并核对 BOM`, tone: "risk", href: "/inventory" });
      }
    }

    return list;
  }, [summary, breakEvenData, forecast, variance]);

  // 经营结论
  const headline = useMemo(() => {
    if (!summary) return "数据加载中…";
    const days = summary.entry_count;
    const totalActual = summary.total_revenue;
    if (!summary.profit_ready) {
      return `近 ${days} 天实收 ¥${Math.round(totalActual).toLocaleString()}，共 ${summary.total_orders} 单；收入已确认，成本未补齐，暂不显示净利与保本结论`;
    }
    const profit = summary.net_profit;
    const profitRate = totalActual > 0 ? profit / totalActual : 0;
    const breakeven = breakEvenData?.daily_breakeven_revenue ?? 0;
    const actualDaily = breakEvenData?.daily_revenue ?? 0;
    const parts: string[] = [];
    parts.push(`近 ${days} 天实收 ¥${Math.round(totalActual).toLocaleString()}，净利 ¥${Math.round(profit).toLocaleString()}（${(profitRate * 100).toFixed(1)}%）`);
    if (breakeven > 0) {
      parts.push(actualDaily >= breakeven
        ? `日均 ¥${actualDaily.toLocaleString()} 已过保本线 ¥${breakeven.toLocaleString()}`
        : `日均 ¥${actualDaily.toLocaleString()} 未达保本线 ¥${breakeven.toLocaleString()}`);
    }
    if (summary.food_cost_rate > 0.38) {
      parts.push(`食材率 ${(summary.food_cost_rate * 100).toFixed(1)}% 偏高`);
    }
    if (variance && variance.verification_coverage < 0.3) {
      parts.push("库存消耗因缺 BOM 暂不可核验");
    }
    return parts.join("；");
  }, [summary, breakEvenData, variance]);

  return (
    <ModulePage module={getModule("/profit")}>
      <div className="space-y-5">
        {!initialized && <div className="h-0.5 w-full animate-pulse rounded-full bg-primary/30" />}
        {loadError && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-red-800">⚠️ {loadError}</p>
              <button onClick={fetchData} className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white">重试</button>
            </div>
          </div>
        )}
        {moneyView && (
          <section className="rounded-2xl border border-stone-200 bg-white/80 p-4 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-bold text-stone-950">钱账：钱在哪里</p>
                <p className="mt-1 text-xs leading-5 text-stone-500">7/4 销售发生、客如云待结算、第三方平台、前老板账户和老板现金分开解释。</p>
              </div>
              <span className="rounded-full bg-stone-900 px-3 py-1 text-xs font-semibold text-white">2026-07-04</span>
            </div>
            {moneyView.fixture_sales && (
              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                <MoneyBlock title="1. 今日销售发生" rows={[
                  ["订单金额", `¥${moneyView.fixture_sales.sales.order_amount.toFixed(2)}`],
                  ["营业收入", `¥${moneyView.fixture_sales.sales.net_operating_income.toFixed(2)}`],
                  ["店内营业收入", `¥${moneyView.fixture_sales.sales.dine_in_income.toFixed(2)}`],
                  ["第三方营业收入", `¥${moneyView.fixture_sales.sales.third_party_income.toFixed(2)}`],
                ]} source="来源：7/4 客如云营业日报" />
                <MoneyBlock title="2. 老板已掌握资金" rows={[
                  ["招商银行卡到账", "待确认"],
                  ["现金", "¥185.00，待确认"],
                ]} source="来源：7/4 客如云营业概况 / 微信聊天截图" />
                <MoneyBlock title="3. 客如云待结算" rows={[
                  ["微信", "¥956.00"],
                  ["支付宝", "¥166.00"],
                  ["二代码支付小程序", "¥1.00"],
                  ["是否 T+1 到招行卡", "待确认"],
                ]} source="来源：7/4 客如云营业概况" />
                <MoneyBlock title="4. 第三方/平台待确认" rows={[
                  ["淘宝闪购相关金额", "¥104.37 / ¥224.01 需对账"],
                  ["美团外卖相关金额", "¥81.40 / ¥188.73 需对账"],
                  ["抖音团购券", "¥226.76"],
                  ["美团团购券", "¥75.27"],
                  ["需要确认", "平台未结算 / 前老板代收 / 已回款"],
                ]} source="来源：7/4 客如云营业概况" />
                <MoneyBlock title="5. 前老板账户" rows={[
                  ["前老板应转给我", moneyView.former_owner?.receivable_from_former_owner || "待确认"],
                  ["前老板已转给我", moneyView.former_owner?.transferred_to_owner || "待确认"],
                  ["待分摊回款", moneyView.former_owner?.pending_allocation || "待确认"],
                  ["当前未结清", moneyView.former_owner?.unsettled || "待确认"],
                ]} source="来源：微信聊天截图" />
                <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-3">
                  <p className="text-xs font-semibold text-amber-900">重要提示</p>
                  <p className="mt-1 text-[11px] leading-5 text-amber-800">
                    前老板回款是<b>资金转移</b>，不是新的销售收入。它只改变钱的位置（从前老板账户 → 老板银行卡），
                    不增加今日营业收入，也不记入利润。确认回款时生成的是「应收回款 / 内部转账」类型。
                  </p>
                </div>
                <MoneyBlock title="6. 不是收入的项目" rows={[
                  ["退款/扣款", "与收入分开"],
                  ["采购支出", "付款影响现金，不等于今日消耗"],
                  ["非经营款", "不计入销售"],
                  ["前老板转账", "不是新收入，是应收回款"],
                ]} source="规则：可信经营账本" />
              </div>
            )}
            <div className="mt-3 grid gap-2 text-xs text-stone-600 md:grid-cols-2">
              {moneyView.rules.map((rule) => (
                <p key={rule} className="rounded-xl bg-stone-50 px-3 py-2">{rule}</p>
              ))}
            </div>
          </section>
        )}
        {initialized && !hasData && (
          <div className="rounded-2xl border border-dashed border-white/60 bg-white/35 p-8 text-center">
            <p className="text-sm font-medium text-on-background">还没有经营数据</p>
            <p className="mt-1 text-xs text-on-surface-variant">在首页录入日报后这里会显示利润拆解</p>
          </div>
        )}

        {hasData && (
          <>
            {/* 首屏：经营结论 + 核心指标 */}
            <section className="relative overflow-hidden rounded-3xl border border-stone-200 bg-[linear-gradient(135deg,#fffdf8_0%,#fff7ed_48%,#fef2e7_100%)] p-5 shadow-[0_22px_70px_rgba(120,88,55,0.16)]">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-octo-500/10">
                  <Wallet className="h-5 w-5 text-octo-600" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-stone-500">经营结论 · {periodStart && periodEnd ? `${periodStart.slice(5)} ~ ${periodEnd.slice(5)}` : ""}</p>
                  <h1 className="mt-1 text-lg font-bold leading-snug text-stone-900">{headline}</h1>
                </div>
              </div>
              <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
                <HeroKpi label="实收总额" value={`¥${(summary!.total_revenue / 1000).toFixed(1)}k`} sub={`${summary!.entry_count} 天`} tone="info" />
                <HeroKpi label="净利" value={profitReady ? `¥${(summary!.net_profit / 1000).toFixed(1)}k` : "待核算"} sub={profitReady ? `${(summary!.net_profit / Math.max(summary!.total_revenue, 1) * 100).toFixed(1)}%` : "成本未补齐"} tone={profitReady ? (summary!.net_profit > 0 ? "good" : "risk") : "watch"} />
                <HeroKpi label="日均实收" value={`¥${Math.round(summary!.total_revenue / summary!.entry_count).toLocaleString()}`} sub={`${summary!.total_orders} 单`} tone="info" />
                <HeroKpi label="食材率" value={profitReady ? `${(summary!.food_cost_rate * 100).toFixed(1)}%` : "待录入"} sub={profitReady ? (summary!.food_cost_rate > 0.38 ? "偏高" : "正常") : "不能用 0% 代替"} tone={profitReady ? (summary!.food_cost_rate > 0.38 ? "watch" : "good") : "watch"} />
              </div>
            </section>

            {/* 1. 日结对账 */}
            <section className="space-y-3">
              <div className="flex items-center gap-2">
                <Receipt className="h-4 w-4 text-octo-600" />
                <h2 className="text-sm font-bold text-stone-900">1. 日结对账</h2>
                <span className="ml-auto text-[10px] text-stone-400">原价 → 优惠 → 退款 → 实收</span>
              </div>
              <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white/70">
                <div className="space-y-2 p-3 sm:hidden">
                  {reconciliation.map((r) => (
                    <div key={r.date} className="rounded-xl border border-stone-200 bg-white/80 p-3">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-semibold text-stone-900">{r.date.slice(5)}</p>
                        <p className="text-sm font-bold tabular-nums text-stone-950">实收 ¥{Math.round(r.actual).toLocaleString()}</p>
                      </div>
                      <div className="mt-2 grid grid-cols-3 gap-2 text-[11px]">
                        <div><p className="text-stone-400">订单原价</p><p className="mt-0.5 font-medium text-stone-700">¥{Math.round(r.original).toLocaleString()}</p></div>
                        <div><p className="text-stone-400">优惠/退款</p><p className="mt-0.5 font-medium text-amber-700">-¥{Math.round(r.discount + r.refund).toLocaleString()}</p></div>
                        <div><p className="text-stone-400">订单/客单</p><p className="mt-0.5 font-medium text-stone-700">{r.orders}单 · ¥{r.aovAfter.toFixed(1)}</p></div>
                      </div>
                    </div>
                  ))}
                  {totals && (
                    <div className="flex items-center justify-between rounded-xl bg-stone-900 px-3 py-2.5 text-white">
                      <span className="text-xs">{summary!.entry_count}日合计 · {totals.orders} 单</span>
                      <span className="text-sm font-bold">¥{Math.round(totals.actual).toLocaleString()}</span>
                    </div>
                  )}
                </div>
                <div className="hidden overflow-x-auto sm:block">
                  <table className="w-full text-xs">
                    <thead className="bg-stone-100/70 text-stone-500">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium">日期</th>
                        <th className="px-3 py-2 text-right font-medium">原价</th>
                        <th className="px-3 py-2 text-right font-medium">商户优惠</th>
                        <th className="px-3 py-2 text-right font-medium">退款</th>
                        <th className="px-3 py-2 text-right font-medium">实收</th>
                        <th className="px-3 py-2 text-right font-medium">订单</th>
                        <th className="px-3 py-2 text-right font-medium">客单价</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-100">
                      {reconciliation.map((r) => (
                        <tr key={r.date} className="hover:bg-stone-50/60">
                          <td className="px-3 py-2.5 font-medium text-stone-900">{r.date.slice(5)}</td>
                          <td className="px-3 py-2.5 text-right text-stone-600">¥{Math.round(r.original).toLocaleString()}</td>
                          <td className="px-3 py-2.5 text-right text-amber-600">-¥{Math.round(r.discount).toLocaleString()}</td>
                          <td className="px-3 py-2.5 text-right text-red-600">-¥{Math.round(r.refund).toLocaleString()}{r.refundOrders > 0 ? ` (${r.refundOrders}单)` : ""}</td>
                          <td className="px-3 py-2.5 text-right font-semibold text-stone-900">¥{Math.round(r.actual).toLocaleString()}</td>
                          <td className="px-3 py-2.5 text-right text-stone-600">{r.orders}</td>
                          <td className="px-3 py-2.5 text-right text-stone-600">¥{r.aovAfter.toFixed(1)}</td>
                        </tr>
                      ))}
                      {totals && (
                        <tr className="bg-stone-50/80 font-semibold">
                          <td className="px-3 py-2.5 text-stone-900">合计</td>
                          <td className="px-3 py-2.5 text-right text-stone-900">¥{Math.round(totals.original).toLocaleString()}</td>
                          <td className="px-3 py-2.5 text-right text-amber-700">-¥{Math.round(totals.discount).toLocaleString()}</td>
                          <td className="px-3 py-2.5 text-right text-red-700">-¥{Math.round(totals.refund).toLocaleString()}</td>
                          <td className="px-3 py-2.5 text-right text-stone-900">¥{Math.round(totals.actual).toLocaleString()}</td>
                          <td className="px-3 py-2.5 text-right text-stone-900">{totals.orders}</td>
                          <td className="px-3 py-2.5 text-right text-stone-900">¥{(totals.actual / Math.max(totals.orders, 1)).toFixed(1)}</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </section>

            {/* 2. 资金归属 */}
            <section className="space-y-3">
              <div className="flex items-center gap-2">
                <Wallet className="h-4 w-4 text-octo-600" />
                <h2 className="text-sm font-bold text-stone-900">2. 钱在哪里</h2>
                <span className="ml-auto text-[10px] text-stone-400">销售确认与实际到账分开管理</span>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <SettlementCard
                  label="当前老板名下"
                  value={summary!.settlement_summary.current_owner}
                  hint="线下扫码与收银机现金"
                  tone="good"
                />
                <SettlementCard
                  label="前老板代收待核对"
                  value={summary!.settlement_summary.former_owner}
                  hint="外卖与美团/抖音团购"
                  tone="risk"
                />
                <SettlementCard
                  label="收银机现金"
                  value={summary!.settlement_summary.cash_on_hand}
                  hint="属于收入，但尚未存入账户"
                  tone="watch"
                />
              </div>
              <p className="rounded-xl border border-stone-200 bg-stone-50 px-3 py-2.5 text-xs leading-5 text-stone-600">
                {summary!.settlement_summary.method}
              </p>
            </section>

            {/* 3. 成本与现金口径 */}
            <section className="space-y-3">
              <div className="flex items-center gap-2">
                <Receipt className="h-4 w-4 text-octo-600" />
                <h2 className="text-sm font-bold text-stone-900">3. 成本与现金口径</h2>
                <span className="ml-auto text-[10px] text-stone-400">现金流 ≠ 当期损益</span>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <SettlementCard label="接店投入" value={transferFee} hint="¥40,000进入回本基数，不一次性计入7月成本" tone="watch" />
                <SettlementCard label="已付采购" value={paidPurchases} hint={`${pendingPurchases > 0 ? "仍在途，收货后形成库存资产" : "已形成库存资产"}`} tone="watch" />
                <SettlementCard label="7月房租" value={0} hint="本月不由本店承担" tone="good" />
                <SettlementCard label="8月起月固定" value={monthlyRent + garbageFee} hint={`房租 ¥${monthlyRent.toLocaleString()} + 垃圾费 ¥${garbageFee.toLocaleString()}，未含水电`} tone="risk" />
              </div>
              <p className="rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-2.5 text-xs leading-5 text-amber-900">
                水电尚未确认，食材和包装仍主要是估算值；在实际领用、生产批次和盘点形成闭环前，系统不会确认真实净利或承诺盈利。
              </p>
            </section>

            {/* 4. 利润拆解 */}
            <section className="space-y-3">
              <div className="flex items-center gap-2">
                <Calculator className="h-4 w-4 text-octo-600" />
                <h2 className="text-sm font-bold text-stone-900">4. 利润拆解</h2>
              </div>
              {!profitReady && (
                <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50/70 p-4">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                  <div>
                    <p className="text-sm font-semibold text-amber-950">暂不生成利润结论</p>
                    <p className="mt-1 text-xs leading-5 text-amber-800">
                      {summary!.entry_count}天实际收入已经对账，但食材、包装、人工和水电尚未完整确认；7月房租为0是已知事实。下方只展示收入趋势，避免把估算成本误判为真实利润。
                    </p>
                  </div>
                </div>
              )}
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-stone-200 bg-white/70 p-4">
                  <p className="text-xs font-medium text-stone-500">{profitReady ? "营收 vs 成本 vs 净利" : `${summary!.entry_count}日实际收入趋势`}</p>
                  <div className="mt-3 h-64">
                    <ReactEChartsCore echarts={echarts} option={profitTrendOption} style={{ height: "100%" }} notMerge />
                  </div>
                </div>
                <div className="rounded-2xl border border-stone-200 bg-white/70 p-4">
                  <p className="text-xs font-medium text-stone-500">成本结构占比</p>
                  <div className="mt-3 h-64">
                    {costPieOption ? <ReactEChartsCore echarts={echarts} option={costPieOption} style={{ height: "100%" }} notMerge /> : <div className="flex h-full items-center justify-center text-xs text-stone-400">暂无成本数据</div>}
                  </div>
                </div>
              </div>
              {breakEvenData && (
                <div className="rounded-2xl border border-stone-200 bg-white/70 p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-medium text-stone-500">保本分析</p>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${breakEvenData.is_profitable ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>
                      {breakEvenData.is_profitable ? "已过保本线" : "未过保本线"}
                    </span>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
                    <Metric label="月固定成本" value={`¥${breakEvenData.monthly_fixed_cost.toLocaleString()}`} sub="人工+房租+水电" />
                    <Metric label="变动成本率" value={`${(breakEvenData.variable_cost_rate * 100).toFixed(0)}%`} sub="食材+平台+营销" />
                    <Metric label="日保本营收" value={`¥${breakEvenData.daily_breakeven_revenue?.toLocaleString() ?? "—"}`} sub="基于当前成本" />
                    <Metric label="日均实际营收" value={`¥${breakEvenData.daily_revenue.toLocaleString()}`} sub={`${breakEvenData.gap_to_breakeven !== null ? (breakEvenData.gap_to_breakeven >= 0 ? "+" : "") + "¥" + breakEvenData.gap_to_breakeven.toLocaleString() : ""}`} />
                  </div>
                </div>
              )}
            </section>

            {/* 5. 渠道 */}
            <section className="space-y-3">
              <div className="flex items-center gap-2">
                <ShoppingBag className="h-4 w-4 text-octo-600" />
                <h2 className="text-sm font-bold text-stone-900">5. 渠道</h2>
                {!channelAggregated && <span className="ml-auto text-[10px] text-stone-400">渠道明细待补录</span>}
              </div>
              {channelAggregated ? (
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-2xl border border-stone-200 bg-white/70 p-4">
                    <p className="text-xs font-medium text-stone-500">渠道汇总</p>
                    <div className="mt-3 space-y-2">
                      {channelAggregated.map((c) => (
                        <div key={c.channel} className="flex items-center justify-between rounded-xl bg-stone-50/70 px-3 py-2">
                          <div>
                            <p className="text-sm font-semibold text-stone-900">{c.channel}</p>
                            <p className="text-[10px] text-stone-500">{c.orders} 单 · 原价 ¥{Math.round(c.original).toLocaleString()}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-sm font-semibold text-stone-900">{c.actualKnown ? `¥${Math.round(c.actual).toLocaleString()}` : "实收待拆分"}</p>
                            <p className="text-[10px] text-amber-600">{c.discountRate != null ? `优惠率 ${(c.discountRate * 100).toFixed(1)}%` : "仅有订单金额"}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  {paymentAggregated && (
                    <div className="rounded-2xl border border-stone-200 bg-white/70 p-4">
                      <p className="text-xs font-medium text-stone-500">支付方式</p>
                      <div className="mt-3 space-y-2">
                        {paymentAggregated.slice(0, 6).map((p) => (
                          <div key={p.method} className="flex items-center justify-between rounded-xl bg-stone-50/70 px-3 py-2">
                            <p className="text-sm font-medium text-stone-900">{p.method}</p>
                            <p className="text-xs text-stone-600">{p.orders} 单 · ¥{Math.round(p.amount).toLocaleString()}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-stone-300 bg-white/50 p-6 text-center">
                  <p className="text-sm text-stone-600">渠道 breakdown 数据尚未录入</p>
                  <p className="mt-1 text-xs text-stone-400">上传客如云日报截图后，系统会自动识别堂食/外卖/支付明细</p>
                </div>
              )}
            </section>

            {/* 6. 库存差异 */}
            <section className="space-y-3">
              <div className="flex items-center gap-2">
                <PackageSearch className="h-4 w-4 text-octo-600" />
                <h2 className="text-sm font-bold text-stone-900">6. 库存差异</h2>
                {variance && (
                  <span className="ml-auto text-[10px] text-stone-500">
                    覆盖率 {(variance.verification_coverage * 100).toFixed(0)}% · 差异金额 ¥{variance.total_variance_value.toFixed(0)}
                  </span>
                )}
              </div>
              {variance ? (
                <div className="rounded-2xl border border-stone-200 bg-white/70 p-4">
                  {variance.verification_coverage < 0.3 ? (
                    <div className="flex items-start gap-3 rounded-xl bg-stone-50/70 p-3">
                      <HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-stone-400" />
                      <div>
                        <p className="text-sm font-semibold text-stone-900">暂不可核验</p>
                        <p className="mt-0.5 text-xs text-stone-500">{variance.method}</p>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {variance.rows.filter((r) => r.theoretical_consumption !== null).slice(0, 6).map((r) => (
                        <div key={r.sku_id} className="flex items-center justify-between rounded-xl bg-stone-50/70 px-3 py-2">
                          <div>
                            <p className="text-sm font-semibold text-stone-900">{r.sku_name}</p>
                            <p className="text-[10px] text-stone-500">实际 {r.actual_consumption != null ? `${r.actual_consumption.toFixed(1)}${r.base_unit}` : "不可计算"} · 理论 {r.theoretical_consumption != null ? `${r.theoretical_consumption.toFixed(1)}${r.base_unit}` : "待补"}</p>
                          </div>
                          <span className="rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ backgroundColor: `${STATUS_COLORS[r.verification_status]}20`, color: STATUS_COLORS[r.verification_status] }}>
                            {STATUS_LABELS[r.verification_status]}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="mt-3 flex justify-end">
                    <Link href="/inventory" className="inline-flex items-center gap-1 text-xs font-medium text-octo-600 hover:underline">
                      去库存页查看详情 <ChevronRight className="h-3 w-3" />
                    </Link>
                  </div>
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-stone-300 bg-white/50 p-6 text-center text-xs text-stone-400">库存差异数据加载失败</div>
              )}
            </section>

            {/* 7. 明日动作 */}
            <section className="space-y-3">
              <div className="flex items-center gap-2">
                <ClipboardCheck className="h-4 w-4 text-octo-600" />
                <h2 className="text-sm font-bold text-stone-900">7. 明日动作</h2>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {actions.map((action, i) => (
                  <Link
                    key={i}
                    href={action.href}
                    className={`group flex items-start gap-3 rounded-2xl border p-4 transition-colors hover:bg-white/80 ${
                      action.tone === "risk" ? "border-red-200 bg-red-50/40" :
                      action.tone === "watch" ? "border-amber-200 bg-amber-50/40" :
                      "border-emerald-200 bg-emerald-50/40"
                    }`}
                  >
                    <action.icon className={`mt-0.5 h-4 w-4 shrink-0 ${action.tone === "risk" ? "text-red-500" : action.tone === "watch" ? "text-amber-500" : "text-emerald-500"}`} />
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-stone-900">{action.title}</p>
                      <p className="mt-0.5 text-xs text-stone-600">{action.body}</p>
                    </div>
                    <ArrowRight className="ml-auto h-4 w-4 shrink-0 text-stone-300 transition-colors group-hover:text-stone-500" />
                  </Link>
                ))}
                {actions.length === 0 && (
                  <div className="rounded-2xl border border-stone-200 bg-white/70 p-4 text-center text-xs text-stone-500">暂无明确动作，继续保持记录</div>
                )}
              </div>
            </section>
          </>
        )}
      </div>
    </ModulePage>
  );
}

function HeroKpi({ label, value, sub, tone }: { label: string; value: string; sub: string; tone: "good" | "watch" | "risk" | "info" }) {
  const border = tone === "good" ? "border-emerald-200" : tone === "risk" ? "border-red-200" : tone === "watch" ? "border-amber-200" : "border-stone-200";
  const bg = tone === "good" ? "bg-emerald-50/40" : tone === "risk" ? "bg-red-50/40" : tone === "watch" ? "bg-amber-50/40" : "bg-white/60";
  const dot = tone === "good" ? "bg-emerald-400" : tone === "risk" ? "bg-red-400" : tone === "watch" ? "bg-amber-400" : "bg-stone-400";
  return (
    <div className={`rounded-2xl border ${border} ${bg} px-3 py-2.5`}>
      <p className="text-[10px] text-stone-500">{label}</p>
      <p className="mt-0.5 text-base font-bold text-stone-900">{value}</p>
      <div className="mt-0.5 flex items-center gap-1">
        <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
        <p className="text-[10px] text-stone-500">{sub}</p>
      </div>
    </div>
  );
}

function SettlementCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: number;
  hint: string;
  tone: "good" | "watch" | "risk";
}) {
  const styles = tone === "good"
    ? "border-emerald-200 bg-emerald-50/45"
    : tone === "risk"
      ? "border-red-200 bg-red-50/45"
      : "border-amber-200 bg-amber-50/45";
  return (
    <div className={`rounded-2xl border p-4 ${styles}`}>
      <p className="text-xs font-medium text-stone-600">{label}</p>
      <p className="mt-2 text-xl font-bold tabular-nums text-stone-950">
        ¥{Math.round(value).toLocaleString()}
      </p>
      <p className="mt-1 text-[11px] leading-5 text-stone-500">{hint}</p>
    </div>
  );
}

function MoneyBlock({ title, rows, source }: { title: string; rows: Array<[string, string]>; source: string }) {
  return (
    <div className="min-w-0 rounded-2xl border border-stone-200 bg-stone-50/70 p-4">
      <p className="text-sm font-semibold text-stone-950">{title}</p>
      <div className="mt-3 space-y-2">
        {rows.map(([label, value]) => (
          <div key={label} className="flex min-w-0 items-start justify-between gap-3 rounded-xl bg-white/75 px-3 py-2">
            <p className="min-w-0 text-xs text-stone-500">{label}</p>
            <p className="max-w-[58%] text-right text-xs font-semibold leading-5 text-stone-900">{value}</p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-[11px] leading-5 text-stone-500">{source}</p>
    </div>
  );
}

function Metric({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-xl bg-stone-50/70 px-3 py-2">
      <p className="text-[10px] text-stone-500">{label}</p>
      <p className="mt-0.5 text-sm font-bold text-stone-900">{value}</p>
      <p className="text-[9px] text-stone-400">{sub}</p>
    </div>
  );
}
