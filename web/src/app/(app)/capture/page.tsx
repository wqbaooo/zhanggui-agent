"use client";

import { useCallback, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Archive, Camera, CheckCircle2, FileText, Loader2, Upload, X } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import {
  DEFAULT_PROJECT_ID, addOperation, createDocument, recognizeCapture,
  type DailyOperationEntry, type DocumentFact, type RecognizeField, type RecognizeResponse, type RiskFlag,
} from "@/lib/api";
import { toDateInputValue } from "@/lib/operationDraft";

type CaptureStage =
  | "idle" | "recognizing" | "result" | "saving" | "saved" | "error";

const WRITABLE_FIELDS: Array<keyof DailyOperationEntry> = [
  "revenue", "orders", "food_cost", "labor", "rent_allocated", "utility",
  "other_cost", "takeout_orders", "platform_fee", "marketing_cost", "inventory_loss", "bad_reviews",
];

export default function CapturePage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [stage, setStage] = useState<CaptureStage>("idle");
  const [fileName, setFileName] = useState("");
  const [result, setResult] = useState<RecognizeResponse | null>(null);
  const [entry, setEntry] = useState<DailyOperationEntry | null>(null);
  const [message, setMessage] = useState("");

  const processFile = useCallback(async (file: File) => {
    setFileName(file.name);
    setStage("recognizing");
    try {
      const res = await recognizeCapture(file);
      setResult(res);
      if (res.capture_kind === "operation") {
        const e: DailyOperationEntry = {
          date: toDateInputValue(new Date()), revenue: 0, orders: 0, food_cost: 0, labor: 0,
          rent_allocated: 0, utility: 0, other_cost: 0, takeout_orders: 0,
          platform_fee: 0, marketing_cost: 0, inventory_loss: 0, bad_reviews: 0, notes: "",
        };
        for (const f of res.fields) {
          const k = f.key as keyof DailyOperationEntry;
          if (k in e) (e as unknown as Record<string, number | string>)[k] = f.value;
        }
        setEntry(e);
      }
      setStage("result");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "识别失败");
      setStage("error");
    }
  }, []);

  const handleConfirmOperation = useCallback(async () => {
    if (!entry) return;
    const count = WRITABLE_FIELDS.filter((k) => typeof entry[k] === "number" && entry[k] > 0).length;
    if (count === 0) return;
    setStage("saving");
    try {
      await addOperation(entry, DEFAULT_PROJECT_ID);
      queryClient.invalidateQueries({ queryKey: ["project", DEFAULT_PROJECT_ID] });
      queryClient.invalidateQueries({ queryKey: ["operations", DEFAULT_PROJECT_ID] });
      setStage("saved");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "写入日报失败");
      setStage("error");
    }
  }, [entry, queryClient]);

  const handleConfirmDocument = useCallback(async () => {
    if (!result) return;
    setStage("saving");
    try {
      const docType = result.source_type === "合同/转让协议" ? "转让协议"
        : result.source_type === "总部/SOP资料" ? "其他"
        : result.source_type === "水电费用" ? "水电账单"
        : "其他";
      await createDocument({
        title: fileName,
        doc_type: docType,
        source: result.source_type,
        extracted_fields: Object.fromEntries(result.fields.map((f) => [f.key, f.value])),
        risk_flags: (result.risk_flags || []).map((r) => `${r.title}: ${r.detail}`),
        key_terms: (result.document_facts || []).map((f) => `${f.label}: ${f.value}`),
        notes: result.raw_text?.slice(0, 500) || "",
      }, DEFAULT_PROJECT_ID);
      queryClient.invalidateQueries({ queryKey: ["documents", DEFAULT_PROJECT_ID] });
      setStage("saved");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "归档失败");
      setStage("error");
    }
  }, [result, fileName, queryClient]);

  const reset = useCallback(() => {
    setStage("idle"); setResult(null); setEntry(null); setFileName(""); setMessage("");
  }, []);

  const isOperation = result?.capture_kind === "operation";
  const canConfirmOp = isOperation && entry && WRITABLE_FIELDS.filter((k) => typeof entry[k] === "number" && entry[k] > 0).length > 0;
  const isDocument = result && (result.capture_kind === "document" || (!isOperation && result.fields.length > 0));

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; if (f) processFile(f);
  };

  return (
    <ModulePage module={getModule("/capture")}>

      {stage === "idle" && (
        <section className="rounded-2xl border-2 border-dashed border-primary/25 bg-primary-container/8 p-10 text-center"
          onDrop={(e) => { e.preventDefault(); const f = Array.from(e.dataTransfer.files).find((x) => x.type.startsWith("image/")); if (f) processFile(f); }}
          onDragOver={(e) => e.preventDefault()}
          onPaste={(e) => { const item = Array.from(e.clipboardData.items).find((x) => x.type.startsWith("image/")); const f = item?.getAsFile(); if (f) processFile(new File([f], `粘贴-${Date.now()}.png`, { type: f.type })); }}
          tabIndex={0} role="button">
          <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
          <Camera className="mx-auto h-10 w-10 text-primary/50" />
          <h2 className="mt-4 text-xl font-semibold text-on-background">资料入库</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-on-surface-variant">
            上传截图、合同、进货单、库存照、总部SOP资料。<br />
            系统自动识别来源、抽字段、判断是经营数据还是文档资料。
          </p>
          <div className="mt-6 flex items-center justify-center gap-4">
            <button type="button" onClick={() => fileInputRef.current?.click()} className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-on-primary shadow-lg shadow-primary/20 transition-transform hover:-translate-y-0.5">
              <Upload className="h-4 w-4" />上传资料
            </button>
            <span className="text-xs text-on-surface-variant">或 Ctrl+V 粘贴 · 拖拽图片</span>
          </div>

          <div className="mt-6 grid grid-cols-3 gap-3 text-left">
            {[
              { icon: FileText, label: "经营截图", desc: "客如云日报、美团/淘宝后台、进货单 → 自动抽数字写入日报", color: "text-emerald-600" },
              { icon: Archive, label: "合同证照", desc: "租赁合同、转让协议、健康证、营业执照 → 抽关键条款归档", color: "text-amber-600" },
              { icon: Camera, label: "SOP资料", desc: "总部标准、现场流程、卫生检查 → 识别后转入SOP作业库", color: "text-sky-600" },
            ].map((item) => (
              <div key={item.label} className="rounded-xl border border-white/45 bg-white/42 p-3">
                <item.icon className={`h-5 w-5 ${item.color}`} />
                <p className="mt-2 text-sm font-semibold text-on-background">{item.label}</p>
                <p className="mt-1 text-[11px] leading-relaxed text-on-surface-variant">{item.desc}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {stage === "recognizing" && (
        <section className="rounded-2xl border border-white/45 bg-white/42 p-10 text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" />
          <h2 className="mt-4 text-lg font-semibold text-on-background">正在识别...</h2>
          <p className="mt-2 text-sm text-on-surface-variant">{fileName}</p>
          <p className="mt-1 text-xs text-on-surface-variant">来源识别 → OCR → 字段抽取 → 校验</p>
          <button onClick={reset} className="mt-4 rounded-full border border-muted-border/40 px-4 py-1.5 text-xs text-on-surface-variant">取消</button>
        </section>
      )}

      {stage === "result" && result && (
        <div className="space-y-4">
          {/* 识别结果头 */}
          <section className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-medium text-on-surface-variant">识别结果</p>
                <h2 className="mt-1 text-lg font-semibold text-on-background">{fileName}</h2>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-white/70 px-2.5 py-0.5 text-xs text-on-surface-variant">来源：{result.source_type}</span>
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    isOperation ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                  }`}>
                    {isOperation ? "经营数据 → 日报" : "文档资料 → 资料箱"}
                  </span>
                  {result.fields.length > 0 && (
                    <span className="rounded-full bg-white/70 px-2.5 py-0.5 text-xs text-on-surface-variant">
                      {result.fields.length} 个字段
                    </span>
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={reset} className="rounded-full border border-muted-border/40 px-3 py-1.5 text-xs text-on-surface-variant">重新上传</button>
                {isOperation && (
                  <button onClick={handleConfirmOperation} disabled={!canConfirmOp}
                    className="rounded-full bg-primary px-4 py-1.5 text-xs font-semibold text-on-primary disabled:opacity-40">
                    确认写入日报
                  </button>
                )}
                {isDocument && (
                  <button onClick={handleConfirmDocument}
                    className="rounded-full bg-amber-600 px-4 py-1.5 text-xs font-semibold text-white">
                    确认归档资料箱
                  </button>
                )}
              </div>
            </div>
          </section>

          {/* 经营数据字段编辑 */}
          {isOperation && entry && (
            <section className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <p className="text-xs font-medium text-on-surface-variant">提取的经营字段（可编辑）</p>
              <div className="mt-3 grid grid-cols-3 gap-2 md:grid-cols-6">
                {[
                  { key: "date" as const, label: "日期" },
                  { key: "revenue" as const, label: "营收" },
                  { key: "orders" as const, label: "订单" },
                  { key: "takeout_orders" as const, label: "外卖单" },
                  { key: "food_cost" as const, label: "食材成本" },
                  { key: "labor" as const, label: "人工" },
                  { key: "platform_fee" as const, label: "平台费" },
                  { key: "marketing_cost" as const, label: "营销费" },
                  { key: "bad_reviews" as const, label: "差评" },
                ].map(({ key, label }) => {
                  const field = result.fields.find((f) => f.key === key);
                  return (
                    <label key={key} className="min-w-0">
                      <span className="flex items-center gap-1 text-[10px] text-on-surface-variant">
                        {label}
                        {field && <span className={`h-1.5 w-1.5 rounded-full ${field.confidence === "high" ? "bg-emerald-400" : field.confidence === "medium" ? "bg-amber-400" : "bg-slate-300"}`} />}
                      </span>
                      <input
                        type={key === "date" ? "date" : "number"}
                        value={entry[key] ?? ""}
                        min={key === "date" ? undefined : 0}
                        onChange={(e) => setEntry((prev) => prev ? { ...prev, [key]: key === "date" ? e.target.value : Number(e.target.value) || 0 } : prev)}
                        className={`mt-0.5 w-full rounded-lg border px-2 py-1.5 text-xs text-on-background outline-none focus:border-primary/50 ${field ? "border-primary/30 bg-primary-container/10" : "border-white/50 bg-white/55"}`}
                      />
                    </label>
                  );
                })}
              </div>
              <p className="mt-2 text-[10px] text-on-surface-variant">高亮字段来自识别结果。确认后写入经营日报。</p>
            </section>
          )}

          {/* 文档事实 & 风险 */}
          {isDocument && (
            <div className="grid gap-4 md:grid-cols-2">
              <section className="rounded-2xl border border-white/45 bg-white/42 p-4">
                <p className="text-xs font-medium text-on-surface-variant">提取的关键事实</p>
                {(result.document_facts || []).length > 0 ? (
                  <div className="mt-2 space-y-1.5">
                    {(result.document_facts || []).map((f, i) => (
                      <div key={i} className="flex items-center justify-between rounded-lg bg-white/55 px-3 py-2">
                        <span className="text-xs text-on-surface-variant">{f.label}</span>
                        <span className="text-xs font-semibold text-on-background">{f.value}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-on-surface-variant">未识别到结构化事实，将保存原始OCR文本</p>
                )}
              </section>
              <section className="rounded-2xl border border-white/45 bg-white/42 p-4">
                <p className="text-xs font-medium text-on-surface-variant">风险标记</p>
                {(result.risk_flags || []).length > 0 ? (
                  <div className="mt-2 space-y-1.5">
                    {(result.risk_flags || []).map((r, i) => (
                      <div key={i} className={`rounded-lg px-3 py-2 ${r.level === "high" ? "bg-red-50 border border-red-200" : "bg-amber-50"}`}>
                        <p className={`text-xs font-semibold ${r.level === "high" ? "text-red-700" : "text-amber-700"}`}>{r.title}</p>
                        <p className="mt-0.5 text-[11px] opacity-80">{r.detail}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-on-surface-variant">未识别到明显风险点</p>
                )}
              </section>
            </div>
          )}

          {/* OCR 原文 */}
          {result.raw_text && (
            <section className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <p className="text-xs font-medium text-on-surface-variant">OCR 原文</p>
              <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-xl bg-white/55 p-4 text-xs leading-relaxed text-on-surface-variant">{result.raw_text}</pre>
            </section>
          )}

          {/* 字段列表 */}
          {result.fields.length > 0 && isOperation && (
            <section className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <p className="text-xs font-medium text-on-surface-variant">全部识别字段</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {result.fields.map((f) => (
                  <div key={f.key} className="flex items-center gap-2 rounded-full bg-white/55 px-3 py-1.5">
                    <span className="text-[10px] text-on-surface-variant">{f.label}</span>
                    <span className="text-xs font-semibold text-on-background">{String(f.value)}</span>
                    <span className={`h-1.5 w-1.5 rounded-full ${f.confidence === "high" ? "bg-emerald-400" : f.confidence === "medium" ? "bg-amber-400" : "bg-slate-300"}`} />
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      )}

      {stage === "saving" && (
        <section className="rounded-2xl border border-white/45 bg-white/42 p-10 text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" />
          <h2 className="mt-4 text-lg font-semibold text-on-background">正在写入...</h2>
          <p className="mt-2 text-sm text-on-surface-variant">{fileName}</p>
        </section>
      )}

      {stage === "saved" && (
        <section className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-10 text-center">
          <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600" />
          <h2 className="mt-4 text-xl font-semibold text-on-background">已入库</h2>
          <p className="mt-2 text-sm text-on-surface-variant">
            {isOperation ? "数据已写入经营日报，进入营业走势和利润分析。" : "资料已归档到资料箱，可随时检索。"}
          </p>
          <button onClick={reset} className="mt-6 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-on-primary shadow-sm transition-transform hover:-translate-y-0.5">
            <Upload className="h-4 w-4" />继续录入
          </button>
        </section>
      )}

      {stage === "error" && (
        <section className="rounded-2xl border border-red-200 bg-red-50/60 p-10 text-center">
          <X className="mx-auto h-10 w-10 text-red-500" />
          <h2 className="mt-4 text-xl font-semibold text-on-background">识别失败</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-on-surface-variant">{message}</p>
          <button onClick={reset} className="mt-6 rounded-full bg-on-background px-5 py-2.5 text-sm font-semibold text-inverse-on-surface">重新上传</button>
        </section>
      )}
    </ModulePage>
  );
}
