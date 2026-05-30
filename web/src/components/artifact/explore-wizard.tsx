"use client";

import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiPost, checkBackend } from "@/lib/api";

type Step = "city" | "category" | "review" | "report";

export function ExploreWizard({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<Step>("city");
  const [city, setCity] = useState("");
  const [budget, setBudget] = useState("");
  const [experience, setExperience] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<string>("");
  const [backendOk, setBackendOk] = useState<boolean | null>(null);

  useEffect(() => {
    checkBackend().then(setBackendOk);
  }, []);

  const allCategories = ["早餐", "快餐", "小吃", "奶茶", "咖啡", "火锅", "烧烤", "面馆", "粉店", "日料", "炸鸡", "烘焙"];

  function toggleCategory(c: string) {
    setCategories((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  }

  async function generate() {
    setLoading(true);
    try {
      const data = await apiPost<{ response: string }>("/api/chat/sync", {
        message: `我在${city}，预算${budget}，${experience === "none" ? "完全没有餐饮经验" : experience === "some" ? "有一点餐饮经验" : "开过餐饮店"}。我对${categories.join("、")}这些品类感兴趣。请帮我做一份可行性分析报告，包括：1）品类推荐排序 2）预算拆解 3）风险提示 4）Go/No-Go判断。`,
      });
      setReport(data.response);
      setStep("report");
    } catch {
      setReport("⚠️ 无法连接后端服务。请先启动后端：\n\n```bash\ncd 掌柜Agent\npython3 -m uvicorn server.main:app --port 8000\n```\n\n然后重试。");
      setStep("report");
    } finally {
      setLoading(false);
    }
  }

  if (step === "report") {
    return (
      <div className="max-w-2xl mx-auto p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">可行性分析报告</h2>
          <Button variant="outline" size="sm" onClick={onBack}>返回首页</Button>
        </div>
        <Card className="p-6">
          <div className="text-sm whitespace-pre-wrap">{report}</div>
        </Card>
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => { setStep("city"); setReport(""); }}>重新生成</Button>
          <Button onClick={onBack}>保存并开始筹备</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto p-6 space-y-8">
      <div className="text-center">
        <h1 className="text-xl font-semibold">开店可行性分析</h1>
        <p className="text-sm text-muted-foreground mt-1">3 步填写基本信息，AI 帮你判断该不该干</p>
        {backendOk === false && (
          <p className="text-xs text-red-600 mt-2 bg-red-50 py-1 px-2 rounded inline-block">
            ⚠️ 后端未连接 — 启动方式见页面底部
          </p>
        )}
      </div>

      <div className="flex justify-center gap-2">
        {(["city", "category", "review"] as Step[]).map((s, i) => (
          <div key={s} className={`w-24 h-1 rounded-full ${step === s ? "bg-primary" : step === "review" && i < 2 ? "bg-primary" : "bg-muted"}`} />
        ))}
      </div>

      {step === "city" && (
        <Card className="p-6 space-y-4">
          <h3 className="font-medium">第一步：你在哪里，有多少资金？</h3>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">目标城市</label>
              <input value={city} onChange={(e) => setCity(e.target.value)} placeholder="如：江西新余 / 恒太城" className="w-full border rounded-md px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">预算范围</label>
              <div className="grid grid-cols-4 gap-2">
                {["5万", "10万", "15万", "20万", "30万", "50万"].map((b) => (
                  <button key={b} onClick={() => setBudget(b)} className={`text-sm py-2 rounded-md border transition-colors ${budget === b ? "bg-primary text-primary-foreground border-primary" : "hover:bg-muted"}`}>{b}</button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">餐饮经验</label>
              <div className="grid grid-cols-3 gap-2">
                {[{ v: "none", l: "零经验" }, { v: "some", l: "有点经验" }, { v: "veteran", l: "开过店" }].map((e) => (
                  <button key={e.v} onClick={() => setExperience(e.v)} className={`text-sm py-2 rounded-md border transition-colors ${experience === e.v ? "bg-primary text-primary-foreground border-primary" : "hover:bg-muted"}`}>{e.l}</button>
                ))}
              </div>
            </div>
          </div>
          <Button className="w-full" disabled={!city || !budget || !experience} onClick={() => setStep("category")}>下一步</Button>
        </Card>
      )}

      {step === "category" && (
        <Card className="p-6 space-y-4">
          <h3 className="font-medium">第二步：你对哪些品类感兴趣？</h3>
          <div className="grid grid-cols-3 gap-2">
            {allCategories.map((c) => (
              <button key={c} onClick={() => toggleCategory(c)} className={`text-sm py-2 rounded-md border transition-colors ${categories.includes(c) ? "bg-primary text-primary-foreground border-primary" : "hover:bg-muted"}`}>{c}</button>
            ))}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep("city")}>上一步</Button>
            <Button className="flex-1" disabled={categories.length === 0} onClick={() => setStep("review")}>下一步</Button>
          </div>
        </Card>
      )}

      {step === "review" && (
        <Card className="p-6 space-y-4">
          <h3 className="font-medium">确认信息</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-muted-foreground">城市</span><span>{city}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">预算</span><span>{budget}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">经验</span><span>{experience === "none" ? "零经验" : experience === "some" ? "有点经验" : "开过店"}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">品类</span><span>{categories.join("、")}</span></div>
          </div>
          {backendOk === false && (
            <p className="text-xs text-red-600 bg-red-50 p-2 rounded">
              后端未连接。请在新终端运行：<code className="bg-red-100 px-1">python3 -m uvicorn server.main:app --port 8000</code>
            </p>
          )}
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep("category")}>上一步</Button>
            <Button className="flex-1" onClick={generate} disabled={loading || backendOk === false}>{loading ? "生成中…" : backendOk === false ? "后端未连接" : "生成可行性报告"}</Button>
          </div>
        </Card>
      )}
    </div>
  );
}
