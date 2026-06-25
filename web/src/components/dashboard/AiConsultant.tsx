"use client";

import React, { useState } from "react";
import { Sparkles, X, Send } from "lucide-react";
import { cn } from "@/lib/utils";

export const AiConsultant: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [prompt, setPrompt] = useState("");

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "fixed right-6 bottom-6 z-50 w-12 h-12 rounded-full grid place-items-center shadow-lg transition-all",
          isOpen ? "bg-surface-bright border-2 border-agent-gold text-on-background" : "bg-on-background text-inverse-on-surface hover:scale-105"
        )}
      >
        {isOpen ? <X className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
      </button>

      {isOpen && (
        <div className="fixed right-6 bottom-20 z-50 w-[360px] max-w-[calc(100vw-2rem)] bg-surface-bright border border-muted-border/30 rounded-xl shadow-xl p-4">
          <div className="flex items-center justify-between pb-2 border-b border-muted-border/20">
            <div className="flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-agent-gold" />
              <span className="text-xs font-semibold text-on-background">Agent</span>
              <span className="text-[9px] font-mono text-on-surface-variant">LangGraph ReAct</span>
            </div>
            <button onClick={() => setIsOpen(false)} className="text-on-surface-variant/50 hover:text-on-surface-variant"><X className="w-3.5 h-3.5" /></button>
          </div>

          <div className="flex flex-wrap gap-1.5 mt-3">
            {["接店盘点清单", "门店日账复盘", "外卖渠道诊断"].map((q) => (
              <button key={q} onClick={() => setPrompt(q)} className="text-[10px] text-on-surface-variant bg-surface-container-high/40 border border-muted-border/30 hover:border-agent-gold/40 hover:text-on-background rounded-full px-2 py-1 transition-colors">{q}</button>
            ))}
          </div>

          <div className="flex gap-1.5 mt-3">
            <input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="输入需求..."
              className="flex-1 h-8 rounded-lg border border-muted-border/30 bg-surface-container-high/30 px-3 text-xs text-on-background outline-none placeholder:text-on-surface-variant/40 focus:border-agent-gold"
            />
            <button className="w-8 h-8 rounded-lg bg-on-background text-inverse-on-surface flex items-center justify-center hover:opacity-90 shrink-0">
              <Send className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </>
  );
};
