import {
  AlertTriangle,
  Archive,
  BarChart3,
  Boxes,
  BrainCircuit,
  CalendarDays,
  Camera,
  ClipboardCheck,
  ClipboardList,
  CloudSun,
  FileCheck2,
  FileText,
  GraduationCap,
  LineChart,
  Package,
  ReceiptText,
  Repeat2,
  ScanSearch,
  ShieldCheck,
  Store,
  Truck,
  Utensils,
  WalletCards,
  Workflow,
  type LucideIcon,
} from "lucide-react";

export type HealthTone = "good" | "watch" | "risk" | "info";

export interface AgentSignal {
  title: string;
  body: string;
  tone: HealthTone;
  source: string;
}

export interface AgentModule {
  href: string;
  title: string;
  eyebrow: string;
  description: string;
  icon: LucideIcon;
  primaryMetric: string;
  secondaryMetric: string;
  status: HealthTone;
  tasks: string[];
  evidence: string[];
}

export interface StoreObjective {
  title: string;
  ownerLine: string;
  agentLine: string;
  guardrails: string[];
}

export interface OkrMemoryItem {
  label: string;
  target: string;
  current: string;
  progress: number;
  tone: HealthTone;
  next: string;
}

export interface AgentDepartment {
  key: string;
  title: string;
  role: string;
  lead: string;
  icon: LucideIcon;
  tone: HealthTone;
  focus: string;
  input: string;
  output: string;
  proof: string;
}

export interface AgentTask {
  title: string;
  owner: string;
  status: "等你补信息" | "Agent 可执行" | "要人工确认" | "复盘中";
  priority: "高" | "中" | "低";
  body: string;
  proof: string;
}

export interface ProofArtifact {
  title: string;
  type: string;
  status: HealthTone;
  detail: string;
}

export interface OperatingLoopStep {
  title: string;
  body: string;
  icon: LucideIcon;
}

export const storeIdentity = {
  name: "新余恒太城大口章鱼烧",
  location: "江西新余 · 恒太城五楼美食城",
  category: "章鱼小丸子 / 商场小吃档口",
  ownerMode: "老板亲自守店 + 1 名员工",
  target: "先保住历史利润，再冲击更高净利",
};

export const storeObjective: StoreObjective = {
  title: "把这家章鱼烧店跑成可控、可算、可复盘的赚钱机器",
  ownerLine: "你负责现场判断、拍照补证据、确认关键动作。",
  agentLine: "掌柜 Agent 负责盯利润、盯库存、盯渠道、盯 SOP、盯风险，并每天给你最少动作。",
  guardrails: ["不为了流水牺牲利润", "营业中不让你填复杂表", "所有建议必须能追到数据或照片"],
};

export const profitTargets = [
  { label: "保底月净利", value: "¥10,000", progress: 42, tone: "watch" as const },
  { label: "增长月净利", value: "¥15,000", progress: 28, tone: "info" as const },
  { label: "冲刺月净利", value: "¥20,000", progress: 19, tone: "risk" as const },
];

export const okrMemory: OkrMemoryItem[] = [
  {
    label: "本月净利",
    target: "先守 ¥10,000",
    current: "等真实日账",
    progress: 42,
    tone: "watch",
    next: "补租金、工资、水电、平台费后才能算准。",
  },
  {
    label: "数据模型",
    target: "连续 14 天可用",
    current: "第 0 天",
    progress: 8,
    tone: "info",
    next: "每天打烊录客如云、平台、库存和异常。",
  },
  {
    label: "外卖利润",
    target: "只做有贡献的单",
    current: "待拆佣金",
    progress: 18,
    tone: "risk",
    next: "先拍美团/淘宝闪购经营分析，拆到手利润。",
  },
  {
    label: "SOP 覆盖",
    target: "核心岗位 7 天能上手",
    current: "框架已建",
    progress: 36,
    tone: "good",
    next: "拍总部资料和南昌店经验，转成训练卡。",
  },
];

export const agentSignals: AgentSignal[] = [
  {
    title: "先把线下信息喂进来",
    body: "客如云日报、美团后台、进货单、水电单、总部资料统一进资料箱，复核后入库。",
    tone: "info",
    source: "资料入库",
  },
  {
    title: "利润目标不能只看流水",
    body: "房租、工资、水电、商场费用、平台佣金、活动费、包装耗材都要进入保本模型。",
    tone: "watch",
    source: "财务 Agent",
  },
  {
    title: "SOP 要和问题联动",
    body: "外卖错单、面糊剩余、卫生漏项会反向更新 SOP，并生成员工训练任务。",
    tone: "good",
    source: "SOP Agent",
  },
];

export const agentDepartments: AgentDepartment[] = [
  {
    key: "finance",
    title: "财务 Agent",
    role: "保本和净利",
    lead: "长期记住房租、工资、水电、抽成和利润目标",
    icon: WalletCards,
    tone: "watch",
    focus: "今天卖多少才不亏，本月离净利目标还差多少。",
    input: "客如云日报 / 工资 / 房租 / 水电 / 平台费率",
    output: "保本线、真实净利、亏损预警",
    proof: "日账、费用单、平台账单",
  },
  {
    key: "inventory",
    title: "库存 Agent",
    role: "进货和备料",
    lead: "按半月批次和消耗速度，不要求逐克称重",
    icon: Boxes,
    tone: "info",
    focus: "章鱼、粉、鸡蛋、盒子、袋子什么时候会断。",
    input: "进货单 / 库存照片 / 打烊剩料 / 商品销量",
    output: "安全库存、补货建议、滞留风险",
    proof: "进货单、冰柜/货架照片",
  },
  {
    key: "channel",
    title: "渠道 Agent",
    role: "外卖和团购",
    lead: "只判断到手贡献，不被流水骗",
    icon: Truck,
    tone: "risk",
    focus: "满减、佣金、包装、退款扣完以后到底赚不赚。",
    input: "美团 / 淘宝闪购 / 抖音团购 / 退款差评",
    output: "活动 ROI、菜单建议、亏损渠道预警",
    proof: "平台经营分析截图",
  },
  {
    key: "product",
    title: "产品 Agent",
    role: "菜单和爆品",
    lead: "记住每个口味的复杂度、盒型、渠道适配",
    icon: Utensils,
    tone: "good",
    focus: "全家福、双拼、原味、肉松、藤椒、玉米奶酪怎么推。",
    input: "商品销量 / 配方照片 / 错单记录",
    output: "主推品、下架观察、备料优先级",
    proof: "客如云商品排行、产品 SOP",
  },
  {
    key: "sop",
    title: "SOP Agent",
    role: "标准和训练",
    lead: "总部资料、南昌经验、卫生检查统一入库",
    icon: ClipboardCheck,
    tone: "good",
    focus: "员工离职后，新人能不能 7 天顶上。",
    input: "总部资料照片 / 现场流程 / 异常复盘",
    output: "产品 SOP、培训卡、检查清单",
    proof: "SOP 文档、训练记录",
  },
  {
    key: "intel",
    title: "情报 Agent",
    role: "天气商圈",
    lead: "把外部变化变成备料和营销提醒",
    icon: CloudSun,
    tone: "info",
    focus: "下雨、高温、暑假、商场活动、学校放假会不会影响客流。",
    input: "天气 API / 本地新闻 / 商场活动 / 周边学校",
    output: "备料标签、客流解释、活动提醒",
    proof: "天气、公告、地图数据",
  },
];

export const agentTasks: AgentTask[] = [
  {
    title: "把第一套保本模型算准",
    owner: "财务 Agent",
    status: "等你补信息",
    priority: "高",
    body: "缺房租、商场抽成/管理费、平台真实费率。补齐后能告诉你每天最低要卖多少。",
    proof: "租金/费用截图 + 平台后台截图",
  },
  {
    title: "建立 14 天打烊台账",
    owner: "掌柜总控",
    status: "Agent 可执行",
    priority: "高",
    body: "每天只录打烊后的汇总，不要求营业中填表。连续 14 天后开始形成备料和客流模型。",
    proof: "客如云日报 + 库存照片",
  },
  {
    title: "把外卖出餐防错做成台面规则",
    owner: "店长 Agent",
    status: "要人工确认",
    priority: "中",
    body: "不是做表格，而是小票顺序、盒子标签、待做/已做/待打包区域。",
    proof: "台面照片 + 错单记录",
  },
  {
    title: "总部资料转成新人训练 SOP",
    owner: "SOP Agent",
    status: "复盘中",
    priority: "中",
    body: "把拍来的总部标准、南昌店经验、你实际做法拆成 7 天训练任务。",
    proof: "总部资料照片 + 训练卡",
  },
];

export const proofArtifacts: ProofArtifact[] = [
  {
    title: "客如云日报",
    type: "每日核心证据",
    status: "watch",
    detail: "用于流水、订单、商品销量、客单价。",
  },
  {
    title: "平台经营分析",
    type: "渠道证据",
    status: "risk",
    detail: "用于拆外卖佣金、满减、退款、差评。",
  },
  {
    title: "库存和进货照片",
    type: "供应链证据",
    status: "info",
    detail: "用于半月批次、安全库存和断货提醒。",
  },
  {
    title: "总部 / 现场 SOP",
    type: "作业证据",
    status: "good",
    detail: "用于制作标准、卫生检查、新人培训。",
  },
];

export const operatingLoop: OperatingLoopStep[] = [
  {
    title: "喂信息",
    body: "你说一句话、拍一张图、传一份资料。",
    icon: Camera,
  },
  {
    title: "识别入库",
    body: "Worker Agent 抽字段，低置信度让你确认。",
    icon: ScanSearch,
  },
  {
    title: "部门分析",
    body: "财务、库存、渠道、SOP、情报各自更新判断。",
    icon: BrainCircuit,
  },
  {
    title: "给动作",
    body: "掌柜总控只给今天最该做的几件事。",
    icon: ClipboardList,
  },
  {
    title: "留证据",
    body: "每个建议都能追到截图、单据、SOP 或数据。",
    icon: FileCheck2,
  },
  {
    title: "复盘更新",
    body: "昨天的判断用今天结果校准，店铺模型越来越懂你。",
    icon: Repeat2,
  },
];

export const cockpitMetrics = [
  { label: "今日目标流水", value: "¥1,200", helper: "先覆盖现金成本", tone: "watch" as const },
  { label: "冲刺流水", value: "¥1,600", helper: "支持利润增长", tone: "good" as const },
  { label: "当前数据质量", value: "待建模", helper: "等客如云和平台截图", tone: "info" as const },
  { label: "关键缺口", value: "7 项", helper: "租金/平台费/商品销量等", tone: "risk" as const },
];

export const revenueTrend = [
  { day: "周一", revenue: 520, target: 1200 },
  { day: "周二", revenue: 610, target: 1200 },
  { day: "周三", revenue: 580, target: 1200 },
  { day: "周四", revenue: 760, target: 1200 },
  { day: "周五", revenue: 930, target: 1200 },
  { day: "周六", revenue: 1850, target: 1600 },
  { day: "周日", revenue: 2100, target: 1600 },
];

export const storeModules: AgentModule[] = [
  {
    href: "/capture",
    title: "资料入库",
    eyebrow: "证据箱",
    description: "截图、单据、合同、SOP、库存照片统一识别、复核、归档。",
    icon: FileText,
    primaryMetric: "自动识别",
    secondaryMetric: "复核入库",
    status: "info",
    tasks: ["来源识别", "字段抽取", "低置信标记", "归档去向"],
    evidence: ["客如云日报", "平台后台", "合同/转让协议", "进货单", "总部/SOP资料"],
  },
  {
    href: "/dashboard",
    title: "经营驾驶舱",
    eyebrow: "老板看板",
    description: "把收入、成本、库存、渠道、天气和预警汇总成今天该做什么。",
    icon: BarChart3,
    primaryMetric: "7 日趋势",
    secondaryMetric: "今日三件事",
    status: "good",
    tasks: ["看保本进度", "看库存红灯", "看渠道利润"],
    evidence: ["日账", "平台截图", "库存照片"],
  },
  {
    href: "/sales",
    title: "营业走势",
    eyebrow: "Revenue",
    description: "按日、周、天气、节假日、暑假标签分析营业额、订单数和客单价。",
    icon: LineChart,
    primaryMetric: "¥1,200/日",
    secondaryMetric: "临时保本目标",
    status: "watch",
    tasks: ["建立 7 日均线", "区分平日/周末", "记录天气标签"],
    evidence: ["客如云", "天气 API", "节假日"],
  },
  {
    href: "/profit",
    title: "利润与保本",
    eyebrow: "Profit",
    description: "用老板能懂的话解释房租、工资、水电、抽成、平台费和耗材怎么影响利润。",
    icon: WalletCards,
    primaryMetric: "三档利润目标",
    secondaryMetric: "保底/增长/冲刺",
    status: "watch",
    tasks: ["补房租", "补商场费用", "补员工工资"],
    evidence: ["费用单", "工资", "平台费率"],
  },
  {
    href: "/channels",
    title: "渠道外卖",
    eyebrow: "Meituan / 淘宝闪购 / Douyin",
    description: "不只看外卖流水，重点看扣掉佣金、满减、包装、退款后的到手贡献。",
    icon: Truck,
    primaryMetric: "到手利润",
    secondaryMetric: "待截图校准",
    status: "risk",
    tasks: ["拍平台后台", "记录活动成本", "核对退款和差评"],
    evidence: ["美团后台", "淘宝闪购", "抖音核销"],
  },
  {
    href: "/products",
    title: "商品菜单",
    eyebrow: "Menu",
    description: "按销量、复杂度、盒型、渠道适配判断原味、肉松、藤椒、全家福等产品怎么推。",
    icon: Utensils,
    primaryMetric: "主推 4 类",
    secondaryMetric: "全家福/双拼/基础款/复杂款",
    status: "good",
    tasks: ["补商品销量", "关联盒型", "关联产品 SOP"],
    evidence: ["商品销售排行", "制作配方照片", "客如云商品表"],
  },
  {
    href: "/inventory",
    title: "进货库存",
    eyebrow: "Batch Stock",
    description: "按半月进货批次、消耗速度、安全库存判断章鱼粉、盒子、章鱼粒什么时候补。",
    icon: Boxes,
    primaryMetric: "批次法",
    secondaryMetric: "不逐克称重",
    status: "watch",
    tasks: ["拍进货单", "录当前剩余", "设置安全库存"],
    evidence: ["进货单", "库存照片", "打烊剩料"],
  },
  {
    href: "/consumables",
    title: "水电耗材",
    eyebrow: "Utilities",
    description: "把水电、6 粒盒、4 粒盒、圆盒、塑料袋、小票纸、手套和清洁用品单独看。",
    icon: Package,
    primaryMetric: "高频小成本",
    secondaryMetric: "防止漏算",
    status: "info",
    tasks: ["补水电单", "补盒子库存", "补清洁用品"],
    evidence: ["水电单", "耗材进货", "库存照片"],
  },
  {
    href: "/sop",
    title: "SOP 作业库",
    eyebrow: "Operating Standard",
    description: "总部资料、南昌店经验、卫生标准、检查要求全部转成可查可执行的 SOP。",
    icon: ClipboardCheck,
    primaryMetric: "10 类 SOP",
    secondaryMetric: "拍照生成草稿",
    status: "good",
    tasks: ["产品 SOP", "打烊 SOP", "卫生检查 SOP"],
    evidence: ["总部资料", "现场照片", "异常复盘"],
  },
  {
    href: "/training",
    title: "员工训练",
    eyebrow: "Training",
    description: "统一管理员工、健康证、技能矩阵和 7 天训练，不再区分当前员工和新员工。",
    icon: GraduationCap,
    primaryMetric: "7 天训练",
    secondaryMetric: "按技能解锁",
    status: "watch",
    tasks: ["录员工档案", "建立技能表", "关联错单训练"],
    evidence: ["SOP", "异常记录", "排班"],
  },
  {
    href: "/workflow",
    title: "店铺动线",
    eyebrow: "Counter Flow",
    description: "把十平不到的长方形档口拆成未做、正在做、加料、打包、核销、异常单。",
    icon: Workflow,
    primaryMetric: "小票流",
    secondaryMetric: "营业中不填表",
    status: "good",
    tasks: ["生成台面标签", "设置小票顺序", "记录错单位置"],
    evidence: ["线下台面", "小票", "错单记录"],
  },
  {
    href: "/calendar",
    title: "天气商圈",
    eyebrow: "Context",
    description: "把高温、下雨、暑假、开学、商场活动、周边学校和本地新闻变成经营标签。",
    icon: CloudSun,
    primaryMetric: "外部标签",
    secondaryMetric: "影响备料和客流",
    status: "info",
    tasks: ["接天气", "抓假期", "记录商场活动"],
    evidence: ["高德", "官方消息", "商场活动"],
  },
  {
    href: "/alerts",
    title: "异常预警",
    eyebrow: "Risk Radar",
    description: "连续低流水、库存断货、平台亏损、水电异常、卫生检查和设备问题统一进红黄灯。",
    icon: AlertTriangle,
    primaryMetric: "红黄绿灯",
    secondaryMetric: "主动提醒",
    status: "risk",
    tasks: ["配置阈值", "记录异常", "生成修正动作"],
    evidence: ["日报", "库存", "SOP 执行"],
  },
  {
    href: "/reports",
    title: "经营复盘",
    eyebrow: "Review",
    description: "每周看趋势、每月看真实净利，自动总结下周要冲什么、要防什么。",
    icon: FileText,
    primaryMetric: "自动复盘",
    secondaryMetric: "老板话输出",
    status: "good",
    tasks: ["周报", "月报", "利润目标复盘"],
    evidence: ["日账", "成本", "外部标签"],
  },
  {
    href: "/settings",
    title: "店铺模型",
    eyebrow: "Store Model",
    description: "维护房租、工资、平台费率、安全库存、商品、物料、SOP 分类和目标利润。",
    icon: Store,
    primaryMetric: "底层参数",
    secondaryMetric: "持续校准",
    status: "info",
    tasks: ["成本参数", "商品参数", "Agent 规则"],
    evidence: ["店铺档案", "费用单", "历史数据"],
  },
];

export const sopGroups = [
  "产品制作",
  "备料",
  "开店",
  "营业中",
  "外卖",
  "打烊",
  "卫生",
  "检查",
  "培训",
  "异常处理",
];

export const captureSources = [
  "客如云日报",
  "商品销量排行",
  "美团经营分析",
  "淘宝闪购后台",
  "抖音团购核销",
  "进货单",
  "合同/转让协议",
  "水电单",
  "库存照片",
  "总部/SOP资料",
  "异常小票",
];

export const navGroups = [
  {
    label: "Agent",
    items: [
      { href: "/overview", label: "今日工作台", icon: ShieldCheck },
    ],
  },
  {
    label: "情报与复盘",
    items: [
      { href: "/calendar", label: "天气商圈", icon: CalendarDays },
      { href: "/alerts", label: "异常预警", icon: AlertTriangle },
      { href: "/reports", label: "经营复盘", icon: ReceiptText },
    ],
  },
  {
    label: "档案",
    items: [
      { href: "/capture", label: "资料入库", icon: FileText },
      { href: "/documents", label: "资料档案", icon: Archive },
    ],
  },
  {
    label: "经营",
    items: [
      { href: "/dashboard", label: "驾驶舱", icon: BarChart3 },
      { href: "/sales", label: "营业走势", icon: LineChart },
      { href: "/profit", label: "利润保本", icon: WalletCards },
      { href: "/channels", label: "渠道外卖", icon: Truck },
      { href: "/products", label: "商品菜单", icon: Utensils },
      { href: "/inventory", label: "进货库存", icon: Boxes },
      { href: "/consumables", label: "水电耗材", icon: Package },
    ],
  },
  {
    label: "作业",
    items: [
      { href: "/sop", label: "SOP作业库", icon: ClipboardCheck },
      { href: "/training", label: "员工训练", icon: GraduationCap },
      { href: "/workflow", label: "店铺动线", icon: Workflow },
    ],
  },
];
