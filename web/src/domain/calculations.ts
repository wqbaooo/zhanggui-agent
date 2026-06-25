/* ─── 计算逻辑（运营增强版） ─── */

import type { InvestmentModel, InvestmentResult, Scenario } from "./types";

/**
 * 核心投资测算 — 对齐文档公式
 */
export function calculateInvestment(model: InvestmentModel): InvestmentResult {
  // 初始投资总额
  const totalInvestment =
    0 + // removed franchiseFee
    0 + // removed deposit
    model.transferFee +
    model.rentDeposit +
    model.firstMonthRent +
    model.renovationCost +
    model.equipmentCost +
    model.firstInventoryCost +
    model.licenseCost +
    model.openingMarketingCost +
    model.trainingCost +
    model.otherStartupCost;

  // 月固定成本
  const monthlyFixedCost =
    model.monthlyRent +
    model.monthlyLabor +
    model.monthlyUtilities +
    model.monthlyManagementFee +
    model.monthlySystemFee +
    model.monthlyMarketing +
    model.otherMonthlyFixedCost;

  // 月营业额
  const monthlyRevenue = model.averageDailyOrders * model.averageOrderValue * model.monthlyOperatingDays;

  // 变动成本率 = (1 - 毛利率) + 平台抽佣 + 损耗 + 折扣
  const variableCostRate = (1 - model.grossMarginRate) + model.platformCommissionRate + model.lossRate + model.discountRate;

  // 月变动成本
  const monthlyVariableCost = monthlyRevenue * variableCostRate;

  // 月毛利
  const monthlyGrossProfit = monthlyRevenue * (1 - (1 - model.grossMarginRate));

  // 月净利润 = 月营业额 - 月变动成本 - 月固定成本
  const monthlyNetProfit = monthlyRevenue - monthlyVariableCost - monthlyFixedCost;

  // 贡献毛利率 = 毛利率 - 平台抽佣 - 损耗 - 折扣
  const contributionMargin = model.grossMarginRate - model.platformCommissionRate - model.lossRate - model.discountRate;

  // 日均保本营业额 = 月固定成本 ÷ 月营业天数 ÷ 贡献毛利率
  const breakevenDailyRevenue = contributionMargin > 0
    ? monthlyFixedCost / model.monthlyOperatingDays / contributionMargin
    : Infinity;

  // 日均保本订单数
  const breakevenDailyOrders = model.averageOrderValue > 0
    ? breakevenDailyRevenue / model.averageOrderValue
    : Infinity;

  // 回本周期
  const paybackMonths = monthlyNetProfit > 0
    ? totalInvestment / monthlyNetProfit
    : Infinity;

  // 现金流安全月数
  const cashflowSafeMonths = monthlyNetProfit < 0
    ? model.reserveCash / Math.abs(monthlyNetProfit)
    : Infinity;

  const canRecover = monthlyNetProfit > 0 && paybackMonths < 60;

  const scenario = calculateScenarios(model, totalInvestment, monthlyFixedCost, variableCostRate);

  return {
    totalInvestment,
    monthlyFixedCost,
    monthlyVariableCostRate: variableCostRate,
    monthlyRevenue,
    monthlyGrossProfit,
    monthlyNetProfit,
    breakevenDailyRevenue,
    breakevenDailyOrders,
    paybackMonths,
    cashflowSafeMonths,
    canRecover,
    scenario,
  };
}

function calculateScenarios(
  model: InvestmentModel,
  totalInvestment: number,
  monthlyFixedCost: number,
  baseVariableRate: number,
): InvestmentResult["scenario"] {
  const result = {} as InvestmentResult["scenario"];

  const configs: Array<{ key: Scenario; orderMul: number; priceMul: number; marginAdj: number }> = [
    { key: "conservative", orderMul: 0.7, priceMul: 0.9, marginAdj: -0.05 },
    { key: "neutral", orderMul: 1.0, priceMul: 1.0, marginAdj: 0 },
    { key: "optimistic", orderMul: 1.2, priceMul: 1.05, marginAdj: 0.03 },
  ];

  for (const c of configs) {
    const orders = model.averageDailyOrders * c.orderMul;
    const price = model.averageOrderValue * c.priceMul;
    const margin = Math.min(model.grossMarginRate + c.marginAdj, 0.85);
    const varRate = (1 - margin) + model.platformCommissionRate + model.lossRate + model.discountRate;
    const revenue = orders * price * model.monthlyOperatingDays;
    const profit = revenue - revenue * varRate - monthlyFixedCost;
    const payback = profit > 0 ? totalInvestment / profit : Infinity;

    result[c.key] = {
      monthlyProfit: Math.round(profit),
      paybackMonths: payback === Infinity ? -1 : Math.round(payback * 10) / 10,
    };
  }

  return result;
}

/**
 * 租金压力指数
 */
export function calcRentPressureIndex(monthlyRent: number, expectedDailyRevenue: number): number {
  if (expectedDailyRevenue <= 0) return 100;
  return Math.round((monthlyRent / (expectedDailyRevenue * 30)) * 100);
}

/**
 * 选址评分
 */
export function calcLocationScore(input: {
  rentPressure: number;
  weekdayTraffic: number;
  weekendTraffic: number;
  competitorCount: number;
  visibility: number;
  deliveryFit: number;
  customerFit: number;
  anchorPoints: number;
}): number {
  let score = 50;

  if (input.rentPressure < 10) score += 15;
  else if (input.rentPressure < 15) score += 10;
  else if (input.rentPressure < 20) score += 5;
  else if (input.rentPressure > 25) score -= 15;
  else if (input.rentPressure > 30) score -= 25;

  // 人流
  if (input.weekdayTraffic > 2000) score += 8;
  else if (input.weekdayTraffic > 1000) score += 4;
  else score -= 4;

  // 周末人流波动
  const trafficRatio = input.weekendTraffic / Math.max(input.weekdayTraffic, 1);
  if (trafficRatio > 1.5 || trafficRatio < 0.5) score -= 5;

  // 竞品
  if (input.competitorCount >= 2 && input.competitorCount <= 5) score += 5;
  else if (input.competitorCount > 10) score -= 10;

  score += (input.visibility - 3) * 3;
  score += (input.deliveryFit - 3) * 3;
  score += (input.customerFit - 3) * 4;
  score += input.anchorPoints * 3;

  return Math.max(0, Math.min(100, score));
}

/**
 * Prime Cost 计算
 */
export function calcPrimeCost(cogs: number, laborCost: number, revenue: number): {
  primeCost: number;
  primeCostRate: number;
  status: "healthy" | "warning" | "critical";
} {
  const primeCost = cogs + laborCost;
  const primeCostRate = revenue > 0 ? primeCost / revenue : 0;
  const status = primeCostRate <= 0.60 ? "healthy" : primeCostRate <= 0.65 ? "warning" : "critical";
  return { primeCost, primeCostRate, status };
}

/**
 * 运营诊断
 */
export function diagnoseOperation(params: {
  revenue: number;
  breakevenRevenue: number;
  grossMargin: number;
  modelMargin: number;
  orders: number;
  targetOrders: number;
  aov: number;
  targetAOV: number;
  laborCostRate: number;
  badReviews: number;
  previousBadReviews: number;
}): {
  healthLevel: "green" | "yellow" | "red";
  mainProblem: string;
  actions: string[];
} {
  const {
    revenue, breakevenRevenue, grossMargin, modelMargin,
    orders, targetOrders, aov, targetAOV,
    laborCostRate, badReviews, previousBadReviews,
  } = params;

  const belowBreakeven = revenue < breakevenRevenue;
  const marginGap = grossMargin - modelMargin;
  const orderGap = (orders - targetOrders) / targetOrders;
  const aovGap = (aov - targetAOV) / targetAOV;

  let healthLevel: "green" | "yellow" | "red" = "green";
  let mainProblem = "";
  const actions: string[] = [];

  if (belowBreakeven) {
    healthLevel = "red";
    if (orders < targetOrders * 0.8) {
      mainProblem = "订单数不足";
      actions.push("检查门头转化、外卖曝光、活动触达");
      actions.push("先做小范围套餐测试，不直接大额投流");
    } else if (marginGap < -0.05) {
      mainProblem = "毛利率偏低";
      actions.push("检查外卖满减、原材料损耗和低毛利产品占比");
      actions.push("拉出销量TOP 20单品毛利表");
    } else {
      mainProblem = "营业额未达保本线";
      actions.push("拆分订单数、客单价、毛利率，确认主要偏差来源");
    }
  } else if (marginGap < -0.05) {
    healthLevel = "yellow";
    mainProblem = "毛利异常";
    actions.push("检查采购价、损耗、活动折扣、低毛利产品占比");
  } else if (laborCostRate > 0.25) {
    healthLevel = "yellow";
    mainProblem = "人工成本偏高";
    actions.push("按时段重排班，低峰减人，高峰保体验");
  } else if (badReviews > previousBadReviews * 1.5) {
    healthLevel = "yellow";
    mainProblem = "差评增加";
    actions.push("按口味、速度、服务、包装、漏单分类处理");
  } else {
    healthLevel = "green";
    mainProblem = "经营正常";
    actions.push("保持当前策略，关注复购和客单价提升");
  }

  return { healthLevel, mainProblem, actions };
}

/**
 * 格式化金额
 */
export function fmtMoney(value: number): string {
  if (Math.abs(value) >= 10000) {
    return `¥${(value / 10000).toFixed(1)}万`;
  }
  return `¥${Math.round(value).toLocaleString()}`;
}

export function fmtPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function safeDiv(a: number, b: number): number {
  if (b === 0) return 0;
  return a / b;
}

/* ─── 专业餐饮指标 ─── */
export function calcRevenuePerSqm(monthlyRevenue: number, areaSqm: number) { const value = safeDiv(monthlyRevenue, areaSqm); const status = value >= 5000 ? "healthy" : value >= 2000 ? "warning" : "critical"; return { value, status, label: `${Math.round(value)}元/㎡/月` }; }
export function calcRevenuePerStaff(monthlyRevenue: number, staffCount: number) { const value = safeDiv(monthlyRevenue, staffCount); const status = value >= 30000 ? "healthy" : value >= 20000 ? "warning" : "critical"; return { value, status, label: `${fmtMoney(value)}/人/月` }; }
export function calcFoodCostRate(materialCost: number, revenue: number) { const value = safeDiv(materialCost, revenue); const status = value <= 0.35 ? "healthy" : value <= 0.40 ? "warning" : "critical"; return { value, status, label: fmtPct(value) }; }
export function calcLaborCostRate(laborCost: number, revenue: number) { const value = safeDiv(laborCost, revenue); const status = value <= 0.25 ? "healthy" : value <= 0.30 ? "warning" : "critical"; return { value, status, label: fmtPct(value) }; }
export function calcRentCostRate(monthlyRent: number, monthlyRevenue: number) { const value = safeDiv(monthlyRent, monthlyRevenue); const status = value <= 0.15 ? "healthy" : value <= 0.20 ? "warning" : "critical"; return { value, status, label: fmtPct(value) }; }
export function calcThreeCostRate(foodRate: number, laborRate: number, rentRate: number) { const value = foodRate + laborRate + rentRate; const status = value <= 0.70 ? "healthy" : value <= 0.80 ? "warning" : "critical"; return { value, status, label: fmtPct(value) }; }
export function calcDeliveryProfitPerOrder(deliveryRevenue: number, deliveryOrders: number, materialCost: number, packagingCost: number, platformCommission: number, deliverySubsidy: number, discountCost: number) { const totalCost = materialCost + packagingCost + platformCommission + deliverySubsidy + discountCost; const profit = deliveryRevenue - totalCost; const value = safeDiv(profit, deliveryOrders); const status = value >= 3 ? "healthy" : value >= 0 ? "warning" : "critical"; return { value, profit, status, label: `${value >= 0 ? "+" : ""}${value.toFixed(1)}元/单` }; }
export function calcDeliveryRatio(deliveryRevenue: number, totalRevenue: number) { const value = safeDiv(deliveryRevenue, totalRevenue); const status = value <= 0.40 ? "healthy" : value <= 0.60 ? "warning" : "critical"; return { value, status, label: fmtPct(value) }; }
export function calcPlatformCommissionRate(commission: number, deliveryRevenue: number) { const value = safeDiv(commission, deliveryRevenue); const status = value <= 0.20 ? "healthy" : value <= 0.25 ? "warning" : "critical"; return { value, status, label: fmtPct(value) }; }
export function calcWasteRate(lossAmount: number, materialCost: number) { const value = safeDiv(lossAmount, materialCost + lossAmount); const status = value <= 0.03 ? "healthy" : value <= 0.05 ? "warning" : "critical"; return { value, status, label: fmtPct(value) }; }
export function calcBadReviewRate(badReviews: number, totalOrders: number) { const value = safeDiv(badReviews, totalOrders); const status = value <= 0.03 ? "healthy" : value <= 0.05 ? "warning" : "critical"; return { value, status, label: fmtPct(value) }; }
export function calcRepeatRate(repeatOrders: number, totalOrders: number) { const value = safeDiv(repeatOrders, totalOrders); const status = value >= 0.30 ? "healthy" : value >= 0.20 ? "warning" : "critical"; return { value, status, label: fmtPct(value) }; }
export function calcTotalCostRate(totalCost: number, revenue: number) { const value = safeDiv(totalCost, revenue); const status = value <= 0.85 ? "healthy" : value <= 0.95 ? "warning" : "critical"; return { value, status, label: fmtPct(value) }; }
export function calcNetProfitRate(netProfit: number, revenue: number) { const value = safeDiv(netProfit, revenue); const status = value >= 0.08 ? "healthy" : value >= 0.03 ? "warning" : "critical"; return { value, status, label: fmtPct(value) }; }

export function calcDailyMetrics(record: { revenue: number; orders: number; dineInOrders: number; deliveryOrders: number; dineInRevenue: number; deliveryRevenue: number; materialCost: number; laborCost: number; rentAllocated: number; packagingCost: number; platformCommission: number; deliverySubsidy: number; discountCost: number; lossAmount: number; badReviews: number; repeatOrders: number }) {
  const foodCostRate = calcFoodCostRate(record.materialCost, record.revenue);
  const laborCostRate = calcLaborCostRate(record.laborCost, record.revenue);
  const rentCostRate = calcRentCostRate(record.rentAllocated, record.revenue);
  const threeCostRate = calcThreeCostRate(foodCostRate.value, laborCostRate.value, rentCostRate.value);
  const primeCost = calcPrimeCost(record.materialCost, record.laborCost, record.revenue);
  const deliveryRatio = calcDeliveryRatio(record.deliveryRevenue, record.revenue);
  const deliveryProfit = calcDeliveryProfitPerOrder(record.deliveryRevenue, record.deliveryOrders, record.materialCost, record.packagingCost, record.platformCommission, record.deliverySubsidy, record.discountCost);
  const commissionRate = calcPlatformCommissionRate(record.platformCommission, record.deliveryRevenue);
  const wasteRate = calcWasteRate(record.lossAmount, record.materialCost);
  const badReviewRate = calcBadReviewRate(record.badReviews, record.orders);
  const repeatRate = calcRepeatRate(record.repeatOrders, record.orders);
  const totalCost = record.materialCost + record.laborCost + record.rentAllocated + record.packagingCost + record.platformCommission + record.deliverySubsidy + record.discountCost + record.lossAmount;
  const netProfit = record.revenue - totalCost;
  return { foodCostRate, laborCostRate, rentCostRate, threeCostRate, primeCost, deliveryRatio, deliveryProfit, commissionRate, wasteRate, badReviewRate, repeatRate, totalCostRate: calcTotalCostRate(totalCost, record.revenue), netProfitRate: calcNetProfitRate(netProfit, record.revenue), netProfit, totalCost };
}

/* ─── 现金流预测 ─── */
export interface CashFlowMonth { month: number; revenue: number; costs: { food: number; labor: number; rent: number; platform: number; other: number }; totalCost: number; netProfit: number; cumulativeProfit: number; cashBalance: number; isBreakeven: boolean; }

export function generateCashFlowProjection(model: InvestmentModel, months = 24): CashFlowMonth[] {
  const totalInvestment = 0 + 0 + model.transferFee + model.rentDeposit + model.firstMonthRent + model.renovationCost + model.equipmentCost + model.firstInventoryCost + model.licenseCost + model.openingMarketingCost + model.trainingCost + model.otherStartupCost;
  let cumulativeProfit = 0; const result: CashFlowMonth[] = [];
  for (let m = 1; m <= months; m++) {
    const rampUp = m <= 1 ? 0.6 : m <= 2 ? 0.75 : m <= 3 ? 0.85 : m <= 6 ? 0.95 : 1.0;
    const seasonFactor = [0.90, 0.85, 0.95, 1.00, 1.05, 1.10, 1.15, 1.10, 1.05, 1.00, 0.95, 0.90][(m - 1) % 12];
    const growthFactor = 1 + (m - 1) * 0.005;
    const dailyOrders = model.averageDailyOrders * rampUp * seasonFactor * growthFactor;
    const monthlyRevenue = dailyOrders * model.averageOrderValue * model.monthlyOperatingDays;
    const foodCost = monthlyRevenue * (1 - model.grossMarginRate);
    const platformCost = monthlyRevenue * model.platformCommissionRate;
    const otherVarCost = monthlyRevenue * (model.lossRate + model.discountRate);
    const totalCost = foodCost + model.monthlyLabor + model.monthlyRent + platformCost + otherVarCost + model.monthlyUtilities + model.monthlyManagementFee + model.monthlySystemFee + model.monthlyMarketing + model.otherMonthlyFixedCost;
    const netProfit = monthlyRevenue - totalCost; cumulativeProfit += netProfit;
    result.push({ month: m, revenue: Math.round(monthlyRevenue), costs: { food: Math.round(foodCost), labor: Math.round(model.monthlyLabor), rent: Math.round(model.monthlyRent), platform: Math.round(platformCost), other: Math.round(model.monthlyUtilities + model.monthlyManagementFee + model.monthlySystemFee + model.monthlyMarketing + model.otherMonthlyFixedCost + otherVarCost) }, totalCost: Math.round(totalCost), netProfit: Math.round(netProfit), cumulativeProfit: Math.round(cumulativeProfit), cashBalance: Math.round(model.reserveCash + cumulativeProfit), isBreakeven: cumulativeProfit >= totalInvestment });
  }
  return result;
}

/* ─── 敏感性分析 ─── */
export interface SensitivityVariable { name: string; label: string; baseValue: number; lowValue: number; highValue: number; impactOnProfit: number; impactOnPayback: number; direction: "positive" | "negative"; }

export function calculateSensitivity(model: InvestmentModel): SensitivityVariable[] {
  const baseResult = calculateInvestment(model); const baseProfit = baseResult.monthlyNetProfit;
  const vars = [
    { name: "dailyOrders", label: "日均订单", get: () => model.averageDailyOrders, set: (v: number) => { model.averageDailyOrders = v; }, chg: 0.20 },
    { name: "avgOrderValue", label: "客单价", get: () => model.averageOrderValue, set: (v: number) => { model.averageOrderValue = v; }, chg: 0.15 },
    { name: "grossMargin", label: "毛利率", get: () => model.grossMarginRate, set: (v: number) => { model.grossMarginRate = v; }, chg: 0.10 },
    { name: "monthlyRent", label: "月租金", get: () => model.monthlyRent, set: (v: number) => { model.monthlyRent = v; }, chg: 0.20 },
    { name: "monthlyLabor", label: "人工成本", get: () => model.monthlyLabor, set: (v: number) => { model.monthlyLabor = v; }, chg: 0.15 },
    { name: "platformCommission", label: "平台佣金率", get: () => model.platformCommissionRate, set: (v: number) => { model.platformCommissionRate = v; }, chg: 0.10 },
  ];
  const results: SensitivityVariable[] = [];
  for (const v of vars) {
    const baseVal = v.get(); v.set(baseVal * (1 - v.chg));
    const lowResult = calculateInvestment({ ...model }); v.set(baseVal);
    const impactOnProfit = lowResult.monthlyNetProfit - baseProfit;
    results.push({ name: v.name, label: v.label, baseValue: baseVal, lowValue: baseVal * (1 - v.chg), highValue: baseVal * (1 + v.chg), impactOnProfit: Math.round(impactOnProfit), impactOnPayback: 0, direction: impactOnProfit < 0 ? "negative" : "positive" });
  }
  results.sort((a, b) => Math.abs(b.impactOnProfit) - Math.abs(a.impactOnProfit));
  return results;
}

export function calculateBreakevenAnalysis(model: InvestmentModel) {
  const r = calculateInvestment(model);
  return { dailyRevenue: r.breakevenDailyRevenue, dailyOrders: r.breakevenDailyOrders, monthlyRevenue: r.breakevenDailyRevenue * model.monthlyOperatingDays, contributionMargin: model.grossMarginRate - model.platformCommissionRate - model.lossRate - model.discountRate, safetyMargin: model.averageDailyOrders * model.averageOrderValue > r.breakevenDailyRevenue ? (model.averageDailyOrders * model.averageOrderValue - r.breakevenDailyRevenue) / (model.averageDailyOrders * model.averageOrderValue) : 0 };
}
