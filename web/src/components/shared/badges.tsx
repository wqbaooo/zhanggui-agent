import type { RiskLevel, PermissionStatus, FulfillmentStatus } from "@/domain/types";

export const RISK_BADGE: Record<RiskLevel, { bg: string; text: string; label: string }> = {
  low: { bg: "bg-emerald-500/15", text: "text-emerald-700", label: "低" },
  medium: { bg: "bg-amber-500/15", text: "text-amber-700", label: "中" },
  high: { bg: "bg-red-500/15", text: "text-red-700", label: "高" },
  critical: { bg: "bg-red-600/20", text: "text-red-800", label: "极高" },
};

export function PermBadge({ status }: { status: PermissionStatus }) {
  const config: Record<PermissionStatus, { bg: string; text: string; label: string }> = {
    hq_control: { bg: "bg-red-500/15", text: "text-red-700", label: "总部控制" },
    hq_approval: { bg: "bg-amber-500/15", text: "text-amber-700", label: "需审批" },
    store_autonomous: { bg: "bg-emerald-500/15", text: "text-emerald-700", label: "门店自主" },
    unclear: { bg: "bg-surface-container-high/70", text: "text-on-surface-variant", label: "不明确" },
  };
  const c = config[status];
  return <span className={`font-label-caps text-[9px] px-1.5 py-0.5 rounded-full ${c.bg} ${c.text}`}>{c.label}</span>;
}

export function FulfillBadge({ status }: { status: FulfillmentStatus }) {
  const config: Record<FulfillmentStatus, { bg: string; text: string; label: string }> = {
    fulfilled: { bg: "bg-emerald-500/15", text: "text-emerald-700", label: "已兑现" },
    partial: { bg: "bg-amber-500/15", text: "text-amber-700", label: "部分兑现" },
    not_fulfilled: { bg: "bg-red-500/15", text: "text-red-700", label: "未兑现" },
    not_agreed: { bg: "bg-surface-container-high/70", text: "text-on-surface-variant", label: "未约定" },
    pending: { bg: "bg-blue-500/15", text: "text-blue-700", label: "待验证" },
    na: { bg: "bg-surface-container-high/70", text: "text-on-surface-variant", label: "独立经营" },
  };
  const c = config[status];
  return <span className={`font-label-caps text-[9px] px-1.5 py-0.5 rounded-full ${c.bg} ${c.text}`}>{c.label}</span>;
}

export function PermSmallBadge({ perm }: { perm: string }) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    store_owner: { bg: "bg-emerald-500/10", text: "text-emerald-700/80", label: "门店可自主" },
    brand_approval: { bg: "bg-amber-500/10", text: "text-amber-700/80", label: "需品牌审批" },
    hq_only: { bg: "bg-red-500/10", text: "text-red-700/80", label: "仅总部" },
    unclear: { bg: "bg-surface-container-high/60", text: "text-on-surface-variant/80", label: "权限不明" },
  };
  const c = config[perm] || config.unclear;
  return <span className={`font-label-caps text-[8px] px-1.5 py-0.5 rounded-full ${c.bg} ${c.text}`}>{c.label}</span>;
}

export const PHASE_LABELS: Record<string, string> = {
  idea: "想法期",
  franchise_talk: "接店洽谈期",
  location_selection: "接店盘点期",
  renovation: "准备期",
  trial_operation: "试营业",
  active_operation: "正式经营",
};
