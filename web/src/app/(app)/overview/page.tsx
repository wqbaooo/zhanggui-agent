"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  BookOpen,
  Boxes,
  Camera,
  Check,
  ChevronRight,
  CloudSun,
  FileText,
  Loader2,
  Maximize2,
  Mic,
  PackageCheck,
  RefreshCw,
  ReceiptText,
  ScanLine,
  Send,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Truck,
  Upload,
  Users,
  Wallet,
  X,
  type LucideIcon,
} from "lucide-react";
import { storeIdentity, type HealthTone } from "@/data/agent-store-os";
import {
  DEFAULT_PROJECT_ID,
  addOperation,
  getCaptureAuditLog,
  getConsumptionVariance,
  getForecast,
  getOperationSummary,
  getOperations,
  getStaff,
  getTodayInsight,
  getWeather,
  recognizeCapture,
  transcribeSpeech,
  type CaptureAuditLogItem,
  type ConsumptionVariance,
  type DailyOperationEntry,
  type ForecastItem,
  type OperationSummary,
  type RecognizeResponse,
  type WeatherResponse,
} from "@/lib/api";
import { useAIChat } from "@/lib/hooks/useAIChat";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { parseOperationDraft, toDateInputValue, type OperationDraft } from "@/lib/operationDraft";
import { calcBreakEvenAnalysis, type BreakEvenResult } from "@/domain/calculations";

type SourceType =
  | "客如云"
  | "美团"
  | "抖音"
  | "淘宝闪购"
  | "进货单"
  | "库存照片"
  | "SOP资料"
  | "水电费用"
  | "经营文字"
  | "未知资料";
type WorkStatus = "待确认" | "分析中" | "已入库";
type IntakeItem = { id: string; name: string; source: SourceType; status: WorkStatus; summary: string };

const WEATHER_LABELS: Record<string, string> = {
  sunny: "晴",
  cloudy: "多云",
  overcast: "阴",
  light_rain: "小雨",
  heavy_rain: "大雨",
  thunderstorm: "雷阵雨",
  snow: "雪",
  fog: "雾",
  unknown: "暂不可用",
};

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

export default function OverviewPage() {
  return (
    <Suspense fallback={<div className="min-h-[calc(100vh-56px)] bg-[#fbf7ef]" />}>
      <OverviewPageContent />
    </Suspense>
  );
}

function OverviewPageContent() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const audioRecorderRef = useRef<MediaRecorder | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const chatCardRef = useRef<HTMLDivElement>(null);
  const { messages, isStreaming, error: chatError, sendMessage } = useAIChat();

  const [input, setInput] = useState("");
  const [chatOpen, setChatOpen] = useState(searchParams.get("chat") === "open");
  const [intakeItems, setIntakeItems] = useState<IntakeItem[]>([]);
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceMessage, setVoiceMessage] = useState("");
  const [operationDraft, setOperationDraft] = useState<OperationDraft | null>(null);
  const [draftEntry, setDraftEntry] = useState<DailyOperationEntry | null>(null);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [draftSourceItemId, setDraftSourceItemId] = useState<string | null>(null);
  const [now, setNow] = useState(() => new Date());
  const [latestOperationDate, setLatestOperationDate] = useState<string | null>(null);
  const [recognitionStage, setRecognitionStage] = useState<string | null>(null);
  const [recognitionResult, setRecognitionResult] = useState<{
    itemId: string;
    fileName: string;
    imageUrl: string;
    source: SourceType;
    result: RecognizeResponse;
  } | null>(null);

  const [opsSummary, setOpsSummary] = useState<OperationSummary | null>(null);
  const [forecastUrgent, setForecastUrgent] = useState<ForecastItem[]>([]);
  const [staffCount, setStaffCount] = useState(0);
  const [dailyTrend, setDailyTrend] = useState<{ date: string; 营收: number }[]>([]);
  const [breakEvenData, setBreakEvenData] = useState<BreakEvenResult | null>(null);
  const [consumptionVariance, setConsumptionVariance] = useState<ConsumptionVariance | null>(null);
  const [weather, setWeather] = useState<WeatherResponse | null>(null);
  const [weatherFailed, setWeatherFailed] = useState(false);
  const [auditLogs, setAuditLogs] = useState<CaptureAuditLogItem[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [todayInsight, setTodayInsight] = useState<{ insight: string; health_status: "good" | "watch" | "risk"; key_concern: string | null } | null>(null);

  const confirmedCount = intakeItems.filter((item) => item.status === "已入库").length;
  const pendingCount = intakeItems.filter((item) => item.status === "待确认" || item.status === "分析中").length;

  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
  const todayLabel = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(now);
  const hasTodayOperation = latestOperationDate === today;
  const hasData = Boolean(opsSummary && opsSummary.entry_count > 0);

  const fetchLiveData = useCallback(async () => {
    setLoadError(null);
    try {
      const [ops, fRes, staffRes, opsList, auditRes, insightRes] = await Promise.all([
        getOperationSummary(DEFAULT_PROJECT_ID, 7),
        getForecast(DEFAULT_PROJECT_ID),
        getStaff(DEFAULT_PROJECT_ID),
        getOperations(DEFAULT_PROJECT_ID, 7),
        getCaptureAuditLog(DEFAULT_PROJECT_ID, 8),
        getTodayInsight(DEFAULT_PROJECT_ID).catch(() => null),
      ]);
      setOpsSummary(ops);
      setForecastUrgent(fRes.forecast.filter((f) => f.action === "urgent" || f.action === "recommend").slice(0, 3));
      setStaffCount(staffRes.staff.filter((s) => s.status === "在岗").length);
      setDailyTrend(opsList.entries.slice(-7).map((e) => ({ date: e.date.slice(5), 营收: e.revenue })));
      setLatestOperationDate(opsList.entries.at(-1)?.date ?? null);
      setBreakEvenData(ops.profit_ready ? calcBreakEvenAnalysis(opsList.entries, ops.entry_count) : null);
      setAuditLogs(auditRes.logs || []);
      if (insightRes) setTodayInsight(insightRes);

      // 拉取库存消耗差异（按已有台账日期范围）
      if (opsList.entries.length > 0) {
        const sorted = [...opsList.entries].sort((a, b) => a.date.localeCompare(b.date));
        try {
          const v = await getConsumptionVariance(DEFAULT_PROJECT_ID, sorted[0].date, sorted[sorted.length - 1].date);
          setConsumptionVariance(v);
        } catch {
          setConsumptionVariance(null);
        }
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "数据加载失败，请检查后端服务");
    }

    try {
      const w = await getWeather();
      setWeather(w);
      setWeatherFailed(false);
    } catch {
      setWeather(null);
      setWeatherFailed(true);
    }
  }, []);

  useEffect(() => { fetchLiveData(); }, [fetchLiveData]);

  useEffect(() => {
    const interval = setInterval(fetchLiveData, 60000);
    return () => clearInterval(interval);
  }, [fetchLiveData]);

  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 60000);
    return () => clearInterval(interval);
  }, []);

  const classifyFile = useCallback((name: string): SourceType => {
    const lower = name.toLowerCase();
    if (/客如云|keruyun|kyy/.test(name)) return "客如云";
    if (/美团|meituan|mt/.test(lower)) return "美团";
    if (/抖音|douyin|核销/.test(lower)) return "抖音";
    if (/淘宝闪购|taobao|闪购/.test(name) || /tbflash|taobao_flash|flash/.test(lower)) return "淘宝闪购";
    if (/进货|采购|供应|货单/.test(name)) return "进货单";
    if (/库存|冰柜|货架|剩余/.test(name)) return "库存照片";
    if (/sop|总部|标准|卫生|培训/.test(lower)) return "SOP资料";
    if (/水电|电费|水费|费用/.test(name)) return "水电费用";
    return "未知资料";
  }, []);

  const buildEmptyOperation = useCallback((): DailyOperationEntry => ({
    date: toDateInputValue(new Date()),
    revenue: 0,
    orders: 0,
    dine_in_revenue: 0,
    dine_in_orders: 0,
    delivery_revenue: 0,
    delivery_orders: 0,
    food_cost: 0,
    packaging_cost: 0,
    labor: 0,
    rent_allocated: 0,
    utility: 0,
    other_cost: 0,
    takeout_orders: 0,
    platform_fee: 0,
    marketing_cost: 0,
    inventory_loss: 0,
    bad_reviews: 0,
    repeat_orders: 0,
    new_members: 0,
    notes: "",
  }), []);

  const registerFile = useCallback(async (file: File, sourceLabel: string) => {
    const source = classifyFile(file.name);
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
      const result = await recognizeCapture(file);
      setRecognitionStage("extracting");
      const detectedSource = classifyFile(result.source_type || file.name);
      const writeTargets = result.structured_artifact?.write_targets?.join("、") || result.recommended_destination || "待人工确认";

      setRecognitionResult({ itemId, fileName: file.name, imageUrl, source: detectedSource, result });

      if (result.parse_error || result.capture_kind !== "operation" || !result.can_write_operation || result.fields.length === 0) {
        const summary = result.parse_error || `识别为${result.source_type || "未知资料"}，建议写入：${writeTargets}`;
        setIntakeItems((prev) => prev.map((e) => e.id === itemId ? { ...e, source: detectedSource, status: "待确认", summary } : e));
        setRecognitionStage(null);
        return;
      }

      const entry = buildEmptyOperation();
      for (const field of result.fields) {
        const key = field.key as keyof DailyOperationEntry;
        if (key in entry) (entry as unknown as Record<string, unknown>)[key] = field.value;
      }
      setIntakeItems((prev) => prev.map((e) => e.id === itemId ? {
        ...e,
        source: detectedSource,
        status: "待确认",
        summary: `识别到 ${result.fields.length} 个经营字段，可确认写入经营台账`,
      } : e));
      setDraftSourceItemId(itemId);
      setOperationDraft({
        source: `${sourceLabel}: ${file.name}`,
        entry,
        fields: result.fields.map((f) => ({
          key: f.key as keyof DailyOperationEntry,
          label: f.label,
          value: f.value,
          confidence: f.confidence === "low" ? "medium" : f.confidence,
        })),
        missing: [],
        confidence: result.fields.length >= 3 ? "high" : "medium",
      });
      setDraftEntry(entry);
      setDraftError(null);
      setRecognitionStage(null);
    } catch (err) {
      setIntakeItems((prev) => prev.map((e) => e.id === itemId ? {
        ...e,
        status: "待确认",
        summary: err instanceof Error ? err.message : "识别请求失败",
      } : e));
      setRecognitionStage(null);
    }
  }, [buildEmptyOperation, classifyFile]);

  const handleSubmit = useCallback((event: React.FormEvent) => {
    event.preventDefault();
    const value = input.trim();
    if (!value) return;

    const draft = parseOperationDraft(value);
    if (draft) {
      const itemId = `text-${Date.now()}`;
      setIntakeItems((prev) => [{
        id: itemId,
        name: "文字经营信息",
        source: "经营文字",
        status: "待确认",
        summary: "从文字中识别到经营日报字段，可确认写入",
      }, ...prev]);
      setDraftSourceItemId(itemId);
      setOperationDraft(draft);
      setDraftEntry(draft.entry);
      setDraftError(null);
      return;
    }

    setIntakeItems((prev) => [{
      id: `chat-${Date.now()}`,
      name: value.slice(0, 28) || "文字经营信息",
      source: "经营文字",
      status: "分析中",
      summary: "已交给掌柜对话分析；后续会接入统一文本归类写入",
    }, ...prev]);
    sendMessage(value);
    setInput("");
  }, [input, sendMessage]);

  const openChat = useCallback(() => {
    setChatOpen(true);
    const params = new URLSearchParams(searchParams.toString());
    params.set("chat", "open");
    router.push(`?${params.toString()}`, { scroll: false });
  }, [router, searchParams]);

  const closeChat = useCallback(() => {
    setChatOpen(false);
    const params = new URLSearchParams(searchParams.toString());
    params.delete("chat");
    const queryStr = params.toString();
    router.push(queryStr ? `?${queryStr}` : window.location.pathname, { scroll: false });
  }, [router, searchParams]);

  useEffect(() => {
    const isChatOpen = searchParams.get("chat") === "open";
    setChatOpen(isChatOpen);
  }, [searchParams]);

  const handleFileChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    registerFile(file, "电脑上传");
  }, [registerFile]);

  const handlePaste = useCallback((event: React.ClipboardEvent<HTMLFormElement>) => {
    const imageItem = Array.from(event.clipboardData.items).find((item) => item.type.startsWith("image/"));
    const file = imageItem?.getAsFile();
    if (!file) return;
    registerFile(new File([file], `粘贴截图-${Date.now()}.png`, { type: file.type }), "粘贴截图");
  }, [registerFile]);

  const handleDrop = useCallback((event: React.DragEvent<HTMLFormElement>) => {
    event.preventDefault();
    const file = Array.from(event.dataTransfer.files).find((item) => item.type.startsWith("image/"));
    if (!file) return;
    registerFile(file, "拖拽图片");
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
        registerFile(new File([blob], `电脑拍照-${Date.now()}.jpg`, { type: "image/jpeg" }), "Mac 摄像头拍照");
        closeCamera();
      }
    }, "image/jpeg", 0.92);
  }, [closeCamera, registerFile]);

  const stopVoiceRecording = useCallback(() => {
    const recorder = audioRecorderRef.current;
    if (recorder && recorder.state !== "inactive") recorder.stop();
  }, []);

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

  useEffect(() => () => {
    closeCamera();
    audioStreamRef.current?.getTracks().forEach((track) => track.stop());
  }, [closeCamera]);

  useEffect(() => {
    const handleGlobalPaste = (event: ClipboardEvent) => {
      const imageItem = Array.from(event.clipboardData?.items || []).find((item) => item.type.startsWith("image/"));
      const file = imageItem?.getAsFile();
      if (!file) return;
      event.preventDefault();
      registerFile(new File([file], `粘贴截图-${Date.now()}.png`, { type: file.type }), "Ctrl+V 粘贴");
    };
    window.addEventListener("paste", handleGlobalPaste);
    return () => window.removeEventListener("paste", handleGlobalPaste);
  }, [registerFile]);

  const handleConfirmDraft = useCallback(async () => {
    if (!draftEntry) return;
    setIsSavingDraft(true);
    setDraftError(null);
    try {
      await addOperation(draftEntry, DEFAULT_PROJECT_ID);
      await queryClient.invalidateQueries({ queryKey: ["project", DEFAULT_PROJECT_ID] });
      await queryClient.invalidateQueries({ queryKey: ["operations", DEFAULT_PROJECT_ID] });
      if (draftSourceItemId) {
        setIntakeItems((prev) => prev.map((e) => e.id === draftSourceItemId ? { ...e, status: "已入库" } : e));
        setDraftSourceItemId(null);
      }
      setOperationDraft(null);
      setDraftEntry(null);
      setInput("");
      setRecognitionResult(null);
      await fetchLiveData();
    } catch (err) {
      setDraftError(err instanceof Error ? err.message : "写入失败");
    } finally {
      setIsSavingDraft(false);
    }
  }, [draftEntry, queryClient, draftSourceItemId, fetchLiveData]);

  const weatherText = weather
    ? weather.current.weather === "unknown"
      ? "天气暂不可用"
      : weather.current.weather === "light_rain" || weather.current.weather === "heavy_rain"
        ? `${weather.forecast[1]?.weekday || "明日"}有雨`
        : weather.current.temperature > 35
          ? `${weather.current.temperature}° 高温`
          : `${WEATHER_LABELS[weather.current.weather] || "天气"} ${weather.current.temperature}°`
    : weatherFailed ? "天气源异常" : "天气加载中";

  const todayActions = useMemo(() => {
    const actions: { icon: LucideIcon; text: string; tone: HealthTone; href?: string; evidence: string }[] = [];
    if (forecastUrgent.length > 0) {
      const f = forecastUrgent[0];
      const daysText = f.days_remaining != null ? `剩${f.days_remaining}天` : "需补货";
      actions.push({
        icon: f.risk_level === "high" ? AlertTriangle : PackageCheck,
        text: `${f.name}：${daysText}，建议补${f.recommend_qty ?? "?"}${f.unit}`,
        tone: f.risk_level === "high" ? "risk" : "watch",
        href: "/inventory",
        evidence: "来自 SKU 断货预测",
      });
    }
    if (hasData && opsSummary) {
      if (opsSummary.profit_ready) {
        actions.push({
          icon: opsSummary.net_profit < 0 ? TrendingDown : TrendingUp,
          text: opsSummary.net_profit < 0
            ? `近 7 天亏损 ¥${Math.abs(opsSummary.net_profit).toFixed(0)}，先查成本`
            : `近 7 天净利 ¥${(opsSummary.net_profit / 1000).toFixed(1)}k，复盘可复制动作`,
          tone: opsSummary.net_profit < 0 ? "risk" : "good",
          href: "/profit",
          evidence: "来自完整经营台账",
        });
      } else {
        actions.push({
          icon: ReceiptText,
          text: `三天实收 ¥${opsSummary.total_revenue.toFixed(0)} 已确认，补齐成本后计算利润`,
          tone: "watch",
          href: "/profit",
          evidence: "来自客如云日结与成本完整度检查",
        });
      }
      if (breakEvenData && !breakEvenData.is_profitable && breakEvenData.daily_breakeven_revenue) {
        const gap = breakEvenData.gap_to_breakeven ?? 0;
        actions.push({
          icon: AlertTriangle,
          text: `日均低于保本线 ¥${Math.abs(gap).toFixed(0)}，保本需 ¥${breakEvenData.daily_breakeven_revenue.toFixed(0)}/天，先保堂食单量`,
          tone: "risk",
          href: "/profit",
          evidence: "来自保本点分析",
        });
      }
      if (opsSummary.food_cost_rate > 0.35) {
        actions.push({
          icon: AlertTriangle,
          text: `食材率 ${(opsSummary.food_cost_rate * 100).toFixed(0)}% 超标（红线 35%），检查损耗和采购价`,
          tone: "risk",
          href: "/profit",
          evidence: "来自成本结构",
        });
      }
      if (opsSummary.labor_cost_rate > 0.25) {
        actions.push({
          icon: Users,
          text: `人工率 ${(opsSummary.labor_cost_rate * 100).toFixed(0)}% 超标（红线 25%），按时段重排班`,
          tone: "risk",
          href: "/training",
          evidence: "来自成本结构",
        });
      }
      if (opsSummary.takeout_ratio > 0.45) {
        actions.push({
          icon: Truck,
          text: `外卖占比 ${(opsSummary.takeout_ratio * 100).toFixed(0)}%，核对平台费和到手利润`,
          tone: "watch",
          href: "/channels",
          evidence: "来自渠道拆分",
        });
      }
    }
    if (weather && (weather.current.weather === "light_rain" || weather.current.weather === "heavy_rain" || weather.current.temperature > 35)) {
      actions.push({
        icon: CloudSun,
        text: weather.current.tips?.[0] || "结合天气调整备料和排班",
        tone: "watch",
        href: "/calendar",
        evidence: weather.source === "open-meteo" ? "Open-Meteo 天气源" : "天气兜底估算",
      });
    }
    if (pendingCount > 0) {
      actions.push({
        icon: ScanLine,
        text: `${pendingCount} 条资料待确认，确认后才能写入经营档案`,
        tone: "watch",
        href: "/capture",
        evidence: "来自本页识别队列",
      });
    }
    if (actions.length === 0) {
      actions.push({
        icon: Sparkles,
        text: "把今天和店有关的任何信息交给掌柜，AI 会先分类再写入",
        tone: "info",
        evidence: "等待新的经营输入",
      });
    }
    return actions.slice(0, 4);
  }, [forecastUrgent, hasData, opsSummary, pendingCount, weather, breakEvenData]);

  const modules = useMemo(() => [
    {
      href: "/capture",
      icon: ScanLine,
      title: "万能录入",
      value: pendingCount > 0 ? `${pendingCount} 待确认` : "可接收",
      detail: pendingCount > 0 ? "待确认的资料需确认后才会入档" : "上传截图或输入经营信息",
      tone: pendingCount > 0 ? "watch" as HealthTone : "good" as HealthTone,
    },
    {
      href: "/calendar",
      icon: CloudSun,
      title: "天气客流",
      value: weather ? weatherText : (weatherFailed ? "源异常" : "加载中"),
      detail: weather ? weather.current.tips?.[0] || "正常备货" : "等待天气数据",
      tone: weatherFailed ? "risk" as HealthTone : weather?.source === "fallback" ? "watch" as HealthTone : "info" as HealthTone,
    },
    {
      href: "/inventory",
      icon: Boxes,
      title: "库存采购",
      value: forecastUrgent.length > 0 ? `${forecastUrgent.length} 风险` : "稳定",
      detail: forecastUrgent[0] ? `${forecastUrgent[0].name} · 剩${forecastUrgent[0].days_remaining ?? "?"}天` : "暂无紧急补货需求",
      tone: forecastUrgent.length > 0 ? "risk" as HealthTone : "good" as HealthTone,
    },
    {
      href: "/channels",
      icon: Truck,
      title: "外卖渠道",
      value: hasData && opsSummary ? `${(opsSummary.takeout_ratio * 100).toFixed(0)}%` : "待录入",
      detail: hasData && opsSummary && opsSummary.takeout_ratio > 0.45 ? "外卖占比偏高，需核对平台费" : "录入外卖数据后分析渠道利润",
      tone: hasData && opsSummary && opsSummary.takeout_ratio > 0.45 ? "watch" as HealthTone : "info" as HealthTone,
    },
    {
      href: "/training",
      icon: Users,
      title: "人工工资",
      value: `${staffCount} 人在岗`,
      detail: staffCount > 0 ? `${staffCount}人在岗，影响日均人工摊销` : "录入员工信息后自动核算",
      tone: "info" as HealthTone,
    },
    {
      href: "/sop",
      icon: BookOpen,
      title: "SOP 作业",
      value: "资料可入库",
      detail: "总部资料入库后自动生成作业清单",
      tone: "info" as HealthTone,
    },
    {
      href: "/reports",
      icon: FileText,
      title: "周报月报",
      value: auditLogs.length > 0 ? "有证据" : "待生成",
      detail: auditLogs.length > 0 ? "已写入记录可生成复盘报告" : "确认写入后自动生成周报",
      tone: auditLogs.length > 0 ? "good" as HealthTone : "watch" as HealthTone,
    },
    {
      href: "/risks",
      icon: AlertTriangle,
      title: "风险预警",
      value: loadError ? "需检查" : "监控中",
      detail: loadError || "库存、成本、合规风险实时监控",
      tone: loadError ? "risk" as HealthTone : "info" as HealthTone,
    },
  ], [auditLogs.length, forecastUrgent, hasData, loadError, opsSummary, pendingCount, staffCount, weather, weatherFailed, weatherText]);

  const settlement = opsSummary?.settlement_summary;
  const currentOwnerAmount = settlement ? settlement.current_owner + settlement.cash_on_hand : 0;
  const formerOwnerAmount = settlement?.former_owner ?? 0;
  const platformPendingAmount = settlement?.by_status?.expected_settled_unconfirmed ?? 0;
  const latestEntry = opsSummary?.latest_entry;

  const dailyFactRows = useMemo(() => [
    {
      label: "今日销售额",
      value: latestEntry ? formatCurrency(latestEntry.revenue) : "待录入",
      sub: hasTodayOperation ? "来自今日已确认台账" : "缺今日销售截图或文字日报",
      tone: latestEntry ? "good" as HealthTone : "watch" as HealthTone,
    },
    {
      label: "已到我账户",
      value: hasData ? formatCurrency(currentOwnerAmount) : "待核对",
      sub: settlement ? "含当前老板名下收款和现金" : "上传到账截图后核对",
      tone: currentOwnerAmount > 0 ? "good" as HealthTone : "watch" as HealthTone,
    },
    {
      label: "前老板代收",
      value: hasData ? formatCurrency(formerOwnerAmount) : "待核对",
      sub: formerOwnerAmount > 0 ? "需要确认是否已转给你" : "暂未发现待核对代收",
      tone: formerOwnerAmount > 0 ? "watch" as HealthTone : "info" as HealthTone,
    },
    {
      label: "平台未结算",
      value: hasData ? formatCurrency(platformPendingAmount) : "待核对",
      sub: platformPendingAmount > 0 ? "影响钱在哪里，不影响销售归属" : "等待平台账单或结算截图",
      tone: platformPendingAmount > 0 ? "watch" as HealthTone : "info" as HealthTone,
    },
    {
      label: "今日采购支出",
      value: latestEntry && latestEntry.food_cost > 0 ? formatCurrency(latestEntry.food_cost) : "待确认",
      sub: latestEntry && latestEntry.food_cost > 0 ? "已作为食材成本记录" : "上传进货单或付款截图",
      tone: latestEntry && latestEntry.food_cost > 0 ? "good" as HealthTone : "watch" as HealthTone,
    },
    {
      label: "库存消耗",
      value: consumptionVariance ? `${Math.round(consumptionVariance.verification_coverage * 100)}% 可核验` : "待盘点",
      sub: consumptionVariance ? `差异金额 ${formatCurrency(consumptionVariance.total_variance_value)}` : "缺开店/打烊库存照片或 BOM",
      tone: consumptionVariance && consumptionVariance.verification_coverage >= 0.3 ? "info" as HealthTone : "watch" as HealthTone,
    },
    {
      label: "预估利润",
      value: hasData && opsSummary?.profit_ready ? formatCurrency(opsSummary.net_profit) : "不能确认",
      sub: opsSummary?.profit_ready ? `基于 ${opsSummary.entry_count} 条完整台账` : "成本、库存或平台费未补齐",
      tone: opsSummary?.profit_ready ? (opsSummary.net_profit >= 0 ? "good" as HealthTone : "risk" as HealthTone) : "watch" as HealthTone,
    },
    {
      label: "明日断货",
      value: forecastUrgent.length > 0 ? `${forecastUrgent.length} 项` : "暂无紧急",
      sub: forecastUrgent[0] ? `${forecastUrgent[0].name} 剩${forecastUrgent[0].days_remaining ?? "?"}天` : "继续保持每日盘点",
      tone: forecastUrgent.length > 0 ? "risk" as HealthTone : "good" as HealthTone,
    },
  ], [consumptionVariance, currentOwnerAmount, forecastUrgent, formerOwnerAmount, hasData, hasTodayOperation, latestEntry, opsSummary, platformPendingAmount, settlement]);

  const gapQuestions = useMemo(() => {
    const gaps: { title: string; body: string; action: string; tone: HealthTone; href: string }[] = [];
    if (pendingCount > 0) {
      gaps.push({
        title: `${pendingCount} 条资料还没确认`,
        body: "不确认就不能正式写入钱账或库存账，避免把截图金额当成真实账。",
        action: "去确认",
        tone: "watch",
        href: "/capture",
      });
    }
    if (!hasTodayOperation) {
      gaps.push({
        title: "缺今日销售事实",
        body: "会影响今日销售额、利润估算和明天备货判断。上传客如云日报或直接输入今日销售。",
        action: "补销售",
        tone: "risk",
        href: "/capture",
      });
    }
    if (formerOwnerAmount > 0) {
      gaps.push({
        title: "前老板代收款未核销",
        body: "会影响钱在哪里，但不影响这笔收入是否属于本店经营。确认已转、未转或部分转。",
        action: "核对钱账",
        tone: "watch",
        href: "/profit",
      });
    }
    if (!opsSummary?.profit_ready) {
      gaps.push({
        title: "利润不能正式确认",
        body: "缺少食材、包装、平台费、人工或库存消耗时，只能暂估，不能当成真实净利。",
        action: "补成本",
        tone: "watch",
        href: "/profit",
      });
    }
    if (!consumptionVariance || consumptionVariance.verification_coverage < 0.3) {
      gaps.push({
        title: "库存消耗缺证据",
        body: "会影响食材成本和断货预测。最省事的补法是拍冰柜、章鱼粒、粉、酱料和盒子。",
        action: "补库存",
        tone: "watch",
        href: "/inventory",
      });
    }
    return gaps.slice(0, 4);
  }, [consumptionVariance, formerOwnerAmount, hasTodayOperation, opsSummary?.profit_ready, pendingCount]);

  return (
    <div className="min-h-[calc(100vh-56px)] bg-[#fbf7ef]">
      <main className="mx-auto w-full max-w-7xl space-y-4 px-4 py-4">
        {loadError && (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {loadError}
          </div>
        )}

        <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileChange} className="hidden" />

        <section className="relative overflow-hidden rounded-[2rem] border border-stone-200 bg-[linear-gradient(135deg,#fffdf8_0%,#fff7ed_48%,#fef2e7_100%)] p-4 text-stone-950 shadow-[0_22px_70px_rgba(120,88,55,0.16)] md:min-h-[650px] md:p-5">
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute -left-24 bottom-0 h-72 w-72 rounded-full bg-octo-200/50 blur-3xl" />
            <div className="absolute left-[18%] top-12 h-72 w-[38rem] -rotate-12 rounded-full bg-sauce-100/80 blur-3xl" />
            <div className="absolute right-12 top-8 h-80 w-80 rounded-full bg-nori-100/45 blur-3xl" />
            <div className="absolute inset-0 bg-[linear-gradient(115deg,rgba(255,255,255,0.92),transparent_38%,rgba(249,115,22,0.10)_72%,transparent)]" />
            <div className="absolute inset-0 opacity-[0.32] [background-image:linear-gradient(rgba(120,88,55,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(120,88,55,0.08)_1px,transparent_1px)] [background-size:28px_28px]" />
          </div>

          <div className="relative z-10 flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/70 bg-white/70 px-3 py-2 shadow-sm backdrop-blur-xl">
              <div className="flex items-center gap-2">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-octo-500 text-white shadow-sm shadow-octo-200/70">
                  <Sparkles className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-sm font-semibold text-stone-950">{storeIdentity.name}</p>
                  <p className="text-[11px] text-stone-500">{storeIdentity.location}</p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <StagePill label="天气" value={weatherText} tone={weatherFailed ? "risk" : weather?.source === "fallback" ? "watch" : "info"} />
              </div>
            </div>

            <div className="grid w-full min-w-0 flex-1 grid-cols-1 gap-5 xl:grid-cols-[200px_minmax(0,1fr)]">
              <aside className="hidden flex-col gap-3 xl:flex">
                <div className="rounded-2xl border border-white/70 bg-white/65 p-3 shadow-sm backdrop-blur-xl">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-stone-400">今天</p>
                  <p className="mt-1 text-sm font-semibold text-stone-800">{todayLabel}</p>
                </div>
                <div className="rounded-2xl border border-white/70 bg-white/65 p-3 shadow-sm backdrop-blur-xl">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-stone-400">最近入档</p>
                  <div className="mt-2 space-y-2">
                    {(auditLogs.length ? auditLogs.slice(0, 3) : [
                      { id: "empty-1", write_target: "等待第一条资料", source_type: "掌柜台", file_name: "今天还没有新写入", review_status: "" },
                    ] as CaptureAuditLogItem[]).map((log, i) => (
                      <motion.div
                        key={log.id}
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.3, delay: 0.15 + i * 0.08 }}
                        className="flex items-center gap-2"
                      >
                        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-octo-50 text-octo-600 ring-1 ring-octo-100">
                          <FileText className="h-3.5 w-3.5" />
                        </span>
                        <div className="min-w-0">
                          <p className="truncate text-[11px] font-medium text-stone-800">{log.write_target || log.capture_kind}</p>
                          <p className="truncate text-[9px] text-stone-400">{log.file_name || log.source_type}</p>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </div>
              </aside>

              <div className="flex min-h-[420px] min-w-0 flex-col gap-5 md:min-h-[500px]">
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4 }}
                  className="w-full min-w-0"
                >
                  <div className="flex items-center gap-3">
                    <h1 className="text-[1.75rem] font-semibold leading-[1.1] tracking-tight text-stone-950 md:text-[2.25rem]">
                      掌柜台 · 今日经营卡
                    </h1>
                  </div>
                  {todayInsight?.insight && (
                    <div className={`mt-3 rounded-2xl border p-3 ${
                      todayInsight.health_status === "good"
                        ? "border-nori-200 bg-nori-50/50"
                        : todayInsight.health_status === "risk"
                          ? "border-red-200 bg-red-50/50"
                          : "border-stone-200 bg-stone-50/50"
                    }`}>
                      <p className={`text-sm leading-6 ${
                        todayInsight.health_status === "good"
                          ? "text-nori-800"
                          : todayInsight.health_status === "risk"
                            ? "text-red-800"
                            : "text-stone-700"
                      }`}>
                        {todayInsight.insight}
                      </p>
                    </div>
                  )}
                  <p className="mt-2 text-sm text-stone-500">
                    {hasData && opsSummary
                      ? opsSummary.profit_ready
                        ? `钱账、成本和库存证据已覆盖 ${opsSummary.entry_count} 条台账，今天先看钱在哪里`
                        : `已有销售记录，但利润还缺成本、平台费或库存证据`
                      : "把销售、到账、进货、库存照片直接丢给掌柜，先生成待确认事实"}
                  </p>
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, y: 14 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: 0.08 }}
                  className="grid gap-3 sm:grid-cols-3"
                >
                  <HeroMetricCard
                    icon={TrendingUp}
                    label="销售事实"
                    value={latestEntry ? formatCurrency(latestEntry.revenue) : "待录入"}
                    sub={hasData && opsSummary
                      ? hasTodayOperation ? "今日销售已入账" : "最近一条销售记录不是今天"
                      : "上传客如云或平台销售截图"}
                    tone={hasTodayOperation ? "good" : "watch"}
                    delay={0.1}
                  />
                  <HeroMetricCard
                    icon={Wallet}
                    label="钱在哪里"
                    value={hasData ? formatCurrency(currentOwnerAmount + formerOwnerAmount + platformPendingAmount) : "待核对"}
                    sub={formerOwnerAmount > 0
                      ? `前老板代收 ${formatCurrency(formerOwnerAmount)} 待核销`
                      : hasData ? `已到我账户 ${formatCurrency(currentOwnerAmount)}` : "上传到账或转账截图"}
                    tone={formerOwnerAmount > 0 || platformPendingAmount > 0 ? "watch" : hasData ? "good" : "info"}
                    delay={0.18}
                  />
                  <HeroMetricCard
                    icon={PackageCheck}
                    label="货能不能卖"
                    value={forecastUrgent.length > 0 ? `${forecastUrgent.length} 项风险` : "暂无紧急"}
                    sub={forecastUrgent[0]
                      ? `${forecastUrgent[0].name} 建议补 ${forecastUrgent[0].recommend_qty ?? "?"}${forecastUrgent[0].unit}`
                      : "库存预测暂未发现紧急断货"}
                    tone={forecastUrgent.length > 0 ? "risk" : "good"}
                    delay={0.26}
                  />
                </motion.div>

                <StageInputDock
                  input={input}
                  setInput={setInput}
                  isStreaming={isStreaming}
                  isRecording={isRecording}
                  isTranscribing={isTranscribing}
                  voiceMessage={voiceMessage}
                  onSubmit={handleSubmit}
                  onPaste={handlePaste}
                  onDrop={handleDrop}
                  onUpload={() => fileInputRef.current?.click()}
                  onCamera={openCamera}
                  onVoice={isRecording ? stopVoiceRecording : startVoiceRecording}
                />

                <AnimatePresence>
                  {breakEvenData && !breakEvenData.is_profitable && breakEvenData.daily_breakeven_revenue && (
                    <motion.div
                      initial={{ opacity: 0, height: 0, y: -8 }}
                      animate={{ opacity: 1, height: "auto", y: 0 }}
                      exit={{ opacity: 0, height: 0, y: -8 }}
                      transition={{ duration: 0.3 }}
                      className="overflow-hidden"
                    >
                      <div className="rounded-2xl border border-red-200 bg-red-50/80 p-3 backdrop-blur-sm">
                        <div className="flex items-center gap-2">
                          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-red-100 text-red-600">
                            <AlertTriangle className="h-4 w-4" />
                          </span>
                          <p className="text-sm font-semibold text-red-900">保本诊断</p>
                          <span className="ml-auto text-xs font-medium text-red-700">
                            日均差 ¥{Math.abs(breakEvenData.gap_to_breakeven ?? 0).toFixed(0)}
                          </span>
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-red-800">
                          <span>实际日均 <b className="tabular-nums">¥{breakEvenData.daily_revenue.toLocaleString()}</b></span>
                          <span>保本日均 <b className="tabular-nums">¥{breakEvenData.daily_breakeven_revenue.toLocaleString()}</b></span>
                          <span>月固定 <b className="tabular-nums">¥{breakEvenData.monthly_fixed_cost.toLocaleString()}</b></span>
                          <span>边际贡献率 <b className="tabular-nums">{(breakEvenData.contribution_margin_rate * 100).toFixed(0)}%</b></span>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-medium text-red-700">先保堂食单量</span>
                          <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-medium text-red-700">核查食材损耗</span>
                          <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-medium text-red-700">低峰减人</span>
                          <Link href="/profit" className="rounded-full bg-red-600 px-2 py-0.5 text-[10px] font-semibold text-white">查看利润分析 →</Link>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                <motion.div
                  initial={{ opacity: 0, y: 14 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: 0.15 }}
                  className="grid gap-3 lg:grid-cols-[1.35fr_0.9fr]"
                >
                  <section className="rounded-3xl border border-stone-200 bg-white/82 p-4 shadow-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-stone-950">今日经营卡</p>
                        <p className="mt-1 text-xs leading-5 text-stone-500">销售、到账、代收、采购、库存和利润必须分开看。</p>
                      </div>
                      <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${hasTodayOperation ? "bg-nori-50 text-nori-700" : "bg-sauce-50 text-sauce-700"}`}>
                        {hasTodayOperation ? "今日已入账" : "今日待入账"}
                      </span>
                    </div>
                    <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                      {dailyFactRows.map((row) => (
                        <FactTile key={row.label} {...row} />
                      ))}
                    </div>
                  </section>

                  <section className="rounded-3xl border border-stone-200 bg-white/82 p-4 shadow-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-stone-950">Agent 追问</p>
                        <p className="mt-1 text-xs leading-5 text-stone-500">只问会影响入账、利润或库存判断的缺口。</p>
                      </div>
                      <span className="rounded-full bg-stone-100 px-2.5 py-1 text-[11px] font-medium text-stone-500">
                        {gapQuestions.length} 项
                      </span>
                    </div>
                    <div className="mt-4 space-y-2">
                      {gapQuestions.length > 0 ? gapQuestions.map((gap) => (
                        <Link key={gap.title} href={gap.href} className="group block rounded-2xl border border-stone-100 bg-stone-50/70 p-3 transition-colors hover:border-octo-200 hover:bg-octo-50/40">
                          <div className="flex items-start gap-2">
                            <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${dotToneClass(gap.tone)}`} />
                            <div className="min-w-0 flex-1">
                              <p className="text-sm font-semibold text-stone-900">{gap.title}</p>
                              <p className="mt-1 text-xs leading-5 text-stone-500">{gap.body}</p>
                            </div>
                            <span className="shrink-0 rounded-full bg-white px-2 py-1 text-[10px] font-medium text-stone-500 group-hover:text-octo-700">{gap.action}</span>
                          </div>
                        </Link>
                      )) : (
                        <div className="rounded-2xl border border-nori-100 bg-nori-50/50 p-3">
                          <p className="text-sm font-semibold text-nori-800">今天没有关键缺口</p>
                          <p className="mt-1 text-xs leading-5 text-nori-700">继续补充打烊库存照片和平台结算截图，明天的利润估算会更准。</p>
                        </div>
                      )}
                    </div>
                  </section>
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: 0.15 }}
                >
                  <button
                    onClick={openChat}
                    className="group flex items-center gap-3 rounded-2xl border border-stone-200 bg-white/82 px-4 py-3 shadow-sm transition-all hover:border-octo-200 hover:shadow-md"
                  >
                    <span className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-octo-500 to-octo-600 text-white shadow-sm shadow-octo-200/60">
                      <Sparkles className="h-5 w-5" />
                    </span>
                    <div className="flex-1 text-left">
                      <p className="text-sm font-semibold text-stone-900">掌柜对话</p>
                      <p className="text-[11px] text-stone-500">
                        {messages.length > 0 && !isStreaming
                          ? messages[messages.length - 1].content?.slice(0, 20) + "..."
                          : messages.length === 0 && !isStreaming
                            ? "点击进入对话，分析经营数据"
                            : "正在处理…"}
                      </p>
                    </div>
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-octo-50 text-octo-600 group-hover:bg-octo-100 transition-colors">
                      <ChevronRight className="h-4 w-4" />
                    </span>
                  </button>
                </motion.div>
              </div>
            </div>
          </div>
        </section>

        <AnimatePresence>
          {chatOpen && (
            <>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
                className="fixed inset-0 z-40 bg-stone-900/40 backdrop-blur-sm"
                onClick={closeChat}
              />
              <motion.div
                initial={{
                  opacity: 0,
                  scale: 0.9,
                  y: 20,
                  borderRadius: "1.6rem",
                }}
                animate={{
                  opacity: 1,
                  scale: 1,
                  y: 0,
                  borderRadius: 0,
                }}
                exit={{
                  opacity: 0,
                  scale: 0.95,
                  y: 10,
                  borderRadius: "1.6rem",
                }}
                transition={{
                  duration: 0.35,
                  ease: [0.22, 1, 0.36, 1],
                }}
                className="fixed inset-0 z-50 overflow-hidden bg-white"
              >
                <ChatPanel variant="modal" onClose={closeChat} />
              </motion.div>
            </>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {recognitionResult && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              className="rounded-3xl border border-octo-200 bg-white p-4 shadow-sm"
            >
              <RecognitionResultCard
                recognitionResult={recognitionResult}
                onClose={() => setRecognitionResult(null)}
                onConfirm={recognitionResult.result.capture_kind === "operation" && recognitionResult.result.can_write_operation ? handleConfirmDraft : undefined}
                isSaving={isSavingDraft}
              />
            </motion.div>
          )}
        </AnimatePresence>

        <section className="rounded-3xl border border-stone-200 bg-white/80 p-4 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-stone-950">经营结论 → 明日动作</p>
              <p className="mt-1 text-xs text-stone-500">日结对账 · 利润拆解 · 渠道 · 库存差异 · 明日动作</p>
            </div>
            <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${hasTodayOperation ? "bg-nori-50 text-nori-700" : "bg-sauce-50 text-sauce-700"}`}>
              {hasTodayOperation ? "今日已入账" : "今日待入账"}
            </span>
          </div>

          {/* 5 步经营决策流摘要 */}
          {hasData && opsSummary && (
            <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-5">
              <DecisionStep
                step="1"
                label="日结对账"
                value={`¥${Math.round(opsSummary.total_original_amount || opsSummary.total_revenue).toLocaleString()}`}
                sub={`实收 ¥${Math.round(opsSummary.total_revenue).toLocaleString()}`}
                tone="info"
                href="/profit"
              />
              <DecisionStep
                step="2"
                label="利润拆解"
                value={opsSummary.profit_ready ? (opsSummary.net_profit >= 0 ? `+¥${Math.round(opsSummary.net_profit).toLocaleString()}` : `-¥${Math.abs(Math.round(opsSummary.net_profit)).toLocaleString()}`) : "待核算"}
                sub={opsSummary.profit_ready ? `食材率 ${(opsSummary.food_cost_rate * 100).toFixed(0)}%` : "成本未补齐"}
                tone={opsSummary.profit_ready ? (opsSummary.net_profit >= 0 ? "good" : "risk") : "watch"}
                href="/profit"
              />
              <DecisionStep
                step="3"
                label="渠道"
                value={`${(opsSummary.takeout_ratio * 100).toFixed(0)}%`}
                sub="外卖占比"
                tone={opsSummary.takeout_ratio > 0.45 ? "watch" : "info"}
                href="/channels"
              />
              <DecisionStep
                step="4"
                label="库存差异"
                value={consumptionVariance ? `${(consumptionVariance.verification_coverage * 100).toFixed(0)}%` : "—"}
                sub={consumptionVariance ? (consumptionVariance.verification_coverage < 0.3 ? "暂不可核验" : `差异 ¥${consumptionVariance.total_variance_value.toFixed(0)}`) : "加载中"}
                tone={consumptionVariance && consumptionVariance.verification_coverage < 0.3 ? "watch" : "info"}
                href="/inventory"
              />
              <DecisionStep
                step="5"
                label="明日动作"
                value={`${todayActions.length} 项`}
                sub={todayActions.length > 0 ? todayActions[0].text.slice(0, 8) + "…" : "暂无"}
                tone={todayActions.length > 0 && todayActions[0].tone === "risk" ? "risk" : todayActions.length > 0 && todayActions[0].tone === "watch" ? "watch" : "good"}
                href="/profit"
              />
            </div>
          )}

          <div className="mt-4 space-y-3">
            {todayActions.map((action, index) => {
              const Icon = action.icon;
              return (
                <Link key={`${action.text}-${index}`} href={action.href || "/"} className="group flex items-center gap-3 rounded-2xl border border-stone-100 bg-white/70 p-3 transition-colors hover:border-octo-200 hover:bg-octo-50/40">
                  <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${iconToneClass(action.tone)}`}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-stone-900">{action.text}</p>
                    <p className="mt-0.5 text-[11px] text-stone-500">{action.evidence}</p>
                  </div>
                  <ChevronRight className="h-4 w-4 text-stone-300 transition-colors group-hover:text-octo-600" />
                </Link>
              );
            })}
          </div>
        </section>
      </main>

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

      {operationDraft && draftEntry && (
        <DraftModal
          draftEntry={draftEntry}
          draftError={draftError}
          isSavingDraft={isSavingDraft}
          fields={operationDraft.fields}
          overallConfidence={operationDraft.confidence}
          onClose={() => { setOperationDraft(null); setDraftSourceItemId(null); }}
          onSendAsChat={() => {
            if (operationDraft) sendMessage(operationDraft.source);
            setOperationDraft(null);
            setDraftSourceItemId(null);
            setInput("");
          }}
          onConfirm={handleConfirmDraft}
          onChange={(key, value) => setDraftEntry((prev) => prev ? { ...prev, [key]: key === "date" || key === "notes" ? value : Number(value) || 0 } : prev)}
        />
      )}

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
                <p className="text-sm font-semibold text-stone-900">电脑拍照</p>
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
    </div>
  );
}

function SourcePill({ label, value, tone }: { label: string; value: string; tone: HealthTone }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs ${softToneClass(tone)}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dotToneClass(tone)}`} />
      <span className="text-stone-500">{label}</span>
      <span className="max-w-[160px] truncate font-medium">{value}</span>
    </span>
  );
}

function StagePill({ label, value, tone }: { label: string; value: string; tone: HealthTone }) {
  const color =
    tone === "risk" ? "border-red-200 bg-red-50 text-red-700" :
    tone === "watch" ? "border-sauce-200 bg-sauce-50 text-sauce-800" :
    tone === "good" ? "border-nori-200 bg-nori-50 text-nori-700" :
    "border-sky-200 bg-sky-50 text-sky-700";
  return (
    <span className={`inline-flex max-w-[220px] items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] shadow-sm ${color}`}>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotToneClass(tone)}`} />
      <span className="text-stone-500">{label}</span>
      <span className="truncate font-medium">{value}</span>
    </span>
  );
}

function HeroMetricCard({
  icon: Icon,
  label,
  value,
  sub,
  tone,
  delay = 0,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  sub: string;
  tone: HealthTone;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
      whileHover={{ y: -2, transition: { duration: 0.2 } }}
      className="group relative overflow-hidden rounded-2xl border border-white/80 bg-white/70 p-4 shadow-sm backdrop-blur-xl transition-shadow hover:shadow-md"
    >
      <div className="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          background: tone === "good" ? "radial-gradient(circle, rgba(34,197,94,0.18), transparent 70%)" :
            tone === "risk" ? "radial-gradient(circle, rgba(239,68,68,0.18), transparent 70%)" :
            tone === "watch" ? "radial-gradient(circle, rgba(249,115,22,0.2), transparent 70%)" :
            "radial-gradient(circle, rgba(249,115,22,0.12), transparent 70%)",
        }}
      />
      <div className="relative z-10">
        <div className="flex items-center justify-between">
          <span className={`flex h-8 w-8 items-center justify-center rounded-xl ${iconToneClass(tone)}`}>
            <Icon className="h-4 w-4" />
          </span>
          <span className={`rounded-full px-2 py-0.5 text-[9px] font-medium ${
            tone === "good" ? "bg-nori-50 text-nori-700" :
            tone === "risk" ? "bg-red-50 text-red-700" :
            tone === "watch" ? "bg-sauce-50 text-sauce-700" :
            "bg-stone-100 text-stone-500"
          }`}>
            {tone === "good" ? "健康" : tone === "risk" ? "注意" : tone === "watch" ? "观察" : "待录入"}
          </span>
        </div>
        <p className="mt-3 text-[11px] font-medium text-stone-500">{label}</p>
        <p className="mt-1 text-2xl font-semibold tabular-nums tracking-tight text-stone-950">{value}</p>
        <p className="mt-2 text-[11px] leading-4 text-stone-500">{sub}</p>
      </div>
    </motion.div>
  );
}

function StageMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/80 bg-white/70 px-4 py-3 shadow-sm backdrop-blur-xl">
      <p className="text-[10px] text-stone-400">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums text-stone-950">{value}</p>
    </div>
  );
}

function StageInputDock({
  input,
  setInput,
  isStreaming,
  isRecording,
  isTranscribing,
  voiceMessage,
  onSubmit,
  onPaste,
  onDrop,
  onUpload,
  onCamera,
  onVoice,
}: {
  input: string;
  setInput: (value: string) => void;
  isStreaming: boolean;
  isRecording: boolean;
  isTranscribing: boolean;
  voiceMessage: string;
  onSubmit: (event: React.FormEvent) => void;
  onPaste: (event: React.ClipboardEvent<HTMLFormElement>) => void;
  onDrop: (event: React.DragEvent<HTMLFormElement>) => void;
  onUpload: () => void;
  onCamera: () => void;
  onVoice: () => void;
}) {
  return (
    <form
      onSubmit={onSubmit}
      onPaste={onPaste}
      onDrop={onDrop}
      onDragOver={(event) => event.preventDefault()}
      className="rounded-[1.6rem] border border-stone-200 bg-white/82 p-2 shadow-[0_16px_50px_rgba(120,88,55,0.16)] backdrop-blur-2xl"
    >
      <div className="flex flex-col gap-2 md:flex-row md:items-center">
        <div className="flex min-w-0 flex-1 items-center gap-3 rounded-[1.25rem] bg-stone-50/80 px-3 py-2 ring-1 ring-stone-200">
          <span className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-octo-50 text-octo-600 ring-1 ring-octo-100 md:flex">
            <Sparkles className="h-5 w-5" />
          </span>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="问经营问题、安排任务，或直接发文字和资料…"
            rows={1}
            className="max-h-24 min-h-11 min-w-0 flex-1 resize-none bg-transparent py-3 text-sm leading-5 text-stone-900 outline-none placeholder:text-stone-400"
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                onSubmit(event as unknown as React.FormEvent);
              }
            }}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2 md:shrink-0">
          <StageDockButton onClick={onUpload} icon={Upload} label="文件" />
          <StageDockButton onClick={onCamera} icon={Camera} label="拍照" />
          <StageDockButton onClick={onVoice} icon={isTranscribing ? Loader2 : Mic} label={isRecording ? "结束" : "语音"} active={isRecording} />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="ml-auto inline-flex h-12 items-center justify-center gap-2 rounded-full bg-octo-500 px-5 text-sm font-semibold text-white shadow-sm shadow-octo-200/80 transition-transform hover:scale-[1.02] hover:bg-octo-600 disabled:cursor-not-allowed disabled:bg-stone-200 disabled:text-stone-400 disabled:shadow-none md:ml-0"
          >
            {isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            交给掌柜
          </button>
        </div>
      </div>
      {voiceMessage && <p className="px-3 pt-2 text-[11px] text-stone-500">{voiceMessage}</p>}
    </form>
  );
}

function StageDockButton({ onClick, icon: Icon, label, active = false }: { onClick: () => void; icon: LucideIcon; label: string; active?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex h-12 items-center gap-1.5 rounded-full px-3 text-xs font-medium transition-colors ${
        active ? "bg-red-50 text-red-700 ring-1 ring-red-200" : "bg-stone-100 text-stone-600 hover:bg-octo-50 hover:text-octo-700"
      }`}
    >
      <Icon className={`h-4 w-4 ${active ? "animate-pulse" : ""}`} />
      {label}
    </button>
  );
}

function IntakePanel({
  input,
  setInput,
  isStreaming,
  isRecording,
  isTranscribing,
  voiceMessage,
  onSubmit,
  onPaste,
  onDrop,
  onUpload,
  onCamera,
  onVoice,
  onPrompt,
}: {
  input: string;
  setInput: (value: string) => void;
  isStreaming: boolean;
  isRecording: boolean;
  isTranscribing: boolean;
  voiceMessage: string;
  onSubmit: (event: React.FormEvent) => void;
  onPaste: (event: React.ClipboardEvent<HTMLFormElement>) => void;
  onDrop: (event: React.DragEvent<HTMLFormElement>) => void;
  onUpload: () => void;
  onCamera: () => void;
  onVoice: () => void;
  onPrompt: (value: string) => void;
}) {
  return (
    <form
      onSubmit={onSubmit}
      onPaste={onPaste}
      onDrop={onDrop}
      onDragOver={(event) => event.preventDefault()}
      className="rounded-3xl border border-octo-200 bg-white p-4 shadow-sm"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 text-sm font-semibold text-stone-950">
            <Sparkles className="h-4 w-4 text-octo-600" />
            交给掌柜
          </p>
          <p className="mt-1 text-xs leading-5 text-stone-500">记账、截图、单据、库存、员工、异常，都可以直接放进来。</p>
        </div>
        <span className="rounded-full bg-octo-50 px-2.5 py-1 text-[11px] font-medium text-octo-700">今日入口</span>
      </div>

      <textarea
        value={input}
        onChange={(event) => setInput(event.target.value)}
        placeholder="今天有什么要记？例如：卖了2300，美团900，章鱼粉快没了……"
        className="mt-4 min-h-32 w-full resize-none rounded-2xl border border-stone-200 bg-stone-50/70 px-4 py-3 text-sm leading-6 text-stone-900 outline-none transition-colors placeholder:text-stone-400 focus:border-octo-300 focus:bg-white focus:ring-4 focus:ring-octo-50"
        rows={5}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            onSubmit(event as unknown as React.FormEvent);
          }
        }}
      />

      <div className="mt-3 flex flex-wrap gap-2">
        {QUICK_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => onPrompt(prompt)}
            className="rounded-full border border-stone-200 bg-white px-3 py-1.5 text-xs text-stone-600 transition-colors hover:border-octo-200 hover:bg-octo-50 hover:text-octo-700"
          >
            {prompt}
          </button>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-stone-100 pt-3">
        <AgentInputButton onClick={onUpload} icon={Upload} label="截图/文件" />
        <AgentInputButton onClick={onCamera} icon={Camera} label="拍照" />
        <AgentInputButton onClick={onVoice} icon={isTranscribing ? Loader2 : Mic} label={isRecording ? "结束录音" : "语音"} active={isRecording} />
        <span className="hidden text-xs text-stone-400 md:inline">录入后先确认，再写入经营档案</span>
        <button
          type="submit"
          disabled={!input.trim() || isStreaming}
          className="ml-auto inline-flex items-center gap-2 rounded-2xl bg-octo-500 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-octo-600 disabled:cursor-not-allowed disabled:bg-stone-300"
        >
          {isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          交给掌柜
        </button>
      </div>
      {voiceMessage && <p className="mt-2 text-xs text-stone-500">{voiceMessage}</p>}
    </form>
  );
}

function RecognitionResultCard({
  recognitionResult,
  onClose,
  onConfirm,
  isSaving,
}: {
  recognitionResult: { fileName: string; imageUrl: string; source: SourceType; result: RecognizeResponse };
  onClose: () => void;
  onConfirm?: () => void;
  isSaving: boolean;
}) {
  const artifact = recognitionResult.result.structured_artifact;
  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      className="overflow-hidden rounded-3xl border border-octo-200 bg-white shadow-sm"
    >
      <div className="flex items-center justify-between border-b border-stone-100 px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-stone-950">已整理：{recognitionResult.source}</p>
          <p className="mt-0.5 text-xs text-stone-500">{recognitionResult.fileName}</p>
        </div>
        <button type="button" onClick={onClose} className="rounded-full p-1.5 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="grid gap-4 p-4 md:grid-cols-[180px_minmax(0,1fr)]">
        <div className="aspect-[4/5] overflow-hidden rounded-2xl border border-stone-100 bg-stone-50">
          <Image src={recognitionResult.imageUrl} alt="识别图片" width={360} height={450} unoptimized className="h-full w-full object-contain" />
        </div>
        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap gap-2">
            <Chip label={recognitionResult.result.capture_kind || "unknown"} />
            <Chip label={artifact?.document_class || recognitionResult.result.source_type || "待分类"} />
            <Chip label={`写入：${artifact?.write_targets?.join("、") || recognitionResult.result.recommended_destination || "待确认"}`} />
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {recognitionResult.result.fields.slice(0, 8).map((field) => (
              <div key={`${field.key}-${field.label}`} className="rounded-2xl bg-stone-50 p-3">
                <p className="text-[11px] text-stone-500">{field.label || field.key}</p>
                <p className="mt-1 truncate text-sm font-semibold text-stone-900">{String(field.value || "—")}</p>
                <p className="mt-1 text-[10px] text-stone-400">置信度：{confidenceLabel(field.confidence)}</p>
              </div>
            ))}
          </div>
          {artifact?.canonical_sections?.risks && artifact.canonical_sections.risks.length > 0 && (
            <p className="rounded-2xl bg-red-50 p-3 text-xs text-red-700">{artifact.canonical_sections.risks[0].title}：{artifact.canonical_sections.risks[0].detail}</p>
          )}
          <div className="flex flex-wrap justify-end gap-2">
            <Link href="/capture" className="rounded-xl border border-stone-200 px-3 py-2 text-xs font-medium text-stone-600 transition-colors hover:bg-stone-50">进入资料入库详情</Link>
            {onConfirm && (
              <button type="button" onClick={onConfirm} disabled={isSaving} className="rounded-xl bg-octo-500 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-octo-600 disabled:opacity-50">
                {isSaving ? "写入中…" : "确认写入经营台账"}
              </button>
            )}
          </div>
        </div>
      </div>
    </motion.section>
  );
}

function AgentInputButton({
  onClick,
  icon: Icon,
  label,
  active = false,
}: {
  onClick: () => void;
  icon: LucideIcon;
  label: string;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-medium transition-colors ${
        active ? "bg-red-50 text-red-700 ring-1 ring-red-200" : "bg-stone-100 text-stone-600 hover:bg-stone-200"
      }`}
    >
      <Icon className={`h-3.5 w-3.5 ${active ? "animate-pulse" : ""}`} />
      {label}
    </button>
  );
}

function DraftModal({ draftEntry, draftError, isSavingDraft, fields, overallConfidence, onClose, onSendAsChat, onConfirm, onChange }: {
  draftEntry: DailyOperationEntry;
  draftError: string | null;
  isSavingDraft: boolean;
  fields?: { key: keyof DailyOperationEntry; label: string; value: number | string; confidence: "high" | "medium" | "low" }[];
  overallConfidence?: "high" | "medium" | "low";
  onClose: () => void;
  onSendAsChat: () => void;
  onConfirm: () => void;
  onChange: (key: keyof DailyOperationEntry, value: string) => void;
}) {
  const confColor = overallConfidence === "high" ? "text-nori-600 bg-nori-50" : overallConfidence === "medium" ? "text-sauce-600 bg-sauce-50" : "text-red-600 bg-red-50";
  const confLabel = overallConfidence === "high" ? "高置信度" : overallConfidence === "medium" ? "中置信度" : "低置信度";
  return (
    <div className="fixed inset-0 z-60 flex items-end justify-center bg-stone-900/60 px-4 pb-4 backdrop-blur-md md:items-center">
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        className="w-full max-w-xl rounded-2xl border border-white/50 bg-white p-4 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-medium text-stone-500">经营数据草稿</p>
            <h2 className="mt-1 text-base font-semibold text-stone-900">确认后写入经营档案</h2>
          </div>
          <button onClick={onClose} className="rounded-full p-1.5 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700"><X className="h-4 w-4" /></button>
        </div>
        {fields && fields.length > 0 && (
          <div className="mt-3 rounded-xl border border-octo-100 bg-octo-50/30 p-2.5">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-[10px] font-medium text-stone-500">AI 识别字段 · {fields.length} 项</p>
              {overallConfidence && <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${confColor}`}>{confLabel}</span>}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {fields.map((field) => (
                <div key={String(field.key)} className="min-w-[72px] rounded-lg border border-stone-100 bg-white/70 p-1.5">
                  <p className="text-[9px] text-stone-500">{field.label}</p>
                  <p className="text-xs font-semibold text-stone-900">{field.value || "—"}</p>
                  <p className="mt-0.5 text-[8px] text-stone-400">{confidenceLabel(field.confidence)}</p>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
          <DraftInput label="日期" value={draftEntry.date} onChange={(v) => onChange("date", v)} type="date" />
          <DraftInput label="营收" value={draftEntry.revenue} onChange={(v) => onChange("revenue", v)} />
          <DraftInput label="订单" value={draftEntry.orders} onChange={(v) => onChange("orders", v)} />
          <DraftInput label="差评" value={draftEntry.bad_reviews ?? 0} onChange={(v) => onChange("bad_reviews", v)} />
          <DraftInput label="外卖单" value={draftEntry.takeout_orders} onChange={(v) => onChange("takeout_orders", v)} />
          <DraftInput label="食材成本" value={draftEntry.food_cost} onChange={(v) => onChange("food_cost", v)} />
          <DraftInput label="人工" value={draftEntry.labor} onChange={(v) => onChange("labor", v)} />
          <DraftInput label="平台费" value={draftEntry.platform_fee} onChange={(v) => onChange("platform_fee", v)} />
        </div>
        {draftError && <p className="mt-2 rounded-lg bg-red-50 px-3 py-1.5 text-xs text-red-700">{draftError}</p>}
        <div className="mt-3 flex justify-end gap-2">
          <button onClick={onSendAsChat} className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs text-stone-600 transition-colors hover:bg-stone-100">只当聊天</button>
          <button onClick={onConfirm} disabled={isSavingDraft} className="rounded-lg bg-octo-500 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-octo-600 disabled:opacity-50">{isSavingDraft ? "写入中..." : "确认写入"}</button>
        </div>
      </motion.div>
    </div>
  );
}

function DraftInput({ label, value, onChange, type = "number" }: { label: string; value: string | number; onChange: (value: string) => void; type?: "number" | "date" }) {
  return (
    <label className="min-w-0">
      <span className="text-[10px] text-stone-500">{label}</span>
      <input type={type} value={value} min={type === "number" ? 0 : undefined} onChange={(e) => onChange(e.target.value)} className="mt-0.5 w-full rounded-lg border border-stone-200 bg-stone-50 px-2 py-1.5 text-xs text-stone-900 outline-none focus:border-octo-400 focus:bg-white" />
    </label>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-white px-3 py-2">
      <p className="text-[10px] text-stone-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-stone-950">{value}</p>
    </div>
  );
}

function FactTile({ label, value, sub, tone }: { label: string; value: string; sub: string; tone: HealthTone }) {
  return (
    <div className={`min-h-28 rounded-2xl border p-3 ${softToneClass(tone)}`}>
      <div className="flex items-center gap-1.5">
        <span className={`h-1.5 w-1.5 rounded-full ${dotToneClass(tone)}`} />
        <p className="text-[11px] font-medium text-stone-600">{label}</p>
      </div>
      <p className="mt-2 text-xl font-semibold tabular-nums text-stone-950">{value}</p>
      <p className="mt-1 text-[11px] leading-4 text-stone-600">{sub}</p>
    </div>
  );
}

function Chip({ label }: { label: string }) {
  return <span className="rounded-full bg-stone-100 px-2.5 py-1 text-[11px] font-medium text-stone-600">{label}</span>;
}

function DecisionStep({
  step,
  label,
  value,
  sub,
  tone,
  href,
}: {
  step: string;
  label: string;
  value: string;
  sub: string;
  tone: "good" | "watch" | "risk" | "info";
  href: string;
}) {
  const border = tone === "good" ? "border-emerald-200" : tone === "risk" ? "border-red-200" : tone === "watch" ? "border-amber-200" : "border-stone-200";
  const bg = tone === "good" ? "bg-emerald-50/40" : tone === "risk" ? "bg-red-50/40" : tone === "watch" ? "bg-amber-50/40" : "bg-white/60";
  const dot = tone === "good" ? "bg-emerald-500" : tone === "risk" ? "bg-red-500" : tone === "watch" ? "bg-amber-500" : "bg-stone-400";
  return (
    <Link href={href} className={`group block rounded-2xl border ${border} ${bg} p-3 transition-colors hover:bg-white/80`}>
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white text-[10px] font-bold text-stone-600 shadow-sm">{step}</span>
        <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
        <span className="text-[10px] font-medium text-stone-500">{label}</span>
      </div>
      <p className="mt-2 text-sm font-bold text-stone-900">{value}</p>
      <p className="mt-0.5 text-[10px] text-stone-500">{sub}</p>
    </Link>
  );
}

function formatCurrency(value: number) {
  return `¥${Math.round(value).toLocaleString()}`;
}

function confidenceLabel(confidence: "high" | "medium" | "low") {
  return confidence === "high" ? "高" : confidence === "medium" ? "中" : "低";
}

function softToneClass(tone: HealthTone) {
  if (tone === "risk") return "border-red-200 bg-red-50 text-red-700";
  if (tone === "watch") return "border-sauce-200 bg-sauce-50 text-sauce-700";
  if (tone === "good") return "border-nori-200 bg-nori-50 text-nori-700";
  return "border-sky-200 bg-sky-50 text-sky-700";
}

function dotToneClass(tone: HealthTone) {
  if (tone === "risk") return "bg-red-500";
  if (tone === "watch") return "bg-sauce-400";
  if (tone === "good") return "bg-nori-500";
  return "bg-sky-500";
}

function iconToneClass(tone: HealthTone) {
  if (tone === "risk") return "bg-red-50 text-red-600";
  if (tone === "watch") return "bg-sauce-50 text-sauce-600";
  if (tone === "good") return "bg-nori-50 text-nori-600";
  return "bg-octo-50 text-octo-700";
}
