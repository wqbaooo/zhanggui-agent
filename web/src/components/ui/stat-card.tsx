"use client";

import { motion } from "framer-motion";
import type { ReactNode } from "react";
import CountUp from "react-countup";
import { Sparkline } from "./sparkline";

interface StatCardProps {
  label: string;
  value: number;
  unit?: string;
  prefix?: string;
  suffix?: string;
  trend?: number[];
  trendLabel?: string;
  icon?: ReactNode;
  emoji?: string;
  tone?: "default" | "success" | "warning" | "danger";
  delay?: number;
}

const TONE_STYLES = {
  default: { accent: "text-octo-500", bg: "bg-octo-50" },
  success: { accent: "text-nori-600", bg: "bg-nori-50" },
  warning: { accent: "text-sauce-600", bg: "bg-sauce-50" },
  danger: { accent: "text-red-600", bg: "bg-red-50" },
} as const;

export function StatCard({
  label,
  value,
  unit,
  prefix,
  suffix,
  trend,
  trendLabel,
  icon,
  emoji,
  tone = "default",
  delay = 0,
}: StatCardProps) {
  const styles = TONE_STYLES[tone];
  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1], delay }}
      className="glass-card rounded-xl p-4"
    >
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <p className="font-label-caps text-stone-500">{label}</p>
          <div className="mt-1.5 flex items-baseline gap-1">
            {prefix && <span className={`text-lg font-semibold ${styles.accent}`}>{prefix}</span>}
            <CountUp
              end={value}
              duration={0.6}
              separator=","
              decimals={value % 1 !== 0 ? 1 : 0}
              className="font-data-mono text-2xl font-semibold text-stone-900"
            />
            {unit && <span className="text-sm text-stone-500">{unit}</span>}
            {suffix && <span className={`text-sm font-medium ${styles.accent}`}>{suffix}</span>}
          </div>
          {trendLabel && <p className="mt-1 text-xs text-stone-400">{trendLabel}</p>}
        </div>
        <div className={`flex shrink-0 items-center justify-center rounded-lg ${styles.bg} h-9 w-9 text-base`}>
          {emoji || icon}
        </div>
      </div>
      {trend && trend.length > 1 && (
        <div className="mt-3 flex items-center justify-between">
          <Sparkline data={trend} width={80} height={20} />
        </div>
      )}
    </motion.div>
  );
}
