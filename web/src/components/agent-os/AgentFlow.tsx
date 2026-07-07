"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Check, Loader2, X, Sparkles, ArrowRight } from "lucide-react";

export type AgentStep = {
  id: string;
  label: string;
  status: "pending" | "processing" | "done" | "error";
};

export type AgentFlowProps = {
  open: boolean;
  onClose: () => void;
  steps: AgentStep[];
  title?: string;
  writeTargets?: string[];
  generatedTasks?: string[];
};

export function AgentFlow({
  open,
  onClose,
  steps,
  title = "Agent 处理中",
  writeTargets = [],
  generatedTasks = [],
}: AgentFlowProps) {
  const allDone = steps.length > 0 && steps.every((s) => s.status === "done");

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-stone-900/20 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, x: 400, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 400, scale: 0.95 }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className="fixed right-4 top-16 z-50 w-80 max-h-[calc(100vh-5rem)] overflow-y-auto rounded-3xl border border-orange-100 bg-white shadow-2xl"
          >
            {/* 头部 */}
            <div className="flex items-center justify-between border-b border-stone-100 px-4 py-3">
              <div className="flex items-center gap-2">
                <div className={`flex h-7 w-7 items-center justify-center rounded-lg ${allDone ? "bg-emerald-100" : "bg-orange-100"}`}>
                  {allDone ? (
                    <Check className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <Sparkles className="h-4 w-4 text-orange-500" />
                  )}
                </div>
                <span className="text-sm font-semibold text-stone-800">
                  {allDone ? "处理完成" : title}
                </span>
              </div>
              <button
                onClick={onClose}
                className="rounded-lg p-1 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* 步骤列表 */}
            <div className="space-y-1 px-4 py-3">
              {steps.map((step, idx) => (
                <motion.div
                  key={step.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.1 }}
                  className="flex items-center gap-2.5 py-1.5"
                >
                  <div className="flex h-5 w-5 shrink-0 items-center justify-center">
                    {step.status === "done" && (
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ type: "spring", damping: 15 }}
                      >
                        <Check className="h-4 w-4 text-emerald-500" />
                      </motion.div>
                    )}
                    {step.status === "processing" && (
                      <Loader2 className="h-4 w-4 animate-spin text-orange-500" />
                    )}
                    {step.status === "pending" && (
                      <div className="h-2 w-2 rounded-full bg-stone-200" />
                    )}
                    {step.status === "error" && (
                      <X className="h-4 w-4 text-red-500" />
                    )}
                  </div>
                  <span
                    className={`text-xs ${
                      step.status === "done"
                        ? "text-stone-700"
                        : step.status === "processing"
                        ? "text-orange-600 font-medium"
                        : "text-stone-400"
                    }`}
                  >
                    {step.label}
                  </span>
                </motion.div>
              ))}
            </div>

            {/* 写入目标 */}
            {writeTargets.length > 0 && allDone && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="border-t border-stone-100 px-4 py-3"
              >
                <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-stone-400">
                  数据已写入
                </p>
                <div className="space-y-1">
                  {writeTargets.map((target, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-1.5 rounded-lg bg-emerald-50 px-2.5 py-1.5 text-[11px] text-emerald-700"
                    >
                      <Check className="h-3 w-3" />
                      {target}
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {/* 生成的行动项 */}
            {generatedTasks.length > 0 && allDone && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="border-t border-stone-100 px-4 py-3"
              >
                <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-stone-400">
                  生成的行动项
                </p>
                <div className="space-y-1">
                  {generatedTasks.map((task, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-1.5 rounded-lg bg-orange-50 px-2.5 py-1.5 text-[11px] text-orange-700"
                    >
                      <ArrowRight className="mt-0.5 h-3 w-3 shrink-0" />
                      {task}
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {/* 底部操作 */}
            {allDone && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="border-t border-stone-100 p-3"
              >
                <button
                  onClick={onClose}
                  className="w-full rounded-xl bg-gradient-to-r from-orange-500 to-orange-600 py-2 text-xs font-semibold text-white shadow-md shadow-orange-200/50 transition-all hover:-translate-y-0.5"
                >
                  完成
                </button>
              </motion.div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
