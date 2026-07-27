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
        className="fixed right-4 bottom-4 z-40 hidden items-center gap-1.5 rounded-full border border-muted-border bg-surface-container-high px-3 py-2 text-[10px] text-on-surface-variant shadow-sm transition-colors hover:border-agent-gold hover:text-agent-gold sm:flex"
      >
        <span className="font-mono text-[9px]">⌘⇧F</span>
        <span>反馈</span>
      </button>
      {fbOpen && <FeedbackModal onClose={() => setFbOpen(false)} onSubmit={() => setFbOpen(false)} />}
    </>
  );
}
