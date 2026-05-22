"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const tasks = [
  { id: "1", title: "实地走访万达金街铺位", phase: "选址筹备", priority: "high", due: "5月28日", status: "pending" },
  { id: "2", title: "完成竞品调研报告", phase: "选址筹备", priority: "high", due: "5月30日", status: "in_progress" },
  { id: "3", title: "更新财务测算（租金确认后）", phase: "选址筹备", priority: "medium", due: "6月2日", status: "pending" },
  { id: "4", title: "确认证照办理流程", phase: "开店执行", priority: "medium", due: "6月10日", status: "pending" },
];

const insights = [
  "红谷滩万达商圈评分 72/100，同类小吃竞品密度高，但章鱼烧品类空缺",
  "建议周末18:00-21:00增加1名兼职，过去3周此时段产能不足30%",
];

const priorityColors: Record<string, string> = {
  high: "bg-red-100 text-red-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-gray-100 text-gray-800",
};

export function ProjectOverview() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">大口章鱼烧 · 南昌红谷滩</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            预算 200,000 · 目标开业 2026-08 · 剩余 76 天
          </p>
        </div>
        <Badge variant="secondary">筹备中</Badge>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">候选铺位</p>
          <p className="text-2xl font-semibold mt-1">3</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">已记录竞品</p>
          <p className="text-2xl font-semibold mt-1">12</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">预算已消耗</p>
          <p className="text-2xl font-semibold mt-1">¥12,000</p>
        </Card>
      </div>

      <div>
        <h3 className="text-sm font-medium mb-3">项目进度</h3>
        <div className="space-y-2">
          {["想法验证", "选址筹备", "开店执行", "运营增长"].map((phase, i) => {
            const pcts = [100, 58, 0, 0];
            return (
              <div key={phase} className="flex items-center gap-3 text-sm">
                <span className="w-20 text-muted-foreground">{phase}</span>
                <div className="flex-1 bg-muted rounded-full h-2">
                  <div
                    className="bg-primary h-2 rounded-full transition-all"
                    style={{ width: `${pcts[i]}%` }}
                  />
                </div>
                <span className="w-10 text-right text-xs text-muted-foreground">{pcts[i]}%</span>
              </div>
            );
          })}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium mb-3">下一步任务</h3>
        <div className="space-y-1">
          {tasks.map((t) => (
            <div key={t.id} className="flex items-center gap-3 text-sm py-2 px-3 rounded-lg hover:bg-muted/50 transition-colors">
              <span className={t.status === "in_progress" ? "text-blue-600" : "text-muted-foreground"}>
                {t.status === "in_progress" ? "●" : "○"}
              </span>
              <span className="flex-1">{t.title}</span>
              <span className={`text-xs px-1.5 py-0.5 rounded ${priorityColors[t.priority]}`}>
                {t.priority === "high" ? "高" : t.priority === "medium" ? "中" : "低"}
              </span>
              <span className="text-xs text-muted-foreground w-16 text-right">{t.due}</span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium mb-3">AI 洞察</h3>
        <div className="space-y-2">
          {insights.map((insight, i) => (
            <Card key={i} className="p-3 text-sm text-muted-foreground">
              {insight}
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
