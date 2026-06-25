"use client";

import { useState, useCallback, useRef } from "react";
import { API_BASE, DEFAULT_PROJECT_ID } from "@/lib/api";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  toolCalls?: Array<{ name: string; status: "running" | "done"; output?: string }>;
}

export interface AIInsight {
  id: string;
  type: "health" | "warning" | "opportunity" | "action";
  title: string;
  description: string;
  metric?: string;
  value?: string;
  target?: string;
  priority: "high" | "medium" | "low";
}

export function useAIChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isStreaming) return;
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: content.trim(),
      timestamp: new Date().toISOString(),
    };

    const assistantMsg: ChatMessage = {
      id: `assistant-${Date.now()}`,
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
      toolCalls: [],
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/chat/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: content.trim(), project_id: DEFAULT_PROJECT_ID }),
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data = await res.json();
      const response = data.response || "";
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last.role === "assistant") {
          last.content = response;
        }
        return updated;
      });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "请求失败";
      setError(errorMsg);
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last.role === "assistant") {
          last.content = `抱歉，出现了错误：${errorMsg}`;
        }
        return updated;
      });
    } finally {
      setIsStreaming(false);
    }
  }, [isStreaming]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    isStreaming,
    error,
    sendMessage,
    clearMessages,
  };
}

/**
 * 生成 AI 每日洞察（基于项目数据的静态分析）
 */
export function generateDailyInsights(data: {
  avgRevenue: number;
  breakevenRevenue?: number | null;
  foodCostRate?: number | null;
  laborCostRate?: number | null;
  deliveryRatio?: number | null;
  badReviewRate?: number | null;
  repeatRate?: number | null;
  primeCost?: number | null;
}): AIInsight[] {
  const insights: AIInsight[] = [];

  // 营收健康度
  if (data.avgRevenue > 0 && data.breakevenRevenue != null && data.breakevenRevenue > 0) {
    const safetyMargin = (data.avgRevenue - data.breakevenRevenue) / data.breakevenRevenue;
    if (safetyMargin < 0.2) {
      insights.push({
        id: "revenue-warning",
        type: "warning",
        title: "营收接近保本线",
        description: `日均营收距保本线仅${(safetyMargin * 100).toFixed(0)}%的安全边际，需关注客流变化`,
        metric: "安全边际",
        value: `${(safetyMargin * 100).toFixed(0)}%`,
        target: ">20%",
        priority: "high",
      });
    } else if (safetyMargin > 0.5) {
      insights.push({
        id: "revenue-healthy",
        type: "health",
        title: "营收健康",
        description: `日均营收超过保本线${(safetyMargin * 100).toFixed(0)}%，经营状况良好`,
        metric: "安全边际",
        value: `${(safetyMargin * 100).toFixed(0)}%`,
        priority: "low",
      });
    }
  }

  // Prime Cost
  if (data.primeCost != null && data.primeCost > 0.65) {
    insights.push({
      id: "prime-cost-warning",
      type: "warning",
      title: "Prime Cost 偏高",
      description: `食材+人工成本率${(data.primeCost * 100).toFixed(1)}%，超过65%警戒线，利润空间被压缩`,
      metric: "Prime Cost",
      value: `${(data.primeCost * 100).toFixed(1)}%`,
      target: "<65%",
      priority: "high",
    });
  }

  // 外卖占比
  if (data.deliveryRatio != null && data.deliveryRatio > 0.6) {
    insights.push({
      id: "delivery-warning",
      type: "warning",
      title: "外卖依赖度过高",
      description: `外卖占比${(data.deliveryRatio * 100).toFixed(0)}%，平台佣金侵蚀利润，建议提升堂食比例`,
      metric: "外卖占比",
      value: `${(data.deliveryRatio * 100).toFixed(0)}%`,
      target: "<40%",
      priority: "medium",
    });
  }

  // 差评率
  if (data.badReviewRate != null && data.badReviewRate > 0.03) {
    insights.push({
      id: "review-warning",
      type: "warning",
      title: "差评率偏高",
      description: `差评率${(data.badReviewRate * 100).toFixed(1)}%，超过3%警戒线，影响店铺评分和流量`,
      metric: "差评率",
      value: `${(data.badReviewRate * 100).toFixed(1)}%`,
      target: "<3%",
      priority: "high",
    });
  }

  // 复购率
  if (data.repeatRate != null && data.repeatRate < 0.20) {
    insights.push({
      id: "repeat-opportunity",
      type: "opportunity",
      title: "复购率有提升空间",
      description: `复购率${(data.repeatRate * 100).toFixed(0)}%，低于20%，建议推出会员体系或复购券`,
      metric: "复购率",
      value: `${(data.repeatRate * 100).toFixed(0)}%`,
      target: ">30%",
      priority: "medium",
    });
  }

  // 食材成本率
  if (data.foodCostRate != null && data.foodCostRate > 0.40) {
    insights.push({
      id: "food-cost-warning",
      type: "warning",
      title: "食材成本率过高",
      description: `食材成本率${(data.foodCostRate * 100).toFixed(1)}%，超过40%警戒线，需检查采购价格和损耗`,
      metric: "食材成本率",
      value: `${(data.foodCostRate * 100).toFixed(1)}%`,
      target: "30-35%",
      priority: "high",
    });
  }

  // 如果没有预警，给出正面反馈
  if (insights.length === 0) {
    insights.push({
      id: "all-good",
      type: "health",
      title: "经营状况良好",
      description: "各项指标均在健康范围内，继续保持",
      priority: "low",
    });
  }

  return insights;
}
