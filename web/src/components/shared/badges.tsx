import type { RiskLevel, PermissionStatus, FulfillmentStatus } from "@/domain/types";

export const RISK_BADGE: Record<RiskLevel, { bg: string; text: string; label: string }> = {
  low: { bg: "bg-emerald-500/15", text: "text-emerald-400", label: "低" },
  medium: { bg: "bg-amber-500/15", text: "text-amber-400", label: "中" },
  high: { bg: "bg-red-500/15", text: "text-red-400", label: "高" },
  critical: { bg: "bg-red-600/20", text: "text-red-300", label: "极高" },
};

export function PermBadge({ status }: { status: PermissionStatus }) {
  const config: Record<PermissionStatus, { bg: string; text: string; label: string }> = {
    hq_control: { bg: "bg-red-500/15", text: "text-red-400", label: "总部控制" },
    hq_approval: { bg: "bg-amber-500/15", text: "text-amber-400", label: "需总部审批" },
    store_autonomous: { bg: "bg-emerald-500/15", text: "text-emerald-400", label: "门店自主" },
    unclear: { bg: "bg-black/[0.240]", text: "text-black/85", label: "合同未明确" },
  };
  const c = config[status];
  return <span className={`mono-tag text-[9px] px-1.5 py-0.5 rounded-full ${c.bg} ${c.text}`}>{c.label}</span>;
}

export function FulfillBadge({ status }: { status: FulfillmentStatus }) {
  const config: Record<FulfillmentStatus, { bg: string; text: string; label: string }> = {
    fulfilled: { bg: "bg-emerald-500/15", text: "text-emerald-400", label: "已兑现" },
    partial: { bg: "bg-amber-500/15", text: "text-amber-400", label: "部分兑现" },
    not_fulfilled: { bg: "bg-red-500/15", text: "text-red-400", label: "未兑现" },
    not_agreed: { bg: "bg-black/[0.240]", text: "text-black/85", label: "未约定" },
    pending: { bg: "bg-blue-500/15", text: "text-blue-400", label: "待验证" },
  };
  const c = config[status];
  return <span className={`mono-tag text-[9px] px-1.5 py-0.5 rounded-full ${c.bg} ${c.text}`}>{c.label}</span>;
}

export function PermSmallBadge({ perm }: { perm: string }) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    store_owner: { bg: "bg-emerald-500/10", text: "text-emerald-400/60", label: "门店可自主" },
    brand_approval: { bg: "bg-amber-500/10", text: "text-amber-400/60", label: "需品牌审批" },
    hq_only: { bg: "bg-red-500/10", text: "text-red-400/60", label: "仅总部" },
    unclear: { bg: "bg-black/[0.200]", text: "text-black/80", label: "权限不明" },
  };
  const c = config[perm] || config.unclear;
  return <span className={`mono-tag text-[8px] px-1.5 py-0.5 rounded-full ${c.bg} ${c.text}`}>{c.label}</span>;
}

export const PHASE_LABELS: Record<string, string> = {
  idea: "想法期",
  franchise_talk: "加盟洽谈期",
  location_selection: "选址期",
  renovation: "装修期",
  trial_operation: "试营业",
  active_operation: "正式经营",
};
