import {
  Boxes, CloudSun, ClipboardCheck,
  LucideIcon, Truck, Utensils, WalletCards,
} from "lucide-react";

export type DepartmentAgentStatus = "idle" | "running" | "done" | "blocked";

export type DepartmentAgent = {
  id: string;
  name: string;
  role: string;
  status: DepartmentAgentStatus;
  confidence: number;
  inputs: string[];
  outputs: string[];
  nextAction: string;
  icon: LucideIcon;
  passTo?: string;
};

export type DynamicResultCard = {
  id: string;
  type: "judgement" | "evidence" | "forecast" | "action" | "risk" | "chart";
  title: string;
  eyebrow: string;
  summary: string;
  tone: "green" | "amber" | "blue" | "red";
  metric?: string;
  bullets: string[];
};

export type StoreMemoryEvent = {
  id: string;
  time: string;
  type: string;
  title: string;
  detail: string;
  status: "recorded" | "pending" | "risk";
};

// ── 大口章鱼烧 6 个经营 Agent（线上员工，互相协作） ──
export const departmentAgents: DepartmentAgent[] = [
  {
    id: "finance",
    name: "财务 Agent",
    role: "保本和净利",
    status: "running",
    confidence: 76,
    inputs: ["7天营收 ¥14,130", "食材成本率 36%", "人工 ¥400/天"],
    outputs: ["日均保本线 ¥1,420", "近7天净利 ¥420", "食材成本正常"],
    nextAction: "等库存 Agent 采购清单 → 更新保本模型",
    icon: WalletCards,
    passTo: "掌柜总控",
  },
  {
    id: "inventory",
    name: "库存 Agent",
    role: "进货和备料",
    status: "running",
    confidence: 82,
    inputs: ["15 项 SKU", "7 天消耗趋势", "进货批次"],
    outputs: ["4 项耗材低于安全线", "章鱼粒+酱料本周补", "塑料袋今日应补"],
    nextAction: "生成采购清单 → 传给财务 Agent 算成本",
    icon: Boxes,
    passTo: "财务 Agent",
  },
  {
    id: "channel",
    name: "渠道 Agent",
    role: "外卖和团购",
    status: "running",
    confidence: 69,
    inputs: ["美团佣金 22%", "外卖占比 44%", "满减成本"],
    outputs: ["到手利润偏低", "建议降满减力度", "6/24差评影响评分"],
    nextAction: "把差评归因 → 传给 SOP Agent",
    icon: Truck,
    passTo: "SOP Agent",
  },
  {
    id: "product",
    name: "产品 Agent",
    role: "菜单和爆品",
    status: "idle",
    confidence: 64,
    inputs: ["客如云商品排行", "产品 SOP", "盒型适配"],
    outputs: ["等录入商品销量", "需要客如云截图"],
    nextAction: "待客如云对接",
    icon: Utensils,
  },
  {
    id: "sop",
    name: "SOP Agent",
    role: "标准和训练",
    status: "running",
    confidence: 71,
    inputs: ["渠道 Agent 差评归因", "出餐流程", "配送超时"],
    outputs: ["出餐优化建议已生成", "外卖核单 SOP 待更新"],
    nextAction: "生成训练任务 → 传给训练 Agent",
    icon: ClipboardCheck,
    passTo: "训练 Agent",
  },
  {
    id: "intel",
    name: "情报 Agent",
    role: "天气商圈",
    status: "done",
    confidence: 85,
    inputs: ["天气 API", "恒太城活动", "学校假期"],
    outputs: ["今日小雨 35°C", "明日降雨外卖上调", "暑假客流增加"],
    nextAction: "天气标签 → 传给库存 Agent 调备货",
    icon: CloudSun,
    passTo: "库存 Agent",
  },
];
