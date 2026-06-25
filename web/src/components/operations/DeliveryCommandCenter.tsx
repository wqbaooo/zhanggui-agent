"use client";

import { useMemo, useState } from "react";
import { BarChart3, Bot, ClipboardPaste, MessageSquareWarning, ShieldAlert, TrendingUp, UploadCloud, Zap } from "lucide-react";
import { mockDeliveryFunnel, mockPlatformComparison, mockPlatformMetrics } from "@/data/mockProject";
import { createDeliveryImport } from "@/lib/api";
import { fmtMoney } from "@/domain/calculations";

const importHints = [
  "美团商家后台：昨日曝光4200，进店756，下单47，营业额850，平台费187，满减35，差评1",
  "淘宝闪购：曝光1800，进店288，下单18，营业额320，佣金64，差评率3%",
  "抖音团购：曝光3500，访问175，核销4单，营业额70，佣金4，转化率0.6%",
];

function parseImportText(text: string) {
  const pick = (patterns: RegExp[]) => {
    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match?.[1]) return Number(match[1]);
    }
    return 0;
  };

  return {
    revenue: pick([/营业额\s*(\d+(?:\.\d+)?)/, /营收\s*(\d+(?:\.\d+)?)/]),
    orders: pick([/下单\s*(\d+)/, /订单\s*(\d+)/, /核销\s*(\d+)/]),
    impressions: pick([/曝光\s*(\d+)/]),
    visits: pick([/进店\s*(\d+)/, /访问\s*(\d+)/]),
    platformFee: pick([/平台费\s*(\d+(?:\.\d+)?)/, /佣金\s*(\d+(?:\.\d+)?)/]),
    discount: pick([/满减\s*(\d+(?:\.\d+)?)/, /补贴\s*(\d+(?:\.\d+)?)/]),
    badReviews: pick([/差评\s*(\d+)/]),
  };
}

export function DeliveryCommandCenter() {
  const [rawText, setRawText] = useState(importHints[0]);
  const [source, setSource] = useState("meituan");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const parsed = useMemo(() => parseImportText(rawText), [rawText]);
  const totalRevenue = mockPlatformComparison.totals.revenue;
  const totalOrders = mockPlatformComparison.totals.orders;
  const totalFees = mockPlatformComparison.totals.totalCommission;
  const avgProfit = totalOrders > 0 ? (totalRevenue - totalFees) / totalOrders : 0;
  const weakPlatform = mockPlatformMetrics.find((item) => item.overallConversion < 0.02);
  const highFeePlatform = mockPlatformMetrics.find((item) => item.commissionRate >= 0.22);
  const aiDiagnosis = useMemo(() => {
    const feeRate = parsed.revenue ? parsed.platformFee / parsed.revenue : 0;
    const visitRate = parsed.impressions ? parsed.visits / parsed.impressions : 0;
    const orderRate = parsed.visits ? parsed.orders / parsed.visits : 0;
    const alerts = [
      feeRate > 0.2 ? "平台扣费偏高，先核算满减后单均利润，别盲目冲单。" : "平台扣费暂未超过警戒线，重点看转化和复购。",
      visitRate && visitRate < 0.12 ? "曝光没有有效进店，优先改门店图、标题、评分露出。" : "进店率不算最差，下一步看下单转化。",
      orderRate && orderRate < 0.18 ? "进店后不下单，套餐价格锚点或配送门槛可能有问题。" : "下单转化可继续监控，先找利润最低的套餐。",
      parsed.badReviews > 0 ? `昨日识别到 ${parsed.badReviews} 条差评，要拆成出餐、包装、口味、配送四类。` : "未识别到差评数量，建议补充评价摘要。",
    ];
    return { feeRate, visitRate, orderRate, alerts };
  }, [parsed]);

  async function handleSaveImport() {
    setSaveState("saving");
    try {
      await createDeliveryImport({ source, raw_text: rawText, parsed });
      setSaveState("saved");
    } catch {
      setSaveState("error");
    }
  }

  return (
    <div className="space-y-4">
      <section className="glass-card interactive-card rounded-xl p-5">
        <div className="relative z-10 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="font-label-caps text-on-surface-variant">外卖部 Agent · 商家侧诊断</p>
            <h1 className="mt-1 text-2xl font-semibold text-on-background">外卖渠道经营诊断</h1>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-on-surface-variant">
              这不是做外卖平台，而是帮你的门店看清外卖渠道：曝光有没有变成订单、满减是否亏钱、评价问题在哪里、今天该改哪个动作。美团、淘宝闪购、抖音只是数据来源。
            </p>
          </div>
          <div className="grid grid-cols-3 gap-2 lg:w-[420px]">
            <Metric label="外卖营收" value={fmtMoney(totalRevenue)} />
            <Metric label="外卖订单" value={`${totalOrders}单`} />
            <Metric label="扣点/佣金" value={fmtMoney(totalFees)} warning={totalFees > totalRevenue * 0.18} />
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <section className="glass-card interactive-card rounded-xl p-4">
          <div className="relative z-10">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="font-label-caps text-on-surface-variant">商家后台漏斗</p>
                <h2 className="text-lg font-semibold text-on-background">曝光 → 进店 → 下单 → 复购</h2>
              </div>
              <BarChart3 className="h-5 w-5 text-agent-gold" />
            </div>
            <div className="space-y-3">
              {mockDeliveryFunnel.map((item) => (
                <div key={item.platform} className="rounded-lg border border-muted-border/25 bg-surface-container-high/25 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm font-medium text-on-background">{item.platformName}</span>
                    <span className="text-[10px] font-mono text-on-surface-variant">整体转化 {(item.rates.overallRate * 100).toFixed(1)}%</span>
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-center">
                    <FunnelStep label="曝光" value={item.data.impressions} pct={1} />
                    <FunnelStep label="进店" value={item.data.storeVisits} sub={`${(item.rates.visitRate * 100).toFixed(0)}%`} pct={item.rates.visitRate} />
                    <FunnelStep label="下单" value={item.data.orders} sub={`${(item.rates.orderRate * 100).toFixed(0)}%`} pct={item.rates.orderRate} />
                    <FunnelStep label="复购" value={item.data.repeatOrders} sub={`${(item.rates.repeatRate * 100).toFixed(0)}%`} pct={item.rates.repeatRate} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="glass-card interactive-card rounded-xl p-4">
          <div className="relative z-10">
            <div className="mb-3 flex items-center gap-2">
              <ClipboardPaste className="h-4 w-4 text-agent-gold" />
              <div>
                <p className="font-label-caps text-on-surface-variant">笨办法接入</p>
                <h2 className="text-lg font-semibold text-on-background">复制商家后台日报</h2>
              </div>
            </div>
            <div className="mb-2 flex flex-wrap gap-1.5">
              {[
                ["meituan", "美团"],
                ["taobao_flash", "淘宝闪购"],
                ["douyin", "抖音"],
                ["manual", "手动"],
              ].map(([item, label]) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setSource(item)}
                  className={`rounded-full px-2.5 py-1 text-[10px] font-mono transition-colors ${source === item ? "bg-agent-gold text-background" : "border border-muted-border/35 text-on-surface-variant hover:border-agent-gold/50"}`}
                >
                  {label}
                </button>
              ))}
            </div>
            <textarea
              value={rawText}
              onChange={(event) => setRawText(event.target.value)}
              className="min-h-28 w-full resize-none rounded-lg border border-muted-border/35 bg-background/20 px-3 py-2 text-xs leading-relaxed text-on-background outline-none focus:border-agent-gold/50"
            />
            <div className="mt-3 grid grid-cols-3 gap-2">
              <Metric label="解析营收" value={parsed.revenue ? fmtMoney(parsed.revenue) : "未识别"} />
              <Metric label="解析订单" value={parsed.orders ? `${parsed.orders}单` : "未识别"} />
              <Metric label="解析扣费" value={parsed.platformFee ? fmtMoney(parsed.platformFee) : "未识别"} />
            </div>
            <button
              type="button"
              onClick={handleSaveImport}
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-agent-gold px-3 py-2 text-xs font-semibold text-background transition-opacity disabled:opacity-50"
              disabled={saveState === "saving" || !rawText.trim()}
            >
              <UploadCloud className="h-3.5 w-3.5" />
              {saveState === "saving" ? "保存中..." : saveState === "saved" ? "已保存到项目档案" : "保存导入记录"}
            </button>
            {saveState === "error" && (
              <p className="mt-2 text-[10px] text-error">保存失败。后端没启动时不会丢失当前输入，可稍后重试。</p>
            )}
          </div>
        </section>
      </div>

      <section className="glass-card interactive-card rounded-xl p-4">
        <div className="relative z-10 grid gap-4 xl:grid-cols-[260px_1fr]">
          <div>
            <div className="flex items-center gap-2 text-primary">
              <Bot className="h-4 w-4" />
              <p className="font-label-caps">AI 经营判断</p>
            </div>
            <h2 className="mt-2 text-lg font-semibold text-on-background">把后台数字翻译成老板动作</h2>
            <p className="mt-2 text-xs leading-relaxed text-on-surface-variant">
              你不用学平台复杂报表。每天复制日报后，系统先判断流量、转化、扣费、评价四件事，再给你当天该改的动作。
            </p>
          </div>
          <div className="grid gap-3 lg:grid-cols-4">
            <AiSignal label="扣费率" value={aiDiagnosis.feeRate ? `${(aiDiagnosis.feeRate * 100).toFixed(1)}%` : "待识别"} danger={aiDiagnosis.feeRate > 0.2} />
            <AiSignal label="进店率" value={aiDiagnosis.visitRate ? `${(aiDiagnosis.visitRate * 100).toFixed(1)}%` : "待识别"} danger={Boolean(aiDiagnosis.visitRate && aiDiagnosis.visitRate < 0.12)} />
            <AiSignal label="下单率" value={aiDiagnosis.orderRate ? `${(aiDiagnosis.orderRate * 100).toFixed(1)}%` : "待识别"} danger={Boolean(aiDiagnosis.orderRate && aiDiagnosis.orderRate < 0.18)} />
            <AiSignal label="差评数" value={parsed.badReviews ? `${parsed.badReviews}条` : "待补充"} danger={parsed.badReviews > 0} />
          </div>
        </div>
        <div className="relative z-10 mt-3 grid gap-2 lg:grid-cols-2">
          {aiDiagnosis.alerts.map((alert) => (
            <div key={alert} className="rounded-lg border border-muted-border/30 bg-surface-container-high/25 px-3 py-2 text-xs leading-relaxed text-on-surface-variant transition-all hover:border-primary/25 hover:bg-primary-container/30">
              {alert}
            </div>
          ))}
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-3">
        <DiagnosisCard
          icon={<ShieldAlert className="h-4 w-4" />}
          title="佣金和满减压力"
          body={`${highFeePlatform?.platformName ?? "美团外卖"} 扣点偏高，单均利润约 ${fmtMoney(avgProfit)}。先核算满减后每单真实利润，再决定是否继续拉高外卖占比。`}
          action="今天先导出 TOP20 商品外卖毛利"
        />
        <DiagnosisCard
          icon={<MessageSquareWarning className="h-4 w-4" />}
          title="评价与差评"
          body="差评不能只回复，要聚类到出餐慢、包装漏、骑手等待、口味波动四类，再对应改流程。"
          action="建立 7 天差评原因表"
        />
        <DiagnosisCard
          icon={<TrendingUp className="h-4 w-4" />}
          title="流量转化短板"
          body={`${weakPlatform?.platformName ?? "抖音本地生活"} 曝光不低但转化弱，优先检查团购标题、套餐图片、价格锚点和评价露出。`}
          action="重做 1 个高毛利引流套餐"
        />
      </div>

      <section className="glass-card interactive-card rounded-xl p-4">
        <div className="relative z-10">
          <div className="mb-3 flex items-center gap-2">
            <Zap className="h-4 w-4 text-agent-gold" />
            <h2 className="text-lg font-semibold text-on-background">今日运营动作</h2>
          </div>
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            {[
              "导出美团/淘宝闪购昨日订单与评价",
              "核算外卖 TOP10 商品单均利润",
              "回复所有差评并记录根因",
              "测试一个不亏钱的满减套餐",
            ].map((item, index) => (
              <div key={item} className="rounded-lg bg-surface-container-high/25 px-3 py-2 text-xs text-on-surface-variant">
                <span className="mr-2 font-mono text-agent-gold">{index + 1}</span>
                {item}
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function AiSignal({ label, value, danger = false }: { label: string; value: string; danger?: boolean }) {
  return (
    <div className={`rounded-lg border px-3 py-2 transition-all hover:-translate-y-0.5 ${danger ? "border-amber-500/25 bg-amber-500/10" : "border-primary/15 bg-primary-container/35"}`}>
      <p className="font-label-caps text-on-surface-variant">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${danger ? "text-amber-800" : "text-primary"}`}>{value}</p>
    </div>
  );
}

function Metric({ label, value, warning = false }: { label: string; value: string; warning?: boolean }) {
  return (
    <div className="rounded-lg bg-surface-container-high/30 px-3 py-2">
      <p className="font-label-caps text-on-surface-variant">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${warning ? "text-amber-700" : "text-on-background"}`}>{value}</p>
    </div>
  );
}

function FunnelStep({ label, value, sub, pct }: { label: string; value: number; sub?: string; pct: number }) {
  const width = Math.max(8, Math.min(100, pct * 100));
  return (
    <div className="group rounded-lg bg-background/20 px-2 py-2 transition-all hover:-translate-y-0.5 hover:bg-primary-container/40">
      <p className="text-[9px] text-on-surface-variant/60">{label}</p>
      <p className="mt-1 text-sm font-semibold text-on-background">{value}</p>
      {sub && <p className="text-[9px] text-agent-gold">{sub}</p>}
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-container-high">
        <div className="meter-fill h-full rounded-full bg-primary group-hover:bg-secondary" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function DiagnosisCard({ icon, title, body, action }: { icon: React.ReactNode; title: string; body: string; action: string }) {
  return (
    <section className="glass-card interactive-card rounded-xl p-4">
      <div className="relative z-10">
        <div className="mb-2 flex items-center gap-2 text-agent-gold">
          {icon}
          <h2 className="text-sm font-semibold text-on-background">{title}</h2>
        </div>
        <p className="text-xs leading-relaxed text-on-surface-variant">{body}</p>
        <p className="mt-3 rounded-lg border border-agent-gold/20 bg-agent-gold/5 px-3 py-2 text-[11px] text-agent-gold">
          {action}
        </p>
      </div>
    </section>
  );
}
