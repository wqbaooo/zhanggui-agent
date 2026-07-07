"use client";

import { useEffect, useState } from "react";
import { Clock, FileImage, FileText, Mic, Database, AlertCircle, CheckCircle, type LucideIcon } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { DEFAULT_PROJECT_ID, getCaptureAuditLog, type CaptureAuditLogItem } from "@/lib/api";

const sourceTypeLabels: Record<string, { label: string; icon: LucideIcon }> = {
  image: { label: "图片", icon: FileImage },
  speech: { label: "语音", icon: Mic },
  text: { label: "文字", icon: FileText },
  manual: { label: "手动", icon: FileText },
  csv: { label: "CSV", icon: FileText },
};

const statusLabels: Record<string, { label: string; icon: LucideIcon; color: string }> = {
  written: { label: "已写入", icon: CheckCircle, color: "text-emerald-600 bg-emerald-100" },
  confirmed: { label: "已确认", icon: CheckCircle, color: "text-blue-600 bg-blue-100" },
  recognized: { label: "待确认", icon: AlertCircle, color: "text-amber-600 bg-amber-100" },
  failed: { label: "失败", icon: AlertCircle, color: "text-red-600 bg-red-100" },
};

export default function CaptureHistoryPage() {
  const [logs, setLogs] = useState<CaptureAuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const captureModule = getModule("/capture");

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await getCaptureAuditLog(DEFAULT_PROJECT_ID, 50);
        if (mounted) setLogs(res.logs || []);
      } catch {
        /* ignore */
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  const formatTime = (ts: number) => {
    const d = new Date(ts * 1000);
    return d.toLocaleString("zh-CN", {
      month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
    });
  };

  const renderField = (field: unknown) => {
    if (typeof field === "object" && field !== null && "key" in field) {
      const value = field as { key: string; label?: string; value?: unknown };
      return `${value.label || value.key}: ${String(value.value ?? "")}`;
    }
    return String(field);
  };

  return (
    <ModulePage module={captureModule}>
      <section className="rounded-xl border border-muted-border/35 bg-surface/95 p-4 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="font-label-caps text-on-surface-variant">录入历史</p>
            <h2 className="text-lg font-semibold text-on-background">最近 50 条记录</h2>
          </div>
          <a href="/capture" className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500">
            去录入
          </a>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent" />
          </div>
        ) : logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Database className="h-12 w-12 text-on-surface-variant/30" />
            <p className="mt-3 text-on-surface-variant">暂无录入记录</p>
            <p className="mt-1 text-sm text-on-surface-variant/60">上传图片或录音开始录入</p>
          </div>
        ) : (
          <div className="space-y-2">
            {logs.map((log) => {
              const srcInfo = sourceTypeLabels[log.source_type] || sourceTypeLabels.manual;
              const SrcIcon = srcInfo.icon;
              const statusInfo = statusLabels[log.review_status] || statusLabels.recognized;
              const StatusIcon = statusInfo.icon;
              return (
                <div key={log.id} className="rounded-lg border border-muted-border/30 p-3 hover:bg-surface-muted/30">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 rounded-md bg-blue-100 p-1.5">
                        <SrcIcon className="h-3.5 w-3.5 text-blue-600" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium text-on-background">{log.file_name || "未命名文件"}</p>
                          <span className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${statusInfo.color}`}>
                            <StatusIcon className="h-2.5 w-2.5" />
                            {statusInfo.label}
                          </span>
                        </div>
                        <div className="mt-1 flex items-center gap-3 text-xs text-on-surface-variant">
                          <span className="inline-flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatTime(log.timestamp)}
                          </span>
                          <span>写入：{log.write_target || "未写入"}</span>
                          {log.date && <span>日期：{log.date}</span>}
                        </div>
                        {log.recognized_fields && log.recognized_fields.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1">
                            {log.recognized_fields.slice(0, 6).map((f, i) => (
                              <span key={i} className="rounded-md bg-surface-muted/40 px-1.5 py-0.5 text-[11px] text-on-surface-variant">
                                {renderField(f)}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </ModulePage>
  );
}
