"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface Site {
  id: string;
  address: string;
  rent: number;
  area: number;
  transferFee: number;
  score: number;
  competitors: number;
  notes: string;
}

const demo: Site[] = [
  {
    id: "1",
    address: "红谷滩万达广场 B1 美食区 A12",
    rent: 8000,
    area: 25,
    transferFee: 30000,
    score: 78,
    competitors: 8,
    notes: "万达客流稳定，周末日均 3 万+，美食区同行品类丰富",
  },
  {
    id: "2",
    address: "红谷滩万达金街 2 楼 208",
    rent: 5500,
    area: 30,
    transferFee: 15000,
    score: 72,
    competitors: 5,
    notes: "金街人流略低于主商场，但租金便宜 30%，适合走外卖+堂食",
  },
  {
    id: "3",
    address: "地铁大厦站出口 50 米临街",
    rent: 12000,
    area: 20,
    transferFee: 50000,
    score: 65,
    competitors: 12,
    notes: "通勤人流大但停留意愿低，竞品密度高（12 家小吃），需差异化",
  },
];

export function SiteAnalysis() {
  const [selected, setSelected] = useState<string[]>([]);

  function toggle(id: string) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  const compareSites = demo.filter((s) => selected.includes(s.id));

  return (
    <div className="flex gap-6 h-full p-6">
      <div className="flex-1 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">选址分析 · 南昌红谷滩</h2>
          <Badge variant="secondary">{demo.length} 个候选铺位</Badge>
        </div>

        <div className="bg-muted rounded-lg h-48 flex items-center justify-center text-sm text-muted-foreground">
          高德地图 — 红谷滩商圈（加载中...）
        </div>

        <div className="space-y-3">
          {demo.map((site) => (
            <Card
              key={site.id}
              className={`p-4 cursor-pointer transition-colors ${
                selected.includes(site.id) ? "border-primary/50 bg-accent/30" : "hover:border-primary/30"
              }`}
              onClick={() => toggle(site.id)}
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium">{site.address}</p>
                  <p className="text-xs text-muted-foreground mt-1">{site.notes}</p>
                </div>
                <Badge variant={site.score >= 75 ? "default" : "secondary"}>评分 {site.score}</Badge>
              </div>
              <div className="flex gap-4 mt-3 text-xs text-muted-foreground">
                <span>月租 ¥{site.rent.toLocaleString()}</span>
                <span>{site.area}㎡</span>
                <span>转让费 ¥{site.transferFee.toLocaleString()}</span>
                <span>500m 内竞品 {site.competitors} 家</span>
              </div>
            </Card>
          ))}
        </div>
      </div>

      {compareSites.length >= 2 && (
        <div className="w-96 shrink-0 space-y-3">
          <h3 className="text-sm font-medium">对比模式</h3>
          <Card className="p-3">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="pb-2">维度</th>
                  {compareSites.map((s) => (
                    <th key={s.id} className="pb-2 font-medium text-foreground">
                      方案 {s.id}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="[&_td]:py-1.5 [&_td]:pr-2">
                {[
                  ["月租", "rent"],
                  ["面积", "area"],
                  ["转让费", "transferFee"],
                  ["评分", "score"],
                  ["竞品数", "competitors"],
                ].map(([label, key]) => (
                  <tr key={key}>
                    <td className="text-muted-foreground">{label}</td>
                    {compareSites.map((s) => (
                      <td key={s.id}>
                        {key === "rent" || key === "transferFee"
                          ? `¥${(s as any)[key].toLocaleString()}`
                          : key === "area"
                          ? `${(s as any)[key]}㎡`
                          : (s as any)[key]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <Button variant="outline" size="sm" className="w-full" onClick={() => setSelected([])}>
            清除对比
          </Button>
        </div>
      )}
    </div>
  );
}
