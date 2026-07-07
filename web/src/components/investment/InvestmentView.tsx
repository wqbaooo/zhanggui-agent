"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, Banknote, Boxes, CalendarClock, CheckCircle2, ReceiptText } from "lucide-react";
import { DEFAULT_PROJECT_ID, getPurchases, type PurchaseRecord } from "@/lib/api";
import { useProjectData } from "@/lib/hooks/useProjectData";

const TABS = [
  { key: "overview", label: "资金总览" },
  { key: "cashflow", label: "现金流" },
  { key: "sensitivity", label: "成本基准" },
  { key: "scenarios", label: "盈利条件" },
  { key: "breakdown", label: "会计分类" },
  { key: "risks", label: "缺口与风险" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

function money(value: number) {
  return `¥${value.toLocaleString("zh-CN", { minimumFractionDigits: value % 1 ? 2 : 0, maximumFractionDigits: 2 })}`;
}

function numberValue(profile: Record<string, unknown>, key: string) {
  const value = Number(profile[key]);
  return Number.isFinite(value) ? value : 0;
}

export function InvestmentView({ initialTab = "overview" }: { initialTab?: TabKey }) {
  const { cockpit, isLoading } = useProjectData();
  const [purchases, setPurchases] = useState<PurchaseRecord[]>([]);
  const [activeTab, setActiveTab] = useState<TabKey>(initialTab);
  const profile = cockpit?.profile || {};

  useEffect(() => {
    getPurchases(DEFAULT_PROJECT_ID, 30)
      .then((response) => setPurchases(response.purchases || []))
      .catch(() => setPurchases([]));
  }, []);

  const transferFee = numberValue(profile, "transfer_fee");
  const rent = numberValue(profile, "monthly_rent");
  const garbageFee = numberValue(profile, "monthly_garbage_fee");
  const labor = numberValue(profile, "monthly_labor");
  const rentStart = String(profile.monthly_rent_start_date || "");
  const paidPurchases = useMemo(
    () => purchases.filter((purchase) => purchase.payment_status.includes("已付")).reduce((sum, purchase) => sum + (purchase.paid_amount || purchase.total_cost), 0),
    [purchases],
  );
  const pendingInventory = useMemo(
    () => purchases.filter((purchase) => purchase.fulfillment_status === "ordered").reduce((sum, purchase) => sum + (purchase.paid_amount || purchase.total_cost), 0),
    [purchases],
  );
  const startupCashOut = transferFee + paidPurchases;
  const knownMonthlyFixedFromAugust = rent + garbageFee + labor;

  if (isLoading && !cockpit) {
    return <div className="h-1 w-full animate-pulse rounded-full bg-orange-300" />;
  }

  return (
    <div className="space-y-4">
      <section className="rounded-3xl border border-stone-200 bg-white/90 p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500">真实资金与成本</p>
            <h1 className="mt-2 text-2xl font-bold text-stone-950">钱花到哪里，不等于当期亏了多少</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-stone-600">
              现金流、资产和经营损益分开记录。采购付款会减少现金，但收货后先形成库存，只有被实际消耗的部分才进入商品成本。
            </p>
          </div>
          <span className="w-fit rounded-full bg-amber-100 px-3 py-1.5 text-xs font-semibold text-amber-800">利润模型尚未完整</span>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="接店投入" value={money(transferFee)} hint="长期投入/回本基数" icon={<ReceiptText className="h-5 w-5" />} />
          <Metric label="已付采购" value={money(paidPurchases)} hint={`${money(pendingInventory)} 仍在途`} icon={<Boxes className="h-5 w-5" />} />
          <Metric label="已知现金流出" value={money(startupCashOut)} hint="不等于当期费用" icon={<Banknote className="h-5 w-5" />} />
          <Metric label="8月起已知月固定" value={money(knownMonthlyFixedFromAugust)} hint="人工+房租+垃圾费，未含水电" icon={<CalendarClock className="h-5 w-5" />} />
        </div>
      </section>

      <nav className="flex gap-1 overflow-x-auto rounded-xl border border-stone-200 bg-white/75 p-1" aria-label="资金分析视图">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={`min-h-10 flex-1 whitespace-nowrap rounded-lg px-3 text-sm font-medium ${activeTab === tab.key ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100"}`}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {activeTab === "overview" && (
        <div className="grid gap-4 lg:grid-cols-3">
          <ClassificationCard title="接店投入" amount={transferFee} status="已确认" lines={["转租店面 ¥40,000", "进入回本基数", "不应一次性混入7月日经营成本"]} />
          <ClassificationCard title="采购存货" amount={paidPurchases} status={pendingInventory ? "待收货" : "已收货"} lines={["付款时：现金减少", "收货时：形成库存资产", "领用/销售时：按实际消耗进入成本"]} />
          <ClassificationCard title="月度经营费用" amount={knownMonthlyFixedFromAugust} status="部分确认" lines={["7月房租：本店不承担", `8月起房租：${money(rent)}/月`, `垃圾费：${money(garbageFee)}/月 · 水电待确认`]} />
        </div>
      )}

      {activeTab === "cashflow" && (
        <section className="rounded-2xl border border-stone-200 bg-white/85 p-5">
          <h2 className="text-base font-bold text-stone-950">当前现金流事实</h2>
          <div className="mt-4 space-y-3">
            <FlowRow from="银行卡/现金" action="支付接店转租款" to="长期投入" amount={transferFee} />
            <FlowRow from="银行卡" action="支付供应链订单" to={pendingInventory ? "预付/在途采购" : "库存资产"} amount={paidPurchases} />
            <FlowRow from="8月经营收入" action="按月承担" to="房租与垃圾费" amount={rent + garbageFee} />
          </div>
        </section>
      )}

      {activeTab === "sensitivity" && (
        <section className="rounded-2xl border border-stone-200 bg-white/85 p-5">
          <h2 className="text-base font-bold text-stone-950">已确认成本基准</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Fact label="7月房租" value="¥0" note={`合同成本从 ${rentStart || "2026-08-01"} 开始`} />
            <Fact label="8月起房租" value={money(rent)} note="按月计入经营费用，日分析再按当月天数摊销" />
            <Fact label="垃圾费" value={money(garbageFee)} note="每月固定费用" />
            <Fact label="水电费" value="待确认" note="不能用 ¥0 或猜测区间代替真实账单" warning />
          </div>
        </section>
      )}

      {activeTab === "scenarios" && (
        <section className="rounded-2xl border border-amber-200 bg-amber-50/65 p-5">
          <h2 className="text-base font-bold text-stone-950">现在不能保证盈利，但可以定义盈利成立条件</h2>
          <p className="mt-2 text-sm leading-6 text-stone-600">必须先补齐实际物料消耗、包装、人工、水电和平台结算，系统才计算贡献毛利、日保本额和回本周期。</p>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <Condition title="收入基准" body="客如云营业收入、退款、优惠和渠道服务费每日对账" />
            <Condition title="变动成本" body="商品销量 × BOM，与开包、生产批次、盘点差异互相核验" />
            <Condition title="固定成本" body="人工、8月起房租、垃圾费、水电按真实发生期摊销" />
          </div>
        </section>
      )}

      {activeTab === "breakdown" && (
        <section className="overflow-hidden rounded-2xl border border-stone-200 bg-white/85">
          <LedgerRow name="转租费" amount={transferFee} category="接店投入" profitImpact="不直接进入每日利润" />
          <LedgerRow name="供应链采购" amount={paidPurchases} category={pendingInventory ? "预付/在途资产" : "库存资产"} profitImpact="随实际消耗结转" />
          <LedgerRow name="7月房租" amount={0} category="本月费用" profitImpact="本店不承担" />
          <LedgerRow name="8月起房租" amount={rent} category="月固定费用" profitImpact="从8月开始" />
          <LedgerRow name="垃圾费" amount={garbageFee} category="月固定费用" profitImpact="每月计入" />
          <LedgerRow name="水电" amount={0} category="待确认" profitImpact="未录入前禁止确认净利" unknown />
        </section>
      )}

      {activeTab === "risks" && (
        <section className="rounded-2xl border border-red-200 bg-red-50/60 p-5">
          <div className="flex items-center gap-2 text-red-800"><AlertTriangle className="h-5 w-5" /><h2 className="font-bold">当前财务缺口</h2></div>
          <ul className="mt-4 space-y-2 text-sm leading-6 text-stone-700">
            <li>• 水电账单未确认，真实净利润和保本额不能出最终结论。</li>
            <li>• ¥13,791 采购仍待到货清点，不能提前增加库存。</li>
            <li>• 商品 BOM 与包装规格未完整，商品贡献利润仍是待计算状态。</li>
            <li>• 前老板代收团购券款需持续对账，避免“有销售、钱未到账”被忽略。</li>
          </ul>
        </section>
      )}
    </div>
  );
}

function Metric({ label, value, hint, icon }: { label: string; value: string; hint: string; icon: React.ReactNode }) {
  return <div className="rounded-xl border border-stone-200 bg-stone-50/80 p-4"><div className="flex items-center justify-between text-stone-500"><span className="text-xs font-medium">{label}</span>{icon}</div><p className="mt-2 text-xl font-bold tabular-nums text-stone-950">{value}</p><p className="mt-1 text-[11px] text-stone-500">{hint}</p></div>;
}

function ClassificationCard({ title, amount, status, lines }: { title: string; amount: number; status: string; lines: string[] }) {
  return <section className="rounded-2xl border border-stone-200 bg-white/85 p-5"><div className="flex items-center justify-between"><h2 className="font-bold text-stone-950">{title}</h2><span className="rounded-full bg-stone-100 px-2 py-1 text-[10px] text-stone-600">{status}</span></div><p className="mt-3 text-2xl font-bold tabular-nums text-stone-950">{money(amount)}</p><ul className="mt-4 space-y-2">{lines.map((line) => <li key={line} className="flex gap-2 text-xs leading-5 text-stone-600"><CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />{line}</li>)}</ul></section>;
}

function FlowRow({ from, action, to, amount }: { from: string; action: string; to: string; amount: number }) {
  return <div className="grid gap-2 rounded-xl border border-stone-200 p-3 sm:grid-cols-[1fr_auto_1fr_auto] sm:items-center"><span className="text-sm font-medium text-stone-900">{from}</span><span className="inline-flex items-center gap-1 text-xs text-stone-500">{action}<ArrowRight className="h-3.5 w-3.5" /></span><span className="text-sm font-medium text-stone-900">{to}</span><strong className="text-right tabular-nums text-stone-950">{money(amount)}</strong></div>;
}

function Fact({ label, value, note, warning = false }: { label: string; value: string; note: string; warning?: boolean }) {
  return <div className={`rounded-xl border p-4 ${warning ? "border-amber-200 bg-amber-50" : "border-stone-200 bg-stone-50"}`}><p className="text-xs text-stone-500">{label}</p><p className="mt-2 text-xl font-bold text-stone-950">{value}</p><p className="mt-1 text-xs leading-5 text-stone-500">{note}</p></div>;
}

function Condition({ title, body }: { title: string; body: string }) {
  return <div className="rounded-xl border border-amber-200 bg-white/80 p-4"><p className="text-sm font-bold text-stone-950">{title}</p><p className="mt-2 text-xs leading-5 text-stone-600">{body}</p></div>;
}

function LedgerRow({ name, amount, category, profitImpact, unknown = false }: { name: string; amount: number; category: string; profitImpact: string; unknown?: boolean }) {
  return <div className="grid gap-2 border-b border-stone-100 px-5 py-4 last:border-0 md:grid-cols-[1fr_140px_180px_1.4fr] md:items-center"><strong className="text-sm text-stone-950">{name}</strong><span className="text-sm tabular-nums text-stone-900">{unknown ? "待确认" : money(amount)}</span><span className="text-xs text-stone-500">{category}</span><span className="text-xs text-stone-500">{profitImpact}</span></div>;
}
