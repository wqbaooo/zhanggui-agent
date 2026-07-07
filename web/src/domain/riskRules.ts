/* ─── 风险评分规则（运营增强版） ─── */

import type {
  InvestmentModel, LocationAssessment,
  OperationDailyRecord, RiskItem, RiskLevel,
  PermissionMatrix, FulfillmentTracker, FulfillmentItem,
} from "./types";
import { calculateInvestment, calcRentPressureIndex } from "./calculations";

// ─── 投资风险 ───
export function assessInvestmentRisks(model: InvestmentModel): RiskItem[] {
  const risks: RiskItem[] = [];
  const result = calculateInvestment(model);

  if (!result.canRecover) {
    risks.push({
      id: "inv-no-recover", name: "当前模型无法回本",
      module: "investment", severity: "critical", probability: "high",
      evidence: `月净利润${result.monthlyNetProfit < 0 ? "亏损" : ""}${Math.round(result.monthlyNetProfit)}元`,
      impact: "持续亏损直到现金耗尽",
      suggestedAction: "提高日均订单或客单价，或降低固定成本",
      status: "verified",
    });
  }

  if (result.paybackMonths > 18 && result.paybackMonths !== Infinity) {
    risks.push({
      id: "inv-payback-long", name: "回本周期超过18个月",
      module: "investment", severity: "high", probability: "medium",
      evidence: `预计回本${result.paybackMonths.toFixed(1)}个月`,
      impact: "长期占用资金，经营压力大",
      suggestedAction: "优化成本结构或提高营收预期",
      status: "verified",
    });
  }

  if (result.monthlyNetProfit < 0 && result.cashflowSafeMonths < 6) {
    risks.push({
      id: "inv-cashflow", name: "现金流可能在6个月内断裂",
      module: "investment", severity: "critical", probability: "high",
      evidence: `当前现金可支撑${result.cashflowSafeMonths.toFixed(1)}个月`,
      impact: "资金耗尽后被迫关店",
      suggestedAction: "准备额外资金或立即调整经营策略",
      status: "verified",
    });
  }

  if (result.breakevenDailyOrders > 150) {
    risks.push({
      id: "inv-breakeven-high", name: "日均保本订单数过高",
      module: "investment", severity: "high", probability: "medium",
      evidence: `需要日均${Math.round(result.breakevenDailyOrders)}单才能保本`,
      impact: "实际客流可能达不到保本线",
      suggestedAction: "降低固定成本或提高客单价",
      status: "unverified",
    });
  }

  if (result.scenario.conservative.monthlyProfit <= 0) {
    risks.push({
      id: "inv-conservative", name: "保守情境下无法盈利",
      module: "investment", severity: "high", probability: "medium",
      evidence: `保守情境月利润${result.scenario.conservative.monthlyProfit}元`,
      impact: "一旦客流或毛利低于预期，将持续亏损",
      suggestedAction: "准备额外备用现金或降低投资规模",
      status: "verified",
    });
  }

  return risks;
}

// ─── 选址风险 ───
export function assessLocationRisks(loc: LocationAssessment, model: InvestmentModel): RiskItem[] {
  const risks: RiskItem[] = [];
  const rentPressure = calcRentPressureIndex(loc.monthlyRent, model.averageDailyOrders * model.averageOrderValue);

  if (rentPressure > 25) {
    risks.push({
      id: "loc-rent", name: "租金占预期营收比例过高",
      module: "location", severity: "high", probability: "high",
      evidence: `租金占比${rentPressure}%`,
      impact: "利润被租金吃掉，经营压力大",
      suggestedAction: "租金应控制在营收15%以内，或寻找更低租金位置",
      status: "verified",
    });
  }

  if (loc.competitorCount500m > 8) {
    risks.push({
      id: "loc-competition", name: "周边竞品过多",
      module: "location", severity: "medium", probability: "high",
      evidence: `周边${loc.competitorCount500m}家同类竞品`,
      impact: "客源分流，获客成本高",
      suggestedAction: "分析竞品优劣势，确认差异化空间",
      status: "verified",
    });
  }

  if (loc.storefrontVisibility <= 2) {
    risks.push({
      id: "loc-visibility", name: "门头可见度差",
      module: "location", severity: "medium", probability: "high",
      evidence: `可见度评分${loc.storefrontVisibility}/5`,
      impact: "路过客流难以发现门店",
      suggestedAction: "增加门头灯光、招牌面积、或选择转角位置",
      status: "verified",
    });
  }

  if (!loc.hasAnchorTraffic) {
    risks.push({
      id: "loc-anchor", name: "周边缺少稳定锚点客流",
      module: "location", severity: "medium", probability: "medium",
      evidence: "附近无学校/社区/写字楼/商场/地铁/医院",
      impact: "缺少稳定基础客流",
      suggestedAction: "确认是否有其他稳定客流来源",
      status: "unverified",
    });
  }

  return risks;
}

// ─── 运营风险 ───
export function assessOperationRisks(records: OperationDailyRecord[], model: InvestmentModel): RiskItem[] {
  const risks: RiskItem[] = [];
  if (records.length === 0) return risks;

  const recent = records.slice(-7);
  const avgRevenue = recent.reduce((s, r) => s + r.revenue, 0) / recent.length;
  const avgMargin = recent.reduce((s, r) => {
    const margin = r.revenue > 0 ? (r.revenue - r.materialCost - r.packagingCost - r.platformCommission - r.lossAmount) / r.revenue : 0;
    return s + margin;
  }, 0) / recent.length;
  const avgReviews = recent.reduce((s, r) => s + r.badReviews, 0) / recent.length;
  const result = calculateInvestment(model);

  if (avgRevenue < result.breakevenDailyRevenue) {
    const daysBelow = recent.filter(r => r.revenue < result.breakevenDailyRevenue).length;
    risks.push({
      id: "ops-below-breakeven", name: `连续${daysBelow}天低于保本线`,
      module: "operations", severity: daysBelow >= 7 ? "critical" : "high", probability: "high",
      evidence: `日均营收¥${Math.round(avgRevenue)}，保本线¥${Math.round(result.breakevenDailyRevenue)}`,
      impact: "持续亏损",
      suggestedAction: daysBelow >= 7 ? "重估月度现金流，暂停新增投入" : "拆分订单数、客单价、毛利率，确认主要偏差来源",
      status: "verified",
    });
  }

  if (avgMargin < model.grossMarginRate - 0.05) {
    risks.push({
      id: "ops-margin-low", name: "毛利率低于模型5个百分点",
      module: "operations", severity: "high", probability: "high",
      evidence: `近7天平均毛利率${(avgMargin * 100).toFixed(1)}%，模型${(model.grossMarginRate * 100).toFixed(1)}%`,
      impact: "利润空间被压缩",
      suggestedAction: "检查采购价、损耗、活动折扣、低毛利产品占比",
      status: "verified",
    });
  }

  if (avgReviews > 2) {
    risks.push({
      id: "ops-reviews", name: "差评数量偏高",
      module: "operations", severity: "medium", probability: "medium",
      evidence: `近7天日均${avgReviews.toFixed(1)}条差评`,
      impact: "影响评分和客流",
      suggestedAction: "按口味、速度、服务、包装、漏单分类处理",
      status: "verified",
    });
  }

  const deliveryRatio = recent.reduce((s, r) => s + r.deliveryOrders, 0) / Math.max(recent.reduce((s, r) => s + r.orders, 0), 1);
  if (deliveryRatio > 0.6) {
    const deliveryProfit = recent.reduce((s, r) => {
      const dr = r.deliveryRevenue;
      const dc = dr * (1 - model.grossMarginRate) + r.platformCommission + r.deliverySubsidy + r.packagingCost * (r.deliveryOrders / Math.max(r.orders, 1));
      return s + (dr - dc);
    }, 0) / recent.length;
    if (deliveryProfit < 0) {
      risks.push({
        id: "ops-delivery-loss", name: "外卖流水增长但利润为负",
        module: "operations", severity: "high", probability: "high",
        evidence: `外卖占比${(deliveryRatio * 100).toFixed(0)}%，外卖日均利润${Math.round(deliveryProfit)}元`,
        impact: "外卖越做越亏",
        suggestedAction: "单独核算平台活动，不再用总流水判断外卖效果",
        status: "verified",
      });
    }
  }

  return risks;
}

// ─── 蹲点清单 ───
export function generateScoutChecklist(): string[] {
  return [
    "工作日 11:30-13:30 记录经过门口人数",
    "工作日 17:30-19:30 记录经过门口人数",
    "周末 14:00-16:00 记录经过门口人数",
    "停下来看门头的人数",
    "进入同类竞品的人数",
    "竞品出餐速度",
    "竞品客单价",
    "周边人群年龄层",
    "外卖骑手取餐频率",
    "午高峰是否排队",
    "晚间是否断流",
    "雨天是否影响人流",
  ];
}

// ─── 经营权限风险 ───
export function assessPermissionRisks(perm: PermissionMatrix): RiskItem[] {
  void perm;
  // 自营店全部自主，无权限风险
  return [];
}

// ─── 经营项兑现风险 ───
export function assessFulfillmentRisks(ff: FulfillmentTracker): RiskItem[] {
  const risks: RiskItem[] = [];
  for (const item of Object.values(ff) as FulfillmentItem[]) {
    if (item.status === "not_fulfilled") {
      risks.push({
        id: `ful-${item.key}`, name: `${item.label}未兑现`, module: "operations", severity: "high", probability: "medium",
        evidence: item.reality, impact: item.impact, suggestedAction: "评估影响并制定替代方案", status: "verified",
      });
    }
  }
  return risks;
}

// ─── 保本线预警（每日监控） ───
export function assessBreakevenAlert(records: OperationDailyRecord[], model: InvestmentModel): {
  level: "green" | "yellow" | "red";
  message: string;
  cause: string[];
} {
  if (records.length === 0) return { level: "green", message: "暂无数据", cause: [] };

  const result = calculateInvestment(model);
  const recent = records.slice(-7);
  const belowDays = recent.filter(r => r.revenue < result.breakevenDailyRevenue).length;

  if (belowDays >= 7) {
    const causes: string[] = [];
    const avgOrders = recent.reduce((s, r) => s + r.orders, 0) / recent.length;
    const avgAOV = recent.reduce((s, r) => s + r.averageOrderValue, 0) / recent.length;
    const avgMargin = recent.reduce((s, r) => s + (r.revenue > 0 ? (r.revenue - r.materialCost - r.packagingCost - r.platformCommission - r.lossAmount) / r.revenue : 0), 0) / recent.length;

    if (avgOrders < model.averageDailyOrders * 0.8) causes.push("订单数不足");
    if (avgAOV < model.averageOrderValue * 0.9) causes.push("客单价偏低");
    if (avgMargin < model.grossMarginRate - 0.05) causes.push("毛利率偏低");
    if (recent.reduce((s, r) => s + r.platformCommission, 0) / recent.length > model.averageDailyOrders * model.averageOrderValue * model.platformCommissionRate * 1.2) causes.push("平台抽佣过高");

    return {
      level: "red",
      message: `连续7天低于保本线，触发止损评估。日均营收¥${Math.round(recent.reduce((s, r) => s + r.revenue, 0) / recent.length)}，保本线¥${Math.round(result.breakevenDailyRevenue)}。`,
      cause: causes,
    };
  }

  if (belowDays >= 3) {
    return {
      level: "yellow",
      message: `近7天有${belowDays}天未达保本线，需要关注。`,
      cause: ["需拆分订单数、客单价、毛利率确认偏差来源"],
    };
  }

  return { level: "green", message: "经营正常，保本线以上。", cause: [] };
}

// ─── 汇总 ───
export function calcOverallRisk(risks: RiskItem[]): { score: number; level: RiskLevel; topRisks: RiskItem[] } {
  let score = 0;
  for (const r of risks) {
    const sev = r.severity === "critical" ? 40 : r.severity === "high" ? 25 : r.severity === "medium" ? 15 : 5;
    const prob = r.probability === "high" ? 1.5 : r.probability === "medium" ? 1.0 : 0.5;
    score += sev * prob;
  }
  const level: RiskLevel = score >= 100 ? "critical" : score >= 60 ? "high" : score >= 30 ? "medium" : "low";
  const topRisks = [...risks].sort((a, b) => {
    const sa = a.severity === "critical" ? 4 : a.severity === "high" ? 3 : a.severity === "medium" ? 2 : 1;
    const sb = b.severity === "critical" ? 4 : b.severity === "high" ? 3 : b.severity === "medium" ? 2 : 1;
    return sb - sa;
  }).slice(0, 5);
  return { score, level, topRisks };
}
