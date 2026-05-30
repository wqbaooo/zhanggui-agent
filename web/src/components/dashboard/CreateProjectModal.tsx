"use client";

import React, { useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const CreateProjectModal: React.FC<Props> = ({ isOpen, onClose }) => {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("茶饮 / 咖啡");
  const [city, setCity] = useState("");
  const [budget, setBudget] = useState("");
  const [stage, setStage] = useState("正在看品牌");

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-hunter-900/30 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-lg bg-white border border-cream-200 rounded-2xl p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between pb-4 border-b border-cream-100">
          <div>
            <h3 className="text-lg font-bold text-hunter-800">创建开店项目档案</h3>
            <p className="text-xs text-gray-400 mt-1">仅填写基础信息，后续由 Agent 基于工具链产出结构化分析</p>
          </div>
          <button onClick={onClose} className="text-gray-300 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); onClose(); }} className="mt-5 space-y-4">
          <div>
            <label className="text-xs font-semibold text-hunter-800 block mb-1.5">项目名称</label>
            <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：苏州茶饮加盟项目" autoFocus />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-hunter-800 block mb-1.5">经营品类</label>
              <select value={category} onChange={(e) => setCategory(e.target.value)} className="flex h-9 w-full rounded-lg border border-cream-200 bg-cream-50/50 px-3 py-1 text-sm shadow-sm outline-none focus-visible:border-hunter-800">
                <option>茶饮 / 咖啡</option>
                <option>中式快餐 / 小吃</option>
                <option>烧烤 / 夜宵</option>
                <option>烘焙 / 轻食</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-hunter-800 block mb-1.5">目标城市</label>
              <Input required value={city} onChange={(e) => setCity(e.target.value)} placeholder="例如：苏州" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-hunter-800 block mb-1.5">预算范围</label>
              <Input value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="例如：45万" />
            </div>
            <div>
              <label className="text-xs font-semibold text-hunter-800 block mb-1.5">当前阶段</label>
              <select value={stage} onChange={(e) => setStage(e.target.value)} className="flex h-9 w-full rounded-lg border border-cream-200 bg-cream-50/50 px-3 py-1 text-sm shadow-sm outline-none focus-visible:border-hunter-800">
                <option>正在看品牌</option>
                <option>已锁定品牌，正在沟通</option>
                <option>准备看铺位</option>
                <option>已签约，准备开业</option>
              </select>
            </div>
          </div>

          <div className="rounded-xl bg-cream-50/80 border border-cream-200 p-4 text-xs text-gray-500 leading-6">
            生成后系统将创建：开店前路线图、资料清单、资金测算空表、总部协作清单、开业后经营模板。
          </div>

          <div className="flex gap-3 pt-2">
            <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>取消</Button>
            <Button type="submit" className="flex-1">生成项目骨架</Button>
          </div>
        </form>
      </div>
    </div>
  );
};
