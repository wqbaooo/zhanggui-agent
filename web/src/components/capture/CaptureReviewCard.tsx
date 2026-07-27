"use client";

import Image from "next/image";
import { AlertTriangle, X } from "lucide-react";
import type { CaptureReview } from "@/lib/capture-intake";

function confidenceLabel(value: string | undefined) {
  if (value === "high") return "高";
  if (value === "medium") return "中";
  if (value === "low") return "低";
  return "待核对";
}

export function CaptureReviewCard({
  review,
  onClose,
  onConfirm,
  isSaving,
  error,
}: {
  review: CaptureReview;
  onClose: () => void;
  onConfirm: () => void;
  isSaving: boolean;
  error?: string | null;
}) {
  const artifact = review.result.structured_artifact;
  const facts = review.result.document_facts?.length
    ? review.result.document_facts
    : artifact?.canonical_sections?.facts ?? [];
  const destination = artifact?.write_targets?.join("、")
    || review.result.recommended_destination
    || "资料箱";

  return (
    <section className="overflow-hidden rounded-2xl border border-octo-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-3 border-b border-stone-100 px-4 py-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-stone-950">{review.source}</p>
          <p className="mt-0.5 truncate text-xs text-stone-500">{review.fileName}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="关闭识别结果"
          className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-stone-400 hover:bg-stone-100 hover:text-stone-700"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className={`grid gap-4 p-4 ${review.imageUrl ? "md:grid-cols-[180px_minmax(0,1fr)]" : ""}`}>
        {review.imageUrl && (
          <div className="aspect-[4/5] overflow-hidden rounded-xl border border-stone-100 bg-stone-50">
            <Image
              src={review.imageUrl}
              alt="待确认原始资料"
              width={360}
              height={450}
              unoptimized
              className="h-full w-full object-contain"
            />
          </div>
        )}

        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap gap-1.5">
            <span className="rounded-full bg-stone-100 px-2.5 py-1 text-[10px] font-medium text-stone-600">
              {artifact?.document_class || review.result.capture_kind || "待分类"}
            </span>
            <span className="rounded-full bg-octo-50 px-2.5 py-1 text-[10px] font-medium text-octo-700">
              {destination}
            </span>
          </div>

          {review.result.fields.length > 0 && (
            <div className="grid gap-2 sm:grid-cols-2">
              {review.result.fields.slice(0, 10).map((field) => (
                <div key={`${field.key}-${field.label}`} className="rounded-xl bg-stone-50 p-3">
                  <p className="text-[11px] text-stone-500">{field.label || field.key}</p>
                  <p className="mt-1 break-words text-sm font-semibold text-stone-900">{String(field.value ?? "—")}</p>
                  <p className="mt-1 text-[10px] text-stone-400">置信度：{confidenceLabel(field.confidence)}</p>
                </div>
              ))}
            </div>
          )}

          {facts.length > 0 && (
            <div className="space-y-2">
              {facts.slice(0, 8).map((fact, index) => (
                <div key={`${fact.label}-${index}`} className="rounded-xl bg-stone-50 px-3 py-2.5">
                  <p className="text-[11px] text-stone-500">{fact.label}</p>
                  <p className="mt-1 whitespace-pre-wrap break-words text-sm text-stone-900">{fact.value}</p>
                </div>
              ))}
            </div>
          )}

          {review.result.parse_error && (
            <p className="flex items-start gap-2 rounded-xl bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              {review.result.parse_error}
            </p>
          )}
          {error && <p className="rounded-xl bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>}

          <div className="flex justify-end gap-2 border-t border-stone-100 pt-3">
            <button
              type="button"
              onClick={onClose}
              className="min-h-10 rounded-xl border border-stone-200 px-4 text-xs font-medium text-stone-600 hover:bg-stone-50"
            >
              取消
            </button>
            <button
              type="button"
              onClick={onConfirm}
              disabled={isSaving}
              className="min-h-10 rounded-xl bg-octo-500 px-4 text-xs font-semibold text-white hover:bg-octo-600 disabled:opacity-50"
            >
              {isSaving ? "保存中…" : "确认归档"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
