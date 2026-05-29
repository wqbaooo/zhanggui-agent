"use client";

import { useEffect, useState } from "react";
import { BarChart3, CalendarDays, LineChart, Target } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DEFAULT_PROJECT_ID, getOperations, type OperationListResponse } from "@/lib/api";

function money(value: number) {
  return `¥${Math.round(value).toLocaleString()}`;
}

export function DataAnalytics() {
  const [range, setRange] = useState<"7d" | "30d" | "12m">("7d");
  const [data, setData] = useState<OperationListResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getOperations(DEFAULT_PROJECT_ID, range === "7d" ? 7 : range === "30d" ? 30 : 366)
      .then((res) => {
        setData(res);
        setError("");
      })
      .catch(() => setError("后端 API 暂不可用，无法读取统一项目账本。"));
  }, [range]);

  const entries = data?.entries || [];
  const maxRevenue = Math.max(...entries.map((d) => d.revenue), 1);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">数据分析 · 新余恒太城大口章鱼烧</h2>
          <p className="mt-1 text-sm text-muted-foreground">只读取统一项目账本，不使用演示经营数据。</p>
        </div>
        <div className="flex gap-2">
          {(["7d", "30d", "12m"] as const).map((r) => (
            <Button key={r} variant={range === r ? "default" : "outline"} size="sm" onClick={() => setRange(r)}>
              {r === "7d" ? "7天" : r === "30d" ? "30天" : "12月"}
            </Button>
          ))}
        </div>
      </div>

      {error ? <Card className="border-l-4 border-l-yellow-500 p-4 text-sm">{error}</Card> : null}

      {entries.length === 0 ? (
        <Card className="overflow-hidden rounded-xl border border-[var(--app-border)] bg-white p-0">
          <div className="grid md:grid-cols-[1fr_320px]">
            <div className="p-6">
              <div className="flex size-12 items-center justify-center rounded-xl bg-[#fff1df] text-[#d95b00]">
                <LineChart className="size-6" />
              </div>
              <h3 className="mt-4 text-xl font-semibold">还不能做趋势分析</h3>
              <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
                当前没有真实经营流水。连续录入 7 天后，这里会自动生成日营收趋势、订单波动、食材率、外卖占比和预期 vs 实际。
              </p>
              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                {[
                  ["第 1 步", "录入每日 P&L"],
                  ["第 2 步", "保存财务 baseline"],
                  ["第 3 步", "生成 7 天复盘"],
                ].map(([step, title]) => (
                  <div key={step} className="rounded-lg border border-[var(--app-border)] bg-[#fbfcfd] p-3">
                    <p className="text-xs text-muted-foreground">{step}</p>
                    <p className="mt-1 text-sm font-medium">{title}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="border-t bg-[#fbfcfd] p-6 md:border-l md:border-t-0">
              <p className="text-sm font-semibold">上线后会看什么</p>
              <div className="mt-4 space-y-3 text-sm text-[#536078]">
                <p className="flex gap-2"><BarChart3 className="mt-0.5 size-4 text-[#d95b00]" />日均营收是否达到财务测算 baseline</p>
                <p className="flex gap-2"><Target className="mt-0.5 size-4 text-[#d95b00]" />高峰时段产能是否卡在出餐或人员</p>
                <p className="flex gap-2"><CalendarDays className="mt-0.5 size-4 text-[#d95b00]" />连续 30 天后是否进入复购增长阶段</p>
              </div>
            </div>
          </div>
        </Card>
      ) : (
        <>
          <Card className="p-4">
            <p className="text-sm font-medium mb-3">营收趋势</p>
            <div className="flex items-end gap-2 h-44">
              {entries.map((d) => (
                <div key={d.date} className="flex-1 flex min-w-12 flex-col items-center gap-1">
                  <span className="text-xs font-medium">{money(d.revenue)}</span>
                  <div className="w-full rounded-t bg-[#d95b00]" style={{ height: `${Math.max((d.revenue / maxRevenue) * 128, 8)}px`, opacity: 0.68 + (d.revenue / maxRevenue) * 0.32 }} />
                  <span className="text-xs text-muted-foreground">{d.date.slice(5)}</span>
                </div>
              ))}
            </div>
          </Card>
          <div className="grid grid-cols-3 gap-3">
            <Card className="p-3"><p className="text-xs text-muted-foreground">周期总营收</p><p className="text-lg font-semibold">{money(data?.summary.total_revenue || 0)}</p></Card>
            <Card className="p-3"><p className="text-xs text-muted-foreground">周期订单</p><p className="text-lg font-semibold">{data?.summary.total_orders || 0} 单</p></Card>
            <Card className="p-3"><p className="text-xs text-muted-foreground">周期净利润</p><p className="text-lg font-semibold">{money(data?.summary.net_profit || 0)}</p></Card>
          </div>
        </>
      )}
    </div>
  );
}
