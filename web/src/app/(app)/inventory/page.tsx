"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import Image from "next/image";
import { motion } from "framer-motion";
import { useSearchParams } from "next/navigation";
import {
  ArrowLeftRight,
  BarChart3,
  Boxes,
  CalendarCheck,
  Check,
  ChevronRight,
  ClipboardList,
  CookingPot,
  History,
  FileText,
  PackageCheck,
  Printer,
  RefreshCw,
  Store,
  X,
} from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import {
  DEFAULT_PROJECT_ID,
  createInventoryCount,
  createInventoryTransfer,
  replaceInventoryUsage,
  createInventoryWaste,
  createProductionBatch,
  getFirstStageInventory,
  getForecast,
  getInventoryCounts,
  getInventoryEvents,
  getInventorySummary,
  getInventoryUsageLogs,
  getInventoryVariance,
  getPurchases,
  getProductionBatches,
  getSkus,
  getStoreOperatingFacts,
  receivePurchase,
  type FirstStageInventory,
  type ForecastItem,
  type InventoryCountRecord,
  type InventoryEvent,
  type InventorySummary,
  type InventoryUsageLog,
  type InventoryVariance,
  type PurchaseRecord,
  type ProductionBatch,
  type SkuItem,
  type StoreOperatingFactsV1,
} from "@/lib/api";
import { DataSourceTag } from "@/components/ui/data-source-tag";
import { StatusTag } from "@/components/ui/status-tag";

type InventoryTab = "overview" | "usage" | "count" | "flow" | "analysis" | "production" | "forms";
type PrintSheet = "daily" | "weekly" | null;
type LocationKey = "store" | "warehouse" | "freezer" | "unallocated";

const LOCATION_LABELS: Record<LocationKey, string> = { store: "门店", warehouse: "仓库", freezer: "大冰箱", unallocated: "待分配" };
const EVENT_LABELS: Record<string, string> = {
  receipt: "收货",
  transfer: "调拨",
  usage: "开包领用",
  count_adjustment: "盘点校准",
  production_issue: "生产领料",
  waste: "报损",
};
const REAL_FIXTURE_DATE = "2026-07-04";
const DAILY_USAGE_GROUPS = [
  { label: "基础粉料", names: ["章鱼预拌粉", "调料包"], tone: "border-emerald-200 bg-emerald-50 text-emerald-900", printFill: "#e7f3ef" },
  { label: "酱料", names: ["原味酱", "香甜酱", "藤椒酱", "蛋黄酱", "番茄酱", "芥末酱", "奶酪酱"], tone: "border-amber-200 bg-amber-50 text-amber-950", printFill: "#fbf1dc" },
  { label: "撒料", names: ["木鱼花", "切丝海苔", "青海苔粉", "海苔肉松"], tone: "border-lime-200 bg-lime-50 text-lime-950", printFill: "#edf3df" },
  { label: "冷链配料", names: ["章鱼粒", "章鱼花", "玉米粒", "培根丁", "肉肠", "麻辣鲜蛤", "咸蛋黄", "芝士", "蟹柳"], tone: "border-sky-200 bg-sky-50 text-sky-950", printFill: "#e7f1f7" },
  { label: "餐盒与袋装", names: ["章鱼烧盒子（4粒）", "章鱼烧盒子（6粒）", "全家福打包盒", "全家福打包盒塑料盖", "外卖塑料袋", "外卖无纺布袋"], tone: "border-orange-200 bg-orange-50 text-orange-950", printFill: "#faeee3" },
  { label: "出餐辅助耗材", names: ["纸巾", "竹签", "烤肠竹签"], tone: "border-stone-200 bg-stone-100 text-stone-800", printFill: "#f0efec" },
  { label: "标签与收银耗材", names: ["外卖贴纸", "标签纸", "收银纸80*80", "收银纸57*50"], tone: "border-slate-200 bg-slate-100 text-slate-800", printFill: "#edf0f2" },
];
const DAILY_USAGE_PRIORITY = DAILY_USAGE_GROUPS.flatMap((group) => group.names);

function shanghaiDate() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai" }).format(new Date());
}

function unitOf(sku: SkuItem) {
  return sku.display_unit || sku.standard_unit || sku.unit || "单位";
}

function stockOf(sku: SkuItem, location: LocationKey) {
  if (sku.stock_by_location && typeof sku.stock_by_location[location] === "number") {
    return sku.stock_by_location[location];
  }
  return location === "unallocated" ? sku.current_stock || 0 : 0;
}

function displayNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function skuImage(sku: SkuItem) {
  return sku.hq_image || "";
}

export default function InventoryPage() {
  const [skus, setSkus] = useState<SkuItem[]>([]);
  const [summary, setSummary] = useState<InventorySummary | null>(null);
  const [counts, setCounts] = useState<InventoryCountRecord[]>([]);
  const [usageLogs, setUsageLogs] = useState<InventoryUsageLog[]>([]);
  const [events, setEvents] = useState<InventoryEvent[]>([]);
  const [variance, setVariance] = useState<InventoryVariance | null>(null);
  const [firstStageInventory, setFirstStageInventory] = useState<FirstStageInventory | null>(null);
  const [purchases, setPurchases] = useState<PurchaseRecord[]>([]);
  const [productionBatches, setProductionBatches] = useState<ProductionBatch[]>([]);
  const [operatingFacts, setOperatingFacts] = useState<StoreOperatingFactsV1 | null>(null);
  const [forecast, setForecast] = useState<ForecastItem[]>([]);
  const [activeTab, setActiveTab] = useState<InventoryTab>("overview");
  const [category, setCategory] = useState("全部");
  const [selectedSkuId, setSelectedSkuId] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [printSheet, setPrintSheet] = useState<PrintSheet>(null);

  const fetchData = useCallback(async () => {
    setLoadError(null);
    try {
      const [skuRes, summaryRes, countRes, usageRes, eventRes, varianceRes, purchaseRes, productionRes, firstStageRes, operatingFactRes, forecastRes] = await Promise.all([
        getSkus(DEFAULT_PROJECT_ID),
        getInventorySummary(DEFAULT_PROJECT_ID),
        getInventoryCounts(DEFAULT_PROJECT_ID, 20),
        getInventoryUsageLogs(DEFAULT_PROJECT_ID, 31),
        getInventoryEvents(DEFAULT_PROJECT_ID, 60),
        getInventoryVariance(DEFAULT_PROJECT_ID, 12),
        getPurchases(DEFAULT_PROJECT_ID, 50),
        getProductionBatches(DEFAULT_PROJECT_ID, 30),
        getFirstStageInventory(DEFAULT_PROJECT_ID, REAL_FIXTURE_DATE),
        getStoreOperatingFacts(DEFAULT_PROJECT_ID),
        getForecast(DEFAULT_PROJECT_ID),
      ]);
      setSkus(skuRes.skus || []);
      setSummary(summaryRes);
      setCounts(countRes.counts || []);
      setUsageLogs(usageRes.logs || []);
      setEvents(eventRes.events || []);
      setVariance(varianceRes);
      setFirstStageInventory(firstStageRes);
      setPurchases(purchaseRes.purchases || []);
      setProductionBatches(productionRes.batches || []);
      setOperatingFacts(operatingFactRes);
      setForecast(forecastRes.forecast || []);
      if (!selectedSkuId) {
        const firstInventorySku = skuRes.skus?.find(
          (sku) => sku.active !== false && sku.asset_class !== "equipment" && sku.tracking_mode !== "asset_registry",
        );
        if (firstInventorySku) setSelectedSkuId(firstInventorySku.id);
      }
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "库存数据加载失败");
    }
  }, [selectedSkuId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const activeSkus = useMemo(() => skus.filter((sku) => sku.active !== false), [skus]);
  const inventorySkus = useMemo(() => activeSkus
    .filter((sku) => sku.asset_class !== "equipment" && sku.tracking_mode !== "asset_registry")
    .sort((left, right) => {
      const leftIndex = DAILY_USAGE_PRIORITY.indexOf(left.name);
      const rightIndex = DAILY_USAGE_PRIORITY.indexOf(right.name);
      if (leftIndex >= 0 || rightIndex >= 0) return (leftIndex < 0 ? 999 : leftIndex) - (rightIndex < 0 ? 999 : rightIndex);
      return left.category.localeCompare(right.category, "zh-CN") || left.name.localeCompare(right.name, "zh-CN");
    }), [activeSkus]);
  const dailyUsageSkus = useMemo(
    () => inventorySkus.filter((sku) => sku.tracking_mode === "daily_usage"),
    [inventorySkus],
  );
  const categories = useMemo(() => ["全部", ...Array.from(new Set(inventorySkus.map((sku) => sku.category)))], [inventorySkus]);
  const filteredSkus = useMemo(
    () => category === "全部" ? inventorySkus : inventorySkus.filter((sku) => sku.category === category),
    [inventorySkus, category],
  );
  const selectedSku = inventorySkus.find((sku) => sku.id === selectedSkuId) || inventorySkus[0];

  async function afterSave(message: string) {
    setNotice(message);
    await fetchData();
    window.setTimeout(() => setNotice(null), 3500);
  }

  function print(type: Exclude<PrintSheet, null>) {
    setPrintSheet(type);
    window.setTimeout(() => {
      window.print();
      setPrintSheet(null);
    }, 80);
  }

  const currentModule = getModule("/inventory");

  return (
    <ModulePage module={currentModule}>
      <style jsx global>{`
        .inventory-print { display: none; }
        @media print {
          @page { size: ${printSheet === "daily" ? "A4 portrait" : "A4 landscape"}; margin: 7mm; }
          body * { visibility: hidden !important; }
          .inventory-print, .inventory-print * { visibility: visible !important; }
          .inventory-print {
            display: block !important;
            position: absolute;
            inset: 0;
            width: 100%;
            color: #111;
            background: #fff;
            padding: 20px;
          }
          .inventory-print table { width: 100%; border-collapse: collapse; font-size: 9px; }
          .inventory-print th, .inventory-print td { border: 1px solid #777; padding: 3px 5px; height: 18px; }
        }
      `}</style>

      <div className="inventory-screen space-y-4">
        {loadError && (
          <div className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
            <p className="text-sm text-red-800">{loadError}</p>
            <button onClick={fetchData} className="inline-flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white">
              <RefreshCw className="h-3.5 w-3.5" />重试
            </button>
          </div>
        )}

        {notice && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            <Check className="h-4 w-4" />{notice}
          </motion.div>
        )}

        <InventoryHeader summary={summary} onPrint={print} compact={activeTab !== "overview"} />

        {firstStageInventory && activeTab === "analysis" && (
          <PendingSection agentKey="warehouse">
            <section id="pending" className="rounded-2xl border border-stone-200 bg-white/80 p-4 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-bold text-stone-950">接店基线复核</p>
                <p className="mt-1 text-xs leading-5 text-stone-500">这是截至 {firstStageInventory.date} 的历史快照，仅用于对照首次盘存和补录 BOM，不代表今日实时库存。</p>
              </div>
              <span className="rounded-full bg-stone-100 px-3 py-1 text-xs font-medium text-stone-600">最近盘点 {firstStageInventory.last_count_date || firstStageInventory.date}</span>
            </div>
            <div className="mt-3 grid gap-2 text-xs text-stone-600 md:grid-cols-3">
              <p className="rounded-xl bg-stone-50 px-3 py-2">待确认库存事实：<b>{firstStageInventory.pending_inventory_facts ?? 0}</b> 条</p>
              <p className="rounded-xl bg-stone-50 px-3 py-2">{firstStageInventory.inventory_value_basis}</p>
              <p className="rounded-xl bg-stone-50 px-3 py-2">{firstStageInventory.bom_cost_status}</p>
            </div>
            <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50/60 p-3 text-[11px] leading-5 text-blue-800">
              <p className="font-semibold text-blue-900">库存口径说明</p>
              <ul className="mt-1.5 space-y-1">
                <li>· <b>当前库存来源</b>：7/4 盘点表 + 7/6 进货单入库，低置信度物料需老板人工确认</li>
                <li>· <b>采购价来源</b>：最近一次供应链进货单单价，缺历史采购记录时为估算值</li>
                <li>· <b>库存金额口径</b>：数量 × 最近采购单价，非加权平均，仅作参考</li>
                <li>· <b>理论消耗</b>：销量 × BOM（缺 BOM 时不能精确计算）</li>
                <li>· <b>实际消耗</b>：期初库存 + 今日入库 - 期末库存（缺期初或期末盘点时不能精确计算）</li>
                <li>· <b>采购 vs 入库</b>：采购只影响钱账（应付/已付），入库才影响库存数量，两者严格分离</li>
              </ul>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {firstStageInventory.items.map((item) => (
                <div key={item.id} className={`rounded-2xl border p-3 ${
                  item.risk_level === "high" ? "border-red-200 bg-red-50/60" :
                  item.risk_level === "watch" ? "border-amber-200 bg-amber-50/60" :
                  "border-emerald-100 bg-emerald-50/40"
                }`}>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-stone-950">{item.name}</p>
                      <p className="mt-0.5 text-xs text-stone-500">最近采购价 ¥{item.latest_unit_cost}/{item.unit}</p>
                      <p className="mt-0.5 text-[11px] text-stone-500">价格来源：{item.latest_unit_cost_source || "待确认"}</p>
                    </div>
                    <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-medium text-stone-600">{item.risk_level === "high" ? "可能断货" : item.risk_level === "watch" ? "观察" : "正常"}</span>
                  </div>
                  <div className="mt-2 grid gap-1 text-[11px] text-stone-600">
                    <p>来源：{item.evidence_source || "seed"}</p>
                    <p>状态：{item.confirmation_status || "待确认"} · 老板确认：{item.owner_confirmed ? "已确认" : "未确认"}</p>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                    <p>当前 <b>{displayNumber(item.current_quantity)}{item.unit}</b></p>
                    <p>安全 <b>{displayNumber(item.safe_stock)}{item.unit}</b></p>
                    <p>入库 <b>{displayNumber(item.today_stock_in)}{item.unit}</b></p>
                    <p>消耗 <b>{displayNumber(item.today_estimated_consumption)}{item.unit}</b></p>
                    <p>报损 <b>{displayNumber(item.today_loss)}{item.unit}</b></p>
                    <p>建议补 <b>{displayNumber(item.purchase_recommendation)}{item.unit}</b></p>
                  </div>
                  <div className="mt-3 rounded-xl bg-white/65 px-3 py-2 text-[11px] leading-5 text-stone-600">
                    <p>理论消耗：销量 × BOM</p>
                    <p>实际消耗：期初库存 + 入库 - 期末库存</p>
                  </div>
                </div>
              ))}
            </div>
            {firstStageInventory.alerts.length > 0 && (
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {firstStageInventory.alerts.map((alert) => (
                  <p key={`${alert.level}-${alert.title}`} className="rounded-xl bg-stone-50 px-3 py-2 text-xs text-stone-700">
                    <b>{alert.level}</b> {alert.title}：{alert.body}
                  </p>
                ))}
              </div>
            )}
          </section>
          </PendingSection>
        )}

        <nav aria-label="库存视图" className="sticky top-14 z-20 flex gap-1 overflow-x-auto rounded-xl border border-stone-200 bg-white/95 p-1 shadow-sm backdrop-blur">
          {([
            ["overview", "库存总览", Boxes],
            ["usage", "每日使用", ClipboardList],
            ["count", "阶段盘点", CalendarCheck],
            ["flow", "进货与流水", ArrowLeftRight],
            ["analysis", "分析预警", BarChart3],
            ["production", "生产批次", CookingPot],
            ["forms", "门店表单", FileText],
          ] as const).map(([id, label, Icon]) => (
            <button
              key={id}
              type="button"
              onClick={() => setActiveTab(id)}
              className={`inline-flex min-h-10 flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-3 text-sm font-medium transition-colors ${
                activeTab === id ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100 hover:text-stone-900"
              }`}
            >
              <Icon className="h-4 w-4" />{label}
            </button>
          ))}
        </nav>

        {activeTab === "overview" && (
          <OverviewPanel
            skus={filteredSkus}
            selectedSku={selectedSku}
            selectedSkuId={selectedSkuId}
            setSelectedSkuId={setSelectedSkuId}
            categories={categories}
            category={category}
            setCategory={setCategory}
            summary={summary}
            events={events}
          />
        )}

        {activeTab === "usage" && (
          <UsagePanel
            skus={dailyUsageSkus}
            allSkus={inventorySkus}
            logs={usageLogs}
            saving={saving}
            onSubmit={async (date, items, notes) => {
              setSaving(true);
              try {
                await replaceInventoryUsage({
                  date,
                  location: "operational",
                  items,
                  source: "paper_daily_usage",
                  notes,
                });
                await afterSave(`${date} 的每日使用已覆盖保存，库存流水已同步`);
              } catch (error) {
                setLoadError(error instanceof Error ? error.message : "开包台账保存失败");
              } finally {
                setSaving(false);
              }
            }}
            onWaste={async (skuId, quantity, reason, notes) => {
              setSaving(true);
              try {
                await createInventoryWaste({
                  date: shanghaiDate(),
                  location: "store",
                  items: [{ sku_id: skuId, quantity }],
                  reason,
                  notes,
                });
                await afterSave("报损已扣减库存并写入流水");
              } catch (error) {
                setLoadError(error instanceof Error ? error.message : "报损登记失败");
              } finally {
                setSaving(false);
              }
            }}
          />
        )}

        {activeTab === "production" && (
          <ProductionPanel
            skus={inventorySkus}
            batches={productionBatches}
            saving={saving}
            onSubmit={async (bucketCount, inputs, notes) => {
              setSaving(true);
              try {
                await createProductionBatch({
                  date: shanghaiDate(),
                  name: bucketCount === 0.5 ? "半桶面糊" : "一桶面糊",
                  location: "store",
                  inputs,
                  output_quantity: bucketCount,
                  output_unit: "桶",
                  pan_cycle_minutes: 10,
                  source: "店员确认",
                  notes,
                });
                await afterSave(`${bucketCount === 0.5 ? "半桶" : "一桶"}面糊已转为在制品，原料库存已扣减`);
              } catch (error) {
                setLoadError(error instanceof Error ? error.message : "生产批次保存失败");
              } finally {
                setSaving(false);
              }
            }}
          />
        )}

        {activeTab === "count" && (
          <CountPanel
            skus={inventorySkus}
            counts={counts}
            variance={variance}
            saving={saving}
            onSubmit={async (location, countType, lines, notes) => {
              setSaving(true);
              try {
                await createInventoryCount({
                  date: shanghaiDate(),
                  location,
                  count_type: countType,
                  lines,
                  notes,
                });
                await afterSave(`${LOCATION_LABELS[location]}盘点已完成，差异已生成`);
              } catch (error) {
                setLoadError(error instanceof Error ? error.message : "盘点保存失败");
              } finally {
                setSaving(false);
              }
            }}
          />
        )}

        {activeTab === "flow" && (
          <FlowPanel
            skus={inventorySkus}
            events={events}
            purchases={purchases}
            saving={saving}
            onReceive={async (purchaseId, items, notes) => {
              setSaving(true);
              try {
                await receivePurchase(purchaseId, {
                  date: shanghaiDate(),
                  items,
                  source: "老板到货清点",
                  notes,
                });
                await afterSave("到货数量和三个存放位置已入账，采购单已转为已收货");
              } catch (error) {
                setLoadError(error instanceof Error ? error.message : "收货入库失败");
              } finally {
                setSaving(false);
              }
            }}
            onSubmit={async (from, to, skuId, quantity, notes) => {
              setSaving(true);
              try {
                await createInventoryTransfer({
                  date: shanghaiDate(),
                  from_location: from,
                  to_location: to,
                  items: [{ sku_id: skuId, quantity }],
                  notes,
                });
                await afterSave("库存调拨已完成，门店和仓库数量已同步");
              } catch (error) {
                setLoadError(error instanceof Error ? error.message : "调拨失败");
              } finally {
                setSaving(false);
              }
            }}
          />
        )}

        {activeTab === "forms" && operatingFacts && (
          <FormsPanel forms={operatingFacts.operational_forms} inventoryPolicy={operatingFacts.inventory_policy} />
        )}

        {activeTab === "analysis" && (
          <AnalysisPanel forecast={forecast} summary={summary} />
        )}
      </div>

      <PrintTemplates type={printSheet} dailySkus={dailyUsageSkus} allSkus={inventorySkus} />
    </ModulePage>
  );
}

function FormsPanel({ forms, inventoryPolicy }: { forms: StoreOperatingFactsV1["operational_forms"]; inventoryPolicy: StoreOperatingFactsV1["inventory_policy"] }) {
  return <section className="space-y-4">
    <div className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-4">
      <p className="text-xs font-semibold text-emerald-700">已按真实门店操作拆分</p>
      <h2 className="mt-1 text-base font-bold text-emerald-950">每日记使用，阶段盘结余，进货单独记台账</h2>
      <p className="mt-2 text-xs leading-5 text-emerald-800">{inventoryPolicy.employee_action} {inventoryPolicy.exception}</p>
    </div>
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {forms.map((form) => <article key={form.id} className="rounded-2xl border border-stone-200 bg-white/80 p-4">
        <div className="flex items-start justify-between gap-3"><div><p className="text-sm font-bold text-stone-950">{form.name}</p><p className="mt-1 text-[11px] text-stone-500">填写频率：{form.frequency}</p></div><FileText className="h-4 w-4 shrink-0 text-octo-700" /></div>
        <div className="mt-3 flex flex-wrap gap-1.5">{form.fields.map((field) => <span key={field} className="rounded-md bg-stone-100 px-2 py-1 text-[11px] text-stone-600">{field}</span>)}</div>
      </article>)}
    </div>
    <div className="flex flex-wrap justify-end gap-2">
      <a href="/downloads/商品档案_来源副本_2026-07-26.xlsx" download className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-stone-300 bg-white px-4 text-sm font-semibold text-stone-800">商品档案来源副本</a>
      <a href="/downloads/大口章鱼烧_库存线下表格_2026-07-27.xlsx" download className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-stone-900 px-4 text-sm font-semibold text-white"><FileText className="h-4 w-4" />下载最新 Excel 线下表格</a>
    </div>
  </section>;
}

function AnalysisPanel({ forecast, summary }: { forecast: ForecastItem[]; summary: InventorySummary | null }) {
  const actionable = forecast.filter((item) => item.action === "urgent" || item.action === "recommend");
  const unknown = forecast.filter((item) => item.action === "not_enough_data");
  const known = forecast.filter((item) => item.days_remaining != null);
  const recommendedAmount = actionable.reduce((sum, item) => sum + (item.recommend_amount || 0), 0);
  return (
    <div className="space-y-4">
      <section className="flex flex-col gap-3 rounded-2xl border border-stone-200 bg-white/85 p-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-semibold text-stone-950">库存不是孤立模块</p>
          <p className="mt-1 text-xs leading-5 text-stone-500">进货对应财务凭证，每日使用形成成本估算，商品毛利必须继续结合 BOM 与真实销量。</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a href="/finance/profit" className="inline-flex min-h-10 items-center rounded-lg border border-stone-200 bg-white px-3 text-xs font-semibold text-stone-800 hover:bg-stone-50">去财务成本与利润</a>
          <a href="/products" className="inline-flex min-h-10 items-center rounded-lg border border-stone-200 bg-white px-3 text-xs font-semibold text-stone-800 hover:bg-stone-50">去商品/BOM</a>
          <a href="/finance/reports" className="inline-flex min-h-10 items-center rounded-lg border border-stone-200 bg-white px-3 text-xs font-semibold text-stone-800 hover:bg-stone-50">去凭证与报表</a>
          <a href="/reports" className="inline-flex min-h-10 items-center rounded-lg bg-stone-900 px-3 text-xs font-semibold text-white">去经营周报月报</a>
        </div>
      </section>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="可计算覆盖" value={`${known.length}/${forecast.length}`} hint="有连续使用记录的库存物料" icon={<BarChart3 className="h-5 w-5" />} />
        <Metric label="需要采购" value={`${actionable.length} 项`} hint="由现有库存、日均使用和提前期计算" tone={actionable.length ? "warning" : "default"} icon={<PackageCheck className="h-5 w-5" />} />
        <Metric label="建议采购金额" value={actionable.length ? `¥${recommendedAmount.toFixed(2)}` : "—"} hint={actionable.length ? "按当前单位成本估算" : "暂无可核验建议"} icon={<Boxes className="h-5 w-5" />} />
        <Metric label="数据不足" value={`${unknown.length} 项`} hint="需继续录入每日使用和首次实盘" tone={unknown.length ? "warning" : "default"} icon={<ClipboardList className="h-5 w-5" />} />
      </section>

      <section className="overflow-hidden rounded-2xl border border-stone-200 bg-white/85">
        <div className="flex flex-col gap-2 border-b border-stone-200 p-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-stone-950">补货预测与证据</h2>
            <p className="mt-1 text-xs leading-5 text-stone-500">没有连续使用记录时只显示“数据不足”；系统不会用目录报价或单次进货间隔冒充消耗速度。</p>
          </div>
          <DataSourceTag sourceLabel="库存实盘 + 每日使用 + 采购提前期" confidence={summary?.data_status === "ready" ? "high" : "medium"} />
        </div>
        <div className="divide-y divide-stone-100">
          {forecast.map((item) => (
            <div key={item.sku_id} className="grid gap-3 px-4 py-3.5 md:grid-cols-[minmax(180px,1fr)_110px_110px_130px] md:items-center">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="truncate text-sm font-semibold text-stone-900">{item.name}</p>
                  <StatusTag type={item.risk_level === "high" ? "danger" : item.risk_level === "medium" ? "warning" : item.risk_level === "unknown" ? "neutral" : "success"}>
                    {item.action === "not_enough_data" ? "数据不足" : item.action === "urgent" ? "立即采购" : item.action === "recommend" ? "建议采购" : "库存正常"}
                  </StatusTag>
                </div>
                <p className="mt-1 text-xs text-stone-500">门店 {displayNumber(item.store_stock)} · 仓库 {displayNumber(item.warehouse_stock)} · 待分配 {displayNumber(item.unallocated_stock)} {item.unit}</p>
              </div>
              <div><p className="text-[10px] text-stone-400">实测日均</p><p className="mt-0.5 text-sm font-semibold tabular-nums text-stone-800">{item.observed_daily_consumption > 0 ? `${displayNumber(item.observed_daily_consumption)}${item.unit}/天` : "—"}</p></div>
              <div><p className="text-[10px] text-stone-400">可售天数</p><p className="mt-0.5 text-sm font-semibold tabular-nums text-stone-800">{item.days_remaining == null ? "—" : `${item.days_remaining} 天`}</p></div>
              <div className="md:text-right"><p className="text-[10px] text-stone-400">建议采购</p><p className="mt-0.5 text-sm font-semibold tabular-nums text-stone-900">{item.recommend_qty == null ? "—" : `${displayNumber(item.recommend_qty)}${item.unit} · ¥${(item.recommend_amount || 0).toFixed(2)}`}</p></div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function InventoryHeader({ summary, onPrint, compact = false }: { summary: InventorySummary | null; onPrint: (type: "daily" | "weekly") => void; compact?: boolean }) {
  return (
    <section className="rounded-2xl border border-stone-200 bg-white/85 p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">Inventory Agent</p>
            <StatusTag type={summary?.data_status === "ready" ? "success" : "warning"}>
              {summary?.data_status === "ready" ? "已校准" : "校准中"}
            </StatusTag>
          </div>
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-stone-950">门店与仓库库存</h1>
          {!compact && (
            <p className="mt-1 text-sm leading-6 text-stone-600">
              真实入库、位置调拨、每日物料使用和阶段实盘共同形成库存账。销售推算只做对照，不覆盖实盘。
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <button onClick={() => onPrint("daily")} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-stone-200 bg-white px-3 text-sm font-medium text-stone-700 hover:bg-stone-50">
            <Printer className="h-4 w-4" />每日使用表
          </button>
          <button onClick={() => onPrint("weekly")} className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-stone-900 px-3 text-sm font-medium text-white hover:bg-stone-800">
            <Printer className="h-4 w-4" />阶段盘点表
          </button>
        </div>
      </div>

      {!compact && <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <Metric label="库存物料" value={`${summary?.sku_count ?? 0} 项`} hint={`商品档案共 ${summary?.catalog_sku_count ?? 0} 项，设备 ${summary?.equipment_count ?? 0} 项`} icon={<Store className="h-5 w-5" />} />
        <Metric label="盘点覆盖" value={`${summary?.counted_sku_count ?? 0}/${summary?.sku_count ?? 0}`} hint={summary?.data_status === "ready" ? "全部库存物料已有实盘基线" : "未覆盖的 SKU 仍属待校准"} tone={summary?.data_status === "ready" ? "default" : "warning"} icon={<Boxes className="h-5 w-5" />} />
        <Metric label="最近盘点" value={summary?.last_count?.date || "尚未盘点"} hint={summary?.last_count ? `${summary.last_count.lines.length} 项 · ${LOCATION_LABELS[summary.last_count.location as LocationKey] || summary.last_count.location}` : "先建立首次实盘基线"} icon={<CalendarCheck className="h-5 w-5" />} />
        <Metric label="库存账面金额" value={summary && summary.inventory_value > 0 ? `¥${summary.inventory_value.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : "待校准"} hint="实盘数量 × 当前单位成本；目录报价仅补缺" icon={<PackageCheck className="h-5 w-5" />} />
        <Metric label="今日已用" value={`${summary?.today_usage_sku_count ?? 0} 项`} hint="按开封/领用整数次数记录" icon={<ClipboardList className="h-5 w-5" />} />
        <Metric label="今日库存耗用成本" value={summary?.today_usage_cost ? `¥${summary.today_usage_cost.toFixed(2)}` : "—"} hint="移动加权单位成本估算，不等于已确认商品毛利" icon={<BarChart3 className="h-5 w-5" />} />
      </div>}
      {!compact && <div className="mt-3"><DataSourceTag sourceLabel="库存API与接店盘存" confidence={summary?.data_status === "ready" ? "high" : "medium"} /></div>}
    </section>
  );
}

function Metric({ label, value, hint, icon, tone = "default" }: { label: string; value: string; hint: string; icon: React.ReactNode; tone?: "default" | "warning" }) {
  return (
    <div className={`rounded-xl border p-3.5 ${tone === "warning" ? "border-amber-200 bg-amber-50/70" : "border-stone-200 bg-stone-50/70"}`}>
      <div className="flex items-center justify-between text-stone-500">
        <span className="text-xs font-medium">{label}</span>{icon}
      </div>
      <p className="mt-2 text-xl font-bold tabular-nums text-stone-950">{value}</p>
      <p className="mt-1 text-[11px] text-stone-500">{hint}</p>
    </div>
  );
}

function OverviewPanel({
  skus,
  selectedSku,
  selectedSkuId,
  setSelectedSkuId,
  categories,
  category,
  setCategory,
  summary,
  events,
}: {
  skus: SkuItem[];
  selectedSku?: SkuItem;
  selectedSkuId: string;
  setSelectedSkuId: (value: string) => void;
  categories: string[];
  category: string;
  setCategory: (value: string) => void;
  summary: InventorySummary | null;
  events: InventoryEvent[];
}) {
  const [previewSku, setPreviewSku] = useState<SkuItem | null>(null);

  useEffect(() => {
    if (!previewSku) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPreviewSku(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [previewSku]);

  return (
    <>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,.65fr)]">
        <section className="overflow-hidden rounded-2xl border border-stone-200 bg-white/85">
        <div className="border-b border-stone-200 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-stone-950">图文SKU库存</h2>
              <p className="mt-0.5 text-xs text-stone-500">位置未确认的旧盘存明确显示为“待分配”</p>
            </div>
            <div className="flex flex-wrap gap-1">
              {categories.map((item) => (
                <button key={item} onClick={() => setCategory(item)} className={`rounded-full px-2.5 py-1 text-xs ${category === item ? "bg-stone-900 text-white" : "bg-stone-100 text-stone-600 hover:bg-stone-200"}`}>
                  {item}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="max-h-[680px] divide-y divide-stone-100 overflow-y-auto">
          {skus.map((sku) => (
            <div key={sku.id} className={`grid w-full grid-cols-[64px_minmax(0,1fr)_auto] items-center gap-3 px-4 py-3.5 text-left transition-colors ${selectedSkuId === sku.id ? "bg-orange-50/70" : "hover:bg-stone-50"}`}>
              {skuImage(sku) ? (
                <button
                  type="button"
                  onClick={() => setPreviewSku(sku)}
                  aria-label={`查看${sku.hq_name || sku.name}大图`}
                  className="group relative h-16 w-16 overflow-hidden rounded-xl border border-stone-200 bg-white shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 focus-visible:ring-offset-2"
                >
                  <Image src={skuImage(sku)} alt="" fill sizes="64px" className="object-cover transition-transform group-hover:scale-105" />
                  <span className="absolute inset-0 bg-stone-950/0 transition-colors group-hover:bg-stone-950/10" />
                </button>
              ) : (
                <div className="flex h-16 w-16 items-center justify-center rounded-xl border border-stone-200 bg-stone-100 text-stone-500"><Boxes className="h-6 w-6" /></div>
              )}
              <button
                type="button"
                onClick={() => setSelectedSkuId(sku.id)}
                className="col-span-2 grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 focus-visible:ring-offset-2"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="truncate text-sm font-semibold text-stone-900">{sku.hq_name || sku.name}</p>
                    {stockOf(sku, "unallocated") > 0 && <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800">待分配</span>}
                  </div>
                  <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="shrink-0 rounded-md bg-orange-100 px-1.5 py-0.5 text-[10px] font-semibold text-orange-800">采购规格</span>
                    <p className="truncate text-sm font-medium text-stone-700">{sku.spec || "规格待补"}</p>
                    <span className="shrink-0 text-[11px] text-stone-400">核算 / {unitOf(sku)}</span>
                  </div>
                  <StockLocations sku={sku} />
                </div>
                <div className="min-w-[64px] text-right">
                  <p className="text-[10px] font-medium text-stone-400">现有库存</p>
                  <p className="mt-1 text-lg font-bold tabular-nums text-stone-950">
                    {displayNumber(sku.current_stock || 0)}
                    <span className="ml-0.5 text-xs font-semibold text-stone-600">{unitOf(sku)}</span>
                  </p>
                </div>
              </button>
            </div>
          ))}
          {skus.length === 0 && <p className="p-8 text-center text-sm text-stone-500">这个分类暂无物料</p>}
        </div>
        </section>

        <div className="space-y-4">
          <AgentActions actions={summary?.actions || []} />
          {selectedSku && <SkuDetail sku={selectedSku} events={events.filter((event) => event.sku_id === selectedSku.id).slice(0, 8)} />}
        </div>
      </div>

      {previewSku && skuImage(previewSku) && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`${previewSku.hq_name || previewSku.name}大图`}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-stone-950/70 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setPreviewSku(null);
          }}
        >
          <div className="relative w-full max-w-[48rem] overflow-hidden rounded-2xl bg-white shadow-2xl">
            <button
              type="button"
              onClick={() => setPreviewSku(null)}
              aria-label="关闭大图"
              className="absolute right-3 top-3 z-10 flex h-11 w-11 items-center justify-center rounded-full border border-stone-200 bg-white/95 text-stone-700 shadow-sm transition-colors hover:bg-stone-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500"
            >
              <X className="h-5 w-5" />
            </button>
            <div className="relative h-[min(72vh,44rem)] w-full bg-stone-50">
              <Image
                src={skuImage(previewSku)}
                alt={previewSku.hq_name || previewSku.name}
                fill
                sizes="(max-width: 768px) 100vw, 768px"
                className="object-contain p-4 sm:p-8"
                priority
              />
            </div>
            <div className="border-t border-stone-200 px-5 py-4">
              <p className="text-base font-semibold text-stone-950">{previewSku.hq_name || previewSku.name}</p>
              <p className="mt-1 text-sm text-stone-500">{previewSku.spec || "规格待补"} · 核算单位 {unitOf(previewSku)}</p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function StockLocations({ sku }: { sku: SkuItem }) {
  const store = stockOf(sku, "store");
  const warehouse = stockOf(sku, "warehouse");
  const freezer = stockOf(sku, "freezer");
  const unallocated = stockOf(sku, "unallocated");
  const unit = unitOf(sku);
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px]" aria-label={`门店${store}${unit}，仓库${warehouse}${unit}，待分配${unallocated}${unit}`}>
      <span className="inline-flex items-center gap-1.5 text-stone-600">
        <span className="flex h-5 w-5 items-center justify-center rounded-md bg-emerald-50 text-emerald-700"><Store className="h-3 w-3" /></span>
        门店 <strong className="font-semibold tabular-nums text-stone-800">{displayNumber(store)}{unit}</strong>
      </span>
      {freezer > 0 && (
        <span className="inline-flex items-center gap-1.5 text-stone-600">
          <span className="flex h-5 w-5 items-center justify-center rounded-md bg-cyan-50 text-cyan-700"><PackageCheck className="h-3 w-3" /></span>
          大冰箱 <strong className="font-semibold tabular-nums text-stone-800">{displayNumber(freezer)}{unit}</strong>
        </span>
      )}
      <span className="inline-flex items-center gap-1.5 text-stone-600">
        <span className="flex h-5 w-5 items-center justify-center rounded-md bg-sky-50 text-sky-700"><Boxes className="h-3 w-3" /></span>
        仓库 <strong className="font-semibold tabular-nums text-stone-800">{displayNumber(warehouse)}{unit}</strong>
      </span>
      {unallocated > 0 && (
        <span className="inline-flex items-center gap-1.5 text-amber-800">
          <span className="flex h-5 w-5 items-center justify-center rounded-md bg-amber-100"><ClipboardList className="h-3 w-3" /></span>
          待分配 <strong className="font-semibold tabular-nums">{displayNumber(unallocated)}{unit}</strong>
        </span>
      )}
    </div>
  );
}

function AgentActions({ actions }: { actions: NonNullable<InventorySummary["actions"]> }) {
  return (
    <section className="rounded-2xl border border-stone-200 bg-stone-950 p-4 text-white">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-orange-300">仓管</p>
          <h2 className="mt-1 text-base font-semibold">当前闭环</h2>
        </div>
        <span className="rounded-full bg-white/10 px-2.5 py-1 text-xs text-stone-300">{actions.length} 项</span>
      </div>
      <div className="mt-4 space-y-2">
        {actions.slice(0, 5).map((action) => (
          <div key={action.id} className="rounded-xl border border-white/10 bg-white/[0.06] p-3">
            <p className="text-sm font-medium">{action.title}</p>
            <p className="mt-1 text-xs leading-5 text-stone-300">{action.reason}</p>
            <div className="mt-2 flex items-center justify-between gap-3">
              <span className="text-xs font-medium text-orange-300">{action.action}</span>
              <span className="text-[10px] text-stone-400">置信度 {action.confidence === "high" ? "高" : action.confidence === "medium" ? "中" : "低"}</span>
            </div>
          </div>
        ))}
        {actions.length === 0 && <p className="rounded-xl bg-white/[0.06] p-4 text-sm text-stone-300">当前没有需要处理的库存动作。</p>}
      </div>
    </section>
  );
}

function SkuDetail({ sku, events }: { sku: SkuItem; events: InventoryEvent[] }) {
  return (
    <section className="rounded-2xl border border-stone-200 bg-white/85 p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium text-stone-500">当前物料</p>
          <h2 className="mt-1 text-base font-semibold text-stone-950">{sku.hq_name || sku.name}</h2>
          <p className="mt-1 text-xs text-stone-500">{sku.spec || "总部规格待补充"}</p>
        </div>
        <StatusTag type={stockOf(sku, "unallocated") > 0 ? "warning" : "success"}>
          {stockOf(sku, "unallocated") > 0 ? "待校准" : "已分位置"}
        </StatusTag>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        {(["store", "warehouse", "freezer", "unallocated"] as const).map((location) => (
          <div key={location} className="rounded-lg bg-stone-50 p-2.5 text-center">
            <p className="text-[10px] text-stone-500">{LOCATION_LABELS[location]}</p>
            <p className="mt-1 text-sm font-bold tabular-nums text-stone-900">{displayNumber(stockOf(sku, location))}{unitOf(sku)}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 border-t border-stone-100 pt-3">
        <p className="text-xs font-semibold text-stone-700">最近库存事件</p>
        <div className="mt-2 space-y-2">
          {events.map((event) => (
            <div key={event.id} className="flex items-center justify-between gap-3 text-xs">
              <span className="text-stone-600">{event.date} · {EVENT_LABELS[event.event_type] || event.event_type}</span>
              <span className="font-medium tabular-nums text-stone-900">{displayNumber(event.quantity)}{unitOf(sku)}</span>
            </div>
          ))}
          {events.length === 0 && <p className="text-xs leading-5 text-stone-400">还没有库存流水；首次实盘后开始形成可追溯历史。</p>}
        </div>
      </div>
    </section>
  );
}

function UsagePanel({ skus, allSkus, logs, saving, onSubmit, onWaste }: {
  skus: SkuItem[];
  allSkus: SkuItem[];
  logs: InventoryUsageLog[];
  saving: boolean;
  onSubmit: (date: string, items: Array<{ sku_id: string; quantity: number; name: string; unit: string }>, notes: string) => Promise<void>;
  onWaste: (skuId: string, quantity: number, reason: string, notes: string) => Promise<void>;
}) {
  const [date, setDate] = useState(shanghaiDate());
  const [values, setValues] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState("");
  const [query, setQuery] = useState("");
  const [wasteSkuId, setWasteSkuId] = useState("");
  const [wasteQuantity, setWasteQuantity] = useState("");
  const [wasteReason, setWasteReason] = useState("撒漏");
  const [wasteNotes, setWasteNotes] = useState("");
  const savedLog = logs.find((log) => log.date === date && log.source === "paper_daily_usage")
    || logs.find((log) => log.date === date);
  useEffect(() => {
    const nextValues: Record<string, string> = {};
    for (const item of savedLog?.items || []) {
      if (item.quantity > 0) nextValues[item.sku_id] = String(item.quantity);
    }
    setValues(nextValues);
    setNotes(savedLog?.notes || "");
  }, [date, savedLog?.id, savedLog?.created_at]);
  const visibleSkus = skus.filter((sku) => `${sku.name}${sku.hq_name || ""}${sku.category}${sku.daily_usage_group || ""}`.toLowerCase().includes(query.trim().toLowerCase()));
  const groupedVisibleSkus = DAILY_USAGE_GROUPS
    .map((group) => ({ ...group, items: visibleSkus.filter((sku) => sku.daily_usage_group === group.label || group.names.includes(sku.name)) }))
    .filter((group) => group.items.length > 0);
  const items = skus
    .map((sku) => ({ sku_id: sku.id, quantity: Number(values[sku.id] || 0), name: sku.name, unit: unitOf(sku) }))
    .filter((item) => item.quantity > 0);
  const usageCost = items.reduce((sum, item) => {
    const sku = skus.find((candidate) => candidate.id === item.sku_id);
    return sum + item.quantity * (sku?.unit_cost || 0);
  }, 0);
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
      <section className="rounded-2xl border border-stone-200 bg-white/85 p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-stone-950">今日物料使用</h2>
            <p className="mt-1 text-sm text-stone-500">只填今天实际开封或领用的高频营业物料；低频耗材放在阶段盘点中管理。</p>
          </div>
          <label className="text-xs font-medium text-stone-600">营业日期
            <input type="date" max={shanghaiDate()} value={date} onChange={(event) => setDate(event.target.value)} className="mt-1 block h-10 rounded-lg border border-stone-200 bg-white px-3 text-sm text-stone-900" />
          </label>
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
          <input value={query} onChange={(event) => setQuery(event.target.value)} aria-label="搜索物料" className="h-10 w-full rounded-lg border border-stone-200 px-3 text-sm outline-none focus:border-orange-500 sm:max-w-xs" placeholder="搜索品名或类别" />
          <span className="text-xs text-stone-500">共 {skus.length} 项，已填写 {items.length} 项{savedLog ? " · 正在修改已保存记录" : ""}</span>
        </div>
        <div className="mt-3 max-h-[620px] space-y-3 overflow-y-auto pr-1">
          {groupedVisibleSkus.map((group) => (
            <section key={group.label} className="overflow-hidden rounded-xl border border-stone-200 bg-stone-50/45">
              <div className={`flex items-center justify-between border-b px-3 py-2 ${group.tone}`}>
                <h3 className="text-xs font-semibold">{group.label}</h3>
                <span className="text-[11px] opacity-70">{group.items.length} 项</span>
              </div>
              <div className="grid gap-2 p-2 sm:grid-cols-2">
                {group.items.map((sku) => (
                  <label key={sku.id} className="flex items-center gap-3 rounded-lg border border-stone-200 bg-white p-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-orange-50 text-orange-700"><PackageCheck className="h-4 w-4" /></div>
                    <div className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-stone-900">{sku.hq_name || sku.name}</span>
                      <span className="text-xs text-stone-500">{sku.spec || "规格待补"} · {unitOf(sku)}</span>
                    </div>
                    <input
                      aria-label={`${sku.name}今日使用数量`}
                      type="number"
                      min="0"
                      step="1"
                      value={values[sku.id] || ""}
                      onChange={(event) => {
                        const nextValue = event.target.value;
                        if (nextValue === "" || /^\d+$/.test(nextValue)) {
                          setValues((current) => ({ ...current, [sku.id]: nextValue }));
                        }
                      }}
                      inputMode="numeric"
                      className="h-10 w-20 rounded-lg border border-stone-200 px-2 text-right text-sm tabular-nums outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-100"
                      placeholder="0"
                    />
                  </label>
                ))}
              </div>
            </section>
          ))}
        </div>
        <label className="mt-4 block text-sm font-medium text-stone-700">
          备注
          <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={2} placeholder="只写发酸报废、特殊大单、临时补货等重要情况" className="mt-2 w-full rounded-xl border border-stone-200 p-3 text-sm outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-100" />
        </label>
        <div className="mt-4 flex flex-col gap-3 rounded-xl border border-stone-200 bg-stone-50/80 p-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs text-stone-500">本日库存耗用成本估算</p>
            <p className="mt-0.5 text-lg font-bold tabular-nums text-stone-950">{usageCost > 0 ? `¥${usageCost.toFixed(2)}` : "—"}</p>
          </div>
          <p className="max-w-md text-[11px] leading-5 text-stone-500">只是当前移动加权成本的库存耗用估算；商品毛利要结合完整 BOM、销量与实盘差异核对。</p>
        </div>
        <button
          type="button"
          disabled={saving || items.length === 0}
          onClick={async () => {
            await onSubmit(date, items, notes);
          }}
          className="mt-4 inline-flex min-h-11 items-center justify-center rounded-lg bg-stone-900 px-5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          {saving ? "保存中…" : savedLog ? `覆盖保存 ${items.length} 项` : `确认写入 ${items.length} 项`}
        </button>
      </section>
      <div className="space-y-4">
        <section className="rounded-2xl border border-rose-200 bg-rose-50/55 p-4">
          <h3 className="text-sm font-semibold text-rose-950">单独报损</h3>
          <p className="mt-1 text-xs leading-5 text-rose-700">撒漏、变质、过期或破损不算正常使用，单独登记才能看到真实耗损。</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
            <select aria-label="报损物料" value={wasteSkuId} onChange={(event) => setWasteSkuId(event.target.value)} className="h-10 rounded-lg border border-rose-200 bg-white px-3 text-sm outline-none focus:border-rose-400">
              <option value="">选择报损物料</option>
              {allSkus.map((sku) => <option key={sku.id} value={sku.id}>{sku.hq_name || sku.name} / {unitOf(sku)}</option>)}
            </select>
            <div className="grid grid-cols-2 gap-2">
              <input aria-label="报损数量" type="number" min="0" step="0.1" value={wasteQuantity} onChange={(event) => setWasteQuantity(event.target.value)} placeholder="数量" className="h-10 rounded-lg border border-rose-200 bg-white px-3 text-sm outline-none focus:border-rose-400" />
              <select aria-label="报损原因" value={wasteReason} onChange={(event) => setWasteReason(event.target.value)} className="h-10 rounded-lg border border-rose-200 bg-white px-3 text-sm outline-none focus:border-rose-400">
                {["撒漏", "变质", "过期", "破损", "操作失误", "其他"].map((reason) => <option key={reason}>{reason}</option>)}
              </select>
            </div>
            <input aria-label="报损备注" value={wasteNotes} onChange={(event) => setWasteNotes(event.target.value)} placeholder="可选：简要说明" className="h-10 rounded-lg border border-rose-200 bg-white px-3 text-sm outline-none focus:border-rose-400" />
          </div>
          <button type="button" disabled={saving || !wasteSkuId || Number(wasteQuantity) <= 0} onClick={async () => {
            await onWaste(wasteSkuId, Number(wasteQuantity), wasteReason, wasteNotes);
            setWasteSkuId("");
            setWasteQuantity("");
            setWasteNotes("");
          }} className="mt-3 inline-flex min-h-10 items-center justify-center rounded-lg bg-rose-700 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40">
            确认报损
          </button>
        </section>
        <HistoryList title="最近使用台账" empty="还没有使用记录">
          {logs.slice(0, 12).map((log) => (
            <div key={log.id} className="border-b border-stone-100 py-3 last:border-0">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-stone-900">{log.date}</p>
                <span className="text-xs text-stone-400">{log.items.length}项</span>
              </div>
              <p className="mt-1 text-xs leading-5 text-stone-500">{log.items.filter((item) => item.quantity > 0).map((item) => `${item.name} ${displayNumber(item.quantity)}${item.unit}`).join("、")}</p>
            </div>
          ))}
        </HistoryList>
      </div>
    </div>
  );
}

function ProductionPanel({ skus, batches, saving, onSubmit }: {
  skus: SkuItem[];
  batches: ProductionBatch[];
  saving: boolean;
  onSubmit: (
    bucketCount: 0.5 | 1,
    inputs: Array<{ sku_id: string; quantity: number; name?: string; unit?: string }>,
    notes: string,
  ) => Promise<void>;
}) {
  const [bucketCount, setBucketCount] = useState<0.5 | 1>(0.5);
  const [notes, setNotes] = useState("");
  const flour = skus.find((sku) => `${sku.name}${sku.hq_name || ""}`.includes("章鱼烧粉"));
  const seasoning = skus.find((sku) => sku.name.includes("调料包"));
  const multiplier = bucketCount === 0.5 ? 1 : 2;
  const inputs = [flour, seasoning]
    .filter((sku): sku is SkuItem => Boolean(sku))
    .map((sku) => ({ sku_id: sku.id, quantity: multiplier, name: sku.name, unit: unitOf(sku) }));
  const canCreate = Boolean(flour && seasoning);

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
      <section className="rounded-2xl border border-stone-200 bg-white/85 p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-stone-950">面糊生产批次</h2>
            <p className="mt-1 text-sm leading-6 text-stone-500">拆包不是消失：原料转成面糊在制品，打烊时再确认实际使用与报损。</p>
          </div>
          <StatusTag type="success">10 分钟 / 锅</StatusTag>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {([0.5, 1] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setBucketCount(value)}
              className={`rounded-xl border p-4 text-left transition-colors ${bucketCount === value ? "border-orange-400 bg-orange-50" : "border-stone-200 bg-white hover:bg-stone-50"}`}
            >
              <p className="text-sm font-bold text-stone-950">{value === 0.5 ? "半桶配方" : "一桶配方"}</p>
              <p className="mt-2 text-xs leading-5 text-stone-500">
                章鱼烧粉 {value === 0.5 ? 1 : 2} 包 · 调料包 {value === 0.5 ? 1 : 2} 包 · 鸡蛋 {value === 0.5 ? 18 : 36} 个 · 水 {value === 0.5 ? 4000 : 8000} ml · 海苔粉 {value === 0.5 ? 0.5 : 1} 勺
              </p>
            </button>
          ))}
        </div>
        <div className="mt-4 rounded-xl bg-stone-50 p-4 text-xs leading-6 text-stone-600">
          系统当前自动扣减章鱼烧粉和调料包。鸡蛋、水、海苔粉尚未建立可盘点 SKU，先作为配方标准保留，不伪造库存扣减。
        </div>
        <label className="mt-4 block text-sm font-medium text-stone-700">批次备注
          <input value={notes} onChange={(event) => setNotes(event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-stone-200 px-3 text-sm" placeholder="例如：周末下午加开第二桶" />
        </label>
        <button
          type="button"
          disabled={saving || !canCreate}
          onClick={async () => {
            await onSubmit(bucketCount, inputs, notes);
            setNotes("");
          }}
          className="mt-4 min-h-11 rounded-lg bg-stone-900 px-5 text-sm font-semibold text-white disabled:opacity-40"
        >
          {saving ? "正在建批…" : `确认制作${bucketCount === 0.5 ? "半桶" : "一桶"}`}
        </button>
      </section>
      <HistoryList title="面糊批次" empty="还没有生产批次">
        {batches.map((batch) => (
          <div key={batch.id} className="border-b border-stone-100 py-3 last:border-0">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-stone-900">{batch.date} · {batch.name}</p>
              <StatusTag type={batch.status === "open" ? "warning" : "success"}>{batch.status === "open" ? "使用中" : "已结清"}</StatusTag>
            </div>
            <p className="mt-1 text-xs leading-5 text-stone-500">
              {batch.inputs.map((item) => `${item.name} ${displayNumber(item.quantity)}${item.unit}`).join("、")} · {batch.pan_cycle_minutes}分钟/锅
            </p>
          </div>
        ))}
      </HistoryList>
    </div>
  );
}

function CountPanel({ skus, counts, variance, saving, onSubmit }: {
  skus: SkuItem[];
  counts: InventoryCountRecord[];
  variance: InventoryVariance | null;
  saving: boolean;
  onSubmit: (
    location: "store" | "warehouse" | "freezer",
    countType: "weekly" | "biweekly" | "monthly" | "spot",
    lines: Array<{ sku_id: string; counted_quantity: number }>,
    notes: string,
  ) => Promise<void>;
}) {
  const [location, setLocation] = useState<"store" | "warehouse" | "freezer">("store");
  const [countType, setCountType] = useState<"weekly" | "biweekly" | "monthly" | "spot">("weekly");
  const [values, setValues] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState("");
  const lines = Object.entries(values)
    .filter(([, value]) => value !== "")
    .map(([sku_id, value]) => ({ sku_id, counted_quantity: Number(value) }));
  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-stone-200 bg-white/85 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-base font-semibold text-stone-950">盲盘录入</h2>
            <p className="mt-1 text-sm text-stone-500">不显示系统预计数量，避免照着账面数填写。没有盘到的SKU不会被改动。</p>
          </div>
          <div className="flex gap-2">
            <select value={location} onChange={(event) => setLocation(event.target.value as "store" | "warehouse" | "freezer")} className="h-10 rounded-lg border border-stone-200 bg-white px-3 text-sm">
              <option value="store">门店</option><option value="warehouse">仓库</option><option value="freezer">大冰箱</option>
            </select>
            <select value={countType} onChange={(event) => setCountType(event.target.value as typeof countType)} className="h-10 rounded-lg border border-stone-200 bg-white px-3 text-sm">
              <option value="weekly">周盘</option><option value="biweekly">双周盘</option><option value="monthly">月盘</option><option value="spot">临时盘点</option>
            </select>
          </div>
        </div>
        <div className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {skus.map((sku) => (
            <label key={sku.id} className="flex items-center gap-3 rounded-lg border border-stone-200 px-3 py-2.5">
              <div className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-stone-900">{sku.hq_name || sku.name}</span>
                <span className="text-[11px] text-stone-500">{sku.spec || sku.category} · {unitOf(sku)}</span>
              </div>
              <input
                aria-label={`${sku.name}实盘数量`}
                type="number"
                min="0"
                step="0.1"
                value={values[sku.id] || ""}
                onChange={(event) => setValues((current) => ({ ...current, [sku.id]: event.target.value }))}
                className="h-9 w-20 rounded-lg border border-stone-200 px-2 text-right text-sm tabular-nums outline-none focus:border-orange-500"
                placeholder="—"
              />
            </label>
          ))}
        </div>
        <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={2} placeholder="盘点备注，可不填" className="mt-4 w-full rounded-xl border border-stone-200 p-3 text-sm outline-none focus:border-orange-500" />
        <button
          disabled={saving || lines.length === 0}
          onClick={async () => {
            await onSubmit(location, countType, lines, notes);
            setValues({});
            setNotes("");
          }}
          className="mt-3 min-h-11 rounded-lg bg-stone-900 px-5 text-sm font-semibold text-white disabled:opacity-40"
        >
          {saving ? "正在校准…" : `完成盘点 ${lines.length} 项`}
        </button>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <HistoryList title="最近盘点" empty="暂无盘点记录">
          {counts.slice(0, 8).map((count) => (
            <div key={count.id} className="flex items-center justify-between border-b border-stone-100 py-3 last:border-0">
              <div>
                <p className="text-sm font-medium text-stone-900">{count.date} · {count.location === "store" ? "门店" : "仓库"}</p>
                <p className="mt-0.5 text-xs text-stone-500">{count.lines.length}项 · {count.count_type}</p>
              </div>
              <ChevronRight className="h-4 w-4 text-stone-400" />
            </div>
          ))}
        </HistoryList>
        <HistoryList title="盘点差异" empty="完成两次盘点后开始形成差异">
          {variance?.value_accuracy != null && (
            <div className="mb-2 rounded-xl bg-stone-950 p-3 text-white">
              <p className="text-xs text-stone-400">金额库存准确率</p>
              <p className="mt-1 text-2xl font-bold">{(variance.value_accuracy * 100).toFixed(1)}%</p>
            </div>
          )}
          {(variance?.rows || []).slice(0, 8).map((row, index) => (
            <div key={`${row.count_id}-${row.sku_id}-${index}`} className="flex items-center justify-between border-b border-stone-100 py-2.5 last:border-0">
              <div>
                <p className="text-sm text-stone-900">{row.name}</p>
                <p className="text-[11px] text-stone-500">{row.date} · {row.location_label}</p>
              </div>
              <span className={`text-sm font-semibold tabular-nums ${row.variance_quantity < 0 ? "text-red-600" : row.variance_quantity > 0 ? "text-emerald-600" : "text-stone-500"}`}>
                {row.variance_quantity > 0 ? "+" : ""}{displayNumber(row.variance_quantity)}{row.unit}
              </span>
            </div>
          ))}
        </HistoryList>
      </div>
    </div>
  );
}

function FlowPanel({ skus, events, purchases, saving, onReceive, onSubmit }: {
  skus: SkuItem[];
  events: InventoryEvent[];
  purchases: PurchaseRecord[];
  saving: boolean;
  onReceive: (
    purchaseId: string,
    items: Array<{ sku_id: string; received_quantity: number; allocations: Partial<Record<"store" | "warehouse" | "freezer", number>> }>,
    notes: string,
  ) => Promise<void>;
  onSubmit: (from: LocationKey, to: "store" | "warehouse" | "freezer", skuId: string, quantity: number, notes: string) => Promise<void>;
}) {
  const [from, setFrom] = useState<LocationKey>("warehouse");
  const [to, setTo] = useState<"store" | "warehouse" | "freezer">("store");
  const [skuId, setSkuId] = useState(skus[0]?.id || "");
  const [quantity, setQuantity] = useState("");
  const [notes, setNotes] = useState("");
  useEffect(() => {
    if (!skuId && skus[0]) setSkuId(skus[0].id);
  }, [skuId, skus]);
  const pendingPurchase = purchases.find((purchase) => purchase.fulfillment_status === "ordered");
  return (
    <div className="space-y-4">
      {pendingPurchase && <PendingReceiptPanel purchase={pendingPurchase} saving={saving} onReceive={onReceive} />}
      <div className="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
      <section className="rounded-2xl border border-stone-200 bg-white/85 p-5">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-sky-50 text-sky-700"><ArrowLeftRight className="h-5 w-5" /></div>
        <h2 className="mt-4 text-base font-semibold text-stone-950">登记库存调拨</h2>
        <p className="mt-1 text-sm leading-6 text-stone-500">从仓库带到门店不是消耗，必须作为调拨保留流水。</p>
        <div className="mt-5 grid grid-cols-[1fr_auto_1fr] items-end gap-2">
          <label className="text-xs font-medium text-stone-600">从
            <select value={from} onChange={(event) => setFrom(event.target.value as LocationKey)} className="mt-1 block h-10 w-full rounded-lg border border-stone-200 bg-white px-2 text-sm">
              <option value="warehouse">仓库</option><option value="store">门店</option><option value="freezer">大冰箱</option><option value="unallocated">待分配</option>
            </select>
          </label>
          <ArrowLeftRight className="mb-2.5 h-4 w-4 text-stone-400" />
          <label className="text-xs font-medium text-stone-600">到
            <select value={to} onChange={(event) => setTo(event.target.value as "store" | "warehouse" | "freezer")} className="mt-1 block h-10 w-full rounded-lg border border-stone-200 bg-white px-2 text-sm">
              <option value="store">门店</option><option value="warehouse">仓库</option><option value="freezer">大冰箱</option>
            </select>
          </label>
        </div>
        <label className="mt-3 block text-xs font-medium text-stone-600">物料
          <select value={skuId} onChange={(event) => setSkuId(event.target.value)} className="mt-1 block h-10 w-full rounded-lg border border-stone-200 bg-white px-2 text-sm">
            {skus.map((sku) => <option key={sku.id} value={sku.id}>{sku.hq_name || sku.name}</option>)}
          </select>
        </label>
        <label className="mt-3 block text-xs font-medium text-stone-600">数量
          <input value={quantity} onChange={(event) => setQuantity(event.target.value)} type="number" min="0" step="0.1" className="mt-1 block h-10 w-full rounded-lg border border-stone-200 px-3 text-sm" />
        </label>
        <label className="mt-3 block text-xs font-medium text-stone-600">备注
          <input value={notes} onChange={(event) => setNotes(event.target.value)} className="mt-1 block h-10 w-full rounded-lg border border-stone-200 px-3 text-sm" placeholder="例如：周末前补门店" />
        </label>
        <button
          disabled={saving || !skuId || Number(quantity) <= 0 || from === to}
          onClick={async () => {
            await onSubmit(from, to, skuId, Number(quantity), notes);
            setQuantity("");
            setNotes("");
          }}
          className="mt-4 min-h-11 w-full rounded-lg bg-stone-900 px-4 text-sm font-semibold text-white disabled:opacity-40"
        >
          {saving ? "调拨中…" : "确认调拨"}
        </button>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <HistoryList title="库存流水" empty="暂无库存流水">
          {events.slice(0, 20).map((event) => (
            <div key={event.id} className="border-b border-stone-100 py-3 last:border-0">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-stone-900">{event.sku_name}</p>
                <span className="text-sm font-semibold tabular-nums text-stone-900">{displayNumber(event.quantity)}</span>
              </div>
              <p className="mt-1 text-xs text-stone-500">
                {event.date} · {EVENT_LABELS[event.event_type] || event.event_type}
                {event.from_location && ` · ${LOCATION_LABELS[event.from_location as LocationKey] || event.from_location}`}
                {event.to_location && ` → ${LOCATION_LABELS[event.to_location as LocationKey] || event.to_location}`}
              </p>
            </div>
          ))}
        </HistoryList>
        <HistoryList title="采购与收货" empty="暂无采购记录">
          {purchases.map((purchase) => (
            <div key={purchase.id} className="border-b border-stone-100 py-3 last:border-0">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-stone-900">{purchase.date} · {purchase.platform || purchase.supplier}</p>
                  <p className="mt-0.5 truncate text-[11px] text-stone-500">{purchase.supplier}{purchase.external_order_id ? ` · ${purchase.external_order_id}` : ""}</p>
                </div>
                <span className={`text-sm font-semibold tabular-nums ${purchase.refund_amount ? "text-emerald-700" : "text-stone-900"}`}>¥{purchase.total_cost.toFixed(2)}</span>
              </div>
              <p className="mt-2 text-xs leading-5 text-stone-700">{purchase.items.map((item) => `${item.name} ${displayNumber(item.quantity)}${item.unit || ""}`).join("、")}</p>
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-stone-500">
                <span>{purchase.items.length}个 SKU · {purchase.fulfillment_status === "ordered"
                  ? "已付款，待到货清点"
                  : purchase.fulfillment_status === "refunded"
                  ? "已退款，未计入库存"
                  : purchase.payment_status === "接店盘存"
                  ? "接店盘存"
                  : purchase.location === "store"
                    ? "门店收货"
                    : purchase.location === "warehouse"
                      ? "仓库收货"
                      : "收货地点待确认"}</span>
                {(purchase.freight || 0) > 0 && <span>运费 ¥{purchase.freight?.toFixed(2)}</span>}
                {(purchase.discount_amount || 0) > 0 && <span>优惠 ¥{purchase.discount_amount?.toFixed(2)}</span>}
                {(purchase.refund_amount || 0) > 0 && <span>退款 ¥{purchase.refund_amount?.toFixed(2)}</span>}
                {purchase.evidence_file && <a href={`/downloads/inventory-evidence/${purchase.evidence_file}`} target="_blank" rel="noreferrer" className="font-semibold text-octo-700 hover:underline">查看原始凭证</a>}
              </div>
            </div>
          ))}
        </HistoryList>
      </div>
      </div>
    </div>
  );
}

function PendingReceiptPanel({ purchase, saving, onReceive }: {
  purchase: PurchaseRecord;
  saving: boolean;
  onReceive: (
    purchaseId: string,
    items: Array<{ sku_id: string; received_quantity: number; allocations: Partial<Record<"store" | "warehouse" | "freezer", number>> }>,
    notes: string,
  ) => Promise<void>;
}) {
  const [allocations, setAllocations] = useState<Record<string, Record<"store" | "warehouse" | "freezer", string>>>({});
  const [notes, setNotes] = useState("");
  const lines = purchase.items.map((item) => {
    const values = allocations[item.sku_id] || { store: "", warehouse: "", freezer: "" };
    const parsed = {
      store: Number(values.store || 0),
      warehouse: Number(values.warehouse || 0),
      freezer: Number(values.freezer || 0),
    };
    return {
      sku_id: item.sku_id,
      received_quantity: parsed.store + parsed.warehouse + parsed.freezer,
      allocations: parsed,
      ordered_quantity: item.quantity,
      name: item.name,
    };
  });
  const complete = lines.every((line) => Math.abs(line.received_quantity - line.ordered_quantity) < 0.0001);

  return (
    <section className="rounded-2xl border border-amber-200 bg-amber-50/65 p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-700">待执行 · 到货清点</p>
          <h2 className="mt-1 text-base font-semibold text-stone-950">¥{purchase.paid_amount.toLocaleString()} 已付款，库存尚未增加</h2>
          <p className="mt-1 text-sm text-stone-600">订单 {purchase.external_order_id || purchase.id} · 每项实收数必须等于分配到门店、仓库和大冰箱的合计。</p>
        </div>
        <StatusTag type="warning">供应商发货后再确认</StatusTag>
      </div>
      <div className="mt-4 max-h-[420px] overflow-y-auto rounded-xl border border-amber-200 bg-white">
        <div className="sticky top-0 z-10 grid grid-cols-[minmax(120px,1fr)_76px_76px_76px] gap-2 border-b border-stone-200 bg-stone-50 px-3 py-2 text-[11px] font-semibold text-stone-500">
          <span>品名 / 订购</span><span>门店</span><span>仓库</span><span>大冰箱</span>
        </div>
        {purchase.items.map((item) => (
          <div key={item.sku_id} className="grid grid-cols-[minmax(120px,1fr)_76px_76px_76px] items-center gap-2 border-b border-stone-100 px-3 py-2 last:border-0">
            <div className="min-w-0">
              <p className="truncate text-xs font-medium text-stone-900">{item.name}</p>
              <p className="text-[10px] text-stone-500">订购 {displayNumber(item.quantity)}</p>
            </div>
            {(["store", "warehouse", "freezer"] as const).map((location) => (
              <input
                key={location}
                aria-label={`${item.name}分配至${LOCATION_LABELS[location]}`}
                type="number"
                min="0"
                step="0.1"
                value={allocations[item.sku_id]?.[location] || ""}
                onChange={(event) => setAllocations((current) => ({
                  ...current,
                  [item.sku_id]: {
                    store: current[item.sku_id]?.store || "",
                    warehouse: current[item.sku_id]?.warehouse || "",
                    freezer: current[item.sku_id]?.freezer || "",
                    [location]: event.target.value,
                  },
                }))}
                className="h-9 min-w-0 rounded-lg border border-stone-200 px-2 text-right text-xs tabular-nums"
                placeholder="0"
              />
            ))}
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-col gap-3 md:flex-row">
        <input value={notes} onChange={(event) => setNotes(event.target.value)} className="h-10 flex-1 rounded-lg border border-amber-200 bg-white px-3 text-sm" placeholder="破损、少货、替代品等异常说明" />
        <button
          type="button"
          disabled={saving || !complete}
          onClick={() => onReceive(
            purchase.id,
            lines.map(({ sku_id, received_quantity, allocations: itemAllocations }) => ({ sku_id, received_quantity, allocations: itemAllocations })),
            notes,
          )}
          className="min-h-10 rounded-lg bg-stone-900 px-4 text-sm font-semibold text-white disabled:opacity-40"
        >
          {saving ? "正在入库…" : complete ? "确认清点并入库" : "先完成全部位置分配"}
        </button>
      </div>
    </section>
  );
}

function HistoryList({ title, empty, children }: { title: string; empty: string; children: React.ReactNode }) {
  const hasChildren = Array.isArray(children) ? children.length > 0 : Boolean(children);
  return (
    <section className="rounded-2xl border border-stone-200 bg-white/85 p-4">
      <div className="flex items-center gap-2 border-b border-stone-100 pb-3">
        <History className="h-4 w-4 text-stone-500" />
        <h2 className="text-sm font-semibold text-stone-900">{title}</h2>
      </div>
      <div className="max-h-[520px] overflow-y-auto">
        {hasChildren ? children : <p className="py-8 text-center text-sm text-stone-400">{empty}</p>}
      </div>
    </section>
  );
}

function PrintTemplates({ type, dailySkus, allSkus }: { type: PrintSheet; dailySkus: SkuItem[]; allSkus: SkuItem[] }) {
  const dailyGroups = DAILY_USAGE_GROUPS.map((group) => ({
    ...group,
    items: dailySkus.filter((sku) => sku.daily_usage_group === group.label || group.names.includes(sku.name)),
  }));
  return (
    <div className="inventory-print">
      {type === "daily" && (
        <>
          <h1 style={{ textAlign: "center", fontSize: 16, marginBottom: 4 }}>新余恒太城五楼大口章鱼烧｜每日物料使用登记表</h1>
          <p style={{ marginBottom: 7 }}>日期：____年__月__日　　只填高频营业物料的当日实际开封/领用数量（整数）；低频耗材放在阶段盘点表。</p>
          <table>
            <thead><tr style={{ background: "#e6eeeb", color: "#21352f" }}><th style={{ width: "22%" }}>品名</th><th style={{ width: "28%" }}>规格</th><th style={{ width: "8%" }}>单位</th><th style={{ width: "14%" }}>今日使用</th><th style={{ width: "28%" }}>异常/备注</th></tr></thead>
            <tbody>{dailyGroups.map((group, groupIndex) => (
              <Fragment key={group.label}>
                <tr><td colSpan={5} style={{ background: group.printFill, borderLeft: "4px solid #64877d", fontWeight: 700, color: "#2b413a" }}>{String(groupIndex + 1).padStart(2, "0")}　{group.label} · {group.items.length}项</td></tr>
                {group.items.map((sku) => <tr key={sku.id}><td>{sku.hq_name || sku.name}</td><td>{sku.spec || "规格待补"}</td><td style={{ textAlign: "center" }}>{unitOf(sku)}</td><td style={{ background: "#fff6d8" }} /><td /></tr>)}
              </Fragment>
            ))}</tbody>
          </table>
          <p style={{ marginTop: 6 }}>特殊情况（报损、撒漏、过期等）：________________________________________________________________________________</p>
        </>
      )}
      {type === "weekly" && (
        <>
          <h1 style={{ textAlign: "center", fontSize: 18, marginBottom: 8 }}>大口章鱼烧阶段总库存盲盘表</h1>
          <p style={{ marginBottom: 12 }}>位置：□门店　□仓库　□店内冰箱　日期：________　盘点范围：本页全部物料</p>
          <table>
            <thead><tr><th>分类</th><th>品名</th><th>总部/采购规格</th><th>整箱/件</th><th>整包/袋/捆</th><th>零散估数</th><th>备注</th></tr></thead>
            <tbody>{allSkus.map((sku) => <tr key={sku.id}><td>{sku.category}</td><td>{sku.hq_name || sku.name}</td><td>{sku.spec || "待确认"}</td><td /><td /><td /><td /></tr>)}</tbody>
          </table>
        </>
      )}
    </div>
  );
}

function PendingSection({ agentKey, children }: { agentKey: string; children: React.ReactNode }) {
  const searchParams = useSearchParams();
  const [highlight, setHighlight] = useState(false);

  useEffect(() => {
    const pending = searchParams.get("pending");
    if (pending === agentKey) {
      setHighlight(true);
      const timer = setTimeout(() => setHighlight(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [searchParams, agentKey]);

  useEffect(() => {
    if (highlight) {
      setTimeout(() => {
        const el = document.getElementById("pending");
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }, 100);
    }
  }, [highlight]);

  return (
    <motion.div
      animate={highlight ? {
        boxShadow: [
          "0 0 0 0 rgba(249, 115, 22, 0)",
          "0 0 0 4px rgba(249, 115, 22, 0.3), 0 0 20px rgba(249, 115, 22, 0.15)",
          "0 0 0 0 rgba(249, 115, 22, 0)",
        ],
      } : {}}
      transition={{ duration: 1.5, repeat: highlight ? 2 : 0 }}
      className="rounded-2xl"
    >
      {children}
    </motion.div>
  );
}
