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

  const scenario = calculateScenarios(model, totalInvestment, monthlyFixedCost);

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
    orders, targetOrders,
    laborCostRate, badReviews, previousBadReviews,
  } = params;

  const belowBreakeven = revenue < breakevenRevenue;
  const marginGap = grossMargin - modelMargin;
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

/* ─── 统一经营计算（消除 5 处重复） ─── */

/** 单日总成本 */
export function calcEntryTotalCost(e: {
  food_cost: number; packaging_cost?: number; labor: number;
  rent_allocated: number; utility: number; other_cost: number;
  platform_fee: number; marketing_cost: number; inventory_loss: number;
  revenue_basis?: "net_settlement" | "gross_sales"; actual_revenue?: number;
}): number {
  const coreCost = e.food_cost + (e.packaging_cost || 0) + e.labor + e.rent_allocated
    + e.utility + e.other_cost + e.inventory_loss;
  const isNetSettlement = e.revenue_basis === "net_settlement" || (e.actual_revenue ?? 0) > 0;
  return coreCost + (isNetSettlement ? 0 : e.platform_fee + e.marketing_cost);
}

/** 单日净利润（优先使用 actual_revenue，兼容旧 revenue 字段） */
export function calcEntryNetProfit(e: {
  revenue: number; actual_revenue?: number; food_cost: number; packaging_cost?: number;
  labor: number; rent_allocated: number; utility: number; other_cost: number;
  platform_fee: number; marketing_cost: number; inventory_loss: number;
  revenue_basis?: "net_settlement" | "gross_sales";
}): number {
  const income = e.actual_revenue ?? e.revenue;
  return income - calcEntryTotalCost(e);
}

/** 单日堂食营收（兼容旧数据：无 dine_in_revenue 时用 revenue - delivery_revenue 或 revenue） */
export function calcDineInRevenue(e: {
  dine_in_revenue?: number; delivery_revenue?: number; revenue: number;
}): number {
  if (e.dine_in_revenue && e.dine_in_revenue > 0) return e.dine_in_revenue;
  if (e.delivery_revenue && e.delivery_revenue > 0) return e.revenue - e.delivery_revenue;
  return e.revenue;
}

/** 期间累计成本结构（用于饼图） */
export function calcCostBreakdown(entries: Array<{
  food_cost: number; packaging_cost?: number; labor: number;
  rent_allocated: number; utility: number; other_cost: number;
  platform_fee: number; marketing_cost: number; inventory_loss: number;
  revenue_basis?: "net_settlement" | "gross_sales"; actual_revenue?: number;
}>, totalRevenue: number): Array<{ name: string; value: number }> {
  if (entries.length === 0 || totalRevenue <= 0) return [];
  const sum = (key: string) => entries.reduce((s, e: Record<string, unknown>) => s + (Number(e[key]) || 0), 0);
  return [
    { name: "食材成本", value: Math.round(sum("food_cost") / totalRevenue * 100) },
    { name: "包装成本", value: Math.round(sum("packaging_cost") / totalRevenue * 100) },
    { name: "人工", value: Math.round(sum("labor") / totalRevenue * 100) },
    { name: "房租", value: Math.round(sum("rent_allocated") / totalRevenue * 100) },
    {
      name: "平台费",
      value: Math.round(entries.reduce((s, e) => s + (e.revenue_basis === "net_settlement" || (e.actual_revenue ?? 0) > 0 ? 0 : e.platform_fee), 0) / totalRevenue * 100),
    },
    {
      name: "营销",
      value: Math.round(entries.reduce((s, e) => s + (e.revenue_basis === "net_settlement" || (e.actual_revenue ?? 0) > 0 ? 0 : e.marketing_cost), 0) / totalRevenue * 100),
    },
    { name: "水电", value: Math.round(sum("utility") / totalRevenue * 100) },
    { name: "报损+其他", value: Math.round((sum("inventory_loss") + sum("other_cost")) / totalRevenue * 100) },
  ].filter((c) => c.value > 0);
}

/** 期间累计值 */
export function sumEntries<T>(entries: T[], key: keyof T): number {
  return entries.reduce((s, e) => s + (Number(e[key]) || 0), 0);
}

/** 日均保本线 = 期间日均总成本（简化为单日保本 = 日均总成本），精确版见 calcBreakEvenAnalysis */
export function calcBreakEvenDaily(entries: Array<Parameters<typeof calcEntryTotalCost>[0]>, days: number): number {
  if (days <= 0) return 0;
  return Math.round(entries.reduce((s, e) => s + calcEntryTotalCost(e), 0) / days);
}

export interface BreakEvenResult {
  days: number;
  total_revenue: number;
  daily_revenue: number;
  fixed_cost: number;
  variable_cost: number;
  daily_fixed_cost: number;
  monthly_fixed_cost: number;
  variable_cost_rate: number;
  contribution_margin_rate: number;
  monthly_breakeven_revenue: number | null;
  daily_breakeven_revenue: number | null;
  is_profitable: boolean;
  gap_to_breakeven: number | null;
  breakeven_pct: number | null;
}

/** 保本点分析：固定/变动成本拆分 + 边际贡献率 + 日保本营收 */
export function calcBreakEvenAnalysis(entries: Array<{
  food_cost: number; packaging_cost?: number; labor: number;
  rent_allocated: number; utility: number; other_cost: number;
  platform_fee: number; marketing_cost: number; inventory_loss: number;
  revenue: number; actual_revenue?: number; revenue_basis?: "net_settlement" | "gross_sales";
}>, days: number): BreakEvenResult | null {
  if (entries.length === 0 || days <= 0) return null;

  const totalRevenue = entries.reduce((s, e) => s + (e.actual_revenue ?? e.revenue), 0);
  const fixedCost = entries.reduce((s, e) => s + e.labor + e.rent_allocated + e.utility, 0);
  const variableCost = entries.reduce((s, e) => {
    const isNetSettlement = e.revenue_basis === "net_settlement" || (e.actual_revenue ?? 0) > 0;
    return s + e.food_cost + (e.packaging_cost || 0) + e.inventory_loss + e.other_cost
      + (isNetSettlement ? 0 : e.platform_fee + e.marketing_cost);
  }, 0);

  const variableCostRate = totalRevenue > 0 ? variableCost / totalRevenue : 0;
  const contributionMarginRate = 1 - variableCostRate;
  const dailyRevenue = totalRevenue / days;
  const dailyFixed = fixedCost / days;
  const monthlyFixed = dailyFixed * 30;

  const monthlyBreakeven = contributionMarginRate > 0 ? monthlyFixed / contributionMarginRate : null;
  const dailyBreakeven = monthlyBreakeven !== null ? monthlyBreakeven / 30 : null;
  const isProfitable = dailyBreakeven !== null && dailyRevenue > dailyBreakeven;
  const gap = dailyBreakeven !== null ? Math.round(dailyRevenue - dailyBreakeven) : null;
  const breakevenPct = dailyBreakeven && dailyBreakeven > 0 ? dailyRevenue / dailyBreakeven : null;

  return {
    days,
    total_revenue: Math.round(totalRevenue),
    daily_revenue: Math.round(dailyRevenue),
    fixed_cost: Math.round(fixedCost),
    variable_cost: Math.round(variableCost),
    daily_fixed_cost: Math.round(dailyFixed),
    monthly_fixed_cost: Math.round(monthlyFixed),
    variable_cost_rate: Math.round(variableCostRate * 10000) / 10000,
    contribution_margin_rate: Math.round(contributionMarginRate * 10000) / 10000,
    monthly_breakeven_revenue: monthlyBreakeven !== null ? Math.round(monthlyBreakeven) : null,
    daily_breakeven_revenue: dailyBreakeven !== null ? Math.round(dailyBreakeven) : null,
    is_profitable: isProfitable,
    gap_to_breakeven: gap,
    breakeven_pct: breakevenPct !== null ? Math.round(breakevenPct * 10000) / 10000 : null,
  };
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

/* ─── 异常检测 ─── */

export interface AnomalyItem {
  type: "revenue" | "food_cost_rate" | "refund" | "orders" | "labor";
  level: "warning" | "danger";
  title: string;
  description: string;
  date: string;
  value: number;
  expected: number;
  deviation: number;
}

export function detectAnomalies(
  entries: Array<{
    date: string;
    revenue: number;
    actual_revenue?: number;
    food_cost: number;
    labor: number;
    orders: number;
    refund_amount?: number;
    refund_orders?: number;
    revenue_basis?: "net_settlement" | "gross_sales";
  }>,
): AnomalyItem[] {
  if (entries.length < 3) return [];

  const sorted = [...entries].sort((a, b) => a.date.localeCompare(b.date));
  const anomalies: AnomalyItem[] = [];

  const getRevenue = (e: typeof sorted[0]) => e.actual_revenue ?? e.revenue;
  const getFoodCostRate = (e: typeof sorted[0]) => {
    const rev = getRevenue(e);
    return rev > 0 ? e.food_cost / rev : 0;
  };

  const avgRevenue = sorted.reduce((s, e) => s + getRevenue(e), 0) / sorted.length;
  const avgFoodRate = sorted.reduce((s, e) => s + getFoodCostRate(e), 0) / sorted.length;
  const avgOrders = sorted.reduce((s, e) => s + e.orders, 0) / sorted.length;

  for (const e of sorted) {
    const rev = getRevenue(e);
    const revDev = avgRevenue > 0 ? (rev - avgRevenue) / avgRevenue : 0;
    if (Math.abs(revDev) > 0.3) {
      anomalies.push({
        type: "revenue",
        level: revDev < -0.4 ? "danger" : "warning",
        title: revDev < 0 ? "营收异常偏低" : "营收异常偏高",
        description: `当日实收 ¥${Math.round(rev).toLocaleString()}，${Math.abs(revDev * 100).toFixed(0)}%偏离均值`,
        date: e.date,
        value: Math.round(rev),
        expected: Math.round(avgRevenue),
        deviation: Math.round(revDev * 10000) / 100,
      });
    }

    const rate = getFoodCostRate(e);
    const rateDev = avgFoodRate > 0 ? (rate - avgFoodRate) / avgFoodRate : 0;
    if (rate > 0 && Math.abs(rateDev) > 0.15) {
      anomalies.push({
        type: "food_cost_rate",
        level: rateDev > 0.25 ? "danger" : "warning",
        title: rateDev > 0 ? "食材成本率偏高" : "食材成本率偏低",
        description: `当日食材率 ${(rate * 100).toFixed(1)}%，${Math.abs(rateDev * 100).toFixed(0)}%偏离均值`,
        date: e.date,
        value: Math.round(rate * 10000) / 10000,
        expected: Math.round(avgFoodRate * 10000) / 10000,
        deviation: Math.round(rateDev * 10000) / 100,
      });
    }

    const orderDev = avgOrders > 0 ? (e.orders - avgOrders) / avgOrders : 0;
    if (Math.abs(orderDev) > 0.3) {
      anomalies.push({
        type: "orders",
        level: orderDev < -0.4 ? "danger" : "warning",
        title: orderDev < 0 ? "订单数异常偏少" : "订单数异常偏多",
        description: `当日 ${e.orders} 单，${Math.abs(orderDev * 100).toFixed(0)}%偏离均值`,
        date: e.date,
        value: e.orders,
        expected: Math.round(avgOrders),
        deviation: Math.round(orderDev * 10000) / 100,
      });
    }

    const refundAmount = e.refund_amount || 0;
    if (refundAmount > 0 && rev > 0 && refundAmount / rev > 0.05) {
      anomalies.push({
        type: "refund",
        level: refundAmount / rev > 0.1 ? "danger" : "warning",
        title: "退款金额偏高",
        description: `当日退款 ¥${refundAmount.toFixed(0)}，占营收 ${(refundAmount / rev * 100).toFixed(1)}%`,
        date: e.date,
        value: refundAmount,
        expected: 0,
        deviation: refundAmount / rev,
      });
    }
  }

  return anomalies.sort((a, b) => {
    const levelOrder = { danger: 0, warning: 1 };
    if (levelOrder[a.level] !== levelOrder[b.level]) return levelOrder[a.level] - levelOrder[b.level];
    return b.date.localeCompare(a.date);
  });
}

/* ─── 利润表（损益表） ─── */

export interface IncomeStatementItem {
  name: string;
  amount: number;
  rate: number;
  children?: IncomeStatementItem[];
  indent?: number;
}

export interface IncomeStatement {
  revenue: number;
  variableCosts: IncomeStatementItem[];
  totalVariableCost: number;
  grossProfit: number;
  grossProfitRate: number;
  fixedCosts: IncomeStatementItem[];
  totalFixedCost: number;
  netProfit: number;
  netProfitRate: number;
}

export function calcIncomeStatement(
  entries: Array<{
    food_cost: number; packaging_cost?: number; labor: number;
    rent_allocated: number; utility: number; other_cost: number;
    platform_fee: number; marketing_cost: number; inventory_loss: number;
    revenue: number; actual_revenue?: number; revenue_basis?: "net_settlement" | "gross_sales";
  }>,
): IncomeStatement | null {
  if (entries.length === 0) return null;

  const totalRevenue = entries.reduce((s, e) => s + (e.actual_revenue ?? e.revenue), 0);
  const isNetSettlement = entries.some((e) => e.revenue_basis === "net_settlement" || (e.actual_revenue ?? 0) > 0);

  const foodCost = entries.reduce((s, e) => s + e.food_cost, 0);
  const packagingCost = entries.reduce((s, e) => s + (e.packaging_cost || 0), 0);
  const platformFee = isNetSettlement ? 0 : entries.reduce((s, e) => s + e.platform_fee, 0);
  const marketingCost = isNetSettlement ? 0 : entries.reduce((s, e) => s + e.marketing_cost, 0);
  const inventoryLoss = entries.reduce((s, e) => s + e.inventory_loss, 0);
  const otherVariable = entries.reduce((s, e) => s + e.other_cost, 0);

  const laborCost = entries.reduce((s, e) => s + e.labor, 0);
  const rentCost = entries.reduce((s, e) => s + e.rent_allocated, 0);
  const utilityCost = entries.reduce((s, e) => s + e.utility, 0);

  const variableCosts: IncomeStatementItem[] = [
    { name: "食材成本", amount: Math.round(foodCost), rate: totalRevenue > 0 ? foodCost / totalRevenue : 0 },
    { name: "包装成本", amount: Math.round(packagingCost), rate: totalRevenue > 0 ? packagingCost / totalRevenue : 0 },
  ];
  if (platformFee > 0) {
    variableCosts.push({ name: "平台费用", amount: Math.round(platformFee), rate: totalRevenue > 0 ? platformFee / totalRevenue : 0 });
  }
  if (marketingCost > 0) {
    variableCosts.push({ name: "营销费用", amount: Math.round(marketingCost), rate: totalRevenue > 0 ? marketingCost / totalRevenue : 0 });
  }
  if (inventoryLoss > 0) {
    variableCosts.push({ name: "损耗报损", amount: Math.round(inventoryLoss), rate: totalRevenue > 0 ? inventoryLoss / totalRevenue : 0 });
  }
  if (otherVariable > 0) {
    variableCosts.push({ name: "其他变动成本", amount: Math.round(otherVariable), rate: totalRevenue > 0 ? otherVariable / totalRevenue : 0 });
  }

  const totalVariableCost = variableCosts.reduce((s, c) => s + c.amount, 0);
  const grossProfit = totalRevenue - totalVariableCost;
  const grossProfitRate = totalRevenue > 0 ? grossProfit / totalRevenue : 0;

  const fixedCosts: IncomeStatementItem[] = [
    { name: "人工成本", amount: Math.round(laborCost), rate: totalRevenue > 0 ? laborCost / totalRevenue : 0 },
    { name: "房租成本", amount: Math.round(rentCost), rate: totalRevenue > 0 ? rentCost / totalRevenue : 0 },
    { name: "水电能耗", amount: Math.round(utilityCost), rate: totalRevenue > 0 ? utilityCost / totalRevenue : 0 },
  ];

  const totalFixedCost = fixedCosts.reduce((s, c) => s + c.amount, 0);
  const netProfit = grossProfit - totalFixedCost;
  const netProfitRate = totalRevenue > 0 ? netProfit / totalRevenue : 0;

  return {
    revenue: Math.round(totalRevenue),
    variableCosts,
    totalVariableCost: Math.round(totalVariableCost),
    grossProfit: Math.round(grossProfit),
    grossProfitRate: Math.round(grossProfitRate * 10000) / 10000,
    fixedCosts,
    totalFixedCost: Math.round(totalFixedCost),
    netProfit: Math.round(netProfit),
    netProfitRate: Math.round(netProfitRate * 10000) / 10000,
  };
}

/* ─── 真实经营财务指标（基于 DailyOperationEntry，非假设模型） ─── */

export interface OperatingFinanceResult {
  totalRevenue: number;
  totalVariableCost: number;
  totalFixedCost: number;
  totalCost: number;
  netProfit: number;
  grossMarginRate: number;
  netProfitRate: number;
  dailyRevenue: number;
  dailyNetProfit: number;
  estimatedMonthlyNetProfit: number;
  paybackMonths: number | null;
  paybackDate: string | null;
  safetyMarginRate: number | null;
  dailyBreakeven: number | null;
  days: number;
  dataSufficient: boolean;
  confidence: "low" | "medium" | "high";
}

export function calcOperatingFinance(
  entries: Array<{
    food_cost: number; packaging_cost?: number; labor: number;
    rent_allocated: number; utility: number; other_cost: number;
    platform_fee: number; marketing_cost: number; inventory_loss: number;
    revenue: number; actual_revenue?: number; revenue_basis?: "net_settlement" | "gross_sales";
  }>,
  days: number,
  transferFee: number,
): OperatingFinanceResult | null {
  if (entries.length === 0 || days <= 0) return null;

  const totalRevenue = entries.reduce((s, e) => s + (e.actual_revenue ?? e.revenue), 0);
  const totalCost = entries.reduce((s, e) => s + calcEntryTotalCost(e), 0);
  const totalFixedCost = entries.reduce((s, e) => s + e.labor + e.rent_allocated + e.utility, 0);
  const totalVariableCost = entries.reduce((s, e) => {
    const isNetSettlement = e.revenue_basis === "net_settlement" || (e.actual_revenue ?? 0) > 0;
    return s + e.food_cost + (e.packaging_cost || 0) + e.inventory_loss + e.other_cost
      + (isNetSettlement ? 0 : e.platform_fee + e.marketing_cost);
  }, 0);

  const netProfit = totalRevenue - totalCost;
  const grossMarginRate = totalRevenue > 0 ? (totalRevenue - totalVariableCost) / totalRevenue : 0;
  const netProfitRate = totalRevenue > 0 ? netProfit / totalRevenue : 0;
  const dailyRevenue = totalRevenue / days;
  const dailyNetProfit = netProfit / days;
  const estimatedMonthlyNetProfit = dailyNetProfit * 30;

  const breakEven = calcBreakEvenAnalysis(entries, days);
  const dailyBreakeven = breakEven?.daily_breakeven_revenue ?? null;
  const safetyMarginRate = (dailyBreakeven !== null && dailyBreakeven > 0 && dailyRevenue > dailyBreakeven)
    ? (dailyRevenue - dailyBreakeven) / dailyBreakeven
    : null;

  const paybackMonths = (estimatedMonthlyNetProfit > 0 && transferFee > 0)
    ? transferFee / estimatedMonthlyNetProfit
    : null;

  let paybackDate: string | null = null;
  if (paybackMonths !== null) {
    const date = new Date();
    date.setMonth(date.getMonth() + Math.ceil(paybackMonths));
    paybackDate = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
  }

  const dataSufficient = days >= 14;
  const confidence: "low" | "medium" | "high" = days >= 30 ? "high" : days >= 14 ? "medium" : "low";

  return {
    totalRevenue: Math.round(totalRevenue),
    totalVariableCost: Math.round(totalVariableCost),
    totalFixedCost: Math.round(totalFixedCost),
    totalCost: Math.round(totalCost),
    netProfit: Math.round(netProfit),
    grossMarginRate: Math.round(grossMarginRate * 10000) / 10000,
    netProfitRate: Math.round(netProfitRate * 10000) / 10000,
    dailyRevenue: Math.round(dailyRevenue),
    dailyNetProfit: Math.round(dailyNetProfit),
    estimatedMonthlyNetProfit: Math.round(estimatedMonthlyNetProfit),
    paybackMonths: paybackMonths !== null ? Math.round(paybackMonths * 10) / 10 : null,
    paybackDate,
    safetyMarginRate: safetyMarginRate !== null ? Math.round(safetyMarginRate * 10000) / 10000 : null,
    dailyBreakeven,
    days,
    dataSufficient,
    confidence,
  };
}
