"use client";

import type { FeedbackItem } from "@/domain/types";
import { SectionHeader } from "@/components/shared/SectionHeader";
import { MessageSquare, Plus } from "lucide-react";

export function FeedbackView({ items, onOpen }: { items: FeedbackItem[]; onOpen: () => void }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <SectionHeader title="反馈记录" subtitle={`${items.length} 条`} />
        <button onClick={onOpen} className="rounded-lg bg-deep-forest px-4 py-2 text-[11px] font-medium text-on-primary transition-colors border border-agent-gold/30 hover:bg-primary flex items-center gap-1.5">
          <Plus className="w-3.5 h-3.5" />
          新反馈
        </button>
      </div>

      {items.length === 0 ? (
        <div className="glass-card rounded-xl p-8 interactive-card border-dashed border-muted-border/40">
          <div className="text-center relative z-10">
            <MessageSquare className="w-8 h-8 text-on-surface-variant/30 mx-auto mb-3" />
            <p className="text-sm text-on-surface-variant">还没有反馈记录</p>
            <p className="mt-1 text-[11px] text-on-surface-variant/60">⌘⇧F 或点击右下角按钮提交反馈</p>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map(fb => (
            <div key={fb.id} className="glass-card rounded-xl p-4 interactive-card">
              <div className="flex items-center gap-2 mb-1.5 relative z-10">
                <span className="font-label-caps text-on-surface-variant">{fb.type}</span>
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-mono ${fb.severity === "high" ? "bg-error/15 text-error" : fb.severity === "medium" ? "bg-amber-500/15 text-amber-700" : "bg-surface-container-high/70 text-on-surface-variant"}`}>{fb.severity}</span>
                {fb.page && <span className="text-[10px] font-mono text-on-surface-variant/50">{fb.page}</span>}
              </div>
              <p className="text-xs text-on-surface-variant relative z-10">{fb.notes}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
