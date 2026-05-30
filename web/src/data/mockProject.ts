/* ─── 真实 Mock 数据 — 霸王茶姬 · 新余 ─── */

import type {
  Project, FranchiseAnalysis, InvestmentModel,
  LocationAssessment, OperationDailyRecord, MenuItemPerformance, RiskItem,
  FranchisePermissionMatrix, HQFulfillmentTracker, OperationAction,
} from "../domain/types";

export const mockProject: Project = {
  id: "xinyu-bgcj",
  name: "霸王茶姬 · 新余",
  category: "茶饮",
  city: "新余",
  stage: "franchise_talk",
  budget: 300000,
  availableCash: 150000,
  createdAt: "2026-05-15",
  updatedAt: "2026-05-29",
};

export const mockFranchise: FranchiseAnalysis = {
  brandName: "霸王茶姬",
  category: "茶饮",
  franchiseFee: 69800,
  deposit: 20000,
  equipmentFee: 150000,
  firstInventoryFee: 30000,
  renovationRequirement: 180000,
  managementFeeMonthly: 1000,
  royaltyRate: 0.03,
  contractYears: 3,
  hasFilingRecord: null,
  directStoreCount: null,
  franchiseStoreCount: null,
  providesDisclosure: false,
  providesRealStoreData: false,
  allowsExistingFranchiseeContact: false,
  hasTerritoryProtection: true,
  hasExitMechanism: false,
  forcesProcurement: true,
  providesPurchasePriceList: false,
  promisesPaybackPeriod: true,
  promisedPaybackMonths: 10,
  salesPitch: ["10个月回本", "日均流水8000+", "总部全程扶持", "区域保护", "统一供应链"],
};

export const mockInvestment: InvestmentModel = {
  franchiseFee: 69800,
  deposit: 20000,
  transferFee: 0,
  rentDeposit: 17000,
  firstMonthRent: 8500,
  renovationCost: 180000,
  equipmentCost: 150000,
  firstInventoryCost: 30000,
  licenseCost: 3000,
  openingMarketingCost: 10000,
  trainingCost: 5000,
  reserveCash: 30000,
  otherStartupCost: 5000,
  monthlyRent: 8500,
  monthlyLabor: 12000,
  monthlyUtilities: 2000,
  monthlyManagementFee: 1000,
  monthlySystemFee: 300,
  monthlyMarketing: 2000,
  otherMonthlyFixedCost: 500,
  averageDailyOrders: 120,
  averageOrderValue: 18,
  monthlyOperatingDays: 30,
  grossMarginRate: 0.65,
  platformCommissionRate: 0.22,
  lossRate: 0.03,
  discountRate: 0.02,
};

export const mockLocation: LocationAssessment = {
  city: "新余",
  district: "渝水区",
  businessAreaType: "community",
  areaSqm: 35,
  monthlyRent: 8500,
  transferFee: 0,
  weekdayFootTraffic: 1500,
  weekendFootTraffic: 2200,
  targetCustomerFit: 3,
  competitorCount500m: 6,
  hasAnchorTraffic: true,
  storefrontVisibility: 3,
  deliveryFit: 4,
  nearSchool: false,
  nearCommunity: true,
  nearOffice: true,
  nearMall: false,
  nearSubway: false,
  nearHospital: false,
};

export const mockOperations: OperationDailyRecord[] = [
  { date: "2026-05-22", revenue: 2100, orders: 115, averageOrderValue: 18.3, dineInOrders: 45, deliveryOrders: 70, dineInRevenue: 850, deliveryRevenue: 1250, materialCost: 735, packagingCost: 63, platformCommission: 275, deliverySubsidy: 45, discountCost: 42, laborCost: 400, rentAllocated: 283, utilitiesAllocated: 67, marketingCost: 67, lossAmount: 63, badReviews: 1, newMembers: 5, repeatOrders: 12, notes: "试营业第1天" },
  { date: "2026-05-23", revenue: 1850, orders: 98, averageOrderValue: 18.9, dineInOrders: 38, deliveryOrders: 60, dineInRevenue: 720, deliveryRevenue: 1130, materialCost: 648, packagingCost: 55, platformCommission: 242, deliverySubsidy: 38, discountCost: 37, laborCost: 400, rentAllocated: 283, utilitiesAllocated: 67, marketingCost: 67, lossAmount: 56, badReviews: 0, newMembers: 3, repeatOrders: 8, notes: "" },
  { date: "2026-05-24", revenue: 2300, orders: 128, averageOrderValue: 18.0, dineInOrders: 55, deliveryOrders: 73, dineInRevenue: 1000, deliveryRevenue: 1300, materialCost: 805, packagingCost: 69, platformCommission: 286, deliverySubsidy: 50, discountCost: 46, laborCost: 400, rentAllocated: 283, utilitiesAllocated: 67, marketingCost: 67, lossAmount: 69, badReviews: 2, newMembers: 8, repeatOrders: 15, notes: "周末" },
  { date: "2026-05-25", revenue: 2450, orders: 135, averageOrderValue: 18.1, dineInOrders: 60, deliveryOrders: 75, dineInRevenue: 1100, deliveryRevenue: 1350, materialCost: 858, packagingCost: 74, platformCommission: 303, deliverySubsidy: 52, discountCost: 49, laborCost: 400, rentAllocated: 283, utilitiesAllocated: 67, marketingCost: 67, lossAmount: 74, badReviews: 0, newMembers: 10, repeatOrders: 18, notes: "周末" },
  { date: "2026-05-26", revenue: 1920, orders: 105, averageOrderValue: 18.3, dineInOrders: 42, deliveryOrders: 63, dineInRevenue: 770, deliveryRevenue: 1150, materialCost: 672, packagingCost: 58, platformCommission: 247, deliverySubsidy: 40, discountCost: 38, laborCost: 400, rentAllocated: 283, utilitiesAllocated: 67, marketingCost: 67, lossAmount: 58, badReviews: 1, newMembers: 4, repeatOrders: 10, notes: "" },
  { date: "2026-05-27", revenue: 1780, orders: 96, averageOrderValue: 18.5, dineInOrders: 35, deliveryOrders: 61, dineInRevenue: 650, deliveryRevenue: 1130, materialCost: 623, packagingCost: 53, platformCommission: 229, deliverySubsidy: 37, discountCost: 36, laborCost: 400, rentAllocated: 283, utilitiesAllocated: 67, marketingCost: 67, lossAmount: 53, badReviews: 3, newMembers: 2, repeatOrders: 7, notes: "差评多" },
  { date: "2026-05-28", revenue: 2050, orders: 112, averageOrderValue: 18.3, dineInOrders: 44, deliveryOrders: 68, dineInRevenue: 810, deliveryRevenue: 1240, materialCost: 718, packagingCost: 62, platformCommission: 267, deliverySubsidy: 44, discountCost: 41, laborCost: 400, rentAllocated: 283, utilitiesAllocated: 67, marketingCost: 67, lossAmount: 62, badReviews: 1, newMembers: 6, repeatOrders: 13, notes: "" },
];

export const mockMenuItems: MenuItemPerformance[] = [
  { id: "m1", name: "伯牙绝弦", category: "奶茶", price: 18, unitCost: 5.4, grossMargin: 0.70, unitsSold: 45, revenue: 810, grossProfit: 567, prepComplexity: "low", isPromotionItem: false },
  { id: "m2", name: "花田乌龙", category: "奶茶", price: 20, unitCost: 6.0, grossMargin: 0.70, unitsSold: 38, revenue: 760, grossProfit: 532, prepComplexity: "low", isPromotionItem: false },
  { id: "m3", name: "新品尝鲜价", category: "活动款", price: 12, unitCost: 5.0, grossMargin: 0.58, unitsSold: 55, revenue: 660, grossProfit: 385, prepComplexity: "low", isPromotionItem: true },
  { id: "m4", name: "桂馥兰香", category: "鲜奶茶", price: 22, unitCost: 7.7, grossMargin: 0.65, unitsSold: 28, revenue: 616, grossProfit: 400, prepComplexity: "medium", isPromotionItem: false },
  { id: "m5", name: "小料加购", category: "加购", price: 3, unitCost: 0.6, grossMargin: 0.80, unitsSold: 80, revenue: 240, grossProfit: 192, prepComplexity: "low", isPromotionItem: false },
];

export const mockRisks: RiskItem[] = [
  { id: "risk-1", name: "品牌方承诺10个月回本但无数据支撑", module: "franchise", severity: "critical", probability: "high", evidence: "招商经理口头承诺，未提供任何门店流水证明", impact: "可能远超10个月，实际回本周期可能18-24个月", suggestedAction: "要求提供3家以上门店的真实POS流水截图", status: "unverified" },
  { id: "risk-2", name: "合同无退出条款", module: "franchise", severity: "high", probability: "medium", evidence: "合同模板中未找到退出/解约条款", impact: "经营困难时无法止损，保证金不退", suggestedAction: "签约前要求加入退出条款", status: "verified" },
  { id: "risk-3", name: "强制采购导致毛利不可控", module: "franchise", severity: "high", probability: "high", evidence: "合同规定必须从总部采购所有原材料", impact: "总部涨价直接压缩利润空间", suggestedAction: "问清原材料价格是否有涨价机制", status: "verified" },
  { id: "risk-4", name: "日均保本订单数偏高", module: "investment", severity: "high", probability: "medium", evidence: "按当前成本结构计算，需要日均160+单才能保本", impact: "实际客流可能达不到保本线", suggestedAction: "降低固定成本或提高客单价到22元以上", status: "verified" },
  { id: "risk-5", name: "无法联系老加盟商", module: "franchise", severity: "high", probability: "high", evidence: "品牌方表示不方便提供老加盟商联系方式", impact: "可能隐瞒加盟商真实亏损情况", suggestedAction: "自行通过美团/大众点评找到门店，实地访谈", status: "unverified" },
  { id: "risk-6", name: "外卖抽佣后利润过低", module: "operations", severity: "medium", probability: "high", evidence: "平台抽佣22%，加上活动折扣，外卖毛利可能低于40%", impact: "外卖占比越高，整体利润越低", suggestedAction: "控制外卖占比在30%以内，提升堂食比例", status: "verified" },
  { id: "risk-7", name: "保守情境下无法盈利", module: "investment", severity: "high", probability: "medium", evidence: "保守情境（订单-30%，客单-10%，毛利-5%）月利润为负", impact: "一旦客流不达预期，将持续亏损", suggestedAction: "准备额外备用现金或降低投资规模", status: "verified" },
  { id: "risk-8", name: "连续2天差评偏高", module: "operations", severity: "medium", probability: "medium", evidence: "5月27日3条差评，主要关于配送超时", impact: "影响店铺评分和自然流量", suggestedAction: "优化出餐流程，与骑手沟通取餐效率", status: "verified" },
];

// ─── 经营权限矩阵（霸王茶姬示例） ───
export const mockPermissions: FranchisePermissionMatrix = {
  menu:          { key: "menu", label: "菜单调整", status: "hq_approval", note: "新品需总部审批，现有菜品可微调" },
  pricing:       { key: "pricing", label: "定价", status: "hq_control", note: "全国统一定价，门店不可自主调价" },
  promotion:     { key: "promotion", label: "促销", status: "hq_approval", note: "活动需报备，满减由总部统一设置" },
  procurement:   { key: "procurement", label: "采购", status: "hq_control", note: "必须从总部采购全部原材料" },
  delivery:      { key: "delivery", label: "外卖运营", status: "hq_approval", note: "平台代运营由总部负责，门店可提需求" },
  membership:    { key: "membership", label: "会员体系", status: "hq_control", note: "会员系统由总部统一管理" },
  marketing:     { key: "marketing", label: "本地营销", status: "store_autonomous", note: "门店可自行做本地推广，但不能使用未授权素材" },
  hours:         { key: "hours", label: "营业时间", status: "hq_approval", note: "需报备调整，但实际可灵活执行" },
  renovation:    { key: "renovation", label: "装修调整", status: "hq_control", note: "必须符合品牌VI标准，不可自行改动" },
  newProduct:    { key: "newProduct", label: "新品引入", status: "hq_control", note: "新品由总部统一研发和下发" },
};

// ─── 总部支持兑现度 ───
export const mockFulfillment: HQFulfillmentTracker = {
  siteSupport:       { key: "siteSupport", label: "选址支持", status: "partial", promised: "总部派人实地评估", reality: "远程给了选址标准，未派人到场", impact: "选址判断缺少专业支持" },
  renovationGuide:   { key: "renovationGuide", label: "装修指导", status: "fulfilled", promised: "提供装修方案和施工指导", reality: "提供了标准方案和供应商清单", impact: "基本兑现" },
  training:          { key: "training", label: "培训", status: "fulfilled", promised: "7天总部培训", reality: "完成了5天培训，内容覆盖产品制作和门店管理", impact: "基本兑现，但缺少外卖运营培训" },
  openingSupervision: { key: "openingSupervision", label: "开业督导", status: "partial", promised: "开业期间督导驻店3天", reality: "督导来了1天就走了", impact: "开业期问题处理不及时" },
  marketingSupport:  { key: "marketingSupport", label: "营销支持", status: "not_fulfilled", promised: "提供开业营销方案和物料", reality: "只给了几张海报模板，没有完整方案", impact: "开业引流效果不达预期" },
  deliveryOperation: { key: "deliveryOperation", label: "外卖代运营", status: "pending", promised: "总部代运营美团/饿了么", reality: "账号已交接，但运营策略还没看到", impact: "待验证" },
  newProductTraining: { key: "newProductTraining", label: "新品培训", status: "not_agreed", promised: "新品上市前提供培训", reality: "合同未明确新品培训频率和方式", impact: "可能影响产品更新节奏" },
  supplyChain:       { key: "supplyChain", label: "供应链稳定", status: "partial", promised: "稳定供应，价格透明", reality: "配送时效还行，但部分物料价格比市场价高", impact: "毛利率被压缩" },
  responseTime:      { key: "responseTime", label: "问题响应", status: "partial", promised: "24小时内响应", reality: "一般问题1-2天回复，紧急问题需要反复催", impact: "经营问题处理延迟" },
  regionProtection:  { key: "regionProtection", label: "区域保护", status: "pending", promised: "3公里内不再开同品牌", reality: "目前没有新店，但合同条款模糊", impact: "待观察" },
};

// ─── 运营动作示例 ───
export const mockActions: OperationAction[] = [
  {
    title: "优化外卖满减结构",
    reason: "外卖流水增长但净利下降，平台抽佣+满减吞噬利润",
    expectedImpact: "外卖净利率提升3-5个百分点",
    difficulty: "medium",
    requiredPermission: "brand_approval",
    contractConstraint: "外卖活动由总部代运营设置，门店需与总部沟通调整",
    nextStep: "联系总部运营负责人，提交满减调整建议方案",
    alternativeAction: "如果总部不调整满减，优化出餐效率降低人工成本",
  },
  {
    title: "设计高毛利套餐",
    reason: "当前高销量产品中2个毛利低于35%，利润被低毛利产品吃掉",
    expectedImpact: "客单价提升2-3元，整体毛利率提升2个百分点",
    difficulty: "low",
    requiredPermission: "brand_approval",
    contractConstraint: "菜单调整需总部审批，但套餐组合可在现有产品内自由搭配",
    nextStep: "在现有产品内设计3个套餐组合，提交总部审批",
    alternativeAction: "如果套餐审批慢，先通过员工话术推荐高毛利产品搭配",
  },
  {
    title: "调整晚高峰排班",
    reason: "晚高峰订单量低于预期，但排班人数与午高峰相同",
    expectedImpact: "人工成本率降低2-3个百分点",
    difficulty: "low",
    requiredPermission: "store_owner",
    contractConstraint: "排班由门店自主决定",
    nextStep: "下周一开始晚高峰从3人减为2人，观察3天",
    alternativeAction: "",
  },
  {
    title: "推出老客复购券",
    reason: "新客多但复购率低，尝鲜后没有形成消费习惯",
    expectedImpact: "7日复购率从12%提升到20%",
    difficulty: "medium",
    requiredPermission: "brand_approval",
    contractConstraint: "会员体系由总部统一管理，券的发放需通过总部系统",
    nextStep: "向总部申请开通门店自主发券权限，或提交复购券方案",
    alternativeAction: "如果总部系统不支持，做企业微信私域，手动发券",
  },
  {
    title: "检查TOP 10产品出品克重",
    reason: "毛利率低于模型5个百分点，可能存在出品偏差导致食材浪费",
    expectedImpact: "食材成本率降低1-2个百分点",
    difficulty: "low",
    requiredPermission: "store_owner",
    contractConstraint: "出品标准由总部制定，门店执行",
    nextStep: "连续3天抽查TOP 10产品的实际克重与标准对比",
    alternativeAction: "",
  },
];
