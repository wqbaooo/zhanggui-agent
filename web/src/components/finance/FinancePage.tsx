"use client";

// Shared by the daily finance workspace and the four specialist finance routes.

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  AlertTriangle, ArrowDownLeft, ArrowDownToLine, ArrowLeftRight, ArrowUpRight, Banknote, CalendarDays,
  BookOpen, BrainCircuit, Check, ChevronLeft, ChevronRight, CircleDollarSign, ClipboardCheck,
  FileSearch, Images, Landmark, LayoutList, Loader2, MessageCircle, Plus, ReceiptText, RefreshCw,
  MoreHorizontal, Repeat2, ScanLine, Search, Send, ShieldCheck, Sparkles, Upload, X, ZoomIn,
} from "lucide-react";
import { FinanceFundsAnalytics, FinanceIntelligenceDashboard, FinanceProfitAnalytics, FinanceSettlementAnalytics } from "@/components/finance/FinanceAnalyticsPanels";
import {
  confirmBookkeepingRecord, confirmFinanceExecutionPlan, confirmPlatformReport, createBookkeepingRecord, createCashPlanItem, createFinanceIntake,
  DEFAULT_PROJECT_ID, getBookkeepingRecords, getCashChainForecast, getFinanceAnalytics, getFinanceCategories,
  getDailyRevenueChecklist, getPlatformArrivals, matchPlatformBoundCardTransfer, saveDailyRevenue,
  getEvidenceVoucherFileUrl, getEvidenceVouchers, getFinanceAlerts,
  getFinanceDailySnapshot, getFinanceExecutionPlans, getFinanceExportUrl, getFinanceFundAccounts, getFinancePeriodSnapshot,
  getFinanceOverview, getFinanceReconciliationQueue, getPlatformCollectionBindings, getFinanceAgentInsights, getAgentSession, matchFinanceReconciliation, queryFinanceAgent,
  parseFinanceIntakeText, previewPlatformReport, recognizeCapture, reopenFinanceDailyClose, reviewBookkeepingRecord, saveFinanceDailyClose, uploadFinanceStatement,
  savePlatformCollectionBinding,
  type BookkeepingRecordV1, type CashChainForecastV1,
  type DailyFinanceSnapshotV1, type DailyRevenueChecklistV1, type EvidenceVoucherV1, type FinanceAlertV1, type FinanceAnalyticsV1,
  type AgentSessionV1, type FinanceAgentInsightsV1, type FinanceCategoryCatalogV1, type FinanceExecutionPlanV1, type FinanceOverviewV1, type FinanceQueryV1, type FinanceTextParseV1, type FundAccountV1, type PlatformArrivalMatchV1, type PlatformCollectionBindingV1, type PlatformReportPreviewV1, type ReconciliationQueueItemV1,
} from "@/lib/api";

export type FinanceView = "workspace" | "intelligence" | "ledger" | "funds" | "profit" | "reports";
type FinanceRange = "day" | "month" | "since_takeover" | "custom";
type FinanceTool = "settlement" | "reconcile" | "daily";

const STORE_TAKEOVER_DATE = "2026-07-01";
const RANGE_OPTIONS: Array<{ key: FinanceRange; label: string }> = [
  { key: "day", label: "当日" },
  { key: "month", label: "本月累计" },
  { key: "since_takeover", label: "接手至今" },
  { key: "custom", label: "自定义" },
];

const FINANCE_VIEW_META: Record<FinanceView, { label: string; description: string; icon: React.ElementType }> = {
  workspace: { label: "财务总览", description: "围绕一个营业日，完成收入、支出、到账、凭证和日结。", icon: CalendarDays },
  intelligence: { label: "财务智能分析", description: "用真实台账、资金、到账和成本数据，动态判断经营结果与风险。", icon: BrainCircuit },
  ledger: { label: "记账与台账", description: "按期间查询、分类和修正每一笔财务事实。", icon: BookOpen },
  funds: { label: "资金与对账", description: "跟踪平台到账、工商银行、现金与流水核销。", icon: Landmark },
  profit: { label: "成本与利润", description: "按统一期间分析收入、成本完整性和经营结果。", icon: Banknote },
  reports: { label: "凭证与报表", description: "查找原始凭证、查看专业报表并导出工作簿。", icon: FileSearch },
};

function yuan(value: number | null | undefined, fallback = "待核算") {
  return value == null ? fallback : `¥${(value / 100).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateShift(value: string, offset: number) {
  const [year, month, day] = value.split("-").map(Number);
  const current = new Date(Date.UTC(year, month - 1, day));
  current.setUTCDate(current.getUTCDate() + offset);
  return current.toISOString().slice(0, 10);
}

function shanghaiToday() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function analysisStartFor(mode: FinanceRange, cutoffDate: string, customStart: string) {
  if (mode === "day") return cutoffDate;
  if (mode === "month") return `${cutoffDate.slice(0, 7)}-01`;
  if (mode === "since_takeover") return cutoffDate < STORE_TAKEOVER_DATE ? cutoffDate : STORE_TAKEOVER_DATE;
  return customStart && customStart <= cutoffDate ? customStart : cutoffDate;
}

function statusLabel(status: string) {
  return ({
    posted: "已完成", confirmed: "已完成", completed: "已完成", closed: "已关账", open: "待日结", matched: "已对账",
    awaiting_arrival: "已到平台钱包", awaiting_reconciliation: "待转店铺工商卡",
    needs_information: "需要补信息", needs_review: "需要补信息", draft: "需要补信息",
    unmatched: "待对账", partial: "部分到账", pending: "需要补信息", permission_blocked: "权限受限",
  } as Record<string, string>)[status] ?? status;
}

const FINANCE_TERM_LABELS: Record<string, string> = {
  owner_workbook: "店主整理表",
  owner_manual_count: "店主实点",
  keruyun_only: "仅客如云口径",
  fund_movement: "资金流水",
  platform_report: "平台报表",
  settlement_screenshot: "平台结算截图",
  bank_receipt_screenshot: "银行到账截图",
  personal_excluded: "个人支出（不计店铺损益）",
  cash_outflow_pending_accounting_classification: "店铺流出（会计分类待确认）",
  former_owner_transfer: "平台绑定卡周期款转入",
  bank_receipt: "银行到账回单",
  daily_sales: "当日销售",
  daily_close: "当日关账",
};

function financeText(value: string | null | undefined) {
  if (!value) return "";
  return Object.entries(FINANCE_TERM_LABELS).reduce(
    (text, [raw, label]) => text.replaceAll(raw, label),
    value,
  );
}

function isImageFile(filename: string | null | undefined) {
  return Boolean(filename && /\.(png|jpe?g|webp|gif)$/i.test(filename));
}

function flatFinanceCategories(catalog: FinanceCategoryCatalogV1) {
  return catalog.groups.flatMap((group) =>
    group.items.map((item) => ({ ...item, groupKey: group.key, groupName: group.name })),
  );
}

function factTypeForFinanceCategory(category: ReturnType<typeof flatFinanceCategories>[number]) {
  return category.accounting_treatment === "revenue"
    ? "merchant_net_sale"
    : category.key === "former_owner_transfer"
      ? "former_owner_transfer"
      : category.key === "loan_received"
        ? "loan_in"
        : category.key === "loan_principal_repayment"
          ? "loan_repayment"
          : category.key === "owner_investment"
            ? "owner_investment"
            : category.key === "owner_draw"
              ? "owner_draw"
              : category.transaction_kind === "personal_spending"
                ? "personal_spending"
                : category.transaction_kind === "inventory_purchase"
                  ? "inventory_purchase"
                  : category.transaction_kind === "operating_expense"
                    ? "operating_expense"
                    : category.transaction_kind === "platform_settlement"
                      ? "platform_settlement"
                      : "categorized_transaction";
}

function moneyFlowVisual(eventType: string) {
  if (eventType === "sale") return { label: "营业收入", icon: ArrowDownLeft, frame: "border-emerald-200 border-l-emerald-500 bg-emerald-50/35 hover:bg-emerald-50/70", badge: "bg-emerald-100 text-emerald-800", amount: "text-emerald-800", arrow: "text-emerald-500", amountLabel: "收入形成" };
  if (eventType === "receipt") return { label: "资金到账", icon: ArrowDownToLine, frame: "border-sky-200 border-l-sky-500 bg-sky-50/35 hover:bg-sky-50/70", badge: "bg-sky-100 text-sky-800", amount: "text-sky-800", arrow: "text-sky-500", amountLabel: "资金转入" };
  if (eventType === "outflow") return { label: "资金支出", icon: ArrowUpRight, frame: "border-rose-200 border-l-rose-500 bg-rose-50/35 hover:bg-rose-50/70", badge: "bg-rose-100 text-rose-800", amount: "text-rose-800", arrow: "text-rose-500", amountLabel: "资金流出" };
  return { label: "内部流转", icon: Repeat2, frame: "border-violet-200 border-l-violet-500 bg-violet-50/35 hover:bg-violet-50/70", badge: "bg-violet-100 text-violet-800", amount: "text-violet-800", arrow: "text-violet-500", amountLabel: "位置变动" };
}

export function FinancePage({ initialView = "workspace", initialDate = "" }: { initialView?: FinanceView; initialDate?: string }) {
  const view = initialView;
  const viewMeta = FINANCE_VIEW_META[view];
  const [selectedDate, setSelectedDate] = useState(initialDate);
  const [rangeMode, setRangeMode] = useState<FinanceRange>(view === "workspace" ? "day" : "month");
  const [customStart, setCustomStart] = useState(STORE_TAKEOVER_DATE);
  const [financeTool, setFinanceTool] = useState<FinanceTool | null>(null);
  const [overview, setOverview] = useState<FinanceOverviewV1 | null>(null);
  const [snapshot, setSnapshot] = useState<DailyFinanceSnapshotV1 | null>(null);
  const [periodSnapshot, setPeriodSnapshot] = useState<DailyFinanceSnapshotV1 | null>(null);
  const [analytics, setAnalytics] = useState<FinanceAnalyticsV1 | null>(null);
  const [agentInsights, setAgentInsights] = useState<FinanceAgentInsightsV1 | null>(null);
  const [forecast, setForecast] = useState<CashChainForecastV1 | null>(null);
  const [accounts, setAccounts] = useState<FundAccountV1[]>([]);
  const [bookkeeping, setBookkeeping] = useState<BookkeepingRecordV1[]>([]);
  const [vouchers, setVouchers] = useState<EvidenceVoucherV1[]>([]);
  const [reconciliation, setReconciliation] = useState<ReconciliationQueueItemV1[]>([]);
  const [alerts, setAlerts] = useState<FinanceAlertV1[]>([]);
  const [pendingPlans, setPendingPlans] = useState<FinanceExecutionPlanV1[]>([]);
  const [collectionBindings, setCollectionBindings] = useState<PlatformCollectionBindingV1[]>([]);
  const [dailyChecklist, setDailyChecklist] = useState<DailyRevenueChecklistV1 | null>(null);
  const [categories, setCategories] = useState<FinanceCategoryCatalogV1 | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [entryOpen, setEntryOpen] = useState(false);
  const [intakeOpen, setIntakeOpen] = useState(false);
  const [intakeCategoryGroup, setIntakeCategoryGroup] = useState<string | null>(null);
  const [editing, setEditing] = useState<BookkeepingRecordV1 | null>(null);
  const [agentOpen, setAgentOpen] = useState(false);
  const [agentPrompt, setAgentPrompt] = useState("");
  const loadSequence = useRef(0);

  async function load(date?: string, requestedRange = rangeMode, requestedCustomStart = customStart) {
    const requestId = ++loadSequence.current;
    setLoading(true);
    setError(null);
    try {
      const target = date || selectedDate || shanghaiToday();
      const analysisStart = analysisStartFor(requestedRange, target, requestedCustomStart);
      const finance = await getFinanceOverview(DEFAULT_PROJECT_ID, analysisStart, target);
      const day = await getFinanceDailySnapshot(target);
      const monthStart = `${target.slice(0, 7)}-01`;
      const [cash, period, analysis, insightResult, accountResult, recordResult, voucherResult, matchResult, alertResult, planResult, bindingResult, checklistResult] = await Promise.all([
        getCashChainForecast(target),
        getFinancePeriodSnapshot(analysisStart, target),
        getFinanceAnalytics(analysisStart, target),
        getFinanceAgentInsights(target),
        getFinanceFundAccounts(target),
        getBookkeepingRecords(analysisStart, target),
        getEvidenceVouchers(analysisStart, target),
        getFinanceReconciliationQueue(analysisStart, target),
        getFinanceAlerts(DEFAULT_PROJECT_ID, analysisStart, target),
        getFinanceExecutionPlans(),
        getPlatformCollectionBindings(target),
        getDailyRevenueChecklist(monthStart, target),
      ]);
      if (requestId !== loadSequence.current) return;
      setOverview(finance);
      setSnapshot(day);
      setPeriodSnapshot(period);
      setForecast(cash);
      setAnalytics(analysis);
      setAgentInsights(insightResult);
      setAccounts(accountResult.accounts);
      setBookkeeping(recordResult.rows);
      setVouchers(voucherResult.rows);
      setReconciliation(matchResult.rows);
      setAlerts(alertResult.alerts);
      setPendingPlans(planResult.rows);
      setCollectionBindings(bindingResult.rows);
      setDailyChecklist(checklistResult);
      setSelectedDate(target);
      try {
        const categoryResult = await getFinanceCategories();
        if (requestId !== loadSequence.current) return;
        setCategories(categoryResult);
      } catch {
        if (requestId !== loadSequence.current) return;
        setCategories(null);
        setError("台账、资金和利润数据已加载，但录入分类服务尚未同步。请重启后端后刷新；现有账目不会丢失。");
      }
    } catch (cause) {
      if (requestId === loadSequence.current) setError(cause instanceof Error ? cause.message : "财务系统加载失败");
    } finally {
      if (requestId === loadSequence.current) setLoading(false);
    }
  }

  useEffect(() => { void load(initialDate || shanghaiToday(), view === "workspace" ? "day" : "month"); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const storeAccounts = accounts.filter((item) => item.status === "active");
  const entryAccounts = storeAccounts.filter((item) => ["store", "owner"].includes(item.owner_kind) && item.account_kind !== "platform_wallet");
  const pendingCount = bookkeeping.filter((item) => item.status === "needs_review" || item.status === "draft").length + pendingPlans.length;
  const totalAnalysisDays = analytics?.daily_series.length ?? 0;
  const recordedAnalysisDays = analytics?.daily_series.filter((item) => item.state !== "missing").length ?? 0;
  const pendingSettlementCount = analytics?.settlement_timeline.filter((item) => item.status !== "completed").length ?? 0;
  const isPeriodScope = Boolean(periodSnapshot && periodSnapshot.scope_kind === "period");
  const detailRangeLabel = periodSnapshot
    ? periodSnapshot.scope_kind === "day" ? periodSnapshot.period_end : `${periodSnapshot.period_start} 至 ${periodSnapshot.period_end}`
    : "—";

  async function changeDate(date: string) {
    setSelectedDate(date);
    await load(date, rangeMode, customStart);
  }

  async function changeRange(mode: FinanceRange, start = customStart) {
    setRangeMode(mode);
    await load(selectedDate || shanghaiToday(), mode, start);
  }

  async function confirmRecord(recordId: string) {
    setWorking(true);
    setError(null);
    try {
      await confirmBookkeepingRecord(recordId);
      setNotice("这笔流水已写入资金账；只有满足会计条件的项目才同步生成分录。");
      await load(selectedDate);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "确认入账失败");
    } finally {
      setWorking(false);
    }
  }

  async function resumePlan(planId: string) {
    setWorking(true);
    setError(null);
    try {
      await confirmFinanceExecutionPlan(planId);
      setNotice("已按原始凭证和你之前确认的字段记入，资金、台账和凭证已同步。");
      await load(selectedDate);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "继续记入失败");
    } finally {
      setWorking(false);
    }
  }

  function openAgent(question = "") {
    setAgentPrompt(question);
    setAgentOpen(true);
  }

  function openIntake(categoryGroup: string | null = null) {
    setIntakeCategoryGroup(categoryGroup);
    setIntakeOpen(true);
  }

  const ViewIcon = viewMeta.icon;
  const reduceMotion = useReducedMotion();

  return (
    <main className="finance-shell mx-auto flex w-full max-w-[1600px] flex-col gap-5 pb-10">
      <div className="space-y-4">
        <motion.section layout={!reduceMotion} initial={reduceMotion ? false : { opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .28, ease: [0.22, 1, 0.36, 1] }} className="finance-command-bar sticky top-0 z-30">
          <div className="flex flex-col gap-3">
            <div className="flex min-w-0 items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-3">
                <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center text-octo-700"><ViewIcon className="h-[18px] w-[18px]" /></span>
                <div className="min-w-0">
                  <h1 className="text-[19px] font-semibold tracking-[-0.02em] text-stone-950">财务中心</h1>
                  <p className="mt-1 text-[13px] leading-5 text-stone-500"><span className="font-medium text-stone-700">{viewMeta.label}</span><span className="mx-1.5 text-stone-300">·</span>{viewMeta.description}</p>
                </div>
              </div>
              {view === "workspace" && pendingCount > 0 && <span className="finance-status finance-status-warning shrink-0">{pendingCount} 项待处理</span>}
            </div>
            <div className="flex flex-wrap items-center gap-2 border-t border-stone-100 pt-3">
              {view !== "workspace" && <div className="flex min-h-10 flex-wrap items-center gap-1 rounded-lg bg-stone-100 p-1" aria-label="财务分析范围">
                {RANGE_OPTIONS.map((item) => <button key={item.key} type="button" onClick={() => void changeRange(item.key)} className={`relative min-h-8 overflow-hidden rounded-md px-3 text-[11px] font-semibold transition ${rangeMode === item.key ? "text-stone-950" : "text-stone-500 hover:text-stone-800"}`}>{rangeMode === item.key && <motion.span layoutId="finance-range-active" transition={reduceMotion ? { duration: 0 } : { type: "spring", stiffness: 480, damping: 38 }} className="absolute inset-0 rounded-md bg-white shadow-sm" />}<span className="relative z-10">{item.label}</span></button>)}
              </div>}
              {view !== "workspace" && rangeMode === "custom" && <label className="flex min-h-10 items-center gap-2 rounded-lg border border-stone-200 bg-white px-3 text-xs text-stone-600"><span>起始</span><input aria-label="累计分析起始日期" type="date" max={selectedDate || shanghaiToday()} value={customStart} onChange={(event) => { setCustomStart(event.target.value); void changeRange("custom", event.target.value); }} className="bg-transparent font-semibold text-stone-900 outline-none" /></label>}
              <span className={`${view === "workspace" ? "" : "ml-auto"} text-xs font-medium text-stone-500`}>{view === "workspace" ? "营业日" : "分析截至"}</span>
              <button aria-label="前一天" onClick={() => void changeDate(dateShift(selectedDate, -1))} disabled={!selectedDate} className="grid h-10 w-10 place-items-center rounded-lg border border-stone-200 text-stone-600 hover:bg-stone-50 disabled:opacity-40"><ChevronLeft className="h-4 w-4" /></button>
              <label className="flex min-h-10 items-center gap-2 rounded-lg border border-stone-200 bg-white px-3 text-xs text-stone-600"><CalendarDays className="h-4 w-4 text-octo-700" /><input aria-label={view === "workspace" ? "营业日" : "财务分析截至日期"} type="date" max={shanghaiToday()} value={selectedDate} onChange={(event) => void changeDate(event.target.value)} className="bg-transparent font-semibold text-stone-900 outline-none" /></label>
              <button aria-label="后一天" onClick={() => void changeDate(dateShift(selectedDate, 1))} disabled={!selectedDate || selectedDate >= shanghaiToday()} className="grid h-10 w-10 place-items-center rounded-lg border border-stone-200 text-stone-600 hover:bg-stone-50 disabled:opacity-40"><ChevronRight className="h-4 w-4" /></button>
              <button onClick={() => void changeDate(shanghaiToday())} className="min-h-10 rounded-lg border border-stone-200 px-3 text-xs font-semibold text-stone-700 hover:bg-stone-50">回到今天</button>
              <button aria-label="刷新财务数据" onClick={() => void load(selectedDate)} className="group grid h-10 w-10 place-items-center rounded-lg border border-stone-200 text-stone-600 transition hover:border-octo-200 hover:bg-octo-50 hover:text-octo-800"><RefreshCw className="h-4 w-4 transition-transform duration-300 group-active:rotate-180" /></button>
              <button onClick={() => openAgent()} className="finance-button-quiet ml-auto"><MessageCircle className="h-4 w-4" />问财务</button>
              <motion.button whileHover={reduceMotion ? undefined : { y: -1 }} whileTap={reduceMotion ? undefined : { scale: .985 }} disabled={!categories} title={categories ? "智能识别并一次确认入账" : "分类服务尚未同步，暂不能录入"} onClick={() => openIntake()} className="finance-button-primary"><Sparkles className="h-4 w-4" />智能录入</motion.button>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-stone-100 pt-3 text-xs text-stone-500">
            <span>最新数据日期：<strong className="text-stone-800">{snapshot?.latest_data_date ?? "暂无"}</strong></span>
            {view === "workspace" ? <>
              <span>当前营业日：<strong className="text-stone-800">{selectedDate || "—"}</strong></span>
              <span className={snapshot?.data_state === "missing" ? "font-semibold text-amber-700" : "text-emerald-700"}>{snapshot?.data_state === "missing" ? "当日尚未录入，不按0处理" : "当日已存在财务事实"}</span>
            </> : <>
              <span>明细范围：<strong className="text-stone-800">{detailRangeLabel}</strong></span>
              <span>累计分析：<strong className="text-stone-800">{analytics ? `${analytics.period_start} 至 ${analytics.period_end}` : "—"}</strong></span>
              {analytics && <span><strong className="text-stone-800">{recordedAnalysisDays}</strong> 个有记录日 / {totalAnalysisDays} 个自然日{analytics.missing_days.length > 0 ? `，缺 ${analytics.missing_days.length} 天` : "，资料连续"}</span>}
              <span className={snapshot?.data_state === "missing" ? "font-semibold text-amber-700" : "text-emerald-700"}>{snapshot?.data_state === "missing" ? isPeriodScope ? "截止日尚未录入，期间明细仍按事实展示" : "当日尚未录入，不按0处理" : isPeriodScope ? "期间明细已按所选范围汇总" : "当日存在已登记财务事实"}</span>
            </>}
          </div>
        </motion.section>

        <AnimatePresence initial={false} mode="popLayout">
          {loading && <motion.div key="finance-loading" initial={reduceMotion ? false : { opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={reduceMotion ? undefined : { opacity: 0, y: -4 }} className="flex min-h-20 items-center justify-center gap-2 rounded-xl border border-stone-200 bg-white text-sm text-stone-500"><Loader2 className="h-4 w-4 animate-spin" />正在重算资金、利润与对账状态…</motion.div>}
          {error && <motion.div key="finance-error" initial={reduceMotion ? false : { opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={reduceMotion ? undefined : { opacity: 0 }} className="flex items-start justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"><span className="break-words">{error}</span><button onClick={() => setError(null)} aria-label="关闭错误"><X className="h-4 w-4" /></button></motion.div>}
          {notice && <motion.div key="finance-notice" initial={reduceMotion ? false : { opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={reduceMotion ? undefined : { opacity: 0 }} className="flex items-start justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900"><span>{notice}</span><button onClick={() => setNotice(null)} aria-label="关闭提示"><X className="h-4 w-4" /></button></motion.div>}
        </AnimatePresence>

        {!loading && (["intelligence", "profit", "reports"] as FinanceView[]).includes(view) && <FinanceAnalysisSubnav view={view} selectedDate={selectedDate} />}

        {!loading && view === "workspace" && snapshot && overview && <DailyFinanceHub snapshot={snapshot} overview={overview} voucherCount={vouchers.length} pendingSettlementCount={pendingSettlementCount} selectedDate={selectedDate} onDailyClose={() => setFinanceTool("daily")} />}
        {!loading && view === "workspace" && dailyChecklist && <DailyRevenueWorkspace checklist={dailyChecklist} selectedDate={selectedDate} working={working} onSaved={async (message) => { setNotice(message); await load(selectedDate); }} onError={setError} setWorking={setWorking} />}
        {!loading && view === "workspace" && categories && <FinanceQuickEntry selectedDate={selectedDate} categories={categories} onChooseCategory={openIntake} onImportStatement={() => setFinanceTool("reconcile")} />}
        {!loading && view === "workspace" && pendingPlans.length > 0 && <div id="pending"><PendingPlans plans={pendingPlans} vouchers={vouchers} accounts={accounts} working={working} onResume={(id) => void resumePlan(id)} onEdit={() => openIntake()} /></div>}
        {!loading && view === "intelligence" && analytics && snapshot && overview && <FinanceIntelligenceDashboard analytics={analytics} snapshot={snapshot} overview={overview} agentInsights={agentInsights} voucherCount={vouchers.length} onAsk={openAgent} />}
        {!loading && view === "ledger" && periodSnapshot && <LedgerWorkspace key={`ledger-${periodSnapshot.period_start}-${periodSnapshot.period_end}`} snapshot={periodSnapshot} working={working} onNew={() => openIntake()} onEdit={(record) => { setEditing(record); setEntryOpen(true); }} onConfirm={(id) => void confirmRecord(id)} />}
        {!loading && view === "funds" && snapshot && forecast && overview && analytics && <div className="space-y-4">
          <FinanceTaskHub pendingSettlementCount={pendingSettlementCount} reconciliationCount={reconciliation.length} dailyCloseStatus={snapshot.daily_close.status} onOpen={setFinanceTool} />
          <FinanceFundsAnalytics analytics={analytics} onAsk={openAgent} />
        </div>}
        {!loading && view === "profit" && analytics && <FinanceProfitAnalytics analytics={analytics} onAsk={openAgent} />}
        {!loading && view === "reports" && overview && snapshot && <div className="space-y-4"><ReportsView overview={overview} snapshot={snapshot} /><VoucherView key={`vouchers-${overview.period_start}-${overview.period_end}`} vouchers={vouchers} periodStart={overview.period_start} periodEnd={overview.period_end} /><ExportPanel overview={overview} /></div>}

        {entryOpen && categories && <EntryDialog selectedDate={selectedDate} accounts={entryAccounts} categories={categories} records={bookkeeping} editing={editing} working={working} onClose={() => { setEntryOpen(false); setEditing(null); }} onSaved={async (message) => { setNotice(message); setEntryOpen(false); setEditing(null); await load(selectedDate); }} onError={setError} setWorking={setWorking} />}
        {intakeOpen && categories && <FinanceIntakeDialog selectedDate={selectedDate} accounts={entryAccounts} categories={categories} initialCategoryGroup={intakeCategoryGroup} onClose={() => setIntakeOpen(false)} onSaved={async (message) => { setNotice(message); setIntakeOpen(false); await load(selectedDate); }} onError={setError} />}
        <AnimatePresence>{agentOpen && overview && <FinanceAgentDrawer key="finance-agent-drawer" overview={overview} selectedDate={selectedDate} initialQuery={agentPrompt} onFinanceChanged={() => load(selectedDate)} onClose={() => setAgentOpen(false)} />}</AnimatePresence>
        {financeTool && snapshot && forecast && analytics && <FinanceToolDrawer title={financeTool === "settlement" ? "平台到账与收款路径" : financeTool === "reconcile" ? "流水导入与逐笔对账" : "截止日日结与资金计划"} detail={financeTool === "daily" ? `截至日期 ${selectedDate}` : `${analytics.period_start} 至 ${analytics.period_end}`} onClose={() => setFinanceTool(null)}>
          {financeTool === "settlement" && <div className="space-y-4"><WeeklyPlatformTransferPanel selectedDate={selectedDate} onSaved={async (message) => { setNotice(message); await load(selectedDate); }} onError={setError} /><FinanceSettlementAnalytics analytics={analytics} onAsk={openAgent} /><PlatformCollectionPanel selectedDate={selectedDate} bindings={collectionBindings} accounts={accounts} onSaved={async () => { setNotice("平台收款路径已按生效日更新；历史流水和旧路径均已保留。"); await load(selectedDate); }} onError={setError} /></div>}
          {financeTool === "reconcile" && <ReconciliationView accounts={storeAccounts} queue={reconciliation} periodStart={analytics.period_start} periodEnd={analytics.period_end} working={working} onUploaded={async (message) => { setNotice(message); await load(selectedDate); }} onMatched={async (item, candidate) => { setWorking(true); try { await matchFinanceReconciliation(item.record.id, { target_type: candidate.target_type, target_id: candidate.id, matched_amount: candidate.suggested_match_minor / 100 }); setNotice("对账关系已确认；不会重复增加营业收入。"); await load(selectedDate); } catch (cause) { setError(cause instanceof Error ? cause.message : "对账失败"); } finally { setWorking(false); } }} />}
          {financeTool === "daily" && <CockpitView snapshot={snapshot} forecast={forecast} alerts={alerts} onRefresh={() => void load(selectedDate)} />}
        </FinanceToolDrawer>}
      </div>
    </main>
  );
}

export default function ProfitPage() {
  return <FinancePage />;
}

function FinanceAnalysisSubnav({ view, selectedDate }: { view: FinanceView; selectedDate: string }) {
  const reduceMotion = useReducedMotion();
  const items: Array<{ key: FinanceView; href: string; label: string; icon: React.ElementType }> = [
    { key: "intelligence", href: "/finance/intelligence", label: "智能分析", icon: BrainCircuit },
    { key: "profit", href: "/finance/profit", label: "成本与利润", icon: Banknote },
    { key: "reports", href: "/finance/reports", label: "凭证与报表", icon: ReceiptText },
  ];
  return <nav aria-label="分析与报表视图" className="flex w-fit items-center gap-1 rounded-xl border border-stone-200 bg-white p-1 shadow-[0_4px_16px_rgba(72,52,40,.04)]">
    {items.map((item) => {
      const Icon = item.icon;
      const active = item.key === view;
      return <Link key={item.key} href={`${item.href}?date=${selectedDate}`} className={`relative flex min-h-9 items-center gap-2 overflow-hidden rounded-lg px-3.5 text-xs font-semibold transition-colors ${active ? "text-octo-900" : "text-stone-500 hover:bg-stone-50 hover:text-stone-800"}`}>
        {active && <motion.span layoutId="finance-analysis-subnav" transition={reduceMotion ? { duration: 0 } : { type: "spring", stiffness: 460, damping: 36 }} className="absolute inset-0 rounded-lg bg-octo-50 ring-1 ring-inset ring-octo-100" />}
        <Icon className={`relative z-10 h-3.5 w-3.5 ${active ? "text-octo-700" : "text-stone-400"}`} />
        <span className="relative z-10">{item.label}</span>
      </Link>;
    })}
  </nav>;
}

function DailyFinanceHub({ snapshot, overview, voucherCount, pendingSettlementCount, selectedDate, onDailyClose }: {
  snapshot: DailyFinanceSnapshotV1;
  overview: FinanceOverviewV1;
  voucherCount: number;
  pendingSettlementCount: number;
  selectedDate: string;
  onDailyClose: () => void;
}) {
  const reduceMotion = useReducedMotion();
  const costMinor = Object.values(snapshot.day_activity.costs_minor).reduce((sum, value) => sum + value, 0);
  const closeDone = snapshot.daily_close.status === "closed";
  const rows = [
    { href: `/finance/ledger?date=${selectedDate}`, icon: BookOpen, label: "当日台账", value: `${snapshot.ledger_entries.length}笔`, detail: `店铺流出 ${yuan(snapshot.day_activity.store_outflow_minor, "¥0.00")}` },
    { href: `/finance/funds?date=${selectedDate}`, icon: Landmark, label: "到账与资金", value: pendingSettlementCount > 0 ? `${pendingSettlementCount}笔待跟进` : "当日无待办", detail: `账面可追溯资金 ${yuan(snapshot.as_of.store_controlled_minor)}` },
    { href: `/finance/profit?date=${selectedDate}`, icon: Banknote, label: "当日营业与成本", value: yuan(snapshot.day_activity.merchant_net_minor, "收入待录"), detail: costMinor > 0 ? `已确认成本 ${yuan(costMinor)}` : "当日成本待补充" },
    { href: `/finance/reports?date=${selectedDate}`, icon: ReceiptText, label: "凭证与报表", value: `${voucherCount}份凭证`, detail: voucherCount > 0 ? "原图已按事实日期关联" : "当日还没有凭证" },
  ];
  return <motion.section initial={reduceMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .3, ease: [0.22, 1, 0.36, 1] }} className="finance-surface overflow-hidden">
    <div className="flex items-center justify-between border-b border-stone-200/80 px-5 py-4">
      <div><SectionTitle icon={ArrowLeftRight} title="当日账务进度" detail={selectedDate} /><p className="mt-1.5 text-[13px] text-stone-500">以当前营业日为主线，进入明细时会自动带上这个日期。</p></div>
      <span className={`finance-status ${closeDone ? "finance-status-success" : "finance-status-warning"}`}>{closeDone ? "已完成日结" : "等待日结"}</span>
    </div>
    <div className="finance-day-rail grid grid-cols-4">{rows.map((item, index) => { const Icon = item.icon; return <Link key={item.href} href={item.href} className="group relative min-w-0 px-5 py-4 outline-none transition-colors duration-200 hover:bg-[#fffaf6] focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-octo-400">
      {index < rows.length - 1 && <span className="absolute right-0 top-4 h-[calc(100%-2rem)] w-px bg-stone-200" />}
      <span className="flex items-center gap-2.5"><Icon className="h-4 w-4 shrink-0 text-stone-400 transition-colors group-hover:text-octo-700" /><strong className="text-[13px] font-medium text-stone-700">{item.label}</strong><ChevronRight className="ml-auto h-4 w-4 text-stone-300 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-octo-600" /></span>
      <span className="mt-3 block truncate text-xl font-semibold tracking-[-0.02em] tabular-nums text-stone-950">{item.value}</span>
      <span className="mt-1.5 block truncate text-xs text-stone-500">{item.detail}</span>
    </Link>; })}</div>
    <div className="flex items-center justify-between gap-5 border-t border-stone-200/80 bg-[#fbfaf8] px-5 py-3.5">
      <div className="flex min-w-0 items-center gap-3"><span className={`h-2 w-2 shrink-0 rounded-full ${closeDone ? "bg-emerald-500" : "bg-amber-500"}`} /><div className="min-w-0"><p className="text-[13px] font-medium text-stone-800">{closeDone ? "这一天已经完成核对" : "录完营业与支出后即可日结"}</p><p className="mt-0.5 truncate text-xs text-stone-500">{closeDone ? "后续修正会保留调整记录。" : `营业收入 ${yuan(overview.revenue_minor, "待录")} · 个人资金流出 ${yuan(snapshot.day_activity.personal_outflow_minor, "¥0.00")}`}</p></div></div>
      <motion.button type="button" onClick={onDailyClose} whileHover={reduceMotion ? undefined : { x: 2 }} whileTap={reduceMotion ? undefined : { scale: .985 }} className="finance-button-secondary">{closeDone ? "查看日结" : "去完成日结"}<ChevronRight className="h-4 w-4" /></motion.button>
    </div>
  </motion.section>;
}

function FinanceTaskHub({ pendingSettlementCount, reconciliationCount, dailyCloseStatus, onOpen }: {
  pendingSettlementCount: number;
  reconciliationCount: number;
  dailyCloseStatus: string;
  onOpen: (tool: FinanceTool) => void;
}) {
  const tasks: Array<{ key: FinanceTool; icon: React.ElementType; title: string; detail: string; badge: string; tone: string }> = [
    { key: "settlement", icon: Landmark, title: "平台到账", detail: "查看 T+N 账期、绑定卡与店铺工商卡", badge: pendingSettlementCount > 0 ? `${pendingSettlementCount} 笔待跟进` : "本期已跟进", tone: pendingSettlementCount > 0 ? "text-amber-800 bg-amber-50" : "text-emerald-800 bg-emerald-50" },
    { key: "reconcile", icon: ArrowLeftRight, title: "流水对账", detail: "导入银行流水并核销对应交易", badge: reconciliationCount > 0 ? `${reconciliationCount} 笔待对账` : "暂无待对账", tone: reconciliationCount > 0 ? "text-amber-800 bg-amber-50" : "text-stone-600 bg-stone-100" },
    { key: "daily", icon: ClipboardCheck, title: "截止日日结", detail: "核对截止日期当天，并登记未来收付", badge: statusLabel(dailyCloseStatus), tone: dailyCloseStatus === "closed" ? "text-emerald-800 bg-emerald-50" : "text-sky-800 bg-sky-50" },
  ];
  return <section className="finance-surface overflow-hidden">
    <div className="border-b border-stone-200/80 px-5 py-4"><h2 className="text-[15px] font-semibold text-stone-950">资金待办</h2><p className="mt-1 text-[13px] text-stone-500">只展示需要采取动作的事项，点击后在当前页面打开。</p></div>
    <div className="grid grid-cols-3 divide-x divide-stone-200">{tasks.map((item) => { const Icon = item.icon; return <button key={item.key} type="button" onClick={() => onOpen(item.key)} className="group flex min-h-[92px] items-center gap-3 px-5 py-4 text-left transition-colors duration-200 hover:bg-[#fffaf6]"><Icon className="h-[18px] w-[18px] shrink-0 text-stone-400 transition-colors group-hover:text-octo-700" /><span className="min-w-0 flex-1"><span className="flex items-center justify-between gap-2"><strong className="text-[13px] font-medium text-stone-900">{item.title}</strong><span className={`rounded-full px-2.5 py-1 text-xs font-medium ${item.tone}`}>{item.badge}</span></span><span className="mt-1.5 block truncate text-xs text-stone-500">{item.detail}</span></span><ChevronRight className="h-4 w-4 shrink-0 text-stone-300 transition-transform group-hover:translate-x-0.5 group-hover:text-octo-700" /></button>; })}</div>
  </section>;
}

function FinanceToolDrawer({ title, detail, onClose, children }: { title: string; detail: string; onClose: () => void; children: React.ReactNode }) {
  return <div className="fixed inset-0 z-50 flex justify-end bg-stone-950/30 backdrop-blur-[1px]" role="dialog" aria-modal="true" aria-label={title} onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="animate-slide-in-right flex h-full w-full max-w-5xl flex-col bg-stone-50 shadow-2xl">
      <header className="flex min-h-16 items-center justify-between gap-3 border-b border-stone-200 bg-white px-4 sm:px-6"><div className="min-w-0"><h2 className="truncate text-sm font-bold text-stone-950">{title}</h2><p className="mt-0.5 text-[10px] text-stone-500">{detail}</p></div><button type="button" aria-label={`关闭${title}`} onClick={onClose} className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-stone-200 text-stone-600 hover:bg-stone-100"><X className="h-4 w-4" /></button></header>
      <div className="min-h-0 flex-1 overflow-y-auto p-3 sm:p-5">{children}</div>
    </div>
  </div>;
}

function CockpitView({ snapshot, forecast, alerts, onRefresh }: { snapshot: DailyFinanceSnapshotV1; forecast: CashChainForecastV1; alerts: FinanceAlertV1[]; onRefresh: () => void }) {
  const [planOpen, setPlanOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ due_date: snapshot.selected_date, flow_type: "required_outflow" as "required_outflow" | "expected_inflow", amount: "", category: "", counterparty: "", priority: "must_pay" as "must_pay" | "expected" | "optional" });
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setSaving(true);
    try {
      await createCashPlanItem({ ...form, amount: Number(form.amount), source_reference: `manual-plan-${Date.now()}` });
      setPlanOpen(false); setForm({ ...form, amount: "", category: "", counterparty: "" }); onRefresh();
    } finally { setSaving(false); }
  }
  return <div className="space-y-4">
    {forecast.status === "at_risk" && <section className="flex flex-col gap-3 rounded-xl border border-red-300 bg-red-50 p-4 sm:flex-row sm:items-center sm:justify-between"><div className="flex gap-3"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-700" /><div><p className="text-sm font-bold text-red-950">预计 {forecast.first_risk_date} 出现资金缺口</p><p className="mt-1 text-xs leading-5 text-red-800">已登记的必须付款将使可控资金低于安全备用金。请优先确认预计到账、付款日期和可延后项目。</p></div></div><button onClick={() => setPlanOpen(true)} className="min-h-10 shrink-0 rounded-lg bg-red-800 px-4 text-xs font-semibold text-white">补充资金计划</button></section>}
    {forecast.status === "partial" && <section className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" /><div><p className="text-sm font-bold text-amber-950">资金预测尚不完整</p><p className="mt-1 text-xs leading-5 text-amber-800">{forecast.blocking_reasons.includes("future_receipts_and_obligations_missing") ? "还没有登记未来工资、房租、进货、还款和预计到账，当前不能判断资金链是否安全。" : "店铺专用账户或期初余额仍需补充。"}</p></div></section>}
    <section className="grid gap-4 xl:grid-cols-[1.15fr_.85fr]">
      <div className="rounded-xl border border-stone-200 bg-white p-4">
        <div className="flex items-center justify-between"><SectionTitle icon={ShieldCheck} title="7 / 14 / 30 天资金安全" detail="按已登记未来收付" /><button onClick={() => setPlanOpen((value) => !value)} className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-stone-200 px-3 text-xs font-semibold text-stone-700"><Plus className="h-3.5 w-3.5" />计划收付</button></div>
        <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[560px] text-left text-xs"><thead className="text-stone-500"><tr className="border-b border-stone-200"><th className="pb-2 font-medium">周期</th><th className="pb-2 text-right font-medium">预计到账</th><th className="pb-2 text-right font-medium">必须付款</th><th className="pb-2 text-right font-medium">预计余额</th><th className="pb-2 text-right font-medium">缺口</th></tr></thead><tbody>{forecast.horizons.map((row) => <tr key={row.days} className="border-b border-stone-100 last:border-0"><td className="py-3 font-semibold text-stone-900">未来 {row.days} 天<br/><span className="font-normal text-stone-400">至 {row.through_date}</span></td><td className="py-3 text-right text-emerald-700">{yuan(row.expected_inflow_minor, "¥0.00")}</td><td className="py-3 text-right text-stone-700">{yuan(row.required_outflow_minor, "¥0.00")}</td><td className={`py-3 text-right font-bold ${row.ending_minor < forecast.safety_reserve_minor ? "text-red-700" : "text-stone-950"}`}>{yuan(row.ending_minor)}</td><td className="py-3 text-right font-semibold text-red-700">{row.shortfall_minor ? yuan(row.shortfall_minor) : "—"}</td></tr>)}</tbody></table></div>
        {planOpen && <form onSubmit={submit} className="mt-4 grid gap-3 border-t border-stone-100 pt-4 sm:grid-cols-2 lg:grid-cols-3"><FormInput type="date" label="日期" value={form.due_date} onChange={(value) => setForm({ ...form, due_date: value })} /><FormSelect label="类型" value={form.flow_type} onChange={(value) => setForm({ ...form, flow_type: value as typeof form.flow_type })} options={[{ value: "required_outflow", label: "必须付款" }, { value: "expected_inflow", label: "预计到账" }]} /><FormInput label="金额" type="number" value={form.amount} onChange={(value) => setForm({ ...form, amount: value })} /><FormInput label="项目" value={form.category} onChange={(value) => setForm({ ...form, category: value })} placeholder="工资、房租、进货…" /><FormInput label="对方" value={form.counterparty} onChange={(value) => setForm({ ...form, counterparty: value })} /><button disabled={saving || !form.amount || !form.category} className="min-h-10 self-end rounded-lg bg-octo-700 px-4 text-xs font-semibold text-white disabled:opacity-40">{saving ? "保存中…" : "加入资金计划"}</button></form>}
      </div>
      <div className="rounded-xl border border-stone-200 bg-white p-4"><SectionTitle icon={Banknote} title="钱现在在哪里" detail="截至所选日期" /><div className="mt-4 space-y-2">{snapshot.as_of.fund_positions.filter((item) => item.balance_minor !== 0 || item.status === "planned").map((item) => <div key={item.id} className="flex items-center justify-between gap-3 border-b border-stone-100 py-2 last:border-0"><div className="min-w-0"><p className="truncate text-xs font-semibold text-stone-800">{item.name}</p><p className="mt-0.5 text-[10px] text-stone-400">{item.is_store_controlled ? "店铺可控" : "平台/前老板/个人账户，待核位置"}</p></div><strong className={`shrink-0 text-sm tabular-nums ${item.is_store_controlled ? "text-stone-950" : "text-amber-800"}`}>{yuan(item.balance_minor)}</strong></div>)}</div></div>
    </section>
    <DailyClosePanel snapshot={snapshot} onSaved={onRefresh} />
    {forecast.timeline.length > 0 && <section className="rounded-xl border border-stone-200 bg-white p-4"><SectionTitle icon={CalendarDays} title="未来收付日历" detail={`${forecast.timeline.length}项`} /><div className="mt-3 divide-y divide-stone-100">{forecast.timeline.map((item) => <div key={item.id} className="grid gap-2 py-3 text-xs sm:grid-cols-[90px_1fr_auto_auto]"><span className="font-semibold text-stone-700">{item.due_date}</span><span className="text-stone-700">{item.category}{item.counterparty ? ` · ${item.counterparty}` : ""}</span><span className={item.flow_type === "expected_inflow" ? "font-semibold text-emerald-700" : "font-semibold text-red-700"}>{item.flow_type === "expected_inflow" ? "+" : "−"}{yuan(item.amount_minor)}</span><span className="text-right text-stone-500">余 {yuan(item.projected_balance_minor)}</span></div>)}</div></section>}
    {alerts.length > 0 && <section className="rounded-xl border border-stone-200 bg-white p-4"><SectionTitle icon={AlertTriangle} title="财务风险与数据缺口" detail={`${alerts.length}项`} /><div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">{alerts.map((item) => <div key={item.code} className="rounded-lg border border-amber-200 bg-amber-50 p-3"><p className="text-xs font-bold text-amber-950">{item.title}</p><p className="mt-1 text-[11px] leading-5 text-amber-800">{financeText(item.detail)}</p></div>)}</div></section>}
  </div>;
}

function ListPagination({ page, pageCount, total, onChange }: { page: number; pageCount: number; total: number; onChange: (page: number) => void }) {
  if (pageCount <= 1) return null;
  return <div className="mt-4 flex flex-col gap-2 border-t border-stone-100 pt-3 text-[11px] text-stone-500 sm:flex-row sm:items-center sm:justify-between">
    <span>共 {total} 笔 · 第 {page} / {pageCount} 页</span>
    <div className="flex items-center gap-2"><button type="button" disabled={page <= 1} onClick={() => onChange(page - 1)} className="min-h-9 rounded-lg border border-stone-200 bg-white px-3 font-semibold text-stone-700 transition hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-35">上一页</button><button type="button" disabled={page >= pageCount} onClick={() => onChange(page + 1)} className="min-h-9 rounded-lg border border-stone-200 bg-white px-3 font-semibold text-stone-700 transition hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-35">下一页</button></div>
  </div>;
}

function MoneyFlowPanel({ snapshot }: { snapshot: DailyFinanceSnapshotV1 }) {
  const events = snapshot.money_flow.events;
  const pageSize = 10;
  const [page, setPage] = useState(1);
  const pageCount = Math.max(1, Math.ceil(events.length / pageSize));
  const visibleEvents = events.slice((page - 1) * pageSize, page * pageSize);
  const isPeriod = snapshot.scope_kind === "period";
  const eventCounts = events.reduce<Record<string, number>>((counts, item) => ({ ...counts, [item.event_type]: (counts[item.event_type] ?? 0) + 1 }), {});
  return <section className="rounded-xl border border-stone-200 bg-white p-4">
    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <SectionTitle icon={ArrowLeftRight} title={isPeriod ? "期间资金流" : "当日资金流"} detail={`${events.length}笔`} />
        <p className="mt-1 text-[11px] text-stone-500">每一行都按“钱从哪里来 → 现在在哪里 → 最终做什么”展示，并关联同一张原始凭证。</p>
      </div>
      <p className="rounded-lg bg-amber-50 px-3 py-2 text-[11px] font-medium text-amber-800">累计到账不等于银行卡余额</p>
    </div>
    {events.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{["sale", "receipt", "outflow", "transfer"].map((type) => { const visual = moneyFlowVisual(type); const Icon = visual.icon; return <span key={type} className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-semibold ${visual.badge}`}><Icon className="h-3 w-3" />{visual.label} {eventCounts[type] ?? 0}</span>; })}</div>}
    {events.length === 0 ? <EmptyState title={isPeriod ? "所选期间还没有资金事件" : "当日还没有资金事件"} body="上传截图或记一笔后，资金来源、位置、用途和凭证会同时出现在这里。" /> : <div className="mt-4 space-y-2">
      <div className="hidden grid-cols-[1fr_32px_1fr_32px_1fr_132px] gap-2 px-3 text-[10px] font-semibold text-stone-400 md:grid"><span>业务来源</span><span /><span>资金当前位置</span><span /><span>去向 / 意义</span><span className="text-right">性质与金额</span></div>
      {visibleEvents.map((item) => { const visual = moneyFlowVisual(item.event_type); const Icon = visual.icon; return <div key={`${item.event_type}-${item.id}`} className={`group grid gap-2 rounded-xl border border-l-4 p-3 shadow-[0_1px_0_rgba(0,0,0,.02)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md md:grid-cols-[1fr_32px_1fr_32px_1fr_132px] md:items-center ${visual.frame}`}>
        <div className="min-w-0"><span className={`mb-2 inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-[10px] font-bold ${visual.badge}`}><Icon className="h-3 w-3" />{visual.label}</span><p className="truncate text-xs font-semibold text-stone-900">{item.source_label}</p><p className="mt-1 text-[10px] text-stone-500">{item.scene} · {item.date}</p></div>
        <span className={`hidden h-7 w-7 items-center justify-center rounded-full bg-white shadow-sm transition-transform duration-200 group-hover:translate-x-1 md:flex ${visual.arrow}`}><ChevronRight className="h-4 w-4" /></span>
        <div className="min-w-0"><p className="text-[10px] font-semibold text-stone-400 md:hidden">现在在哪里</p><p className="truncate text-xs text-stone-700">{item.location_label}</p><span className="mt-1 inline-flex rounded-full bg-stone-100 px-2 py-0.5 text-[10px] font-medium text-stone-600">{item.status_label}</span></div>
        <span className={`hidden h-7 w-7 items-center justify-center rounded-full bg-white shadow-sm transition-transform delay-75 duration-200 group-hover:translate-x-1 md:flex ${visual.arrow}`}><ChevronRight className="h-4 w-4" /></span>
        <div className="min-w-0"><p className="text-[10px] font-semibold text-stone-400 md:hidden">去向 / 意义</p><p className="truncate text-xs text-stone-700">{item.destination_label}</p>{item.voucher_id ? <a href={getEvidenceVoucherFileUrl(item.voucher_id)} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-2 text-[10px] font-semibold text-octo-700"><span className="grid h-10 w-10 place-items-center overflow-hidden rounded-md border border-stone-200 bg-stone-50">{isImageFile(item.voucher_filename) ? <img src={getEvidenceVoucherFileUrl(item.voucher_id)} alt={item.voucher_filename || "原始凭证"} className="h-full w-full object-contain" /> : <ReceiptText className="h-4 w-4" />}</span><span>打开原图</span></a> : <p className="mt-1 text-[10px] text-amber-700">暂无图片凭证</p>}</div>
        <div className="rounded-lg bg-white/80 px-3 py-2 text-right shadow-sm"><p className={`text-[10px] font-bold ${visual.amount}`}>{visual.amountLabel}</p><strong className={`mt-1 block text-base tabular-nums ${visual.amount}`}>{yuan(item.amount_minor)}</strong></div>
      </div>; })}
      <ListPagination page={page} pageCount={pageCount} total={events.length} onChange={setPage} />
    </div>}
  </section>;
}

function LedgerView({ snapshot, working, onNew, onEdit, onConfirm, title, description, showNew = true }: { snapshot: DailyFinanceSnapshotV1; working: boolean; onNew: () => void; onEdit: (record: BookkeepingRecordV1) => void; onConfirm: (id: string) => void; title?: string; description?: string; showNew?: boolean }) {
  const isPeriod = snapshot.scope_kind === "period";
  const pageSize = 10;
  const [page, setPage] = useState(1);
  const pageCount = Math.max(1, Math.ceil(snapshot.ledger_entries.length / pageSize));
  const visibleEntries = snapshot.ledger_entries.slice((page - 1) * pageSize, page * pageSize);
  return <section className="rounded-xl border border-stone-200 bg-white p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><SectionTitle icon={BookOpen} title={title || (isPeriod ? "期间资金台账" : "当日资金台账")} detail={`${snapshot.ledger_entries.length}笔`} /><p className="mt-1 text-[11px] text-stone-500">{description || "每笔都保留事实日期、收付款账户、交易对象、会计性质和原始凭证。"}</p></div>{showNew && <button onClick={onNew} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-octo-700 px-4 text-xs font-semibold text-white"><Plus className="h-4 w-4" />记一笔</button>}</div>
    {snapshot.ledger_entries.length === 0 ? <EmptyState title={isPeriod ? "所选期间还没有资金记录" : "当日还没有资金记录"} body="上传截图或记一笔后，会同时生成资金事件、台账记录和凭证关联。" /> : <div className="mt-4 divide-y divide-stone-100">{visibleEntries.map((item) => <div key={`${item.entry_origin}-${item.id}`} className="grid gap-3 py-3 md:grid-cols-[56px_minmax(0,1fr)_150px_120px]"><div>{item.voucher_id ? <a href={getEvidenceVoucherFileUrl(item.voucher_id)} target="_blank" rel="noreferrer" className="grid h-14 w-14 place-items-center overflow-hidden rounded-lg border border-stone-200 bg-stone-50 transition hover:border-octo-300 hover:shadow-md">{isImageFile(item.voucher_filename) ? <img src={getEvidenceVoucherFileUrl(item.voucher_id)} alt={item.voucher_filename || item.voucher_number || "原始凭证"} className="h-14 w-14 object-contain" /> : <ReceiptText className="h-5 w-5 text-octo-700" />}</a> : <div className="grid h-14 w-14 place-items-center rounded-lg border border-dashed border-stone-300 bg-stone-50"><ReceiptText className="h-4 w-4 text-stone-400" /></div>}</div><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="truncate text-sm font-semibold text-stone-900">{item.category_name}</p><StatusPill status={item.status} /></div><p className="mt-1 truncate text-[11px] text-stone-500">{item.counterparty || item.account_name || "交易对象待补充"}{item.summary ? ` · ${financeText(item.summary)}` : ""}</p><p className="mt-1 text-[10px] text-stone-400">事实日期 {item.traceability?.business_date || item.transaction_date} · 录入 {item.traceability?.recorded_at ? String(item.traceability.recorded_at).replace("T", " ").slice(0, 16) : "时间待补"} · {item.business_scope === "personal" ? "个人，不计店铺损益" : item.transaction_kind === "inventory_purchase" ? "库存，耗用时进成本" : "店铺资金"}</p></div><div className={`rounded-lg px-3 py-2 md:text-right ${item.direction === "inflow" ? "bg-emerald-50" : item.business_scope === "personal" ? "bg-stone-100" : item.direction === "outflow" ? "bg-rose-50" : "bg-violet-50"}`}><p className={`text-[10px] font-bold ${item.direction === "inflow" ? "text-emerald-700" : item.business_scope === "personal" ? "text-stone-600" : item.direction === "outflow" ? "text-rose-700" : "text-violet-700"}`}>{item.direction === "inflow" ? "资金流入" : item.business_scope === "personal" ? "个人资金流出" : item.direction === "outflow" ? "店铺资金流出" : "账户间流转"}</p><p className={`mt-1 text-base font-bold tabular-nums ${item.direction === "inflow" ? "text-emerald-800" : item.business_scope === "personal" ? "text-stone-700" : item.direction === "outflow" ? "text-rose-800" : "text-violet-800"}`}>{yuan(item.amount_minor)}</p><p className="mt-1 truncate text-[10px] text-stone-500">{item.account_name || "资金位置待补充"}</p></div><div className="flex items-center gap-2 md:justify-end">{item.entry_origin === "bookkeeping" && item.status !== "posted" && <><button onClick={() => onEdit(item as BookkeepingRecordV1)} className="min-h-9 rounded-lg border border-stone-200 px-3 text-[11px] font-semibold text-stone-700 transition hover:bg-stone-100">补充信息</button><button disabled={working || item.business_scope === "unknown"} onClick={() => onConfirm(item.id)} className="min-h-9 rounded-lg bg-stone-900 px-3 text-[11px] font-semibold text-white transition hover:bg-stone-700 disabled:opacity-40">确认记入</button></>}</div></div>)}<ListPagination page={page} pageCount={pageCount} total={snapshot.ledger_entries.length} onChange={setPage} /></div>}
    <p className="mt-4 rounded-lg bg-blue-50 px-3 py-2 text-[11px] leading-5 text-blue-800">账户到账只证明资金移动，不自动证明产生了新收入；采购付款先进入库存，只有实际耗用才进入利润表。</p>
  </section>;
}

type LedgerMajorKey = "income" | "store_cost" | "funds" | "personal";

const LEDGER_MAJOR_GROUPS: Array<{ key: LedgerMajorKey; label: string; description: string; icon: React.ElementType; tone: string; active: string }> = [
  { key: "income", label: "营业收入", description: "实际销售与销售调整", icon: CircleDollarSign, tone: "bg-emerald-50 text-emerald-800", active: "border-emerald-400 ring-2 ring-emerald-100" },
  { key: "store_cost", label: "店铺支出", description: "进货、经营费用与长期投入", icon: ArrowUpRight, tone: "bg-rose-50 text-rose-800", active: "border-rose-400 ring-2 ring-rose-100" },
  { key: "funds", label: "资金往来", description: "到账、转账、借款与老板往来", icon: Repeat2, tone: "bg-blue-50 text-blue-800", active: "border-blue-400 ring-2 ring-blue-100" },
  { key: "personal", label: "个人资金", description: "与店铺损益分开展示", icon: ReceiptText, tone: "bg-stone-100 text-stone-700", active: "border-stone-400 ring-2 ring-stone-100" },
];

function ledgerMajorGroup(item: DailyFinanceSnapshotV1["ledger_entries"][number]): LedgerMajorKey {
  if (item.business_scope === "personal" || item.transaction_kind === "personal_spending") return "personal";
  if (item.entry_origin === "merchant_net" || ["merchant_net_sale", "sales_receipt", "sales_adjustment"].includes(item.transaction_kind)) return "income";
  if ([
    "platform_settlement", "former_owner_collection", "former_owner_transfer", "account_transfer",
    "loan_in", "loan_repayment", "owner_investment", "owner_draw", "owner_advance", "owner_advance_repayment",
  ].includes(item.transaction_kind)) return "funds";
  if (item.direction === "outflow") return "store_cost";
  return "funds";
}

function DailyRevenueWorkspace({ checklist, selectedDate, working, onSaved, onError, setWorking }: {
  checklist: DailyRevenueChecklistV1;
  selectedDate: string;
  working: boolean;
  onSaved: (message: string) => Promise<void>;
  onError: (message: string) => void;
  setWorking: (value: boolean) => void;
}) {
  const reduceMotion = useReducedMotion();
  type DraftRow = { status: "recorded" | "confirmed_zero" | "not_available" | "missing"; amount: string };
  const day = checklist.days.find((item) => item.business_date === selectedDate) || checklist.days.at(-1);
  const [drafts, setDrafts] = useState<Record<string, DraftRow>>({});
  const [openStatusMenu, setOpenStatusMenu] = useState<string | null>(null);
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  useEffect(() => {
    if (!day) return;
    setDrafts(Object.fromEntries(day.channels.map((item) => [item.channel, {
      status: item.status,
      amount: item.amount_minor == null ? "" : (item.amount_minor / 100).toFixed(2),
    }])));
  }, [day]);
  if (!day) return null;

  const completed = day.channels.filter((row) => (drafts[row.channel]?.status ?? row.status) !== "missing").length;
  const totalMinor = day.channels.reduce((sum, row) => {
    const draft = drafts[row.channel];
    return sum + (draft?.status === "recorded" && Number.isFinite(Number(draft.amount)) ? Math.round(Number(draft.amount) * 100) : 0);
  }, 0);
  const setRow = (channel: string, patch: Partial<DraftRow>) => setDrafts((current) => ({
    ...current,
    [channel]: { ...(current[channel] || { status: "missing", amount: "" }), ...patch },
  }));

  async function submit() {
    if (!day) return;
    const items = day.channels.flatMap((row) => {
      const draft = drafts[row.channel];
      if (!draft || draft.status === "missing") return [];
      return [{
        channel: row.channel,
        status: draft.status as "recorded" | "confirmed_zero" | "not_available",
        amount: draft.status === "not_available" ? null : Number(draft.amount || 0),
      }];
    });
    if (items.length === 0) {
      onError("请至少录入一个渠道，或标记“当天0元/平台暂未出数”。");
      return;
    }
    setWorking(true);
    try {
      await saveDailyRevenue(selectedDate, items);
      await onSaved(`${selectedDate} 的营业情况已更新；到账状态依然按平台规则单独跟踪。`);
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "每日营业保存失败");
    } finally {
      setWorking(false);
    }
  }

  return <section className="finance-surface overflow-visible">
    <div className="flex items-center justify-between gap-6 border-b border-stone-200/80 px-5 py-4">
      <div><SectionTitle icon={CircleDollarSign} title="当日营业录入" detail={selectedDate} /><p className="mt-1.5 text-[13px] text-stone-500">直接填写各渠道当天实际收入；平台结算和工商银行到账会在资金页继续跟踪。</p></div>
      <div className="flex min-w-[250px] items-center gap-3"><div className="h-1.5 flex-1 overflow-hidden rounded-full bg-stone-100"><motion.div initial={false} animate={{ width: `${completed / 7 * 100}%` }} transition={{ duration: .35, ease: [0.22, 1, 0.36, 1] }} className={`h-full rounded-full ${completed === 7 ? "bg-emerald-500" : "bg-octo-500"}`} /></div><span className="w-20 text-right text-xs font-medium tabular-nums text-stone-600">{completed} / 7 完成</span></div>
    </div>
    <div className="grid grid-cols-[180px_minmax(300px,1fr)_260px_52px] items-center border-b border-stone-200 bg-[#fbfaf8] px-5 py-2.5 text-xs font-medium text-stone-500"><span>收入渠道</span><span>预计资金路径</span><span className="text-right">当日实际收入</span><span /></div>
    <div className="divide-y divide-stone-100">{day.channels.map((row, rowIndex) => {
      const draft = drafts[row.channel] || { status: row.status, amount: row.amount_minor == null ? "" : String(row.amount_minor / 100) };
      const statusText = draft.status === "recorded" ? "已录入" : draft.status === "confirmed_zero" ? "当天无收入" : draft.status === "not_available" ? "平台尚未出数" : "待录入";
      return <div key={row.channel} className={`group relative grid grid-cols-[180px_minmax(300px,1fr)_260px_52px] items-center px-5 py-3 transition-colors duration-200 ${openStatusMenu === row.channel ? "z-20 bg-[#fffaf6]" : "hover:bg-[#fdfcfb]"}`}>
        <div className="min-w-0"><p className="truncate text-[14px] font-medium text-stone-900">{row.channel}</p><p className={`mt-1 flex items-center gap-1.5 text-xs ${draft.status === "recorded" || draft.status === "confirmed_zero" ? "text-emerald-700" : draft.status === "not_available" ? "text-stone-500" : "text-amber-700"}`}><span className={`h-1.5 w-1.5 rounded-full ${draft.status === "recorded" || draft.status === "confirmed_zero" ? "bg-emerald-500" : draft.status === "not_available" ? "bg-stone-400" : "bg-amber-500"}`} />{statusText}</p></div>
        <div className="min-w-0 pr-6"><p className="truncate text-[13px] text-stone-700">{row.expected_fund_path}</p>{row.expected_wallet_date ? <p className="mt-1 truncate text-xs text-stone-500">预计 {row.expected_wallet_date} 到平台钱包{row.withdrawal_mode === "manual" ? " · 需手动提现" : ""}</p> : row.expected_bank_date ? <p className="mt-1 truncate text-xs text-stone-500">预计 {row.expected_bank_date} 到{row.kind === "pos" ? "工商银行店铺账户" : "平台绑定卡"}</p> : row.kind !== "cash" && <p className="mt-1 text-xs text-amber-700">到账规则待确认</p>}</div>
        <label className={`finance-money-input ${draft.status === "not_available" ? "finance-money-input-disabled" : ""}`}><span>¥</span><input ref={(element) => { inputRefs.current[row.channel] = element; }} aria-label={`${row.channel}当日金额`} inputMode="decimal" value={draft.amount} disabled={draft.status === "not_available"} onFocus={() => setOpenStatusMenu(null)} onKeyDown={(event) => { if (event.key !== "Enter") return; event.preventDefault(); const next = day.channels[rowIndex + 1]; if (next) inputRefs.current[next.channel]?.focus(); }} onChange={(event) => setRow(row.channel, { amount: event.target.value, status: event.target.value.trim() === "" ? "missing" : "recorded" })} placeholder={draft.status === "not_available" ? "等待平台数据" : "0.00"} /></label>
        <div className="relative flex justify-end"><button type="button" aria-label={`设置${row.channel}录入状态`} aria-expanded={openStatusMenu === row.channel} onClick={() => setOpenStatusMenu((current) => current === row.channel ? null : row.channel)} className="grid h-9 w-9 place-items-center rounded-lg text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-800 focus-visible:ring-2 focus-visible:ring-octo-300"><MoreHorizontal className="h-4 w-4" /></button>
          <AnimatePresence>{openStatusMenu === row.channel && <motion.div initial={reduceMotion ? false : { opacity: 0, scale: .96, y: -4 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: .97, y: -3 }} transition={{ duration: .16, ease: [0.22, 1, 0.36, 1] }} className="absolute right-0 top-10 z-30 w-48 overflow-hidden rounded-xl border border-stone-200 bg-white p-1.5 shadow-[0_18px_44px_rgba(50,35,25,.16)]">
            <button type="button" onClick={() => { setRow(row.channel, { status: "confirmed_zero", amount: "0.00" }); setOpenStatusMenu(null); }} className="finance-menu-item"><Check className={`h-4 w-4 ${draft.status === "confirmed_zero" ? "opacity-100" : "opacity-0"}`} />当天无收入</button>
            {!['cash', 'pos'].includes(row.kind) && <button type="button" onClick={() => { setRow(row.channel, { status: "not_available", amount: "" }); setOpenStatusMenu(null); }} className="finance-menu-item"><Check className={`h-4 w-4 ${draft.status === "not_available" ? "opacity-100" : "opacity-0"}`} />平台尚未出数</button>}
            <button type="button" onClick={() => { setRow(row.channel, { status: "missing", amount: "" }); setOpenStatusMenu(null); }} className="finance-menu-item"><Check className={`h-4 w-4 ${draft.status === "missing" ? "opacity-100" : "opacity-0"}`} />稍后补录</button>
          </motion.div>}</AnimatePresence>
        </div>
      </div>;
    })}</div>
    <div className="flex items-center justify-between gap-5 border-t border-stone-200/80 bg-[#fbfaf8] px-5 py-4"><div className="flex items-baseline gap-5"><p className="text-[13px] text-stone-600">已录 <strong className="font-semibold text-stone-950">{completed}</strong> 项，待补 <strong className="font-semibold text-amber-700">{7 - completed}</strong> 项</p><p className="text-[13px] text-stone-500">当日合计 <strong className="ml-1 text-lg font-semibold tabular-nums text-stone-950">{yuan(totalMinor, "¥0.00")}</strong></p><p className="text-xs text-stone-400">空缺不会按 0 元处理</p></div><motion.button type="button" disabled={working} onClick={() => void submit()} whileTap={reduceMotion ? undefined : { scale: .985 }} className="finance-button-primary min-w-40">{working ? "正在保存…" : "确认当日营业"}</motion.button></div>
  </section>;
}

function FinanceQuickEntry({ selectedDate, categories, onChooseCategory, onImportStatement }: {
  selectedDate: string;
  categories: FinanceCategoryCatalogV1;
  onChooseCategory: (group: string | null) => void;
  onImportStatement: () => void;
}) {
  const availableGroups = categories.groups.filter((group) => group.key !== "sales");
  const [group, setGroup] = useState("");
  const selected = availableGroups.find((item) => item.key === group);
  return <section className="finance-surface overflow-hidden">
    <div className="grid grid-cols-[minmax(0,1fr)_minmax(480px,680px)] items-center gap-8 px-5 py-5">
      <div className="min-w-0">
        <div className="flex items-center gap-2.5"><ReceiptText className="h-[17px] w-[17px] text-octo-700" /><h2 className="text-[15px] font-semibold text-stone-950">当日其他钱账</h2><span className="h-4 w-px bg-stone-200" /><span className="text-xs text-stone-500">{selectedDate}</span></div>
        <p className="mt-2 text-[13px] leading-5 text-stone-500">支出不设固定窗口。先选台账大类，系统只展示这笔账需要填写的内容。</p>
      </div>
      <div className="flex items-center gap-2.5">
        <label className="flex h-11 min-w-0 flex-1 items-center rounded-[10px] border border-stone-200 bg-white px-3 transition focus-within:border-octo-400 focus-within:ring-2 focus-within:ring-octo-100">
          <BookOpen className="mr-2 h-4 w-4 shrink-0 text-stone-400" />
          <select aria-label="选择台账大类" value={group} onChange={(event) => setGroup(event.target.value)} className="min-w-0 flex-1 bg-transparent text-[13px] font-medium text-stone-800 outline-none">
            <option value="">选择台账大类…</option>
            {availableGroups.map((item) => <option key={item.key} value={item.key}>{item.name}</option>)}
          </select>
        </label>
        <button type="button" disabled={!selected} onClick={() => onChooseCategory(group)} className="finance-button-primary min-w-24">继续<ChevronRight className="h-4 w-4" /></button>
        <span className="mx-1 h-6 w-px bg-stone-200" />
        <button type="button" onClick={onImportStatement} className="finance-button-secondary whitespace-nowrap"><Upload className="h-4 w-4" />导入银行流水</button>
      </div>
    </div>
    <div className="flex items-center justify-between border-t border-stone-100 bg-[#fbfaf8] px-5 py-3 text-xs text-stone-500"><span>单张账单或截图也可以直接使用右上角“智能录入”。</span><span>系统自动分类，你只确认一次</span></div>
  </section>;
}

function WeeklyPlatformTransferPanel({ selectedDate, onSaved, onError }: { selectedDate: string; onSaved: (message: string) => Promise<void>; onError: (message: string) => void }) {
  const [periodStart, setPeriodStart] = useState(dateShift(selectedDate, -7));
  const [periodEnd, setPeriodEnd] = useState(selectedDate);
  const [amount, setAmount] = useState("");
  const [preview, setPreview] = useState<PlatformArrivalMatchV1 | null>(null);
  const [working, setWorking] = useState(false);
  useEffect(() => { setPeriodStart(dateShift(selectedDate, -7)); setPeriodEnd(selectedDate); setPreview(null); }, [selectedDate]);

  async function calculate() {
    setWorking(true);
    try { setPreview(await getPlatformArrivals(periodStart, periodEnd)); }
    catch (cause) { onError(cause instanceof Error ? cause.message : "平台到账计算失败"); }
    finally { setWorking(false); }
  }
  async function matchTransfer() {
    if (!amount) return;
    setWorking(true);
    try {
      const result = await matchPlatformBoundCardTransfer({ transfer_date: selectedDate, amount: Number(amount), arrival_period_start: periodStart, arrival_period_end: periodEnd, source_reference: `owner-weekly-transfer:${selectedDate}:${amount}:${periodStart}:${periodEnd}` });
      setPreview(result);
      if (result.status === "matched") await onSaved(`已将 ${yuan(result.matched_minor)} 与${result.allocations?.length || 0}笔平台到账精确核销，资金已转入工商银行店铺账户，营业收入不重复增加。`);
    } catch (cause) { onError(cause instanceof Error ? cause.message : "周期转账核对失败"); }
    finally { setWorking(false); }
  }
  const expected = preview?.expected_total_minor || 0;
  const difference = amount ? Math.round(Number(amount) * 100) - expected : null;
  return <section className="rounded-xl border border-sky-200 bg-gradient-to-br from-sky-50 to-white p-4">
    <div><SectionTitle icon={ArrowLeftRight} title="周期到账核对" detail="内部资金转移" /><p className="mt-1 text-[11px] leading-5 text-stone-600">按平台 T+N 规则汇总已到平台绑定卡的店铺款；与本次转账一致时，自动核销到工商银行店铺账户。</p></div>
    <div className="mt-4 grid gap-3 md:grid-cols-4"><FormInput label="预计到绑定卡·开始" type="date" value={periodStart} onChange={(value) => { setPeriodStart(value); setPreview(null); }} /><FormInput label="预计到绑定卡·截止" type="date" value={periodEnd} onChange={(value) => { setPeriodEnd(value); setPreview(null); }} /><FormInput label="本次实际转入工商卡" type="number" value={amount} onChange={setAmount} placeholder="0.00" /><button type="button" disabled={working} onClick={() => void calculate()} className="min-h-10 self-end rounded-lg border border-sky-300 bg-white px-4 text-xs font-bold text-sky-800 disabled:opacity-50">计算应到金额</button></div>
    {preview && <div className="mt-4 rounded-xl border border-sky-100 bg-white p-4"><div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-[11px] text-stone-500">该周期平台应到合计</p><p className="mt-1 text-2xl font-black text-sky-900">{yuan(expected)}</p></div>{difference != null && <div className="text-right"><p className="text-[11px] text-stone-500">与实际转入差额</p><p className={`mt-1 text-lg font-black ${difference === 0 ? "text-emerald-700" : "text-amber-700"}`}>{difference === 0 ? "完全一致" : yuan(Math.abs(difference))}</p></div>}</div><div className="mt-3 flex flex-wrap gap-2">{preview.candidates.map((item) => <span key={item.id} className="rounded-full bg-sky-50 px-2.5 py-1 text-[10px] font-semibold text-sky-800">{item.channel}·{item.business_date} {yuan(item.merchant_net_minor)}</span>)}</div>{preview.wallet_settlement_platforms.filter((item) => !preview.manual_withdrawal_platforms.includes(item)).length > 0 && <p className="mt-3 text-[11px] text-sky-700">{preview.wallet_settlement_platforms.filter((item) => !preview.manual_withdrawal_platforms.includes(item)).join("、")}的 T+N 仅代表结算到平台钱包；绑定卡实际到账日以提现记录或银行回单为准，系统未把钱包日期当成银行卡日期。</p>}{preview.manual_withdrawal_platforms.length > 0 && <p className="mt-3 text-[11px] text-violet-700">{preview.manual_withdrawal_platforms.join("、")}已按钱包结算日跟踪，但需要先登记手动提现，因此暂不计入绑定卡应到合计。</p>}{preview.missing_rule_platforms.length > 0 && <p className="mt-3 text-[11px] text-amber-700">未计入：{preview.missing_rule_platforms.join("、")}的账期尚未确认，系统没有猜测。</p>}{difference === 0 && expected > 0 ? <button type="button" disabled={working} onClick={() => void matchTransfer()} className="mt-4 min-h-10 w-full rounded-lg bg-emerald-700 px-4 text-xs font-bold text-white disabled:opacity-50">确认本次转账并自动核销</button> : <p className="mt-3 text-[11px] text-stone-500">只有金额完全一致才自动核销；不一致时保留待查，不改动任何账目。</p>}</div>}
  </section>;
}

function LedgerWorkspace({ snapshot, working, onNew, onEdit, onConfirm }: { snapshot: DailyFinanceSnapshotV1; working: boolean; onNew: () => void; onEdit: (record: BookkeepingRecordV1) => void; onConfirm: (id: string) => void }) {
  const [mode, setMode] = useState<"grouped" | "timeline">("grouped");
  const [selected, setSelected] = useState<LedgerMajorKey>("income");
  const grouped = LEDGER_MAJOR_GROUPS.map((definition) => {
    const rows = snapshot.ledger_entries.filter((item) => ledgerMajorGroup(item) === definition.key);
    return {
      ...definition,
      rows,
      inflowMinor: rows.filter((item) => item.direction === "inflow").reduce((sum, item) => sum + item.amount_minor, 0),
      outflowMinor: rows.filter((item) => item.direction === "outflow").reduce((sum, item) => sum + item.amount_minor, 0),
    };
  });
  const activeGroup = grouped.find((item) => item.key === selected && item.rows.length > 0)
    || grouped.find((item) => item.rows.length > 0)
    || grouped[0];
  const filteredSnapshot: DailyFinanceSnapshotV1 = { ...snapshot, ledger_entries: activeGroup.rows };

  return <div className="space-y-4">
    <section className="rounded-xl border border-stone-200 bg-white p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div><SectionTitle icon={BookOpen} title={snapshot.scope_kind === "period" ? "期间台账分类" : "当日台账分类"} detail={`${snapshot.ledger_entries.length}笔`} /><p className="mt-1 text-[11px] text-stone-500">先看大类汇总，点击后查看每笔的账户、对方、性质和原始凭证。</p></div>
        <div className="flex min-h-10 rounded-lg bg-stone-100 p-1" aria-label="台账展示方式"><button type="button" onClick={() => setMode("grouped")} className={`rounded-md px-3 text-[11px] font-semibold transition ${mode === "grouped" ? "bg-white text-stone-900 shadow-sm" : "text-stone-500"}`}>分类汇总</button><button type="button" onClick={() => setMode("timeline")} className={`rounded-md px-3 text-[11px] font-semibold transition ${mode === "timeline" ? "bg-white text-stone-900 shadow-sm" : "text-stone-500"}`}>按时间查看</button></div>
      </div>
      {mode === "grouped" && <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{grouped.map((item) => { const Icon = item.icon; const isActive = item.key === activeGroup.key; return <button key={item.key} type="button" onClick={() => setSelected(item.key)} className={`rounded-xl border bg-white p-3 text-left transition hover:-translate-y-0.5 hover:shadow-md ${isActive ? item.active : "border-stone-200"}`}><div className="flex items-center justify-between gap-2"><span className={`inline-flex h-8 w-8 items-center justify-center rounded-lg ${item.tone}`}><Icon className="h-4 w-4" /></span><span className="text-[10px] font-semibold text-stone-400">{item.rows.length}笔</span></div><p className="mt-3 text-sm font-bold text-stone-900">{item.label}</p><p className="mt-1 min-h-8 text-[10px] leading-4 text-stone-500">{item.description}</p><div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[11px] font-semibold">{item.inflowMinor > 0 && <span className="text-emerald-700">流入 {yuan(item.inflowMinor)}</span>}{item.outflowMinor > 0 && <span className="text-rose-700">流出 {yuan(item.outflowMinor)}</span>}{item.inflowMinor === 0 && item.outflowMinor === 0 && <span className="text-stone-400">暂无发生</span>}</div></button>; })}</div>}
    </section>
    {mode === "grouped"
      ? <LedgerView key={`${snapshot.period_start}-${snapshot.period_end}-${activeGroup.key}`} snapshot={filteredSnapshot} working={working} onNew={onNew} onEdit={onEdit} onConfirm={onConfirm} title={`${activeGroup.label}明细`} description={`${activeGroup.description}；以事实日期为准，不会把到账重复算成营业收入。`} />
      : <MoneyFlowPanel key={`${snapshot.period_start}-${snapshot.period_end}-timeline`} snapshot={snapshot} />}
  </div>;
}

function PlatformCollectionPanel({ selectedDate, bindings, accounts, onSaved, onError }: { selectedDate: string; bindings: PlatformCollectionBindingV1[]; accounts: FundAccountV1[]; onSaved: () => Promise<void>; onError: (message: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [effectiveFrom, setEffectiveFrom] = useState(selectedDate);
  const targetAccounts = accounts.filter((item) => item.status === "active" && item.account_kind === "bank" && ["store", "owner"].includes(item.owner_kind));
  const recommended = targetAccounts.find((item) => item.account_key === "planned-store-icbc") || targetAccounts[0];
  const [targetAccountKey, setTargetAccountKey] = useState(recommended?.account_key || "");
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(bindings.map((item) => item.platform));
  const accountName = (key: string | null | undefined) => accounts.find((item) => item.account_key === key)?.name || key || "账户待补";

  useEffect(() => {
    setEffectiveFrom(selectedDate);
    setSelectedPlatforms(bindings.map((item) => item.platform));
  }, [selectedDate, bindings]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const target = accounts.find((item) => item.account_key === targetAccountKey);
    if (!target || selectedPlatforms.length === 0) return;
    setSaving(true);
    try {
      await Promise.all(selectedPlatforms.map((platform) => {
        const current = bindings.find((item) => item.platform === platform);
        return savePlatformCollectionBinding({
          platform,
          collector_account_key: target.account_key,
          destination_account_key: target.account_key,
          collector_owner_kind: target.owner_kind,
          settlement_rule: current?.settlement_rule,
          settlement_delay_days: current?.settlement_delay_days,
          settlement_day_basis: current?.settlement_day_basis,
          settlement_rule_status: current?.settlement_rule_status,
          settlement_rule_source: current?.settlement_rule_source,
          settlement_delay_target: current?.settlement_delay_target,
          withdrawal_mode: current?.withdrawal_mode,
          effective_from: effectiveFrom,
          status: "active",
          notes: "营业执照与银行卡换绑后启用；旧收款路径按生效日自动截止",
        });
      }));
      setEditing(false);
      await onSaved();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "平台收款路径更新失败");
    } finally {
      setSaving(false);
    }
  }

  return <section className="rounded-xl border border-stone-200 bg-white p-4">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div><SectionTitle icon={ArrowLeftRight} title="平台收款路径" detail={`${bindings.length}个平台`} /><p className="mt-1 text-[11px] leading-5 text-stone-500">平台钱包 → 平台绑定卡（暂时代管） → 工商银行店铺账户；换绑后只更新新路径，历史不变。</p></div>
      <button type="button" onClick={() => setEditing((value) => !value)} className="min-h-10 shrink-0 rounded-lg border border-octo-200 bg-octo-50 px-4 text-xs font-semibold text-octo-800">{editing ? "取消换绑" : "登记银行卡换绑"}</button>
    </div>
    {bindings.length === 0 ? <EmptyState title="当前日期没有收款路径记录" body="平台账仍可录入，但在补齐绑定关系前，系统不会猜测资金最终到了哪个账户。" /> : <div className="mt-4 grid gap-3 md:grid-cols-2">{bindings.map((item) => <article key={item.id} className="rounded-xl border border-stone-200 bg-stone-50 p-3"><div className="flex items-center justify-between gap-3"><p className="text-xs font-bold text-stone-900">{item.platform}</p><span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${item.settlement_rule_status === "confirmed" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>{item.settlement_rule_status === "confirmed" ? `T+${item.settlement_delay_days}${item.settlement_delay_target === "platform_wallet" ? "到钱包" : "到账"}${item.withdrawal_mode === "manual" ? " · 手动提现" : ""}` : "账期待确认"}</span></div><p className="mt-3 text-xs leading-5 text-stone-800">平台钱包{item.settlement_delay_target === "platform_wallet" && item.withdrawal_mode === "manual" ? "（需手动提现）" : ""} <span className="text-stone-400">→</span> 平台绑定卡（暂时代管）{item.destination_account_key ? <> <span className="text-stone-400">→</span> {accountName(item.destination_account_key)}</> : null}</p><p className="mt-2 text-[10px] leading-4 text-stone-500">{item.settlement_rule || "结算周期以平台账单为准"}</p><p className="mt-2 text-[10px] text-stone-400">生效：{item.effective_from}{item.effective_to ? ` 至 ${item.effective_to}` : " 起"}</p></article>)}</div>}
    {editing && <form onSubmit={submit} className="mt-4 rounded-xl border border-octo-200 bg-octo-50/60 p-4"><p className="text-xs font-bold text-stone-900">选择本次完成换绑的平台</p><div className="mt-3 flex flex-wrap gap-2">{bindings.map((item) => <label key={item.platform} className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-stone-200 bg-white px-3 text-xs text-stone-700"><input type="checkbox" checked={selectedPlatforms.includes(item.platform)} onChange={(event) => setSelectedPlatforms((current) => event.target.checked ? [...new Set([...current, item.platform])] : current.filter((value) => value !== item.platform))} className="h-4 w-4 accent-octo-700" />{item.platform}</label>)}</div><div className="mt-4 grid gap-3 sm:grid-cols-2"><FormInput label="新路径生效日" type="date" value={effectiveFrom} onChange={setEffectiveFrom} /><FormSelect label="换绑后的收款账户" value={targetAccountKey} onChange={setTargetAccountKey} options={targetAccounts.filter((item) => item.owner_kind === "store").map((item) => ({ value: item.account_key, label: item.name }))} /></div><p className="mt-3 text-[11px] leading-5 text-stone-600">确认后，所选平台在生效日前仍按旧路径核对；从生效日起改为直接进入工商银行店铺账户。个人招商卡不进入店铺资金链。</p><button disabled={saving || !effectiveFrom || !targetAccountKey || selectedPlatforms.length === 0} className="mt-3 min-h-10 w-full rounded-lg bg-octo-700 text-xs font-semibold text-white disabled:opacity-40">{saving ? "正在更新收款路径…" : `确认更新${selectedPlatforms.length}个平台`}</button></form>}
  </section>;
}

function ReconciliationView({ accounts, queue, periodStart, periodEnd, working, onUploaded, onMatched }: { accounts: FundAccountV1[]; queue: ReconciliationQueueItemV1[]; periodStart: string; periodEnd: string; working: boolean; onUploaded: (message: string) => Promise<void>; onMatched: (item: ReconciliationQueueItemV1, candidate: ReconciliationQueueItemV1["candidates"][number]) => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null);
  const [account, setAccount] = useState("");
  const [source, setSource] = useState("bank_statement");
  const [uploading, setUploading] = useState(false);
  const [reportFile, setReportFile] = useState<File | null>(null);
  const [report, setReport] = useState<PlatformReportPreviewV1 | null>(null);
  const [walletAccount, setWalletAccount] = useState("");
  const [destinationAccount, setDestinationAccount] = useState("");
  const [reportWorking, setReportWorking] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [imageReport, setImageReport] = useState<Awaited<ReturnType<typeof recognizeCapture>> | null>(null);
  const [imagePlatform, setImagePlatform] = useState("");
  const [imageDate, setImageDate] = useState(periodEnd);
  const [imageAmount, setImageAmount] = useState("");
  const [imageNature, setImageNature] = useState<"daily_sales" | "platform_settlement">("daily_sales");
  const [imageAccount, setImageAccount] = useState("");

  async function upload() {
    if (!file || !account) return;
    setUploading(true);
    try {
      const result = await uploadFinanceStatement(file, account, source);
      await onUploaded(`已解析 ${result.row_count} 笔：收入 ${yuan(result.inflow_minor)}，支出 ${yuan(result.outflow_minor)}。请逐笔确认后入账。`);
      setFile(null);
    } finally {
      setUploading(false);
    }
  }

  async function inspectReport() {
    if (!reportFile) return;
    setReportWorking(true);
    setReportError(null);
    try {
      if (reportFile.type.startsWith("image/") || /\.(png|jpe?g|webp)$/i.test(reportFile.name)) {
        const recognized = await recognizeCapture(reportFile);
        const raw = `${recognized.source_type} ${recognized.raw_text || ""} ${reportFile.name}`;
        const platformMap: Record<string, string> = {
          keyun: "客如云收款", meituan: "美团外卖", meituan_delivery: "美团外卖", meituan_group: "美团团购",
          taobao_flash: "淘宝闪购", jd_delivery: "京东外卖", douyin: "抖音团购", douyin_group: "抖音团购",
        };
        const inferredPlatform = platformMap[recognized.source_platform || ""]
          || (/京东|秒送/.test(raw) ? "京东外卖" : /美团团购/.test(raw) ? "美团团购" : /美团/.test(raw) ? "美团外卖" : /淘宝|闪购/.test(raw) ? "淘宝闪购" : /抖音/.test(raw) ? "抖音团购" : /客如云/.test(raw) ? "客如云收款" : "");
        const valueFor = (...keys: string[]) => recognized.fields.find((field) => keys.includes(field.key))?.value;
        const amount = valueFor("delivery_revenue", "revenue", "amount");
        const date = valueFor("date");
        const settlement = /(钱包|结算|提现|到账|余额)/.test(raw) && !/(营业额|营业收入|外卖实收|当日收入)/.test(raw);
        setImageReport(recognized);
        setImagePlatform(inferredPlatform);
        setImageDate(typeof date === "string" ? date : periodEnd);
        setImageAmount(typeof amount === "number" || typeof amount === "string" ? String(amount) : "");
        setImageNature(settlement ? "platform_settlement" : "daily_sales");
        setImageAccount("");
        setReport(null);
        return;
      }
      const result = await previewPlatformReport(reportFile);
      setReport(result.report);
      setImageReport(null);
    } catch (cause) {
      setReport(null);
      setImageReport(null);
      setReportError(cause instanceof Error ? cause.message : "报表识别失败");
    } finally {
      setReportWorking(false);
    }
  }

  async function postImageReport() {
    if (!reportFile || !imageReport || !imagePlatform || !imageDate || !imageAmount) return;
    if (imageNature === "platform_settlement" && !imageAccount) return;
    setReportWorking(true);
    setReportError(null);
    try {
      const storeIcbc = accounts.find((item) => item.owner_kind === "store" && /工商/.test(`${item.institution || ""}${item.name}`));
      const result = await createFinanceIntake({
        fact_type: imageNature === "daily_sales" ? "merchant_net_sale" : "platform_settlement",
        business_date: imageDate,
        amount: Number(imageAmount),
        channel: imagePlatform,
        settlement_state: imageNature === "daily_sales" ? (imagePlatform === "客如云收款" ? "store_account_received" : "wallet_credited") : undefined,
        current_account_key: imageNature === "daily_sales" && imagePlatform === "客如云收款" ? storeIcbc?.account_key : undefined,
        account_key: imageNature === "platform_settlement" ? imageAccount : undefined,
        business_category_key: imageNature === "daily_sales" ? "delivery_sales" : "platform_wallet_credit",
        category_name: imageNature === "daily_sales" ? "营业收入" : "平台结算到钱包",
        counterparty: imagePlatform,
        source_basis: `${imagePlatform}后台截图（人工确认）`,
        notes: `原图识别：${imageReport.source_type}；确认后写入，不把平台结算重复计为收入。`,
        file: reportFile,
      });
      if (["blocked", "needs_input"].includes(result.plan.status)) {
        setReportError(result.plan.error_message || "这张图还缺必要字段，已保留原图，请补充后再确认。");
        return;
      }
      await confirmFinanceExecutionPlan(result.plan.plan_id);
      await onUploaded(imageNature === "daily_sales" ? `${imagePlatform} ${imageDate} 营业收入 ${yuan(Math.round(Number(imageAmount) * 100))} 已按原图确认。` : `${imagePlatform} ${imageDate} 平台结算 ${yuan(Math.round(Number(imageAmount) * 100))} 已记入资金位置，未重复增加收入。`);
      setReportFile(null); setImageReport(null); setImagePlatform(""); setImageAmount("");
    } catch (cause) {
      setReportError(cause instanceof Error ? cause.message : "图片资料确认失败");
    } finally { setReportWorking(false); }
  }

  async function postReport() {
    if (!reportFile || !report) return;
    setReportWorking(true);
    setReportError(null);
    try {
      const result = await confirmPlatformReport(reportFile, {
        walletAccountKey: walletAccount,
        destinationAccountKey: destinationAccount,
      });
      const message = result.report_type === "keruyun_daily_brief"
        ? `客如云日报已归档，当日营业收入 ${yuan(result.merchant_net_minor)}。`
        : `美团流水已归档，生成 ${result.created_record_count ?? 0} 笔待核对记录；未增加营业收入。`;
      setReport(null);
      setReportFile(null);
      await onUploaded(message);
    } catch (cause) {
      setReportError(cause instanceof Error ? cause.message : "报表确认失败");
    } finally {
      setReportWorking(false);
    }
  }

  const isMeituan = report?.report_type === "meituan_balance_statement";
  const canPostReport = Boolean(
    reportFile
    && report?.can_confirm
    && (!isMeituan || (walletAccount && destinationAccount)),
  );

  return <div className="space-y-4">
    <section className="rounded-xl border border-stone-200 bg-white p-4">
      <SectionTitle icon={FileSearch} title="平台经营资料" detail="客如云 · 美团外卖/团购 · 淘宝闪购 · 京东外卖 · 抖音团购" />
      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
        <FinanceFileDropzone autoFocus file={reportFile} onFile={(next) => { setReportFile(next); setReport(null); setImageReport(null); setReportError(null); }} accept="image/png,image/jpeg,image/webp,.xls,.xlsx,.xlsm" title="粘贴、拖入或上传平台截图/官方报表" hint="打开后可直接 Command+V；图片会显示缩略图，写账前必须确认。" />
        <button disabled={!reportFile || reportWorking} onClick={() => void inspectReport()} className="finance-button-primary min-w-28 self-end">{reportWorking ? "识别中…" : "识别资料"}</button>
      </div>
      {reportError && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-800">{reportError}</p>}
      {report && <div className="mt-4 rounded-xl border border-stone-200 bg-stone-50/60 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-stone-200 pb-3">
          <div><p className="text-sm font-bold text-stone-950">{report.source_platform}</p><p className="mt-0.5 text-[11px] text-stone-500">{report.period_start} — {report.period_end}</p></div>
          <StatusPill status={report.can_confirm ? "confirmed" : "needs_review"} />
        </div>
        {report.report_type === "keruyun_daily_brief" ? <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="订单金额" value={yuan(report.summary.order_amount_minor)} />
          <Metric label="优惠/配送/服务费" value={yuan((report.summary.merchant_discount_minor ?? 0) + (report.summary.delivery_expense_minor ?? 0) + (report.summary.service_fee_minor ?? 0))} />
          <Metric label="补贴（带正负号）" value={yuan(report.summary.subsidy_minor)} />
          <Metric label="平台结算净额" value={yuan(report.summary.merchant_net_minor)} strong />
        </div> : <div className="mt-3 grid gap-2 sm:grid-cols-3">
          <Metric label="平台钱包入账" value={yuan(report.summary.wallet_credit_minor)} />
          <Metric label="钱包提现" value={yuan(report.summary.wallet_withdrawal_minor)} />
          <Metric label="营业收入影响" value={yuan(report.summary.revenue_impact_minor, "¥0.00")} strong />
        </div>}
        {isMeituan && <div className="mt-3 grid gap-3 md:grid-cols-2">
          <FormSelect label="美团平台钱包" value={walletAccount} onChange={setWalletAccount} options={[{ value: "", label: "请选择账户" }, ...accounts.filter((item) => item.account_kind === "platform_wallet").map((item) => ({ value: item.account_key, label: item.name }))]} />
          <FormSelect label="提现到账账户" value={destinationAccount} onChange={setDestinationAccount} options={[{ value: "", label: "请选择账户" }, ...accounts.filter((item) => item.account_kind !== "platform_wallet").map((item) => ({ value: item.account_key, label: item.name }))]} />
        </div>}
        <div className="mt-3 flex justify-end"><button disabled={!canPostReport || reportWorking} onClick={() => void postReport()} className="min-h-10 rounded-lg bg-stone-900 px-5 text-xs font-semibold text-white disabled:opacity-40">{reportWorking ? "保存中…" : "确认并归档"}</button></div>
      </div>}
      {imageReport && <div className="mt-4 rounded-xl border border-octo-200 bg-octo-50/35 p-4">
        <div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold text-stone-950">图片已识别，请确认关键字段</p><p className="mt-1 text-[11px] text-stone-500">{imageReport.source_type} · 原图会与这笔事实一起保留</p></div><span className="finance-status finance-status-warning">待确认</span></div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <FormSelect label="平台/渠道" value={imagePlatform} onChange={setImagePlatform} options={[{ value: "", label: "请确认平台" }, ...["客如云收款", "美团外卖", "美团团购", "淘宝闪购", "京东外卖", "抖音团购"].map((value) => ({ value, label: value }))]} />
          <FormSelect label="资料性质" value={imageNature} onChange={(value) => setImageNature(value as "daily_sales" | "platform_settlement")} options={[{ value: "daily_sales", label: "当日实际营业收入" }, { value: "platform_settlement", label: "平台结算/钱包入账" }]} />
          <FormInput label="事实日期" type="date" value={imageDate} onChange={setImageDate} />
          <FormInput label="金额" type="number" value={imageAmount} onChange={setImageAmount} />
          {imageNature === "platform_settlement" && <FormSelect label="当前资金账户" value={imageAccount} onChange={setImageAccount} options={[{ value: "", label: "请选择" }, ...accounts.map((item) => ({ value: item.account_key, label: item.name }))]} />}
        </div>
        <div className="mt-4 flex items-center justify-between gap-4 border-t border-octo-100 pt-3"><p className="text-[11px] leading-5 text-stone-600">{imageNature === "daily_sales" ? "确认后记入营业收入；后续钱包结算和银行到账不会再增加收入。" : "确认后只更新资金位置，不会重复增加营业收入。"}</p><button type="button" disabled={reportWorking || !imagePlatform || !imageDate || !imageAmount || (imageNature === "platform_settlement" && !imageAccount)} onClick={() => void postImageReport()} className="finance-button-primary shrink-0">确认并记入</button></div>
      </div>}
    </section>
    <section className="rounded-xl border border-stone-200 bg-white p-4"><SectionTitle icon={Upload} title="账户流水导入" detail="工商银行店铺账户 / 招商银行个人账户 / 支付宝 / 微信" /><div className="mt-4 grid gap-3 lg:grid-cols-[.7fr_.9fr_minmax(0,1.4fr)_auto]"><FormSelect label="账单来源" value={source} onChange={setSource} options={[{ value: "bank_statement", label: "银行流水" }, { value: "alipay_statement", label: "支付宝账单" }, { value: "wechat_statement", label: "微信账单" }]} /><FormSelect label="所属账户" value={account} onChange={setAccount} options={[{ value: "", label: "请选择账户" }, ...accounts.map((item) => ({ value: item.account_key, label: item.name }))]} /><FinanceFileDropzone file={file} onFile={setFile} accept=".csv,.xlsx,.xlsm,.pdf" title="粘贴、拖入或上传流水文件" hint="支持 CSV、Excel 和 PDF；导入后生成逐笔待对账记录。" /><button disabled={!file || !account || uploading} onClick={() => void upload()} className="finance-button-primary min-w-28 self-end">{uploading ? "解析中…" : "导入并识别"}</button></div></section>
    <section className="rounded-xl border border-stone-200 bg-white p-4"><SectionTitle icon={ArrowLeftRight} title="逐笔财务对账" detail={`${queue.length}笔待处理 · ${periodStart === periodEnd ? periodEnd : `${periodStart} 至 ${periodEnd}`}`} />{queue.length === 0 ? <EmptyState title={periodStart === periodEnd ? "当日没有待对账流水" : "所选期间没有待对账流水"} body="导入账单后，系统会按金额、日期、账户和交易对象寻找平台结算、资金流水及营业收入记录。" /> : <div className="mt-3 space-y-3">{queue.map((item) => <div key={item.record.id} className="rounded-lg border border-stone-200 p-3"><div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-xs font-bold text-stone-900">{item.record.category_name} · {item.record.counterparty || "交易对方待确认"}</p><p className="mt-1 text-[11px] text-stone-500">{item.record.transaction_date} · {item.record.classification_reason}</p></div><div className="sm:text-right"><strong className="text-base tabular-nums text-stone-950">{yuan(item.record.amount_minor)}</strong>{item.remaining_minor < item.record.amount_minor && <p className="mt-1 text-[10px] text-amber-700">待核销 {yuan(item.remaining_minor)}</p>}</div></div>{item.candidates.length === 0 ? <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-[11px] text-amber-800">没有找到可靠匹配。请补平台账单、到账截图或检查金额与日期。</p> : <div className="mt-3 grid gap-2 md:grid-cols-2">{item.candidates.map((candidate) => <div key={`${candidate.target_type}-${candidate.id}`} className="flex items-center justify-between gap-3 rounded-lg bg-stone-50 p-3"><div><p className="text-xs font-semibold text-stone-800">{candidate.target_label}</p><p className="mt-1 text-[10px] text-stone-500">{candidate.target_date} · {candidate.reason}</p></div><button disabled={working} onClick={() => void onMatched(item, candidate)} className="min-h-9 shrink-0 rounded-lg border border-emerald-300 bg-emerald-50 px-3 text-[11px] font-semibold text-emerald-800">核销 {yuan(candidate.suggested_match_minor)}</button></div>)}</div>}</div>)}</div>}</section></div>;
}

function VoucherView({ vouchers, periodStart, periodEnd }: { vouchers: EvidenceVoucherV1[]; periodStart: string; periodEnd: string }) {
  const isPeriod = periodStart !== periodEnd;
  const pageSize = 20;
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("all");
  const [groupBy, setGroupBy] = useState<"date" | "source">("date");
  const [display, setDisplay] = useState<"list" | "gallery">("list");
  const [preview, setPreview] = useState<EvidenceVoucherV1 | null>(null);
  const [hoverPreview, setHoverPreview] = useState<{ item: EvidenceVoucherV1; left: number; top: number } | null>(null);

  const sources = useMemo(() => Array.from(new Set(vouchers.map((item) => financeText(item.channel || item.evidence_type)))).sort((a, b) => a.localeCompare(b, "zh-CN")), [vouchers]);
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("zh-CN");
    return vouchers.filter((item) => {
      const label = financeText(item.channel || item.evidence_type);
      if (source !== "all" && label !== source) return false;
      if (!needle) return true;
      return [label, financeText(item.evidence_type), item.business_date, item.notes]
        .filter(Boolean)
        .some((value) => String(value).toLocaleLowerCase("zh-CN").includes(needle));
    });
  }, [query, source, vouchers]);

  useEffect(() => setPage(1), [query, source, groupBy, display]);
  useEffect(() => {
    if (!preview) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setPreview(null); };
    document.addEventListener("keydown", close);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", close);
      document.body.style.overflow = previousOverflow;
    };
  }, [preview]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visibleVouchers = filtered.slice((page - 1) * pageSize, page * pageSize);
  const grouped = useMemo(() => {
    const rows = new Map<string, EvidenceVoucherV1[]>();
    visibleVouchers.forEach((item) => {
      const key = groupBy === "date" ? (item.business_date || "日期待补充") : financeText(item.channel || item.evidence_type);
      rows.set(key, [...(rows.get(key) || []), item]);
    });
    return Array.from(rows.entries());
  }, [groupBy, visibleVouchers]);

  const voucherImage = (item: EvidenceVoucherV1, className: string) => isImageFile(item.original_filename)
    ? <img src={getEvidenceVoucherFileUrl(item.id)} alt={`${financeText(item.channel || item.evidence_type)}原始凭证`} className={className} />
    : <ReceiptText className="h-6 w-6 text-stone-400" />;

  return <section className="rounded-xl border border-stone-200 bg-white p-4">
    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div><SectionTitle icon={ReceiptText} title={isPeriod ? "期间凭证档案" : "当日凭证档案"} detail={`${vouchers.length}份 · ${isPeriod ? `${periodStart} 至 ${periodEnd}` : periodEnd}`} /><p className="mt-1 text-[11px] text-stone-500">默认按日期紧凑归档；点击缩略图在当前页查看高清原图。</p></div>
      {vouchers.length > 0 && <div className="flex rounded-lg bg-stone-100 p-1" aria-label="凭证显示方式">
        <button type="button" onClick={() => setDisplay("list")} className={`inline-flex min-h-9 items-center gap-1.5 rounded-md px-3 text-[11px] font-semibold transition ${display === "list" ? "bg-white text-stone-900 shadow-sm" : "text-stone-500 hover:text-stone-800"}`}><LayoutList className="h-3.5 w-3.5" />紧凑列表</button>
        <button type="button" onClick={() => setDisplay("gallery")} className={`inline-flex min-h-9 items-center gap-1.5 rounded-md px-3 text-[11px] font-semibold transition ${display === "gallery" ? "bg-white text-stone-900 shadow-sm" : "text-stone-500 hover:text-stone-800"}`}><Images className="h-3.5 w-3.5" />图片浏览</button>
      </div>}
    </div>

    {vouchers.length === 0 ? <EmptyState title={isPeriod ? "所选期间没有凭证" : "当日没有凭证"} body="上传账单、截图、转账凭证或票据后会自动归档到这里。" /> : <>
      <div className="mt-4 grid gap-2 border-y border-stone-100 py-3 md:grid-cols-[minmax(220px,1fr)_180px_150px]">
        <label className="relative block"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索平台、凭证类型或日期" className="min-h-10 w-full rounded-lg border border-stone-200 bg-white pl-9 pr-3 text-xs outline-none transition focus:border-octo-400 focus:ring-2 focus:ring-octo-100" /></label>
        <select aria-label="按来源筛选凭证" value={source} onChange={(event) => setSource(event.target.value)} className="min-h-10 rounded-lg border border-stone-200 bg-white px-3 text-xs text-stone-700 outline-none focus:border-octo-400"><option value="all">全部来源</option>{sources.map((item) => <option key={item} value={item}>{item}</option>)}</select>
        <select aria-label="凭证分组方式" value={groupBy} onChange={(event) => setGroupBy(event.target.value as "date" | "source")} className="min-h-10 rounded-lg border border-stone-200 bg-white px-3 text-xs text-stone-700 outline-none focus:border-octo-400"><option value="date">按日期分组</option><option value="source">按来源分组</option></select>
      </div>
      <div className="mt-3 flex items-center justify-between gap-3"><p className="text-[11px] text-stone-500">已显示 <strong className="text-stone-800">{filtered.length}</strong> 份凭证</p>{filtered.length !== vouchers.length && <button type="button" onClick={() => { setQuery(""); setSource("all"); }} className="text-[11px] font-semibold text-octo-700">清除筛选</button>}</div>

      {filtered.length === 0 ? <EmptyState title="没有匹配的凭证" body="请更换搜索词或清除来源筛选。" /> : display === "list" ? <div className="mt-2 divide-y divide-stone-200">
        {grouped.map(([group, items]) => <div key={group} className="py-3 first:pt-1">
          <div className="mb-1.5 flex items-center justify-between gap-3"><p className="text-xs font-bold text-stone-900">{group}</p><p className="text-[10px] text-stone-500">{items.length}份{items.some((item) => item.amount_minor != null) ? ` · 已记录 ${yuan(items.reduce((sum, item) => sum + (item.amount_minor || 0), 0))}` : ""}</p></div>
          <div className="divide-y divide-stone-100 rounded-lg border border-stone-200">{items.map((item) => <div key={item.id} className="grid min-w-0 grid-cols-[56px_minmax(0,1fr)_auto] items-center gap-3 p-2.5 sm:grid-cols-[56px_minmax(0,1fr)_140px_110px]">
            <button type="button" onClick={() => setPreview(item)} onMouseEnter={(event) => {
              if (!window.matchMedia("(hover: hover)").matches || !isImageFile(item.original_filename)) return;
              const rect = event.currentTarget.getBoundingClientRect();
              const width = 224;
              const height = 316;
              const left = Math.min(rect.right + 12, window.innerWidth - width - 16);
              const top = Math.min(Math.max(16, rect.top + (rect.height - height) / 2), window.innerHeight - height - 16);
              setHoverPreview({ item, left, top });
            }} onMouseLeave={() => setHoverPreview(null)} aria-label={`查看${financeText(item.channel || item.evidence_type)}原始凭证`} className="group/preview relative grid h-14 w-14 place-items-center rounded-lg border border-stone-200 bg-stone-50 outline-none transition hover:border-octo-300 focus-visible:ring-2 focus-visible:ring-octo-400">
              <span className="grid h-full w-full place-items-center overflow-hidden rounded-[7px]">{voucherImage(item, "h-full w-full object-cover transition duration-300 group-hover/preview:scale-110")}</span>
            </button>
            <div className="min-w-0"><p className="truncate text-xs font-bold text-stone-900">{financeText(item.channel || item.evidence_type)}</p><p className="mt-1 truncate text-[10px] text-stone-500">{financeText(item.evidence_type)} · {item.business_date || "日期待补充"}</p></div>
            <div className="hidden min-w-0 sm:block"><StatusPill status={item.status} /></div>
            <p className="text-right text-sm font-bold tabular-nums text-stone-950">{yuan(item.amount_minor, "金额待补")}</p>
          </div>)}</div>
        </div>)}
      </div> : <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{visibleVouchers.map((item) => <button type="button" key={item.id} onClick={() => setPreview(item)} className="group overflow-hidden rounded-xl border border-stone-200 bg-stone-50 text-left outline-none transition hover:-translate-y-0.5 hover:border-octo-300 hover:shadow-lg focus-visible:ring-2 focus-visible:ring-octo-400"><span className="grid aspect-[4/3] place-items-center overflow-hidden bg-stone-100">{voucherImage(item, "h-full w-full object-contain transition duration-300 group-hover:scale-105")}</span><span className="block bg-white p-3"><span className="block truncate text-xs font-bold text-stone-900">{financeText(item.channel || item.evidence_type)}</span><span className="mt-1 block truncate text-[10px] text-stone-500">{item.business_date || "日期待补充"} · {financeText(item.evidence_type)}</span>{item.amount_minor != null && <span className="mt-2 block text-sm font-bold tabular-nums text-stone-950">{yuan(item.amount_minor)}</span>}</span></button>)}</div>}
      <ListPagination page={page} pageCount={pageCount} total={filtered.length} onChange={setPage} />
    </>}

    {hoverPreview && <div aria-hidden="true" className="pointer-events-none fixed z-[90] hidden w-56 animate-[fade-in-scale_180ms_cubic-bezier(0.16,1,0.3,1)_forwards] overflow-hidden rounded-xl border border-white/70 bg-white p-2 shadow-2xl md:block" style={{ left: hoverPreview.left, top: hoverPreview.top }}><div className="grid aspect-[3/4] place-items-center overflow-hidden rounded-lg bg-stone-100">{voucherImage(hoverPreview.item, "h-full w-full object-contain")}</div><div className="mt-2 flex items-center justify-center gap-1 text-[10px] font-semibold text-stone-600"><ZoomIn className="h-3 w-3" />点击查看高清原图</div></div>}

    {preview && <div role="dialog" aria-modal="true" aria-label="查看高清原始凭证" className="fixed inset-0 z-[100] flex items-center justify-center bg-stone-950/80 p-3 backdrop-blur-sm md:p-8" onClick={() => setPreview(null)}>
      <div className="relative grid max-h-[94vh] w-full max-w-6xl overflow-hidden rounded-2xl bg-white shadow-2xl md:grid-cols-[minmax(0,1fr)_280px]" onClick={(event) => event.stopPropagation()}>
        <button type="button" onClick={() => setPreview(null)} aria-label="关闭原图" className="absolute right-3 top-3 z-10 grid h-10 w-10 place-items-center rounded-full bg-stone-950/70 text-white shadow-lg transition hover:bg-stone-950 focus-visible:ring-2 focus-visible:ring-white"><X className="h-5 w-5" /></button>
        <div className="grid min-h-[50vh] place-items-center overflow-auto bg-stone-950 p-3 md:min-h-[72vh] md:p-6">{voucherImage(preview, "max-h-[82vh] max-w-full object-contain")}</div>
        <aside className="max-h-[38vh] overflow-y-auto border-t border-stone-200 p-5 md:max-h-[94vh] md:border-l md:border-t-0">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-octo-700">原始凭证</p><h3 className="mt-2 text-lg font-bold text-stone-950">{financeText(preview.channel || preview.evidence_type)}</h3>
          <p className="mt-3 text-2xl font-bold tabular-nums text-stone-950">{yuan(preview.amount_minor, "金额待补")}</p>
          <dl className="mt-5 space-y-3 text-xs"><div><dt className="text-stone-400">事实日期</dt><dd className="mt-1 font-semibold text-stone-800">{preview.business_date || "待补充"}</dd></div><div><dt className="text-stone-400">凭证类型</dt><dd className="mt-1 font-semibold text-stone-800">{financeText(preview.evidence_type)}</dd></div><div><dt className="text-stone-400">归档状态</dt><dd className="mt-1"><StatusPill status={preview.status} /></dd></div><div><dt className="text-stone-400">原始文件</dt><dd className="mt-1 break-all text-stone-700">{preview.original_filename}</dd></div><div><dt className="text-stone-400">凭证编号</dt><dd className="mt-1 break-all font-mono text-[10px] text-stone-600">{preview.voucher_number}</dd></div>{preview.notes && <div><dt className="text-stone-400">备注</dt><dd className="mt-1 leading-5 text-stone-700">{financeText(preview.notes)}</dd></div>}</dl>
          <p className="mt-6 rounded-lg bg-stone-100 px-3 py-2 text-[10px] leading-4 text-stone-500">点击图片外部、右上角关闭按钮或按 Esc 即可返回财务页。</p>
        </aside>
      </div>
    </div>}
  </section>;
}

function ReportsView({ overview, snapshot }: { overview: FinanceOverviewV1; snapshot: DailyFinanceSnapshotV1 }) {
  const periodLabel = overview.period_start === overview.period_end ? overview.period_end : `${overview.period_start} 至 ${overview.period_end}`;
  return <section className="grid gap-4 lg:grid-cols-3"><div className="rounded-xl border border-stone-200 bg-white p-4"><SectionTitle icon={CircleDollarSign} title="利润表" detail={periodLabel} /><div className="mt-3"><Metric label="营业收入" value={yuan(overview.revenue_minor)} /><Metric label="已确认经营成本" value={yuan(overview.known_operating_cost_minor, "¥0.00")} /><Metric label={overview.profit_status === "confirmed" ? "经营净利润" : "已录收支差额（非净利润）"} value={yuan(overview.net_profit_minor ?? overview.provisional_net_profit_minor)} strong /></div></div><div className="rounded-xl border border-stone-200 bg-white p-4"><SectionTitle icon={Banknote} title="资金流量" detail={periodLabel} /><div className="mt-3"><Metric label="经营活动" value={yuan(overview.cash_flow_minor.operating, "¥0.00")} /><Metric label="投资活动" value={yuan(overview.cash_flow_minor.investing, "¥0.00")} /><Metric label="筹资活动" value={yuan(overview.cash_flow_minor.financing, "¥0.00")} /><Metric label="资金净变动" value={yuan(overview.cash_flow_minor.net_change, "¥0.00")} strong /></div></div><div className="rounded-xl border border-stone-200 bg-white p-4"><SectionTitle icon={Landmark} title="资产与负债" detail={`截至 ${snapshot.selected_date}`} /><div className="mt-3"><Metric label="店铺可控资金账面值" value={yuan(snapshot.as_of.store_controlled_minor)} /><Metric label="银行卡实际余额" value="待银行流水核对" /><Metric label="库存账面" value={yuan(overview.assets_minor.inventory, "¥0.00")} /><Metric label="借款" value={yuan(snapshot.as_of.debt_outstanding_minor)} strong /></div></div></section>;
}

function ExportPanel({ overview }: { overview: FinanceOverviewV1 }) {
  return <section className="rounded-xl border border-stone-200 bg-white p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><SectionTitle icon={ArrowDownToLine} title="专业财务工作簿" detail={`${overview.period_start}—${overview.period_end}`} /><p className="mt-1 text-[11px] text-stone-500">按同一分类与资金口径导出，可筛选、可追溯凭证，也可交给会计继续处理。</p></div><a href={getFinanceExportUrl(DEFAULT_PROJECT_ID, overview.period_start, overview.period_end)} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-octo-700 px-4 text-xs font-semibold text-white"><ArrowDownToLine className="h-4 w-4" />下载 Excel</a></div></section>;
}

function DailyClosePanel({ snapshot, onSaved }: { snapshot: DailyFinanceSnapshotV1; onSaved: () => void }) {
  const [saving, setSaving] = useState(false);
  const [reopenReason, setReopenReason] = useState("");
  const inputs = snapshot.daily_close.inputs;
  const minorValue = (value: number | null | undefined) => value == null ? "" : String(value / 100);
  const [form, setForm] = useState({
    counted_cash: minorValue(inputs?.counted_cash_minor),
    reserve_cash: inputs?.reserve_cash_minor == null ? "500" : String(inputs.reserve_cash_minor / 100),
    merchant_net_confirmed: Boolean(inputs?.merchant_net_confirmed),
    fund_locations_reviewed: Boolean(inputs?.fund_locations_reviewed),
    outflows_reviewed: Boolean(inputs?.outflows_reviewed),
    food_cost: minorValue(inputs?.food_cost_minor),
    packaging_cost: minorValue(inputs?.packaging_cost_minor),
    overtime_hours: inputs?.overtime_hours == null ? "" : String(inputs.overtime_hours),
    rent: minorValue(inputs?.rent_minor),
    utility: minorValue(inputs?.utility_minor),
    other_cost: minorValue(inputs?.other_cost_minor),
  });
  const numberOrNull = (value: string) => value === "" ? null : Number(value);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      await saveFinanceDailyClose(snapshot.selected_date, {
        counted_cash: numberOrNull(form.counted_cash),
        reserve_cash: Number(form.reserve_cash || 0),
        merchant_net_confirmed: form.merchant_net_confirmed,
        fund_locations_reviewed: form.fund_locations_reviewed,
        outflows_reviewed: form.outflows_reviewed,
        food_cost: numberOrNull(form.food_cost),
        packaging_cost: numberOrNull(form.packaging_cost),
        overtime_hours: numberOrNull(form.overtime_hours),
        rent: numberOrNull(form.rent),
        utility: numberOrNull(form.utility),
        other_cost: numberOrNull(form.other_cost),
      });
      onSaved();
    } finally {
      setSaving(false);
    }
  }
  async function reopen() {
    setSaving(true);
    try {
      await reopenFinanceDailyClose(snapshot.selected_date, reopenReason);
      onSaved();
    } finally {
      setSaving(false);
    }
  }
  const closed = snapshot.daily_close.status === "closed";
  return <form onSubmit={submit} className="rounded-xl border border-stone-200 bg-white p-4">
    <SectionTitle icon={ClipboardCheck} title="截止日日结" detail={`${snapshot.selected_date} · ${closed ? "已完成" : "待核对"}`} />
    <div className="mt-3 space-y-2">{[["merchant_net_confirmed", "当日营业收入已核对"], ["fund_locations_reviewed", "资金位置已核对"], ["outflows_reviewed", "多渠道流出已核对"]].map(([key, label]) => <label key={key} className="flex min-h-10 items-center gap-2 rounded-lg border border-stone-200 px-3 text-xs text-stone-700"><input type="checkbox" disabled={closed} checked={Boolean(form[key as keyof typeof form])} onChange={(event) => setForm({ ...form, [key]: event.target.checked })} className="h-4 w-4 accent-emerald-700" />{label}</label>)}</div>
    <div className="mt-3 grid grid-cols-2 gap-2"><FormInput label="员工实点现金" type="number" disabled={closed} value={form.counted_cash} onChange={(value) => setForm({ ...form, counted_cash: value })} /><FormInput label="留存备用金" type="number" disabled={closed} value={form.reserve_cash} onChange={(value) => setForm({ ...form, reserve_cash: value })} /></div>
    <p className="mt-2 text-[11px] leading-5 text-stone-500">按店铺现行规则：实点现金减去固定 ¥500，再与客如云现金应收核对。</p>
    <p className="mt-4 text-xs font-semibold text-stone-700">利润成本（可后补）</p>
    <div className="mt-2 grid grid-cols-2 gap-2">
      <FormInput label="食材消耗" type="number" disabled={closed} value={form.food_cost} onChange={(value) => setForm({ ...form, food_cost: value })} />
      <FormInput label="包装消耗" type="number" disabled={closed} value={form.packaging_cost} onChange={(value) => setForm({ ...form, packaging_cost: value })} />
      <FormInput label="加班时数" type="number" disabled={closed} value={form.overtime_hours} onChange={(value) => setForm({ ...form, overtime_hours: value })} />
      <FormInput label="当日房租摊销" type="number" disabled={closed} value={form.rent} onChange={(value) => setForm({ ...form, rent: value })} />
      <FormInput label="当日水电" type="number" disabled={closed} value={form.utility} onChange={(value) => setForm({ ...form, utility: value })} />
      <FormInput label="其他成本" type="number" disabled={closed} value={form.other_cost} onChange={(value) => setForm({ ...form, other_cost: value })} />
    </div>
    {closed ? <div className="mt-3 flex gap-2"><FormInput label="重开原因" value={reopenReason} onChange={setReopenReason} /><button type="button" disabled={saving || reopenReason.trim().length < 2} onClick={() => void reopen()} className="mt-5 min-h-10 shrink-0 rounded-lg border border-amber-300 bg-amber-50 px-4 text-xs font-semibold text-amber-800 disabled:opacity-40">重开日结</button></div> : <button disabled={saving} className="mt-3 min-h-10 w-full rounded-lg bg-stone-900 text-xs font-semibold text-white disabled:opacity-40">{saving ? "保存中…" : "保存日结"}</button>}
  </form>;
}

function PendingPlans({ plans, vouchers, accounts, working, onResume, onEdit }: {
  plans: FinanceExecutionPlanV1[];
  vouchers: EvidenceVoucherV1[];
  accounts: FundAccountV1[];
  working: boolean;
  onResume: (planId: string) => void;
  onEdit: (plan: FinanceExecutionPlanV1) => void;
}) {
  const voucherFor = (plan: FinanceExecutionPlanV1) => {
    const reference = String(plan.input?.evidence_reference || plan.normalized_fact.evidence_reference || "");
    return vouchers.find((item) => item.id === reference || reference.includes(item.id));
  };
  return <section id="pending" className="rounded-xl border border-amber-200 bg-amber-50/70 p-4">
    <SectionTitle icon={RefreshCw} title="上次没有完成的记账" detail={`${plans.length}笔`} />
    <p className="mt-1 text-[11px] leading-5 text-amber-900">图片和识别结果已保留，断网或页面关闭不会丢失。请核对日期、金额、账户和归属后继续。</p>
    <div className="mt-3 grid gap-3 lg:grid-cols-2">
      {plans.map((plan) => {
        const voucher = voucherFor(plan);
        const sourceDate = plan.input?.transaction_date || plan.input?.business_date || plan.normalized_fact.transaction_date;
        const account = plan.input?.account_key || plan.normalized_fact.account_key;
        const accountName = accounts.find((item) => item.account_key === account)?.name || account;
        const canResume = plan.status === "awaiting_confirmation";
        return <article key={plan.plan_id} className="overflow-hidden rounded-xl border border-amber-200 bg-white">
          <div className="grid sm:grid-cols-[7rem_minmax(0,1fr)]">
            <div className="grid min-h-28 place-items-center overflow-hidden bg-stone-100">
              {voucher && isImageFile(voucher.original_filename)
                ? <a href={getEvidenceVoucherFileUrl(voucher.id)} target="_blank" rel="noreferrer" className="h-full w-full"><img src={getEvidenceVoucherFileUrl(voucher.id)} alt="打开原始凭证" className="h-full w-full object-contain" /></a>
                : <ReceiptText className="h-7 w-7 text-stone-400" />}
            </div>
            <div className="min-w-0 p-3">
              <div className="flex items-start justify-between gap-3"><div><p className="text-sm font-bold text-stone-950">{plan.title}</p><p className="mt-1 text-[11px] text-stone-500">{sourceDate} · {plan.input?.counterparty || plan.normalized_fact.counterparty || "交易对方待补"}</p></div><strong className="shrink-0 tabular-nums text-stone-950">{yuan(plan.normalized_fact.amount_minor)}</strong></div>
              <p className="mt-2 text-[11px] text-stone-600">资金账户：{String(accountName || "待选择")} · 归属：{plan.event_type === "personal_spending" ? "个人，不计入店铺利润" : "店铺"}</p>
              {plan.error_message && <p className="mt-2 text-[11px] text-rose-700">{plan.error_message}</p>}
              <div className="mt-3 flex gap-2"><button type="button" onClick={() => onEdit(plan)} className="min-h-9 flex-1 rounded-lg border border-stone-200 px-3 text-xs font-semibold text-stone-700">修改后重新识别</button><button type="button" disabled={working || !canResume} onClick={() => onResume(plan.plan_id)} className="min-h-9 flex-1 rounded-lg bg-stone-900 px-3 text-xs font-semibold text-white disabled:opacity-40">{canResume ? "确认并记入" : "需要补充信息"}</button></div>
            </div>
          </div>
        </article>;
      })}
    </div>
  </section>;
}

function FinanceIntakeDialog({ selectedDate, accounts, categories, initialCategoryGroup, onClose, onSaved, onError }: { selectedDate: string; accounts: FundAccountV1[]; categories: FinanceCategoryCatalogV1; initialCategoryGroup?: string | null; onClose: () => void; onSaved: (message: string) => Promise<void>; onError: (message: string) => void }) {
  const categoryItems = useMemo(() => flatFinanceCategories(categories), [categories]);
  const defaultGroup = categories.groups.some((group) => group.key === initialCategoryGroup) ? String(initialCategoryGroup) : "sales";
  const defaultCategory = categoryItems.find((item) => item.groupKey === defaultGroup) ?? categoryItems[0];
  const defaultAccount = defaultCategory?.business_scope === "personal"
    ? accounts.find((item) => item.owner_kind === "owner" && /招商/.test(`${item.institution || ""}${item.name}`))
    : accounts.find((item) => item.owner_kind === "store" && /工商/.test(`${item.institution || ""}${item.name}`))
      ?? accounts.find((item) => item.owner_kind === "store");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [statement, setStatement] = useState("");
  const [textParse, setTextParse] = useState<FinanceTextParseV1 | null>(null);
  const [parsingText, setParsingText] = useState(false);
  const [textParseError, setTextParseError] = useState<string | null>(null);
  const [recognition, setRecognition] = useState<Awaited<ReturnType<typeof recognizeCapture>> | null>(null);
  const [recognizing, setRecognizing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [plan, setPlan] = useState<FinanceExecutionPlanV1 | null>(null);
  const [form, setForm] = useState({
    fact_type: factTypeForFinanceCategory(defaultCategory),
    business_date: selectedDate,
    amount: "",
    channel: "",
    settlement_state: "",
    account_key: defaultAccount?.account_key ?? "",
    counter_account_key: "",
    category_code: defaultCategory?.account_code ?? "",
    category_name: defaultCategory?.name ?? "待选择",
    business_category_key: defaultCategory?.key ?? "",
    source_basis: "手工录入",
    counterparty: "",
    business_period_start: `${selectedDate.slice(0, 8)}01`,
    business_period_end: selectedDate,
    platforms: "美团外卖,淘宝闪购,京东外卖,抖音团购",
    notes: "",
  });
  const [categoryGroup, setCategoryGroup] = useState(defaultGroup);
  const categoryGroupItems = categoryItems.filter((item) => item.groupKey === categoryGroup);

  function selectCategory(key: string) {
    const category = categoryItems.find((item) => item.key === key);
    if (!category) return;
    setCategoryGroup(category.groupKey);
    const factType = factTypeForFinanceCategory(category);
    change({
      business_category_key: category.key,
      category_code: category.account_code || "",
      category_name: category.name,
      fact_type: factType,
      settlement_state: factType === "merchant_net_sale" ? form.settlement_state : "",
    });
  }

  function change(values: Partial<typeof form>) {
    setPlan(null);
    setForm((current) => ({ ...current, ...values }));
  }

  function suggestedCategory(source: string, rawText: string) {
    const content = `${source} ${rawText}`;
    const key = /电网|电力|电费|水费|水电|燃气/.test(content)
      ? "utilities"
      : /进货|采购|供应商|原料|食材/.test(content)
        ? "food_purchase"
        : /房租|商场费/.test(content)
          ? "rent_mall_fee"
          : /工资|加班|临时工/.test(content)
            ? "employee_wage"
            : /(美团|淘宝|闪购|京东|抖音|客如云|POS).*(结算|提现|商家钱包|到账)/.test(content)
              ? "platform_wallet_credit"
              : /(美团|淘宝|闪购|京东|抖音|客如云|POS).*(营业额|销售|实收|收入)/.test(content)
                ? "delivery_sales"
                : null;
    return key ? categoryItems.find((item) => item.key === key) || null : null;
  }

  useEffect(() => {
    const text = statement.trim();
    if (text.length < 4) {
      setTextParse(null);
      setTextParseError(null);
      return;
    }
    let active = true;
    const timer = window.setTimeout(async () => {
      setParsingText(true);
      setTextParseError(null);
      try {
        const parsed = await parseFinanceIntakeText(text);
        if (!active) return;
        setTextParse(parsed);
        const parsedCategory = categoryItems.find((item) => item.key === parsed.fields.business_category_key);
        if (parsedCategory) setCategoryGroup(parsedCategory.groupKey);
        setPlan(null);
        setForm((current) => ({
          ...current,
          fact_type: parsed.fields.fact_type || current.fact_type,
          business_date: parsed.fields.business_date || current.business_date || selectedDate,
          amount: parsed.fields.amount == null ? "" : String(parsed.fields.amount),
          account_key: parsed.fields.account_key || "",
          counter_account_key: "",
          category_code: parsed.fields.category_code || "",
          category_name: parsed.fields.category_name || "",
          business_category_key: parsed.fields.business_category_key || "",
          counterparty: parsed.fields.counterparty || "",
          source_basis: parsed.fields.source_basis,
          notes: parsed.fields.notes
            ? parsed.fields.notes + "；原话：" + parsed.original_text
            : "原话：" + parsed.original_text,
        }));
      } catch (cause) {
        if (active) setTextParseError(cause instanceof Error ? cause.message : "这句话暂时无法自动填写");
      } finally {
        if (active) setParsingText(false);
      }
    }, 650);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [statement, categoryItems, selectedDate]);

  async function inspect(nextFile: File) {
    setFile(nextFile); setPreviewUrl(URL.createObjectURL(nextFile)); setRecognition(null); setPlan(null); setRecognizing(true);
    try {
      const result = await recognizeCapture(nextFile);
      setRecognition(result);
      const valueFor = (...keys: string[]) => result.fields.find((field) => keys.includes(field.key))?.value;
      const date = valueFor("date");
      const amount = valueFor("amount", "delivery_revenue", "revenue");
      const source = result.source_type || "图片凭证";
      const rawText = result.raw_text || "";
      const isFormerOwnerReceipt = source === "银行转账凭证" && /(?:9863|前老板)/.test(rawText);
      const recognizedCategory = isFormerOwnerReceipt
        ? categoryItems.find((item) => item.key === "former_owner_transfer") || null
        : suggestedCategory(source, rawText);
      const period = rawText.match(/(\d{1,2})\s*[.月/-]\s*(\d{1,2})\s*[—一至~-]+\s*(\d{1,2})\s*[.月/-]\s*(\d{1,2})/);
      const year = (typeof date === "string" ? date : selectedDate).slice(0, 4);
      const storeIcbcAccount = accounts.find((item) => item.account_key === "planned-store-icbc")
        || accounts.find((item) => item.owner_kind === "store" && /工商/.test(`${item.institution || ""}${item.name}`));
      if (recognizedCategory) setCategoryGroup(recognizedCategory.groupKey);
      setForm((current) => ({
        ...current,
        fact_type: recognizedCategory ? factTypeForFinanceCategory(recognizedCategory) : "categorized_transaction",
        business_category_key: recognizedCategory?.key || "",
        category_code: recognizedCategory?.account_code || "",
        category_name: recognizedCategory?.name || "",
        business_date: typeof date === "string" ? date : selectedDate,
        amount: amount == null ? current.amount : String(amount),
        account_key: isFormerOwnerReceipt ? (storeIcbcAccount?.account_key || current.account_key) : current.account_key,
        counterparty: isFormerOwnerReceipt ? "前老板" : String(valueFor("counterparty") || current.counterparty),
        business_period_start: period ? `${year}-${period[1].padStart(2, "0")}-${period[2].padStart(2, "0")}` : current.business_period_start,
        business_period_end: period ? `${year}-${period[3].padStart(2, "0")}-${period[4].padStart(2, "0")}` : current.business_period_end,
        source_basis: source,
      }));
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "图片识别失败；请保留图片后手动填写可确认字段。");
    } finally { setRecognizing(false); }
  }

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  function clipboardFile(event: React.ClipboardEvent) {
    const image = Array.from(event.clipboardData.items)
      .find((item) => item.kind === "file" && item.type.startsWith("image/"))
      ?.getAsFile();
    if (image) {
      event.preventDefault();
      void inspect(image);
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      const result = await createFinanceIntake({
        ...form,
        account_key: merchant ? undefined : form.account_key,
        counter_account_key: selectedCategory?.transaction_kind === "account_transfer" ? form.counter_account_key : undefined,
        current_account_key: merchant ? form.account_key : undefined,
        business_period_start: formerOwner ? form.business_period_start : undefined,
        business_period_end: formerOwner ? form.business_period_end : undefined,
        platforms: formerOwner ? form.platforms : undefined,
        amount: Number(form.amount),
        file,
      });
      if (result.plan.status === "blocked" || result.plan.status === "needs_input") {
        setPlan(result.plan);
        return;
      }
      const executed = await confirmFinanceExecutionPlan(result.plan.plan_id);
      await onSaved(
        executed.plan.event_type === "merchant_net_sale"
          ? "已记入：营业收入、资金位置和原始凭证已同步更新。"
          : "已记入：资金流、台账、到账核对和原始凭证已同步更新。",
      );
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "财务事实保存失败");
    } finally { setSaving(false); }
  }

  const merchant = form.fact_type === "merchant_net_sale";
  const formerOwner = form.fact_type === "former_owner_transfer";
  const needsAccount = !merchant;
  const selectedCategory = categoryItems.find((item) => item.key === form.business_category_key);
  const recognitionSummary = recognition?.fields
    .filter((field) => ["date", "amount", "delivery_revenue", "revenue"].includes(field.key))
    .map((field) => `${field.label} ${String(field.value)}`)
    .join(" · ");
  const selectedGroupName = initialCategoryGroup
    ? categories.groups.find((group) => group.key === initialCategoryGroup)?.name
    : null;

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center overflow-y-auto bg-stone-950/45 p-4 backdrop-blur-sm">
      <form
        onSubmit={(event) => void submit(event)}
        onPaste={clipboardFile}
        className="box-border min-w-0 overflow-y-auto rounded-2xl bg-white p-5 shadow-2xl"
        style={{ width: "min(100%, 42rem)", maxHeight: "calc(100dvh - 2rem)" }}
      >
        <div className="flex items-center justify-between gap-4 border-b border-stone-100 pb-4">
          <div><h2 className="text-lg font-bold text-stone-950">{selectedGroupName ? `记一笔 · ${selectedGroupName}` : "智能录入"}</h2><p className="mt-1 text-[11px] text-stone-500">{selectedGroupName ? "按台账分类填写必要信息；确认后同步更新台账、资金与凭证。" : "系统先识别并自动填写；你只需确认一次，台账、资金和凭证同步更新。"}</p></div>
          <button type="button" onClick={onClose} aria-label="关闭财务录入" className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-stone-500 hover:bg-stone-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        {!initialCategoryGroup && <><label className="mt-4 block">
          <span className="text-xs font-medium text-stone-700">直接说这笔账，系统会自动填写</span>
          <textarea value={statement} onChange={(event) => setStatement(event.target.value)} className="mt-1 min-h-20 w-full rounded-xl border border-stone-200 px-3 py-2.5 text-sm outline-none focus:border-octo-500" placeholder="" />
        </label>

        {parsingText && <div className="mt-3 flex items-center gap-2 rounded-xl bg-stone-50 px-3 py-2.5 text-xs text-stone-600"><Loader2 className="h-4 w-4 animate-spin" />正在自动填写金额、日期、类型、账户和用途…</div>}
        {textParseError && <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2.5 text-xs text-rose-800">{textParseError}，你仍可以在下面手动补充。</div>}
        {textParse && !parsingText && (
          <div className={`mt-3 rounded-xl border p-3 ${textParse.can_confirm ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-bold text-stone-900">{textParse.can_confirm ? "已自动填写，可以直接确认" : "已自动填写，还缺少少量信息"}</p>
              <span className="rounded-full bg-white px-2 py-1 text-[10px] font-semibold text-stone-600">
                {textParse.business_scope === "personal" ? "个人资金" : textParse.business_scope === "store" ? "店铺资金" : "归属待补"}
              </span>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-stone-700">
              {textParse.fields.amount != null && <span className="rounded-md bg-white px-2 py-1">金额 {yuan(Math.round(textParse.fields.amount * 100))}</span>}
              {textParse.fields.business_date && <span className="rounded-md bg-white px-2 py-1">日期 {textParse.fields.business_date}</span>}
              {textParse.account_name && <span className="rounded-md bg-white px-2 py-1">{textParse.account_name}</span>}
              {textParse.fields.counterparty && <span className="rounded-md bg-white px-2 py-1">交易方 {textParse.fields.counterparty}</span>}
              {textParse.fields.notes && <span className="rounded-md bg-white px-2 py-1">{textParse.fields.notes}</span>}
            </div>
            <p className="mt-2 text-[11px] leading-5 text-stone-600">
              {textParse.profit_treatment === "excluded_personal" ? "个人消费：只记录个人资金去向，不进入店铺收入、成本或利润。" :
                textParse.profit_treatment === "inventory_not_expensed" ? "店铺进货：先进入库存，实际耗用时再进入成本。" :
                textParse.profit_treatment === "store_profit_effect" ? "店铺经营支出：确认后进入对应成本。" :
                "系统已按资金事实预填，确认前不会写账。"}
            </p>
            {textParse.missing_fields.length > 0 && <p className="mt-2 text-[11px] font-semibold text-amber-800">还需补充：{textParse.missing_fields.map((field) => ({ business_date: "实际交易日期", amount: "金额", account_key: "收付款账户", fact_type: "账目类型" }[field] || field)).join("、")}</p>}
          </div>
        )}</>}

        <div className="mt-4 grid gap-3 border-t border-stone-100 pt-4 sm:grid-cols-2">
          <FormSelect label="大类" value={categoryGroup} onChange={(value) => { const first = categoryItems.find((item) => item.groupKey === value); setCategoryGroup(value); if (first) selectCategory(first.key); }} options={categories.groups.map((group) => ({ value: group.key, label: group.name }))} />
          <FormSelect label="具体类别" value={form.business_category_key} onChange={selectCategory} options={categoryGroupItems.map((item) => ({ value: item.key, label: item.name }))} />
          <FormInput label="日期" type="date" value={form.business_date} onChange={(value) => change({ business_date: value })} />
          <FormInput label="金额" type="number" value={form.amount} onChange={(value) => change({ amount: value })} />
          {merchant ? (
            <FormSelect label="渠道" value={form.channel} onChange={(value) => change({ channel: value })} options={[{ value: "", label: "请选择" }, { value: "客如云收款", label: "客如云收款" }, { value: "美团外卖", label: "美团外卖" }, { value: "美团团购", label: "美团团购" }, { value: "淘宝闪购", label: "淘宝闪购" }, { value: "京东外卖", label: "京东外卖" }, { value: "抖音团购", label: "抖音团购" }, { value: "现金", label: "现金" }]} />
          ) : (
            <FormSelect label="收付款账户" value={form.account_key} onChange={(value) => change({ account_key: value })} options={[{ value: "", label: "请选择" }, ...accounts.map((item) => ({ value: item.account_key, label: item.name }))]} />
          )}
          {selectedCategory?.transaction_kind === "account_transfer" && <FormSelect label="转入账户" value={form.counter_account_key} onChange={(value) => change({ counter_account_key: value })} options={[{ value: "", label: "请选择" }, ...accounts.filter((item) => item.account_key !== form.account_key).map((item) => ({ value: item.account_key, label: item.name }))]} />}
          {merchant && <>
            <FormSelect label="资金位置" value={form.settlement_state} onChange={(value) => change({ settlement_state: value })} options={[{ value: "", label: "请选择" }, { value: "wallet_credited", label: "平台钱包" }, { value: "former_owner_pending_transfer", label: "前老板代收" }, { value: "store_account_received", label: "店铺账户" }, { value: "unknown", label: "待核对" }]} />
            <FormSelect label="当前账户（可选）" value={form.account_key} onChange={(value) => change({ account_key: value })} options={[{ value: "", label: "未绑定店铺账户" }, ...accounts.map((item) => ({ value: item.account_key, label: item.name }))]} />
          </>}
          {formerOwner && <>
            <FormInput label="核销起始日" type="date" value={form.business_period_start} onChange={(value) => change({ business_period_start: value })} />
            <FormInput label="核销截止日" type="date" value={form.business_period_end} onChange={(value) => change({ business_period_end: value })} />
          </>}
          <FormInput label="交易对方" value={form.counterparty} onChange={(value) => change({ counterparty: value })} placeholder="选填" />
        </div>

        <div className="mt-4 rounded-xl border border-dashed border-stone-300 bg-stone-50 p-4"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => { event.preventDefault(); const dropped = event.dataTransfer.files?.[0]; if (dropped) void inspect(dropped); }}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-stone-800">粘贴、拖入或上传原始凭证</p>
              {!file && <p className="mt-1 text-[11px] text-stone-500">在这个窗口直接 Ctrl/Command + V，或把图片拖到这里</p>}
              {file && <p className="mt-1 truncate text-[11px] text-stone-500">{file.name}{recognitionSummary ? ` · ${recognitionSummary}` : ""}</p>}
            </div>
            <label className="cursor-pointer rounded-lg border border-stone-200 bg-white px-3 py-2 text-xs font-semibold text-stone-700 hover:bg-stone-100">
              {file ? "更换文件" : "选择文件"}
              <input type="file" accept="image/*" className="sr-only" onChange={(event) => { const picked = event.target.files?.[0]; if (picked) void inspect(picked); }} />
            </label>
          </div>
          {previewUrl && <button type="button" onClick={() => setPreviewOpen(true)} className="mt-3 block w-full overflow-hidden rounded-xl border border-stone-200 bg-white"><img src={previewUrl} alt="待录入原始凭证预览" className="max-h-64 w-full object-contain" /></button>}
          {recognizing && <p className="mt-2 flex items-center gap-2 text-[11px] text-stone-500"><Loader2 className="h-3.5 w-3.5 animate-spin" />正在提取信息；原图已保留，可先手动确认</p>}
        </div>

        {plan && (
          <div className={`mt-4 rounded-xl border p-3 ${plan.status === "blocked" ? "border-rose-200 bg-rose-50" : "border-emerald-200 bg-emerald-50"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-bold text-stone-900">{plan.title} · {yuan(plan.normalized_fact.amount_minor)}</p>
              <span className="rounded-full bg-white px-2 py-1 text-[10px] font-semibold text-stone-600">需要补信息</span>
            </div>
            <p className="mt-2 text-[11px] leading-5 text-stone-600">{plan.accounting_effect.explanation}</p>
            <div className="mt-2 space-y-1">
              {plan.checks.map((check) => <p key={check.code} className={`text-[11px] ${check.status === "failed" ? "text-rose-700" : "text-emerald-800"}`}>{check.status === "failed" ? "未通过" : "已通过"} · {check.message}</p>)}
            </div>
            {plan.next_steps?.map((step) => <p key={step.action} className="mt-2 rounded-lg bg-white/80 p-2 text-[11px] leading-5 text-amber-800">下一步 · {step.message}</p>)}
            {plan.reconciliation.allocations.length > 0 && (
              <div className="mt-3 border-t border-emerald-200 pt-2 text-[11px] text-stone-600">
                {plan.reconciliation.allocations.map((row) => <p key={row.target_id}>{row.platform} · {row.business_date} · {yuan(row.amount_minor)}</p>)}
                <p className="mt-1 font-semibold text-stone-800">合计 {yuan(plan.reconciliation.matched_minor)} · 差额 {yuan(plan.reconciliation.difference_minor)}</p>
              </div>
            )}
          </div>
        )}

        <div className="mt-3 flex gap-3">
          <button type="button" onClick={onClose} className="min-h-11 flex-1 rounded-lg border border-stone-200 text-sm font-semibold text-stone-700">取消</button>
          <button disabled={saving || !form.business_category_key || !form.business_date || !form.amount || (merchant && (!form.channel || !form.settlement_state)) || (needsAccount && !form.account_key) || (selectedCategory?.transaction_kind === "account_transfer" && !form.counter_account_key)} className="min-h-11 flex-[1.35] rounded-lg bg-octo-700 text-sm font-semibold text-white disabled:opacity-40">{saving ? "正在记入…" : "确认记入"}</button>
        </div>
      </form>
      {previewOpen && previewUrl && <div role="dialog" aria-label="查看原始凭证" className="fixed inset-0 z-[90] grid place-items-center bg-stone-950/85 p-4" onClick={() => setPreviewOpen(false)}><button type="button" aria-label="关闭原图" className="absolute right-5 top-5 grid h-11 w-11 place-items-center rounded-full bg-white/10 text-white"><X className="h-6 w-6" /></button><img src={previewUrl} alt="原始凭证大图" className="max-h-[92vh] max-w-[96vw] object-contain" onClick={(event) => event.stopPropagation()} /></div>}
    </div>
  );
}

function EntryDialog({ selectedDate, accounts, categories, records, editing, working, onClose, onSaved, onError, setWorking }: { selectedDate: string; accounts: FundAccountV1[]; categories: FinanceCategoryCatalogV1; records: BookkeepingRecordV1[]; editing: BookkeepingRecordV1 | null; working: boolean; onClose: () => void; onSaved: (message: string) => Promise<void>; onError: (message: string) => void; setWorking: (value: boolean) => void }) {
  const categoryItems = flatFinanceCategories(categories);
  const inferred = categoryItems.find((item) => item.key === editing?.business_category_key)
    ?? categoryItems.find((item) => item.transaction_kind === editing?.transaction_kind && item.account_code === (editing?.category_code ?? null))
    ?? categoryItems[0];
  const [optionKey, setOptionKey] = useState(inferred.key); const option = categoryItems.find((item) => item.key === optionKey) ?? categoryItems[0];
  const [amount, setAmount] = useState(editing ? String(editing.amount_minor / 100) : ""); const [account, setAccount] = useState(editing?.account_key ?? accounts.find((item) => item.is_store_controlled)?.account_key ?? accounts[0]?.account_key ?? ""); const [counterAccount, setCounterAccount] = useState(editing?.counter_account_key ?? ""); const [counterparty, setCounterparty] = useState(editing?.counterparty ?? ""); const [summary, setSummary] = useState(editing?.summary ?? "");
  const [allowDuplicate, setAllowDuplicate] = useState(false);
  const [duplicateToken, setDuplicateToken] = useState("first");
  const amountMinor = Math.round(Number(amount || 0) * 100);
  const possibleDuplicate = editing ? null : records.find((record) =>
    record.transaction_date === selectedDate
    && record.amount_minor === amountMinor
    && record.direction === option.direction
    && record.transaction_kind === option.transaction_kind
    && (record.category_code ?? null) === option.account_code
    && (record.account_key ?? "") === account
    && (record.counter_account_key ?? "") === (option.transaction_kind === "account_transfer" ? counterAccount : "")
    && record.status !== "rejected"
    && record.status !== "duplicate"
  ) ?? null;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (possibleDuplicate && !allowDuplicate) return;
    setWorking(true);
    try {
      if (editing) {
        await reviewBookkeepingRecord(editing.id, { transaction_kind: option.transaction_kind, business_scope: option.business_scope, category_code: option.account_code, category_name: option.name, business_category_key: option.key, account_key: account, counter_account_key: option.transaction_kind === "account_transfer" ? counterAccount : null, counterparty, summary });
        await confirmBookkeepingRecord(editing.id);
      } else {
        const stableReference = [
          "manual",
          selectedDate,
          option.direction,
          option.transaction_kind,
          option.account_code ?? "none",
          account,
          option.transaction_kind === "account_transfer" ? counterAccount : "none",
          amountMinor,
          counterparty.trim() || "none",
          summary.trim() || "none",
          allowDuplicate ? duplicateToken : "first",
        ].join(":");
        const created = await createBookkeepingRecord({ transaction_date: selectedDate, direction: option.direction, amount: Number(amount), transaction_kind: option.transaction_kind, business_scope: option.business_scope, category_code: option.account_code, category_name: option.name, business_category_key: option.key, account_key: account, counter_account_key: option.transaction_kind === "account_transfer" ? counterAccount : null, counterparty, summary, source_reference: stableReference });
        await confirmBookkeepingRecord(created.record.id);
      }
      await onSaved(editing ? "信息已补齐并记入，资金流和台账已同步更新。" : "已记入，资金位置、台账和相关报表已同步更新。");
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "记账失败");
    } finally {
      setWorking(false);
    }
  }
  return <div className="fixed inset-0 z-50 flex items-end justify-center bg-stone-950/35 p-0 backdrop-blur-[2px] sm:items-center sm:p-4"><form onSubmit={submit} className="max-h-[92vh] w-full overflow-y-auto rounded-t-2xl bg-white p-5 shadow-2xl sm:max-w-xl sm:rounded-2xl"><div className="flex items-center justify-between"><div><p className="text-base font-bold text-stone-950">{editing ? "补充资金信息" : "记一笔资金"}</p><p className="mt-1 text-[11px] text-stone-500">确认后直接进入资金流和台账，不再增加第二次复核。</p></div><button type="button" onClick={onClose} aria-label="关闭记账"><X className="h-5 w-5 text-stone-500" /></button></div><div className="mt-5 grid gap-3 sm:grid-cols-2"><FormSelect label="财务分类" value={optionKey} onChange={(value) => { setAllowDuplicate(false); setOptionKey(value); }} options={categoryItems.map((item) => ({ value: item.key, label: `${item.groupName}｜${item.name}` }))} /><FormInput label="金额" type="number" value={amount} onChange={(value) => { setAllowDuplicate(false); setAmount(value); }} disabled={Boolean(editing)} /><FormSelect label="钱从哪个账户收付" value={account} onChange={(value) => { setAllowDuplicate(false); setAccount(value); }} options={accounts.map((item) => ({ value: item.account_key, label: item.name }))} />{option.transaction_kind === "account_transfer" && <FormSelect label="钱转到哪里" value={counterAccount} onChange={(value) => { setAllowDuplicate(false); setCounterAccount(value); }} options={[{ value: "", label: "请选择另一个账户" }, ...accounts.filter((item) => item.account_key !== account).map((item) => ({ value: item.account_key, label: item.name }))]} />}<FormInput label="钱付给谁 / 从谁收到" value={counterparty} onChange={setCounterparty} placeholder="供应商、员工、平台…" /><label className="block sm:col-span-2"><span className="text-xs font-medium text-stone-600">这笔钱的用途</span><textarea value={summary} onChange={(event) => setSummary(event.target.value)} className="mt-1 min-h-20 w-full rounded-lg border border-stone-200 px-3 py-2 text-sm outline-none focus:border-octo-500 focus:ring-2 focus:ring-octo-100" placeholder="例如：7月员工工资、第一批食材、老板个人取用" /></label></div>{possibleDuplicate && <label className="mt-4 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900"><input type="checkbox" checked={allowDuplicate} onChange={(event) => { const checked = event.target.checked; setAllowDuplicate(checked); if (checked) setDuplicateToken(String(Date.now())); }} className="mt-0.5 h-4 w-4 accent-octo-700" /><span>发现同日同金额、同类型、同账户记录。只有确认这是另一笔钱才再次记入。</span></label>}<div className="mt-5 flex gap-2"><button type="button" onClick={onClose} className="min-h-11 flex-1 rounded-lg border border-stone-200 text-sm font-semibold text-stone-700">取消</button><button disabled={working || !amount || !account || (option.transaction_kind === "account_transfer" && !counterAccount) || Boolean(possibleDuplicate && !allowDuplicate)} className="min-h-11 flex-[1.4] rounded-lg bg-octo-700 text-sm font-semibold text-white disabled:opacity-40">{working ? "正在记入…" : "确认记入"}</button></div></form></div>;
}

type FinanceChatMessage = { role: "user" | "assistant"; content: string; result?: FinanceQueryV1 };

function FinanceAgentDrawer({ overview, selectedDate, initialQuery, onFinanceChanged, onClose }: { overview: FinanceOverviewV1; selectedDate: string; initialQuery?: string; onFinanceChanged: () => Promise<void>; onClose: () => void }) {
  const reduceMotion = useReducedMotion();
  const [query, setQuery] = useState(initialQuery || "");
  const [messages, setMessages] = useState<FinanceChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messageEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const questions = ["这段时间赚了多少钱？", "哪些钱还没到店铺账户？", "目前最缺哪些成本资料？", "资金够不够付工资和房租？"];

  useEffect(() => {
    const stored = window.localStorage.getItem("zhanggui:finance-agent-session") || undefined;
    setSessionId(stored);
    if (!stored) return;
    void getAgentSession(stored).then(({ session }: { session: AgentSessionV1 }) => {
      if (session.scope !== "finance") return;
      setMessages(session.messages.filter((item) => item.role !== "system").map((item) => ({ role: item.role as "user" | "assistant", content: item.content })));
    }).catch(() => window.localStorage.removeItem("zhanggui:finance-agent-session"));
  }, []);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "end" });
  }, [messages, loading, reduceMotion]);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", closeOnEscape);
    const focusTimer = window.setTimeout(() => textareaRef.current?.focus(), 260);
    return () => { window.removeEventListener("keydown", closeOnEscape); window.clearTimeout(focusTimer); };
  }, [onClose]);

  function newConversation() {
    window.localStorage.removeItem("zhanggui:finance-agent-session");
    setSessionId(undefined); setMessages([]); setError(null); setQuery("");
  }

  async function ask(text: string) {
    const value = text.trim();
    if (!value) return;
    setQuery(""); setMessages((current) => [...current, { role: "user", content: value }]); setLoading(true); setError(null);
    try {
      const result = await queryFinanceAgent(value, overview.period_start, selectedDate, sessionId);
      if (result.session_id) {
        setSessionId(result.session_id);
        window.localStorage.setItem("zhanggui:finance-agent-session", result.session_id);
      }
      setMessages((current) => [...current, { role: "assistant", content: result.answer, result }]);
      if (result.execution_plan) await onFinanceChanged();
    } catch (cause) {
      setMessages((current) => current.slice(0, -1)); setQuery(value);
      setError(cause instanceof Error ? cause.message : "财务分析暂时不可用");
    } finally {
      setLoading(false);
    }
  }

  function handleComposerKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    const composing = event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229;
    if (event.key === "Enter" && !event.shiftKey && !composing) {
      event.preventDefault();
      if (!loading && query.trim()) void ask(query);
    }
  }

  return <motion.div initial={reduceMotion ? false : { opacity: 0 }} animate={{ opacity: 1 }} exit={reduceMotion ? undefined : { opacity: 0 }} transition={{ duration: .24 }} className="finance-agent-overlay" onClick={onClose}>
    <motion.aside initial={reduceMotion ? false : { opacity: 0, x: 42, scale: .985 }} animate={{ opacity: 1, x: 0, scale: 1 }} exit={reduceMotion ? undefined : { opacity: 0, x: 34, scale: .988 }} transition={{ type: "spring", stiffness: 360, damping: 36, mass: .85 }} className="finance-agent-panel" role="dialog" aria-modal="true" aria-label="财务 Agent" onClick={(event) => event.stopPropagation()}>
      <div aria-hidden="true" className="finance-agent-ambient finance-agent-ambient-one" /><div aria-hidden="true" className="finance-agent-ambient finance-agent-ambient-two" />
      <header className="finance-agent-header">
        <div className="flex min-w-0 items-center gap-3"><span className="relative grid h-11 w-11 shrink-0 place-items-center rounded-2xl border border-white/90 bg-white/72 text-octo-700 shadow-[0_8px_24px_rgba(122,52,24,.10)] backdrop-blur-xl"><CircleDollarSign className="h-5 w-5" /><span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white bg-emerald-500" /></span><div className="min-w-0"><div className="flex items-center gap-2"><h2 className="text-[17px] font-semibold tracking-[-.02em] text-stone-950">财务 Agent</h2><span className="rounded-full border border-emerald-200/70 bg-emerald-50/75 px-2 py-0.5 text-[9px] font-semibold text-emerald-700">在线</span></div><p className="mt-0.5 truncate text-[11px] text-stone-500">{overview.period_start} 至 {selectedDate} · 台账与凭证事实</p></div></div>
        <div className="flex shrink-0 items-center gap-1"><button type="button" onClick={newConversation} className="rounded-xl px-3 py-2 text-xs font-medium text-stone-600 transition duration-200 hover:bg-white/70 hover:text-octo-800">新对话</button><button type="button" onClick={onClose} aria-label="关闭财务Agent" className="grid h-9 w-9 place-items-center rounded-xl text-stone-500 transition duration-200 hover:bg-white/75 hover:text-stone-900"><X className="h-[18px] w-[18px]" /></button></div>
      </header>
      <div className="finance-agent-body">
        {messages.length === 0 && <motion.div initial={reduceMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: .12, duration: .32 }} className="finance-agent-welcome"><div className="flex items-center gap-2 text-octo-800"><Sparkles className="h-4 w-4" /><span className="text-[11px] font-semibold">这家店的专属财务工作台</span></div><p className="mt-3 text-[15px] font-semibold tracking-[-.01em] text-stone-900">你问结论，我去核对账目和凭证</p><p className="mt-1.5 text-xs leading-5 text-stone-500">收入、到账、支出、成本和利润会分开计算；没有资料时会明确告诉你缺什么。</p></motion.div>}
        {messages.length === 0 && <motion.div initial={reduceMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: .18, duration: .32 }} className="mt-4 grid grid-cols-2 gap-2">{questions.map((item) => <button key={item} type="button" onClick={() => void ask(item)} className="finance-agent-prompt">{item}<span aria-hidden="true">↗</span></button>)}</motion.div>}
        <div className="mt-2 space-y-5">{messages.map((message, index) => <motion.div initial={reduceMotion ? false : { opacity: 0, y: 8, scale: .99 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: .26, ease: [0.22, 1, 0.36, 1] }} key={`${message.role}-${index}`} className={message.role === "user" ? "flex justify-end" : "flex items-start gap-2.5 justify-start"}>{message.role === "assistant" && <span className="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-xl border border-white/80 bg-white/68 text-octo-700 shadow-sm backdrop-blur-xl"><CircleDollarSign className="h-4 w-4" /></span>}<div className={message.role === "user" ? "finance-agent-bubble-user" : "finance-agent-bubble-assistant"}><div className="whitespace-pre-line">{financeText(message.content).replaceAll("**", "")}</div>{message.result?.execution_plan?.status === "awaiting_confirmation" && <motion.button whileHover={reduceMotion ? undefined : { y: -1 }} whileTap={reduceMotion ? undefined : { scale: .98 }} type="button" onClick={() => void ask("确认执行")} disabled={loading} className="mt-3 inline-flex min-h-9 items-center gap-2 rounded-xl bg-octo-700 px-3.5 text-xs font-semibold text-white shadow-[0_7px_18px_rgba(154,52,18,.18)] transition-colors hover:bg-octo-800 disabled:opacity-50"><Check className="h-3.5 w-3.5" />确认执行</motion.button>}{message.result?.conversation_mode === "finance" && <details className="mt-3 border-t border-stone-200/60 pt-2"><summary className="cursor-pointer select-none text-[11px] font-medium text-stone-500 transition hover:text-octo-700">事实依据与核对过程</summary><div className="mt-2 space-y-2 text-[11px] leading-5 text-stone-500">{message.result.skills_used?.map((skill) => <p key={skill.name}>{skill.description}</p>)}{message.result.sources?.map((source, sourceIndex) => <p key={`${source.label}-${sourceIndex}`}>{source.label}{source.reference ? ` · ${source.reference}` : ""}</p>)}{message.result.warnings?.map((warning) => <p key={warning} className="text-amber-700">{financeText(warning)}</p>)}{message.result.handoff && <p className="text-sky-700">建议交给{message.result.handoff.target_agent}：{message.result.handoff.reason}</p>}</div></details>}</div></motion.div>)}</div>
        {loading && <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-5 flex items-start gap-2.5"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl border border-white/80 bg-white/68 text-octo-700 shadow-sm backdrop-blur-xl"><CircleDollarSign className="h-4 w-4" /></span><div className="finance-agent-thinking"><div className="flex items-center gap-1.5"><span className="finance-agent-thinking-dot" /><span className="finance-agent-thinking-dot [animation-delay:140ms]" /><span className="finance-agent-thinking-dot [animation-delay:280ms]" /></div><span>正在理解并核对财务事实…</span></div></motion.div>}
        {error && <motion.p initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="mt-5 rounded-2xl border border-red-200/70 bg-red-50/75 p-3 text-sm text-red-800 backdrop-blur-xl">{error}</motion.p>}
        <div ref={messageEndRef} className="h-1" />
      </div>
      <form onSubmit={(event) => { event.preventDefault(); void ask(query); }} className="finance-agent-composer-wrap"><div className="finance-agent-composer"><textarea ref={textareaRef} rows={1} value={query} onKeyDown={handleComposerKeyDown} onChange={(event) => setQuery(event.target.value)} className="max-h-32 min-h-[48px] flex-1 resize-none bg-transparent px-1 py-3 text-sm leading-6 text-stone-900 outline-none placeholder:text-stone-400" placeholder="直接问这家店的收入、到账、成本或资金…" /><motion.button whileHover={reduceMotion ? undefined : { scale: 1.04 }} whileTap={reduceMotion ? undefined : { scale: .94 }} disabled={loading || !query.trim()} className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-octo-700 text-white shadow-[0_8px_22px_rgba(154,52,18,.22)] transition-colors hover:bg-octo-800 disabled:bg-stone-200 disabled:text-stone-400 disabled:shadow-none" aria-label="发送财务问题"><Send className="h-4 w-4" /></motion.button></div><div className="mt-2 flex items-center justify-between px-1 text-[10px] text-stone-400"><span>Enter 发送 · Shift + Enter 换行</span><span>关键结论可追溯到台账与凭证</span></div></form>
    </motion.aside>
  </motion.div>;
}

function FinanceFileDropzone({ file, onFile, accept, title, hint, autoFocus = false }: { file: File | null; onFile: (file: File | null) => void; accept: string; title: string; hint: string; autoFocus?: boolean }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const zoneRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  useEffect(() => {
    if (!file || !file.type.startsWith("image/")) { setPreviewUrl(null); return; }
    const url = URL.createObjectURL(file); setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  useEffect(() => { if (autoFocus) zoneRef.current?.focus(); }, [autoFocus]);
  function clipboard(event: React.ClipboardEvent) {
    const pasted = Array.from(event.clipboardData.items).find((item) => item.kind === "file")?.getAsFile();
    if (pasted) { event.preventDefault(); onFile(pasted); }
  }
  return <><div ref={zoneRef} tabIndex={0} onPaste={clipboard} onClick={() => zoneRef.current?.focus()} onDragEnter={(event) => { event.preventDefault(); setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); onFile(event.dataTransfer.files?.[0] ?? null); }} className={`group min-w-0 rounded-xl border border-dashed p-3 outline-none transition duration-200 focus:border-octo-400 focus:ring-2 focus:ring-octo-100 ${dragging ? "border-octo-500 bg-octo-50" : "border-stone-300 bg-[#fbfaf8] hover:border-stone-400"}`}>
    <div className="flex min-w-0 items-center gap-3">
      {previewUrl ? <button type="button" onClick={() => setPreviewOpen(true)} className="relative h-14 w-14 shrink-0 overflow-hidden rounded-lg border border-stone-200 bg-white" title="在产品页查看原图"><img src={previewUrl} alt="已粘贴的财务资料缩略图" className="h-full w-full object-cover" /><span className="absolute inset-0 grid place-items-center bg-stone-950/0 text-white opacity-0 transition group-hover:bg-stone-950/25 group-hover:opacity-100"><ZoomIn className="h-4 w-4" /></span></button> : <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-white text-octo-700 ring-1 ring-stone-200"><Upload className="h-4 w-4" /></span>}
      <div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold text-stone-800">{file ? file.name : title}</p><p className="mt-1 text-[10px] leading-4 text-stone-500">{file ? `${(file.size / 1024).toFixed(1)} KB · 可替换或重新粘贴` : hint}</p></div>
      <input ref={inputRef} type="file" accept={accept} onChange={(event) => onFile(event.target.files?.[0] ?? null)} className="sr-only" />
      <button type="button" onClick={(event) => { event.stopPropagation(); inputRef.current?.click(); }} className="finance-button-secondary shrink-0">{file ? "更换" : "选择文件"}</button>
      {file && <button type="button" aria-label="移除已选文件" onClick={(event) => { event.stopPropagation(); onFile(null); }} className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-stone-400 hover:bg-stone-100 hover:text-stone-700"><X className="h-4 w-4" /></button>}
    </div>
  </div>{previewOpen && previewUrl && <div role="dialog" aria-modal="true" aria-label="财务原始图片预览" onClick={() => setPreviewOpen(false)} className="fixed inset-0 z-[110] grid place-items-center bg-stone-950/70 p-8 backdrop-blur-sm"><button type="button" aria-label="关闭原图预览" onClick={() => setPreviewOpen(false)} className="absolute right-6 top-6 grid h-10 w-10 place-items-center rounded-full bg-white/90 text-stone-800 shadow-lg"><X className="h-5 w-5" /></button><img onClick={(event) => event.stopPropagation()} src={previewUrl} alt="财务原始凭证大图" className="max-h-[88vh] max-w-[88vw] rounded-xl bg-white object-contain shadow-2xl" /></div>}</>;
}

function SectionTitle({ icon: Icon, title, detail }: { icon: React.ElementType; title: string; detail: string }) { return <div className="flex min-w-0 items-center gap-2.5"><Icon className="h-[17px] w-[17px] shrink-0 text-octo-700" /><h2 className="shrink-0 text-[15px] font-semibold tracking-[-0.01em] text-stone-950">{title}</h2><span className="h-4 w-px shrink-0 bg-stone-200" /><span title={detail} className="min-w-0 truncate text-xs font-normal text-stone-500">{detail}</span></div>; }
function Metric({ label, value, strong }: { label: string; value: string; strong?: boolean }) { return <div className="flex items-center justify-between gap-4 border-b border-stone-100 py-2.5 last:border-0"><span className="text-xs text-stone-500">{label}</span><span className={`text-right text-sm tabular-nums text-stone-900 ${strong ? "font-bold" : ""}`}>{value}</span></div>; }
function StatusPill({ status }: { status: string }) { const tone = status === "posted" || status === "matched" || status === "confirmed" ? "bg-emerald-50 text-emerald-700" : status === "permission_blocked" || status === "conflict" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-800"; return <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${tone}`}>{statusLabel(status)}</span>; }
function EmptyState({ title, body }: { title: string; body: string }) { return <div className="mt-4 rounded-lg border border-dashed border-stone-300 bg-stone-50 px-4 py-8 text-center"><ScanLine className="mx-auto h-6 w-6 text-stone-400" /><p className="mt-2 text-sm font-semibold text-stone-700">{title}</p><p className="mt-1 w-full text-xs leading-5 text-stone-500">{body}</p></div>; }
function FormInput({ label, value, onChange, type = "text", placeholder, disabled }: { label: string; value: string; onChange: (value: string) => void; type?: "text" | "number" | "date"; placeholder?: string; disabled?: boolean }) { return <label className="block"><span className="text-xs font-medium text-stone-600">{label}</span><input type={type} min={type === "number" ? "0" : undefined} step={type === "number" ? "0.01" : undefined} value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="mt-1 min-h-10 w-full rounded-lg border border-stone-200 bg-white px-3 text-sm outline-none focus:border-octo-500 focus:ring-2 focus:ring-octo-100 disabled:bg-stone-100 disabled:text-stone-500" /></label>; }
function FormSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: Array<{ value: string; label: string }> }) { return <label className="block"><span className="text-xs font-medium text-stone-600">{label}</span><select value={value} onChange={(event) => onChange(event.target.value)} className="mt-1 min-h-10 w-full rounded-lg border border-stone-200 bg-white px-3 text-sm outline-none focus:border-octo-500 focus:ring-2 focus:ring-octo-100">{options.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>; }
