"use client";

import React, { useState } from "react";
import { X } from "lucide-react";
import { useCreateProject } from "@/lib/hooks/useProject";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  projectId?: string;
}

export const CreateProjectModal: React.FC<Props> = ({ isOpen, onClose, projectId = "default" }) => {
  const createProject = useCreateProject();
  const [name, setName] = useState("");
  const [category, setCategory] = useState("茶饮 / 咖啡");
  const [city, setCity] = useState("");
  const [budget, setBudget] = useState("");
  const [stage, setStage] = useState("接店盘点中");

  if (!isOpen) return null;

  const stageMap: Record<string, string> = {
    "接店盘点中": "idea",
    "已看完合同与费用": "franchise_talk",
    "正在补平台和设备信息": "location_selection",
    "已接手，准备打烊复盘": "trial_operation",
  };

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !city.trim()) return;

    createProject.mutate(
      {
        projectId,
        profile: {
          name,
          category,
          city,
          budget: Number(budget) || 0,
          stage: stageMap[stage] || "idea",
          available_cash: Number(budget) * 5000 || 0,
        },
      },
      { onSuccess: () => { onClose(); window.location.reload(); } }
    );
  }

  const inputClass = "flex h-9 w-full rounded-lg border border-muted-border bg-surface-container-high/60 px-3 py-1 text-sm text-on-background shadow-sm outline-none focus:border-agent-gold transition-colors placeholder:text-on-surface-variant/40";
  const selectClass = "flex h-9 w-full rounded-lg border border-muted-border bg-surface-container-high/60 px-3 py-1 text-sm text-on-background shadow-sm outline-none focus:border-agent-gold transition-colors";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-lg glass-card rounded-2xl p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between pb-4 border-b border-muted-border/30 relative z-10">
          <div>
            <h3 className="font-headline-lg text-on-background">创建门店档案</h3>
            <p className="text-xs text-on-surface-variant mt-1">填写基础信息，系统将自动生成门店骨架</p>
          </div>
          <button onClick={onClose} className="text-on-surface-variant hover:text-on-background transition-colors"><X className="w-5 h-5" /></button>
        </div>

        <form onSubmit={handleSubmit} className="mt-5 space-y-4 relative z-10">
          <div>
            <label className="text-xs font-semibold text-on-background block mb-1.5">项目名称</label>
            <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：新余恒太城大口章鱼烧" autoFocus className={inputClass} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-on-background block mb-1.5">经营品类</label>
              <select value={category} onChange={(e) => setCategory(e.target.value)} className={selectClass}>
                <option>茶饮 / 咖啡</option><option>中式快餐 / 小吃</option><option>烧烤 / 夜宵</option><option>烘焙 / 轻食</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-on-background block mb-1.5">目标城市</label>
              <input required value={city} onChange={(e) => setCity(e.target.value)} placeholder="例如：苏州" className={inputClass} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-on-background block mb-1.5">预算范围（万元）</label>
              <input value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="例如：45" className={inputClass} />
            </div>
            <div>
              <label className="text-xs font-semibold text-on-background block mb-1.5">当前阶段</label>
              <select value={stage} onChange={(e) => setStage(e.target.value)} className={selectClass}>
                <option>接店盘点中</option><option>已看完合同与费用</option><option>正在补平台和设备信息</option><option>已接手，准备打烊复盘</option>
              </select>
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 rounded-lg border border-muted-border px-4 py-2 text-xs text-on-surface-variant hover:text-on-background hover:border-agent-gold/50 transition-all">
              取消
            </button>
            <button type="submit" disabled={createProject.isPending} className="flex-1 rounded-lg bg-agent-gold px-4 py-2 text-xs font-bold text-background transition-all hover:bg-agent-gold/80 disabled:opacity-30">
              {createProject.isPending ? "创建中..." : "创建项目"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
