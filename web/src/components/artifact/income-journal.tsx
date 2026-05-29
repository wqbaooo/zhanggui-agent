"use client";

import { FormEvent, useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DEFAULT_PROJECT_ID,
  addOperation,
  getOperations,
  type DailyOperationEntry,
  type OperationListResponse,
} from "@/lib/api";

function blankEntry(): DailyOperationEntry {
  return {
    date: new Date().toISOString().slice(0, 10),
    revenue: 0,
    orders: 0,
    food_cost: 0,
    labor: 0,
    rent_allocated: 0,
    utility: 0,
    other_cost: 0,
    takeout_orders: 0,
    platform_fee: 0,
    marketing_cost: 0,
    inventory_loss: 0,
    notes: "",
  };
}

function money(value: number) {
  return `¥${Math.round(value).toLocaleString()}`;
}

export function IncomeJournal() {
  const [view, setView] = useState<"daily" | "monthly">("daily");
  const [data, setData] = useState<OperationListResponse | null>(null);
  const [entry, setEntry] = useState<DailyOperationEntry>(blankEntry);
  const [status, setStatus] = useState("");

  function refresh() {
    getOperations(DEFAULT_PROJECT_ID, 30)
      .then(setData)
      .catch(() => setStatus("后端暂未启动，暂不能读取或保存经营数据。"));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus("保存中...");
    try {
      await addOperation(entry, DEFAULT_PROJECT_ID);
      setEntry(blankEntry());
      setStatus("已保存");
      refresh();
    } catch {
      setStatus("保存失败，请确认后端 API 已启动。");
    }
  }

  const entries = data?.entries || [];
  const summary = data?.summary;
  const monthRevenue = summary ? summary.total_revenue / Math.max(summary.entry_count, 1) * 30 : 0;
  const monthProfit = summary ? summary.net_profit / Math.max(summary.entry_count, 1) * 30 : 0;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">收支记账 · 新余恒太城大口章鱼烧</h2>
        <div className="flex gap-2">
          <Button variant={view === "daily" ? "default" : "outline"} size="sm" onClick={() => setView("daily")}>日视图</Button>
          <Button variant={view === "monthly" ? "default" : "outline"} size="sm" onClick={() => setView("monthly")}>月汇总</Button>
        </div>
      </div>

      <form onSubmit={submit} className="grid grid-cols-6 gap-2">
        {[
          ["date", "日期", "date"],
          ["revenue", "营业额", "number"],
          ["orders", "订单", "number"],
          ["food_cost", "食材", "number"],
          ["labor", "人工", "number"],
          ["rent_allocated", "租金摊销", "number"],
          ["utility", "水电", "number"],
          ["other_cost", "杂费", "number"],
          ["takeout_orders", "外卖单", "number"],
          ["platform_fee", "平台费", "number"],
          ["marketing_cost", "活动费", "number"],
          ["inventory_loss", "报损", "number"],
        ].map(([key, label, type]) => (
          <label key={key} className="space-y-1 text-xs text-muted-foreground">
            <span>{label}</span>
            <Input
              type={type}
              value={String(entry[key as keyof DailyOperationEntry] ?? "")}
              onChange={(ev) => {
                const value = type === "number" ? Number(ev.target.value) : ev.target.value;
                setEntry((prev) => ({ ...prev, [key]: value }));
              }}
            />
          </label>
        ))}
        <label className="col-span-5 space-y-1 text-xs text-muted-foreground">
          <span>备注</span>
          <Input value={entry.notes || ""} onChange={(ev) => setEntry((prev) => ({ ...prev, notes: ev.target.value }))} />
        </label>
        <div className="flex items-end">
          <Button className="w-full" type="submit">保存</Button>
        </div>
      </form>

      {status ? <Card className="p-3 text-sm">{status}</Card> : null}

      <div className="grid grid-cols-3 gap-3">
        <Card className="p-4"><p className="text-xs text-muted-foreground">周期总营收</p><p className="text-2xl font-semibold mt-1">{money(summary?.total_revenue || 0)}</p></Card>
        <Card className="p-4"><p className="text-xs text-muted-foreground">周期总成本</p><p className="text-2xl font-semibold mt-1">{money(summary?.total_cost || 0)}</p></Card>
        <Card className="p-4"><p className="text-xs text-muted-foreground">周期净利润</p><p className={`text-2xl font-semibold mt-1 ${(summary?.net_profit || 0) >= 0 ? "text-green-700" : "text-red-700"}`}>{money(summary?.net_profit || 0)}</p></Card>
      </div>

      {view === "daily" ? (
        <div className="space-y-1">
          <div className="grid grid-cols-7 text-xs text-muted-foreground px-3 py-1">
            <span>日期</span><span className="text-right">营收</span><span className="text-right">订单</span><span className="text-right">食材</span><span className="text-right">人工</span><span className="text-right">外卖成本</span><span className="text-right">净利</span>
          </div>
          {entries.length === 0 ? (
            <Card className="p-4 text-sm text-muted-foreground">还没有经营流水。先用上面的表单录入第一天试营业或测算数据。</Card>
          ) : entries.slice().reverse().map((item) => {
            const profit = item.revenue - item.food_cost - item.labor - item.rent_allocated - item.utility - item.other_cost - item.platform_fee - item.marketing_cost - item.inventory_loss;
            return (
              <Card key={item.date} className="p-2 hover:bg-muted/30 transition-colors">
                <div className="grid grid-cols-7 text-sm items-center">
                  <span className="font-medium">{item.date}</span>
                  <span className="text-right">{money(item.revenue)}</span>
                  <span className="text-right text-muted-foreground">{item.orders}</span>
                  <span className="text-right text-muted-foreground">{money(item.food_cost)}</span>
                  <span className="text-right text-muted-foreground">{money(item.labor)}</span>
                  <span className="text-right text-muted-foreground">{money(item.platform_fee + item.marketing_cost)}</span>
                  <span className={`text-right font-medium ${profit >= 0 ? "text-green-700" : "text-red-700"}`}>{money(profit)}</span>
                </div>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card className="p-4 bg-accent/30">
          <p className="text-sm font-medium mb-2">月 P&L 推演</p>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="space-y-1">
              <div className="flex justify-between"><span className="text-muted-foreground">月营收</span><span>{money(monthRevenue)}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">月净利</span><span>{money(monthProfit)}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">日均营收</span><span>{money(summary?.avg_order_value && summary?.total_orders ? summary.total_revenue / Math.max(summary.entry_count, 1) : 0)}</span></div>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between"><span className="text-muted-foreground">食材成本率</span><span>{((summary?.food_cost_rate || 0) * 100).toFixed(1)}%</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">外卖占比</span><span>{((summary?.takeout_ratio || 0) * 100).toFixed(1)}%</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">样本天数</span><span>{summary?.entry_count || 0} 天</span></div>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
