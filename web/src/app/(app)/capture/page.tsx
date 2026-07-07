"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import { useQueryClient } from "@tanstack/react-query";
import { Archive, Camera, CheckCircle2, FileSpreadsheet, FileText, Loader2, Upload, X, ChevronDown, Plus } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import {
  DEFAULT_PROJECT_ID, addOperation, createDocument, createSop, recognizeCapture, previewDeliveryCsv, confirmDeliveryCsv,
  updateMonthlyOperating, writePurchaseOrder, confirmCaptureAudit, getSkus,
  type DailyOperationEntry, type RecognizeResponse, type CsvPreviewResponse, type MonthlyOperatingRecord,
  type PurchaseItemCapture, type SkuItem,
} from "@/lib/api";
import { toDateInputValue } from "@/lib/operationDraft";

type CaptureStage =
  | "idle" | "recognizing" | "result" | "saving" | "saved" | "error";

const WRITABLE_FIELDS: Array<keyof DailyOperationEntry> = [
  "revenue", "orders", "dine_in_revenue", "dine_in_orders", "delivery_revenue", "delivery_orders",
  "food_cost", "packaging_cost", "labor", "rent_allocated", "utility",
  "other_cost", "takeout_orders", "platform_fee", "marketing_cost", "inventory_loss",
  "bad_reviews", "repeat_orders", "new_members",
];

type HistoricalMonthlyDraft = {
  baselineYear: number;
  currentYear: number;
  baselineProfits: Array<number | null>;
  currentRevenues: Array<number | null>;
  monthlyRent: number | null;
  utilityMin: number | null;
  utilityMax: number | null;
  wagePerPerson: number | null;
  previousStaffCount: number | null;
  currentStaffCount: number | null;
  ownerOperates: boolean;
};

type ManualDocumentDraft = {
  sourceType: string;
  date: string;
  amount: string;
  counterparty: string;
  description: string;
};

const DOCUMENT_SOURCE_OPTIONS = [
  "银行转账凭证",
  "POS销售小票",
  "进货单",
  "出餐标签",
  "水电单",
  "合同/协议资料",
  "总部/SOP资料",
  "证照资料",
  "库存照片",
  "其他资料",
];

function buildManualDraft(result: RecognizeResponse): ManualDocumentDraft {
  const fact = (label: string) => (result.document_facts || []).find((item) => item.label.includes(label) && item.confidence !== "low")?.value || "";
  const field = (key: string) => result.fields.find((item) => item.key === key && item.confidence !== "low")?.value;
  return {
    sourceType: result.source_type === "未知" || result.source_type === "本地 OCR" ? "其他资料" : result.source_type,
    date: String(field("date") || fact("日期") || ""),
    amount: String(field("amount") || fact("金额") || fact("总额") || ""),
    counterparty: String(fact("供应商") || fact("交易对方") || ""),
    description: String(fact("商品") || fact("用途") || ""),
  };
}

function buildPurchaseItems(result: RecognizeResponse): PurchaseItemCapture[] {
  const payloadItems = result.structured_artifact?.write_payloads?.purchase_order?.items;
  const lineItems = payloadItems || result.structured_artifact?.canonical_sections?.line_items || [];
  return lineItems.flatMap((item) => {
    const value = item as Record<string, unknown>;
    const name = String(value.name || value.product_name || "").trim();
    if (!name) return [];
    return [{
      name,
      quantity: Number(value.quantity || value.qty || 0),
      unit_cost: Number(value.unit_cost || value.price || 0),
    }];
  });
}

export default function CapturePage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const csvInputRef = useRef<HTMLInputElement>(null);
  const [stage, setStage] = useState<CaptureStage>("idle");
  const [csvPreview, setCsvPreview] = useState<CsvPreviewResponse | null>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvStrategy, setCsvStrategy] = useState<string>("overwrite");
  const [fileName, setFileName] = useState("");
  const [result, setResult] = useState<RecognizeResponse | null>(null);
  const [entry, setEntry] = useState<DailyOperationEntry | null>(null);
  const [originalValues, setOriginalValues] = useState<Record<string, number | string>>({});
  const [historicalDraft, setHistoricalDraft] = useState<HistoricalMonthlyDraft | null>(null);
  const [message, setMessage] = useState("");
  const [recognizeStage, setRecognizeStage] = useState(0);
  const [manualDraft, setManualDraft] = useState<ManualDocumentDraft | null>(null);
  const [purchaseItems, setPurchaseItems] = useState<PurchaseItemCapture[]>([]);
  const [skuList, setSkuList] = useState<SkuItem[]>([]);
  const [skuDropdownIndex, setSkuDropdownIndex] = useState<number | null>(null);
  const [skuSearch, setSkuSearch] = useState("");

  const processFile = useCallback(async (file: File) => {
    setFileName(file.name);
    setStage("recognizing");
    setRecognizeStage(0);

    // 模拟分阶段进度
    const stages = ["正在上传图片...", "正在 OCR 识别文字...", "正在分类资料类型...", "正在抽取字段...", "正在校验数据..."];
    let stageTimer: ReturnType<typeof setTimeout>;
    const advanceStage = () => {
      setRecognizeStage((prev) => {
        if (prev < stages.length - 1) {
          stageTimer = setTimeout(advanceStage, 4000);
          return prev + 1;
        }
        return prev;
      });
    };
    stageTimer = setTimeout(advanceStage, 2000);

    try {
      const res = await recognizeCapture(file);
      clearTimeout(stageTimer);
      setRecognizeStage(stages.length - 1);
      setResult(res);
      setManualDraft(buildManualDraft(res));
      setPurchaseItems(buildPurchaseItems(res));
      if (res.capture_kind === "operation") {
        const e: DailyOperationEntry = {
          date: toDateInputValue(new Date()), revenue: 0, orders: 0,
          dine_in_revenue: 0, dine_in_orders: 0, delivery_revenue: 0, delivery_orders: 0,
          food_cost: 0, packaging_cost: 0, labor: 0,
          rent_allocated: 0, utility: 0, other_cost: 0, takeout_orders: 0,
          platform_fee: 0, marketing_cost: 0, inventory_loss: 0,
          bad_reviews: 0, repeat_orders: 0, new_members: 0, notes: "",
        };
        const orig: Record<string, number | string> = {};
        for (const f of res.fields) {
          const k = f.key as keyof DailyOperationEntry;
          if (k in e) {
            (e as unknown as Record<string, number | string>)[k] = f.value;
            orig[k] = f.value;
          }
        }
        setEntry(e);
        setOriginalValues(orig);
      }
      setStage("result");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "识别失败");
      setStage("error");
    }
  }, []);

  useEffect(() => {
    if (manualDraft?.sourceType === "进货单") {
      getSkus().then((res) => setSkuList(res.skus || [])).catch(() => {});
    }
  }, [manualDraft?.sourceType]);

  const purchaseStats = useMemo(() => {
    const items = purchaseItems.filter((i) => i.name && !i.is_ignored);
    const matched = items.filter((i) => i.sku_id);
    const unmatched = items.filter((i) => !i.sku_id);
    const total = items.reduce((sum, i) => sum + (i.quantity || 0) * (i.unit_cost || 0), 0);
    return {
      total: items.length,
      matched: matched.length,
      unmatched: unmatched.length,
      totalAmount: Math.round(total * 100) / 100,
      allMatched: items.length > 0 && unmatched.length === 0,
    };
  }, [purchaseItems]);

  const filteredSkus = useMemo(() => {
    if (!skuSearch.trim()) return skuList.slice(0, 30);
    const q = skuSearch.toLowerCase();
    return skuList.filter((s) => s.name.toLowerCase().includes(q)).slice(0, 30);
  }, [skuList, skuSearch]);

  useEffect(() => {
    const handleWindowPaste = (event: ClipboardEvent) => {
      if (stage !== "idle") return;
      const item = Array.from(event.clipboardData?.items || []).find((candidate) => candidate.type.startsWith("image/"));
      const file = item?.getAsFile();
      if (!file) return;
      event.preventDefault();
      void processFile(new File([file], `粘贴-${Date.now()}.png`, { type: file.type }));
    };
    window.addEventListener("paste", handleWindowPaste);
    return () => window.removeEventListener("paste", handleWindowPaste);
  }, [processFile, stage]);

  const handleConfirmOperation = useCallback(async () => {
    if (!entry) return;
    const count = WRITABLE_FIELDS.filter((k) => typeof entry[k] === "number" && entry[k] > 0).length;
    if (count === 0) return;
    setStage("saving");
    try {
      // 计算人工修改的字段
      const modifiedFields = WRITABLE_FIELDS.filter((k) => {
        const original = originalValues[k as string];
        const current = entry[k];
        return original !== undefined && Number(original) !== Number(current);
      }).map((k) => String(k));

      const payload: DailyOperationEntry & { human_modified_fields?: string[] } = {
        ...entry,
        source_platform: result?.source_platform as DailyOperationEntry["source_platform"] || entry.source_platform,
        source_file_name: fileName || entry.source_file_name,
        human_modified_fields: modifiedFields,
      };
      await addOperation(payload as DailyOperationEntry, DEFAULT_PROJECT_ID);
      queryClient.invalidateQueries({ queryKey: ["project", DEFAULT_PROJECT_ID] });
      queryClient.invalidateQueries({ queryKey: ["operations", DEFAULT_PROJECT_ID] });
      setStage("saved");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "写入日报失败");
      setStage("error");
    }
  }, [entry, result, fileName, originalValues, queryClient]);

  const handleConfirmDocument = useCallback(async () => {
    if (!result || !manualDraft) return;
    const sourceType = manualDraft.sourceType;
    if (sourceType === "进货单" && !purchaseStats.allMatched) {
      setMessage("还有商品未匹配到 SKU，请先完成匹配或忽略后再确认入库。");
      return;
    }
    setStage("saving");
    try {
      const sourceType = manualDraft.sourceType;
      const docType = sourceType === "店铺转让协议" || sourceType === "合同/协议资料" ? "转让协议"
        : sourceType === "银行转账凭证" ? "付款凭证"
        : sourceType === "POS销售小票" || sourceType === "出餐标签" ? "销售凭证"
        : sourceType === "进货单" ? "进货单"
        : sourceType === "效期管理表" ? "总部通知"
        : sourceType === "总部/SOP资料" ? "其他"
        : sourceType === "水电单" ? "水电账单"
        : "其他";
      await createDocument({
        title: fileName,
        doc_type: docType,
        source: sourceType,
        extracted_fields: {
          ...Object.fromEntries(result.fields.map((f) => [f.key, f.value])),
          confirmed_date: manualDraft.date,
          confirmed_amount: manualDraft.amount,
          confirmed_counterparty: manualDraft.counterparty,
          confirmed_description: manualDraft.description,
          recommended_destination: result.recommended_destination,
          structured_artifact: result.structured_artifact || {},
        },
        risk_flags: (result.risk_flags || []).map((r) => `${r.title}: ${r.detail}`),
        key_terms: (result.document_facts || []).map((f) => `${f.label}: ${f.value}`),
        notes: result.raw_text?.slice(0, 500) || "",
      }, DEFAULT_PROJECT_ID);
      const validPurchaseItems = purchaseItems.filter((item) => item.name && item.quantity > 0 && item.sku_id && !item.is_ignored);
      if (sourceType === "进货单" && validPurchaseItems.length > 0) {
        await writePurchaseOrder({
          date: manualDraft.date || toDateInputValue(new Date()),
          supplier: manualDraft.counterparty || "待确认",
          items: validPurchaseItems,
          file_name: fileName,
          source_type: sourceType,
          human_modified_fields: ["source_type", "date", "amount", "counterparty", "description", "line_items"],
        }, DEFAULT_PROJECT_ID);
        queryClient.invalidateQueries({ queryKey: ["skus", DEFAULT_PROJECT_ID] });
        queryClient.invalidateQueries({ queryKey: ["purchases", DEFAULT_PROJECT_ID] });
      } else {
        await confirmCaptureAudit({
          file_name: fileName,
          source_type: sourceType,
          capture_kind: "document",
          recognized_fields: [
            ...result.fields.map((field) => ({ key: field.key, value: field.value })),
            ...(manualDraft.amount ? [{ key: "amount", value: manualDraft.amount }] : []),
          ],
          human_modified_fields: ["source_type", "date", "amount", "counterparty", "description"],
          write_target: "documents",
          date: manualDraft.date,
        }, DEFAULT_PROJECT_ID);
      }
      const suggestedSop = result.structured_artifact?.suggested_sop;
      if (suggestedSop) {
        await createSop({
          category: suggestedSop.category || "其他",
          title: `${fileName} - ${suggestedSop.title || "SOP草稿"}`,
          source: suggestedSop.source || "图片识别",
          description: result.structured_artifact?.summary || "由图片识别生成的 SOP 草稿，需人工复核。",
          steps: suggestedSop.steps || [],
        }, DEFAULT_PROJECT_ID);
        queryClient.invalidateQueries({ queryKey: ["sops", DEFAULT_PROJECT_ID] });
      }
      queryClient.invalidateQueries({ queryKey: ["documents", DEFAULT_PROJECT_ID] });
      setStage("saved");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "归档失败");
      setStage("error");
    }
  }, [result, manualDraft, purchaseItems, fileName, queryClient, purchaseStats]);

  const reset = useCallback(() => {
    setStage("idle"); setResult(null); setEntry(null); setHistoricalDraft(null); setFileName(""); setMessage(""); setOriginalValues({});
    setManualDraft(null); setPurchaseItems([]);
    setBatchResults([]);
  }, []);

  // 批量录入
  const [batchResults, setBatchResults] = useState<Array<{
    file: File;
    status: "pending" | "processing" | "done" | "error";
    result?: RecognizeResponse;
    error?: string;
  }>>([]);

  const isOperation = result?.capture_kind === "operation";
  const canConfirmOp = isOperation && entry && WRITABLE_FIELDS.filter((k) => typeof entry[k] === "number" && entry[k] > 0).length > 0;
  const isDocument = Boolean(result && !isOperation);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    e.target.value = "";

    if (files.length === 1) {
      void processFile(files[0]);
    } else {
      // 批量模式
      setBatchResults(files.map((f) => ({ file: f, status: "pending" })));
      setStage("result");
      void processBatch(files);
    }
  };

  const processBatch = useCallback(async (files: File[]) => {
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setBatchResults((prev) => prev.map((item, idx) =>
        idx === i ? { ...item, status: "processing" } : item,
      ));
      try {
        const res = await recognizeCapture(file);
        setBatchResults((prev) => prev.map((item, idx) =>
          idx === i ? { ...item, status: "done", result: res } : item,
        ));
      } catch (err) {
        setBatchResults((prev) => prev.map((item, idx) =>
          idx === i ? { ...item, status: "error", error: err instanceof Error ? err.message : "识别失败" } : item,
        ));
      }
    }
  }, []);

  const startHistoricalMonthlyReview = useCallback(() => {
    const currentYear = new Date().getFullYear();
    setHistoricalDraft({
      baselineYear: currentYear - 1,
      currentYear,
      baselineProfits: Array.from({ length: 12 }, () => null),
      currentRevenues: Array.from({ length: 12 }, () => null),
      monthlyRent: 6500,
      utilityMin: 1500,
      utilityMax: 1700,
      wagePerPerson: 3500,
      previousStaffCount: 4,
      currentStaffCount: 1,
      ownerOperates: true,
    });
  }, []);

  const handleConfirmHistoricalMonthly = useCallback(async () => {
    if (!historicalDraft || !result) return;
    const source = {
      review_status: "confirmed" as const,
      source_type: "image_confirmed",
      source_file_name: fileName,
      source_raw_text: result.raw_text || "",
    };
    const entries: MonthlyOperatingRecord[] = [
      ...historicalDraft.baselineProfits.flatMap((value, index) => (
        value === null ? [] : [{ year: historicalDraft.baselineYear, month: index + 1, net_profit: value, ...source }]
      )),
      ...historicalDraft.currentRevenues.flatMap((value, index) => (
        value === null ? [] : [{ year: historicalDraft.currentYear, month: index + 1, revenue: value, ...source }]
      )),
    ];
    if (entries.length === 0) {
      setMessage("至少确认一个月的营业额或净利润");
      return;
    }
    setStage("saving");
    try {
      await updateMonthlyOperating({
        entries,
        monthly_rent: historicalDraft.monthlyRent ?? undefined,
        monthly_utility_min: historicalDraft.utilityMin ?? undefined,
        monthly_utility_max: historicalDraft.utilityMax ?? undefined,
        wage_per_person: historicalDraft.wagePerPerson ?? undefined,
        previous_staff_count: historicalDraft.previousStaffCount ?? undefined,
        current_staff_count: historicalDraft.currentStaffCount ?? undefined,
        owner_operates: historicalDraft.ownerOperates,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["project", DEFAULT_PROJECT_ID] }),
        queryClient.invalidateQueries({ queryKey: ["cockpit", DEFAULT_PROJECT_ID] }),
        queryClient.invalidateQueries({ queryKey: ["monthly", DEFAULT_PROJECT_ID] }),
      ]);
      setMessage(`已确认写入 ${entries.length} 条月度经营记录`);
      setStage("saved");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "月度经营数据写入失败");
      setStage("error");
    }
  }, [fileName, historicalDraft, queryClient, result]);

  const handleCsvImport = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFileName(f.name);
    setCsvFile(f);
    setStage("recognizing");
    try {
      const preview = await previewDeliveryCsv(f);
      setCsvPreview(preview);
      setStage("result");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "CSV 预览失败");
      setStage("error");
    }
  }, []);

  const handleCsvConfirm = useCallback(async () => {
    if (!csvFile) return;
    setStage("saving");
    try {
      const res = await confirmDeliveryCsv(csvFile, csvStrategy);
      setMessage(`导入成功：${res.imported} 条（${csvStrategy}），跳过 ${res.skipped} 条`);
      setStage("saved");
      queryClient.invalidateQueries({ queryKey: ["operations", DEFAULT_PROJECT_ID] });
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "CSV 确认导入失败");
      setStage("error");
    }
  }, [csvFile, csvStrategy, queryClient]);

  return (
    <ModulePage module={getModule("/capture")}>

      {stage === "idle" && (
        <section className="rounded-2xl border-2 border-dashed border-primary/25 bg-primary-container/8 p-10 text-center"
          onDrop={(e) => { e.preventDefault(); const f = Array.from(e.dataTransfer.files).find((x) => x.type.startsWith("image/")); if (f) processFile(f); }}
          onDragOver={(e) => e.preventDefault()}
          tabIndex={0} role="button">
          <input id="capture-image-input" ref={fileInputRef} type="file" accept="image/*" multiple onChange={handleFileChange} className="sr-only" />
          <Camera className="mx-auto h-10 w-10 text-primary/50" />
          <h2 className="mt-4 text-xl font-semibold text-on-background">资料入库</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-on-surface-variant">
            上传截图、合同、进货单、库存照、总部SOP资料。<br />
            系统自动识别来源、抽字段、判断是经营数据还是文档资料。
          </p>
          <div className="mt-6 flex items-center justify-center gap-4">
            <label htmlFor="capture-image-input" className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-on-primary shadow-lg shadow-primary/20 transition-transform hover:-translate-y-0.5 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-primary">
              <Upload className="h-4 w-4" />上传资料
            </label>
            <span className="text-xs text-on-surface-variant">或在页面任意位置 Ctrl/⌘+V 粘贴 · 拖拽图片</span>
            <input ref={csvInputRef} type="file" accept=".csv" onChange={handleCsvImport} className="hidden" />
            <button type="button" onClick={() => csvInputRef.current?.click()} className="inline-flex items-center gap-2 rounded-full border border-white/50 bg-white/55 px-4 py-2 text-xs font-medium text-on-surface-variant hover:bg-white/80">
              <FileSpreadsheet className="h-3.5 w-3.5" />导入 CSV
            </button>
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
          <h2 className="mt-4 text-lg font-semibold text-on-background">
            {["正在上传图片...", "正在 OCR 识别文字...", "正在分类资料类型...", "正在抽取字段...", "正在校验数据..."][recognizeStage]}
          </h2>
          <p className="mt-2 text-sm text-on-surface-variant">{fileName}</p>
          <div className="mx-auto mt-4 w-64">
            <div className="h-1.5 w-full rounded-full bg-white/60 overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-700"
                style={{ width: `${((recognizeStage + 1) / 5) * 100}%` }}
              />
            </div>
            <div className="mt-2 flex justify-between text-[10px] text-on-surface-variant">
              <span className={recognizeStage >= 0 ? "text-primary font-medium" : ""}>上传</span>
              <span className={recognizeStage >= 1 ? "text-primary font-medium" : ""}>OCR</span>
              <span className={recognizeStage >= 2 ? "text-primary font-medium" : ""}>分类</span>
              <span className={recognizeStage >= 3 ? "text-primary font-medium" : ""}>抽取</span>
              <span className={recognizeStage >= 4 ? "text-primary font-medium" : ""}>校验</span>
            </div>
          </div>
          <button onClick={reset} className="mt-6 rounded-full border border-muted-border/40 px-4 py-1.5 text-xs text-on-surface-variant">取消</button>
        </section>
      )}

      {stage === "result" && csvPreview && (
        <div className="space-y-4">
          <section className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <p className="text-xs font-medium text-on-surface-variant">CSV 预览</p>
            <h2 className="mt-1 text-lg font-semibold text-on-background">{csvPreview.file_name}</h2>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-white/70 px-2.5 py-0.5 text-xs text-on-surface-variant">平台：{csvPreview.source_platform}</span>
              <span className="rounded-full bg-white/70 px-2.5 py-0.5 text-xs text-on-surface-variant">{csvPreview.total_rows} 行数据</span>
              <span className="rounded-full bg-white/70 px-2.5 py-0.5 text-xs text-on-surface-variant">列：{csvPreview.columns_detected.join("、")}</span>
            </div>
          </section>
          {csvPreview.warnings.length > 0 && (
            <section className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4">
              <p className="text-xs font-medium text-amber-700">{csvPreview.warnings.length} 条警告</p>
              <div className="mt-2 max-h-40 overflow-y-auto space-y-1">
                {csvPreview.warnings.map((w, i) => (<p key={i} className="text-xs text-amber-600">{w}</p>))}
              </div>
            </section>
          )}
          <section className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <p className="text-xs font-medium text-on-surface-variant">数据预览（前{csvPreview.preview_rows.length}行）</p>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-xs">
                <thead><tr className="border-b border-white/60 text-left text-on-surface-variant"><th className="py-1 pr-2">日期</th><th className="py-1 pr-2 text-right">营收</th><th className="py-1 pr-2 text-right">订单</th><th className="py-1 pr-2 text-right">外卖营收</th><th className="py-1 pr-2 text-right">外卖单</th><th className="py-1 pr-2 text-right">平台费</th><th className="py-1 pr-2 text-right">营销</th><th className="py-1 pr-2 text-right">评分</th></tr></thead>
                <tbody>
                  {csvPreview.preview_rows.map((r, i) => (
                    <tr key={i} className="border-b border-white/30"><td className="py-1 pr-2">{r.date}</td><td className="py-1 pr-2 text-right">¥{r.revenue}</td><td className="py-1 pr-2 text-right">{r.orders}</td><td className="py-1 pr-2 text-right">¥{r.delivery_revenue}</td><td className="py-1 pr-2 text-right">{r.delivery_orders}</td><td className="py-1 pr-2 text-right">¥{r.platform_fee}</td><td className="py-1 pr-2 text-right">¥{r.marketing_cost}</td><td className={`py-1 pr-2 text-right font-bold ${r.source_quality_score === "A" ? "text-emerald-600" : "text-amber-600"}`}>{r.source_quality_score}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <p className="text-xs font-medium text-on-surface-variant">导入策略</p>
            <div className="mt-2 flex gap-2">
              {["overwrite", "merge", "skip_duplicates"].map((s) => (
                <button key={s} onClick={() => setCsvStrategy(s)} className={`rounded-full px-3 py-1.5 text-xs font-medium ${csvStrategy === s ? "bg-primary text-on-primary" : "bg-white/55 text-on-surface-variant"}`}>{s === "overwrite" ? "覆盖" : s === "merge" ? "合并" : "跳过重复"}</button>
              ))}
            </div>
            <div className="mt-3 flex gap-2">
              <button onClick={handleCsvConfirm} className="inline-flex items-center gap-1.5 rounded-full bg-primary px-4 py-2 text-sm font-semibold text-on-primary shadow-sm">
                <CheckCircle2 className="h-3.5 w-3.5" />确认导入
              </button>
              <button onClick={reset} className="rounded-full border border-white/50 px-4 py-2 text-sm font-medium text-on-surface-variant">取消</button>
            </div>
          </section>
        </div>
      )}

      {stage === "result" && batchResults.length > 0 && (
        <section className="rounded-2xl border border-white/45 bg-white/42 p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-xs font-medium text-on-surface-variant">批量录入</p>
              <h3 className="text-lg font-semibold text-on-background">
                {batchResults.length} 张图片处理中
              </h3>
            </div>
            <button
              onClick={() => { setBatchResults([]); setStage("idle"); }}
              className="text-sm text-primary hover:underline"
            >
              返回
            </button>
          </div>
          <div className="space-y-2">
            {batchResults.map((item, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg border border-white/50 bg-white/60 p-3">
                <div className="flex items-center gap-3 min-w-0">
                  {item.status === "pending" && <div className="h-4 w-4 rounded-full bg-slate-200" />}
                  {item.status === "processing" && (
                    <div className="animate-spin h-4 w-4 rounded-full border-2 border-blue-500 border-t-transparent" />
                  )}
                  {item.status === "done" && <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
                  {item.status === "error" && <X className="h-4 w-4 text-red-500" />}
                  <span className="text-sm text-on-background truncate">{item.file.name}</span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {item.result && (
                    <>
                      <span className="text-xs text-on-surface-variant">{item.result.source_type}</span>
                      <button
                        onClick={() => {
                          setResult(item.result!);
                          setFileName(item.file.name);
                          setManualDraft(buildManualDraft(item.result!));
                          setPurchaseItems(buildPurchaseItems(item.result!));
                          const e: DailyOperationEntry = {
                            date: toDateInputValue(new Date()), revenue: 0, orders: 0,
                            dine_in_revenue: 0, dine_in_orders: 0, delivery_revenue: 0, delivery_orders: 0,
                            food_cost: 0, packaging_cost: 0, labor: 0,
                            rent_allocated: 0, utility: 0, other_cost: 0, takeout_orders: 0,
                            platform_fee: 0, marketing_cost: 0, inventory_loss: 0,
                            bad_reviews: 0, repeat_orders: 0, new_members: 0, notes: "",
                          };
                          const orig: Record<string, number | string> = {};
                          if (item.result?.capture_kind === "operation") {
                            for (const f of item.result.fields) {
                              const k = f.key as keyof DailyOperationEntry;
                              if (k in e) {
                                (e as unknown as Record<string, number | string>)[k] = f.value;
                                orig[k] = f.value;
                              }
                            }
                          }
                          setEntry(e);
                          setOriginalValues(orig);
                          setBatchResults([]);
                        }}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        查看详情
                      </button>
                    </>
                  )}
                  {item.status === "error" && (
                    <span className="text-xs text-red-500">{item.error}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {stage === "result" && result && !csvPreview && batchResults.length === 0 && (
        <div className="space-y-4">
          {/* 识别结果头 */}
          <section className="rounded-2xl border border-white/45 bg-white/42 p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-medium text-on-surface-variant">识别结果</p>
                <h2 className="mt-1 text-lg font-semibold text-on-background">{fileName}</h2>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-white/70 px-2.5 py-0.5 text-xs text-on-surface-variant">来源：{manualDraft?.sourceType || result.source_type}</span>
                  {result.source_platform && result.source_platform !== "unknown" && (
                    <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700">
                      渠道：{
                        result.source_platform === "meituan" ? "美团" :
                        result.source_platform === "taobao_flash" ? "淘宝闪购" :
                        result.source_platform === "douyin" ? "抖音" :
                        result.source_platform === "keyun" ? "客如云" :
                        result.source_platform
                      }
                    </span>
                  )}
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
                {result.capture_kind === "unknown" && (
                  <p className="mt-2 text-xs text-amber-700">
                    自动识别不足，资料尚未写入。请选择业务类型并人工核对原图。
                  </p>
                )}
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
                  <button
                    onClick={handleConfirmDocument}
                    disabled={manualDraft?.sourceType === "进货单" && !purchaseStats.allMatched}
                    className="rounded-full bg-amber-600 px-4 py-1.5 text-xs font-semibold text-white disabled:opacity-40">
                    {manualDraft?.sourceType === "进货单" ? "确认入库" : "确认归档资料箱"}
                  </button>
                )}
                {result.capture_kind === "unknown" && !historicalDraft && (
                  <button onClick={startHistoricalMonthlyReview}
                    className="rounded-full bg-on-background px-4 py-1.5 text-xs font-semibold text-inverse-on-surface">
                    整理为历史月度经营表
                  </button>
                )}
              </div>
            </div>
          </section>

          {historicalDraft && (
            <HistoricalMonthlyEditor
              draft={historicalDraft}
              message={message}
              onChange={setHistoricalDraft}
              onConfirm={handleConfirmHistoricalMonthly}
            />
          )}

          {isDocument && manualDraft && !historicalDraft && (
            <section className="rounded-2xl border border-amber-200/70 bg-amber-50/45 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-medium text-amber-800">人工确认</p>
                  <p className="mt-1 text-xs text-amber-700">自动结果可以修改。确认后才会写入资料档案或库存。</p>
                </div>
                {result.capture_kind === "unknown" && (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] text-amber-800">必须选择类型</span>
                )}
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-2 lg:grid-cols-5">
                <label className="min-w-0">
                  <span className="text-[10px] text-on-surface-variant">业务类型</span>
                  <select
                    value={manualDraft.sourceType}
                    onChange={(event) => setManualDraft((prev) => prev ? { ...prev, sourceType: event.target.value } : prev)}
                    className="mt-1 w-full rounded-lg border border-amber-200 bg-white px-2 py-2 text-xs text-on-background outline-none focus:border-amber-500"
                  >
                    {DOCUMENT_SOURCE_OPTIONS.map((option) => <option key={option}>{option}</option>)}
                  </select>
                </label>
                {[
                  { key: "date" as const, label: "日期", type: "date", placeholder: "" },
                  { key: "amount" as const, label: "金额", type: "number", placeholder: "0.00" },
                  { key: "counterparty" as const, label: "供应商/交易对方", type: "text", placeholder: "待确认" },
                  { key: "description" as const, label: "商品/用途", type: "text", placeholder: "补充说明" },
                ].map((item) => (
                  <label key={item.key} className="min-w-0">
                    <span className="text-[10px] text-on-surface-variant">{item.label}</span>
                    <input
                      type={item.type}
                      value={manualDraft[item.key]}
                      placeholder={item.placeholder}
                      onChange={(event) => setManualDraft((prev) => prev ? { ...prev, [item.key]: event.target.value } : prev)}
                      className="mt-1 w-full rounded-lg border border-amber-200 bg-white px-2 py-2 text-xs text-on-background outline-none focus:border-amber-500"
                    />
                  </label>
                ))}
              </div>

              {manualDraft.sourceType === "进货单" && (
                <div className="mt-4 rounded-xl border border-amber-200 bg-white/70 p-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold text-on-background">进货明细 & SKU 匹配</p>
                    <button
                      type="button"
                      onClick={() => setPurchaseItems((items) => [...items, { name: "", quantity: 0, unit_cost: 0 }])}
                      className="flex items-center gap-1 rounded-full border border-amber-300 px-3 py-1 text-xs text-amber-800"
                    >
                      <Plus className="h-3 w-3" /> 添加一项
                    </button>
                  </div>

                  {purchaseItems.length > 0 && (
                    <div className="mt-2 flex items-center gap-3 rounded-lg bg-stone-50 px-3 py-2">
                      <div className="flex items-center gap-1.5">
                        <span className={`h-2 w-2 rounded-full ${purchaseStats.allMatched ? "bg-emerald-500" : "bg-amber-500"}`} />
                        <span className="text-[11px] font-medium text-stone-700">
                          已匹配 {purchaseStats.matched} / {purchaseStats.total}
                        </span>
                      </div>
                      <div className="h-3 w-px bg-stone-200" />
                      <span className="text-[11px] text-stone-500">
                        票面合计 <span className="font-medium text-stone-700 tabular-nums">¥{purchaseStats.totalAmount.toFixed(2)}</span>
                      </span>
                      {!purchaseStats.allMatched && purchaseStats.total > 0 && (
                        <span className="ml-auto text-[10px] text-amber-600">
                          未匹配的商品不会增加库存
                        </span>
                      )}
                    </div>
                  )}

                  {purchaseItems.length === 0 ? (
                    <p className="mt-2 text-xs text-amber-700">未可靠识别出明细。可以添加品名、数量和单价后再确认。</p>
                  ) : (
                    <div className="mt-2 space-y-1.5">
                      {purchaseItems.map((item, index) => {
                        const matchedSku = skuList.find((s) => s.id === item.sku_id);
                        const isOpen = skuDropdownIndex === index;
                        return (
                          <div
                            key={`${item.name}-${index}`}
                            className={`rounded-lg border p-2 transition-colors ${
                              item.is_ignored
                                ? "border-stone-200 bg-stone-50/60 opacity-60"
                                : item.sku_id
                                ? "border-emerald-200 bg-emerald-50/30"
                                : "border-amber-200 bg-amber-50/40"
                            }`}
                          >
                            <div className="grid grid-cols-[minmax(0,1fr)_70px_80px_28px] gap-2">
                              <input
                                value={item.name}
                                placeholder="品名"
                                onChange={(event) => setPurchaseItems((items) =>
                                  items.map((value, itemIndex) =>
                                    itemIndex === index ? { ...value, name: event.target.value } : value
                                  )
                                )}
                                className="rounded-md border border-stone-200 bg-white px-2 py-1.5 text-xs"
                              />
                              <input
                                type="number"
                                min={0}
                                value={item.quantity || ""}
                                placeholder="数量"
                                onChange={(event) => setPurchaseItems((items) =>
                                  items.map((value, itemIndex) =>
                                    itemIndex === index ? { ...value, quantity: Number(event.target.value) || 0 } : value
                                  )
                                )}
                                className="rounded-md border border-stone-200 bg-white px-2 py-1.5 text-xs"
                              />
                              <input
                                type="number"
                                min={0}
                                value={item.unit_cost || ""}
                                placeholder="单价"
                                onChange={(event) => setPurchaseItems((items) =>
                                  items.map((value, itemIndex) =>
                                    itemIndex === index ? { ...value, unit_cost: Number(event.target.value) || 0 } : value
                                  )
                                )}
                                className="rounded-md border border-stone-200 bg-white px-2 py-1.5 text-xs"
                              />
                              <button
                                type="button"
                                aria-label={`删除第${index + 1}项`}
                                onClick={() => setPurchaseItems((items) =>
                                  items.filter((_, itemIndex) => itemIndex !== index)
                                )}
                                className="rounded-md text-stone-400 transition-colors hover:text-red-500"
                              >
                                <X className="h-3.5 w-3.5" />
                              </button>
                            </div>

                            <div className="mt-1.5 flex items-center gap-1.5">
                              <button
                                type="button"
                                onClick={() => {
                                  setSkuDropdownIndex(isOpen ? null : index);
                                  setSkuSearch("");
                                }}
                                className={`flex flex-1 items-center gap-2 rounded-md border px-2 py-1 text-left ${
                                  item.is_ignored
                                    ? "border-stone-200 bg-stone-50 text-stone-400"
                                    : item.sku_id
                                    ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                                    : "border-amber-300 bg-amber-50 text-amber-700"
                                }`}
                                disabled={item.is_ignored}
                              >
                                {matchedSku?.hq_image && !item.is_ignored && (
                                  <Image
                                    src={matchedSku.hq_image}
                                    alt=""
                                    width={28}
                                    height={28}
                                    className="h-7 w-7 flex-shrink-0 rounded object-cover"
                                  />
                                )}
                                <div className="min-w-0 flex-1">
                                  <p className="truncate text-[11px] font-medium">
                                    {item.is_ignored
                                      ? "已忽略"
                                      : matchedSku
                                      ? `✓ ${matchedSku.hq_name || matchedSku.name}`
                                      : "点击选择匹配的 SKU..."}
                                  </p>
                                  {matchedSku && matchedSku.spec && !item.is_ignored && (
                                    <p className="truncate text-[10px] text-emerald-600/70">
                                      {matchedSku.spec}
                                    </p>
                                  )}
                                </div>
                                {!item.is_ignored && <ChevronDown className="h-3 w-3 flex-shrink-0 opacity-60" />}
                              </button>
                              <button
                                type="button"
                                onClick={() => setPurchaseItems((items) =>
                                  items.map((value, itemIndex) =>
                                    itemIndex === index
                                      ? { ...value, is_ignored: !value.is_ignored, sku_id: "" }
                                      : value
                                  )
                                )}
                                className={`rounded-md border px-2 py-1 text-[10px] transition-colors ${
                                  item.is_ignored
                                    ? "border-stone-300 bg-white text-stone-500"
                                    : "border-stone-200 bg-white text-stone-400 hover:text-stone-600"
                                }`}
                              >
                                {item.is_ignored ? "恢复" : "忽略"}
                              </button>
                            </div>

                            {isOpen && !item.is_ignored && (
                              <div className="mt-1.5 rounded-md border border-stone-200 bg-white shadow-sm">
                                <div className="border-b border-stone-100 p-1.5">
                                  <input
                                    autoFocus
                                    value={skuSearch}
                                    onChange={(e) => setSkuSearch(e.target.value)}
                                    placeholder="搜索 SKU 名称..."
                                    className="w-full rounded border border-stone-200 px-2 py-1 text-[11px] outline-none focus:border-amber-300"
                                  />
                                </div>
                                <div className="max-h-48 overflow-y-auto py-1">
                                  {filteredSkus.length === 0 ? (
                                    <p className="px-2 py-3 text-center text-[11px] text-stone-400">未找到匹配的 SKU</p>
                                  ) : (
                                    filteredSkus.map((sku) => (
                                      <button
                                        key={sku.id}
                                        type="button"
                                        onClick={() => {
                                          setPurchaseItems((items) =>
                                            items.map((value, itemIndex) =>
                                              itemIndex === index
                                                ? { ...value, sku_id: sku.id, is_ignored: false }
                                                : value
                                            )
                                          );
                                          setSkuDropdownIndex(null);
                                          setSkuSearch("");
                                        }}
                                        className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-amber-50"
                                      >
                                        {sku.hq_image ? (
                                          <Image src={sku.hq_image} alt="" width={32} height={32} className="h-8 w-8 flex-shrink-0 rounded object-cover" />
                                        ) : (
                                          <div className="h-8 w-8 flex-shrink-0 rounded bg-stone-100" />
                                        )}
                                        <div className="min-w-0 flex-1">
                                          <p className="truncate text-[11px] font-medium text-stone-800">
                                            {sku.hq_name || sku.name}
                                          </p>
                                          <p className="truncate text-[10px] text-stone-400">
                                            {sku.spec || sku.category} · {sku.unit}
                                          </p>
                                        </div>
                                      </button>
                                    ))
                                  )}
                                  <div className="border-t border-stone-100 px-2 py-1.5">
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setPurchaseItems((items) =>
                                          items.map((value, itemIndex) =>
                                            itemIndex === index ? { ...value, sku_id: "" } : value
                                          )
                                        );
                                        setSkuDropdownIndex(null);
                                      }}
                                      className="text-[11px] text-stone-400 hover:text-stone-600"
                                    >
                                      清除匹配
                                    </button>
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </section>
          )}

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
                  const isModified = originalValues[key] !== undefined && Number(originalValues[key]) !== Number(entry[key]);
                  return (
                    <label key={key} className="min-w-0">
                      <span className="flex items-center gap-1 text-[10px] text-on-surface-variant">
                        {label}
                        {field && <span className={`h-1.5 w-1.5 rounded-full ${field.confidence === "high" ? "bg-emerald-400" : field.confidence === "medium" ? "bg-amber-400" : "bg-slate-300"}`} />}
                        {isModified && <span className="text-[10px] text-amber-600 font-medium">已修改</span>}
                      </span>
                      <input
                        type={key === "date" ? "date" : "number"}
                        value={entry[key] ?? ""}
                        min={key === "date" ? undefined : 0}
                        onChange={(e) => setEntry((prev) => prev ? { ...prev, [key]: key === "date" ? e.target.value : Number(e.target.value) || 0 } : prev)}
                        className={`mt-0.5 w-full rounded-lg border px-2 py-1.5 text-xs text-on-background outline-none focus:border-primary/50 ${isModified ? "border-amber-300 bg-amber-50" : field ? "border-primary/30 bg-primary-container/10" : "border-white/50 bg-white/55"}`}
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

          {isDocument && result.structured_artifact?.type && (
            <section className="rounded-2xl border border-white/45 bg-white/42 p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-medium text-on-surface-variant">结构化草稿</p>
                  <h3 className="mt-1 text-base font-semibold text-on-background">
                    {result.structured_artifact.title || "业务对象草稿"}
                  </h3>
                  <p className="mt-1 text-xs leading-relaxed text-on-surface-variant">
                    {result.structured_artifact.summary}
                  </p>
                </div>
                <span className="shrink-0 rounded-full bg-white/70 px-2.5 py-0.5 text-xs text-on-surface-variant">
                  {result.structured_artifact.schema_version || result.structured_artifact.type}
                </span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {result.structured_artifact.document_class && (
                  <span className="rounded-full bg-white/70 px-2.5 py-0.5 text-xs text-on-surface-variant">
                    类型：{result.structured_artifact.document_class}
                  </span>
                )}
                {result.structured_artifact.review_status && (
                  <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs text-amber-700">
                    待人工复核
                  </span>
                )}
                {(result.structured_artifact.write_targets || []).slice(0, 4).map((target) => (
                  <span key={target} className="rounded-full bg-primary-container/20 px-2.5 py-0.5 text-xs text-on-background">
                    {target}
                  </span>
                ))}
              </div>
              {(result.structured_artifact.items || result.structured_artifact.recipes) && (
                <div className="mt-3 max-h-52 overflow-auto rounded-xl bg-white/55 p-3">
                  {(result.structured_artifact.items || result.structured_artifact.recipes || []).slice(0, 8).map((item, i) => (
                    <div key={i} className="border-b border-muted-border/30 py-2 last:border-0">
                      <p className="text-xs font-semibold text-on-background">
                        {String(item.name || item.flavor || item.title || `条目 ${i + 1}`)}
                      </p>
                      <p className="mt-0.5 text-[11px] leading-relaxed text-on-surface-variant">
                        {Object.entries(item).filter(([k]) => !["name", "flavor", "title"].includes(k)).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(" / ") : String(v)}`).join(" · ")}
                      </p>
                    </div>
                  ))}
                </div>
              )}
              {(result.structured_artifact.checklist || result.structured_artifact.quality_checks || result.structured_artifact.ai_next_actions) && (
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {(result.structured_artifact.checklist || result.structured_artifact.quality_checks || []).slice(0, 4).map((item, i) => (
                    <div key={`check-${i}`} className="rounded-lg bg-white/55 px-3 py-2 text-xs text-on-surface-variant">{item}</div>
                  ))}
                  {(result.structured_artifact.ai_next_actions || []).slice(0, 4).map((item, i) => (
                    <div key={`action-${i}`} className="rounded-lg bg-primary-container/20 px-3 py-2 text-xs font-medium text-on-background">{item}</div>
                  ))}
                </div>
              )}
            </section>
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
            {historicalDraft ? message : isOperation ? "数据已写入经营日报，进入营业走势和利润分析。" : "资料已归档到资料箱，可随时检索。"}
          </p>
          {historicalDraft && <a href="/monthly" className="mt-3 inline-block text-sm font-semibold text-primary underline underline-offset-4">查看月度经营模型</a>}
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

function HistoricalMonthlyEditor({
  draft,
  message,
  onChange,
  onConfirm,
}: {
  draft: HistoricalMonthlyDraft;
  message: string;
  onChange: (draft: HistoricalMonthlyDraft) => void;
  onConfirm: () => void;
}) {
  const updateValue = (
    key: "baselineProfits" | "currentRevenues",
    index: number,
    value: string,
  ) => {
    const next = [...draft[key]];
    next[index] = value === "" ? null : Number(value);
    onChange({ ...draft, [key]: next });
  };
  const updateNumber = (
    key: "monthlyRent" | "utilityMin" | "utilityMax" | "wagePerPerson" | "previousStaffCount" | "currentStaffCount",
    value: string,
  ) => onChange({ ...draft, [key]: value === "" ? null : Number(value) });

  return (
    <section className="rounded-2xl border border-amber-200 bg-amber-50/45 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-amber-700">人工确认 · 尚未写入</p>
          <h3 className="mt-1 text-base font-semibold text-on-background">历史月度经营表</h3>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-on-surface-variant">
            左侧录入今年营业额，右侧录入上年已实现净利润。两个指标分别建模，不直接互算同比；看不清的月份请留空。
          </p>
        </div>
        <button type="button" onClick={onConfirm}
          className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-on-primary shadow-sm">
          确认写入月度模型
        </button>
      </div>

      {message && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{message}</p>}

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <MonthlyGrid
          title="今年营业额"
          year={draft.currentYear}
          values={draft.currentRevenues}
          onYearChange={(year) => onChange({ ...draft, currentYear: year })}
          onValueChange={(index, value) => updateValue("currentRevenues", index, value)}
        />
        <MonthlyGrid
          title="上年净利润"
          year={draft.baselineYear}
          values={draft.baselineProfits}
          onYearChange={(year) => onChange({ ...draft, baselineYear: year })}
          onValueChange={(index, value) => updateValue("baselineProfits", index, value)}
        />
      </div>

      <div className="mt-4 rounded-xl border border-white/60 bg-white/55 p-3">
        <p className="text-xs font-medium text-on-surface-variant">成本与人员基线</p>
        <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-6">
          {[
            ["monthlyRent", "月租金", draft.monthlyRent],
            ["utilityMin", "水电下限", draft.utilityMin],
            ["utilityMax", "水电上限", draft.utilityMax],
            ["wagePerPerson", "人均月工资", draft.wagePerPerson],
            ["previousStaffCount", "上家人数", draft.previousStaffCount],
            ["currentStaffCount", "当前员工数", draft.currentStaffCount],
          ].map(([key, label, value]) => (
            <label key={String(key)} className="min-w-0">
              <span className="text-[10px] text-on-surface-variant">{String(label)}</span>
              <input type="number" min={0} value={value ?? ""}
                onChange={(event) => updateNumber(key as Parameters<typeof updateNumber>[0], event.target.value)}
                className="mt-1 w-full rounded-lg border border-white/70 bg-white/80 px-2 py-1.5 text-xs outline-none focus:border-primary/50" />
            </label>
          ))}
        </div>
        <label className="mt-3 flex items-center gap-2 text-xs text-on-surface-variant">
          <input type="checkbox" checked={draft.ownerOperates}
            onChange={(event) => onChange({ ...draft, ownerOperates: event.target.checked })} />
          老板本人参与守店（暂不自动计入员工工资）
        </label>
      </div>
    </section>
  );
}

function MonthlyGrid({
  title,
  year,
  values,
  onYearChange,
  onValueChange,
}: {
  title: string;
  year: number;
  values: Array<number | null>;
  onYearChange: (year: number) => void;
  onValueChange: (index: number, value: string) => void;
}) {
  return (
    <div className="rounded-xl border border-white/60 bg-white/55 p-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold text-on-background">{title}</p>
        <label className="flex items-center gap-1 text-[10px] text-on-surface-variant">
          年份
          <input type="number" min={2000} max={2100} value={year}
            onChange={(event) => onYearChange(Number(event.target.value))}
            className="w-20 rounded-lg border border-white/70 bg-white/80 px-2 py-1 text-xs text-on-background outline-none focus:border-primary/50" />
        </label>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-4">
        {values.map((value, index) => (
          <label key={index} className="min-w-0">
            <span className="text-[10px] text-on-surface-variant">{index + 1}月</span>
            <input type="number" min={0} value={value ?? ""} placeholder="留空"
              onChange={(event) => onValueChange(index, event.target.value)}
              className="mt-0.5 w-full rounded-lg border border-white/70 bg-white/85 px-2 py-1.5 text-xs text-on-background outline-none placeholder:text-on-surface-variant/45 focus:border-primary/50" />
          </label>
        ))}
      </div>
    </div>
  );
}
