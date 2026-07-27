"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, CalendarDays, CheckCircle2, ChevronRight, Download, Info, Lightbulb, Loader2, Printer, Sparkles, TrendingDown } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { DEFAULT_PROJECT_ID, getReports, generateReport, getOperationSummary, type Report } from "@/lib/api";

const findingIcon: Record<string, typeof AlertTriangle> = {
  good: CheckCircle2, risk: AlertTriangle, watch: TrendingDown, info: Info,
};
const findingColor: Record<string, string> = {
  good: "border-emerald-200 bg-emerald-50 text-emerald-800",
  risk: "border-red-200 bg-red-50 text-red-800",
  watch: "border-amber-200 bg-amber-50 text-amber-800",
  info: "border-sky-200 bg-sky-50 text-sky-800",
};

function fmtMoney(v: number | null) { return v == null ? "待核算" : `¥${(v / 1000).toFixed(1)}k`; }
function fmtPct(v: number | null) { return v == null ? "待核算" : `${(v * 100).toFixed(0)}%`; }

export default function ReportsPage() {
  const [report, setReport] = useState<Report | null>(null);
  const [history, setHistory] = useState<Report[]>([]);
  const [generating, setGenerating] = useState(false);
  const [dataDays, setDataDays] = useState(0);
  const [initialized, setInitialized] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // 打开页面自动拉最新数据
  const loadLatest = useCallback(async () => {
    setLoadError(null);
    try {
      const [rRes, ops] = await Promise.all([
        getReports(DEFAULT_PROJECT_ID, undefined, 5),
        getOperationSummary(DEFAULT_PROJECT_ID, 7),
      ]);
      setHistory(rRes.reports);
      setDataDays(ops.entry_count || 0);
      // 自动用最新报告或提示生成
      if (rRes.reports.length > 0) {
        setReport(rRes.reports[0]);
      }
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "经营报告加载失败，请检查后端服务");
    }
    setInitialized(true);
  }, []);

  useEffect(() => { loadLatest(); }, [loadLatest]);

  const handleGenerate = useCallback(async (type: "weekly" | "monthly") => {
    setGenerating(true);
    setLoadError(null);
    try {
      const res = await generateReport(DEFAULT_PROJECT_ID, type);
      setReport(res.report);
      await loadLatest();
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "经营报告生成失败，请稍后重试");
    }
    setGenerating(false);
  }, [loadLatest]);

  const hasEnoughData = dataDays >= 3;
  const reportIsVerified = report?.status === "finance_confirmed";
  const downloadCashTemplate = useCallback(() => {
    const rows = [
      ["日期", "班次/经手人", "期初备用金", "现金销售", "其他现金收入", "现金采购支出", "现金退款", "存入银行卡", "应有现金", "实点现金", "长款/短款", "保留备用金", "交接人", "确认人", "备注/凭证"],
      ["", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    ];
    const csv = "\ufeff" + rows.map((row) => row.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "掌柜Agent-现金管理日报空白表.csv";
    a.click();
    URL.revokeObjectURL(url);
  }, []);

  const printCashTemplate = useCallback(() => {
    const rows = ["期初备用金", "现金销售", "其他现金收入", "现金采购支出", "现金退款", "存入银行卡", "应有现金", "实点现金", "长款/短款", "保留备用金"];
    const html = `<html><head><title>现金管理日报</title><style>body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:24px;color:#111}h1{font-size:20px;margin:0 0 12px}.meta{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0}.meta div{border:1px solid #999;padding:8px;height:28px}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid #999;padding:8px;height:28px;text-align:left}th{background:#f3f4f6}</style></head><body><h1>现金管理日报</h1><div class="meta"><div>日期：</div><div>班次：</div><div>经手人：</div><div>确认人：</div></div><table><thead><tr><th>项目</th><th>金额</th><th>说明/凭证</th></tr></thead><tbody>${rows.map((item) => `<tr><td>${item}</td><td></td><td></td></tr>`).join("")}</tbody></table></body></html>`;
    const printWindow = window.open("", "_blank");
    if (!printWindow) return;
    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.print();
  }, []);

  return (
    <ModulePage module={getModule("/reports")}>
        <div className="space-y-4">
          {!initialized && <div className="h-0.5 w-full animate-pulse rounded-full bg-primary/30" />}
          {loadError && (
            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
              {loadError}。系统没有使用模拟报告替代。
            </div>
          )}

          {/* 复盘入口 */}
          <div className="flex items-center gap-3 rounded-2xl border border-white/45 bg-white/42 p-3">
            <div className="flex items-center gap-2 text-sm text-on-surface-variant">
              <CalendarDays className="h-4 w-4" />
              <span>已积累 {dataDays} 天经营数据</span>
            </div>
            <div className="ml-auto flex gap-2">
              <button onClick={downloadCashTemplate}
                className="inline-flex items-center gap-1.5 rounded-full border border-white/50 bg-white/55 px-3 py-1.5 text-xs font-medium text-on-surface-variant hover:bg-white/80">
                <Download className="h-3.5 w-3.5" />现金表
              </button>
              <button onClick={printCashTemplate}
                className="inline-flex items-center gap-1.5 rounded-full border border-white/50 bg-white/55 px-3 py-1.5 text-xs font-medium text-on-surface-variant hover:bg-white/80">
                <Printer className="h-3.5 w-3.5" />打印空白表
              </button>
              <button onClick={() => handleGenerate("weekly")} disabled={generating || !hasEnoughData}
                className="inline-flex items-center gap-1.5 rounded-full bg-primary px-4 py-1.5 text-xs font-semibold text-on-primary shadow-sm disabled:opacity-40">
                {generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                周复盘
              </button>
              <button onClick={() => handleGenerate("monthly")} disabled={generating || !hasEnoughData}
                className="inline-flex items-center gap-1.5 rounded-full border border-white/50 bg-white/55 px-4 py-1.5 text-xs font-medium text-on-surface-variant hover:bg-white/80 disabled:opacity-40">
                月复盘
              </button>
            </div>
          </div>

          {initialized && !report && !hasEnoughData ? (
            <div className="rounded-2xl border border-dashed border-white/60 bg-white/35 p-8 text-center">
              <p className="font-medium text-on-background">数据不足</p>
              <p className="mt-1 text-xs text-on-surface-variant">至少需要 3 天经营数据才能生成复盘。在首页录入日报。</p>
            </div>
          ) : initialized && !report ? (
            <div className="rounded-2xl border border-dashed border-white/60 bg-white/35 p-8 text-center">
              <Lightbulb className="mx-auto h-8 w-8 text-amber-400/50" />
              <p className="mt-3 font-medium text-on-background">点击「周复盘」开始</p>
              <p className="mt-1 text-xs text-on-surface-variant">从日账、库存、员工数据自动找出问题和动作</p>
            </div>
          ) : report ? (
            <div className="space-y-4">

              {/* 报告头 */}
              <div className="rounded-2xl border border-white/45 bg-white/42 p-5">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs font-medium text-on-surface-variant">
                      {report.report_type === "weekly" ? "周复盘" : "月复盘"} · {report.period_start} ~ {report.period_end}
                    </p>
                    <h2 className="mt-1 text-2xl font-bold text-on-background">
                      {reportIsVerified ? ((report.net_profit ?? 0) >= 0 ? "本期盈利" : "本期亏损") : "历史报告未核验"}
                    </h2>
                    <p className="mt-1 text-xs text-on-surface-variant">
                      {reportIsVerified
                        ? `覆盖 ${report.total_days} 天 · 日均 ${(report.total_orders ?? 0) > 0 ? `${Math.round((report.total_orders ?? 0) / Math.max(report.total_days, 1))} 单` : "无数据"}`
                        : "原始记录保留，但不能作为收入、成本或利润结论"}
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = `report-${report.report_type}-${report.period_start}-${report.period_end}.json`;
                      a.click();
                      URL.revokeObjectURL(url);
                    }}
                    className="inline-flex items-center gap-1 rounded-full border border-white/50 bg-white/55 px-3 py-1.5 text-xs font-medium text-on-surface-variant hover:bg-white/80 shrink-0"
                  >
                    <Download className="h-3.5 w-3.5" />导出
                  </button>
                </div>

                {reportIsVerified ? (
                  <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-5">
                    <MiniMetric label="总营收" value={fmtMoney(report.total_revenue)}
                      change={report.revenue_change_pct ?? undefined} />
                    <MiniMetric label="日均" value={report.avg_daily_revenue == null ? "待核算" : `¥${report.avg_daily_revenue.toLocaleString()}`} />
                    <MiniMetric label="净利" value={fmtMoney(report.net_profit)}
                      tone={(report.net_profit ?? 0) < 0 ? "risk" : "good"}
                      change={report.profit_change_pct ?? undefined} />
                    <MiniMetric label="食材率" value={fmtPct(report.food_cost_rate)}
                      tone={(report.food_cost_rate ?? 0) > 0.4 ? "risk" : undefined} />
                    <MiniMetric label="外卖占比" value={fmtPct(report.takeout_ratio)}
                      tone={(report.takeout_ratio ?? 0) > 0.45 ? "watch" : undefined} />
                  </div>
                ) : (
                  <div className="mt-4 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-900">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <div>
                      <p className="text-sm font-semibold">成本与关账依据不完整</p>
                      <p className="mt-1 text-xs leading-5">这份旧报告生成于统一财务底账启用前，页面不再展示其中的利润、成本率和经营结论。补齐对应日期关账后，可重新生成正式报告。</p>
                    </div>
                  </div>
                )}
              </div>

              {/* 叙事摘要 */}
              {reportIsVerified && report.narrative && (
                <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="h-4 w-4 text-primary" />
                    <p className="text-sm font-semibold text-on-background">AI 经营摘要</p>
                  </div>
                  <p className="text-sm leading-relaxed text-on-surface-variant whitespace-pre-line">{report.narrative}</p>
                </div>
              )}

              {/* 发现问题 */}
              {reportIsVerified && report.findings.length > 0 && (
                <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Lightbulb className="h-4 w-4 text-amber-500" />
                    <p className="text-sm font-semibold text-on-background">发现 {report.findings.length} 个值得关注的问题</p>
                  </div>
                  <div className="space-y-2">
                    {report.findings.map((f, i) => {
                      const Icon = findingIcon[f.level] || Info;
                      const target = f.target;
                      const card = (
                        <div className={`flex items-start gap-3 rounded-xl border px-4 py-3 ${findingColor[f.level]} ${target ? "cursor-pointer hover:brightness-95" : ""}`}>
                          <Icon className="mt-0.5 h-4 w-4 shrink-0" />
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-semibold">{f.title}</p>
                            <p className="mt-0.5 text-xs opacity-80">{f.body}</p>
                          </div>
                          {target && <ArrowRight className="mt-1 h-4 w-4 shrink-0 opacity-50" />}
                        </div>
                      );
                      return target ? <Link key={i} href={target}>{card}</Link> : <div key={i}>{card}</div>;
                    })}
                  </div>
                </div>
              )}

              {/* 板块快览 */}
              {reportIsVerified && <div className="grid gap-3 md:grid-cols-3">
                {Object.entries(report.sections).map(([key, sec]) => (
                  <div key={key} className="rounded-2xl border border-white/45 bg-white/42 p-4">
                    <p className="text-xs font-medium text-on-surface-variant">{sec.title}</p>
                    <div className="mt-2 space-y-1.5">
                      {Object.entries(sec.metrics).slice(0, 4).map(([k, v]) => {
                        if (v === null || v === undefined || typeof v === "object") return null;
                        const labels: Record<string, string> = {
                          total_revenue: "营收", net_profit: "净利", avg_daily_revenue: "日均",
                          total_orders: "订单", avg_order_value: "客单价",
                          food_cost_rate: "食材率", labor_cost_rate: "人工率", prime_cost_rate: "PrimeCost",
                          takeout_ratio: "外卖比", takeout_orders: "外卖单", platform_fee: "平台费",
                          marketing: "营销费", bad_reviews: "差评", total_skus: "SKU", urgent: "告急",
                          staff_count: "员工",
                        };
                        const label = labels[k] || k;
                        const val = typeof v === "number"
                          ? (k.includes("rate") || k.includes("ratio") ? fmtPct(v as number) : k.includes("revenue") || k.includes("profit") || k.includes("fee") || k.includes("marketing") ? fmtMoney(v as number) : String(v))
                          : String(v);
                        return (
                          <div key={k} className="flex items-center justify-between rounded-lg bg-white/55 px-3 py-1.5">
                            <span className="text-xs text-on-surface-variant">{label}</span>
                            <span className="text-xs font-semibold text-on-background">{val}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>}

              {/* 动作建议 */}
              {reportIsVerified && report.actions.length > 0 && (
                <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
                  <p className="text-sm font-semibold text-on-background mb-3">该做什么</p>
                  <div className="flex flex-wrap gap-2">
                    {report.actions.map((a, i) => (
                      <Link key={i} href={a.target}
                        className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-transform hover:-translate-y-0.5 ${
                          a.priority === "high" ? "bg-red-600 text-white shadow-lg shadow-red-600/20" :
                          a.priority === "medium" ? "bg-amber-500 text-white" :
                          "bg-white/55 text-on-surface-variant"
                        }`}>
                        {a.action} <ChevronRight className="h-3 w-3" />
                      </Link>
                    ))}
                  </div>
                </div>
              )}

              {/* 历史复盘 */}
              {history.length > 1 && (
                <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
                  <p className="text-xs font-medium text-on-surface-variant">历史复盘</p>
                  <div className="mt-2 flex gap-2 overflow-x-auto">
                    {history.slice(1, 5).map((r) => (
                      <button key={r.id} onClick={() => setReport(r)}
                        className={`shrink-0 rounded-xl border px-3 py-2 text-left hover:bg-white/65 ${r.id === report.id ? "border-primary/40 bg-primary-container/40" : "border-white/45 bg-white/42"}`}>
                        <p className="text-xs font-semibold text-on-background">
                          {r.report_type === "weekly" ? "周" : "月"} {r.period_start.slice(5)}
                        </p>
                        <p className="mt-0.5 text-[10px] text-on-surface-variant">
                          {r.status === "finance_confirmed" ? `${fmtMoney(r.total_revenue)} · ${fmtPct(r.food_cost_rate)}` : "历史未核验"}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              )}

            </div>
          ) : null}
        </div>
    </ModulePage>
  );
}

function MiniMetric({ label, value, tone, change }: { label: string; value: string; tone?: string; change?: number }) {
  const dot = tone === "good" ? "bg-emerald-400" : tone === "risk" ? "bg-red-400" : tone === "watch" ? "bg-amber-400" : "";
  return (
    <div className="rounded-2xl border border-white/45 bg-white/42 px-3 py-2">
      <p className="text-[10px] text-on-surface-variant">{label}</p>
      <p className="mt-0.5 text-base font-bold text-on-background">{value}</p>
      {dot && <span className={`mt-0.5 inline-block h-1.5 w-1.5 rounded-full ${dot}`} />}
      {change != null && change !== 0 && (
        <p className={`mt-0.5 text-[10px] ${change > 0 ? "text-emerald-600" : "text-red-600"}`}>
          {change > 0 ? "↑" : "↓"}{Math.abs(change)}% vs 上期
        </p>
      )}
    </div>
  );
}
