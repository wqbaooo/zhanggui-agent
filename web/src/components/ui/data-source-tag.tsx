import { dataSources, type DataConfidence } from "@/data/agent-store-os";

interface DataSourceTagProps {
  sourceId?: string;
  sourceLabel?: string;
  confidence?: DataConfidence;
  showConfidence?: boolean;
  className?: string;
}

const CONFIDENCE_STYLES: Record<DataConfidence, string> = {
  high: "text-nori-700 bg-nori-50 border-nori-200",
  medium: "text-sauce-700 bg-sauce-50 border-sauce-200",
  low: "text-red-700 bg-red-50 border-red-200",
};

const CONFIDENCE_LABEL: Record<DataConfidence, string> = {
  high: "高可信",
  medium: "待校准",
  low: "低可信",
};

export function DataSourceTag({
  sourceId,
  sourceLabel,
  confidence,
  showConfidence = true,
  className,
}: DataSourceTagProps) {
  const source = sourceId ? dataSources.find((s) => s.id === sourceId) : undefined;
  const emoji = source?.emoji || "📋";
  const label = source?.label || sourceLabel || "未知来源";
  const conf = source?.confidence || confidence || "medium";
  const confStyle = CONFIDENCE_STYLES[conf];

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${confStyle} ${className || ""}`}>
      <span className="text-[11px]">{emoji}</span>
      <span>{label}</span>
      {showConfidence && <span className="opacity-60">· {CONFIDENCE_LABEL[conf]}</span>}
    </span>
  );
}
