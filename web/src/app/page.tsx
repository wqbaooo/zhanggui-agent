"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, MessageCircle, X, Send, Plus } from "lucide-react";
import {
  DEFAULT_PROJECT_ID,
  getProjectCockpit,
  type ProjectCockpit,
  type CockpitAction,
} from "@/lib/api";
import { ProjectOverview } from "@/components/project/project-overview";
import { FinanceTool } from "@/components/artifact/finance-tool";
import { SiteAnalysis } from "@/components/artifact/site-analysis";
import { CompetitorResearch } from "@/components/artifact/competitor-research";
import { RiskRegister } from "@/components/artifact/risk-register";
import { EquipmentList } from "@/components/artifact/equipment-list";
import { MarketingPlan } from "@/components/artifact/marketing-plan";
import { PermitChecklist } from "@/components/artifact/permit-checklist";
import { OperationDashboard } from "@/components/artifact/operation-dashboard";
import { IncomeJournal } from "@/components/artifact/income-journal";
import { apiPost } from "@/lib/api";

type DetailView = "project" | "finance" | "site" | "competitor" | "contract" | "equipment" | "permit" | "marketing" | "operations" | "journal";

interface ChatMessage { role: "user" | "agent"; content: string }

const TITLES: Record<string, string> = {
  project: "项目总览", finance: "财务测算", site: "选址诊断", competitor: "竞品调研",
  contract: "合同与加盟", equipment: "装修与设备", permit: "证照办理", marketing: "营销推广",
  operations: "经营看板", journal: "收支记账",
};

export default function Home() {
  const [cockpit, setCockpit] = useState<ProjectCockpit | null>(null);
  const [detailView, setDetailView] = useState<DetailView | null>(null);

  useEffect(() => {
    getProjectCockpit(DEFAULT_PROJECT_ID, 7).then(setCockpit).catch(() => {});
  }, []);

  return <CaseWorkspace cockpit={cockpit} onNavigate={setDetailView} detailView={detailView} onBack={() => setDetailView(null)} />;
}

function CaseWorkspace({
  cockpit, onNavigate, detailView, onBack,
}: {
  cockpit: ProjectCockpit | null;
  onNavigate: (v: DetailView) => void;
  detailView: DetailView | null;
  onBack: () => void;
}) {
  const profile = cockpit?.profile ?? {};
  const storeName = (profile.店铺名称 as string) || "未命名项目";
  const stage = cockpit?.current_stage || "准备中";
  const actions = cockpit?.next_actions ?? [];
  const alerts = cockpit?.operations?.alerts ?? [];
  const ops = cockpit?.operations;
  const dq = cockpit?.data_quality;

  const [chatOpen, setChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);

  async function sendChat(msg?: string) {
    const m = msg || chatInput.trim();
    if (!m || chatLoading) return;
    setChatInput("");
    setChatLoading(true);
    try {
      const data = await apiPost<{ response: string }>("/api/chat/sync", { message: m });
      setChatHistory((p) => [...p, { role: "user", content: m }, { role: "agent", content: data.response }]);
    } catch {
      setChatHistory((p) => [...p, { role: "user", content: m }, { role: "agent", content: "连接失败" }]);
    } finally {
      setChatLoading(false);
    }
  }

  if (detailView) {
    return <DetailPage view={detailView} onBack={onBack} />;
  }

  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      <div className="flex h-screen flex-col">
        {/* Top Bar */}
        <header className="flex items-center justify-between border-b-2 border-[#F5EFE3]/10 px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="flex size-8 items-center justify-center rounded-[8px] bg-[#D9261C]">
              <span className="text-sm font-bold text-[#F5EFE3]" style={{ fontFamily: "Antonio, sans-serif" }}>K</span>
            </div>
            <span className="text-sm font-bold text-[#F5EFE3]" style={{ fontFamily: "Antonio, sans-serif" }}>KAIDIAN</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="mono-tag text-[#F5EFE3]/40">{storeName}</span>
            {stage && (
              <span className="rounded-full border border-[#F5EFE3]/20 px-2.5 py-0.5 mono-tag text-[10px] text-[#F5EFE3]/50">{stage}</span>
            )}
          </div>
          <div className="flex size-8 items-center justify-center rounded-full bg-gradient-to-br from-[#7FE05A] to-[#0F4C3A]">
            <span className="text-[11px] font-bold text-[#F5EFE3]">W</span>
          </div>
        </header>

        {/* Three Columns */}
        <div className="flex flex-1 overflow-hidden">
          <LeftPanel storeName={storeName} stage={stage} onNavigate={onNavigate} />
          <CenterPanel
            storeName={storeName} stage={stage} actions={actions}
            alerts={alerts} ops={ops ?? null} dq={dq} onNavigate={onNavigate}
          />
          <RightPanel actions={actions} alerts={alerts} onNavigate={onNavigate} />
        </div>
      </div>

      {/* Chat FAB + Panel */}
      <button
        onClick={() => setChatOpen(!chatOpen)}
        className="fixed bottom-5 right-5 z-50 flex size-11 items-center justify-center rounded-full bg-[#0A0A0A] border-2 border-[#F5EFE3]/20 text-[#F5EFE3]/60 shadow-lg transition-colors hover:border-[#F5EFE3]/40 hover:text-[#F5EFE3]"
      >
        {chatOpen ? <X className="size-5" /> : <MessageCircle className="size-5" />}
      </button>

      {chatOpen && (
        <div className="fixed bottom-20 right-5 z-50 flex h-[500px] w-[380px] flex-col rounded-2xl border-2 border-[#0A0A0A] bg-[#F5EFE3] shadow-2xl">
          <div className="flex items-center justify-between border-b-2 border-[#0A0A0A]/10 px-4 py-3">
            <span className="mono-tag text-[#0A0A0A]/40">[ ASSISTANT ]</span>
            <button onClick={() => setChatHistory([])} className="text-[10px] text-[#0A0A0A]/30 mono-tag">清除</button>
          </div>
          <div className="flex-1 overflow-auto px-4 py-3 space-y-3">
            {chatHistory.length === 0 && (
              <p className="text-xs text-[#0A0A0A]/25 mono-tag pt-8 text-center">问点什么...</p>
            )}
            {chatHistory.map((m, i) => (
              <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
                <div className={"max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed " + (m.role === "user" ? "bg-[#0A0A0A] text-[#F5EFE3] rounded-br-md" : "bg-[#0F4C3A] text-[#F5EFE3] rounded-bl-md")}>
                  {m.content}
                </div>
              </div>
            ))}
            {chatLoading && <p className="text-[10px] text-[#0A0A0A]/25 mono-tag">...</p>}
          </div>
          <div className="flex items-center gap-2 border-t-2 border-[#0A0A0A]/10 px-3 py-3">
            <input
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); sendChat(); } }}
              placeholder="问点什么..."
              className="flex-1 bg-transparent text-sm text-[#0A0A0A] outline-none placeholder:text-[#0A0A0A]/25"
              style={{ fontFamily: "Noto Sans SC, sans-serif" }}
            />
            <button onClick={() => sendChat()} disabled={chatLoading} className="flex size-7 items-center justify-center rounded-lg bg-[#0A0A0A] text-[#F5EFE3] disabled:opacity-30">
              <Send className="size-3" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ========== LEFT: Candidate Stack ========== */

function LeftPanel({ storeName, stage }: { storeName: string; stage: string; onNavigate: (v: DetailView) => void }) {
  return (
    <aside className="hidden w-[220px] shrink-0 border-r-2 border-[#F5EFE3]/10 bg-[#0A0A0A] p-4 md:flex md:flex-col">
      <div className="flex items-center justify-between mb-4">
        <span className="mono-tag text-[#F5EFE3]/30">[ CASES ]</span>
        <button className="size-6 flex items-center justify-center rounded-lg border border-[#F5EFE3]/15 text-[#F5EFE3]/25 hover:border-[#F5EFE3]/30 hover:text-[#F5EFE3]/50">
          <Plus className="size-3" />
        </button>
      </div>
      <button className="w-full rounded-xl border border-[#F5EFE3]/15 bg-[#F5EFE3]/[0.06] p-3 text-left transition-colors">
        <p className="text-sm font-medium text-[#F5EFE3]/70">{storeName}</p>
        <div className="mt-1 flex items-center gap-2">
          <span className="mono-tag text-[10px] text-[#F5EFE3]/30">{stage}</span>
          <span className="size-1.5 rounded-full bg-[#7FE05A]" />
        </div>
      </button>
      <button className="mt-3 w-full rounded-xl border border-dashed border-[#F5EFE3]/15 p-3 mono-tag text-[11px] text-[#F5EFE3]/25 hover:border-[#F5EFE3]/30 hover:text-[#F5EFE3]/40">
        [+ 新建案件]
      </button>
    </aside>
  );
}

/* ========== CENTER: Current Case ========== */

function CenterPanel({
  storeName, stage, actions, alerts, ops, dq, onNavigate,
}: {
  storeName: string; stage: string;
  actions: CockpitAction[]; alerts: { level: string; message: string }[];
  ops: ProjectCockpit["operations"] | null;
  dq: ProjectCockpit["data_quality"] | undefined;
  onNavigate: (v: DetailView) => void;
}) {
  return (
    <main className="flex-1 overflow-auto bg-[#0A0A0A] p-5">
      <div className="mx-auto max-w-3xl space-y-5">
        <div>
          <h1 className="text-2xl font-bold text-[#F5EFE3]" style={{ fontFamily: "Antonio, sans-serif" }}>{storeName}</h1>
          <p className="mono-tag text-[#F5EFE3]/25 mt-1">[ {stage} ]</p>
        </div>

        <BlockerCard alerts={alerts} actions={actions} />
        <GatesCard dq={dq} alerts={alerts} />

        <div className="grid gap-4 md:grid-cols-2">
          <EvidenceCard />
          <MissionsCard actions={actions} onNavigate={onNavigate} />
        </div>

        {dq?.has_real_operations && ops && <MetricsCard ops={ops} />}
      </div>
    </main>
  );
}

function BlockerCard({ alerts, actions }: { alerts: { level: string; message: string }[]; actions: CockpitAction[] }) {
  const topAction = actions[0];
  const topAlert = alerts[0];
  const hasHigh = alerts.some((a) => a.level === "high");

  if (!topAction && !topAlert) {
    return (
      <div className="rounded-2xl border-2 border-[#D9261C]/20 bg-[#D9261C]/[0.06] p-5">
        <p className="font-bold text-xl text-[#F5EFE3]" style={{ fontFamily: "Antonio, sans-serif" }}>WAITING FOR DATA</p>
        <p className="text-sm text-[#F5EFE3]/40 mt-2">录入经营数据后，我会分析当前最大的阻塞在哪里。</p>
      </div>
    );
  }

  return (
    <div className={"rounded-2xl p-5 " + (hasHigh ? "border-2 border-[#D9261C]/30 bg-[#D9261C]/[0.08]" : "border-2 border-[#F5EFE3]/10 bg-[#F5EFE3]/[0.03]")}>
      <div className="flex items-center gap-2 mb-2">
        <span className={"size-2 rounded-full " + (hasHigh ? "bg-[#D9261C]" : "bg-[#7FE05A]")} />
        <span className="mono-tag text-[#F5EFE3]/40">[ CURRENT BLOCKER ]</span>
      </div>
      <h2 className="font-bold text-xl text-[#F5EFE3]" style={{ fontFamily: "Antonio, sans-serif" }}>
        {topAlert ? topAlert.message : topAction ? topAction.title : "暂无阻塞"}
      </h2>
      <p className="text-sm text-[#F5EFE3]/40 mt-2">
        {hasHigh ? "这是当前最需要处理的问题。" : "先处理这件事，再推进下一步。"}
      </p>
    </div>
  );
}

function GatesCard({ dq, alerts }: { dq: ProjectCockpit["data_quality"] | undefined; alerts: { level: string; message: string }[] }) {
  const hasOps = dq?.has_real_operations;
  const allClear = alerts.length === 0;
  const gates = [
    { label: "在营加盟商", pass: !!hasOps },
    { label: "退出加盟商", pass: false },
    { label: "财务真实性", pass: !!hasOps },
    { label: "合同审核", pass: allClear },
    { label: "流水验证", pass: !!hasOps },
  ];

  return (
    <div className="rounded-2xl border-2 border-[#F5EFE3]/10 bg-[#F5EFE3]/[0.02] p-5">
      <span className="mono-tag text-[#F5EFE3]/30">[ DECISION GATES ]</span>
      <div className="mt-3 flex flex-wrap gap-3">
        {gates.map((g) => (
          <div key={g.label} className="flex items-center gap-1.5 rounded-full border border-[#F5EFE3]/10 px-3 py-1.5">
            <span>{g.pass ? "🟢" : "🔴"}</span>
            <span className="text-xs text-[#F5EFE3]/50 mono-tag">{g.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function EvidenceCard() {
  const items = [
    { label: "Kill Fast 通过", note: "AI分析", ok: true },
    { label: "知识库匹配", note: "3条相关", ok: true },
    { label: "加盟商访谈", note: "未完成", ok: false },
  ];

  return (
    <div className="rounded-2xl border-2 border-[#F5EFE3]/10 bg-[#F5EFE3]/[0.02] p-5">
      <span className="mono-tag text-[#F5EFE3]/30">[ EVIDENCE ]</span>
      <div className="mt-3 space-y-2.5">
        {items.map((e) => (
          <div key={e.label} className="flex items-center gap-2">
            <span className={e.ok ? "text-[#7FE05A]" : "text-[#F5EFE3]/20"}>✓</span>
            <span className="text-sm text-[#F5EFE3]/50">{e.label}</span>
            <span className="mono-tag text-[10px] text-[#F5EFE3]/20">{e.note}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MissionsCard({ actions, onNavigate }: { actions: CockpitAction[]; onNavigate: (v: DetailView) => void }) {
  const defaultItems: Array<{ id: string; title: string; target: DetailView; done: boolean }> = [
    { id: "1", title: "访谈在营加盟商", target: "project", done: false },
    { id: "2", title: "实地观察门店客流", target: "site", done: false },
    { id: "3", title: "验证合同区域保护", target: "contract", done: false },
    { id: "4", title: "访谈退出加盟商", target: "project", done: false },
  ];
  const displayItems = actions.length > 0 ? defaultItems : defaultItems;

  return (
    <div className="rounded-2xl border-2 border-[#F5EFE3]/10 bg-[#F5EFE3]/[0.02] p-5">
      <span className="mono-tag text-[#F5EFE3]/30">[ MISSIONS ]</span>
      <div className="mt-3 space-y-2">
        {displayItems.map((m) => (
          <button key={m.id} onClick={() => onNavigate(m.target)} className="flex w-full items-center gap-2 rounded-lg py-1.5 text-left hover:bg-[#F5EFE3]/[0.03]">
            <span className={"flex size-5 shrink-0 items-center justify-center rounded border text-[11px] " + (m.done ? "border-[#7FE05A] text-[#7FE05A]" : "border-[#F5EFE3]/20 text-[#F5EFE3]/30")}>
              {m.done ? "✓" : "-"}
            </span>
            <span className={"text-sm " + (m.done ? "text-[#F5EFE3]/30 line-through" : "text-[#F5EFE3]/50")}>{m.title}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function MetricsCard({ ops }: { ops: NonNullable<ProjectCockpit["operations"]> }) {
  return (
    <div className="rounded-2xl border-2 border-[#F5EFE3]/10 bg-[#F5EFE3]/[0.02] p-5">
      <span className="mono-tag text-[#F5EFE3]/30">[ METRICS ]</span>
      <div className="mt-3 flex gap-8">
        <div>
          <p className="text-[10px] mono-tag text-[#F5EFE3]/25">营收</p>
          <p className="mono-num text-lg text-[#F5EFE3]/70">¥{Math.round(ops.total_revenue).toLocaleString()}</p>
        </div>
        <div>
          <p className="text-[10px] mono-tag text-[#F5EFE3]/25">净利润</p>
          <p className={"mono-num text-lg " + (ops.net_profit >= 0 ? "text-[#7FE05A]" : "text-[#D9261C]")}>¥{Math.round(ops.net_profit).toLocaleString()}</p>
        </div>
      </div>
    </div>
  );
}

/* ========== RIGHT: Today ========== */

function RightPanel({ actions, alerts, onNavigate }: { actions: CockpitAction[]; alerts: { level: string; message: string }[]; onNavigate: (v: DetailView) => void }) {
  const top = actions[0];
  const hasHigh = alerts.some((a) => a.level === "high");

  return (
    <aside className="hidden w-[240px] shrink-0 border-l-2 border-[#F5EFE3]/10 bg-[#0A0A0A] p-4 lg:flex lg:flex-col">
      <span className="mono-tag text-[#F5EFE3]/30">[ TODAY ]</span>

      <div className="mt-4 flex-1">
        {top ? (
          <div className="rounded-2xl border-2 border-[#D9261C]/20 bg-[#D9261C]/[0.04] p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className={"size-2 rounded-full " + (hasHigh ? "bg-[#D9261C]" : "bg-[#7FE05A]")} />
              <span className="text-xs font-bold text-[#F5EFE3]/80">今天只做一件事</span>
            </div>
            <p className="text-sm font-semibold text-[#F5EFE3]/60">{top.title}</p>

            <div className="mt-4 space-y-3">
              <div>
                <p className="mono-tag text-[10px] text-[#F5EFE3]/25">[ WHY ]</p>
                <p className="text-xs text-[#F5EFE3]/40 mt-1">{top.priority === "high" ? "这是当前最大的阻塞。先解决它，其他才能推进。" : "完成这一步是推进加盟决策的关键。"}</p>
              </div>
              <div>
                <p className="mono-tag text-[10px] text-[#F5EFE3]/25">[ HOW ]</p>
                <p className="text-xs text-[#F5EFE3]/40 mt-1">进入详情页面，收集相关信息并标记完成。</p>
              </div>
            </div>

            <button onClick={() => onNavigate("project")} className="mt-4 w-full rounded-xl bg-[#F5EFE3] py-2 text-sm font-bold text-[#0A0A0A] transition-colors hover:bg-[#D9261C] hover:text-[#F5EFE3]">
              去处理 →
            </button>
          </div>
        ) : (
          <div className="rounded-2xl border-2 border-dashed border-[#F5EFE3]/10 bg-[#F5EFE3]/[0.02] p-4">
            <p className="text-xs text-[#F5EFE3]/30 mono-tag">[ 暂无待办 ]</p>
            <p className="mt-2 text-xs text-[#F5EFE3]/25">录入数据后，AI 会自动生成今天的优先任务。</p>
          </div>
        )}
      </div>
    </aside>
  );
}

/* ========== Detail Page ========== */

function DetailPage({ view, onBack }: { view: DetailView; onBack: () => void }) {
  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      <div className="mx-auto max-w-5xl px-3 py-3">
        <div className="mb-3 flex items-center gap-3">
          <button onClick={onBack} className="flex size-8 items-center justify-center rounded-xl bg-[#F5EFE3]/10 text-[#F5EFE3]/60 hover:bg-[#F5EFE3]/20 hover:text-[#F5EFE3]">
            <ArrowLeft className="size-4" />
          </button>
          <span className="mono-tag text-[#F5EFE3]/30">[ 工作台 ]</span>
          <span className="text-sm font-bold text-[#F5EFE3]/70">{TITLES[view]}</span>
        </div>
        <div className="rounded-2xl bg-[#F5EFE3] p-5">
          {view === "project" && <ProjectOverview />}
          {view === "finance" && <FinanceTool />}
          {view === "site" && <SiteAnalysis />}
          {view === "competitor" && <CompetitorResearch />}
          {view === "contract" && <RiskRegister />}
          {view === "equipment" && <EquipmentList />}
          {view === "permit" && <PermitChecklist />}
          {view === "marketing" && <MarketingPlan />}
          {view === "operations" && <OperationDashboard />}
          {view === "journal" && <IncomeJournal />}
        </div>
      </div>
    </div>
  );
}
