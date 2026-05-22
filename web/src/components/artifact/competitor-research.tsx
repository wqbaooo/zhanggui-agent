"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Competitor {
  name: string;
  category: string;
  rating: number;
  avgSpend: number;
  monthlySales: number;
  distance: string;
  strengths: string[];
}

const demoCompetitors: Competitor[] = [
  { name: "丸之内章鱼烧", category: "章鱼烧", rating: 4.3, avgSpend: 28, monthlySales: 3200, distance: "150m", strengths: ["品牌老店", "口味稳定", "抖音粉丝2万"] },
  { name: "大阪烧专门店", category: "日式小吃", rating: 4.1, avgSpend: 35, monthlySales: 2800, distance: "200m", strengths: ["品类差异化", "堂食体验好"] },
  { name: "馋嘴猫烤冷面", category: "烤冷面", rating: 4.5, avgSpend: 18, monthlySales: 4500, distance: "80m", strengths: ["价格低", "出餐快", "学生客群"] },
  { name: "韩式炸鸡铺", category: "炸鸡", rating: 3.9, avgSpend: 25, monthlySales: 2100, distance: "300m", strengths: ["外卖单量高"] },
  { name: "麻辣串串香", category: "串串", rating: 4.2, avgSpend: 22, monthlySales: 3800, distance: "120m", strengths: ["品类刚需", "复购率高"] },
  { name: "一口寿司", category: "寿司", rating: 4.0, avgSpend: 32, monthlySales: 1800, distance: "250m", strengths: ["视觉好拍", "小红书曝光"] },
];

export function CompetitorResearch() {
  const [sortBy, setSortBy] = useState<keyof Competitor>("monthlySales");

  const sorted = [...demoCompetitors].sort((a, b) => (b[sortBy] as number) - (a[sortBy] as number));
  const avgPrice = sorted.reduce((s, c) => s + c.avgSpend, 0) / sorted.length;
  const avgRating = sorted.reduce((s, c) => s + c.rating, 0) / sorted.length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">竞品调研 · 南昌红谷滩</h2>
        <Badge variant="secondary">{demoCompetitors.length} 家竞品</Badge>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">平均客单价</p>
          <p className="text-xl font-semibold mt-1">¥{avgPrice.toFixed(0)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">平均评分</p>
          <p className="text-xl font-semibold mt-1">{avgRating.toFixed(1)} ⭐</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">月均总销量</p>
          <p className="text-xl font-semibold mt-1">{(sorted.reduce((s, c) => s + c.monthlySales, 0)).toLocaleString()} 单</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">品类空缺</p>
          <p className="text-xl font-semibold mt-1 text-green-700">章鱼烧 1 家</p>
        </Card>
      </div>

      <div>
        <div className="flex gap-2 mb-3">
          {(["monthlySales", "rating", "avgSpend"] as const).map((k) => (
            <Button key={k} variant={sortBy === k ? "default" : "outline"} size="sm" onClick={() => setSortBy(k)}>
              {k === "monthlySales" ? "按销量" : k === "rating" ? "按评分" : "按客单价"}
            </Button>
          ))}
        </div>
        <div className="space-y-2">
          {sorted.map((c, i) => (
            <Card key={c.name} className="p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">#{i + 1}</span>
                    <span className="font-medium text-sm">{c.name}</span>
                    <Badge variant="outline" className="text-xs">{c.category}</Badge>
                    <span className="text-xs text-muted-foreground">{c.distance}</span>
                  </div>
                  <div className="flex gap-1 mt-2">
                    {c.strengths.map((s) => (
                      <span key={s} className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{s}</span>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-4 text-right text-sm">
                  <div><span className="text-muted-foreground">评分 </span>{c.rating} ⭐</div>
                  <div><span className="text-muted-foreground">客单 </span>¥{c.avgSpend}</div>
                  <div><span className="text-muted-foreground">月销 </span>{c.monthlySales.toLocaleString()} 单</div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>

      <Card className="p-4 bg-accent/30">
        <p className="text-sm font-medium mb-2">差异化建议</p>
        <div className="text-sm text-muted-foreground space-y-1">
          <p>· 章鱼烧品类仅 1 家竞品，蓝海机会明确</p>
          <p>· 竞品均价 ¥28，可定价 ¥25-30 保持竞争力</p>
          <p>· 小红书曝光少 — 可抢先占位同城种草内容</p>
          <p>· 警惕烤冷面/串串的低价分流，做品质差异化</p>
        </div>
      </Card>
    </div>
  );
}
