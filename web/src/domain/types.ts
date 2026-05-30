/* ─── 开店决策操作系统 — 核心类型（运营增强版） ─── */

export type ProjectPhase =
  | "idea"           // 想法期
  | "franchise_talk"  // 加盟洽谈期
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

// ─── 加盟分析 ───
export interface FranchiseAnalysis {
  brandName: string;
  category: string;
  // 费用
  franchiseFee: number;
  deposit: number;
  equipmentFee: number;
  firstInventoryFee: number;
  renovationRequirement: number;
  managementFeeMonthly: number;
  royaltyRate: number;
  contractYears: number;
  // 条款
  hasFilingRecord: boolean | null;
  directStoreCount: number | null;
  franchiseStoreCount: number | null;
  providesDisclosure: boolean;
  providesRealStoreData: boolean;
  allowsExistingFranchiseeContact: boolean;
  hasTerritoryProtection: boolean;
  hasExitMechanism: boolean;
  forcesProcurement: boolean;
  providesPurchasePriceList: boolean;
  promisesPaybackPeriod: boolean;
  promisedPaybackMonths: number | null;
  // 话术
  salesPitch: string[];
}

// ─── 投资模型 ───
export interface InvestmentModel {
  // 初始投资
  franchiseFee: number;
  deposit: number;
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

// ─── 加盟经营权限矩阵 ───
export type PermissionStatus = "hq_control" | "hq_approval" | "store_autonomous" | "unclear";

export interface PermissionItem {
  key: string;
  label: string;
  status: PermissionStatus;
  note: string;  // 合同依据或备注
}

export interface FranchisePermissionMatrix {
  menu: PermissionItem;         // 菜单调整
  pricing: PermissionItem;      // 定价
  promotion: PermissionItem;    // 促销
  procurement: PermissionItem;  // 采购
  delivery: PermissionItem;     // 外卖运营
  membership: PermissionItem;   // 会员体系
  marketing: PermissionItem;    // 本地营销
  hours: PermissionItem;        // 营业时间
  renovation: PermissionItem;   // 装修调整
  newProduct: PermissionItem;   // 新品引入
}

// ─── 总部支持兑现度 ───
export type FulfillmentStatus = "fulfilled" | "partial" | "not_fulfilled" | "not_agreed" | "pending";

export interface FulfillmentItem {
  key: string;
  label: string;
  status: FulfillmentStatus;
  promised: string;   // 招商时怎么说的
  reality: string;    // 实际情况
  impact: string;     // 对经营的影响
}

export interface HQFulfillmentTracker {
  siteSupport: FulfillmentItem;       // 选址支持
  renovationGuide: FulfillmentItem;   // 装修指导
  training: FulfillmentItem;          // 培训
  openingSupervision: FulfillmentItem; // 开业督导
  marketingSupport: FulfillmentItem;  // 营销支持
  deliveryOperation: FulfillmentItem; // 外卖代运营
  newProductTraining: FulfillmentItem; // 新品培训
  supplyChain: FulfillmentItem;       // 供应链稳定
  responseTime: FulfillmentItem;      // 问题响应
  regionProtection: FulfillmentItem;  // 区域保护
}

// ─── 运营动作（增强版） ───
export interface OperationAction {
  title: string;
  reason: string;
  expectedImpact: string;
  difficulty: "low" | "medium" | "high";
  requiredPermission: "store_owner" | "brand_approval" | "hq_only" | "unclear";
  contractConstraint: string;
  nextStep: string;
  alternativeAction: string;  // 如果权限不允许，替代方案
}
