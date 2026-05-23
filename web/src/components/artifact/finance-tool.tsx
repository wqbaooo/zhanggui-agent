"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiPost } from "@/lib/api";

interface FinanceResult {
  investment: number;
  daily_revenue: number;
  daily_gross_profit: number;
  monthly_fixed_cost: number;
  monthly_net_profit: number;
  break_even_daily_revenue: number;
  payback_months: number | null;
  net_margin_pct: number;
  profitable: boolean;
}

export function FinanceTool() {
  const [investment, setInvestment] = useState("20");
  const [dailyRevenue, setDailyRevenue] = useState("1200");
  const [costRate, setCostRate] = useState("35");
  const [rent, setRent] = useState("8000");
  const [labor, setLabor] = useState("12000");
  const [other, setOther] = useState("2000");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FinanceResult | null>(null);

  async function calculate() {
    setLoading(true);
    try {
      const data = await apiPost<{ success: boolean; data: FinanceResult }>("/api/finance", {
        investment: `${investment}万`,
        daily_revenue: dailyRevenue,
        daily_cost_rate: String(parseFloat(costRate) / 100),
        rent_monthly: rent,
        labor_monthly: labor,
        other_monthly: other,
      });
      if (data.success) setResult(data.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  const totalInvestment = parseFloat(investment) * 10000;

  return (
    <div className="flex gap-6 h-full p-6">
      <div className="w-80 shrink-0 space-y-4">
        <h2 className="text-lg font-semibold">财务测算</h2>
        <div className="space-y-3">
          <Field label="总投资（万元）" value={investment} onChange={setInvestment} />
          <Field label="日均营业额（元）" value={dailyRevenue} onChange={setDailyRevenue} />
          <Field label="食材成本率（%）" value={costRate} onChange={setCostRate} />
          <Field label="月租金（元）" value={rent} onChange={setRent} />
          <Field label="月人工（元）" value={labor} onChange={setLabor} />
          <Field label="月其他费用（元）" value={other} onChange={setOther} />
        </div>
        <Button onClick={calculate} disabled={loading} className="w-full">
          {loading ? "计算中…" : "重新测算"}
        </Button>
      </div>

      <div className="flex-1 space-y-4">
        {result ? (
          <>
            <div className="grid grid-cols-3 gap-3">
              <MetricCard label="月净利润" value={`¥${result.monthly_net_profit.toLocaleString()}`} highlight={result.profitable} />
              <MetricCard label="盈亏平衡日营业额" value={`¥${result.break_even_daily_revenue.toLocaleString()}`} />
              <MetricCard
                label="回本周期"
                value={result.payback_months ? `${result.payback_months} 个月` : "无法回本"}
                highlight={!!result.payback_months && result.payback_months <= 12}
              />
            </div>
            <div className="grid grid-cols-4 gap-3">
              <SmallMetric label="总投资" value={`¥${totalInvestment.toLocaleString()}`} />
              <SmallMetric label="日毛利" value={`¥${result.daily_gross_profit.toLocaleString()}`} />
              <SmallMetric label="月固定成本" value={`¥${result.monthly_fixed_cost.toLocaleString()}`} />
              <SmallMetric label="净利润率" value={`${result.net_margin_pct}%`} />
            </div>
            <Card className="p-4">
              <p className="text-sm font-medium mb-2">判断</p>
              <p className={`text-sm ${result.profitable ? "text-green-700" : "text-red-700"}`}>
                {result.profitable ? "✅ 盈利模型成立" : "❌ 当前参数下亏损，需调整"}
              </p>
            </Card>

            <Card className="p-4">
              <p className="text-sm font-medium mb-3">敏感性分析</p>
              <div className="space-y-2 text-sm text-muted-foreground">
                {result.payback_months && (
                  <>
                    <p>保守情景（客流 -20%）：回本约 {Math.round(result.payback_months * 1.25)} 个月</p>
                    <p>乐观情景（客流 +20%）：回本约 {Math.round(result.payback_months * 0.75)} 个月</p>
                  </>
                )}
                <p>月固定成本占比：{((result.monthly_fixed_cost / (result.daily_revenue * 30)) * 100).toFixed(1)}%</p>
              </div>
            </Card>
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            填写参数后点击「重新测算」，查看盈亏分析
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="text-xs text-muted-foreground mb-1 block">{label}</label>
      <Input value={value} onChange={(e) => onChange(e.target.value)} className="h-9 text-sm" />
    </div>
  );
}

function MetricCard({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <Card className="p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-xl font-semibold mt-1 ${highlight ? "text-green-700" : ""}`}>{value}</p>
    </Card>
  );
}

function SmallMetric({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm font-medium mt-0.5">{value}</p>
    </Card>
  );
}
