"use client";

import { useCallback, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle, ArrowRight, CheckCircle2,
  ClipboardList, Package, PenLine, Timer, XCircle,
} from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";

interface StepState {
  label: string;
  subtitle: string;
  count: number;
  icon: typeof ClipboardList;
  color: string;
  bgColor: string;
}

interface ExceptionNote {
  id: string;
  text: string;
  time: string;
}

const INITIAL_STEPS: StepState[] = [
  { label: "未做", subtitle: "新进订单", count: 3, icon: ClipboardList, color: "text-slate-500", bgColor: "bg-slate-50" },
  { label: "正在做", subtitle: "制作中", count: 2, icon: Timer, color: "text-amber-500", bgColor: "bg-amber-50" },
  { label: "待加料", subtitle: "加酱/木鱼花", count: 1, icon: PenLine, color: "text-sky-500", bgColor: "bg-sky-50" },
  { label: "待打包", subtitle: "装盒/封口", count: 2, icon: Package, color: "text-emerald-500", bgColor: "bg-emerald-50" },
  { label: "待核销", subtitle: "平台确认", count: 1, icon: CheckCircle2, color: "text-violet-500", bgColor: "bg-violet-50" },
  { label: "异常单", subtitle: "错单/退单", count: 0, icon: XCircle, color: "text-red-500", bgColor: "bg-red-50" },
];

export default function WorkflowPage() {
  const [steps, setSteps] = useState<StepState[]>(INITIAL_STEPS);
  const [exceptions, setExceptions] = useState<ExceptionNote[]>([]);
  const [showAddException, setShowAddException] = useState(false);
  const [exceptionText, setExceptionText] = useState("");
  const [exceptionForStep, setExceptionForStep] = useState<number | null>(null);

  const moveStep = useCallback((fromIndex: number, toIndex: number) => {
    if (fromIndex === toIndex) return;
    setSteps((prev) => {
      const next = [...prev];
      if (next[fromIndex].count <= 0) return prev;
      next[fromIndex] = { ...next[fromIndex], count: next[fromIndex].count - 1 };
      next[toIndex] = { ...next[toIndex], count: next[toIndex].count + 1 };
      return next;
    });

    // 如果移到异常单，弹出原因输入
    if (toIndex === 5) {
      setExceptionForStep(fromIndex);
      setShowAddException(true);
    }
  }, []);

  const adjustCount = useCallback((index: number, delta: number) => {
    setSteps((prev) => {
      const next = [...prev];
      const newCount = Math.max(0, next[index].count + delta);
      next[index] = { ...next[index], count: newCount };
      return next;
    });
  }, []);

  const addException = useCallback(() => {
    if (!exceptionText.trim()) return;
    setExceptions((prev) => [
      { id: `ex-${Date.now()}`, text: exceptionText.trim(), time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) },
      ...prev,
    ]);
    setExceptionText("");
    setShowAddException(false);
    setExceptionForStep(null);
  }, [exceptionText]);

  const removeException = useCallback((id: string) => {
    setExceptions((prev) => prev.filter((e) => e.id !== id));
  }, []);

  const currentModule = getModule("/workflow");

  return (
    <ModulePage module={currentModule}>
      <div className="space-y-4">

        {/* ── 动线导览 ── */}
        <div className="rounded-2xl border border-white/45 bg-white/42 p-4 backdrop-blur-xl">
          <p className="text-xs font-medium text-on-surface-variant mb-3">
            档口动线 · 十平不到的长方形档口
          </p>

          {/* 六步横排 */}
          <div className="grid grid-cols-3 gap-2 md:grid-cols-6">
            <AnimatePresence mode="popLayout">
              {steps.map((step, i) => {
                const isException = i === 5;
                const nextStep = i < 5 ? steps[i + 1] : null;

                return (
                  <motion.div
                    key={step.label}
                    layout
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: i * 0.05, ease: [0.16, 1, 0.3, 1] }}
                    className={`rounded-2xl border p-3 text-center transition-shadow ${
                      isException && step.count > 0
                        ? "border-red-300 bg-red-50/70 shadow-lg shadow-red-100/50"
                        : step.count > 0
                        ? "border-primary/30 bg-primary-container/15 shadow-sm"
                        : "border-white/45 bg-white/35"
                    }`}
                  >
                    <div className="flex items-center justify-center gap-1.5">
                      <step.icon className={`h-3.5 w-3.5 ${step.color}`} />
                      <span className={`text-[9px] font-mono ${
                        isException && step.count > 0 ? "text-red-500" : "text-on-surface-variant"
                      }`}>0{i + 1}</span>
                    </div>

                    <p className="mt-1.5 text-sm font-semibold text-on-background">{step.label}</p>
                    <p className="text-[10px] text-on-surface-variant">{step.subtitle}</p>

                    {/* 数量 */}
                    <motion.p
                      key={step.count}
                      initial={{ scale: 1.4, opacity: 0.6 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ type: "spring", stiffness: 400, damping: 20 }}
                      className={`mt-2 text-2xl font-bold tabular-nums ${
                        isException && step.count > 0 ? "text-red-600" : "text-on-background"
                      }`}
                    >
                      {step.count}
                    </motion.p>

                    {/* 操作按钮 */}
                    <div className="mt-2 flex items-center justify-center gap-1">
                      <button
                        onClick={() => adjustCount(i, -1)}
                        disabled={step.count <= 0}
                        className="flex h-7 w-7 items-center justify-center rounded-full border border-white/55 bg-white/45 text-xs text-on-surface-variant hover:bg-white/70 disabled:opacity-30 transition-colors"
                      >
                        −
                      </button>
                      <button
                        onClick={() => adjustCount(i, 1)}
                        className="flex h-7 w-7 items-center justify-center rounded-full border border-white/55 bg-white/45 text-xs text-on-surface-variant hover:bg-white/70 transition-colors"
                      >
                        +
                      </button>
                    </div>

                    {/* 移到下一步 / 异常 */}
                    {!isException && nextStep && (
                      <button
                        onClick={() => moveStep(i, i + 1)}
                        disabled={step.count <= 0}
                        className="mt-1.5 flex w-full items-center justify-center gap-1 rounded-full border border-white/50 bg-white/40 px-2 py-1 text-[9px] text-on-surface-variant hover:bg-white/65 disabled:opacity-30 transition-colors"
                      >
                        <ArrowRight className="h-2.5 w-2.5" /> 下一步
                      </button>
                    )}
                    {!isException && (
                      <button
                        onClick={() => moveStep(i, 5)}
                        disabled={step.count <= 0}
                        className="mt-1 flex w-full items-center justify-center gap-1 rounded-full border border-red-200 bg-red-50/30 px-2 py-1 text-[9px] text-red-500 hover:bg-red-100/40 disabled:opacity-30 transition-colors"
                      >
                        <AlertTriangle className="h-2.5 w-2.5" /> 异常
                      </button>
                    )}
                    {isException && (
                      <button
                        onClick={() => setSteps((prev) => {
                          const next = [...prev];
                          next[5] = { ...next[5], count: Math.max(0, next[5].count - 1) };
                          return next;
                        })}
                        disabled={step.count <= 0}
                        className="mt-1.5 flex w-full items-center justify-center gap-1 rounded-full border border-emerald-200 bg-emerald-50/30 px-2 py-1 text-[9px] text-emerald-600 hover:bg-emerald-100/40 disabled:opacity-30 transition-colors"
                      >
                        <CheckCircle2 className="h-2.5 w-2.5" /> 已处理
                      </button>
                    )}
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>

          {/* 图例说明 */}
          <div className="mt-3 flex flex-wrap items-center gap-3 text-[10px] text-on-surface-variant">
            <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-primary/40" /> 有订单</span>
            <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-red-400" /> 异常单</span>
            <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-slate-300" /> 空闲</span>
            <span className="ml-auto">点击 +/− 手动调整 · 「下一步」流转 · 「异常」标记</span>
          </div>
        </div>

        {/* ── 异常记录 ── */}
        <div className="rounded-2xl border border-white/45 bg-white/42 p-4 backdrop-blur-xl">
          <p className="text-xs font-medium text-on-surface-variant mb-3">
            异常记录{exceptions.length > 0 ? ` · ${exceptions.length} 条` : ""}
          </p>

          {exceptions.length > 0 ? (
            <div className="space-y-2">
              {exceptions.map((ex) => (
                <motion.div
                  key={ex.id}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex items-start justify-between gap-2 rounded-xl border border-red-200 bg-red-50/50 px-3 py-2.5"
                >
                  <div className="flex items-start gap-2 min-w-0">
                    <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-red-400" />
                    <div className="min-w-0">
                      <p className="text-sm text-on-background">{ex.text}</p>
                      <p className="mt-0.5 text-[10px] text-on-surface-variant">{ex.time}</p>
                    </div>
                  </div>
                  <button onClick={() => removeException(ex.id)} className="shrink-0 text-xs text-on-surface-variant hover:text-red-500 transition-colors">
                    移除
                  </button>
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-white/50 p-8 text-center">
              <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-300" />
              <p className="mt-2 text-sm font-medium text-on-background">暂无异常记录</p>
              <p className="mt-1 text-xs text-on-surface-variant">当订单流转出现问题时，点「异常」标注原因</p>
            </div>
          )}
        </div>

        {/* ── 异常输入弹层 ── */}
        <AnimatePresence>
          {showAddException && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 flex items-end justify-center bg-background/60 px-4 pb-6 backdrop-blur-sm md:items-center"
              onClick={() => { setShowAddException(false); setExceptionForStep(null); }}
            >
              <motion.div
                initial={{ y: 40, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 40, opacity: 0 }}
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
                onClick={(e) => e.stopPropagation()}
                className="w-full max-w-md rounded-2xl border border-white/45 bg-white/85 p-5 shadow-2xl backdrop-blur-xl"
              >
                <p className="text-sm font-semibold text-on-background">标注异常原因</p>
                <p className="mt-1 text-xs text-on-surface-variant">
                  {exceptionForStep != null ? `从「${steps[exceptionForStep]?.label}」流转到异常单` : "异常单"}
                </p>
                <textarea
                  value={exceptionText}
                  onChange={(e) => setExceptionText(e.target.value)}
                  placeholder="例如：订单重复、口味做错、漏单..."
                  className="mt-3 w-full resize-none rounded-xl border border-white/55 bg-white/55 px-3 py-2.5 text-sm text-on-background outline-none focus:border-primary/50"
                  rows={2}
                  autoFocus
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); addException(); } }}
                />
                <div className="mt-3 flex justify-end gap-2">
                  <button
                    onClick={() => { setShowAddException(false); setExceptionForStep(null); }}
                    className="rounded-full border border-white/55 px-4 py-1.5 text-xs text-on-surface-variant"
                  >
                    跳过
                  </button>
                  <button
                    onClick={addException}
                    disabled={!exceptionText.trim()}
                    className="rounded-full bg-on-background px-4 py-1.5 text-xs font-semibold text-inverse-on-surface disabled:opacity-40"
                  >
                    确认异常
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </ModulePage>
  );
}
