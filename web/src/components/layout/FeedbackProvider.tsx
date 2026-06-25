"use client";

import { useState } from "react";
import { FeedbackModal } from "@/components/shared/FeedbackModal";

export function FeedbackProvider({ children }: { children: React.ReactNode }) {
  const [fbOpen, setFbOpen] = useState(false);

  return (
    <>
      {children}
      <button
        onClick={() => setFbOpen(true)}
        className="fixed right-4 bottom-16 lg:bottom-4 z-40 flex items-center gap-1.5 rounded-full border border-muted-border bg-surface-container-high px-3 py-2 text-[10px] text-on-surface-variant hover:text-agent-gold hover:border-agent-gold shadow-sm transition-colors"
      >
        <span className="font-mono text-[9px]">⌘⇧F</span>
        <span>反馈</span>
      </button>
      {fbOpen && <FeedbackModal onClose={() => setFbOpen(false)} onSubmit={() => setFbOpen(false)} />}
    </>
  );
}
