"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, Camera, FileText, Loader2, Mic,
  PackageCheck, Send, Sparkles, TrendingDown,
  TrendingUp, Truck, Upload, WalletCards, X,
  type LucideIcon,
} from "lucide-react";
import { storeIdentity, type HealthTone } from "@/data/agent-store-os";
import { departmentAgents } from "@/data/mock-agents";
import {
  DEFAULT_PROJECT_ID, addOperation, recognizeCapture,
  getForecast, getOperationSummary, getWageSummary, getStaff, getOperations, getWeather,
  type DailyOperationEntry, type ForecastItem, type WeatherResponse,
} from "@/lib/api";
import { useAIChat } from "@/lib/hooks/useAIChat";
import { parseOperationDraft, toDateInputValue, type OperationDraft } from "@/lib/operationDraft";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import NumberFlow from "@number-flow/react";

type SourceType = "客如云" | "美团" | "抖音" | "淘宝闪购" | "进货单" | "库存照片" | "SOP资料" | "水电费用" | "未知资料";
type WorkStatus = "待确认" | "分析中" | "已入库";
type IntakeItem = { id: string; name: string; source: SourceType; status: WorkStatus; summary: string };

const sourceMeta: Record<SourceType, { icon: LucideIcon; color: string; action: string }> = {
  客如云: { icon: FileText, color: "bg-emerald-100 text-emerald-700", action: "提取营业额、订单、商品销量、客单价" },
  美团: { icon: Truck, color: "bg-yellow-100 text-yellow-800", action: "拆佣金、满减、退款和到手利润" },
  抖音: { icon: Sparkles, color: "bg-rose-100 text-rose-700", action: "核对核销、套餐和活动效果" },
  淘宝闪购: { icon: Truck, color: "bg-blue-100 text-blue-700", action: "拆外卖收入、佣金和退款" },
  进货单: { icon: PackageCheck, color: "bg-indigo-100 text-indigo-700", action: "更新批次、单价、安全库存" },
  库存照片: { icon: FileText, color: "bg-cyan-100 text-cyan-700", action: "估算剩余、断货风险和备料" },
  SOP资料: { icon: FileText, color: "bg-purple-100 text-purple-700", action: "转成作业标准和训练卡" },
  水电费用: { icon: WalletCards, color: "bg-orange-100 text-orange-700", action: "补固定成本和保本线" },
  未知资料: { icon: FileText, color: "bg-slate-100 text-slate-700", action: "先识别来源，再分派" },
};

const shortcuts = [
  { label: "今天赚没赚", prompt: "根据今天已录入的数据，直接告诉我今天赚没赚，哪里漏钱。" },
  { label: "缺什么数据", prompt: "现在要算清楚利润，还缺哪些关键数据？" },
  { label: "打烊总结", prompt: "按老板能懂的话生成今天打烊总结和明天三件事。" },
  { label: "明天备多少", prompt: "结合已录入的销量和库存，帮我判断明天备料风险。" },
];

export default function OverviewPage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const { messages, isStreaming, sendMessage } = useAIChat();
  const [input, setInput] = useState("");
  const [intakeItems, setIntakeItems] = useState<IntakeItem[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [noteInput, setNoteInput] = useState("");
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [operationDraft, setOperationDraft] = useState<OperationDraft | null>(null);
  const [draftEntry, setDraftEntry] = useState<DailyOperationEntry | null>(null);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [draftSourceItemId, setDraftSourceItemId] = useState<string | null>(null);

  // 实时数据
  const [opsSummary, setOpsSummary] = useState<{ total_revenue: number; net_profit: number; entry_count: number; total_orders: number; food_cost_rate: number; labor_cost_rate?: number; takeout_ratio: number } | null>(null);
  const [forecastUrgent, setForecastUrgent] = useState<ForecastItem[]>([]);
  const [staffCount, setStaffCount] = useState(0);
  const [monthWage, setMonthWage] = useState(0);
  const [dailyTrend, setDailyTrend] = useState<{ date: string; 营收: number }[]>([]);
  const [weather, setWeather] = useState<WeatherResponse | null>(null);

  const confirmedCount = intakeItems.filter((item) => item.status === "已入库").length;
  const knownSourceCount = intakeItems.filter((item) => item.source !== "未知资料").length;
  const pendingCount = intakeItems.filter((item) => item.status === "待确认" || item.status === "分析中").length;

  const fetchLiveData = useCallback(async () => {
    try {
      const [ops, fRes, staffRes, opsList] = await Promise.all([
        getOperationSummary(DEFAULT_PROJECT_ID, 7),
        getForecast(DEFAULT_PROJECT_ID),
        getStaff(DEFAULT_PROJECT_ID),
        getOperations(DEFAULT_PROJECT_ID, 7),
      ]);
      setOpsSummary(ops);
      setForecastUrgent(fRes.forecast.filter((f) => f.action === "urgent" || f.action === "recommend").slice(0, 3));
      setStaffCount(staffRes.staff.filter((s) => s.status === "在岗").length);
      setDailyTrend(opsList.entries.slice(-7).map((e) => ({ date: e.date.slice(5), 营收: e.revenue })));

      if (staffRes.staff.length > 0) {
        const now = new Date();
        const ym = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
        try {
          const wage = await getWageSummary(DEFAULT_PROJECT_ID, ym);
          setMonthWage(wage.total_wage);
        } catch { /* no wage data yet */ }
      }
    } catch { /* offline */ }
    // 天气独立拉取（不阻塞主数据）
    try { const w = await getWeather(); setWeather(w); } catch { /* */ }
  }, []);

  useEffect(() => { fetchLiveData(); }, [fetchLiveData]);

  const handleSubmit = useCallback((event: React.FormEvent) => {
    event.preventDefault();
    const value = input.trim();
    if (!value) return;
    const draft = parseOperationDraft(value);
    if (draft) {
      setOperationDraft(draft);
      setDraftEntry(draft.entry);
      setDraftError(null);
      return;
    }
    sendMessage(value);
    setInput("");
  }, [input, sendMessage]);

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

  const registerFile = useCallback(async (file: File, sourceLabel: string) => {
    const source = classifyFile(file.name);
    const itemId = `${file.name}-${Date.now()}`;
    const item: IntakeItem = { id: itemId, name: file.name, source, status: "分析中", summary: "正在识别图片中的经营数据..." };
    setIntakeItems((prev) => [item, ...prev]);
    try {
      const result = await recognizeCapture(file);
      if (result.parse_error) {
        setIntakeItems((prev) => prev.map((e) => e.id === itemId ? { ...e, status: "待确认", summary: result.parse_error || "识别不完整" } : e));
        setInput(`${result.raw_text || file.name}\n\n以上是图片识别结果，请帮我整理成经营数据。`);
        return;
      }
      const entry: DailyOperationEntry = {
        date: toDateInputValue(new Date()),
        revenue: 0, orders: 0, food_cost: 0, labor: 0, rent_allocated: 0, utility: 0, other_cost: 0,
        takeout_orders: 0, platform_fee: 0, marketing_cost: 0, inventory_loss: 0, bad_reviews: 0, notes: "",
      };
      for (const field of result.fields) {
        const key = field.key as keyof DailyOperationEntry;
        if (key in entry) (entry as unknown as Record<string, unknown>)[key] = field.value;
      }
      setIntakeItems((prev) => prev.map((e) => e.id === itemId ? { ...e, status: "待确认", summary: `识别到 ${result.fields.length} 个字段` } : e));
      setDraftSourceItemId(itemId);
      setOperationDraft({ source: `${sourceLabel}: ${file.name}`, entry, fields: result.fields.map((f) => ({ key: f.key as keyof DailyOperationEntry, label: f.label, value: f.value, confidence: f.confidence === "low" ? "medium" : f.confidence })), missing: [], confidence: result.fields.length >= 3 ? "high" : "medium" });
      setDraftEntry(entry);
      setDraftError(null);
    } catch (err) {
      setIntakeItems((prev) => prev.map((e) => e.id === itemId ? { ...e, status: "待确认", summary: err instanceof Error ? err.message : "识别请求失败" } : e));
    }
  }, [classifyFile]);

  const handleFileChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; if (!file) return; registerFile(file, "电脑上传");
  }, [registerFile]);

  const handlePaste = useCallback((event: React.ClipboardEvent<HTMLFormElement>) => {
    const imageItem = Array.from(event.clipboardData.items).find((item) => item.type.startsWith("image/"));
    const file = imageItem?.getAsFile(); if (!file) return;
    registerFile(new File([file], `粘贴截图-${Date.now()}.png`, { type: file.type }), "粘贴截图");
  }, [registerFile]);

  const handleDrop = useCallback((event: React.DragEvent<HTMLFormElement>) => {
    event.preventDefault();
    const file = Array.from(event.dataTransfer.files).find((item) => item.type.startsWith("image/"));
    if (!file) return; registerFile(file, "拖拽图片");
  }, [registerFile]);

  const closeCamera = useCallback(() => {
    cameraStreamRef.current?.getTracks().forEach((track) => track.stop());
    cameraStreamRef.current = null; setIsCameraOpen(false);
  }, []);

  const openCamera = useCallback(async () => {
    setCameraError(null);
    if (!navigator.mediaDevices?.getUserMedia) { setCameraError("不支持摄像头"); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      cameraStreamRef.current = stream; setIsCameraOpen(true);
      requestAnimationFrame(() => { if (videoRef.current) { videoRef.current.srcObject = stream; void videoRef.current.play(); } });
    } catch { setCameraError("没有摄像头权限，可以用选择图片或粘贴截图。"); }
  }, []);

  const takeCameraPhoto = useCallback(() => {
    const video = videoRef.current;
    if (!video || video.videoWidth === 0) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d"); if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => { if (blob) { registerFile(new File([blob], `电脑拍照-${Date.now()}.jpg`, { type: "image/jpeg" }), "Mac 摄像头拍照"); closeCamera(); } }, "image/jpeg", 0.92);
  }, [closeCamera, registerFile]);

  useEffect(() => closeCamera, [closeCamera]);

  const handleConfirmDraft = useCallback(async () => {
    if (!draftEntry) return;
    setIsSavingDraft(true); setDraftError(null);
    try {
      await addOperation(draftEntry, DEFAULT_PROJECT_ID);
      await queryClient.invalidateQueries({ queryKey: ["project", DEFAULT_PROJECT_ID] });
      if (draftSourceItemId) { setIntakeItems((prev) => prev.map((e) => e.id === draftSourceItemId ? { ...e, status: "已入库" } : e)); setDraftSourceItemId(null); }
      setOperationDraft(null); setDraftEntry(null); setInput("");
      fetchLiveData();
    } catch (err) { setDraftError(err instanceof Error ? err.message : "写入失败"); }
    finally { setIsSavingDraft(false); }
  }, [draftEntry, queryClient, draftSourceItemId, fetchLiveData]);

  const addNote = useCallback(() => {
    const value = noteInput.trim(); if (!value) return;
    setNotes((prev) => [value, ...prev]); setNoteInput("");
  }, [noteInput]);

  const hasData = opsSummary && opsSummary.entry_count > 0;
  const today = new Date().toISOString().slice(0, 10);

  return (
    <>
      <main className="mx-auto flex h-[calc(100vh-56px)] w-full max-w-7xl flex-col gap-3 overflow-hidden px-2 pt-2">
        {/* ── 顶部：状态 + 核心指标 ── */}
        <header className="flex flex-wrap items-center justify-between gap-2 px-1">
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/55 bg-white/45 px-2.5 py-0.5 text-xs font-medium text-on-surface-variant">
              <span className="h-2 w-2 rounded-full bg-emerald-400 status-pulse" />掌柜在线
            </span>
            <span className="text-xs text-on-surface-variant">{storeIdentity.location}</span>
            <span className="text-xs text-on-surface-variant">{today}</span>
          </div>
          <span className="text-lg font-semibold text-on-background">大口章鱼烧·总控台</span>
        </header>

        {/* ── 核心指标行 ── */}
        <div className="grid grid-cols-5 gap-2">
          <KpiCard label="近7天营收" value={hasData ? `¥${(opsSummary!.total_revenue / 1000).toFixed(1)}k` : "待录入"} sub={hasData ? `${opsSummary!.entry_count}天` : "先入库"} tone={hasData ? "good" : "watch"} numeric={hasData ? Math.round(opsSummary!.total_revenue) : undefined} prefix="¥" />
          <KpiCard label="净利" value={hasData && opsSummary!.entry_count >= 3 ? (opsSummary!.net_profit >= 0 ? `¥${(opsSummary!.net_profit / 1000).toFixed(1)}k` : "亏") : "不足3天"} sub={hasData ? `食材${(opsSummary!.food_cost_rate * 100).toFixed(0)}%` : "-"} tone={hasData && opsSummary!.net_profit > 0 ? "good" : hasData && opsSummary!.net_profit < 0 ? "risk" : "watch"} numeric={hasData ? Math.round(opsSummary!.net_profit) : undefined} prefix="¥" />
          <KpiCard label="库存预警" value={forecastUrgent.length > 0 ? `${forecastUrgent.length}项` : "正常"} sub={forecastUrgent.length > 0 ? forecastUrgent[0]?.name.slice(0, 4) : "无断货风险"} tone={forecastUrgent.length > 0 ? "risk" : "good"} numeric={forecastUrgent.length} suffix="项" />
          <KpiCard label="员工" value={`${staffCount}人`} sub={monthWage > 0 ? `月薪¥${(monthWage / 1000).toFixed(1)}k` : "待录考勤"} tone={staffCount > 0 ? "good" : "watch"} numeric={staffCount} suffix="人" />
          <KpiCard label="渠道外卖" value={hasData ? `${(opsSummary!.takeout_ratio * 100).toFixed(0)}%` : "-"} sub={hasData ? `占${opsSummary!.total_orders || 0}单` : "待录入"} tone={hasData && opsSummary!.takeout_ratio > 0.45 ? "watch" : "info"} />
        </div>

        {/* ── 快捷日报录入 ── */}
        <QuickDailyEntry onSaved={fetchLiveData} />

        {/* ── 中区：经营详情 + 右侧面板 ── */}
        <div className="grid min-h-0 flex-1 gap-3 xl:grid-cols-[1fr_340px]">
          {/* 左侧：经营明细 + 资料摄入 */}

          <div className="flex min-h-0 flex-col gap-3 overflow-hidden">
            {/* 经营快照 */}
            <div className="grid grid-cols-3 gap-2">
              <Link href="/sales" className="rounded-2xl border border-white/45 bg-white/42 px-3 py-2.5 hover:border-primary/35 hover:bg-white/65">
                <p className="text-xs font-medium text-on-surface-variant">营业走势</p>
                {dailyTrend.length >= 3 ? (
                  <div className="mt-1 h-10">
                    <ResponsiveContainer>
                      <AreaChart data={dailyTrend}>
                        <defs>
                          <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#0F4C3A" stopOpacity={0.3} />
                            <stop offset="100%" stopColor="#0F4C3A" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <Area type="monotone" dataKey="营收" stroke="#0F4C3A" strokeWidth={1.5} fill="url(#sparkGrad)" dot={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <p className="mt-1 font-semibold text-on-background">{hasData ? `${opsSummary!.entry_count}天` : "待录入"}</p>
                )}
              </Link>
              <Link href="/inventory" className="rounded-2xl border border-white/45 bg-white/42 px-3 py-2.5 hover:border-primary/35 hover:bg-white/65">
                <p className="text-xs font-medium text-on-surface-variant">补货预测</p>
                <p className="mt-1 font-semibold text-on-background">{forecastUrgent.length > 0 ? `${forecastUrgent.length}项待补` : "库存正常"}</p>
              </Link>
              <Link href="/profit" className="rounded-2xl border border-white/45 bg-white/42 px-3 py-2.5 hover:border-primary/35 hover:bg-white/65">
                <p className="text-xs font-medium text-on-surface-variant">利润保本</p>
                <p className="mt-1 font-semibold text-on-background">{hasData ? `${(opsSummary!.food_cost_rate * 100).toFixed(0)}%·${((opsSummary!.labor_cost_rate ?? 0) * 100).toFixed(0)}%` : "缺成本"}</p>
              </Link>
            </div>

            {/* Chat / 资料摄入区 */}
            <div className="flex min-h-0 flex-1 flex-col rounded-2xl border border-white/45 bg-white/42">
              <div className="min-h-0 flex-1 overflow-y-auto p-3">
                {messages.length > 0 ? (
                  messages.map((message) => (
                    <div key={message.id} className={`mb-2 max-w-[88%] rounded-2xl border p-2.5 text-sm ${message.role === "user" ? "ml-auto border-white/50 bg-white/70 text-on-background" : "border-primary/20 bg-primary-container/45"}`}>
                      <p className="text-[10px] font-medium text-on-surface-variant">{message.role === "user" ? "你" : "掌柜"}</p>
                      <p className="mt-1 whitespace-pre-wrap">{message.content || "..."}</p>
                    </div>
                  ))
                ) : (
                  <div className="flex h-full items-center justify-center">
                    <div className="text-center">
                      <p className="text-lg font-semibold text-on-background">今天店里怎么跑？</p>
                      <p className="mt-1 text-xs text-on-surface-variant">
                        {hasData
                          ? `近7天营收¥${(opsSummary!.total_revenue / 1000).toFixed(1)}k，净利¥${(opsSummary!.net_profit / 1000).toFixed(1)}k。问打烊总结试试。`
                          : "说话或粘贴截图开始。数字会先进待确认，确认后入库。"}
                      </p>
                    </div>
                  </div>
                )}
              </div>

              <form onSubmit={handleSubmit} onPaste={handlePaste} onDrop={handleDrop} onDragOver={(e) => e.preventDefault()} className="border-t border-white/45 p-2.5">
                <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
                <div className="flex items-end gap-2">
                  <textarea
                    value={input} onChange={(e) => setInput(e.target.value)}
                    placeholder="说句话、粘贴截图，或输入：今天流水912 订单38..."
                    className="min-h-10 max-h-20 flex-1 resize-none rounded-2xl border border-white/50 bg-white/60 px-3 py-2 text-sm text-on-background outline-none placeholder:text-on-surface-variant/50 focus:border-primary/50"
                    rows={1}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(e as unknown as React.FormEvent); } }}
                  />
                  <div className="flex gap-1">
                    <button type="button" onClick={() => fileInputRef.current?.click()} className="rounded-full bg-white/55 p-2 text-on-surface-variant hover:bg-white/80 hover:text-on-background" title="上传截图"><Upload className="h-4 w-4" /></button>
                    <button type="button" onClick={openCamera} className="rounded-full bg-white/55 p-2 text-on-surface-variant hover:bg-white/80 hover:text-on-background" title="拍照"><Camera className="h-4 w-4" /></button>
                    <button type="submit" disabled={!input.trim() || isStreaming} className="rounded-full bg-primary p-2 text-primary-foreground shadow-lg shadow-primary/20 disabled:opacity-40">
                      {isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    </button>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {shortcuts.map((item) => (
                    <button key={item.label} type="button" onClick={() => setInput(item.prompt)} className="rounded-full bg-white/45 px-2.5 py-1 text-[11px] text-on-surface-variant hover:bg-white/75 hover:text-on-background">{item.label}</button>
                  ))}
                </div>
              </form>
            </div>
          </div>

          {/* 右侧面板：待确认 + 情报 + 运行 + 待办 */}
          <aside className="flex min-h-0 flex-col gap-2 overflow-y-auto">
            {/* 待确认 */}
            <div className="rounded-2xl border border-white/45 bg-white/42 p-3">
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium text-on-surface-variant">待确认</p>
                <span className="rounded-full bg-white/55 px-2 py-0.5 text-[10px] text-on-surface-variant">{pendingCount}条</span>
              </div>
              {intakeItems.length > 0 ? (
                <div className="mt-2 space-y-1.5 max-h-32 overflow-y-auto">
                  {intakeItems.slice(0, 3).map((item) => (
                    <div key={item.id} className={`rounded-xl border px-2.5 py-2 text-xs ${item.status === "待确认" ? "border-amber-300 bg-amber-50/80" : "border-white/45 bg-white/45"}`}>
                      <p className="truncate font-medium text-on-background">{item.name}</p>
                      <p className="mt-0.5 text-[10px] text-on-surface-variant">{item.source} · {item.status}</p>
                    </div>
                  ))}
                  {intakeItems.length > 3 && <p className="text-[10px] text-on-surface-variant text-center">还有 {intakeItems.length - 3} 条...</p>}
                </div>
              ) : (
                <p className="mt-2 text-[11px] text-on-surface-variant">暂无待确认资料</p>
              )}
            </div>

            {/* 情报简报 */}
            <div className="rounded-2xl border border-white/45 bg-white/42 p-3">
              <p className="text-xs font-medium text-on-surface-variant">情报简报</p>
              <div className="mt-2 space-y-1.5">
                <Link href="/calendar" className="flex items-center justify-between rounded-xl bg-white/45 px-2.5 py-1.5 text-xs hover:bg-white/65">
                  <span className="text-on-background">天气商圈</span>
                  <span className="text-on-surface-variant">
                    {weather
                      ? weather.current.weather === "light_rain" || weather.current.weather === "heavy_rain"
                        ? `${weather.forecast[1]?.weekday || "明日"}有雨`
                        : weather.current.temperature > 35
                        ? `${weather.current.temperature}° 高温`
                        : `${weather.forecast[0]?.weather ? { sunny: "晴", cloudy: "多云", overcast: "阴", light_rain: "小雨", heavy_rain: "大雨", thunderstorm: "雷阵雨", snow: "雪", fog: "雾" }[weather.forecast[0]?.weather] || "天气" : "天气"} ${weather.current.temperature}°`
                      : "加载中..."}
                  </span>
                </Link>
                <Link href="/capture" className="flex items-center justify-between rounded-xl bg-red-50/60 px-2.5 py-1.5 text-xs">
                  <span className="font-medium text-red-700">证据缺口</span>
                  <span className="text-red-600">{opsSummary ? `${3 - (opsSummary.entry_count >= 30 ? 3 : Math.min(opsSummary.entry_count, 3))}项待补` : "3项待补"}</span>
                </Link>
                <Link href="/reports" className="flex items-center justify-between rounded-xl bg-white/45 px-2.5 py-1.5 text-xs hover:bg-white/65">
                  <span className="text-on-background">周报月报</span>
                  <span className="text-on-surface-variant">{opsSummary && opsSummary.entry_count >= 7 ? "可生成" : "数据不足"}</span>
                </Link>
              </div>
            </div>

            {/* 运行队列 */}
            <div className="rounded-2xl border border-white/45 bg-white/42 p-3">
              <p className="text-xs font-medium text-on-surface-variant">线上员工</p>
              <div className="mt-2 space-y-1">
                {departmentAgents.map((agent) => (
                  <div key={agent.id} className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-white/55 transition-colors">
                    <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${
                      agent.status === "running" ? "bg-emerald-400 status-pulse" :
                      agent.status === "blocked" ? "bg-red-400" :
                      agent.status === "done" ? "bg-sky-400" : "bg-slate-300"
                    }`} />
                    <span className="text-xs font-medium text-on-background min-w-0">{agent.name}</span>
                    <span className="text-[9px] text-on-surface-variant ml-auto shrink-0">
                      {agent.status === "running" ? "工作中" :
                       agent.status === "blocked" ? "缺数据" :
                       agent.status === "done" ? "已完成" : "待命中"}
                    </span>
                    {agent.passTo && (
                      <span className="text-[8px] text-primary-fixed/60 font-mono shrink-0 hidden md:inline">→ {agent.passTo}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* 待办 */}
            <div className="flex-1 rounded-2xl border border-white/45 bg-white/42 p-3">
              <p className="text-xs font-medium text-on-surface-variant">老板待办</p>
              <div className="mt-2 flex gap-1">
                <input value={noteInput} onChange={(e) => setNoteInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") addNote(); }} placeholder="加一条..." className="min-w-0 flex-1 rounded-xl border border-white/50 bg-white/55 px-2.5 py-1 text-xs outline-none focus:border-primary/50" />
                <button type="button" onClick={addNote} className="rounded-xl bg-on-background px-2.5 py-1 text-[11px] font-medium text-inverse-on-surface shrink-0">加</button>
              </div>
              <div className="mt-2 space-y-1 overflow-y-auto">
                {notes.length > 0 ? notes.map((note) => (
                  <div key={note} className="flex items-center justify-between rounded-lg bg-white/45 px-2 py-1.5 text-xs text-on-background">
                    <span className="truncate">{note}</span>
                    <button onClick={() => setNotes((prev) => prev.filter((n) => n !== note))} className="ml-1 shrink-0 text-on-surface-variant/60 hover:text-on-background">&times;</button>
                  </div>
                )) : (
                  <p className="text-[10px] text-on-surface-variant">暂无待办</p>
                )}
              </div>
            </div>
          </aside>
        </div>
      </main>

      {cameraError && (
        <div className="fixed bottom-20 left-1/2 z-50 -translate-x-1/2 rounded-2xl bg-red-100 px-4 py-2 text-xs text-red-700 shadow-lg">{cameraError}</div>
      )}

      {operationDraft && draftEntry && (
        <DraftModal draftEntry={draftEntry} draftError={draftError} isSavingDraft={isSavingDraft}
          onClose={() => { setOperationDraft(null); setDraftSourceItemId(null); }}
          onSendAsChat={() => { if (operationDraft) sendMessage(operationDraft.source); setOperationDraft(null); setDraftSourceItemId(null); setInput(""); }}
          onConfirm={handleConfirmDraft}
          onChange={(key, value) => setDraftEntry((prev) => prev ? { ...prev, [key]: key === "date" || key === "notes" ? value : Number(value) || 0 } : prev)} />
      )}

      {isCameraOpen && (
        <div className="fixed inset-0 z-70 flex items-end justify-center bg-background/70 px-4 pb-4 backdrop-blur-md md:items-center">
          <div className="w-full max-w-lg rounded-2xl border border-white/45 bg-white/80 p-3 shadow-2xl">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-on-background">电脑拍照</p>
              <button onClick={closeCamera} className="rounded-full p-1.5 text-on-surface-variant hover:bg-white/60"><X className="h-4 w-4" /></button>
            </div>
            <video ref={videoRef} className="mt-2 aspect-video w-full rounded-xl bg-black object-cover" playsInline muted />
            <div className="mt-3 flex justify-end gap-2">
              <button onClick={closeCamera} className="rounded-full border border-muted-border/40 px-3 py-1.5 text-xs text-on-surface-variant">取消</button>
              <button onClick={takeCameraPhoto} className="rounded-full bg-on-background px-3 py-1.5 text-xs font-semibold text-inverse-on-surface">拍下</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function QuickDailyEntry({ onSaved }: { onSaved: () => void }) {
  const queryClient = useQueryClient();
  const today = new Date().toISOString().slice(0, 10);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ date: today, revenue: "", orders: "", takeout_orders: "", food_cost: "", labor: "", platform_fee: "" });

  const handleSave = useCallback(async () => {
    const entry: DailyOperationEntry = {
      date: form.date, revenue: Number(form.revenue) || 0, orders: Number(form.orders) || 0,
      food_cost: Number(form.food_cost) || 0, labor: Number(form.labor) || 0,
      rent_allocated: 0, utility: 0, other_cost: 0,
      takeout_orders: Number(form.takeout_orders) || 0,
      platform_fee: Number(form.platform_fee) || 0,
      marketing_cost: 0, inventory_loss: 0, bad_reviews: 0, notes: "",
    };
    if (entry.revenue === 0 && entry.orders === 0) return;
    setSaving(true);
    try {
      await addOperation(entry, DEFAULT_PROJECT_ID);
      await queryClient.invalidateQueries({ queryKey: ["project", DEFAULT_PROJECT_ID] });
      await queryClient.invalidateQueries({ queryKey: ["operations", DEFAULT_PROJECT_ID] });
      await queryClient.invalidateQueries({ queryKey: ["cockpit", DEFAULT_PROJECT_ID] });
      setOpen(false);
      setForm({ date: today, revenue: "", orders: "", takeout_orders: "", food_cost: "", labor: "", platform_fee: "" });
      onSaved();
    } catch { /* */ }
    setSaving(false);
  }, [form, queryClient, onSaved, today]);

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="flex items-center justify-center gap-2 rounded-2xl border border-dashed border-primary/30 bg-primary-container/10 py-1.5 text-xs font-medium text-primary hover:border-primary/50 hover:bg-primary-container/20 transition-colors">
        + 录入今日日报
      </button>
    );
  }

  return (
    <div className="rounded-2xl border border-primary/30 bg-primary-container/8 p-3">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-medium text-on-surface-variant">快捷录入日报</p>
        <button onClick={() => setOpen(false)} className="text-on-surface-variant hover:text-on-background text-xs">&times;</button>
      </div>
      <div className="grid grid-cols-4 gap-1.5 md:grid-cols-7">
        <QuickField label="日期" value={form.date} onChange={(v) => setForm((p) => ({ ...p, date: v }))} type="date" />
        <QuickField label="营收" value={form.revenue} onChange={(v) => setForm((p) => ({ ...p, revenue: v }))} placeholder="¥" />
        <QuickField label="订单" value={form.orders} onChange={(v) => setForm((p) => ({ ...p, orders: v }))} placeholder="单" />
        <QuickField label="外卖单" value={form.takeout_orders} onChange={(v) => setForm((p) => ({ ...p, takeout_orders: v }))} placeholder="单" />
        <QuickField label="食材成本" value={form.food_cost} onChange={(v) => setForm((p) => ({ ...p, food_cost: v }))} placeholder="¥" />
        <QuickField label="人工" value={form.labor} onChange={(v) => setForm((p) => ({ ...p, labor: v }))} placeholder="¥" />
        <QuickField label="平台费" value={form.platform_fee} onChange={(v) => setForm((p) => ({ ...p, platform_fee: v }))} placeholder="¥" />
      </div>
      <button type="button" onClick={handleSave} disabled={saving} className="mt-2 w-full rounded-xl bg-primary py-1.5 text-xs font-semibold text-on-primary disabled:opacity-50">
        {saving ? "写入中..." : "写入今日日报"}
      </button>
    </div>
  );
}

function QuickField({ label, value, onChange, type = "number", placeholder = "" }: { label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string }) {
  return (
    <label className="min-w-0">
      <span className="text-[9px] text-on-surface-variant">{label}</span>
      <input type={type} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} className="mt-0.5 w-full rounded-lg border border-white/50 bg-white/60 px-1.5 py-1 text-[11px] text-on-background outline-none focus:border-primary/50" />
    </label>
  );
}

function KpiCard({ label, value, sub, tone, numeric, prefix = "", suffix = "" }: { label: string; value: string; sub: string; tone: HealthTone; numeric?: number; prefix?: string; suffix?: string }) {
  const dotCls = tone === "good" ? "bg-emerald-400" : tone === "risk" ? "bg-red-400" : tone === "watch" ? "bg-amber-400" : "bg-blue-400";
  return (
    <div className="rounded-2xl border border-white/40 bg-white/38 px-3 py-2.5 backdrop-blur-xl">
      <p className="text-[10px] font-medium text-on-surface-variant">{label}</p>
      <p className="mt-0.5 text-lg font-bold text-on-background tabular-nums">
        {numeric != null ? <NumberFlow value={numeric} format={{ style: "decimal", minimumFractionDigits: 0 }} prefix={prefix} suffix={suffix} /> : value}
      </p>
      <div className="mt-0.5 flex items-center gap-1">
        <span className={`h-1.5 w-1.5 rounded-full ${dotCls}`} />
        <p className="text-[10px] text-on-surface-variant">{sub}</p>
      </div>
    </div>
  );
}

function DraftModal({ draftEntry, draftError, isSavingDraft, onClose, onSendAsChat, onConfirm, onChange }: {
  draftEntry: DailyOperationEntry;
  draftError: string | null;
  isSavingDraft: boolean;
  onClose: () => void;
  onSendAsChat: () => void;
  onConfirm: () => void;
  onChange: (key: keyof DailyOperationEntry, value: string) => void;
}) {
  return (
    <div className="fixed inset-0 z-60 flex items-end justify-center bg-background/60 px-4 pb-4 backdrop-blur-sm md:items-center">
      <div className="w-full max-w-xl rounded-2xl border border-white/45 bg-white/80 p-4 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <div><p className="text-xs font-medium text-on-surface-variant">经营数据草稿</p><h2 className="mt-1 text-base font-semibold text-on-background">确认后写入模型</h2></div>
          <button onClick={onClose} className="rounded-full p-1.5 text-on-surface-variant hover:bg-white/60"><X className="h-4 w-4" /></button>
        </div>
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
        {draftError && <p className="mt-2 rounded-xl bg-red-100 px-3 py-1.5 text-xs text-red-700">{draftError}</p>}
        <div className="mt-3 flex justify-end gap-2">
          <button onClick={onSendAsChat} className="rounded-full border border-muted-border/40 px-3 py-1.5 text-xs text-on-surface-variant">只当聊天</button>
          <button onClick={onConfirm} disabled={isSavingDraft} className="rounded-full bg-primary px-3 py-1.5 text-xs font-semibold text-on-primary disabled:opacity-50">{isSavingDraft ? "写入中..." : "确认写入"}</button>
        </div>
      </div>
    </div>
  );
}

function DraftInput({ label, value, onChange, type = "number" }: { label: string; value: string | number; onChange: (value: string) => void; type?: "number" | "date" }) {
  return (
    <label className="min-w-0">
      <span className="text-[10px] text-on-surface-variant">{label}</span>
      <input type={type} value={value} min={type === "number" ? 0 : undefined} onChange={(e) => onChange(e.target.value)} className="mt-0.5 w-full rounded-xl border border-white/50 bg-white/55 px-2 py-1.5 text-xs text-on-background outline-none focus:border-primary/50" />
    </label>
  );
}
