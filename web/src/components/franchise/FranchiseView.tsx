"use client";

import { useMemo, useState } from "react";
import { fmtMoney, fmtPct } from "@/domain/calculations";
import { assessFranchiseRisks, identifySalesTricks, identifyHiddenCosts, generateNextQuestions } from "@/domain/riskRules";
import { mockFranchise } from "@/data/mockProject";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { SectionHeader } from "@/components/shared/SectionHeader";
import { Row, Clause } from "@/components/shared/DataDisplay";
import { RiskList } from "@/components/shared/RiskList";

const INTEL_SOURCES = ["朋友说的", "网上搜的", "实地看到的", "品牌方说的", "展会了解", "抖音/小红书", "其他"];
const INTEL_CATEGORIES = ["费用", "合同", "经营数据", "退出机制", "口碑评价", "供应链", "其他"];

interface IntelRecord {
  id: string;
  source: string;
  category: string;
  content: string;
  reliability: "高" | "中" | "低";
  timestamp: string;
}

export function FranchiseView() {
  const fa = mockFranchise;
  const risks = useMemo(() => assessFranchiseRisks(fa), []);
  const tricks = useMemo(() => identifySalesTricks(fa.salesPitch), []);
  const hiddenCosts = useMemo(() => identifyHiddenCosts(fa), []);
  const nextQuestions = useMemo(() => generateNextQuestions(fa), []);
  const totalCost = fa.franchiseFee + fa.deposit + fa.equipmentFee + fa.firstInventoryFee + fa.renovationRequirement;
  const [intelRecords, setIntelRecords] = useState<IntelRecord[]>([]);
  const [intelOpen, setIntelOpen] = useState(false);
  const [intelSource, setIntelSource] = useState(INTEL_SOURCES[0]);
  const [intelCategory, setIntelCategory] = useState(INTEL_CATEGORIES[0]);
  const [intelContent, setIntelContent] = useState("");
  const [intelReliability, setIntelReliability] = useState<"高" | "中" | "低">("中");

  function submitIntel() {
    if (!intelContent.trim()) return;
    setIntelRecords(p => [...p, {
      id: `intel-${Date.now()}`,
      source: intelSource,
      category: intelCategory,
      content: intelContent.trim(),
      reliability: intelReliability,
      timestamp: new Date().toISOString(),
    }]);
    setIntelContent("");
    setIntelOpen(false);
  }

  return (
    <div className="space-y-6">
      <SectionHeader title={fa.brandName} subtitle="加盟品牌分析" />

      <Card>
        <CardHeader>
          <CardTitle>费用结构</CardTitle>
          <CardDescription>加盟各项费用明细</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <Row label="加盟费" value={fmtMoney(fa.franchiseFee)} />
            <Row label="保证金" value={fmtMoney(fa.deposit)} />
            <Row label="设备费" value={fmtMoney(fa.equipmentFee)} />
            <Row label="首批物料" value={fmtMoney(fa.firstInventoryFee)} />
            <Row label="装修费" value={fmtMoney(fa.renovationRequirement)} />
            <Row label="管理费/月" value={fmtMoney(fa.managementFeeMonthly)} />
            <Row label="抽成比例" value={fmtPct(fa.royaltyRate)} />
            <Row label="合同年限" value={`${fa.contractYears}年`} />
          </div>
          <div className="mt-3 pt-3 border-t border-cream-200 flex justify-between">
            <span className="text-xs font-semibold text-gray-700">总投资</span>
            <span className="text-sm font-bold text-gray-800" style={{ fontFamily: "Antonio, sans-serif" }}>{fmtMoney(totalCost)}</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle>情报档案</CardTitle>
            <CardDescription>{intelRecords.length} 条记录</CardDescription>
          </div>
          <button onClick={() => setIntelOpen(!intelOpen)} className="rounded-lg bg-hunter-800 text-cream-50 px-3 py-1.5 text-[10px] font-semibold hover:bg-hunter-700 transition-colors">+ 记录</button>
        </CardHeader>
        {intelOpen && (
          <CardContent>
            <div className="rounded-lg border border-cream-200 p-3 space-y-2.5 mb-4">
              <div className="flex gap-2">
                <select value={intelSource} onChange={e => setIntelSource(e.target.value)} className="rounded-lg border border-cream-200 bg-white px-2 py-1.5 text-xs text-gray-600 outline-none">
                  {INTEL_SOURCES.map(s => <option key={s}>{s}</option>)}
                </select>
                <select value={intelCategory} onChange={e => setIntelCategory(e.target.value)} className="rounded-lg border border-cream-200 bg-white px-2 py-1.5 text-xs text-gray-600 outline-none">
                  {INTEL_CATEGORIES.map(c => <option key={c}>{c}</option>)}
                </select>
                <div className="flex gap-1">
                  {(["高","中","低"] as const).map(r => (
                    <button key={r} onClick={() => setIntelReliability(r)} className={`rounded-full px-2 py-1 text-[10px] font-mono ${intelReliability === r ? "bg-hunter-800 text-cream-50" : "border border-cream-200 text-gray-400"}`}>{r}</button>
                  ))}
                </div>
              </div>
              <textarea value={intelContent} onChange={e => setIntelContent(e.target.value)} placeholder="记录获取到的信息..." rows={2} className="w-full resize-none rounded-lg border border-cream-200 bg-white px-3 py-2 text-xs text-gray-600 outline-none placeholder:text-gray-300" />
              <div className="flex justify-end gap-2">
                <button onClick={() => setIntelOpen(false)} className="rounded-lg px-3 py-1.5 text-[10px] text-gray-400">取消</button>
                <button onClick={submitIntel} disabled={!intelContent.trim()} className="rounded-lg bg-hunter-800 text-cream-50 px-3 py-1.5 text-[10px] font-semibold disabled:opacity-30">记录</button>
              </div>
            </div>
          </CardContent>
        )}
        {intelRecords.length > 0 && (
          <CardContent>
            <div className="space-y-2">
              {intelRecords.map(r => (
                <div key={r.id} className="rounded-lg border border-cream-200 p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[9px] font-mono text-gray-400">{r.source}</span>
                    <span className="text-[9px] font-mono text-gray-400">{r.category}</span>
                    <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded-full ${r.reliability === "高" ? "bg-emerald-50 text-emerald-700" : r.reliability === "中" ? "bg-amber-50 text-amber-700" : "bg-gray-100 text-gray-500"}`}>{r.reliability}可信</span>
                    <span className="text-[8px] font-mono text-gray-400 ml-auto">{r.timestamp.slice(5,10)}</span>
                  </div>
                  <p className="text-xs text-gray-600">{r.content}</p>
                </div>
              ))}
            </div>
          </CardContent>
        )}
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>合同条款</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1.5 text-xs">
          <Clause label="强制采购" value={fa.forcesProcurement ? "是" : "否"} warn={fa.forcesProcurement} />
          <Clause label="区域保护" value={fa.hasTerritoryProtection ? "有" : "无"} warn={!fa.hasTerritoryProtection} />
          <Clause label="承诺回本" value={fa.promisesPaybackPeriod ? `${fa.promisedPaybackMonths}个月` : "无"} warn={!!fa.promisesPaybackPeriod && !!fa.promisedPaybackMonths && fa.promisedPaybackMonths < 8} />
          <Clause label="提供真实数据" value={fa.providesRealStoreData ? "是" : "否"} warn={!fa.providesRealStoreData} />
          <Clause label="可联系老加盟商" value={fa.allowsExistingFranchiseeContact ? "是" : "否"} warn={!fa.allowsExistingFranchiseeContact} />
          <Clause label="退出机制" value={fa.hasExitMechanism ? "有" : "无"} warn={!fa.hasExitMechanism} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>品牌方承诺</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1.5">
          {fa.salesPitch.map((s, i) => (
            <div key={i} className="flex items-center gap-2 text-xs text-gray-500"><span className="text-amber-500">⚠</span>{s}</div>
          ))}
        </CardContent>
      </Card>

      {tricks.length > 0 && (
        <Card className="border-amber-400/30 bg-amber-50/30">
          <CardHeader>
            <CardTitle className="text-amber-800">招商话术识别</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {tricks.map((t, i) => (
              <div key={i} className="rounded-lg border border-amber-200 bg-white p-3">
                <p className="text-xs font-medium text-amber-700">话术：{t.trick}</p>
                <p className="text-[11px] text-gray-500 mt-1">风险：{t.risk}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>潜在隐藏成本</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1.5">
          {hiddenCosts.map((c, i) => (
            <div key={i} className="flex items-center gap-2 text-xs text-red-600"><span>+</span>{c}</div>
          ))}
        </CardContent>
      </Card>

      <Card className="border-emerald-400/30 bg-emerald-50/30">
        <CardHeader>
          <CardTitle className="text-emerald-800">下一轮必问品牌方</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {nextQuestions.map((q, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className="flex size-5 shrink-0 items-center justify-center rounded border border-emerald-300 text-[10px] text-emerald-600 font-mono">{i + 1}</span>
                <span className="text-xs text-gray-600">{q}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <RiskList risks={risks} title="加盟风险" />
    </div>
  );
}
