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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="w-[420px] rounded-2xl border border-cream-200 bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <span className="mono-tag text-[10px] text-black/85 tracking-wider">QUICK FEEDBACK</span>
          <button onClick={onClose} className="text-black/75 hover:text-black/95"><X className="size-3.5" /></button>
        </div>

        <div className="mb-3">
          <span className="mono-tag text-[9px] text-black/75 mb-1.5 block">类型</span>
          <div className="flex flex-wrap gap-1.5">
            {TYPES.map((t) => (
              <button key={t.value} onClick={() => setType(t.value)} className={`rounded-full px-2.5 py-1 mono-tag text-[10px] transition-colors ${type === t.value ? "bg-[#D9261C] text-black/85" : "border border-black/15 text-black/85 hover:border-black/25"}`}>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mb-3">
          <span className="mono-tag text-[9px] text-black/75 mb-1.5 block">严重程度</span>
          <div className="flex gap-1.5">
            {(["low", "medium", "high"] as const).map((s) => (
              <button key={s} onClick={() => setSeverity(s)} className={`rounded-full px-3 py-1 mono-tag text-[10px] transition-colors ${severity === s ? "bg-black/[0.400] text-black/95 border border-black/25" : "border border-black/15 text-black/80"}`}>
                {s === "low" ? "低" : s === "medium" ? "中" : "高"}
              </button>
            ))}
          </div>
        </div>

        <div className="mb-3">
          <span className="mono-tag text-[9px] text-black/75 mb-1.5 block">出现位置</span>
          <input value={page} onChange={(e) => setPage(e.target.value)} placeholder="哪个模块/页面" className="w-full rounded-lg border border-black/15 bg-transparent px-3 py-2 text-xs text-black/95 outline-none placeholder:text-black/70 focus:border-black/25" />
        </div>

        <div className="mb-3">
          <span className="mono-tag text-[9px] text-black/75 mb-1.5 block">具体描述 *</span>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="遇到了什么问题？" rows={3} className="w-full resize-none rounded-lg border border-black/15 bg-transparent px-3 py-2 text-xs text-black/95 outline-none placeholder:text-black/70 focus:border-black/25" />
        </div>

        <div className="mb-4">
          <span className="mono-tag text-[9px] text-black/75 mb-1.5 block">期望结果</span>
          <input value={expected} onChange={(e) => setExpected(e.target.value)} placeholder="你希望怎样？" className="w-full rounded-lg border border-black/15 bg-transparent px-3 py-2 text-xs text-black/95 outline-none placeholder:text-black/70 focus:border-black/25" />
        </div>

        <button onClick={submit} disabled={!notes.trim()} className="w-full rounded-lg bg-[#D9261C] py-2 text-xs font-bold text-black/85 transition-colors hover:bg-[#B91C1C] disabled:opacity-30">
          提交
        </button>
      </div>
    </div>
  );
}
