/* ─── 风险评分规则（运营增强版） ─── */

import type {
  FranchiseAnalysis, InvestmentModel, LocationAssessment,
  OperationDailyRecord, RiskItem, RiskLevel,
  FranchisePermissionMatrix, HQFulfillmentTracker,
} from "./types";
import { calculateInvestment, calcRentPressureIndex, calcPrimeCost } from "./calculations";

// ─── 加盟风险 ───
export function assessFranchiseRisks(fa: FranchiseAnalysis): RiskItem[] {
  const risks: RiskItem[] = [];

  if (fa.promisesPaybackPeriod && fa.promisedPaybackMonths && fa.promisedPaybackMonths < 8) {
    risks.push({
      id: "fran-payback", name: "品牌方承诺回本时间过短",
      module: "franchise", severity: "critical", probability: "high",
      evidence: `承诺${fa.promisedPaybackMonths}个月回本`,
      impact: "极可能是快招骗局，正常餐饮回本周期8-18个月",
      suggestedAction: "要求品牌方提供3家以上真实门店流水证明",
      status: "unverified",
    });
  }

  if (!fa.providesRealStoreData) {
    risks.push({
      id: "fran-data", name: "品牌方不提供真实门店数据",
      module: "franchise", severity: "high", probability: "high",
      evidence: "品牌方拒绝提供现有门店经营数据",
      impact: "无法验证品牌方承诺的真实性",
      suggestedAction: "实地走访3家以上门店，记录真实客流和客单价",
      status: "unverified",
    });
  }

  if (!fa.allowsExistingFranchiseeContact) {
    risks.push({
      id: "fran-contact", name: "无法联系老加盟商",
      module: "franchise", severity: "high", probability: "high",
      evidence: "品牌方不允许或无法提供老加盟商联系方式",
      impact: "可能隐瞒加盟商真实亏损情况",
      suggestedAction: "自行通过大众点评/美团找到门店，实地访谈加盟商",
      status: "unverified",
    });
  }

  if (fa.forcesProcurement && !fa.providesPurchasePriceList) {
    risks.push({
      id: "fran-procurement", name: "强制采购但无价格表",
      module: "franchise", severity: "high", probability: "high",
      evidence: "必须从总部采购但未提供完整采购价目表",
      impact: "实际毛利率可能低于测算模型",
      suggestedAction: "要求总部提供常用SKU采购价，并与市场价对比",
      status: "verified",
    });
  }

  if (!fa.hasTerritoryProtection) {
    risks.push({
      id: "fran-region", name: "无区域保护",
      module: "franchise", severity: "high", probability: "medium",
      evidence: "品牌方未承诺区域保护",
      impact: "未来附近可能开同品牌店，分流客源",
      suggestedAction: "要求写入合同：方圆X米内不再开同品牌店",
      status: "verified",
    });
  }

  if (!fa.hasExitMechanism) {
    risks.push({
      id: "fran-exit", name: "合同无退出条款",
      module: "franchise", severity: "high", probability: "medium",
      evidence: "合同未明确退出机制",
      impact: "经营困难时无法止损退出，可能持续亏损",
      suggestedAction: "要求加入退出条款：提前X个月通知，保证金可退",
      status: "verified",
    });
  }

  if (!fa.hasFilingRecord) {
    risks.push({
      id: "fran-filing", name: "无商业特许经营备案",
      module: "franchise", severity: "high", probability: "medium",
      evidence: "未查询到商务部备案记录",
      impact: "可能不具备特许经营资质",
      suggestedAction: "查询商务部商业特许经营信息管理系统",
      status: "unverified",
    });
  }

  const totalFee = fa.franchiseFee + fa.deposit + fa.equipmentFee + fa.firstInventoryFee + fa.renovationRequirement;
  if (fa.franchiseFee / totalFee > 0.3) {
    risks.push({
      id: "fran-fee-ratio", name: "加盟费占总投资比例过高",
      module: "franchise", severity: "medium", probability: "medium",
      evidence: `加盟费${fa.franchiseFee}元，占总投资${Math.round(fa.franchiseFee / totalFee * 100)}%`,
      impact: "前期投入大，回本压力高",
      suggestedAction: "对比同类品牌加盟费，评估是否合理",
      status: "unverified",
    });
  }

  return risks;
}

// ─── 招商话术识别 ───
export function identifySalesTricks(pitches: string[]): Array<{ trick: string; risk: string }> {
  const tricks: Array<{ trick: string; risk: string }> = [];
  const rules: Record<string, string> = {
    "全程扶持": "需要进一步确认扶持内容是选址、培训、督导、营销，还是仅提供开业物料",
    "小投资高回报": "需要拆解完整初始投资和最差情境现金流，不能只看加盟费",
    "快速回本": "必须要求品牌方提供样本门店数据，包括城市、面积、租金、营业额、毛利、人工",
    "区域保护": "需要确认保护半径、线上外卖是否算冲突、商场店和街边店是否互斥",
    "统一供应链": "需要确认采购价、毛利空间、是否允许替代采购、涨价机制",
    "保姆式开店": "需要确认保姆式具体包含哪些服务，是否有额外费用",
    "0经验可做": "需要确认培训周期、培训内容、是否有实操考核",
  };
  for (const p of pitches) {
    for (const [keyword, risk] of Object.entries(rules)) {
      if (p.includes(keyword)) {
        tricks.push({ trick: p, risk });
      }
    }
  }
  return tricks;
}

// ─── 隐藏成本 ───
export function identifyHiddenCosts(fa: FranchiseAnalysis): string[] {
  const costs: string[] = [];
  if (!fa.providesPurchasePriceList) costs.push("总部指定设备/物料溢价");
  if (fa.forcesProcurement) costs.push("原材料采购价可能高于市场价");
  costs.push("二次装修成本（合同到期续约时）");
  costs.push("开业营销强制投入");
  costs.push("物料物流费");
  costs.push("平台活动补贴");
  costs.push("总部新品物料强制采购");
  if (!fa.hasExitMechanism) costs.push("退出时装修/设备残值无法回收");
  return costs;
}

// ─── 追问清单 ───
export function generateNextQuestions(fa: FranchiseAnalysis): string[] {
  const questions: string[] = [
    "你们是否有商业特许经营备案？备案主体是哪家公司？",
    "目前直营店数量是多少？分别开了多久？",
    "加盟店闭店率是多少？过去12个月关了多少家？",
  ];
  if (!fa.providesRealStoreData) {
    questions.push("能否提供3家不同城市门店的真实流水、租金、人工、毛利数据？");
  }
  if (!fa.allowsExistingFranchiseeContact) {
    questions.push("是否允许我联系现有加盟商？");
  }
  if (fa.forcesProcurement) {
    questions.push("物料是否必须从总部采购？完整采购价目表能否提供？");
  }
  questions.push("保证金什么情况下不退？");
  questions.push("合同到期后续约条件是什么？");
  questions.push("如果经营亏损，总部提供什么具体支持？是否写进合同？");
  return questions;
}

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

// ─── 加盟后经营权限风险 ───
export function assessPermissionRisks(perm: FranchisePermissionMatrix): RiskItem[] {
  const risks: RiskItem[] = [];

  if (perm.pricing.status === "hq_control") {
    risks.push({
      id: "perm-pricing", name: "定价权受限，无法自主调价应对成本变化",
      module: "operations", severity: "high", probability: "high",
      evidence: `定价权限：${perm.pricing.note}`,
      impact: "原材料涨价或竞争加剧时，无法通过调价保护利润",
      suggestedAction: "与总部沟通调价机制，或通过优化套餐组合变相调整客单价",
      status: "verified",
    });
  }

  if (perm.procurement.status === "hq_control") {
    risks.push({
      id: "perm-procurement", name: "强制采购导致成本不可控",
      module: "operations", severity: "high", probability: "high",
      evidence: `采购权限：${perm.procurement.note}`,
      impact: "总部供货价高于市场价时，毛利率被压缩",
      suggestedAction: "要求总部提供采购价目表，与市场价对比，确认是否有涨价机制",
      status: "verified",
    });
  }

  if (perm.delivery.status === "hq_control" || perm.delivery.status === "hq_approval") {
    risks.push({
      id: "perm-delivery", name: "外卖运营权限受限",
      module: "operations", severity: "medium", probability: "medium",
      evidence: `外卖权限：${perm.delivery.note}`,
      impact: "外卖活动设置、满减调整需通过总部，响应慢",
      suggestedAction: "与总部确认外卖运营权限边界，争取部分自主权",
      status: "verified",
    });
  }

  if (perm.menu.status === "hq_control") {
    risks.push({
      id: "perm-menu", name: "菜单调整受限，无法快速响应市场",
      module: "operations", severity: "medium", probability: "medium",
      evidence: `菜单权限：${perm.menu.note}`,
      impact: "竞品推出新品时，无法快速跟进",
      suggestedAction: "在现有产品内探索套餐组合创新，同时推动总部加快新品审批流程",
      status: "verified",
    });
  }

  return risks;
}

// ─── 总部支持兑现度风险 ───
export function assessFulfillmentRisks(ff: HQFulfillmentTracker): RiskItem[] {
  const risks: RiskItem[] = [];

  const items = [
    ff.siteSupport, ff.renovationGuide, ff.training,
    ff.openingSupervision, ff.marketingSupport, ff.deliveryOperation,
    ff.newProductTraining, ff.supplyChain, ff.responseTime, ff.regionProtection,
  ];

  const notFulfilled = items.filter(i => i.status === "not_fulfilled");
  const partial = items.filter(i => i.status === "partial");

  if (notFulfilled.length > 0) {
    risks.push({
      id: "ff-not-fulfilled", name: `总部${notFulfilled.length}项支持未兑现`,
      module: "franchise", severity: "high", probability: "high",
      evidence: `未兑现：${notFulfilled.map(i => i.label).join("、")}`,
      impact: "经营支持不到位，增加独立运营难度",
      suggestedAction: "整理未兑现清单，与总部沟通，要求明确兑现时间表",
      status: "verified",
    });
  }

  if (partial.length >= 3) {
    risks.push({
      id: "ff-partial", name: `总部${partial.length}项支持部分兑现`,
      module: "franchise", severity: "medium", probability: "medium",
      evidence: `部分兑现：${partial.map(i => i.label).join("、")}`,
      impact: "支持质量不达预期，影响经营效率",
      suggestedAction: "逐项确认兑现标准，与总部协商补救措施",
      status: "verified",
    });
  }

  if (ff.supplyChain.status === "partial" && ff.supplyChain.reality.includes("价格")) {
    risks.push({
      id: "ff-supply-price", name: "总部供货价偏高",
      module: "franchise", severity: "high", probability: "medium",
      evidence: ff.supplyChain.reality,
      impact: "毛利率被供应链成本压缩",
      suggestedAction: "要求总部提供采购价目表，与市场价逐项对比",
      status: "verified",
    });
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
