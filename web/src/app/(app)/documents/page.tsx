"use client";

import { useCallback, useEffect, useState } from "react";
import { CalendarClock, FileSearch, FileText, Filter, Plus, Search, ShieldAlert, X } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { DEFAULT_PROJECT_ID, getDocuments, createDocument, updateDocument, deleteDocument, type StoreDocument } from "@/lib/api";

const DOC_TYPES = ["全部", "租赁合同", "加盟合同", "供应商协议", "营业执照", "食品经营许可", "健康证", "卫生检查", "转让协议", "设备采购", "劳动合同", "保险单据", "水电账单", "其他"];

const statusMap: Record<string, string> = {
  "原始": "bg-blue-100 text-blue-700",
  "已确认": "bg-emerald-100 text-emerald-700",
  "过时": "bg-amber-100 text-amber-700",
};

export default function DocumentsPage() {
  const [docs, setDocs] = useState<StoreDocument[]>([]);
  const [summary, setSummary] = useState<{ total: number; by_type: Record<string, number>; expiring_soon: number } | null>(null);
  const [selected, setSelected] = useState<StoreDocument | null>(null);
  const [filter, setFilter] = useState("全部");
  const [keyword, setKeyword] = useState("");
  const [expiringOnly, setExpiringOnly] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [newForm, setNewForm] = useState({ title: "", doc_type: "其他", sign_date: "", expiry_date: "", notes: "" });
  const [initialized, setInitialized] = useState(false);

  const fetchDocs = useCallback(async () => {
    try {
      const params: Record<string, unknown> = {};
      if (filter !== "全部") params.doc_type = filter;
      if (keyword.trim()) params.keyword = keyword.trim();
      if (expiringOnly) params.expiring_days = 90;
      const res = await getDocuments(DEFAULT_PROJECT_ID, params);
      setDocs(res.documents);
      setSummary(res.summary);
    } catch { /* offline */ }
    setInitialized(true);
  }, [filter, keyword, expiringOnly]);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  const handleAdd = useCallback(async () => {
    if (!newForm.title.trim()) return;
    await createDocument({ title: newForm.title.trim(), doc_type: newForm.doc_type, sign_date: newForm.sign_date, expiry_date: newForm.expiry_date, notes: newForm.notes }, DEFAULT_PROJECT_ID);
    setNewForm({ title: "", doc_type: "其他", sign_date: "", expiry_date: "", notes: "" });
    setShowAdd(false);
    fetchDocs();
  }, [newForm, fetchDocs]);

  const handleStatusToggle = useCallback(async (docId: string, currentStatus: string) => {
    const nextStatus = currentStatus === "已确认" ? "原始" : "已确认";
    await updateDocument(docId, { status: nextStatus }, DEFAULT_PROJECT_ID);
    fetchDocs();
  }, [fetchDocs]);

  const handleDelete = useCallback(async (docId: string) => {
    await deleteDocument(docId, DEFAULT_PROJECT_ID);
    setSelected(null);
    fetchDocs();
  }, [fetchDocs]);

  const isExpiring = (expiry: string) => {
    if (!expiry) return false;
    const d = new Date(expiry);
    const now = new Date();
    const diff = (d.getTime() - now.getTime()) / 86400000;
    return diff >= 0 && diff <= 30;
  };

  return (
    <ModulePage module={getModule("/capture")}>
        <div className="space-y-3">
          {!initialized && <div className="h-0.5 w-full animate-pulse rounded-full bg-primary/30" />}
          {/* 汇总栏 */}
          {initialized && summary && (
            <div className="grid grid-cols-4 gap-2">
              <StatBadge label="资料总数" value={summary.total} />
              <StatBadge label="已确认" value={Object.entries(summary.by_type).filter(([k]) => k !== "total").reduce((s, [, v]) => s + v, 0)} />
              <StatBadge label="即将到期" value={summary.expiring_soon} tone="watch" />
              <StatBadge label="合同类" value={summary.by_type["租赁合同"] || 0 + (summary.by_type["加盟合同"] || 0) + (summary.by_type["供应商协议"] || 0)} />
            </div>
          )}

          {/* 搜索 + 筛选 */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-on-surface-variant/50" />
              <input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="搜索合同、证照、供应商..." className="w-full rounded-xl border border-white/50 bg-white/55 py-1.5 pl-9 pr-3 text-sm outline-none focus:border-primary/50" />
            </div>
            <select value={filter} onChange={(e) => { setFilter(e.target.value); setExpiringOnly(false); }} className="rounded-xl border border-white/50 bg-white/55 px-3 py-1.5 text-sm outline-none">
              {DOC_TYPES.map((t) => (<option key={t}>{t}</option>))}
            </select>
            <button type="button" onClick={() => { setExpiringOnly(!expiringOnly); setFilter("全部"); }} className={`inline-flex items-center gap-1 rounded-xl px-3 py-1.5 text-sm transition-colors ${expiringOnly ? "bg-red-500 text-white" : "border border-white/50 bg-white/55 text-on-surface-variant"}`}>
              <CalendarClock className="h-3.5 w-3.5" />到期
            </button>
            <button type="button" onClick={() => setShowAdd(!showAdd)} className="inline-flex items-center gap-1 rounded-xl bg-primary px-3 py-1.5 text-sm font-semibold text-on-primary">
              <Plus className="h-3.5 w-3.5" />加资料
            </button>
          </div>

          {/* 添加表单 */}
          {showAdd && (
            <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-white/45 bg-white/55 p-3">
              <input value={newForm.title} onChange={(e) => setNewForm((p) => ({ ...p, title: e.target.value }))} placeholder="资料标题" className="min-w-0 flex-1 rounded-xl border border-white/50 bg-white/70 px-3 py-1.5 text-sm outline-none focus:border-primary/50" />
              <select value={newForm.doc_type} onChange={(e) => setNewForm((p) => ({ ...p, doc_type: e.target.value }))} className="rounded-xl border border-white/50 bg-white/70 px-2 py-1.5 text-sm outline-none">
                {DOC_TYPES.filter((t) => t !== "全部").map((t) => (<option key={t}>{t}</option>))}
              </select>
              <input value={newForm.sign_date} onChange={(e) => setNewForm((p) => ({ ...p, sign_date: e.target.value }))} type="date" className="w-32 rounded-xl border border-white/50 bg-white/70 px-2 py-1.5 text-sm outline-none" placeholder="签署日期" />
              <input value={newForm.expiry_date} onChange={(e) => setNewForm((p) => ({ ...p, expiry_date: e.target.value }))} type="date" className="w-32 rounded-xl border border-white/50 bg-white/70 px-2 py-1.5 text-sm outline-none" placeholder="到期日期" />
              <button type="button" onClick={handleAdd} disabled={!newForm.title.trim()} className="rounded-xl bg-primary px-3 py-1.5 text-sm font-semibold text-on-primary disabled:opacity-50">确认</button>
            </div>
          )}

          {/* 资料列表 */}
          {initialized && docs.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-white/60 bg-white/35 p-8 text-center">
              <FileText className="mx-auto h-8 w-8 text-on-surface-variant/40" />
              <p className="mt-3 text-sm font-medium text-on-background">资料箱为空</p>
              <p className="mt-1 text-xs text-on-surface-variant">拍照合同、证照、供应商协议后在这里归档管理</p>
            </div>
          ) : (
            <div className="grid gap-2">
              {docs.map((doc) => (
                <button
                  key={doc.id}
                  type="button"
                  onClick={() => setSelected(selected?.id === doc.id ? null : doc)}
                  className={`rounded-2xl border p-3 text-left transition-colors ${selected?.id === doc.id ? "border-primary/50 bg-primary-container/45" : "border-white/45 bg-white/55 hover:bg-white/80"}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="rounded-full bg-white/70 px-2 py-0.5 text-[10px] font-medium text-on-surface-variant">{doc.doc_type}</span>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${statusMap[doc.status] || "bg-slate-100 text-slate-700"}`}>{doc.status}</span>
                        {isExpiring(doc.expiry_date) && (
                          <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-medium text-red-700">即将到期</span>
                        )}
                      </div>
                      <h3 className="mt-1.5 truncate text-sm font-semibold text-on-background">{doc.title}</h3>
                      {(doc.sign_date || doc.expiry_date) && (
                        <p className="mt-0.5 text-xs text-on-surface-variant">
                          {doc.sign_date ? `${doc.sign_date} 签署` : ""}{doc.sign_date && doc.expiry_date ? " · " : ""}{doc.expiry_date ? `${doc.expiry_date} 到期` : ""}
                        </p>
                      )}
                    </div>
                    {selected?.id === doc.id && (
                      <div className="flex gap-1 shrink-0">
                        <button type="button" onClick={(e) => { e.stopPropagation(); handleStatusToggle(doc.id, doc.status); }} className="rounded-lg bg-white/70 px-2 py-1 text-[10px] font-medium text-on-surface-variant hover:bg-white">
                          {doc.status === "已确认" ? "标记原始" : "确认"}
                        </button>
                        <button type="button" onClick={(e) => { e.stopPropagation(); handleDelete(doc.id); }} className="rounded-lg bg-red-50 px-2 py-1 text-[10px] font-medium text-red-600 hover:bg-red-100">
                          删除
                        </button>
                      </div>
                    )}
                  </div>

                  {/* 展开详情 */}
                  {selected?.id === doc.id && (
                    <div className="mt-3 space-y-2 border-t border-white/40 pt-3">
                      {doc.notes && <p className="text-xs text-on-surface-variant">{doc.notes}</p>}
                      {doc.parties && doc.parties.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {doc.parties.map((p, i) => (<span key={i} className="rounded-full bg-white/70 px-2 py-0.5 text-[10px] text-on-surface-variant">{p}</span>))}
                        </div>
                      )}
                      {doc.key_terms && doc.key_terms.length > 0 && (
                        <div>
                          <p className="text-[10px] font-medium text-on-surface-variant">关键条款</p>
                          <div className="mt-1 flex flex-wrap gap-1">{doc.key_terms.map((t, i) => (<span key={i} className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] text-amber-800">{t}</span>))}</div>
                        </div>
                      )}
                      {doc.risk_flags && doc.risk_flags.length > 0 && (
                        <div>
                          <p className="text-[10px] font-medium text-red-600">风险标记</p>
                          <div className="mt-1 flex flex-wrap gap-1">{doc.risk_flags.map((r, i) => (<span key={i} className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] text-red-700">{r}</span>))}</div>
                        </div>
                      )}
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

function StatBadge({ label, value, tone = "info" }: { label: string; value: number; tone?: string }) {
  const bg = tone === "watch" ? "border-amber-200 bg-amber-50" : "border-sky-200 bg-sky-50";
  const text = tone === "watch" ? "text-amber-800" : "text-sky-800";
  return (
    <div className={`rounded-2xl border p-3 text-center ${bg}`}>
      <p className={`text-xs ${text}`}>{label}</p>
      <p className={`mt-1 text-2xl font-bold ${text}`}>{value}</p>
    </div>
  );
}
