/* ─── 开店决策操作系统 — 核心类型（运营增强版） ─── */

export type ProjectPhase =
  | "idea"           // 想法期
  | "location_selection" // 选址期
  | "renovation"     // 装修期
  | "trial_operation" // 试营业
  | "active_operation"; // 正式经营

export type RiskLevel = "low" | "medium" | "high" | "critical";
export type RiskStatus = "unverified" | "verified" | "resolved" | "deferred";
export type Scenario = "conservative" | "neutral" | "optimistic";

// ─── 项目 ───
export interface Project {
  id: string;
  name: string;
  category: string;
  city: string;
  stage: ProjectPhase;
  budget: number;
  availableCash: number;
  createdAt: string;
  updatedAt: string;
}

// ─── 投资模型 ───
export interface InvestmentModel {
  // 初始投资
  transferFee: number;
  rentDeposit: number;
  firstMonthRent: number;
  renovationCost: number;
  equipmentCost: number;
  firstInventoryCost: number;
  licenseCost: number;
  openingMarketingCost: number;
  trainingCost: number;
  reserveCash: number;
  otherStartupCost: number;
  // 月固定
  monthlyRent: number;
  monthlyLabor: number;
  monthlyUtilities: number;
  monthlyManagementFee: number;
  monthlySystemFee: number;
  monthlyMarketing: number;
  otherMonthlyFixedCost: number;
  // 经营假设
  averageDailyOrders: number;
  averageOrderValue: number;
  monthlyOperatingDays: number;
  grossMarginRate: number;
  platformCommissionRate: number;
  lossRate: number;
  discountRate: number;
}

// ─── 选址评估 ───
export interface LocationAssessment {
  city: string;
  district: string;
  businessAreaType: string;
  areaSqm: number;
  monthlyRent: number;
  transferFee: number;
  weekdayFootTraffic: number;
  weekendFootTraffic: number;
  targetCustomerFit: number;
  competitorCount500m: number;
  hasAnchorTraffic: boolean;
  storefrontVisibility: number;
  deliveryFit: number;
  nearSchool: boolean;
  nearCommunity: boolean;
  nearOffice: boolean;
  nearMall: boolean;
  nearSubway: boolean;
  nearHospital: boolean;
}

// ─── 运营日报（增强版） ───
export interface OperationDailyRecord {
  date: string;
  revenue: number;
  orders: number;
  averageOrderValue: number;
  dineInOrders: number;
  deliveryOrders: number;
  dineInRevenue: number;
  deliveryRevenue: number;
  materialCost: number;
  packagingCost: number;
  platformCommission: number;
  deliverySubsidy: number;
  discountCost: number;
  laborCost: number;
  rentAllocated: number;
  utilitiesAllocated: number;
  marketingCost: number;
  lossAmount: number;
  badReviews: number;
  newMembers: number;
  repeatOrders: number;
  notes: string;
}

// ─── 菜单项 ───
export interface MenuItemPerformance {
  id: string;
  name: string;
  category: string;
  price: number;
  unitCost: number;
  grossMargin: number;
  unitsSold: number;
  revenue: number;
  grossProfit: number;
  prepComplexity: "low" | "medium" | "high";
  isPromotionItem: boolean;
}

// ─── 风险项 ───
export interface RiskItem {
  id: string;
  name: string;
  module: "franchise" | "investment" | "location" | "operations" | "contract" | "cashflow";
  severity: RiskLevel;
  probability: RiskLevel;
  evidence: string;
  impact: string;
  suggestedAction: string;
  status: RiskStatus;
}

// ─── 反馈项 ───
export interface FeedbackItem {
  id: string;
  type: "ux" | "workflow" | "cognition" | "missing_data" | "false_need" | "blocker";
  severity: "low" | "medium" | "high";
  page: string;
  context: string;
  notes: string;
  expectedResult: string;
  createdAt: string;
}

// ─── 计算结果 ───
export interface InvestmentResult {
  totalInvestment: number;
  monthlyFixedCost: number;
  monthlyVariableCostRate: number;
  monthlyRevenue: number;
  monthlyGrossProfit: number;
  monthlyNetProfit: number;
  breakevenDailyRevenue: number;
  breakevenDailyOrders: number;
  paybackMonths: number;
  cashflowSafeMonths: number;
  canRecover: boolean;
  scenario: {
    conservative: { monthlyProfit: number; paybackMonths: number };
    neutral: { monthlyProfit: number; paybackMonths: number };
    optimistic: { monthlyProfit: number; paybackMonths: number };
  };
}

export interface FranchiseRiskResult {
  overallLevel: RiskLevel;
  overallScore: number;
  hiddenCosts: string[];
  contractRisks: string[];
  commonTricks: string[];
  shouldContinue: boolean;
  nextQuestions: string[];
}

// ─── 运营诊断 ───
export interface OperationDiagnosis {
  date: string;
  healthLevel: "green" | "yellow" | "red";
  breakEvenStatus: "above" | "below";
  mainProblem: string;
  evidence: string[];
  recommendedActions: string[];
  risksToRegister: RiskItem[];
}

// ─── 经营权限矩阵 ───
export type PermissionStatus = "hq_control" | "hq_approval" | "store_autonomous" | "unclear";

export interface PermissionItem {
  key: string;
  label: string;
  status: PermissionStatus;
  note: string;
}

export interface PermissionMatrix {
  menu: PermissionItem;
  pricing: PermissionItem;
  promotion: PermissionItem;
  procurement: PermissionItem;
  delivery: PermissionItem;
  membership: PermissionItem;
  marketing: PermissionItem;
  hours: PermissionItem;
  renovation: PermissionItem;
  newProduct: PermissionItem;
}

// ─── 运营动作 ───
export interface OperationAction {
  title: string;
  reason: string;
  expectedImpact: string;
  difficulty: "low" | "medium" | "high";
  requiredPermission: "store_owner" | "brand_approval" | "hq_only" | "unclear";
  contractConstraint: string;
  nextStep: string;
  alternativeAction: string;
}

// ─── 经营项兑现追踪 ───
export type FulfillmentStatus = "fulfilled" | "partial" | "not_fulfilled" | "not_agreed" | "pending" | "na";

export interface FulfillmentItem {
  key: string;
  label: string;
  status: FulfillmentStatus;
  promised: string;
  reality: string;
  impact: string;
}

export interface FulfillmentTracker {
  siteSupport: FulfillmentItem;
  renovationGuide: FulfillmentItem;
  training: FulfillmentItem;
  openingSupervision: FulfillmentItem;
  marketingSupport: FulfillmentItem;
  deliveryOperation: FulfillmentItem;
  newProductTraining: FulfillmentItem;
  supplyChain: FulfillmentItem;
  responseTime: FulfillmentItem;
  regionProtection: FulfillmentItem;
}

/* ─── 多平台运营数据 ─── */

export type PlatformType = "meituan" | "taobao_flash" | "douyin" | "jd";

export interface PlatformMetrics {
  platform: PlatformType;
  platformName: string;        // 美团外卖 / 淘宝闪购 / 抖音本地生活 / 京东秒送
  
  // 营收
  revenue: number;             // 平台营收
  orders: number;              // 订单数
  avgOrderValue: number;       // 客单价
  
  // 漏斗
  impressions: number;         // 曝光量
  storeVisits: number;         // 进店量
  visitRate: number;           // 进店率 (进店/曝光)
  orderRate: number;           // 下单率 (下单/进店)
  overallConversion: number;   // 整体转化率 (下单/曝光)
  
  // 评分
  rating: number;              // 商家评分
  ratingTrend: "up" | "down" | "stable";
  
  // 成本
  commissionRate: number;      // 平台佣金率
  commissionAmount: number;    // 佣金金额
  deliveryFee: number;         // 配送费
  packagingCost: number;       // 包装成本
  discountAmount: number;      // 满减/折扣金额
  
  // 利润
  grossProfit: number;         // 平台毛利
  grossMargin: number;         // 平台毛利率
  profitPerOrder: number;      // 单均利润
  
  // 用户
  repeatRate: number;          // 复购率
  newCustomerRate: number;     // 新客占比
  badReviewRate: number;       // 差评率
  
  // 状态
  status: "active" | "paused" | "pending";
  lastUpdated: string;
}

export interface DeliveryFunnel {
  platform: PlatformType;
  platformName: string;
  data: {
    impressions: number;       // 曝光
    storeVisits: number;       // 进店
    orders: number;            // 下单
    repeatOrders: number;      // 复购
  };
  rates: {
    visitRate: number;         // 进店率
    orderRate: number;         // 下单率
    repeatRate: number;        // 复购率
    overallRate: number;       // 整体转化率
  };
  benchmarks: {
    visitRate: { good: number; avg: number; poor: number };
    orderRate: { good: number; avg: number; poor: number };
    repeatRate: { good: number; avg: number; poor: number };
  };
}

export interface PlatformComparison {
  platforms: PlatformMetrics[];
  totals: {
    revenue: number;
    orders: number;
    avgOrderValue: number;
    totalCommission: number;
    overallMargin: number;
  };
  insights: string[];          // 对比洞察
}
