"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  CalendarDays,
  Camera,
  ChevronRight,
  CloudSun,
  FileText,
  Loader2,
  Mic,
  PackageCheck,
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
  confirmCaptureAudit,
  getBusinessFacts,
  getCaptureAuditLog,
  getConsumptionVariance,
  getDailyReviewCheck,
  getForecast,
  getFinanceDailySnapshot,
  getFinanceOverview,
  getOperationSummary,
  getOperations,
  getStaff,
  getTodayInsight,
  getTodayOperatingCard,
  getWeather,
  transcribeSpeech,
  type CaptureAuditLogItem,
  type ConsumptionVariance,
  type DailyReviewCheck,
  type DailyOperationEntry,
  type DailyFinanceSnapshotV1,
  type ForecastItem,
  type FinanceOverviewV1,
  type OperationSummary,
  type TodayOperatingCard,
  type WeatherResponse,
} from "@/lib/api";
import { useAIChat } from "@/lib/hooks/useAIChat";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { CaptureReviewCard } from "@/components/capture/CaptureReviewCard";
import {
  classifyCaptureSource,
  processCaptureFile,
  processCaptureText,
  type CaptureReview,
  type CaptureSourceType,
} from "@/lib/capture-intake";
import { toDateInputValue } from "@/lib/operationDraft";
import { calcBreakEvenAnalysis, type BreakEvenResult } from "@/domain/calculations";

type WorkStatus = "待确认" | "分析中" | "已入库";
type IntakeItem = { id: string; name: string; source: CaptureSourceType; status: WorkStatus; summary: string };

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

export default function OverviewPage() {
  return (
    <Suspense fallback={<div className="min-h-[calc(100vh-56px)] bg-[#fbf7ef]" />}>
      <OverviewPageContent />
    </Suspense>
  );
}

function OverviewPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const audioRecorderRef = useRef<MediaRecorder | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const { isStreaming, sendMessage } = useAIChat();

  const [input, setInput] = useState("");
  const [chatOpen, setChatOpen] = useState(searchParams.get("chat") === "open");
  const [intakeItems, setIntakeItems] = useState<IntakeItem[]>([]);
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceMessage, setVoiceMessage] = useState("");
  const [draftError, setDraftError] = useState<string | null>(null);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const [latestOperationDate, setLatestOperationDate] = useState<string | null>(null);
  const [recognitionStage, setRecognitionStage] = useState<string | null>(null);
  const [recognitionResult, setRecognitionResult] = useState<CaptureReview | null>(null);

  const [opsSummary, setOpsSummary] = useState<OperationSummary | null>(null);
  const [operationEntries, setOperationEntries] = useState<DailyOperationEntry[]>([]);
  const [forecastUrgent, setForecastUrgent] = useState<ForecastItem[]>([]);
  const [, setStaffCount] = useState(0);
  const [, setDailyTrend] = useState<{ date: string; 营收: number }[]>([]);
  const [breakEvenData, setBreakEvenData] = useState<BreakEvenResult | null>(null);
  const [consumptionVariance, setConsumptionVariance] = useState<ConsumptionVariance | null>(null);
  const [weather, setWeather] = useState<WeatherResponse | null>(null);
  const [weatherFailed, setWeatherFailed] = useState(false);
  const [auditLogs, setAuditLogs] = useState<CaptureAuditLogItem[]>([]);
  const [todayCard, setTodayCard] = useState<TodayOperatingCard | null>(null);
  const [selectedDate, setSelectedDate] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [, setTodayInsight] = useState<{ insight: string; health_status: "good" | "watch" | "risk"; key_concern: string | null } | null>(null);
  const [reviewCheck, setReviewCheck] = useState<DailyReviewCheck | null>(null);
  const [pendingFactCount, setPendingFactCount] = useState(0);
  const [financeOverview, setFinanceOverview] = useState<FinanceOverviewV1 | null>(null);
  const [financeDay, setFinanceDay] = useState<DailyFinanceSnapshotV1 | null>(null);

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
  const hasData = Boolean(opsSummary && opsSummary.entry_count > 0);
  const latestFinanceDate = financeOverview?.last_data_date ?? null;
  const recordedMerchantNetDates = useMemo(
    () => new Set((financeOverview?.merchant_net_sales ?? []).map((sale) => sale.business_date)),
    [financeOverview?.merchant_net_sales],
  );
  const missingSalesDates = useMemo(
    () => (financeOverview?.daily_revenue ?? []).filter(
      (day) => day.status === "missing" && !recordedMerchantNetDates.has(day.business_date),
    ),
    [financeOverview?.daily_revenue, recordedMerchantNetDates],
  );
  const knownSalesDayCount = useMemo(() => {
    const dates = new Set(recordedMerchantNetDates);
    (financeOverview?.daily_revenue ?? []).forEach((day) => {
      if (day.status !== "missing") dates.add(day.business_date);
    });
    return dates.size;
  }, [financeOverview?.daily_revenue, recordedMerchantNetDates]);
  const unclosedSalesDayCount = Math.max(knownSalesDayCount - (financeOverview?.closed_days ?? 0), 0);

  const fetchLiveData = useCallback(async () => {
    setLoadError(null);
    const weatherRequest = getWeather()
      .then((response) => {
        setWeather(response);
        setWeatherFailed(false);
      })
      .catch(() => {
        setWeather(null);
        setWeatherFailed(true);
      });
    // The workbench always opens on today's operating date.  A missing
    // platform/POS feed is an explicit pending state, never a reason to jump
    // backwards to the last uploaded day.
    const reviewDate = selectedDate || today;
    try {
      const [ops, fRes, staffRes, opsList, auditRes, insightRes, todayCardRes, closeRes, pendingFactsRes, financeRes, financeDayRes] = await Promise.all([
        getOperationSummary(DEFAULT_PROJECT_ID, 7),
        getForecast(DEFAULT_PROJECT_ID),
        getStaff(DEFAULT_PROJECT_ID),
        getOperations(DEFAULT_PROJECT_ID, 7),
        getCaptureAuditLog(DEFAULT_PROJECT_ID, 8),
        getTodayInsight(DEFAULT_PROJECT_ID).catch(() => null),
        getTodayOperatingCard(DEFAULT_PROJECT_ID, reviewDate).catch(() => null),
        getDailyReviewCheck(DEFAULT_PROJECT_ID, reviewDate).catch(() => null),
        getBusinessFacts(DEFAULT_PROJECT_ID, "need_review").catch(() => null),
        getFinanceOverview(DEFAULT_PROJECT_ID).catch(() => null),
        getFinanceDailySnapshot(reviewDate).catch(() => null),
      ]);
      setOpsSummary(ops);
      setForecastUrgent(fRes.forecast.filter((f) => f.action === "urgent" || f.action === "recommend").slice(0, 3));
      setStaffCount(staffRes.staff.filter((s) => s.status === "在岗").length);
      setDailyTrend(opsList.entries.slice(-7).map((e) => ({ date: e.date.slice(5), 营收: e.revenue })));
      setOperationEntries(opsList.entries);
      const latestDate = opsList.entries.at(-1)?.date ?? null;
      setLatestOperationDate(latestDate);
      if (!selectedDate) setSelectedDate(today);
      setBreakEvenData(ops.profit_ready ? calcBreakEvenAnalysis(opsList.entries, ops.entry_count) : null);
      setAuditLogs(auditRes.logs || []);
      if (insightRes) setTodayInsight(insightRes);
      if (todayCardRes) setTodayCard(todayCardRes);
      if (closeRes) setReviewCheck(closeRes);
      setPendingFactCount(pendingFactsRes?.facts?.length ?? 0);
      if (financeRes) setFinanceOverview(financeRes);
      setFinanceDay(financeDayRes);

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

    await weatherRequest;
  }, [selectedDate, today]);

  useEffect(() => { fetchLiveData(); }, [fetchLiveData]);

  useEffect(() => {
    const interval = setInterval(fetchLiveData, 60000);
    return () => clearInterval(interval);
  }, [fetchLiveData]);

  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 60000);
    return () => clearInterval(interval);
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
      setIntakeItems((prev) => prev.map((item) => item.id === itemId ? {
        ...item,
        source: detectedSource,
        status: "待确认",
        summary: imported.created > 0
          ? `已建立 ${imported.created} 条待确认经营事实`
          : (result.parse_error || "等待确认归档"),
      } : item));
      setRecognitionStage(null);
      await fetchLiveData();
      if (imported.created > 0) {
        URL.revokeObjectURL(imageUrl);
        router.push("/capture");
        return;
      }
      setDraftError(importError);
      setRecognitionResult({ itemId, fileName: file.name, imageUrl, source: detectedSource, result });
    } catch (err) {
      URL.revokeObjectURL(imageUrl);
      setIntakeItems((prev) => prev.map((e) => e.id === itemId ? {
        ...e,
        status: "待确认",
        summary: err instanceof Error ? err.message : "识别请求失败",
      } : e));
      setDraftError(err instanceof Error ? err.message : "识别请求失败");
      setRecognitionStage(null);
    }
  }, [fetchLiveData, router]);

  const handleSubmit = useCallback(async (event: React.FormEvent) => {
    event.preventDefault();
    const value = input.trim();
    if (!value) return;

    setChatOpen(true);
    const params = new URLSearchParams(searchParams.toString());
    params.set("chat", "open");
    router.push(`?${params.toString()}`, { scroll: false });
    await sendMessage(value);
    setInput("");
  }, [input, router, searchParams, sendMessage]);

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
        void registerFile(new File([blob], `电脑拍照-${Date.now()}.jpg`, { type: "image/jpeg" }));
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

  const handleConfirmDocument = useCallback(async () => {
    if (!recognitionResult) return;
    setIsSavingDraft(true);
    setDraftError(null);
    try {
      const artifact = recognitionResult.result.structured_artifact;
      const recognizedDate = recognitionResult.result.fields.find((field) => field.key === "date")?.value;
      const result = await confirmCaptureAudit({
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
        summary: result.posted_expenses.length > 0
          ? `已归档，并生成${result.posted_expenses.length}笔经营费用分录`
          : result.posted_business_facts.length > 0
            ? `已归档，${result.posted_business_facts.length}条经营事实已确认入账`
            : result.pending_business_facts.length > 0
              ? `已归档，${result.pending_business_facts.length}条库存事实等待补充数量后确认`
              : "已归档；未发现可安全自动过账的字段",
      } : item));
      closeRecognitionResult();
      await fetchLiveData();
    } catch (err) {
      setDraftError(err instanceof Error ? err.message : "资料归档失败");
    } finally {
      setIsSavingDraft(false);
    }
  }, [closeRecognitionResult, fetchLiveData, recognitionResult]);

  const weatherTemperature = weather?.current.temperature;
  const weatherText = weather
    ? weather.status === "unavailable" || weather.current.weather === "unknown"
      ? "天气暂不可用"
      : `${WEATHER_LABELS[weather.current.weather] || weather.current.weather_text || "天气"} ${weatherTemperature == null ? "—" : `${weatherTemperature}°`}`
    : weatherFailed ? "天气连接失败" : "天气加载中";
  const weatherTone: HealthTone = weatherFailed || weather?.status === "unavailable"
    ? "risk"
    : weather?.status === "partial" || weather?.is_stale
      ? "watch"
      : "info";
  const weatherTitle = weather
    ? `${weather.address}｜实况：${weather.current_source || "不可用"}｜预报：${weather.forecast_source || "不可用"}｜${weather.observed_at || "更新时间未知"}`
    : weatherText;

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
      if (opsSummary.profit_ready && opsSummary.net_profit != null) {
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
          text: `${opsSummary.entry_count}天实收 ¥${opsSummary.total_revenue.toFixed(0)} 已确认，补齐成本后计算利润`,
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
      if (opsSummary.profit_ready && opsSummary.food_cost_rate != null && opsSummary.food_cost_rate > 0.35) {
        actions.push({
          icon: AlertTriangle,
          text: `食材率 ${(opsSummary.food_cost_rate * 100).toFixed(0)}% 超标（红线 35%），检查损耗和采购价`,
          tone: "risk",
          href: "/profit",
          evidence: "来自成本结构",
        });
      }
      if (opsSummary.profit_ready && opsSummary.labor_cost_rate != null && opsSummary.labor_cost_rate > 0.25) {
        actions.push({
          icon: Users,
          text: `人工率 ${(opsSummary.labor_cost_rate * 100).toFixed(0)}% 超标（红线 25%），按时段重排班`,
          tone: "risk",
          href: "/training",
          evidence: "来自成本结构",
        });
      }
      if (opsSummary.takeout_ratio != null && opsSummary.takeout_ratio > 0.45) {
        actions.push({
          icon: Truck,
          text: `外卖占比 ${(opsSummary.takeout_ratio * 100).toFixed(0)}%，核对平台费和到手利润`,
          tone: "watch",
          href: "/channels",
          evidence: "来自渠道拆分",
        });
      }
    }
    if (weather && (
      weather.current.weather === "light_rain"
      || weather.current.weather === "heavy_rain"
      || weather.current.weather === "thunderstorm"
      || (weather.current.temperature != null && weather.current.temperature > 35)
    )) {
      actions.push({
        icon: CloudSun,
        text: weather.current.tips?.[0] || "结合天气调整备料和排班",
        tone: "watch",
        href: "/calendar",
        evidence: `实况 ${weather.current_source || "暂缺"} · 预报 ${weather.forecast_source || "暂缺"}`,
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

  const settlement = opsSummary?.settlement_summary;
  const formerOwnerAmount = settlement?.former_owner ?? 0;
  const fixtureSales = todayCard?.fixture_sales?.sales ? todayCard.fixture_sales : null;
  const selectedBusinessDate = selectedDate || today;
  const selectedOperation = operationEntries.find((entry) => entry.date === selectedBusinessDate) ?? null;
  const financeDayAvailable = financeDay?.data_state === "available";
  const selectedMerchantNet = financeDayAvailable ? financeDay.day_activity.merchant_net_minor / 100 : null;
  const selectedAccountingRevenue = financeDayAvailable ? financeDay.day_activity.accounting_revenue_minor / 100 : null;
  const selectedStoreControlled = financeDay && financeOverview?.has_data
    ? financeDay.as_of.store_controlled_minor / 100
    : null;
  const selectedThirdPartyFunds = financeDay && financeOverview?.has_data
    ? financeDay.as_of.fund_positions
      .filter((position) => position.account_kind === "platform_wallet" || position.owner_kind === "former_owner")
      .reduce((total, position) => total + position.balance_minor, 0) / 100
    : null;
  const hasSelectedLedgerData = financeDayAvailable || Boolean(selectedOperation || fixtureSales);

  const dailyFactRows = useMemo(() => [
    {
      label: "实际到手营业额",
      value: selectedMerchantNet !== null ? formatCurrency(selectedMerchantNet) : fixtureSales ? formatCurrency(fixtureSales.sales.net_operating_income) : selectedOperation ? formatCurrency(selectedOperation.revenue) : "待录入",
      sub: selectedMerchantNet !== null ? "已确认经营口径，不是利润" : fixtureSales ? "来源：客如云营业日报" : "缺当日报表或已确认销售事实",
      tone: hasSelectedLedgerData ? "good" as HealthTone : "watch" as HealthTone,
    },
    {
      label: "会计营业收入",
      value: selectedAccountingRevenue !== null ? formatCurrency(selectedAccountingRevenue) : "待核对",
      sub: selectedAccountingRevenue !== null ? "按已确认销售凭证入账" : "不能用银行卡到账代替营业收入",
      tone: selectedAccountingRevenue !== null ? "good" as HealthTone : "watch" as HealthTone,
    },
    {
      label: "订单数",
      value: fixtureSales ? `${fixtureSales.sales.order_count} 单` : selectedOperation?.orders ? `${selectedOperation.orders} 单` : "待核对",
      sub: fixtureSales ? "来自已保存营业日报" : "报表未提供可靠订单口径时保持待核对",
      tone: fixtureSales || selectedOperation?.orders ? "good" as HealthTone : "watch" as HealthTone,
    },
    {
      label: "平台及代收资金",
      value: selectedThirdPartyFunds !== null ? formatCurrency(selectedThirdPartyFunds) : "待核对",
      sub: "是资金位置，不重复计算营业收入",
      tone: (selectedThirdPartyFunds ?? 0) > 0 ? "watch" as HealthTone : "info" as HealthTone,
    },
    {
      label: "店铺可控资金",
      value: selectedStoreControlled !== null ? formatCurrency(selectedStoreControlled) : "待核对",
      sub: "所选日期截止时点，不等于当日收入",
      tone: selectedStoreControlled !== null ? "good" as HealthTone : "watch" as HealthTone,
    },
    {
      label: "库存消耗",
      value: "暂不能入账",
      sub: fixtureSales?.inventory.status || "缺开店/复盘库存照片或 BOM",
      tone: "watch" as HealthTone,
    },
    {
      label: "利润",
      value: "不能精确确认",
      sub: todayCard?.profit_statement || "成本、库存或平台费未补齐",
      tone: "watch" as HealthTone,
    },
    {
      label: "明日断货",
      value: forecastUrgent.length > 0 ? `${forecastUrgent.length} 项` : "暂无紧急",
      sub: forecastUrgent[0] ? `${forecastUrgent[0].name} 剩${forecastUrgent[0].days_remaining ?? "?"}天` : "继续保持每日盘点",
      tone: forecastUrgent.length > 0 ? "risk" as HealthTone : "good" as HealthTone,
    },
  ], [fixtureSales, forecastUrgent, hasSelectedLedgerData, selectedAccountingRevenue, selectedMerchantNet, selectedOperation, selectedStoreControlled, selectedThirdPartyFunds, todayCard]);

  const gapQuestions = useMemo(() => {
    const gaps: { title: string; body: string; action: string; tone: HealthTone; href: string }[] = [];
    if (todayCard?.missing_fields?.length) {
      todayCard.missing_fields.forEach((gap) => {
        gaps.push({
          title: `${gap.priority} · ${gap.missing}`,
          body: `${gap.why}。影响：${gap.impact}。${gap.action}`,
          action: gap.priority === "P0" ? "立即处理" : "补证据",
          tone: gap.priority === "P0" ? "risk" : "watch",
          href: gap.missing.includes("库存") || gap.missing.includes("BOM") ? "/inventory" : "/capture",
        });
      });
      return gaps.slice(0, 4);
    }
    if (pendingCount > 0) {
      gaps.push({
        title: `${pendingCount} 条资料还没确认`,
        body: "不确认就不能正式写入钱账或库存账，避免把截图金额当成真实账。",
        action: "去确认",
        tone: "watch",
        href: "/capture",
      });
    }
    if (!hasSelectedLedgerData) {
      gaps.push({
        title: `缺 ${selectedBusinessDate} 销售事实`,
        body: "会影响所选日期销售额、利润估算和后续备货判断。上传客如云日报或直接输入当日销售。",
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
  }, [consumptionVariance, formerOwnerAmount, hasSelectedLedgerData, opsSummary?.profit_ready, pendingCount, selectedBusinessDate, todayCard]);

  return (
    <div className="min-h-[calc(100vh-56px)] min-w-0 overflow-x-hidden">
      <main className="mx-auto w-full max-w-[1600px] min-w-0 space-y-3">
        {loadError && (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {loadError}
          </div>
        )}

        {pendingFactCount > 0 && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
            <Link href="/capture" className="flex w-full items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-left transition hover:bg-amber-100/70">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-amber-900">{pendingFactCount} 条待确认事实</p>
                <p className="text-xs text-amber-700">逐条核对证据与识别结果，再写入对应正式记录</p>
              </div>
              <ChevronRight className="h-4 w-4 shrink-0 text-amber-400" />
            </Link>
          </motion.div>
        )}

        {missingSalesDates.length > 0 && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
            <Link href="/capture" className="flex w-full items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-left transition hover:bg-red-100/70">
              <CalendarDays className="h-4 w-4 shrink-0 text-red-700" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-red-950">Agent 发现营业数据缺口</p>
                <p className="text-xs text-red-800">{missingSalesDates.map((day) => day.business_date.slice(5)).join("、")} 未录入；去统一入口补充日报或平台资料。</p>
              </div>
              <ChevronRight className="h-4 w-4 shrink-0 text-red-500" />
            </Link>
          </motion.div>
        )}

        {financeOverview?.has_data && unclosedSalesDayCount > 0 && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
            <Link href="/profit" className="flex items-center gap-3 rounded-lg border border-orange-200 bg-orange-50 px-4 py-2.5 transition hover:bg-orange-100/70">
              <ReceiptText className="h-4 w-4 shrink-0 text-orange-700" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-orange-950">财务主动提醒：截至 {financeOverview.last_data_date ?? financeOverview.period_end} 有 {unclosedSalesDayCount} 个销售日尚未关账</p>
                <p className="text-xs text-orange-800">已记录实际到手营业额 ¥{(financeOverview.merchant_net_minor / 100).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}；这不是利润，缺成本或现金实点时不计算真实利润。</p>
              </div>
              <ChevronRight className="h-4 w-4 shrink-0 text-orange-500" />
            </Link>
          </motion.div>
        )}


        <section className="w-full min-w-0 max-w-full text-stone-950">
          <div className="flex flex-col gap-3">
            <div className="flex min-w-0 flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <div className="flex min-w-0 items-center gap-2">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-octo-500 text-white shadow-sm shadow-octo-200/70">
                  <Sparkles className="h-4 w-4" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-stone-950">{storeIdentity.name}</p>
                  <p className="text-[11px] text-stone-500">{storeIdentity.location}</p>
                </div>
              </div>
              <div className="flex min-w-0 max-w-full flex-wrap items-center gap-2">
                <Link
                  href="/calendar"
                  title={weatherTitle}
                  aria-label={`查看天气商圈：${weatherText}`}
                  className="rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
                >
                  <StagePill label="天气" value={weatherText} tone={weatherTone} />
                </Link>
              </div>
            </div>

            <div className="grid w-full min-w-0 grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_280px]">
              <aside className="order-2 hidden flex-col gap-3 xl:flex">
                <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-stone-400">今天</p>
                  <p className="mt-1 text-sm font-semibold text-stone-800">{todayLabel}</p>
                </div>
                <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
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

              <div className="order-1 flex min-w-0 flex-col gap-3">
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4 }}
                  className="w-full min-w-0"
                >
                  <div className="flex items-center gap-3">
                    <h1 className="min-w-0 text-xl font-semibold leading-tight tracking-tight text-slate-950 md:text-2xl">
                      掌柜台 · 每日经营复盘
                    </h1>
                  </div>
                  <div className="mt-3 flex w-full flex-col gap-2 sm:flex-row sm:items-center">
                    <label className="flex min-w-0 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
                      <span className="shrink-0 font-medium">查看日期</span>
                      <input
                        type="date"
                        value={selectedDate}
                        max={today}
                        onChange={(event) => setSelectedDate(event.target.value)}
                        className="min-w-0 bg-transparent font-semibold text-stone-950 outline-none"
                      />
                    </label>
                    <span className="rounded-lg bg-sky-50 px-3 py-2 text-xs text-sky-800">默认查看今天：{today}</span>
                    <span className="rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800">财务事实最新：{latestFinanceDate || "等待财务事实"}</span>
                    {latestOperationDate && latestOperationDate !== latestFinanceDate && <span className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">完整经营日报最新：{latestOperationDate}（不覆盖财务日期）</span>}
                  </div>
                  <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
                    <p className="text-sm font-semibold text-amber-950">经营结论</p>
                    <p className="mt-1 text-sm leading-6 text-amber-900">
                      {financeOverview?.has_data
                        ? `${financeOverview.period_start} 至 ${financeOverview.last_data_date ?? financeOverview.period_end} 已记录实际到手营业额 ¥${(financeOverview.merchant_net_minor / 100).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}，会计营业收入 ¥${(financeOverview.revenue_minor / 100).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}；已完成 ${financeOverview.closed_days}/${knownSalesDayCount} 个销售日关账，成本未闭合前利润和保本额保持待核算。`
                        : "等待第一份营业日报形成收入主账；收入、到账、成本和利润会分开核算。"}
                    </p>
                  </div>
                  <p className="mt-2 text-sm text-stone-500">
                    {hasData && opsSummary
                      ? opsSummary.profit_ready
                        ? `钱账、成本和库存证据已覆盖 ${opsSummary.entry_count} 条台账，今天先看钱在哪里`
                        : `已有销售记录，但利润还缺成本、平台费或库存证据`
                      : "你可以在这里问整家店的问题；涉及钱的记录统一去财务中心记入"}
                  </p>
                </motion.div>

                <StageInputDock
                  input={input}
                  setInput={setInput}
                  isStreaming={isStreaming}
                  isRecording={isRecording}
                  isTranscribing={isTranscribing}
                  voiceMessage={voiceMessage}
                  onSubmit={handleSubmit}
                  onVoice={isRecording ? stopVoiceRecording : startVoiceRecording}
                />

                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: 0.05 }}
                  className="grid gap-3 sm:grid-cols-3"
                >
                  <HeroMetricCard
                    icon={TrendingUp}
                    label="销售事实"
                    value={selectedMerchantNet !== null ? formatCurrency(selectedMerchantNet) : fixtureSales ? formatCurrency(fixtureSales.sales.net_operating_income) : selectedOperation ? formatCurrency(selectedOperation.revenue) : "待录入"}
                    sub={selectedMerchantNet !== null ? `${selectedBusinessDate} 实际到手营业额，不是利润` : "上传客如云或平台销售报表"}
                    tone={hasSelectedLedgerData ? "good" : "watch"}
                    delay={0.05}
                  />
                  <HeroMetricCard
                    icon={Wallet}
                    label="钱在哪里"
                    value={selectedStoreControlled !== null ? formatCurrency(selectedStoreControlled) : "待核对"}
                    sub={selectedStoreControlled !== null ? `${selectedBusinessDate} 截止的店铺可控资金` : "上传到账或转账截图"}
                    tone="watch"
                    delay={0.1}
                  />
                  <HeroMetricCard
                    icon={PackageCheck}
                    label="货能不能卖"
                    value={forecastUrgent.length > 0 ? `${forecastUrgent.length} 项风险` : "暂无紧急"}
                    sub={forecastUrgent[0]
                      ? `${forecastUrgent[0].name} 建议补 ${forecastUrgent[0].recommend_qty ?? "?"}${forecastUrgent[0].unit}`
                      : "库存预测暂未发现紧急断货"}
                    tone={forecastUrgent.length > 0 ? "risk" : "good"}
                    delay={0.15}
                  />
                </motion.div>

                {reviewCheck && (
                  <section className="rounded-2xl border border-stone-200 bg-white/82 p-4 shadow-sm">
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-stone-950">每日经营复盘 · 今日事实是否够用</p>
                        <p className="mt-1 text-xs leading-5 text-stone-500">
                          复盘核心 5 项：营业日报已确认 / 现金已确认 / 第三方收入结算状态已确认 / 无重复入账风险 / 关键库存无低置信度阻断
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${reviewCheck.can_close ? "bg-green-100 text-green-800" : "bg-amber-100 text-amber-800"}`}>
                          {reviewCheck.can_close ? "复盘可用" : reviewCheck.close_status === "partial" ? "部分可复盘" : "缺口待补"}
                        </span>
                        <Link href="/capture" className="rounded-full bg-stone-900 px-3 py-1.5 text-xs font-semibold text-white">去确认</Link>
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 sm:grid-cols-3">
                      <div className="rounded-xl bg-stone-50 px-3 py-2">
                        <p className="text-[11px] text-stone-500">已确认 / 待确认事实</p>
                        <p className="mt-1 text-sm font-semibold text-stone-950">
                          <span className="text-green-600">{reviewCheck.confirmed_facts_count}</span>
                          <span className="text-stone-400"> / </span>
                          <span className="text-amber-600">{reviewCheck.pending_facts_count}</span>
                          <span className="ml-1 text-[11px] text-stone-400">条</span>
                        </p>
                      </div>
                      <div className="rounded-xl bg-stone-50 px-3 py-2">
                        <p className="text-[11px] text-stone-500">已入账 / 重复风险</p>
                        <p className="mt-1 text-sm font-semibold text-stone-950">
                          <span>{reviewCheck.posted_entries_count}</span>
                          <span className="text-stone-400"> 条入账 · </span>
                          <span className={reviewCheck.duplicate_risks_count > 0 ? "text-red-600" : "text-stone-400"}>
                            {reviewCheck.duplicate_risks_count} 重复风险
                          </span>
                        </p>
                      </div>
                      <div className="rounded-xl bg-stone-50 px-3 py-2">
                        <p className="text-[11px] text-stone-500">低置信度库存</p>
                        <p className="mt-1 text-sm font-semibold text-stone-950">
                          <span className={reviewCheck.low_confidence_inventory_count > 0 ? "text-amber-600" : "text-green-600"}>
                            {reviewCheck.low_confidence_inventory_count} 项
                          </span>
                          <span className="ml-1 text-[11px] text-stone-400">
                            {reviewCheck.low_confidence_inventory_count > 0 ? "需老板确认" : "库存口径可靠"}
                          </span>
                        </p>
                      </div>
                    </div>
                    {reviewCheck.blocking_reasons.length > 0 && (
                      <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50/50 p-3">
                        <p className="text-xs font-semibold text-amber-900">复盘缺口</p>
                        <ul className="mt-1.5 space-y-1">
                          {reviewCheck.blocking_reasons.slice(0, 5).map((reason) => (
                            <li key={reason} className="text-[11px] leading-5 text-amber-800">· {reason}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {reviewCheck.next_actions.length > 0 && (
                      <div className="mt-2">
                        <p className="text-[11px] font-medium text-stone-500">下一步老板该确认：</p>
                        <ul className="mt-1 space-y-0.5">
                          {reviewCheck.next_actions.slice(0, 3).map((action) => (
                            <li key={action} className="text-[11px] text-stone-700">→ {action}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </section>
                )}

                {todayCard?.sources && (
                  <section className="rounded-2xl border border-stone-200 bg-white/82 p-4 shadow-sm">
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-stone-950">原始资料与事实证据</p>
                        <p className="mt-1 text-xs leading-5 text-stone-500">保留原始文件并提取候选事实；低置信字段必须确认后才能正式入账。</p>
                      </div>
                      <Link href="/capture" className="shrink-0 rounded-full bg-stone-900 px-3 py-1.5 text-xs font-semibold text-white">去确认事实</Link>
                    </div>
                    <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
                      {todayCard.sources.map((source) => (
                        <p key={source} className="min-w-0 rounded-xl bg-stone-50 px-3 py-2 text-xs leading-5 text-stone-700">{source}</p>
                      ))}
                    </div>
                  </section>
                )}

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

                {fixtureSales && (
                  <section className="grid gap-3 lg:grid-cols-[1.1fr_0.9fr]">
                    <div className="rounded-2xl border border-stone-200 bg-white/82 p-4 shadow-sm">
                      <p className="text-sm font-semibold text-stone-950">客如云营业字段</p>
                      <p className="mt-1 text-xs text-stone-500">来源：已保存客如云营业日报</p>
                      <div className="mt-3 grid gap-2 sm:grid-cols-2">
                        {[
                          ["订单金额", formatCurrency(fixtureSales.sales.order_amount)],
                          ["营业收入", formatCurrency(fixtureSales.sales.net_operating_income)],
                          ["订单数", `${fixtureSales.sales.order_count} 单`],
                          ["销售/退款", `${fixtureSales.sales.sales_orders} / ${fixtureSales.sales.refund_orders}`],
                          ["店内营业收入", formatCurrency(fixtureSales.sales.dine_in_income)],
                          ["第三方营业收入", formatCurrency(fixtureSales.sales.third_party_income)],
                          ["商户优惠", formatCurrency(fixtureSales.deductions.merchant_discount)],
                          ["服务费", formatCurrency(fixtureSales.deductions.service_fee)],
                          ["配送支出", formatCurrency(fixtureSales.deductions.delivery_cost)],
                          ["补贴", formatCurrency(fixtureSales.deductions.subsidy_adjustment)],
                        ].map(([label, value]) => (
                          <div key={label} className="min-w-0 rounded-xl bg-stone-50 px-3 py-2">
                            <p className="text-[11px] text-stone-500">{label}</p>
                            <p className="mt-1 truncate text-sm font-semibold text-stone-950">{value}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-stone-200 bg-white/82 p-4 shadow-sm">
                      <p className="text-sm font-semibold text-stone-950">商品销售</p>
                      <p className="mt-1 text-xs text-stone-500">来源：已保存客如云营业日报</p>
                      <div className="mt-3 space-y-2">
                        {fixtureSales.products.map((item) => (
                          <div key={item.name} className="flex min-w-0 items-center justify-between gap-3 rounded-xl bg-stone-50 px-3 py-2">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-semibold text-stone-900">{item.name}</p>
                              <p className="text-[11px] text-stone-500">{item.quantity} 份</p>
                            </div>
                            <p className="shrink-0 text-sm font-bold text-stone-950">{formatCurrency(item.amount)}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </section>
                )}

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
                      <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${hasSelectedLedgerData ? "bg-nori-50 text-nori-700" : "bg-sauce-50 text-sauce-700"}`}>
                        {hasSelectedLedgerData ? "所选日期已有事实" : "所选日期待录入"}
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
                          <p className="mt-1 text-xs leading-5 text-nori-700">继续补充复盘库存照片和平台结算截图，明天的利润估算会更准。</p>
                        </div>
                      )}
                    </div>
                  </section>
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
          {recognitionStage && (
            <motion.p
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              className="rounded-xl border border-octo-100 bg-octo-50 px-3 py-2 text-xs text-octo-700"
            >
              {recognitionStage === "recognizing" ? "正在识别资料…" : "正在整理候选事实…"}
            </motion.p>
          )}
          {recognitionResult && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              className="rounded-3xl border border-octo-200 bg-white p-4 shadow-sm"
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

        <section className="rounded-3xl border border-stone-200 bg-white/80 p-4 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-stone-950">截至最新资料的经营结论 → 下一步</p>
              <p className="mt-1 text-xs text-stone-500">历史汇总 · 利润拆解 · 渠道 · 库存差异 · 下一步动作</p>
            </div>
            <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${hasSelectedLedgerData ? "bg-nori-50 text-nori-700" : "bg-sauce-50 text-sauce-700"}`}>
              {hasSelectedLedgerData ? "所选日期已有记录" : "所选日期待录入"}
            </span>
          </div>

          {/* 5 步经营决策流摘要 */}
          {hasData && opsSummary && (
            <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-5">
              <DecisionStep
                step="1"
                label="历史经营汇总"
                value={`¥${Math.round(opsSummary.total_original_amount || opsSummary.total_revenue).toLocaleString()}`}
                sub={`${opsSummary.entry_count} 个经营日报 · 实收 ¥${Math.round(opsSummary.total_revenue).toLocaleString()}`}
                tone="info"
                href="/profit"
              />
              <DecisionStep
                step="2"
                label="利润拆解"
                value={opsSummary.profit_ready && opsSummary.net_profit != null ? (opsSummary.net_profit >= 0 ? `+¥${Math.round(opsSummary.net_profit).toLocaleString()}` : `-¥${Math.abs(Math.round(opsSummary.net_profit)).toLocaleString()}`) : "待核算"}
                sub={opsSummary.profit_ready && opsSummary.food_cost_rate != null ? `食材率 ${(opsSummary.food_cost_rate * 100).toFixed(0)}%` : "成本未补齐"}
                tone={opsSummary.profit_ready && opsSummary.net_profit != null ? (opsSummary.net_profit >= 0 ? "good" : "risk") : "watch"}
                href="/profit"
              />
              <DecisionStep
                step="3"
                label="渠道"
                value={opsSummary.takeout_ratio == null ? "待补" : `${(opsSummary.takeout_ratio * 100).toFixed(0)}%`}
                sub="外卖占比"
                tone={opsSummary.takeout_ratio != null && opsSummary.takeout_ratio > 0.45 ? "watch" : "info"}
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

function StagePill({ label, value, tone }: { label: string; value: string; tone: HealthTone }) {
  const color =
    tone === "risk" ? "border-red-200 bg-red-50 text-red-700" :
    tone === "watch" ? "border-sauce-200 bg-sauce-50 text-sauce-800" :
    tone === "good" ? "border-nori-200 bg-nori-50 text-nori-700" :
    "border-sky-200 bg-sky-50 text-sky-700";
  return (
    <span className={`inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] shadow-sm sm:max-w-[220px] ${color}`}>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotToneClass(tone)}`} />
      <span className="shrink-0 text-stone-500">{label}</span>
      <span className="min-w-0 truncate font-medium">{value}</span>
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
      className="group relative overflow-hidden rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition-colors hover:border-cyan-200"
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

function StageInputDock({
  input,
  setInput,
  isStreaming,
  isRecording,
  isTranscribing,
  voiceMessage,
  onSubmit,
  onVoice,
}: {
  input: string;
  setInput: (value: string) => void;
  isStreaming: boolean;
  isRecording: boolean;
  isTranscribing: boolean;
  voiceMessage: string;
  onSubmit: (event: React.FormEvent) => void;
  onVoice: () => void;
}) {
  return (
    <form
      onSubmit={onSubmit}
      id="store-agent-chat"
      className="rounded-lg border border-cyan-200 bg-white p-2 shadow-sm ring-2 ring-cyan-50"
    >
      <div className="flex flex-col gap-2 md:flex-row md:items-center">
        <div className="flex min-w-0 flex-1 items-center gap-3 rounded-md bg-slate-50 px-3 py-1 ring-1 ring-slate-200">
          <span className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-octo-50 text-octo-600 ring-1 ring-octo-100 md:flex">
            <Sparkles className="h-5 w-5" />
          </span>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="问掌柜：今天钱在哪里、哪个渠道最赚、库存还够几天…"
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
          <StageDockButton onClick={onVoice} icon={isTranscribing ? Loader2 : Mic} label={isRecording ? "结束" : "语音"} active={isRecording} />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="ml-auto inline-flex h-11 items-center justify-center gap-2 rounded-md bg-amber-400 px-5 text-sm font-semibold text-slate-950 transition-colors hover:bg-amber-300 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 md:ml-0"
          >
            {isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            发送
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
