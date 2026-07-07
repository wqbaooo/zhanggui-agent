"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, Boxes, DollarSign, ShieldAlert, TrendingDown, Utensils } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { DEFAULT_PROJECT_ID, getOperationSummary, getForecast, getStaff, type ForecastItem } from "@/lib/api";

type Alert = {
  id: string;
  level: "high" | "medium" | "low";
  title: string;
  body: string;
  icon: typeof AlertTriangle;
  link: string;
};

const levelColor = { high: "border-red-200 bg-red-50 text-red-800", medium: "border-amber-200 bg-amber-50 text-amber-800", low: "border-blue-200 bg-blue-50 text-blue-800" };
const levelDot = { high: "bg-red-500", medium: "bg-amber-500", low: "bg-blue-500" };

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [initialized, setInitialized] = useState(false);

  const fetchAlerts = useCallback(async () => {
    const items: Alert[] = [];
    try {
      const [ops, fRes, staffRes] = await Promise.all([
        getOperationSummary(DEFAULT_PROJECT_ID, 7),
        getForecast(DEFAULT_PROJECT_ID),
        getStaff(DEFAULT_PROJECT_ID),
      ]);

      // 经营预警
      if (ops.alerts) {
        for (const a of ops.alerts) {
          items.push({ id: `ops-${items.length}`, level: a.level as Alert["level"], title: "经营预警", body: a.message, icon: DollarSign, link: "/profit" });
        }
      }

      // 食材成本率
      if (ops.food_cost_rate > 0.4) {
        items.push({ id: `cost-${items.length}`, level: "medium", title: "食材成本偏高", body: `当前食材成本率 ${(ops.food_cost_rate * 100).toFixed(0)}%，超过40%警戒线。核对总部供货价与损耗。`, icon: Utensils, link: "/profit" });
      }

      // 亏损
      if (ops.profit_ready && ops.entry_count >= 3 && ops.net_profit < 0) {
        items.push({ id: `loss-${items.length}`, level: "high", title: "当期亏损", body: `近${ops.entry_count}天净利 ¥${ops.net_profit.toFixed(0)}，优先检查食材、人工和平台活动。`, icon: TrendingDown, link: "/profit" });
      } else if (ops.entry_count >= 3 && !ops.profit_ready) {
        items.push({ id: `cost-gap-${items.length}`, level: "medium", title: "利润等待成本补齐", body: "三天营业收入已确认，食材、包装、人工、房租和水电尚未完整录入。", icon: TrendingDown, link: "/profit" });
      }

      // 数据不足
      if (ops.entry_count < 7) {
        items.push({ id: `data-${items.length}`, level: "low", title: "数据积累中", body: `仅录入 ${ops.entry_count} 天数据，连续 7 天后开始形成趋势模型。`, icon: TrendingDown, link: "/overview" });
      }

      // 补货预警
      const urgent = fRes.forecast.filter((f: ForecastItem) => f.action === "urgent");
      const recommend = fRes.forecast.filter((f: ForecastItem) => f.action === "recommend");
      for (const f of urgent) {
        items.push({ id: `sku-${f.sku_id}`, level: "high", title: "库存预警", body: `${f.name} 仅剩 ${f.current_stock}${f.unit}，安全库存 ${f.safety_stock}${f.unit}，建议立即补 ${f.recommend_qty}${f.unit}。`, icon: Boxes, link: "/inventory" });
      }
      if (urgent.length === 0 && recommend.length > 0) {
        items.push({ id: "sku-recommend", level: "medium", title: "补货建议", body: `${recommend.length} 个 SKU 建议补货：${recommend.map((f) => f.name).join("、")}`, icon: Boxes, link: "/inventory" });
      }

      // 健康证预警
      const certAlerts = staffRes.health_cert_alerts || [];
      for (const a of certAlerts) {
        items.push({ id: `cert-${a.staff_id}`, level: a.days_remaining < 15 ? "high" : "medium", title: "健康证到期", body: `${a.name} 健康证 ${a.expiry_date} 到期，剩余 ${a.days_remaining} 天。`, icon: ShieldAlert, link: "/training" });
      }

    } catch { /* offline */ }

    setAlerts(items.sort((a, b) => (b.level === "high" ? 3 : b.level === "medium" ? 2 : 1) - (a.level === "high" ? 3 : a.level === "medium" ? 2 : 1)));
    setInitialized(true);
  }, []);

  useEffect(() => { fetchAlerts(); const interval = setInterval(fetchAlerts, 300000); return () => clearInterval(interval); }, [fetchAlerts]);

  const highCount = alerts.filter((a) => a.level === "high").length;
  const mediumCount = alerts.filter((a) => a.level === "medium").length;
  const lowCount = alerts.filter((a) => a.level === "low").length;

  return (
    <ModulePage module={getModule("/alerts")}>
        <div className="space-y-4">
          {!initialized && <div className="h-0.5 w-full animate-pulse rounded-full bg-primary/30" />}
          {/* 总览 */}
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-2xl border border-red-200 bg-red-50 p-3 text-center">
              <p className="text-xs text-red-600">严重</p>
              <p className="mt-1 text-2xl font-bold text-red-800">{highCount}</p>
            </div>
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-center">
              <p className="text-xs text-amber-600">注意</p>
              <p className="mt-1 text-2xl font-bold text-amber-800">{mediumCount}</p>
            </div>
            <div className="rounded-2xl border border-blue-200 bg-blue-50 p-3 text-center">
              <p className="text-xs text-blue-600">提示</p>
              <p className="mt-1 text-2xl font-bold text-blue-800">{lowCount}</p>
            </div>
          </div>

          {initialized && alerts.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-white/60 bg-white/35 p-8 text-center">
              <AlertTriangle className="mx-auto h-8 w-8 text-on-surface-variant/40" />
              <p className="mt-3 text-sm font-medium text-on-background">暂无预警</p>
              <p className="mt-1 text-xs text-on-surface-variant">系统持续监控经营、库存、员工健康证</p>
            </div>
          ) : (
            <div className="space-y-2">
              {alerts.map((alert) => {
                const Icon = alert.icon;
                return (
                  <Link key={alert.id} href={alert.link} className={`flex items-start gap-3 rounded-2xl border p-4 transition-colors ${levelColor[alert.level]} hover:brightness-95`}>
                    <Icon className="mt-0.5 h-5 w-5 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${levelDot[alert.level]}`} />
                        <p className="text-sm font-semibold">{alert.title}</p>
                      </div>
                      <p className="mt-1 text-xs leading-relaxed opacity-80">{alert.body}</p>
                    </div>
                    <ArrowRight className="mt-1 h-4 w-4 shrink-0 opacity-50" />
                  </Link>
                );
              })}
            </div>
          )}
        </div>
    </ModulePage>
  );
}
