import {
  Boxes, BrainCircuit, LineChart, Store,
  LucideIcon, WalletCards,
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

// ── 大口章鱼烧 5 岗位数字团队 ──
export const departmentAgents: DepartmentAgent[] = [
  {
    id: "chief",
    name: "掌柜",
    role: "总调度与经营决策",
    status: "running",
    confidence: 80,
    inputs: ["今日营业概况", "天气/商圈情报", "各岗位汇报"],
    outputs: ["今日经营总结", "风险提醒", "下一步动作"],
    nextAction: "汇总各岗位判断 → 给老板今天三件事",
    icon: BrainCircuit,
  },
  {
    id: "accountant",
    name: "会计",
    role: "钱账利润现金流",
    status: "running",
    confidence: 76,
    inputs: ["7天营收 ¥14,130", "食材成本率 36%", "人工 ¥400/天"],
    outputs: ["日均保本线 ¥1,420", "近7天净利 ¥420", "食材成本正常"],
    nextAction: "等仓管采购清单 → 更新保本模型",
    icon: WalletCards,
    passTo: "掌柜",
  },
  {
    id: "store_manager",
    name: "店长",
    role: "门店运营与标准训练",
    status: "running",
    confidence: 71,
    inputs: ["运营差评归因", "出餐流程", "配送超时"],
    outputs: ["出餐优化建议已生成", "外卖核单 SOP 待更新"],
    nextAction: "生成训练任务 → 跟进卫生检查",
    icon: Store,
    passTo: "掌柜",
  },
  {
    id: "warehouse",
    name: "仓管",
    role: "库存采购供应商",
    status: "running",
    confidence: 82,
    inputs: ["15 项 SKU", "7 天消耗趋势", "进货批次"],
    outputs: ["4 项耗材低于安全线", "章鱼粒+酱料本周补", "塑料袋今日应补"],
    nextAction: "生成采购清单 → 传给会计算成本",
    icon: Boxes,
    passTo: "会计",
  },
  {
    id: "operations",
    name: "运营",
    role: "渠道外卖与菜单增长",
    status: "running",
    confidence: 69,
    inputs: ["美团佣金 22%", "外卖占比 44%", "满减成本", "客如云商品排行"],
    outputs: ["到手利润偏低", "建议降满减力度", "6/24差评影响评分"],
    nextAction: "差评归因 → 传给店长改 SOP",
    icon: LineChart,
    passTo: "店长",
  },
];
