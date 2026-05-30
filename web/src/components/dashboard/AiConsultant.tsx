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
          isOpen ? "bg-white border-2 border-hunter-800 text-hunter-800" : "bg-hunter-800 text-cream-50 hover:scale-105"
        )}
      >
        {isOpen ? <X className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
      </button>

      {isOpen && (
        <div className="fixed right-6 bottom-20 z-50 w-[360px] max-w-[calc(100vw-2rem)] bg-white border border-cream-200 rounded-xl shadow-xl p-4">
          <div className="flex items-center justify-between pb-2 border-b border-cream-200">
            <div className="flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-600" />
              <span className="text-xs font-bold text-hunter-800">Agent</span>
              <span className="text-[9px] text-gray-400 font-mono">LangGraph ReAct</span>
            </div>
            <button onClick={() => setIsOpen(false)} className="text-gray-300 hover:text-gray-500"><X className="w-3.5 h-3.5" /></button>
          </div>

          <div className="flex flex-wrap gap-1.5 mt-3">
            {["加盟尽职调查", "投资回本测算", "商圈选址分析"].map((q) => (
              <button key={q} onClick={() => setPrompt(q)} className="text-[10px] text-gray-500 bg-cream-50 border border-cream-200 hover:border-hunter-800 rounded-full px-2 py-1 transition-colors">{q}</button>
            ))}
          </div>

          <div className="flex gap-1.5 mt-3">
            <input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="输入需求..."
              className="flex-1 h-8 rounded-lg border border-cream-200 bg-cream-50 px-3 text-xs text-gray-600 outline-none placeholder:text-gray-300 focus:border-hunter-800"
            />
            <button className="w-8 h-8 rounded-lg bg-hunter-800 text-cream-50 flex items-center justify-center hover:bg-hunter-700 shrink-0">
              <Send className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </>
  );
};
