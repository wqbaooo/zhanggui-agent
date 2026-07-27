"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Boxes,
  CalendarDays,
  CheckCircle2,
  CircleDashed,
  CloudRain,
  Compass,
  Database,
  FileQuestion,
  Info,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { LoadingSpinner } from "@/components/shared/Loading";
import {
  DEFAULT_PROJECT_ID,
  getAdvisorBrief,
  getBusinessForecast,
  type AdvisorBrief,
  type AdvisorSection,
  type AdvisorSectionStatus,
  type BusinessForecastV1,
} from "@/lib/api";

const statusMeta: Record<AdvisorSectionStatus, {
  label: string;
  className: string;
  icon: typeof CheckCircle2;
}> = {
  verified: {
    label: "事实已齐",
    className: "border-emerald-200 bg-emerald-50 text-emerald-700",
    icon: CheckCircle2,
  },
  partial: {
    label: "部分可判断",
    className: "border-amber-200 bg-amber-50 text-amber-700",
    icon: FileQuestion,
  },
  unknown: {
    label: "暂不能判断",
    className: "border-stone-200 bg-stone-100 text-stone-600",
    icon: CircleDashed,
  },
  conflict: {
    label: "需要先核对",
    className: "border-red-200 bg-red-50 text-red-700",
    icon: AlertTriangle,
  },
};

export default function DashboardPage() {
  const [brief, setBrief] = useState<AdvisorBrief | null>(null);
  const [forecast, setForecast] = useState<BusinessForecastV1 | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [forecastError, setForecastError] = useState("");

  const fetchBrief = useCallback(async () => {
    setLoading(true);
    setError("");
    setForecastError("");
    const [briefResult, forecastResult] = await Promise.allSettled([
      getAdvisorBrief(DEFAULT_PROJECT_ID),
      getBusinessForecast(undefined, DEFAULT_PROJECT_ID),
    ]);
    if (briefResult.status === "fulfilled") {
      setBrief(briefResult.value);
    } else {
      setBrief(null);
      setError("经营参谋暂时无法读取门店数据。页面不会用缓存数字或模拟结论代替。");
    }
    if (forecastResult.status === "fulfilled") {
      setForecast(forecastResult.value);
    } else {
      setForecast(null);
      setForecastError("暂时无法读取预测数据；不会使用上次缓存或模拟值代替。");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void fetchBrief();
  }, [fetchBrief]);

  const advisorModule = useMemo(() => ({
    ...getModule("/dashboard"),
    title: "经营参谋",
    eyebrow: "READ-ONLY ADVISOR",
    description: "只读汇总已确认的钱账、渠道、库存、人工和 SOP；把事实、缺口、冲突和下一步分开说明。",
    primaryMetric: "事实 / 缺口 / 冲突",
    secondaryMetric: brief?.latest_fact_date ? `数据至 ${brief.latest_fact_date}` : "等待真实事实",
    status: (
      brief?.data_status === "conflict"
        ? "risk"
        : brief?.data_status === "ready"
          ? "good"
          : brief?.data_status === "partial"
            ? "watch"
            : "info"
    ) as "risk" | "good" | "watch" | "info",
  }), [brief?.data_status, brief?.latest_fact_date]);

  return (
    <ModulePage module={advisorModule}>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_19rem]">
        <div className="min-w-0 space-y-4">
          <AdvisorSummary brief={brief} loading={loading} error={error} onRetry={fetchBrief} />
          <ForecastDecisionPanel
            forecast={forecast}
            loading={loading}
            error={forecastError}
            onRetry={fetchBrief}
          />

          {!loading && brief && (
            <section className="overflow-hidden rounded-xl border border-stone-200 bg-white/80">
              <div className="border-b border-stone-200 px-4 py-3 md:px-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h2 className="text-base font-semibold text-stone-900">参谋核对结果</h2>
                    <p className="mt-0.5 text-xs text-stone-500">
                      每个判断都保留数据来源；未知不会显示成零或正常。
                    </p>
                  </div>
                  <span className="text-xs text-stone-500">
                    已检查 {brief.consulted_modules.length} 个专业模块
                  </span>
                </div>
              </div>

              <div className="divide-y divide-stone-200">
                {brief.sections.map((section) => (
                  <AdvisorSectionRow key={section.key} section={section} />
                ))}
              </div>
            </section>
          )}
        </div>

        <aside className="space-y-4 xl:sticky xl:top-20 xl:self-start">
          <PriorityActions brief={brief} forecast={forecast} loading={loading} />
          <section className="rounded-xl border border-stone-200 bg-stone-50 p-4">
            <div className="flex items-center gap-2 text-stone-800">
              <LockKeyhole className="h-4 w-4" />
              <h2 className="text-sm font-semibold">参谋权限</h2>
            </div>
            <p className="mt-2 text-xs leading-5 text-stone-600">
              只读取已确认事实并生成建议草稿，不记账、不改库存、不下单、不改价。
            </p>
            <Link
              href="/chat"
              className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-octo-700 hover:underline"
            >
              向掌柜追问这份简报
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </section>
        </aside>
      </div>
    </ModulePage>
  );
}

function AdvisorSummary({
  brief,
  loading,
  error,
  onRetry,
}: {
  brief: AdvisorBrief | null;
  loading: boolean;
  error: string;
  onRetry: () => void;
}) {
  if (loading) {
    return (
      <section className="flex min-h-36 items-center justify-center rounded-xl border border-stone-200 bg-white/80">
        <div className="flex items-center gap-2 text-sm text-stone-500">
          <LoadingSpinner />
          正在核对各专业账与档案
        </div>
      </section>
    );
  }

  if (error || !brief) {
    return (
      <section className="rounded-xl border border-red-200 bg-red-50 p-4 md:p-5" role="alert">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
          <div className="min-w-0">
            <h2 className="font-semibold text-red-900">暂时无法形成经营简报</h2>
            <p className="mt-1 text-sm leading-6 text-red-700">{error}</p>
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-2 text-xs font-medium text-red-700 hover:bg-red-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              重新读取
            </button>
          </div>
        </div>
      </section>
    );
  }

  const tone = brief.data_status === "conflict"
    ? "border-red-200 bg-red-50/80"
    : brief.data_status === "ready"
      ? "border-emerald-200 bg-emerald-50/70"
      : "border-amber-200 bg-amber-50/70";

  return (
    <section className={`rounded-xl border p-4 md:p-5 ${tone}`}>
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-stone-200 bg-white px-2.5 py-1 text-[11px] font-medium text-stone-700">
              <Compass className="h-3.5 w-3.5" />
              只读经营判断
            </span>
            <span className="text-xs text-stone-500">现实日期 {brief.calendar_date}</span>
          </div>
          <h2 className="mt-3 text-lg font-semibold leading-7 text-stone-950">{brief.headline}</h2>
          <p className="mt-1 text-sm text-stone-600">
            {brief.latest_fact_date
              ? `最近经营事实日期：${brief.latest_fact_date}`
              : "尚未找到可作为判断依据的经营事实日期"}
          </p>
        </div>
        <div className="shrink-0 rounded-lg border border-white/80 bg-white/70 px-3 py-2 text-xs text-stone-600">
          今天和数据日期分开显示
        </div>
      </div>
    </section>
  );
}

function yuanMinor(value: number | null) {
  if (value == null) return "待补数据";
  return `¥${(value / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

function compactMinor(value: number) {
  const yuan = value / 100;
  return yuan >= 1000 ? `${(yuan / 1000).toFixed(1)}k` : String(Math.round(yuan));
}

function ForecastDecisionPanel({
  forecast,
  loading,
  error,
  onRetry,
}: {
  forecast: BusinessForecastV1 | null;
  loading: boolean;
  error: string;
  onRetry: () => void;
}) {
  const reduceMotion = useReducedMotion();

  if (loading) {
    return (
      <section className="grid min-h-56 place-items-center rounded-xl border border-stone-200 bg-white/80">
        <div className="flex items-center gap-2 text-sm text-stone-500">
          <LoadingSpinner />
          正在核对收入、库存与天气事实
        </div>
      </section>
    );
  }

  if (error || !forecast) {
    return (
      <section className="rounded-xl border border-red-200 bg-red-50 p-4" role="alert">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
          <div>
            <h2 className="text-sm font-semibold text-red-900">经营预测暂不可用</h2>
            <p className="mt-1 text-sm text-red-700">{error}</p>
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 text-xs font-medium text-red-700"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              重新核对
            </button>
          </div>
        </div>
      </section>
    );
  }

  const confidenceLabel = {
    medium: "中等置信",
    low: "较低置信",
    unavailable: "不可预测",
  }[forecast.revenue.confidence];
  const statusTone = forecast.status === "ready"
    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
    : forecast.status === "partial"
      ? "border-amber-200 bg-amber-50 text-amber-700"
      : "border-stone-200 bg-stone-100 text-stone-600";
  const maxDaily = Math.max(
    ...forecast.revenue.forecast_days.map((day) => day.high_minor),
    1,
  );

  return (
    <motion.section
      initial={reduceMotion ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduceMotion ? 0 : 0.24 }}
      className="overflow-hidden rounded-xl border border-stone-200 bg-white/90"
      aria-labelledby="business-forecast-title"
    >
      <header className="flex flex-col gap-3 border-b border-stone-200 px-4 py-4 md:flex-row md:items-center md:justify-between md:px-5">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 id="business-forecast-title" className="text-base font-semibold text-stone-950">
              未来 7 天经营推演
            </h2>
            <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${statusTone}`}>
              {forecast.status === "ready" ? "事实可用" : forecast.status === "partial" ? "部分可判断" : "数据不足"}
            </span>
          </div>
          <p className="mt-1 text-xs leading-5 text-stone-500">
            收入给区间，库存只在盘点、日耗和安全库存齐全时给采购量。
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-stone-500">
          <CalendarDays className="h-4 w-4" />
          预测起点 {forecast.as_of_date}
        </div>
      </header>

      <div className="grid lg:grid-cols-[minmax(0,1.7fr)_minmax(17rem,0.8fr)]">
        <div className="border-b border-stone-200 p-4 md:p-5 lg:border-b-0 lg:border-r">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <div className="flex items-center gap-2 text-stone-700">
                <BarChart3 className="h-4 w-4 text-octo-700" />
                <h3 className="text-sm font-semibold">收入预测区间</h3>
              </div>
              {forecast.revenue.total_predicted_minor != null ? (
                <>
                  <p className="mt-3 text-2xl font-bold tracking-tight text-stone-950 md:text-3xl">
                    {yuanMinor(forecast.revenue.total_low_minor)}
                    <span className="mx-2 font-normal text-stone-300">—</span>
                    {yuanMinor(forecast.revenue.total_high_minor)}
                  </p>
                  <p className="mt-1 text-xs text-stone-500">
                    七天基线 {yuanMinor(forecast.revenue.total_predicted_minor)} · 这是区间，不是收入承诺
                  </p>
                </>
              ) : (
                <p className="mt-3 text-lg font-semibold text-stone-700">暂不能给出金额</p>
              )}
            </div>
            <div className="shrink-0 rounded-lg bg-stone-50 px-3 py-2 text-xs leading-5 text-stone-600">
              <p className="font-medium text-stone-800">{confidenceLabel}</p>
              <p>{forecast.revenue.sample_days} 个营业日样本</p>
              <p>
                {forecast.revenue.days_stale != null
                  ? `距最新事实 ${forecast.revenue.days_stale} 天`
                  : "暂无营业事实日期"}
              </p>
            </div>
          </div>

          {forecast.revenue.forecast_days.length > 0 ? (
            <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-7">
              {forecast.revenue.forecast_days.map((day, index) => (
                <motion.article
                  key={day.date}
                  initial={reduceMotion ? false : { opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: reduceMotion ? 0 : index * 0.035 }}
                  className="min-w-0 rounded-lg border border-stone-200 bg-stone-50/80 p-2.5"
                  title={day.basis}
                >
                  <div className="flex items-center justify-between gap-1">
                    <p className="text-xs font-semibold text-stone-800">{day.weekday}</p>
                    <time className="text-[10px] text-stone-400">{day.date.slice(5).replace("-", "/")}</time>
                  </div>
                  <p className="mt-2 whitespace-nowrap text-xs font-bold text-stone-950">{yuanMinor(day.predicted_minor)}</p>
                  <p
                    className="mt-0.5 whitespace-nowrap text-[9px] tracking-tight text-stone-500"
                    title={`${yuanMinor(day.low_minor)}–${yuanMinor(day.high_minor)}`}
                  >
                    {compactMinor(day.low_minor)}–{compactMinor(day.high_minor)}
                  </p>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-stone-200">
                    <motion.div
                      initial={reduceMotion ? false : { width: 0 }}
                      animate={{ width: `${Math.max((day.predicted_minor / maxDaily) * 100, 5)}%` }}
                      transition={{ delay: reduceMotion ? 0 : 0.1 + index * 0.035, duration: reduceMotion ? 0 : 0.28 }}
                      className="h-full rounded-full bg-octo-500"
                    />
                  </div>
                  <p className="mt-2 truncate text-[10px] text-stone-500">
                    {day.weather || "天气待更新"}
                  </p>
                  {day.weather_risks.length > 0 && (
                    <p className="mt-1 text-[10px] font-medium text-amber-700">
                      {day.weather_risks.join(" · ")}
                    </p>
                  )}
                </motion.article>
              ))}
            </div>
          ) : (
            <div className="mt-4 rounded-lg border border-dashed border-stone-300 bg-stone-50 p-4 text-sm leading-6 text-stone-600">
              至少补齐连续 7 天已确认营业收入后，系统才会显示预测金额。
            </div>
          )}

          <div className="mt-4 flex items-start gap-2 rounded-lg border border-blue-100 bg-blue-50/60 px-3 py-2.5 text-xs leading-5 text-blue-800">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{forecast.revenue.method}。天气目前只用于扩大不确定区间，不直接增减收入。</span>
          </div>
        </div>

        <div className="p-4 md:p-5">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-stone-700">
              <Boxes className="h-4 w-4 text-octo-700" />
              <h3 className="text-sm font-semibold">库存与采购</h3>
            </div>
            <span className="text-xs text-stone-500">
              可计算 {forecast.inventory.modelled_skus}/{forecast.inventory.active_skus}
            </span>
          </div>

          <div className="mt-3 rounded-lg bg-stone-50 px-3 py-3">
            <p className="text-xs text-stone-500">最近库存事实</p>
            <p className="mt-1 text-sm font-semibold text-stone-900">
              {forecast.inventory.data_fact_date || "尚无可追溯日期"}
            </p>
            <p className="mt-1 text-xs text-stone-500">
              {forecast.inventory.days_stale != null
                ? `距预测日 ${forecast.inventory.days_stale} 天`
                : "不能判断库存新鲜度"}
            </p>
          </div>

          {forecast.inventory.risks.length > 0 ? (
            <div className="mt-3 space-y-2">
              {forecast.inventory.risks.slice(0, 4).map((risk) => (
                <Link
                  key={risk.sku_id}
                  href="/inventory"
                  className="block rounded-lg border border-red-100 bg-red-50/70 px-3 py-2.5 transition hover:border-red-200"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-semibold text-red-900">{risk.name}</p>
                    <span className="text-[10px] text-red-700">
                      {risk.action === "urgent" ? "立即处理" : "进入补货窗口"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-red-800">
                    剩余约 {risk.days_remaining ?? "?"} 天
                    {risk.recommend_qty != null ? ` · 建议 ${risk.recommend_qty}${risk.unit}` : ""}
                  </p>
                </Link>
              ))}
            </div>
          ) : (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50/70 p-3">
              <p className="text-xs font-semibold text-amber-900">
                {forecast.inventory.status === "insufficient" ? "当前不能计算断货日" : "没有事实触发的紧急补货"}
              </p>
              <p className="mt-1 text-xs leading-5 text-amber-800">
                {forecast.inventory.gaps[0] || "继续记录开包、领用和盘点，系统会滚动更新。"}
              </p>
            </div>
          )}

          <Link
            href="/inventory"
            className="mt-3 inline-flex min-h-10 items-center gap-1.5 text-xs font-medium text-octo-700 hover:underline"
          >
            补盘点与日耗事实
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>

      <div className="border-t border-stone-200 bg-stone-50/55 px-4 py-4 md:px-5">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(15rem,0.55fr)]">
          <div>
            <div className="flex items-center gap-2">
              <CloudRain className="h-4 w-4 text-stone-600" />
              <h3 className="text-sm font-semibold text-stone-900">主动预警</h3>
            </div>
            {forecast.alerts.length > 0 ? (
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                {forecast.alerts.slice(0, 6).map((alert, index) => (
                  <Link
                    key={`${alert.kind}-${alert.title}-${index}`}
                    href={alert.target}
                    className={`rounded-lg border px-3 py-2.5 ${
                      alert.level === "high"
                        ? "border-red-200 bg-red-50 text-red-900"
                        : "border-amber-200 bg-amber-50 text-amber-900"
                    }`}
                  >
                    <p className="text-xs font-semibold">{alert.title}</p>
                    <p className="mt-1 text-xs leading-5 opacity-80">{alert.body}</p>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-xs text-stone-500">没有由现有事实触发的预警。</p>
            )}
          </div>

          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-stone-600" />
              <h3 className="text-sm font-semibold text-stone-900">证据链</h3>
            </div>
            <div className="mt-2 space-y-2">
              {forecast.evidence.map((item) => (
                <div key={`${item.kind}-${item.label}`} className="rounded-lg border border-stone-200 bg-white px-3 py-2">
                  <p className="text-xs font-medium text-stone-800">{item.label}</p>
                  <p className="mt-0.5 text-[10px] text-stone-500">{item.source} · {item.period}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </motion.section>
  );
}

function AdvisorSectionRow({ section }: { section: AdvisorSection }) {
  const meta = statusMeta[section.status];
  const StatusIcon = meta.icon;

  return (
    <article className="grid gap-4 px-4 py-4 md:px-5 lg:grid-cols-[12rem_minmax(0,1fr)]">
      <div>
        <h3 className="text-sm font-semibold text-stone-900">{section.label}</h3>
        <span className={`mt-2 inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[11px] font-medium ${meta.className}`}>
          <StatusIcon className="h-3.5 w-3.5" />
          {meta.label}
        </span>
      </div>

      <div className="min-w-0 space-y-3">
        {section.facts.length > 0 && (
          <div className="space-y-2">
            {section.facts.map((fact, index) => (
              <div key={`${fact.title}-${index}`} className="rounded-lg bg-stone-50 px-3 py-2.5">
                <div className="flex items-start gap-2">
                  <Database className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-stone-900">{fact.title}</p>
                    <p className="mt-1 break-words text-sm leading-5 text-stone-700">{fact.summary}</p>
                    <p className="mt-1 text-[11px] text-stone-400">来源：{fact.source}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {section.conflicts.map((conflict, index) => (
          <div key={`conflict-${index}`} className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-800">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span className="leading-5">{String(conflict.message || "该模块存在需要人工核对的冲突")}</span>
          </div>
        ))}

        {section.gaps.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50/70 px-3 py-2.5">
            <p className="text-xs font-medium text-amber-800">还缺什么</p>
            <ul className="mt-1.5 space-y-1 text-sm leading-5 text-amber-900">
              {section.gaps.map((gap) => (
                <li key={gap} className="flex items-start gap-2">
                  <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-amber-500" />
                  <span>{gap}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {section.facts.length === 0 && section.gaps.length === 0 && (
          <p className="text-sm text-stone-500">当前没有可用于判断的已确认事实。</p>
        )}

        {section.evidence.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {section.evidence.map((item, index) => (
              <span
                key={`${item.label}-${index}`}
                title={item.source}
                className="rounded-md border border-stone-200 bg-white px-2 py-1 text-[11px] text-stone-500"
              >
                {item.label || "经营证据"}
              </span>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

function PriorityActions({
  brief,
  forecast,
  loading,
}: {
  brief: AdvisorBrief | null;
  forecast: BusinessForecastV1 | null;
  loading: boolean;
}) {
  const actions = [
    ...(forecast?.alerts
      .filter((alert) => alert.kind === "data_gap" || alert.kind === "inventory")
      .map((alert) => ({ label: alert.title, target: alert.target })) || []),
    ...(brief?.priority_actions || []),
  ].filter(
    (action, index, all) =>
      all.findIndex((candidate) => candidate.label === action.label && candidate.target === action.target) === index,
  ).slice(0, 5);

  return (
    <section className="rounded-xl border border-stone-200 bg-white/80 p-4">
      <h2 className="text-sm font-semibold text-stone-900">建议先处理</h2>
      <p className="mt-1 text-xs leading-5 text-stone-500">
        只从当前缺口或冲突生成，不创建虚假的每日任务。
      </p>

      {loading ? (
        <div className="mt-4 flex justify-center py-4"><LoadingSpinner /></div>
      ) : actions.length > 0 ? (
        <div className="mt-3 divide-y divide-stone-100">
          {actions.map((action, index) => (
            <Link
              key={`${action.target}-${action.label}`}
              href={action.target}
              className="flex items-start gap-3 py-3 text-sm text-stone-800 transition hover:text-octo-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-octo-300"
            >
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-octo-50 text-[10px] font-semibold text-octo-700">
                {index + 1}
              </span>
              <span className="min-w-0 flex-1 leading-5">{action.label}</span>
              <ArrowRight className="mt-0.5 h-4 w-4 shrink-0" />
            </Link>
          ))}
        </div>
      ) : (
        <p className="mt-3 rounded-lg bg-stone-50 px-3 py-3 text-sm leading-5 text-stone-600">
          当前没有由真实缺口触发的建议动作。
        </p>
      )}
    </section>
  );
}
