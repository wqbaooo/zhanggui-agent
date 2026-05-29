"use client";

import { useState } from "react";
import { Settings, BarChart3, CalendarCheck, LayoutDashboard } from "lucide-react";
import type { ProjectCockpit } from "@/lib/api";
import { MonoTag } from "./bento";
import { HeroCard } from "./cards/hero-card";
import { StatusCard } from "./cards/status-card";
import { PlanCard } from "./cards/plan-card";
import { TodoCard } from "./cards/todo-card";
import { WeatherCard } from "./cards/weather-card";
import { CommandBar } from "./command-bar";

interface SpaceShellProps {
  cockpit: ProjectCockpit | null;
  onNavigate: (view: string) => void;
  onOpenSheet: (sheet: string) => void;
}

const NAV_ITEMS = [
  { label: "仪表盘", icon: LayoutDashboard },
  { label: "开业计划", icon: CalendarCheck },
  { label: "数据", icon: BarChart3 },
  { label: "设置", icon: Settings },
];

export function SpaceShell({
  cockpit,
  onNavigate,
  onOpenSheet,
}: SpaceShellProps) {
  const [chatHistory, setChatHistory] = useState<
    Array<{ role: "user" | "agent"; content: string }>
  >([]);

  function handleMessage(msg: string, response: string) {
    setChatHistory((prev) => [
      ...prev.slice(-6),
      { role: "user", content: msg },
      { role: "agent", content: response },
    ]);
  }

  return (
    <div className="min-h-screen bg-[#0A0A0A] p-3 sm:p-[14px]">
      {/* Canvas Frame */}
      <div className="canvas-frame">
        {/* Top Navigation Bar */}
        <nav className="mb-4 flex items-center justify-between px-1 py-2">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-[10px] bg-[#D9261C] border-2 border-[#0A0A0A]">
              <span className="display-lg text-base text-[#F5EFE3]">K</span>
            </div>
            <span className="display-lg text-lg tracking-tight text-[#F5EFE3]">
              开店 &middot; AGENT
            </span>
          </div>

          <div className="hidden items-center gap-1 sm:flex">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.label}
                className="flex items-center gap-1.5 rounded-full px-3 py-1.5 mono-tag text-[#F5EFE3]/50 transition-colors hover:text-[#F5EFE3]/80 hover:bg-[#F5EFE3]/10"
              >
                <item.icon className="size-3.5" />
                {item.label}
              </button>
            ))}
          </div>

          <div className="flex size-8 items-center justify-center rounded-full bg-gradient-to-br from-[#7FE05A] to-[#0F4C3A] border-2 border-[#F5EFE3]/20">
            <span className="text-[10px] font-bold text-[#F5EFE3]">W</span>
          </div>
        </nav>

        {/* Bento Grid */}
        <div className="bento-grid">
          {/* Hero: span 8, row 5 */}
          <div className="col-span-12 row-span-5 md:col-span-8">
            <HeroCard cockpit={cockpit} onNavigate={onNavigate} />
          </div>

          {/* Status: span 4, row 5 */}
          <div className="col-span-12 row-span-5 md:col-span-4">
            <StatusCard cockpit={cockpit} />
          </div>

          {/* Plan: span 3, row 3 */}
          <div className="col-span-6 row-span-3 md:col-span-3">
            <PlanCard cockpit={cockpit} onOpen={onOpenSheet} />
          </div>

          {/* Todo: span 5, row 3 */}
          <div className="col-span-6 row-span-3 md:col-span-5">
            <TodoCard cockpit={cockpit} onNavigate={onNavigate} />
          </div>

          {/* Weather: span 4, row 3 */}
          <div className="col-span-12 row-span-3 md:col-span-4">
            <WeatherCard />
          </div>
        </div>

        {/* Chat History */}
        {chatHistory.length > 0 && (
          <div className="mt-3 rounded-[20px] bg-[#EDE4D2] p-[18px]">
            <MonoTag>[ 对话 ]</MonoTag>
            <div className="mt-3 space-y-3">
              {chatHistory.map((msg, i) => (
                <div
                  key={i}
                  className={"flex " + (msg.role === "user" ? "justify-end" : "")}
                >
                  <div
                    className={
                      "max-w-[80%] px-4 py-3 text-sm leading-relaxed " +
                      (msg.role === "user"
                        ? "chat-bubble-user bg-[#0A0A0A] text-[#F5EFE3]"
                        : "chat-bubble bg-[#0F4C3A] text-[#F5EFE3]")
                    }
                  >
                    {msg.content}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Command Bar */}
        <div className="mt-3">
          <CommandBar onMessage={handleMessage} />
        </div>
      </div>
    </div>
  );
}
