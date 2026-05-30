"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { LifecycleMap } from "@/components/dashboard/LifecycleMap";
import { SectionPanels } from "@/components/dashboard/SectionPanels";
import { CreateProjectModal } from "@/components/dashboard/CreateProjectModal";
import { AiConsultant } from "@/components/dashboard/AiConsultant";

export default function OverviewPage() {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div className="space-y-6 pb-24">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <Card className="md:col-span-3">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <span className="size-2 rounded-full bg-amber-500" />
              <CardTitle className="text-sm">项目档案 · 0</CardTitle>
              <span className="text-[10px] text-gray-300 font-mono ml-auto">6 工具 · LangGraph · V2</span>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="grid grid-cols-3 gap-6 text-xs">
                <div><span className="text-gray-300">投资测算</span><p className="text-sm font-bold text-gray-700 mt-0.5" style={{ fontFamily: "Antonio, sans-serif" }}>待录入</p></div>
                <div><span className="text-gray-300">选址评估</span><p className="text-sm font-bold text-gray-700 mt-0.5" style={{ fontFamily: "Antonio, sans-serif" }}>待录入</p></div>
                <div><span className="text-gray-300">风险清单</span><p className="text-sm font-bold text-gray-700 mt-0.5" style={{ fontFamily: "Antonio, sans-serif" }}>0 条</p></div>
              </div>
              <Button size="sm" onClick={() => setModalOpen(true)}>创建项目</Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">系统状态</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            <div className="flex justify-between"><span className="text-gray-400">知识库</span><span className="text-emerald-600 font-mono">1302 chunks</span></div>
            <div className="flex justify-between"><span className="text-gray-400">向量索引</span><span className="text-emerald-600 font-mono">在线</span></div>
            <div className="flex justify-between"><span className="text-gray-400">高德地图</span><span className="text-emerald-600 font-mono">已接入</span></div>
            <div className="flex justify-between"><span className="text-gray-400">联网搜索</span><span className="text-emerald-600 font-mono">已接入</span></div>
            <div className="flex justify-between"><span className="text-gray-400">财务引擎</span><span className="text-emerald-600 font-mono">已接入</span></div>
            <div className="flex justify-between"><span className="text-gray-400">加盟分析</span><span className="text-emerald-600 font-mono">已接入</span></div>
          </CardContent>
        </Card>
      </div>

      <LifecycleMap />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <SectionPanels onCreateProject={() => setModalOpen(true)} />
      </div>

      <AiConsultant />

      <CreateProjectModal isOpen={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  );
}
