"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface Review {
  platform: string;
  author: string;
  rating: number;
  content: string;
  time: string;
  replied: boolean;
  sentiment: "positive" | "neutral" | "negative";
}

const reviews: Review[] = [
  { platform: "美团", author: "吃货小王", rating: 5, content: "南昌最好吃的章鱼烧！酱料很特别，每次来红谷滩必买", time: "2小时前", replied: true, sentiment: "positive" },
  { platform: "小红书", author: "草莓酱", rating: 2, content: "等了20分钟才出餐，味道还行但服务体验太差了", time: "昨天", replied: false, sentiment: "negative" },
  { platform: "大众点评", author: "南昌探店日记", rating: 5, content: "双拼套餐性价比高，芝士章鱼烧绝了！", time: "昨天", replied: true, sentiment: "positive" },
  { platform: "美团", author: "无名氏", rating: 3, content: "一般般吧，没有网上说的那么好吃，价格偏贵", time: "2天前", replied: false, sentiment: "neutral" },
  { platform: "小红书", author: "周末去哪吃", rating: 1, content: "章鱼烧里面章鱼只有指甲盖大，38块钱不值", time: "3天前", replied: false, sentiment: "negative" },
  { platform: "抖音", author: "吃遍南昌", rating: 4, content: "位置有点难找但味道确实不错，下次带朋友来", time: "4天前", replied: true, sentiment: "positive" },
];

const sentimentBadge: Record<string, { text: string; className: string }> = {
  positive: { text: "好评", className: "bg-green-100 text-green-800" },
  neutral: { text: "中评", className: "bg-gray-100 text-gray-800" },
  negative: { text: "差评", className: "bg-red-100 text-red-800" },
};

export function CustomerFeedback() {
  const [filter, setFilter] = useState<string>("all");
  const filtered = filter === "all" ? reviews : reviews.filter((r) => r.sentiment === filter);
  const avgRating = (reviews.reduce((s, r) => s + r.rating, 0) / reviews.length).toFixed(1);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">客户反馈 · 九江店</h2>
        <Badge variant="secondary">评分 {avgRating} ⭐</Badge>
      </div>

      <div className="flex gap-2">
        {(["all", "negative", "positive"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-xs px-3 py-1 rounded-full transition-colors ${
              filter === f ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-accent"
            }`}
          >
            {f === "all" ? `全部 (${reviews.length})` : f === "negative" ? `差评 (${reviews.filter(r => r.sentiment === "negative").length})` : `好评 (${reviews.filter(r => r.sentiment === "positive").length})`}
          </button>
        ))}
      </div>

      <div className="space-y-2">
        {filtered.map((r, i) => (
          <Card key={i} className="p-4">
            <div className="flex items-start justify-between mb-1">
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">{r.platform}</span>
                <span className="text-sm font-medium">{r.author}</span>
                <span className="text-yellow-500 text-xs">{"★".repeat(r.rating)}{"☆".repeat(5 - r.rating)}</span>
              </div>
              <div className="flex items-center gap-2">
                <Badge className={`text-xs ${sentimentBadge[r.sentiment].className}`}>{sentimentBadge[r.sentiment].text}</Badge>
                <span className="text-xs text-muted-foreground">{r.time}</span>
              </div>
            </div>
            <p className="text-sm mt-1">{r.content}</p>
            <div className="flex items-center gap-2 mt-2">
              {r.replied ? (
                <span className="text-xs text-green-700">✓ 已回复</span>
              ) : (
                <span className="text-xs text-red-600 cursor-pointer hover:underline">⚠️ 待回复 — 建议 24 小时内处理</span>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
