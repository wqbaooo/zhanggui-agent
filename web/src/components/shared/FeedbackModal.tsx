"use client";

import { useState } from "react";
import { X } from "lucide-react";
import type { FeedbackItem } from "@/domain/types";

const TYPES: { value: FeedbackItem["type"]; label: string }[] = [
  { value: "ux", label: "UX" },
  { value: "workflow", label: "流程" },
  { value: "cognition", label: "认知" },
  { value: "missing_data", label: "缺失" },
  { value: "false_need", label: "假需求" },
  { value: "blocker", label: "阻塞" },
];

export function FeedbackModal({ onClose, onSubmit }: {
  onClose: () => void;
  onSubmit: (fb: FeedbackItem) => void;
}) {
  const [type, setType] = useState<FeedbackItem["type"]>("ux");
  const [severity, setSeverity] = useState<FeedbackItem["severity"]>("medium");
  const [page, setPage] = useState("");
  const [notes, setNotes] = useState("");
  const [expected, setExpected] = useState("");

  function submit() {
    if (!notes.trim()) return;
    onSubmit({
      id: `fb-${Date.now()}`,
      type,
      severity,
      page,
      context: "",
      notes: notes.trim(),
      expectedResult: expected.trim(),
      createdAt: new Date().toISOString(),
    });
  }

  const inputClass = "w-full rounded-lg border border-muted-border bg-surface-container-high/60 px-3 py-2 text-xs text-on-background outline-none placeholder:text-on-surface-variant/40 focus:border-agent-gold transition-colors";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="w-[420px] glass-card rounded-2xl p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4 relative z-10">
          <span className="font-label-caps text-on-background tracking-wider">QUICK FEEDBACK</span>
          <button onClick={onClose} className="text-on-surface-variant hover:text-on-background transition-colors"><X className="size-3.5" /></button>
        </div>

        <div className="mb-3 relative z-10">
          <span className="font-label-caps text-on-surface-variant mb-1.5 block">类型</span>
          <div className="flex flex-wrap gap-1.5">
            {TYPES.map((t) => (
              <button key={t.value} onClick={() => setType(t.value)} className={`rounded-full px-2.5 py-1 font-label-caps transition-all ${type === t.value ? "bg-agent-gold text-background" : "border border-muted-border text-on-surface-variant hover:border-agent-gold/50"}`}>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mb-3 relative z-10">
          <span className="font-label-caps text-on-surface-variant mb-1.5 block">严重程度</span>
          <div className="flex gap-1.5">
            {(["low", "medium", "high"] as const).map((s) => (
              <button key={s} onClick={() => setSeverity(s)} className={`rounded-full px-3 py-1 font-label-caps transition-all ${severity === s ? "bg-agent-gold text-background" : "border border-muted-border text-on-surface-variant hover:border-agent-gold/50"}`}>
                {s === "low" ? "低" : s === "medium" ? "中" : "高"}
              </button>
            ))}
          </div>
        </div>

        <div className="mb-3 relative z-10">
          <span className="font-label-caps text-on-surface-variant mb-1.5 block">出现位置</span>
          <input value={page} onChange={(e) => setPage(e.target.value)} placeholder="哪个模块/页面" className={inputClass} />
        </div>

        <div className="mb-3 relative z-10">
          <span className="font-label-caps text-on-surface-variant mb-1.5 block">具体描述 *</span>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="遇到了什么问题？" rows={3} className={`${inputClass} resize-none`} />
        </div>

        <div className="mb-4 relative z-10">
          <span className="font-label-caps text-on-surface-variant mb-1.5 block">期望结果</span>
          <input value={expected} onChange={(e) => setExpected(e.target.value)} placeholder="你希望怎样？" className={inputClass} />
        </div>

        <button onClick={submit} disabled={!notes.trim()} className="w-full rounded-lg bg-agent-gold py-2.5 text-xs font-bold text-background transition-all hover:bg-agent-gold/80 disabled:opacity-30 relative z-10">
          提交
        </button>
      </div>
    </div>
  );
}
