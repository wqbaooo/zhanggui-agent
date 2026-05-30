import { cn } from "@/lib/utils";

export function MetricCard({
  label, value, trend, trendLabel, negative, onClick,
}: {
  label: string;
  value: string;
  trend?: "up" | "down" | "flat";
  trendLabel?: string;
  negative?: boolean;
  onClick?: () => void;
}) {
  const El = onClick ? "button" : "div";
  return (
    <El
      onClick={onClick}
      className="rounded-xl border border-cream-200 bg-white p-3.5 text-left hover:bg-cream-50 transition-colors"
    >
      <p className="text-[10px] text-gray-400 font-medium">{label}</p>
      <div className="flex items-baseline gap-2 mt-1">
        <span className={cn(
          "text-lg font-bold",
          negative ? "text-red-600" : "text-gray-800"
        )} style={{ fontFamily: "Antonio, sans-serif" }}>
          {value}
        </span>
        {trend && trend !== "flat" && (
          <span className={cn(
            "text-[10px] font-semibold",
            trend === "up" ? (negative ? "text-red-500" : "text-emerald-600") : (negative ? "text-emerald-600" : "text-red-500")
          )}>
            {trend === "up" ? "↗" : "↘"} {trendLabel}
          </span>
        )}
      </div>
    </El>
  );
}
