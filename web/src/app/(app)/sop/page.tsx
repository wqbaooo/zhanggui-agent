"use client";

import { useCallback, useEffect, useState } from "react";
import { BookOpen, Clock, Plus } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { DEFAULT_PROJECT_ID, getSops, createSop, type SopDocument } from "@/lib/api";
import { sopGroups } from "@/data/agent-store-os";

export default function SopPage() {
  const [documents, setDocuments] = useState<SopDocument[]>([]);
  const [summary, setSummary] = useState<{ total: number; by_category: Record<string, number>; by_status: Record<string, number>; stale: number } | null>(null);
  const [activeCat, setActiveCat] = useState<string>("全部");
  const [activeStatus] = useState<string>("全部");
  const [selected, setSelected] = useState<SopDocument | null>(null);
  const [staleOnly, setStaleOnly] = useState(false);
  const [keyword] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newCat, setNewCat] = useState("产品制作");
  const [newSource, setNewSource] = useState("");
  const [initialized, setInitialized] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const params: Record<string, unknown> = {};
      if (activeCat !== "全部") params.category = activeCat;
      if (activeStatus !== "全部") params.status = activeStatus;
      if (keyword.trim()) params.keyword = keyword.trim();
      if (staleOnly) params.stale = true;
      const res = await getSops(DEFAULT_PROJECT_ID, params);
      setDocuments(res.documents);
      setSummary(res.summary);
    } catch { /* offline */ }
    setInitialized(true);
  }, [activeCat, activeStatus, keyword, staleOnly]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleAdd = useCallback(async () => {
    if (!newTitle.trim()) return;
    await createSop({ title: newTitle.trim(), category: newCat, source: newSource }, DEFAULT_PROJECT_ID);
    setNewTitle(""); setNewSource(""); setShowAdd(false);
    fetchData();
  }, [newTitle, newCat, newSource, fetchData]);

  const statusBadge = (status: string) => {
    const map: Record<string, string> = { "草稿": "bg-slate-100 text-slate-700", "已确认": "bg-emerald-100 text-emerald-700", "过时": "bg-amber-100 text-amber-700" };
    return map[status] || "bg-slate-100 text-slate-700";
  };

  return (
    <ModulePage module={getModule("/sop")}>
        <div className="space-y-4">
          {!initialized && <div className="h-0.5 w-full animate-pulse rounded-full bg-primary/30" />}
          {/* Summary bar */}
          {initialized && summary && (
            <div className="grid grid-cols-4 gap-2">
              {[
                { label: "总数", value: summary.total },
                { label: "已确认", value: summary.by_status["已确认"] || 0 },
                { label: "草稿", value: summary.by_status["草稿"] || 0 },
                { label: "待复核", value: summary.stale },
              ].map((s) => (
                <div key={s.label} className="rounded-2xl border border-white/45 bg-white/55 p-3 text-center">
                  <p className="text-[11px] text-on-surface-variant">{s.label}</p>
                  <p className="mt-1 text-xl font-semibold text-on-background">{s.value}</p>
                </div>
              ))}
            </div>
          )}

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex flex-wrap gap-1">
              <button type="button" onClick={() => { setActiveCat("全部"); setStaleOnly(false); }} className={`rounded-full px-3 py-1 text-xs transition-colors ${activeCat === "全部" && !staleOnly ? "bg-on-background text-inverse-on-surface" : "border border-white/45 bg-white/55 text-on-surface-variant hover:bg-white/80"}`}>全部</button>
              {sopGroups.map((cat) => (
                <button key={cat} type="button" onClick={() => { setActiveCat(cat); setStaleOnly(false); }} className={`rounded-full px-3 py-1 text-xs transition-colors ${activeCat === cat ? "bg-on-background text-inverse-on-surface" : "border border-white/45 bg-white/55 text-on-surface-variant hover:bg-white/80"}`}>{cat}</button>
              ))}
            </div>
            <button type="button" onClick={() => { setStaleOnly(!staleOnly); setActiveCat("全部"); }} className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs transition-colors ${staleOnly ? "bg-amber-500 text-white" : "border border-white/45 bg-white/55 text-on-surface-variant hover:bg-white/80"}`}>
              <Clock className="h-3 w-3" /> 待复核
            </button>
            <button type="button" onClick={() => setShowAdd(!showAdd)} className="ml-auto inline-flex items-center gap-1 rounded-full bg-primary px-3 py-1 text-xs font-medium text-on-primary">
              <Plus className="h-3 w-3" /> 加 SOP
            </button>
          </div>

          {showAdd && (
            <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-white/45 bg-white/55 p-3">
              <input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="SOP 标题" className="min-w-0 flex-1 rounded-xl border border-white/50 bg-white/70 px-3 py-1.5 text-sm outline-none focus:border-primary/50" />
              <select value={newCat} onChange={(e) => setNewCat(e.target.value)} className="rounded-xl border border-white/50 bg-white/70 px-2 py-1.5 text-sm outline-none">
                {sopGroups.slice(0, 6).map((c) => (<option key={c}>{c}</option>))}
              </select>
              <input value={newSource} onChange={(e) => setNewSource(e.target.value)} placeholder="来源（总部/现场）" className="w-32 rounded-xl border border-white/50 bg-white/70 px-3 py-1.5 text-sm outline-none" />
              <button type="button" onClick={handleAdd} disabled={!newTitle.trim()} className="rounded-xl bg-primary px-3 py-1.5 text-sm font-semibold text-on-primary disabled:opacity-50">确认</button>
            </div>
          )}

          {/* Document grid */}
          {initialized && documents.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-white/60 bg-white/35 p-8 text-center">
              <BookOpen className="mx-auto h-8 w-8 text-on-surface-variant/40" />
              <p className="mt-3 text-sm font-medium text-on-background">还没有 {activeCat !== "全部" ? activeCat : ""} SOP</p>
              <p className="mt-1 text-xs text-on-surface-variant">拍照总部资料、记录现场流程后在这里创建标准化文档。</p>
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {documents.map((doc) => (
                <button key={doc.id} type="button" onClick={() => setSelected(selected?.id === doc.id ? null : doc)} className={`rounded-2xl border p-4 text-left transition-colors ${selected?.id === doc.id ? "border-primary/50 bg-primary-container/45" : "border-white/45 bg-white/55 hover:bg-white/80"}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-on-surface-variant">{doc.category}</p>
                      <h3 className="mt-1 truncate text-sm font-semibold text-on-background">v{doc.version} {doc.title}</h3>
                    </div>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${statusBadge(doc.status)}`}>{doc.status}</span>
                  </div>
                  {doc.source && <p className="mt-2 text-xs text-on-surface-variant">来源：{doc.source}</p>}
                  {doc.steps.length > 0 && <p className="mt-1 text-xs text-on-surface-variant">{doc.steps.length} 个步骤</p>}

                  {/* Expanded detail */}
                  {selected?.id === doc.id && (
                    <div className="mt-4 space-y-2 border-t border-white/40 pt-3">
                      {doc.description && <p className="text-xs leading-relaxed text-on-surface-variant">{doc.description}</p>}
                      {doc.steps.map((step, i) => (
                        <div key={i} className="flex items-start gap-2 rounded-xl bg-white/60 p-2">
                          <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${step.is_critical ? "bg-red-100 text-red-700" : "bg-white/70 text-on-surface-variant"}`}>{step.order}</span>
                          <div className="min-w-0">
                            <p className="text-xs font-semibold text-on-background">{step.title}</p>
                            {step.description && <p className="mt-0.5 text-xs text-on-surface-variant">{step.description}</p>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
    </ModulePage>
  );
}
