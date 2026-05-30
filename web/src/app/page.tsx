"use client";

import { useEffect, useState, useMemo } from "react";
import {
  BarChart3, Calculator, FileWarning, HomeIcon, MapPin,
  MessageSquareWarning, ShieldAlert, X,
} from "lucide-react";
import {
  DEFAULT_PROJECT_ID,
  getProjectCockpit,
} from "@/lib/api";
import { calculateInvestment, fmtMoney, fmtPct, calcRentPressureIndex } from "@/domain/calculations";
import {
  assessFranchiseRisks, assessInvestmentRisks,
  assessLocationRisks, assessOperationRisks, calcOverallRisk,
  identifySalesTricks, identifyHiddenCosts, generateNextQuestions, generateScoutChecklist,
  assessPermissionRisks, assessFulfillmentRisks, assessBreakevenAlert,
} from "@/domain/riskRules";
import type { RiskItem, FeedbackItem, RiskLevel, ProjectPhase, PermissionStatus, FulfillmentStatus } from "@/domain/types";
import {
  mockProject, mockFranchise, mockInvestment,
  mockLocation, mockOperations, mockRisks,
  mockPermissions, mockFulfillment, mockActions,
} from "@/data/mockProject";

type Tab = "overview" | "franchise" | "investment" | "location" | "operations" | "risks" | "feedback";

const TABS: { key: Tab; label: string; icon: typeof HomeIcon }[] = [
  { key: "overview", label: "总览", icon: HomeIcon },
  { key: "franchise", label: "加盟分析", icon: ShieldAlert },
  { key: "investment", label: "投资测算", icon: Calculator },
  { key: "location", label: "选址判断", icon: MapPin },
  { key: "operations", label: "运营", icon: BarChart3 },
  { key: "risks", label: "风险清单", icon: FileWarning },
  { key: "feedback", label: "反馈", icon: MessageSquareWarning },
];

const PHASE_LABELS: Record<ProjectPhase, string> = {
  idea: "想法期",
  franchise_talk: "加盟洽谈期",
  location_selection: "选址期",
  renovation: "装修期",
  trial_operation: "试营业",
  active_operation: "正式经营",
};

const RISK_BADGE: Record<RiskLevel, { bg: string; text: string; label: string }> = {
  low: { bg: "bg-emerald-500/15", text: "text-emerald-400", label: "低" },
  medium: { bg: "bg-amber-500/15", text: "text-amber-400", label: "中" },
  high: { bg: "bg-red-500/15", text: "text-red-400", label: "高" },
  critical: { bg: "bg-red-600/20", text: "text-red-300", label: "极高" },
};

interface IntelRecord {
  id: string;
  source: string;
  category: string;
  content: string;
  reliability: "高" | "中" | "低";
  timestamp: string;
}

const INTEL_SOURCES = ["朋友说的", "网上搜的", "实地看到的", "品牌方说的", "展会了解", "抖音/小红书", "其他"];
const INTEL_CATEGORIES = ["费用", "合同", "经营数据", "退出机制", "口碑评价", "供应链", "其他"];

export default function Home() {
  const [tab, setTab] = useState<Tab>("overview");
  const [fbOpen, setFbOpen] = useState(false);
  const [fbList, setFbList] = useState<FeedbackItem[]>([]);
  const [intelRecords, setIntelRecords] = useState<IntelRecord[]>([]);

  function addIntel(record: IntelRecord) {
    setIntelRecords((p) => [...p, record]);
  }

  useEffect(() => {
    getProjectCockpit(DEFAULT_PROJECT_ID, 7).catch(() => {});
  }, []);

  const invResult = useMemo(() => calculateInvestment(mockInvestment), []);
  const allRisks = useMemo(() => [...mockRisks], []);
  const overall = useMemo(() => calcOverallRisk(allRisks), [allRisks]);

  function addFeedback(fb: FeedbackItem) {
    setFbList((p) => [...p, fb]);
    setFbOpen(false);
  }

  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      {/* Top Bar */}
      <header className="sticky top-0 z-30 border-b border-[#F5EFE3]/8 bg-[#0A0A0A]/95 backdrop-blur-sm px-6 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex size-7 items-center justify-center rounded-md bg-[#D9261C]">
              <span className="text-xs font-bold text-[#F5EFE3]" style={{ fontFamily: "Antonio, sans-serif" }}>K</span>
            </div>
            <div>
              <h1 className="text-sm font-bold text-[#F5EFE3]/80" style={{ fontFamily: "Antonio, sans-serif" }}>{mockProject.name}</h1>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="mono-tag text-[9px] text-[#F5EFE3]/25">{PHASE_LABELS[mockProject.stage as ProjectPhase] || mockProject.stage}</span>
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[9px] font-medium ${RISK_BADGE[overall.level].bg} ${RISK_BADGE[overall.level].text}`}>
                  风险{RISK_BADGE[overall.level].label}
                </span>
              </div>
            </div>
          </div>
          <div className="mono-tag text-[9px] text-[#F5EFE3]/15">
            更新于 {mockProject.updatedAt}
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Left Nav */}
        <nav className="hidden w-[160px] shrink-0 border-r border-[#F5EFE3]/6 px-3 py-4 lg:flex lg:flex-col gap-0.5">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={"flex items-center gap-2 rounded-lg px-3 py-2 text-xs transition-colors " + (tab === t.key ? "bg-[#F5EFE3]/[0.06] text-[#F5EFE3]/70" : "text-[#F5EFE3]/25 hover:text-[#F5EFE3]/40 hover:bg-[#F5EFE3]/[0.03]")}
            >
              <t.icon className="size-3.5" />
              {t.label}
            </button>
          ))}
        </nav>

        {/* Main Content */}
        <main className="flex-1 overflow-auto px-6 py-5">
          <div className="mx-auto max-w-3xl">
            {tab === "overview" && <Dashboard overall={overall} risks={allRisks} invResult={invResult} setTab={setTab} />}
            {tab === "franchise" && <FranchiseView intelRecords={intelRecords} addIntel={addIntel} />}
            {tab === "investment" && <InvestmentView />}
            {tab === "location" && <LocationView />}
            {tab === "operations" && <OperationsView />}
            {tab === "risks" && <RisksView risks={allRisks} />}
            {tab === "feedback" && <FeedbackView items={fbList} onOpen={() => setFbOpen(true)} />}
          </div>
        </main>
      </div>

      {/* Mobile Nav */}
      <div className="fixed bottom-0 left-0 right-0 z-30 flex border-t border-[#F5EFE3]/8 bg-[#0A0A0A]/95 backdrop-blur-sm px-2 py-1.5 lg:hidden overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={"flex flex-1 shrink-0 flex-col items-center gap-0.5 rounded-lg py-1.5 " + (tab === t.key ? "text-[#F5EFE3]/70" : "text-[#F5EFE3]/20")}
          >
            <t.icon className="size-3.5" />
            <span className="text-[9px] mono-tag">{t.label}</span>
          </button>
        ))}
      </div>

      {/* Feedback Modal */}
      {fbOpen && <FeedbackModal onClose={() => setFbOpen(false)} onSubmit={addFeedback} />}
    </div>
  );
}

/* ═══════════════════════════════════════════
   1. 总览 Dashboard
   ═══════════════════════════════════════════ */

function Dashboard({ overall, risks, invResult, setTab }: {
  overall: ReturnType<typeof calcOverallRisk>;
  risks: RiskItem[];
  invResult: ReturnType<typeof calculateInvestment>;
  setTab: (t: Tab) => void;
}) {
  const rb = RISK_BADGE[overall.level];

  return (
    <div className="space-y-5">
      {/* 总风险 */}
      <div className={`rounded-xl border-2 p-5 ${overall.level === "critical" ? "border-red-500/25 bg-red-500/[0.04]" : overall.level === "high" ? "border-red-500/15 bg-red-500/[0.03]" : "border-[#F5EFE3]/10 bg-[#F5EFE3]/[0.02]"}`}>
        <div className="flex items-center justify-between mb-3">
          <span className="mono-tag text-[10px] text-[#F5EFE3]/25 tracking-wider">总体风险评估</span>
          <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-medium ${rb.bg} ${rb.text}`}>{rb.label} · {overall.score}分</span>
        </div>
        <div className="space-y-1.5">
          {overall.topRisks.map((r) => (
            <div key={r.id} className="flex items-start gap-2">
              <span className={RISK_BADGE[r.severity].text + " text-xs mt-0.5"}>●</span>
              <span className="text-xs text-[#F5EFE3]/45">{r.name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 4 指标卡 */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard label="总投资" value={fmtMoney(invResult.totalInvestment)} onClick={() => setTab("investment")} />
        <MetricCard label="月净利润" value={fmtMoney(invResult.monthlyNetProfit)} negative={invResult.monthlyNetProfit < 0} onClick={() => setTab("investment")} />
        <MetricCard label="回本月数" value={invResult.paybackMonths === Infinity ? "无法回本" : `${invResult.paybackMonths.toFixed(1)}月`} negative={invResult.paybackMonths > 18} onClick={() => setTab("investment")} />
        <MetricCard label="现金流安全" value={invResult.monthlyNetProfit >= 0 ? "充足" : `${invResult.cashflowSafeMonths.toFixed(1)}月`} negative={invResult.monthlyNetProfit < 0 && invResult.cashflowSafeMonths < 6} onClick={() => setTab("investment")} />
      </div>

      {/* 按模块风险 */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <ModuleRiskCard label="加盟风险" count={risks.filter(r => r.module === "franchise").length} onClick={() => setTab("franchise")} />
        <ModuleRiskCard label="投资风险" count={risks.filter(r => r.module === "investment").length} onClick={() => setTab("investment")} />
        <ModuleRiskCard label="选址风险" count={risks.filter(r => r.module === "location").length} onClick={() => setTab("location")} />
        <ModuleRiskCard label="运营风险" count={risks.filter(r => r.module === "operations").length} onClick={() => setTab("operations")} />
      </div>

      {/* 今日建议 */}
      <div className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-5">
        <span className="mono-tag text-[10px] text-[#F5EFE3]/20 tracking-wider">今日最该处理</span>
        <div className="mt-3 space-y-2">
          {risks.filter(r => r.status === "unverified").slice(0, 3).map((r, i) => (
            <div key={r.id} className="flex items-start gap-2.5">
              <span className="flex size-5 shrink-0 items-center justify-center rounded border border-[#F5EFE3]/12 text-[10px] text-[#F5EFE3]/25">{i + 1}</span>
              <div>
                <p className="text-xs text-[#F5EFE3]/50">{r.name}</p>
                <p className="mono-tag text-[9px] text-[#F5EFE3]/15 mt-0.5">{r.suggestedAction}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 待验证问题 */}
      <div className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-5">
        <span className="mono-tag text-[10px] text-[#F5EFE3]/20 tracking-wider">待验证问题清单</span>
        <div className="mt-3 space-y-1.5">
          {risks.filter(r => r.status === "unverified").map((r) => (
            <div key={r.id} className="flex items-center gap-2">
              <span className="text-[#F5EFE3]/15 text-xs">?</span>
              <span className="text-xs text-[#F5EFE3]/35">{r.name}</span>
              <span className={`ml-auto mono-tag text-[9px] px-1.5 py-0.5 rounded-full ${RISK_BADGE[r.severity].bg} ${RISK_BADGE[r.severity].text}`}>{RISK_BADGE[r.severity].label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value, negative, onClick }: { label: string; value: string; negative?: boolean; onClick?: () => void }) {
  return (
    <button onClick={onClick} className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-3.5 text-left hover:bg-[#F5EFE3]/[0.03] transition-colors">
      <p className="mono-tag text-[9px] text-[#F5EFE3]/20">{label}</p>
      <p className={"text-lg font-bold mt-1 " + (negative ? "text-red-400" : "text-[#F5EFE3]/70")} style={{ fontFamily: "Antonio, sans-serif" }}>{value}</p>
    </button>
  );
}

function ModuleRiskCard({ label, count, onClick }: { label: string; count: number; onClick: () => void }) {
  return (
    <button onClick={onClick} className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-3.5 text-left hover:bg-[#F5EFE3]/[0.03] transition-colors">
      <p className="mono-tag text-[9px] text-[#F5EFE3]/20">{label}</p>
      <p className="text-lg font-bold text-[#F5EFE3]/60 mt-1" style={{ fontFamily: "Antonio, sans-serif" }}>{count}</p>
      <p className="mono-tag text-[9px] text-[#F5EFE3]/15">条风险</p>
    </button>
  );
}

/* ═══════════════════════════════════════════
   2. 加盟分析
   ═══════════════════════════════════════════ */

function FranchiseView({ intelRecords, addIntel }: { intelRecords: IntelRecord[]; addIntel: (r: IntelRecord) => void }) {
  const fa = mockFranchise;
  const risks = useMemo(() => assessFranchiseRisks(fa), [fa]);
  const tricks = useMemo(() => identifySalesTricks(fa.salesPitch), [fa]);
  const hiddenCosts = useMemo(() => identifyHiddenCosts(fa), [fa]);
  const nextQuestions = useMemo(() => generateNextQuestions(fa), [fa]);
  const totalCost = fa.franchiseFee + fa.deposit + fa.equipmentFee + fa.firstInventoryFee + fa.renovationRequirement;
  const [intelOpen, setIntelOpen] = useState(false);
  const [intelSource, setIntelSource] = useState(INTEL_SOURCES[0]);
  const [intelCategory, setIntelCategory] = useState(INTEL_CATEGORIES[0]);
  const [intelContent, setIntelContent] = useState("");
  const [intelReliability, setIntelReliability] = useState<"高" | "中" | "低">("中");

  function submitIntel() {
    if (!intelContent.trim()) return;
    addIntel({
      id: `intel-${Date.now()}`,
      source: intelSource,
      category: intelCategory,
      content: intelContent.trim(),
      reliability: intelReliability,
      timestamp: new Date().toISOString(),
    });
    setIntelContent("");
    setIntelOpen(false);
  }

  return (
    <div className="space-y-5">
      <SectionHeader title={fa.brandName} subtitle="加盟品牌分析" />

      {/* 费用汇总 */}
      <div className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-5">
        <span className="mono-tag text-[10px] text-[#F5EFE3]/20 tracking-wider">费用结构</span>
        <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-[#F5EFE3]/45">
          <Row label="加盟费" value={fmtMoney(fa.franchiseFee)} />
          <Row label="保证金" value={fmtMoney(fa.deposit)} />
          <Row label="设备费" value={fmtMoney(fa.equipmentFee)} />
          <Row label="首批物料" value={fmtMoney(fa.firstInventoryFee)} />
          <Row label="装修费" value={fmtMoney(fa.renovationRequirement)} />
          <Row label="管理费/月" value={fmtMoney(fa.managementFeeMonthly)} />
          <Row label="抽成比例" value={fmtPct(fa.royaltyRate)} />
          <Row label="合同年限" value={`${fa.contractYears}年`} />
        </div>
        <div className="mt-3 pt-3 border-t border-[#F5EFE3]/6 flex justify-between">
          <span className="text-xs font-medium text-[#F5EFE3]/50">总投资</span>
          <span className="text-sm font-bold text-[#F5EFE3]/70" style={{ fontFamily: "Antonio, sans-serif" }}>{fmtMoney(totalCost)}</span>
        </div>
      </div>

      {/* 情报档案 */}
      <div className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="mono-tag text-[10px] text-[#F5EFE3]/20 tracking-wider">情报档案 · {intelRecords.length} 条</span>
          <button
            onClick={() => setIntelOpen(!intelOpen)}
            className="rounded-lg bg-[#D9261C] px-3 py-1.5 text-[10px] font-bold text-[#F5EFE3] hover:bg-[#B91C1C] transition-colors"
          >
            + 记一条
          </button>
        </div>

        {/* 快速录入 */}
        {intelOpen && (
          <div className="mb-4 rounded-lg border border-[#F5EFE3]/10 p-3 space-y-2.5">
            <div className="flex gap-2">
              <select value={intelSource} onChange={(e) => setIntelSource(e.target.value)} className="rounded-lg border border-[#F5EFE3]/10 bg-transparent px-2 py-1.5 text-xs text-[#F5EFE3]/50 outline-none">
                {INTEL_SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
              <select value={intelCategory} onChange={(e) => setIntelCategory(e.target.value)} className="rounded-lg border border-[#F5EFE3]/10 bg-transparent px-2 py-1.5 text-xs text-[#F5EFE3]/50 outline-none">
                {INTEL_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <div className="flex gap-1">
                {(["高", "中", "低"] as const).map((r) => (
                  <button key={r} onClick={() => setIntelReliability(r)} className={`rounded-full px-2 py-1 text-[10px] mono-tag ${intelReliability === r ? "bg-[#F5EFE3]/[0.1] text-[#F5EFE3]/60 border border-[#F5EFE3]/20" : "border border-[#F5EFE3]/10 text-[#F5EFE3]/25"}`}>
                    {r}
                  </button>
                ))}
              </div>
            </div>
            <textarea
              value={intelContent}
              onChange={(e) => setIntelContent(e.target.value)}
              placeholder="记下你了解到的信息..."
              rows={2}
              className="w-full resize-none rounded-lg border border-[#F5EFE3]/10 bg-transparent px-3 py-2 text-xs text-[#F5EFE3]/50 outline-none placeholder:text-[#F5EFE3]/15 focus:border-[#F5EFE3]/20"
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setIntelOpen(false)} className="rounded-lg px-3 py-1.5 text-[10px] text-[#F5EFE3]/30 hover:text-[#F5EFE3]/50">取消</button>
              <button onClick={submitIntel} disabled={!intelContent.trim()} className="rounded-lg bg-[#D9261C] px-3 py-1.5 text-[10px] font-bold text-[#F5EFE3] hover:bg-[#B91C1C] disabled:opacity-30">记录</button>
            </div>
          </div>
        )}

        {/* 已收集的情报 */}
        {intelRecords.length > 0 ? (
          <div className="space-y-2">
            {intelRecords.map((r) => (
              <div key={r.id} className="rounded-lg border border-[#F5EFE3]/6 p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="mono-tag text-[9px] text-[#F5EFE3]/25">{r.source}</span>
                  <span className="mono-tag text-[9px] text-[#F5EFE3]/25">{r.category}</span>
                  <span className={`mono-tag text-[9px] px-1.5 py-0.5 rounded-full ${r.reliability === "高" ? "bg-emerald-500/10 text-emerald-400/60" : r.reliability === "中" ? "bg-amber-500/10 text-amber-400/60" : "bg-[#F5EFE3]/[0.05] text-[#F5EFE3]/20"}`}>{r.reliability}可信</span>
                  <span className="mono-tag text-[8px] text-[#F5EFE3]/15 ml-auto">{r.timestamp.slice(5, 10)}</span>
                </div>
                <p className="text-xs text-[#F5EFE3]/45 leading-relaxed">{r.content}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-[#F5EFE3]/20">从各个渠道收集到的品牌信息，随手记在这里。</p>
        )}
      </div>

      {/* 条款 */}
      <div className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-5">
        <span className="mono-tag text-[10px] text-[#F5EFE3]/20 tracking-wider">合同条款</span>
        <div className="mt-3 space-y-2 text-xs">
          <Clause label="强制采购" value={fa.forcesProcurement ? "是" : "否"} warn={fa.forcesProcurement} />
          <Clause label="区域保护" value={fa.hasTerritoryProtection ? "有" : "无"} warn={!fa.hasTerritoryProtection} />
          <Clause label="承诺回本" value={fa.promisesPaybackPeriod ? `${fa.promisedPaybackMonths}个月` : "无"} warn={!!fa.promisesPaybackPeriod && !!fa.promisedPaybackMonths && fa.promisedPaybackMonths < 8} />
          <Clause label="提供真实数据" value={fa.providesRealStoreData ? "是" : "否"} warn={!fa.providesRealStoreData} />
          <Clause label="可联系老加盟商" value={fa.allowsExistingFranchiseeContact ? "是" : "否"} warn={!fa.allowsExistingFranchiseeContact} />
          <Clause label="退出机制" value={fa.hasExitMechanism ? "有" : "无"} warn={!fa.hasExitMechanism} />
        </div>
      </div>

      {/* 品牌方话术 */}
      <div className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-5">
        <span className="mono-tag text-[10px] text-[#F5EFE3]/20 tracking-wider">品牌方承诺</span>
        <div className="mt-3 space-y-1.5">
          {fa.salesPitch.map((s, i) => (
            <div key={i} className="flex items-center gap-2 text-xs text-[#F5EFE3]/40">
              <span className="text-amber-400/60">⚠</span>
              {s}
            </div>
          ))}
        </div>
      </div>

      {/* 话术识别 */}
      {tricks.length > 0 && (
        <div className="rounded-xl border border-amber-500/15 bg-amber-500/[0.03] p-5">
          <span className="mono-tag text-[10px] text-amber-400/60 tracking-wider">招商话术识别</span>
          <div className="mt-3 space-y-2.5">
            {tricks.map((t, i) => (
              <div key={i} className="rounded-lg border border-amber-500/10 p-3">
                <p className="text-xs font-medium text-amber-400/70">话术：{t.trick}</p>
                <p className="text-[11px] text-[#F5EFE3]/35 mt-1">风险：{t.risk}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 隐藏成本 */}
      <div className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-5">
        <span className="mono-tag text-[10px] text-[#F5EFE3]/20 tracking-wider">可能隐藏成本</span>
        <div className="mt-3 space-y-1.5">
          {hiddenCosts.map((c, i) => (
            <div key={i} className="flex items-center gap-2 text-xs text-[#F5EFE3]/40">
              <span className="text-red-400/50">+</span>
              {c}
            </div>
          ))}
        </div>
      </div>

      {/* 追问清单 */}
      <div className="rounded-xl border border-emerald-500/10 bg-emerald-500/[0.02] p-5">
        <span className="mono-tag text-[10px] text-emerald-400/50 tracking-wider">下一轮必问品牌方</span>
        <div className="mt-3 space-y-2">
          {nextQuestions.map((q, i) => (
            <div key={i} className="flex items-start gap-2">
              <span className="flex size-5 shrink-0 items-center justify-center rounded border border-emerald-500/20 text-[10px] text-emerald-400/50">{i + 1}</span>
              <span className="text-xs text-[#F5EFE3]/45">{q}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 风险 */}
      <RiskList risks={risks} title="加盟风险" />
    </div>
  );
}

/* ═══════════════════════════════════════════
   3. 投资测算
   ═══════════════════════════════════════════ */

function InvestmentView() {
  const result = useMemo(() => calculateInvestment(mockInvestment), []);
  const risks = useMemo(() => assessInvestmentRisks(mockInvestment), []);

  return (
    <div className="space-y-5">
      <SectionHeader title="投资测算" subtitle="基于真实成本结构的回本分析" />

      {/* 关键指标 */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <MetricCard label="初始投资" value={fmtMoney(result.totalInvestment)} />
        <MetricCard label="月固定成本" value={fmtMoney(result.monthlyFixedCost)} />
        <MetricCard label="月净利润" value={fmtMoney(result.monthlyNetProfit)} negative={result.monthlyNetProfit < 0} />
        <MetricCard label="日均保本额" value={fmtMoney(result.breakevenDailyRevenue)} />
        <MetricCard label="日均保本单数" value={result.breakevenDailyOrders === Infinity ? "∞" : `${Math.round(result.breakevenDailyOrders)}单`} />
        <MetricCard label="回本周期" value={result.paybackMonths === Infinity ? "无法回本" : `${result.paybackMonths.toFixed(1)}月`} negative={result.paybackMonths > 18} />
      </div>

      {/* 三情景 */}
      <div className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-5">
        <span className="mono-tag text-[10px] text-[#F5EFE3]/20 tracking-wider">情景模拟</span>
        <div className="mt-3 grid grid-cols-3 gap-3">
          {(["conservative", "neutral", "optimistic"] as const).map((s) => {
            const d = result.scenario[s];
            const label = s === "conservative" ? "保守" : s === "neutral" ? "中性" : "乐观";
            return (
              <div key={s} className="rounded-lg border border-[#F5EFE3]/8 p-3 text-center">
                <p className="mono-tag text-[9px] text-[#F5EFE3]/20">{label}</p>
                <p className={"text-lg font-bold mt-1 " + (d.monthlyProfit < 0 ? "text-red-400" : "text-emerald-400")} style={{ fontFamily: "Antonio, sans-serif" }}>
                  {fmtMoney(d.monthlyProfit)}
                </p>
                <p className="mono-tag text-[9px] text-[#F5EFE3]/15 mt-0.5">
                  {d.paybackMonths < 0 ? "无法回本" : `${d.paybackMonths}月回本`}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* 详细成本 */}
      <div className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-5">
        <span className="mono-tag text-[10px] text-[#F5EFE3]/20 tracking-wider">成本明细</span>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-[#F5EFE3]/45">
          <Row label="加盟费" value={fmtMoney(mockInvestment.franchiseFee)} />
          <Row label="保证金" value={fmtMoney(mockInvestment.deposit)} />
          <Row label="装修费" value={fmtMoney(mockInvestment.renovationCost)} />
          <Row label="设备费" value={fmtMoney(mockInvestment.equipmentCost)} />
          <Row label="首批物料" value={fmtMoney(mockInvestment.firstInventoryCost)} />
          <Row label="其他启动" value={fmtMoney(mockInvestment.otherStartupCost)} />
        </div>
      </div>

      <RiskList risks={risks} title="投资风险" />
    </div>
  );
}

/* ═══════════════════════════════════════════
   4. 选址判断
   ═══════════════════════════════════════════ */

function LocationView() {
  const loc = mockLocation;
  const rentPressure = calcRentPressureIndex(loc.monthlyRent, mockInvestment.averageDailyOrders * mockInvestment.averageOrderValue);
  const risks = useMemo(() => assessLocationRisks(mockLocation, mockInvestment), []);
  const scoutChecklist = useMemo(() => generateScoutChecklist(), []);

  return (
    <div className="space-y-5">
      <SectionHeader title="选址评估" subtitle={`${loc.city} ${loc.district} ${loc.businessAreaType}`} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <MetricCard label="面积" value={`${loc.areaSqm}㎡`} />
        <MetricCard label="月租" value={fmtMoney(loc.monthlyRent)} />
        <MetricCard label="租金压力" value={`${rentPressure}%`} negative={rentPressure > 20} />
        <MetricCard label="竞品数量" value={`${loc.competitorCount500m}家`} negative={loc.competitorCount500m > 8} />
        <MetricCard label="人流" value={`${loc.weekdayFootTraffic}/天`} />
        <MetricCard label="可见度" value={`${loc.storefrontVisibility}/5`} negative={loc.storefrontVisibility <= 2} />
      </div>

      <div className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-5">
        <span className="mono-tag text-[10px] text-[#F5EFE3]/20 tracking-wider">周边环境</span>
        <div className="mt-3 flex flex-wrap gap-2">
          {loc.nearCommunity && <Tag label="靠近社区" />}
          {loc.nearOffice && <Tag label="靠近写字楼" />}
          {loc.nearSchool && <Tag label="靠近学校" />}
          {loc.nearMall && <Tag label="靠近商场" />}
          {loc.nearSubway && <Tag label="靠近地铁" />}
          {loc.nearHospital && <Tag label="靠近医院" />}
          <Tag label={`外卖适配 ${loc.deliveryFit}/5`} />
        </div>
      </div>

      <RiskList risks={risks} title="选址风险" />

      {/* 蹲点观察清单 */}
      <div className="rounded-xl border border-emerald-500/10 bg-emerald-500/[0.02] p-5">
        <span className="mono-tag text-[10px] text-emerald-400/50 tracking-wider">实地蹲点清单</span>
        <p className="text-[11px] text-[#F5EFE3]/25 mt-1 mb-3">建议在以下时段实地观察，记录真实数据</p>
        <div className="space-y-1.5">
          {scoutChecklist.map((item, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="flex size-5 shrink-0 items-center justify-center rounded border border-emerald-500/20 text-[10px] text-emerald-400/40">{i + 1}</span>
              <span className="text-xs text-[#F5EFE3]/40">{item}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   5. 运营驾驶舱
   ═══════════════════════════════════════════ */

function OperationsView() {
  const records = mockOperations;
  const risks = useMemo(() => assessOperationRisks(mockOperations, mockInvestment), []);
  const permRisks = useMemo(() => assessPermissionRisks(mockPermissions), []);
  const ffRisks = useMemo(() => assessFulfillmentRisks(mockFulfillment), []);
  const breakeven = useMemo(() => assessBreakevenAlert(mockOperations, mockInvestment), []);
  const allOpsRisks = useMemo(() => [...risks, ...permRisks, ...ffRisks], [risks, permRisks, ffRisks]);
  const recent = records.slice(-7);
  const avgRevenue = recent.reduce((s, r) => s + r.revenue, 0) / recent.length;
  const avgOrders = recent.reduce((s, r) => s + r.orders, 0) / recent.length;
  const avgMargin = recent.reduce((s, r) => {
    const margin = r.revenue > 0 ? (r.revenue - r.materialCost - r.packagingCost - r.platformCommission - r.lossAmount) / r.revenue : 0;
    return s + margin;
  }, 0) / recent.length;
  const totalProfit = recent.reduce((s, r) => {
    const cogs = r.materialCost + r.packagingCost + r.platformCommission + r.deliverySubsidy + r.discountCost + r.lossAmount;
    const profit = r.revenue - cogs - r.laborCost - r.rentAllocated - r.utilitiesAllocated - r.marketingCost;
    return s + profit;
  }, 0);
  const avgDeliveryRatio = recent.reduce((s, r) => s + r.deliveryOrders, 0) / Math.max(recent.reduce((s, r) => s + r.orders, 0), 1);
  const avgLaborCostRate = recent.reduce((s, r) => s + (r.revenue > 0 ? r.laborCost / r.revenue : 0), 0) / recent.length;
  const result = calculateInvestment(mockInvestment);
  const belowBreakevenDays = recent.filter(r => r.revenue < result.breakevenDailyRevenue).length;
  const healthLevel = belowBreakevenDays >= 5 ? "red" : belowBreakevenDays >= 3 ? "yellow" : "green";

  return (
    <div className="space-y-5">
      <SectionHeader title="运营驾驶舱" subtitle={`近${recent.length}天经营数据`} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard label="日均营收" value={fmtMoney(avgRevenue)} />
        <MetricCard label="日均订单" value={`${Math.round(avgOrders)}单`} />
        <MetricCard label="平均毛利率" value={`${(avgMargin * 100).toFixed(1)}%`} negative={avgMargin < 0.55} />
        <MetricCard label="7天总利润" value={fmtMoney(totalProfit)} negative={totalProfit < 0} />
      </div>

      {/* 每日明细 */}
      <div className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-5">
        <span className="mono-tag text-[10px] text-[#F5EFE3]/20 tracking-wider">每日经营</span>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[#F5EFE3]/6 text-[#F5EFE3]/25">
                <th className="py-2 text-left font-medium">日期</th>
                <th className="py-2 text-right font-medium">营收</th>
                <th className="py-2 text-right font-medium">订单</th>
                <th className="py-2 text-right font-medium">毛利</th>
                <th className="py-2 text-right font-medium">差评</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r) => (
                <tr key={r.date} className="border-b border-[#F5EFE3]/4 last:border-0">
                  <td className="py-2 text-[#F5EFE3]/40">{r.date.slice(5)}</td>
                  <td className="py-2 text-right text-[#F5EFE3]/50">{fmtMoney(r.revenue)}</td>
                  <td className="py-2 text-right text-[#F5EFE3]/50">{r.orders}</td>
                  <td className="py-2 text-right text-[#F5EFE3]/50">{r.revenue > 0 ? ((r.revenue - r.materialCost - r.packagingCost - r.platformCommission - r.lossAmount) / r.revenue * 100).toFixed(0) : 0}%</td>
                  <td className={"py-2 text-right " + (r.badReviews >= 3 ? "text-red-400" : "text-[#F5EFE3]/30")}>{r.badReviews}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <RiskList risks={allOpsRisks} title="运营风险" />

      {/* 收入结构 */}
      <div className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-5">
        <span className="mono-tag text-[10px] text-[#F5EFE3]/20 tracking-wider">收入结构</span>
        <div className="mt-3 grid grid-cols-2 gap-4 text-xs">
          <div>
            <p className="text-[#F5EFE3]/30">堂食占比</p>
            <p className="text-lg font-bold text-[#F5EFE3]/60 mt-1" style={{ fontFamily: "Antonio, sans-serif" }}>{((1 - avgDeliveryRatio) * 100).toFixed(0)}%</p>
          </div>
          <div>
            <p className="text-[#F5EFE3]/30">外卖占比</p>
            <p className={"text-lg font-bold mt-1 " + (avgDeliveryRatio > 0.6 ? "text-amber-400" : "text-[#F5EFE3]/60")} style={{ fontFamily: "Antonio, sans-serif" }}>{(avgDeliveryRatio * 100).toFixed(0)}%</p>
          </div>
          <div>
            <p className="text-[#F5EFE3]/30">人工成本率</p>
            <p className={"text-lg font-bold mt-1 " + (avgLaborCostRate > 0.25 ? "text-red-400" : "text-[#F5EFE3]/60")} style={{ fontFamily: "Antonio, sans-serif" }}>{(avgLaborCostRate * 100).toFixed(1)}%</p>
          </div>
          <div>
            <p className="text-[#F5EFE3]/30">Prime Cost</p>
            <p className="text-lg font-bold text-[#F5EFE3]/60 mt-1" style={{ fontFamily: "Antonio, sans-serif" }}>{((avgMargin + avgLaborCostRate) * 100).toFixed(0)}%</p>
          </div>
        </div>
      </div>

      {/* 经营诊断 */}
      <div className={"rounded-xl border-2 p-5 " + (healthLevel === "red" ? "border-red-500/25 bg-red-500/[0.04]" : healthLevel === "yellow" ? "border-amber-500/20 bg-amber-500/[0.03]" : "border-emerald-500/15 bg-emerald-500/[0.02]")}>
        <div className="flex items-center gap-2 mb-3">
          <span className={"size-2 rounded-full " + (healthLevel === "red" ? "bg-red-400" : healthLevel === "yellow" ? "bg-amber-400" : "bg-emerald-400")} />
          <span className="mono-tag text-[10px] text-[#F5EFE3]/30 tracking-wider">
            今日经营判断：{healthLevel === "red" ? "红色预警" : healthLevel === "yellow" ? "黄色预警" : "正常"}
          </span>
        </div>
        <p className="text-xs text-[#F5EFE3]/45 leading-relaxed">
          {healthLevel === "red"
            ? `连续${belowBreakevenDays}天未达保本线。主要问题：${avgOrders < mockInvestment.averageDailyOrders * 0.8 ? "订单数不足" : "毛利率偏低"}。`
            : healthLevel === "yellow"
            ? `有${belowBreakevenDays}天未达保本线。建议检查毛利率和订单结构。`
            : "当前经营正常，保持策略。"}
        </p>
        {breakeven.cause.length > 0 && (
          <div className="mt-2">
            <p className="mono-tag text-[9px] text-[#F5EFE3]/20">偏差原因：</p>
            {breakeven.cause.map((c, i) => (
              <p key={i} className="text-[11px] text-[#F5EFE3]/35 ml-2">· {c}</p>
            ))}
          </div>
        )}
      </div>

      {/* 保本线预警 */}
      <div className={"rounded-xl border-2 p-5 " + (breakeven.level === "red" ? "border-red-500/25 bg-red-500/[0.04]" : breakeven.level === "yellow" ? "border-amber-500/20 bg-amber-500/[0.03]" : "border-emerald-500/15 bg-emerald-500/[0.02]")}>
        <div className="flex items-center gap-2 mb-2">
          <span className={"size-2 rounded-full " + (breakeven.level === "red" ? "bg-red-400" : breakeven.level === "yellow" ? "bg-amber-400" : "bg-emerald-400")} />
          <span className="mono-tag text-[10px] text-[#F5EFE3]/30 tracking-wider">保本线监控</span>
        </div>
        <p className="text-xs text-[#F5EFE3]/45">{breakeven.message}</p>
      </div>

      {/* 经营权限矩阵 */}
      <div className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-5">
        <span className="mono-tag text-[10px] text-[#F5EFE3]/20 tracking-wider">经营权限矩阵</span>
        <p className="text-[11px] text-[#F5EFE3]/20 mt-1 mb-3">加盟店不是完全自由经营，以下权限受合同和总部SOP约束</p>
        <div className="space-y-2">
          {Object.values(mockPermissions).map((p) => (
            <div key={p.key} className="flex items-center gap-3 rounded-lg border border-[#F5EFE3]/6 px-3 py-2">
              <span className="text-xs text-[#F5EFE3]/50 w-20 shrink-0">{p.label}</span>
              <PermBadge status={p.status} />
              <span className="text-[11px] text-[#F5EFE3]/25 flex-1 truncate">{p.note}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 总部支持兑现度 */}
      <div className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-5">
        <span className="mono-tag text-[10px] text-[#F5EFE3]/20 tracking-wider">总部支持兑现度</span>
        <p className="text-[11px] text-[#F5EFE3]/20 mt-1 mb-3">招商承诺 vs 实际交付</p>
        <div className="space-y-2">
          {Object.values(mockFulfillment).map((f) => (
            <div key={f.key} className="flex items-center gap-3 rounded-lg border border-[#F5EFE3]/6 px-3 py-2">
              <span className="text-xs text-[#F5EFE3]/50 w-24 shrink-0">{f.label}</span>
              <FulfillBadge status={f.status} />
              <span className="text-[11px] text-[#F5EFE3]/25 flex-1 truncate">{f.reality}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 运营动作（带可执行性判断） */}
      <div className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-5">
        <span className="mono-tag text-[10px] text-[#F5EFE3]/20 tracking-wider">运营动作建议</span>
        <p className="text-[11px] text-[#F5EFE3]/20 mt-1 mb-3">每条建议标注所需权限和合同约束</p>
        <div className="space-y-3">
          {mockActions.map((a, i) => (
            <div key={i} className="rounded-lg border border-[#F5EFE3]/6 p-3">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-xs font-medium text-[#F5EFE3]/55">{a.title}</span>
                <PermSmallBadge perm={a.requiredPermission} />
              </div>
              <p className="text-[11px] text-[#F5EFE3]/35 mb-1">原因：{a.reason}</p>
              <p className="text-[11px] text-[#F5EFE3]/30 mb-1">合同约束：{a.contractConstraint}</p>
              <p className="text-[11px] text-[#F5EFE3]/25">下一步：{a.nextStep}</p>
              {a.alternativeAction && (
                <p className="text-[11px] text-amber-400/40 mt-1">替代方案：{a.alternativeAction}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   6. 风险清单
   ═══════════════════════════════════════════ */

function RisksView({ risks }: { risks: RiskItem[] }) {
  const [filter, setFilter] = useState<RiskLevel | "all">("all");
  const filtered = filter === "all" ? risks : risks.filter((r) => r.severity === filter);

  return (
    <div className="space-y-5">
      <SectionHeader title="风险清单" subtitle={`共 ${risks.length} 条风险`} />

      <div className="flex gap-1.5">
        {(["all", "critical", "high", "medium", "low"] as const).map((l) => (
          <button key={l} onClick={() => setFilter(l)} className={`rounded-full px-3 py-1 mono-tag text-[10px] transition-colors ${filter === l ? "bg-[#F5EFE3]/[0.1] text-[#F5EFE3]/60 border border-[#F5EFE3]/20" : "border border-[#F5EFE3]/10 text-[#F5EFE3]/25 hover:border-[#F5EFE3]/20"}`}>
            {l === "all" ? "全部" : RISK_BADGE[l].label}
          </button>
        ))}
      </div>

      <RiskList risks={filtered} />
    </div>
  );
}

/* ═══════════════════════════════════════════
   7. 反馈
   ═══════════════════════════════════════════ */

function FeedbackView({ items, onOpen }: { items: FeedbackItem[]; onOpen: () => void }) {
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <SectionHeader title="反馈记录" subtitle={`${items.length} 条`} />
        <button onClick={onOpen} className="rounded-lg bg-[#D9261C] px-4 py-2 text-xs font-bold text-[#F5EFE3] hover:bg-[#B91C1C] transition-colors">
          + 新反馈
        </button>
      </div>

      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#F5EFE3]/10 p-8 text-center">
          <p className="text-xs text-[#F5EFE3]/20">还没有反馈记录</p>
          <p className="mono-tag text-[9px] text-[#F5EFE3]/15 mt-1">使用过程中发现问题，点右上角「新反馈」</p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((fb) => (
            <div key={fb.id} className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-4">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="mono-tag text-[9px] text-[#F5EFE3]/25">{fb.type}</span>
                <span className={`mono-tag text-[9px] px-1.5 py-0.5 rounded-full ${fb.severity === "high" ? "bg-red-500/15 text-red-400" : fb.severity === "medium" ? "bg-amber-500/15 text-amber-400" : "bg-[#F5EFE3]/[0.06] text-[#F5EFE3]/30"}`}>{fb.severity}</span>
                {fb.page && <span className="mono-tag text-[9px] text-[#F5EFE3]/15">{fb.page}</span>}
              </div>
              <p className="text-xs text-[#F5EFE3]/45">{fb.notes}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════
   Shared Components
   ═══════════════════════════════════════════ */

function SectionHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div>
      <h2 className="text-xl font-bold text-[#F5EFE3]/80" style={{ fontFamily: "Antonio, sans-serif" }}>{title}</h2>
      <p className="mono-tag text-[10px] text-[#F5EFE3]/20 mt-0.5">{subtitle}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-1">
      <span className="text-[#F5EFE3]/30">{label}</span>
      <span className="text-[#F5EFE3]/55">{value}</span>
    </div>
  );
}

function Clause({ label, value, warn }: { label: string; value: string; warn: boolean }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-[#F5EFE3]/30">{label}</span>
      <span className={warn ? "text-red-400" : "text-[#F5EFE3]/55"}>
        {warn && <span className="mr-1">⚠</span>}
        {value}
      </span>
    </div>
  );
}

function Tag({ label }: { label: string }) {
  return <span className="rounded-full border border-[#F5EFE3]/10 px-2.5 py-1 text-[10px] text-[#F5EFE3]/35">{label}</span>;
}

/* ─── Permission & Fulfillment Badges ─── */

function PermBadge({ status }: { status: PermissionStatus }) {
  const config: Record<PermissionStatus, { bg: string; text: string; label: string }> = {
    hq_control: { bg: "bg-red-500/15", text: "text-red-400", label: "总部控制" },
    hq_approval: { bg: "bg-amber-500/15", text: "text-amber-400", label: "需总部审批" },
    store_autonomous: { bg: "bg-emerald-500/15", text: "text-emerald-400", label: "门店自主" },
    unclear: { bg: "bg-[#F5EFE3]/[0.06]", text: "text-[#F5EFE3]/30", label: "合同未明确" },
  };
  const c = config[status];
  return <span className={`mono-tag text-[9px] px-1.5 py-0.5 rounded-full ${c.bg} ${c.text}`}>{c.label}</span>;
}

function FulfillBadge({ status }: { status: FulfillmentStatus }) {
  const config: Record<FulfillmentStatus, { bg: string; text: string; label: string }> = {
    fulfilled: { bg: "bg-emerald-500/15", text: "text-emerald-400", label: "已兑现" },
    partial: { bg: "bg-amber-500/15", text: "text-amber-400", label: "部分兑现" },
    not_fulfilled: { bg: "bg-red-500/15", text: "text-red-400", label: "未兑现" },
    not_agreed: { bg: "bg-[#F5EFE3]/[0.06]", text: "text-[#F5EFE3]/30", label: "未约定" },
    pending: { bg: "bg-blue-500/15", text: "text-blue-400", label: "待验证" },
  };
  const c = config[status];
  return <span className={`mono-tag text-[9px] px-1.5 py-0.5 rounded-full ${c.bg} ${c.text}`}>{c.label}</span>;
}

function PermSmallBadge({ perm }: { perm: string }) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    store_owner: { bg: "bg-emerald-500/10", text: "text-emerald-400/60", label: "门店可自主" },
    brand_approval: { bg: "bg-amber-500/10", text: "text-amber-400/60", label: "需品牌审批" },
    hq_only: { bg: "bg-red-500/10", text: "text-red-400/60", label: "仅总部" },
    unclear: { bg: "bg-[#F5EFE3]/[0.05]", text: "text-[#F5EFE3]/25", label: "权限不明" },
  };
  const c = config[perm] || config.unclear;
  return <span className={`mono-tag text-[8px] px-1.5 py-0.5 rounded-full ${c.bg} ${c.text}`}>{c.label}</span>;
}

function RiskList({ risks, title }: { risks: RiskItem[]; title?: string }) {
  if (risks.length === 0) return null;
  const rb = (l: RiskLevel) => RISK_BADGE[l];

  return (
    <div className="rounded-xl border border-[#F5EFE3]/8 bg-[#F5EFE3]/[0.015] p-5">
      {title && <span className="mono-tag text-[10px] text-[#F5EFE3]/20 tracking-wider">{title} · {risks.length}</span>}
      <div className="mt-3 space-y-3">
        {risks.map((r) => (
          <div key={r.id} className="rounded-lg border border-[#F5EFE3]/6 p-3">
            <div className="flex items-start gap-2 mb-1.5">
              <span className={`mt-0.5 size-1.5 rounded-full ${rb(r.severity).text === "text-red-400" ? "bg-red-400" : rb(r.severity).text === "text-amber-400" ? "bg-amber-400" : "bg-emerald-400"}`} />
              <span className="text-xs font-medium text-[#F5EFE3]/55">{r.name}</span>
              <span className={`ml-auto mono-tag text-[9px] px-1.5 py-0.5 rounded-full ${rb(r.severity).bg} ${rb(r.severity).text}`}>{rb(r.severity).label}</span>
            </div>
            <p className="text-[11px] text-[#F5EFE3]/30 ml-4">{r.evidence}</p>
            <p className="text-[11px] text-[#F5EFE3]/25 ml-4 mt-0.5">→ {r.suggestedAction}</p>
            <div className="flex items-center gap-2 ml-4 mt-1.5">
              <span className={`mono-tag text-[8px] px-1.5 py-0.5 rounded-full ${r.status === "verified" ? "bg-emerald-500/10 text-emerald-400/60" : r.status === "unverified" ? "bg-amber-500/10 text-amber-400/60" : "bg-[#F5EFE3]/[0.05] text-[#F5EFE3]/20"}`}>
                {r.status === "verified" ? "已验证" : r.status === "unverified" ? "待验证" : r.status === "resolved" ? "已解决" : "暂缓"}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FeedbackModal({ onClose, onSubmit }: { onClose: () => void; onSubmit: (fb: FeedbackItem) => void }) {
  const [type, setType] = useState<FeedbackItem["type"]>("ux");
  const [severity, setSeverity] = useState<FeedbackItem["severity"]>("medium");
  const [page, setPage] = useState("");
  const [notes, setNotes] = useState("");
  const [expected, setExpected] = useState("");

  function submit() {
    if (!notes.trim()) return;
    onSubmit({
      id: `fb-${Date.now()}`,
      type,
      severity,
      page,
      context: "",
      notes: notes.trim(),
      expectedResult: expected.trim(),
      createdAt: new Date().toISOString(),
    });
  }

  const TYPES: { value: FeedbackItem["type"]; label: string }[] = [
    { value: "ux", label: "UX" },
    { value: "workflow", label: "流程" },
    { value: "cognition", label: "认知" },
    { value: "missing_data", label: "缺失" },
    { value: "false_need", label: "假需求" },
    { value: "blocker", label: "阻塞" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="w-[420px] rounded-xl border border-[#F5EFE3]/10 bg-[#0A0A0A] p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <span className="mono-tag text-[10px] text-[#F5EFE3]/30 tracking-wider">QUICK FEEDBACK</span>
          <button onClick={onClose} className="text-[#F5EFE3]/20 hover:text-[#F5EFE3]/50"><X className="size-3.5" /></button>
        </div>

        <div className="mb-3">
          <span className="mono-tag text-[9px] text-[#F5EFE3]/20 mb-1.5 block">类型</span>
          <div className="flex flex-wrap gap-1.5">
            {TYPES.map((t) => (
              <button key={t.value} onClick={() => setType(t.value)} className={`rounded-full px-2.5 py-1 mono-tag text-[10px] transition-colors ${type === t.value ? "bg-[#D9261C] text-[#F5EFE3]" : "border border-[#F5EFE3]/10 text-[#F5EFE3]/30 hover:border-[#F5EFE3]/20"}`}>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mb-3">
          <span className="mono-tag text-[9px] text-[#F5EFE3]/20 mb-1.5 block">严重程度</span>
          <div className="flex gap-1.5">
            {(["low", "medium", "high"] as const).map((s) => (
              <button key={s} onClick={() => setSeverity(s)} className={`rounded-full px-3 py-1 mono-tag text-[10px] transition-colors ${severity === s ? "bg-[#F5EFE3]/[0.1] text-[#F5EFE3]/60 border border-[#F5EFE3]/20" : "border border-[#F5EFE3]/10 text-[#F5EFE3]/25"}`}>
                {s === "low" ? "低" : s === "medium" ? "中" : "高"}
              </button>
            ))}
          </div>
        </div>

        <div className="mb-3">
          <span className="mono-tag text-[9px] text-[#F5EFE3]/20 mb-1.5 block">出现位置</span>
          <input value={page} onChange={(e) => setPage(e.target.value)} placeholder="哪个模块/页面" className="w-full rounded-lg border border-[#F5EFE3]/10 bg-transparent px-3 py-2 text-xs text-[#F5EFE3]/50 outline-none placeholder:text-[#F5EFE3]/15 focus:border-[#F5EFE3]/20" />
        </div>

        <div className="mb-3">
          <span className="mono-tag text-[9px] text-[#F5EFE3]/20 mb-1.5 block">具体描述 *</span>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="遇到了什么问题？" rows={3} className="w-full resize-none rounded-lg border border-[#F5EFE3]/10 bg-transparent px-3 py-2 text-xs text-[#F5EFE3]/50 outline-none placeholder:text-[#F5EFE3]/15 focus:border-[#F5EFE3]/20" />
        </div>

        <div className="mb-4">
          <span className="mono-tag text-[9px] text-[#F5EFE3]/20 mb-1.5 block">期望结果</span>
          <input value={expected} onChange={(e) => setExpected(e.target.value)} placeholder="你希望怎样？" className="w-full rounded-lg border border-[#F5EFE3]/10 bg-transparent px-3 py-2 text-xs text-[#F5EFE3]/50 outline-none placeholder:text-[#F5EFE3]/15 focus:border-[#F5EFE3]/20" />
        </div>

        <button onClick={submit} disabled={!notes.trim()} className="w-full rounded-lg bg-[#D9261C] py-2 text-xs font-bold text-[#F5EFE3] transition-colors hover:bg-[#B91C1C] disabled:opacity-30">
          提交
        </button>
      </div>
    </div>
  );
}
