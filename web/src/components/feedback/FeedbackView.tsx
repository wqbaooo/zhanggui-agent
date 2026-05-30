"use client";

import type { FeedbackItem } from "@/domain/types";
import { Card, CardContent } from "@/components/ui/card";
import { SectionHeader } from "@/components/shared/SectionHeader";

export function FeedbackView({ items, onOpen }: { items: FeedbackItem[]; onOpen: () => void }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <SectionHeader title="反馈记录" subtitle={`${items.length} 条`} />
        <button onClick={onOpen} className="rounded-lg bg-hunter-800 hover:bg-hunter-700 text-cream-50 px-4 py-2 text-xs font-semibold transition-colors">+ 新反馈</button>
      </div>

      {items.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center">
            <p className="text-sm text-gray-400">还没有反馈记录</p>
            <p className="text-[10px] text-gray-300 font-mono mt-1">⌘⇧F 或点击右下角按钮提交反馈</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {items.map(fb => (
            <Card key={fb.id}>
              <CardContent className="py-3">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-[9px] font-mono text-gray-500">{fb.type}</span>
                  <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded-full ${fb.severity === "high" ? "bg-red-50 text-red-600" : fb.severity === "medium" ? "bg-amber-50 text-amber-600" : "bg-gray-100 text-gray-500"}`}>{fb.severity}</span>
                  {fb.page && <span className="text-[9px] font-mono text-gray-400">{fb.page}</span>}
                </div>
                <p className="text-xs text-gray-600">{fb.notes}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
