"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import {
  API_BASE,
  DEFAULT_PROJECT_ID,
  confirmBusinessFact,
  confirmCaptureAudit,
  getBusinessFacts,
  markBusinessFact,
  rejectBusinessFact,
  transcribeSpeech,
  updateBusinessFact,
  type BusinessFact,
} from "@/lib/api";
import { FactChatPanel } from "@/components/chat/FactChatPanel";
import { CaptureReviewCard } from "@/components/capture/CaptureReviewCard";
import {
  buildTextNoteReview,
  classifyCaptureSource,
  processCaptureFile,
  processCaptureText,
  type CaptureReview,
  type CaptureSourceType,
} from "@/lib/capture-intake";
import {
  AlertTriangle,
  Camera,
  Check,
  ChevronDown,
  Loader2,
  Maximize2,
  MessageSquare,
  Mic,
  RefreshCw,
  Send,
  Upload,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { toDateInputValue } from "@/lib/operationDraft";

function getAnomalyLabel(fact: BusinessFact): string | null {
  if (fact.anomaly_reason) return fact.anomaly_reason;
  if (fact.missing_fields && fact.missing_fields.length > 0) return `缺字段：${fact.missing_fields.join("、")}`;
  if (fact.duplicate_of) return "疑似重复";
  if (fact.confidence === "low") return "识别置信度低，建议核对原图";
  return null;
}

function getMoreActions(fact: BusinessFact): Array<[string, string]> {
  const salesTypes = new Set(["pos_sale", "net_operating_income", "dine_in_income", "third_party_income", "refund"]);
  const formerOwnerTypes = new Set(["former_owner_transfer", "former_owner_collected", "platform_settlement"]);
  const purchaseTypes = new Set(["purchase", "stock_in", "supplier_invoice"]);
  if (formerOwnerTypes.has(fact.fact_type)) {
    return [
      ["former_owner_collected", "标记前老板代收"],
      ["former_owner_transfer", "确认前老板回款"],
      ["platform_unsettled", "标记平台未结算"],
    ];
  }
  if (purchaseTypes.has(fact.fact_type)) {
    return [
      ["purchase", "确认采购"],
      ["stock_in", "确认入库"],
    ];
  }
  if (salesTypes.has(fact.fact_type)) {
    return [
      ["platform_unsettled", "标记平台未结算"],
      ["refund", "标记退款"],
      ["former_owner_collected", "标记前老板代收"],
    ];
  }
  return [];
}

const QUICK_PROMPTS = [
  "今天营业截图/客如云日报",
  "外卖后台截图",
  "库存照片或缺货描述",
  "进货单/付款凭证",
  "员工考勤或工资",
  "差评/退款/异常事件",
  "总部/SOP/商场通知",
  "老板一句话备注",
];

type WorkStatus = "待确认" | "分析中" | "已入库";
type IntakeItem = { id: string; name: string; source: CaptureSourceType; status: WorkStatus; summary: string };

export default function CapturePage() {
  const [pendingFacts, setPendingFacts] = useState<BusinessFact[]>([]);
  const [factMessage, setFactMessage] = useState("");
  const [factSavingId, setFactSavingId] = useState<string | null>(null);
  const [factAmountDrafts, setFactAmountDrafts] = useState<Record<string, string>>({});
  const [editingAmountId, setEditingAmountId] = useState<string | null>(null);
  const [chatFactId, setChatFactId] = useState<string | null>(null);
  const [expandedMore, setExpandedMore] = useState<Set<string>>(new Set());
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const audioRecorderRef = useRef<MediaRecorder | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const [input, setInput] = useState("");
  const [intakeItems, setIntakeItems] = useState<IntakeItem[]>([]);
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceMessage, setVoiceMessage] = useState("");
  const [draftError, setDraftError] = useState<string | null>(null);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [recognitionStage, setRecognitionStage] = useState<string | null>(null);
  const [recognitionResult, setRecognitionResult] = useState<CaptureReview | null>(null);

  const fetchPendingFacts = useCallback(async () => {
    try {
      const res = await getBusinessFacts(DEFAULT_PROJECT_ID, "need_review");
      setPendingFacts(res.facts || []);
      setFactAmountDrafts(Object.fromEntries((res.facts || []).map((fact) => [fact.id, String(fact.amount ?? 0)])));
    } catch (err) {
      setFactMessage(err instanceof Error ? err.message : "待确认事实加载失败");
    }
  }, []);

  useEffect(() => { void fetchPendingFacts(); }, [fetchPendingFacts]);

  const handleFactAction = useCallback(async (fact: BusinessFact, action: string) => {
    setFactSavingId(fact.id);
    setFactMessage("");
    try {
      if (action === "confirm") await confirmBusinessFact(fact.id);
      else if (action === "reject") await rejectBusinessFact(fact.id);
      else await markBusinessFact(fact.id, action);
      await fetchPendingFacts();
      setFactMessage(action === "confirm" ? "已确认并写入正式钱账/库存账" : action === "reject" ? "已驳回" : "已标记");
    } catch (err) {
      setFactMessage(err instanceof Error ? err.message : "处理失败");
    } finally {
      setFactSavingId(null);
    }
  }, [fetchPendingFacts]);

  const handleSaveAmount = useCallback(async (fact: BusinessFact) => {
    const amount = Number(factAmountDrafts[fact.id]);
    if (!Number.isFinite(amount) || amount === fact.amount) {
      setEditingAmountId(null);
      return;
    }
    setFactSavingId(fact.id);
    try {
      await updateBusinessFact(fact.id, { amount });
      await fetchPendingFacts();
      setFactMessage("金额已修改，请确认入账");
    } catch (err) {
      setFactMessage(err instanceof Error ? err.message : "修改失败");
    } finally {
      setFactSavingId(null);
      setEditingAmountId(null);
    }
  }, [factAmountDrafts, fetchPendingFacts]);

  const toggleMore = useCallback((factId: string) => {
    setExpandedMore((prev) => {
      const next = new Set(prev);
      if (next.has(factId)) next.delete(factId);
      else next.add(factId);
      return next;
    });
  }, []);

  const chatFact = pendingFacts.find((f) => f.id === chatFactId) || null;

  const factImageUrl = useCallback((fact: BusinessFact): string | null => {
    if (!fact.evidence_image_url) return null;
    return `${API_BASE}${fact.evidence_image_url}`;
  }, []);

  const closeRecognitionResult = useCallback(() => {
    setRecognitionResult((current) => {
      if (current?.imageUrl?.startsWith("blob:")) URL.revokeObjectURL(current.imageUrl);
      return null;
    });
    setDraftError(null);
  }, []);
  const cancelRecognitionResult = useCallback(() => {
    const itemId = recognitionResult?.itemId;
    closeRecognitionResult();
    if (itemId) setIntakeItems((current) => current.filter((item) => item.id !== itemId));
  }, [closeRecognitionResult, recognitionResult?.itemId]);

  const registerFile = useCallback(async (file: File) => {
    const source = classifyCaptureSource(file.name);
    const itemId = `${file.name}-${Date.now()}`;
    setIntakeItems((prev) => [{
      id: itemId,
      name: file.name,
      source,
      status: "分析中",
      summary: "正在自动识别资料类型、字段和写入目标",
    }, ...prev]);
    setRecognitionStage("recognizing");
    const imageUrl = URL.createObjectURL(file);

    try {
      const { result, source: detectedSource, imported, importError } = await processCaptureFile(file);
      setRecognitionStage("extracting");
      const writeTargets = result.structured_artifact?.write_targets?.join("、") || result.recommended_destination || "待人工确认";
      if (imported.created > 0) {
        setIntakeItems((prev) => prev.map((item) => item.id === itemId ? {
          ...item,
          source: detectedSource,
          status: "待确认",
          summary: `已生成 ${imported.created} 条候选事实，确认后才会写入正式记录`,
        } : item));
        URL.revokeObjectURL(imageUrl);
        await fetchPendingFacts();
      } else {
        setDraftError(importError);
        setIntakeItems((prev) => prev.map((item) => item.id === itemId ? {
          ...item,
          source: detectedSource,
          status: "待确认",
          summary: result.parse_error || `识别为${result.source_type || detectedSource}，归档到：${writeTargets}`,
        } : item));
        setRecognitionResult({ itemId, fileName: file.name, imageUrl, source: detectedSource, result });
      }
      setRecognitionStage(null);
    } catch (err) {
      URL.revokeObjectURL(imageUrl);
      setIntakeItems((prev) => prev.map((e) => e.id === itemId ? {
        ...e,
        status: "待确认",
        summary: err instanceof Error ? err.message : "识别失败，请重试",
      } : e));
      setDraftError(err instanceof Error ? err.message : "识别失败，请重试");
      setRecognitionStage(null);
    }
  }, [fetchPendingFacts]);

  const handleFileChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    void registerFile(file);
  }, [registerFile]);

  const handlePaste = useCallback((event: React.ClipboardEvent<HTMLFormElement>) => {
    const imageItem = Array.from(event.clipboardData.items).find((item) => item.type.startsWith("image/"));
    const file = imageItem?.getAsFile();
    if (!file) return;
    void registerFile(new File([file], `粘贴截图-${Date.now()}.png`, { type: file.type }));
  }, [registerFile]);

  const handleDrop = useCallback((event: React.DragEvent<HTMLFormElement>) => {
    event.preventDefault();
    const file = Array.from(event.dataTransfer.files).find((item) => item.type.startsWith("image/"));
    if (!file) return;
    void registerFile(file);
  }, [registerFile]);

  const closeCamera = useCallback(() => {
    cameraStreamRef.current?.getTracks().forEach((track) => track.stop());
    cameraStreamRef.current = null;
    setIsCameraOpen(false);
  }, []);

  const openCamera = useCallback(async () => {
    setCameraError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError("当前浏览器不支持摄像头，可以改用上传或粘贴截图。");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      cameraStreamRef.current = stream;
      setIsCameraOpen(true);
      requestAnimationFrame(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          void videoRef.current.play();
        }
      });
    } catch {
      setCameraError("没有摄像头权限，可以用选择图片或粘贴截图。");
    }
  }, []);

  const takeCameraPhoto = useCallback(() => {
    const video = videoRef.current;
    if (!video || video.videoWidth === 0) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (blob) {
        void registerFile(new File([blob], `拍照-${Date.now()}.jpg`, { type: "image/jpeg" }));
        closeCamera();
      }
    }, "image/jpeg", 0.92);
  }, [closeCamera, registerFile]);

  const startVoiceRecording = useCallback(async () => {
    setVoiceMessage("");
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setVoiceMessage("当前浏览器不支持录音，请使用文字输入。");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioStreamRef.current = stream;
      audioChunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      audioRecorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };
      recorder.onstop = async () => {
        setIsRecording(false);
        stream.getTracks().forEach((track) => track.stop());
        audioStreamRef.current = null;
        const blob = new Blob(audioChunksRef.current, { type: recorder.mimeType || "audio/webm" });
        if (!blob.size) {
          setVoiceMessage("没有录到声音，请重试。");
          return;
        }
        setIsTranscribing(true);
        setVoiceMessage("正在转写，结果出来后请确认文字。");
        try {
          const result = await transcribeSpeech(blob);
          setInput(result.text);
          setVoiceMessage(`已转写 ${result.duration_seconds.toFixed(1)} 秒录音，请检查文字后发送。`);
        } catch (err) {
          setVoiceMessage(err instanceof Error ? err.message : "语音转写失败");
        } finally {
          setIsTranscribing(false);
        }
      };
      recorder.start();
      setIsRecording(true);
      setVoiceMessage("正在录音，再点一次麦克风结束。");
    } catch {
      setVoiceMessage("没有麦克风权限，请允许访问后重试。");
    }
  }, []);

  const stopVoiceRecording = useCallback(() => {
    const recorder = audioRecorderRef.current;
    if (recorder && recorder.state !== "inactive") recorder.stop();
  }, []);

  useEffect(() => () => {
    closeCamera();
    audioStreamRef.current?.getTracks().forEach((track) => track.stop());
  }, [closeCamera]);

  const handleSubmit = useCallback(async (event: React.FormEvent) => {
    event.preventDefault();
    const value = input.trim();
    if (!value) return;
    setDraftError(null);
    try {
      const processed = await processCaptureText(value);
      if (processed?.imported.created) {
        setIntakeItems((prev) => [{
          id: `text-${Date.now()}`,
          name: "文字经营信息",
          source: "经营文字",
          status: "待确认",
          summary: `已生成 ${processed.imported.created} 条候选事实`,
        }, ...prev]);
        setInput("");
        await fetchPendingFacts();
        return;
      }
      const review = buildTextNoteReview(value, processed?.draft);
      setRecognitionResult(review);
      setIntakeItems((prev) => [{
        id: review.itemId,
        name: review.fileName,
        source: review.source,
        status: "待确认",
        summary: "等待确认归档",
      }, ...prev]);
      setInput("");
    } catch (err) {
      setDraftError(err instanceof Error ? err.message : "文字识别失败，请重试");
    }
  }, [fetchPendingFacts, input]);

  const handleConfirmDocument = useCallback(async () => {
    if (!recognitionResult) return;
    setIsSavingDraft(true);
    setDraftError(null);
    try {
      const artifact = recognitionResult.result.structured_artifact;
      const recognizedDate = recognitionResult.result.fields.find((field) => field.key === "date")?.value;
      await confirmCaptureAudit({
        file_name: recognitionResult.fileName,
        image_url: recognitionResult.result.image_url,
        source_type: recognitionResult.result.source_type || recognitionResult.source,
        capture_kind: recognitionResult.result.capture_kind || "document",
        recognized_fields: recognitionResult.result.fields.map((field) => ({ key: field.key, value: field.value })),
        human_modified_fields: [],
        write_target: artifact?.write_targets?.join(" + ") || recognitionResult.result.recommended_destination || "资料箱",
        date: typeof recognizedDate === "string" ? recognizedDate : toDateInputValue(new Date()),
        structured_artifact: artifact,
      });
      setIntakeItems((current) => current.map((item) => item.id === recognitionResult.itemId ? {
        ...item,
        status: "已入库",
        summary: "已归档并保留原始凭证",
      } : item));
      closeRecognitionResult();
      await fetchPendingFacts();
    } catch (err) {
      setDraftError(err instanceof Error ? err.message : "资料归档失败");
    } finally {
      setIsSavingDraft(false);
    }
  }, [closeRecognitionResult, fetchPendingFacts, recognitionResult]);

  return (
    <>
      <ModulePage module={getModule("/capture")}>
        <section className="mb-4 rounded-2xl border border-octo-200 bg-gradient-to-br from-octo-50 to-amber-50/30 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-base font-bold text-stone-950">录入资料</p>
            </div>
          </div>

          <form
            onSubmit={handleSubmit}
            onPaste={handlePaste}
            onDrop={handleDrop}
            onDragOver={(event) => event.preventDefault()}
            className="mt-3 rounded-xl border border-stone-200 bg-white p-3"
          >
            <div className="flex flex-col gap-2 md:flex-row md:items-center">
              <div className="flex min-w-0 flex-1 items-center gap-2 rounded-lg bg-stone-50 px-3 py-2">
                <textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="今天发生了什么？发截图、拍库存、说一句话都可以…"
                  rows={1}
                  className="max-h-24 min-h-9 min-w-0 flex-1 resize-none bg-transparent text-sm leading-5 text-stone-900 outline-none placeholder:text-stone-400"
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      handleSubmit(event as unknown as React.FormEvent);
                    }
                  }}
                />
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="inline-flex items-center gap-1 rounded-full bg-stone-100 px-3 py-1.5 text-xs font-medium text-stone-600 hover:bg-octo-50 hover:text-octo-700"
                >
                  <Upload className="h-3.5 w-3.5" /> 上传
                </button>
                <button
                  type="button"
                  onClick={openCamera}
                  className="inline-flex items-center gap-1 rounded-full bg-stone-100 px-3 py-1.5 text-xs font-medium text-stone-600 hover:bg-octo-50 hover:text-octo-700"
                >
                  <Camera className="h-3.5 w-3.5" /> 拍照
                </button>
                <button
                  type="button"
                  onClick={isRecording ? stopVoiceRecording : startVoiceRecording}
                  className={`inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-medium ${
                    isRecording ? "bg-red-50 text-red-700" : "bg-stone-100 text-stone-600 hover:bg-octo-50 hover:text-octo-700"
                  }`}
                >
                  <Mic className={`h-3.5 w-3.5 ${isRecording ? "animate-pulse" : ""}`} />
                  {isRecording ? "结束" : "语音"}
                </button>
                <button
                  type="submit"
                  disabled={!input.trim() || isRecording}
                  className="inline-flex items-center gap-1 rounded-full bg-octo-500 px-4 py-1.5 text-xs font-semibold text-white hover:bg-octo-600 disabled:cursor-not-allowed disabled:bg-stone-200 disabled:text-stone-400"
                >
                  {isRecording ? <Loader2 className="h-3 w-3 animate-spin" /> : <Send className="h-3 w-3" />}
                  识别
                </button>
              </div>
            </div>
            {(voiceMessage || recognitionStage || isTranscribing) && (
              <p className="mt-2 px-1 text-[11px] text-stone-500">
                {isTranscribing ? "正在转写…" : recognitionStage === "recognizing" ? "正在识别…" : recognitionStage === "extracting" ? "正在整理…" : voiceMessage}
              </p>
            )}

            <div className="mt-3 flex flex-wrap gap-1.5">
              {QUICK_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => setInput(prompt)}
                  className="rounded-full border border-stone-200 bg-white px-2.5 py-1 text-[10px] text-stone-600 hover:border-octo-200 hover:bg-octo-50 hover:text-octo-700"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </form>

          <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
        </section>

        <AnimatePresence>
          {recognitionResult && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="mb-4"
            >
              <CaptureReviewCard
                review={recognitionResult}
                onClose={cancelRecognitionResult}
                onConfirm={() => void handleConfirmDocument()}
                isSaving={isSavingDraft}
                error={draftError}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {draftError && !recognitionResult && (
          <p className="mb-4 rounded-xl border border-red-100 bg-red-50 px-3 py-2 text-xs text-red-700">{draftError}</p>
        )}

        {intakeItems.length > 0 && (
          <section className="mb-4 rounded-2xl border border-stone-200 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-stone-950">录入进度</p>
              <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[10px] text-stone-500">
                {intakeItems.filter((i) => i.status === "已入库").length}/{intakeItems.length} 已入库
              </span>
            </div>
            <div className="mt-3 space-y-2">
              {intakeItems.map((item) => (
                <div key={item.id} className="flex items-center gap-2 rounded-lg bg-stone-50/50 px-3 py-2">
                  <span className={`flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-medium ${
                    item.status === "分析中" ? "bg-blue-100 text-blue-700" :
                    item.status === "待确认" ? "bg-amber-100 text-amber-700" :
                    "bg-green-100 text-green-700"
                  }`}>
                    {item.status === "分析中" ? <Loader2 className="h-3 w-3 animate-spin" /> :
                     item.status === "待确认" ? "?" : <Check className="h-3 w-3" />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-stone-900">{item.name}</p>
                    <p className="truncate text-[10px] text-stone-500">{item.summary}</p>
                  </div>
                  <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[10px] text-stone-500">{item.source}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="mb-4 rounded-2xl border border-amber-200 bg-amber-50/55 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-base font-bold text-stone-950">待确认事实</p>
              <p className="mt-1 text-xs leading-5 text-stone-600">
                逐条核对原图与识别结果，确认后写入对应的正式记录。
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void fetchPendingFacts()}
                className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-xs font-medium text-stone-600 ring-1 ring-amber-200"
              >
                <RefreshCw className="h-3.5 w-3.5" /> 刷新
              </button>
            </div>
          </div>
          {factMessage && (
            <p className="mt-3 rounded-xl bg-white/80 px-3 py-2 text-xs text-stone-700">{factMessage}</p>
          )}
        </section>

        <div className="grid gap-3">
          {pendingFacts.length === 0 ? (
            <div className="rounded-2xl border border-stone-100 bg-white/70 p-8 text-center">
              <Check className="mx-auto h-8 w-8 text-stone-300" />
              <p className="mt-3 text-sm text-stone-500">暂无待确认事实。新资料识别后会先出现在这里。</p>
            </div>
          ) : (
            pendingFacts.map((fact) => {
              const anomaly = getAnomalyLabel(fact);
              const imgUrl = factImageUrl(fact);
              const moreActions = getMoreActions(fact);
              const isSaving = factSavingId === fact.id;

              return (
                <motion.div
                  key={fact.id}
                  layout
                  className="overflow-hidden rounded-2xl border border-stone-100 bg-white shadow-sm"
                >
                  <div className="flex gap-3 p-3">
                    {imgUrl ? (
                      <button
                        onClick={() => setImagePreview(imgUrl)}
                        className="group relative h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-stone-100"
                      >
                        <Image src={imgUrl} alt="原图" width={160} height={160} unoptimized className="h-full w-full object-cover" />
                        <span className="absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition group-hover:bg-black/30 group-hover:opacity-100">
                          <Maximize2 className="h-4 w-4 text-white" />
                        </span>
                      </button>
                    ) : (
                      <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-xl bg-stone-50 text-stone-300">
                        <AlertTriangle className="h-5 w-5" />
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <p className="text-sm font-semibold text-stone-950">
                          {fact.title || fact.description || fact.fact_type}
                        </p>
                        <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[10px] font-medium text-stone-600">
                          ¥{fact.amount}
                        </span>
                        <span className="rounded-full bg-stone-50 px-2 py-0.5 text-[10px] text-stone-500">
                          {fact.date}
                        </span>
                      </div>
                      {anomaly && (
                        <p className="mt-1.5 inline-flex items-center gap-1 rounded-lg bg-amber-50 px-2 py-1 text-[11px] leading-4 text-amber-800">
                          <AlertTriangle className="h-3 w-3 shrink-0" />
                          {anomaly}
                        </p>
                      )}
                      {(fact.affects_accounts?.length || fact.affects_inventory_items?.length) && (
                        <p className="mt-1.5 text-[11px] leading-4 text-stone-500">
                          {fact.affects_accounts?.length ? `影响钱账：${fact.affects_accounts.join("、")}。` : ""}
                          {fact.affects_inventory_items?.length ? `影响库存：${fact.affects_inventory_items.join("、")}` : ""}
                        </p>
                      )}
                    </div>
                  </div>

                  <AnimatePresence>
                    {editingAmountId === fact.id && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden border-t border-stone-50"
                      >
                        <div className="flex items-center gap-2 px-3 py-2">
                          <label className="text-xs text-stone-500">金额</label>
                          <input
                            value={factAmountDrafts[fact.id] ?? String(fact.amount ?? 0)}
                            onChange={(e) => setFactAmountDrafts((prev) => ({ ...prev, [fact.id]: e.target.value }))}
                            className="flex-1 rounded-lg border border-stone-200 px-2 py-1.5 text-sm font-semibold text-stone-950 outline-none focus:border-amber-300"
                          />
                          <button
                            onClick={() => void handleSaveAmount(fact)}
                            disabled={isSaving}
                            className="rounded-full bg-stone-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
                          >
                            {isSaving ? <Loader2 className="h-3 w-3 animate-spin" /> : "保存"}
                          </button>
                          <button
                            onClick={() => { setEditingAmountId(null); setFactAmountDrafts((prev) => ({ ...prev, [fact.id]: String(fact.amount) })); }}
                            className="rounded-full px-2 py-1.5 text-xs text-stone-400"
                          >
                            取消
                          </button>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <div className="flex items-center gap-2 border-t border-stone-50 px-3 py-2.5">
                    <button
                      onClick={() => void handleFactAction(fact, "confirm")}
                      disabled={isSaving}
                      className="inline-flex items-center gap-1 rounded-full bg-stone-900 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                    >
                      {isSaving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                      确认写入
                    </button>
                    <button
                      onClick={() => setEditingAmountId(fact.id)}
                      className="rounded-full bg-stone-100 px-3 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-200"
                    >
                      修改金额
                    </button>
                    <button
                      onClick={() => void handleFactAction(fact, "reject")}
                      disabled={isSaving}
                      className="inline-flex items-center gap-1 rounded-full bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700 ring-1 ring-red-100 disabled:opacity-50"
                    >
                      <X className="h-3.5 w-3.5" />
                      驳回
                    </button>
                    <button
                      onClick={() => setChatFactId(fact.id)}
                      className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-800 ring-1 ring-amber-200"
                    >
                      <MessageSquare className="h-3.5 w-3.5" />
                      问这条
                    </button>
                    {moreActions.length > 0 && (
                      <button
                        onClick={() => toggleMore(fact.id)}
                        className="ml-auto inline-flex items-center gap-0.5 rounded-full px-2 py-1.5 text-xs text-stone-400 hover:bg-stone-50"
                      >
                        更多
                        <ChevronDown className={`h-3 w-3 transition-transform ${expandedMore.has(fact.id) ? "rotate-180" : ""}`} />
                      </button>
                    )}
                  </div>

                  <AnimatePresence>
                    {expandedMore.has(fact.id) && moreActions.length > 0 && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden border-t border-stone-50"
                      >
                        <div className="flex flex-wrap gap-2 px-3 py-2.5">
                          {moreActions.map(([action, label]) => (
                            <button
                              key={action}
                              onClick={() => void handleFactAction(fact, action)}
                              disabled={isSaving}
                              className="rounded-full bg-stone-50 px-3 py-1.5 text-xs font-medium text-stone-600 ring-1 ring-stone-100 hover:bg-stone-100 disabled:opacity-50"
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              );
            })
          )}
        </div>

        {imagePreview && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
            onClick={() => setImagePreview(null)}
          >
            <Image src={imagePreview} alt="原图" width={1600} height={1200} unoptimized className="max-h-[90vh] max-w-full rounded-lg object-contain" />
          </div>
        )}
      </ModulePage>

      <AnimatePresence>
        {chatFact && (
          <FactChatPanel
            fact={chatFact}
            onClose={() => setChatFactId(null)}
            onResolved={fetchPendingFacts}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {cameraError && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
            className="fixed bottom-5 left-1/2 z-60 -translate-x-1/2 rounded-full border border-red-200 bg-white px-4 py-2 text-sm text-red-700 shadow-xl"
          >
            {cameraError}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {isCameraOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-70 flex items-end justify-center bg-stone-900/60 px-4 pb-4 backdrop-blur-md md:items-center"
          >
            <motion.div
              initial={{ opacity: 0, y: 30, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 30, scale: 0.95 }}
              className="w-full max-w-lg rounded-2xl border border-stone-200 bg-white p-4 shadow-2xl"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-stone-900">拍照录入</p>
                <button onClick={closeCamera} className="rounded-full p-1.5 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700"><X className="h-4 w-4" /></button>
              </div>
              <video ref={videoRef} className="mt-3 aspect-video w-full rounded-xl bg-black object-cover" playsInline muted />
              <div className="mt-3 flex justify-end gap-2">
                <button onClick={closeCamera} className="rounded-xl border border-stone-300 px-3 py-2 text-xs text-stone-600 transition-colors hover:bg-stone-100">取消</button>
                <button onClick={takeCameraPhoto} className="rounded-xl bg-octo-500 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-octo-600">拍下并识别</button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
