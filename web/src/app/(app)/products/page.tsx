"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  BookOpenCheck,
  Boxes,
  Check,
  ChevronDown,
  CircleDollarSign,
  ClipboardList,
  Plus,
  RefreshCw,
  Save,
  ShoppingCart,
  Trash2,
  Utensils,
} from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import {
  DEFAULT_PROJECT_ID,
  createProduct,
  createProductVariant,
  getProductEntryContext,
  getStoreOperatingFacts,
  saveProductBom,
  type ProductEntryContext,
  type StoreOperatingFactsV1,
} from "@/lib/api";

type ProductTab = "overview" | "catalog" | "bom";
type BomDraftLine = { sku_id: string; quantity: string; unit: string };

function today() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai" }).format(new Date());
}

function money(minor: number) {
  return `¥${(minor / 100).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function ProductsPage() {
  const [tab, setTab] = useState<ProductTab>("overview");
  const [context, setContext] = useState<ProductEntryContext | null>(null);
  const [facts, setFacts] = useState<StoreOperatingFactsV1 | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [entryContext, operatingFacts] = await Promise.all([
        getProductEntryContext(DEFAULT_PROJECT_ID),
        getStoreOperatingFacts(DEFAULT_PROJECT_ID),
      ]);
      setContext(entryContext);
      setFacts(operatingFacts);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "商品资料加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function perform(action: () => Promise<unknown>, message: string) {
    setSaving(true);
    setError("");
    try {
      await action();
      setNotice(message);
      await load();
      window.setTimeout(() => setNotice(""), 3200);
      return true;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "保存失败");
      return false;
    } finally {
      setSaving(false);
    }
  }

  return (
    <ModulePage module={getModule("/products")}>
      <div className="space-y-4">
        {loading && <div className="h-0.5 animate-pulse rounded-full bg-orange-400" />}
        {error && <div className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"><span>{error}</span><button type="button" onClick={() => void load()} className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-red-700 px-3 font-semibold text-white"><RefreshCw className="h-4 w-4" />重试</button></div>}
        {notice && <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800"><Check className="h-4 w-4" />{notice}</div>}

        <header className="min-w-0 max-w-full overflow-hidden rounded-3xl border border-stone-200 bg-stone-950 text-white shadow-sm">
          <div className="grid min-w-0 max-w-full gap-6 p-5 md:grid-cols-[minmax(0,1fr)_auto] md:p-7">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-orange-300">商品 × 物料 × 销售</p>
              <h1 className="mt-2 break-words text-2xl font-bold tracking-tight">先建真实商品档案，再让每个数字互相影响</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-stone-300">
                销量按营业日进来，每日物料使用、进货单和阶段盘点分别保留原始事实。BOM 只保存你确认的配方版本，不根据名称猜用量。
              </p>
            </div>
            <div className="grid min-w-0 grid-cols-3 gap-2 self-start md:w-[300px]">
              <Metric value={context?.counts.products ?? 0} label="商品" />
              <Metric value={context?.counts.variants ?? 0} label="规格" />
              <Metric value={context?.counts.bom_versions ?? 0} label="BOM版本" />
            </div>
          </div>
          <div className="grid border-t border-white/10 sm:grid-cols-3">
            <EntryLink href="/inventory?tab=usage" icon={ClipboardList} title="录每日物料" description="按营业日覆盖保存" />
            <EntryLink href="/inventory?tab=flow&action=purchase" icon={ShoppingCart} title="建进货单" description="按订单和 SKU 记录" />
            <EntryLink href="/inventory?tab=count" icon={Boxes} title="做阶段盘点" description="按实际周期校准库存" />
          </div>
        </header>

        <nav aria-label="商品工作台" className="flex gap-1 overflow-x-auto rounded-xl border border-stone-200 bg-white p-1">
          {([
            ["overview", "经营概览", CircleDollarSign],
            ["catalog", "商品资料", Utensils],
            ["bom", "配方版本", BookOpenCheck],
          ] as const).map(([id, label, Icon]) => (
            <button key={id} type="button" onClick={() => setTab(id)} className={`inline-flex min-h-11 flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-4 text-sm font-semibold transition-colors ${tab === id ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100"}`}>
              <Icon className="h-4 w-4" />{label}
            </button>
          ))}
        </nav>

        {tab === "overview" && <Overview facts={facts} context={context} />}
        {tab === "catalog" && context && <CatalogEditor context={context} saving={saving} perform={perform} />}
        {tab === "bom" && context && <BomEditor context={context} saving={saving} perform={perform} />}
      </div>
    </ModulePage>
  );
}

function Overview({ facts, context }: { facts: StoreOperatingFactsV1 | null; context: ProductEntryContext | null }) {
  const sales = facts?.product_sales;
  const mappedNames = useMemo(() => new Set(context?.products.flatMap((product) => [product.name, ...product.aliases.map((alias) => alias.name)]) ?? []), [context]);
  const mappedSales = sales?.ranked_products.filter((item) => mappedNames.has(item.name)).length ?? 0;
  return <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,.75fr)]">
    <section className="rounded-2xl border border-stone-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4"><div><p className="text-xs font-semibold text-stone-500">已接入的真实销售</p><h2 className="mt-1 text-lg font-bold text-stone-950">商品销量和营业收入</h2></div><span className="rounded-full bg-stone-100 px-3 py-1 text-xs text-stone-600">{sales?.period.start || "—"} 至 {sales?.period.end || "—"}</span></div>
      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Fact label="营业收入" value={sales ? money(sales.recognized_revenue_minor) : "—"} />
        <Fact label="销售数量" value={sales ? `${sales.total_quantity}份` : "—"} />
        <Fact label="退款" value={sales ? money(sales.refund_minor) : "—"} />
        <Fact label="已对应商品" value={`${mappedSales}/${sales?.ranked_products.length ?? 0}`} />
      </div>
      <div className="mt-5 overflow-hidden rounded-xl border border-stone-200">
        {(sales?.ranked_products ?? []).slice(0, 12).map((product) => (
          <div key={product.name} className="grid grid-cols-[36px_minmax(0,1fr)_70px_100px] items-center gap-3 border-b border-stone-100 px-3 py-3 last:border-0">
            <span className="text-xs font-bold text-stone-400">#{product.rank}</span><span className="truncate text-sm font-semibold text-stone-900">{product.name}</span><span className="text-right text-sm tabular-nums text-stone-600">{product.quantity}份</span><span className="text-right text-sm font-bold tabular-nums text-stone-950">{money(product.amount_minor)}</span>
          </div>
        ))}
      </div>
    </section>
    <section className="rounded-2xl border border-stone-200 bg-white p-5">
      <p className="text-xs font-semibold text-stone-500">计算链路</p><h2 className="mt-1 text-lg font-bold text-stone-950">什么时候才能出毛利</h2>
      <div className="mt-4 space-y-2">
        <ChainStep index="1" title="商品与规格" body="对齐客如云、美团、淘宝闪购等名称" done={Boolean(context?.variants.length)} />
        <ChainStep index="2" title="真实 BOM 版本" body="你逐项录入每份商品的实际用量" done={Boolean(context?.bom_versions.length)} />
        <ChainStep index="3" title="物料移动加权成本" body="来自每一次按 SKU 录入的进货单" done={false} />
        <ChainStep index="4" title="商品毛利与耗损" body="销量×BOM 与实际使用、阶段盘点交叉核验" done={false} />
      </div>
      <p className="mt-4 rounded-xl bg-amber-50 px-3 py-2.5 text-xs leading-5 text-amber-900">完整 BOM 和采购成本不足时，系统保持“数据不足”，不会用 0 成本制造虚假毛利。</p>
    </section>
  </div>;
}

function CatalogEditor({ context, saving, perform }: { context: ProductEntryContext; saving: boolean; perform: (action: () => Promise<unknown>, message: string) => Promise<boolean> }) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("章鱼烧");
  const [channel, setChannel] = useState("客如云");
  const [alias, setAlias] = useState("");
  const [productId, setProductId] = useState(context.products[0]?.id || "");
  const [variantName, setVariantName] = useState("");
  const [spec, setSpec] = useState("");
  const [saleUnit, setSaleUnit] = useState("份");
  useEffect(() => { if (!productId && context.products[0]) setProductId(context.products[0].id); }, [context.products, productId]);

  async function submitProduct(event: FormEvent) {
    event.preventDefault();
    const ok = await perform(() => createProduct({ name, category, aliases: alias.trim() ? [{ channel, name: alias.trim() }] : [] }), "商品资料已保存");
    if (ok) { setName(""); setAlias(""); }
  }
  async function submitVariant(event: FormEvent) {
    event.preventDefault();
    const ok = await perform(() => createProductVariant(productId, { name: variantName, spec, sale_unit: saleUnit }), "商品规格已保存");
    if (ok) { setVariantName(""); setSpec(""); }
  }
  return <div className="grid gap-4 xl:grid-cols-[minmax(0,.8fr)_minmax(0,1.2fr)]">
    <div className="space-y-4">
      <EditorCard title="新建销售商品" description="商品名是统一主档；渠道名只作别名映射。">
        <form onSubmit={submitProduct} className="grid gap-3">
          <Field label="商品名"><input required value={name} onChange={(e) => setName(e.target.value)} className={inputClass} placeholder="例：经典原味章鱼烧" /></Field>
          <Field label="品类"><input value={category} onChange={(e) => setCategory(e.target.value)} className={inputClass} /></Field>
          <div className="grid grid-cols-[130px_minmax(0,1fr)] gap-2"><Field label="渠道"><input value={channel} onChange={(e) => setChannel(e.target.value)} className={inputClass} /></Field><Field label="该渠道商品名"><input value={alias} onChange={(e) => setAlias(e.target.value)} className={inputClass} placeholder="可选" /></Field></div>
          <SaveButton saving={saving} label="保存商品" />
        </form>
      </EditorCard>
      <EditorCard title="添加商品规格" description="四粒、六粒、全家福等规格分开建档。">
        <form onSubmit={submitVariant} className="grid gap-3">
          <Field label="所属商品"><Select value={productId} onChange={setProductId} options={context.products.map((item) => ({ value: item.id, label: item.name }))} /></Field>
          <Field label="规格名"><input required value={variantName} onChange={(e) => setVariantName(e.target.value)} className={inputClass} placeholder="例：六粒装" /></Field>
          <div className="grid grid-cols-[minmax(0,1fr)_100px] gap-2"><Field label="规格说明"><input value={spec} onChange={(e) => setSpec(e.target.value)} className={inputClass} placeholder="包装、口味等真实说明" /></Field><Field label="销售单位"><input value={saleUnit} onChange={(e) => setSaleUnit(e.target.value)} className={inputClass} /></Field></div>
          <SaveButton saving={saving} label="保存规格" disabled={!productId} />
        </form>
      </EditorCard>
    </div>
    <section className="rounded-2xl border border-stone-200 bg-white p-5">
      <p className="text-xs font-semibold text-stone-500">当前商品主档</p><h2 className="mt-1 text-lg font-bold text-stone-950">{context.products.length} 个商品 · {context.variants.length} 个规格</h2>
      <div className="mt-4 space-y-3">
        {context.products.map((product) => {
          const variants = context.variants.filter((variant) => variant.product_id === product.id);
          return <article key={product.id} className="rounded-xl border border-stone-200 bg-stone-50/60 p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold text-stone-950">{product.name}</h3><p className="mt-1 text-xs text-stone-500">{product.category || "未分类"}{product.aliases.length ? ` · ${product.aliases.map((item) => `${item.channel}：${item.name}`).join("；")}` : ""}</p></div><span className="rounded-full bg-white px-2 py-1 text-xs text-stone-600">{variants.length}规格</span></div><div className="mt-3 flex flex-wrap gap-2">{variants.map((variant) => <span key={variant.id} className="rounded-lg border border-stone-200 bg-white px-2.5 py-1.5 text-xs text-stone-700">{variant.name}{variant.spec ? ` · ${variant.spec}` : ""}</span>)}</div></article>;
        })}
        {!context.products.length && <Empty message="先在左侧建第一个销售商品。" />}
      </div>
    </section>
  </div>;
}

function BomEditor({ context, saving, perform }: { context: ProductEntryContext; saving: boolean; perform: (action: () => Promise<unknown>, message: string) => Promise<boolean> }) {
  const [variantId, setVariantId] = useState(context.variants[0]?.id || "");
  const [effectiveDate, setEffectiveDate] = useState(today());
  const [source, setSource] = useState("店主实际配方");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<BomDraftLine[]>([{ sku_id: "", quantity: "", unit: "" }]);
  useEffect(() => { if (!variantId && context.variants[0]) setVariantId(context.variants[0].id); }, [context.variants, variantId]);
  const selectedVariant = context.variants.find((item) => item.id === variantId);
  const selectedProduct = context.products.find((item) => item.id === selectedVariant?.product_id);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selectedVariant || lines.some((line) => !line.sku_id || Number(line.quantity) <= 0 || !line.unit)) return;
    const ok = await perform(() => saveProductBom(selectedVariant.product_id, selectedVariant.id, {
      effective_date: effectiveDate, source, notes,
      lines: lines.map((line) => ({ sku_id: line.sku_id, quantity: Number(line.quantity), unit: line.unit })),
    }), `${selectedProduct?.name || "商品"} ${selectedVariant.name} 的 BOM 新版本已保存`);
    if (ok) { setLines([{ sku_id: "", quantity: "", unit: "" }]); setNotes(""); }
  }
  return <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,.85fr)]">
    <EditorCard title="录入真实 BOM" description="数量一律从空白开始。每次保存新建一个版本，方便以后追溯配方和成本变化。">
      <form onSubmit={submit} className="grid gap-4">
        <Field label="商品规格"><Select value={variantId} onChange={setVariantId} options={context.variants.map((variant) => ({ value: variant.id, label: `${context.products.find((p) => p.id === variant.product_id)?.name || "商品"} · ${variant.name}` }))} /></Field>
        <div className="grid gap-3 sm:grid-cols-2"><Field label="生效日期"><input required type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} className={inputClass} /></Field><Field label="来源"><input required value={source} onChange={(e) => setSource(e.target.value)} className={inputClass} /></Field></div>
        <div className="space-y-2">
          <div className="grid grid-cols-[minmax(0,1fr)_110px_90px_42px] gap-2 px-1 text-xs font-semibold text-stone-500"><span>物料 SKU</span><span>每份用量</span><span>单位</span><span /></div>
          {lines.map((line, index) => <div key={index} className="grid grid-cols-[minmax(0,1fr)_110px_90px_42px] gap-2">
            <select required value={line.sku_id} onChange={(e) => { const material = context.materials.find((item) => item.id === e.target.value); setLines((current) => current.map((item, i) => i === index ? { ...item, sku_id: e.target.value, unit: material?.display_unit || material?.unit || "" } : item)); }} className={inputClass}><option value="">选择真实物料</option>{context.materials.map((material) => <option key={material.id} value={material.id}>{material.hq_name || material.name} · {material.spec || material.display_unit || material.unit}</option>)}</select>
            <input required type="number" min="0.0001" step="any" inputMode="decimal" value={line.quantity} onChange={(e) => setLines((current) => current.map((item, i) => i === index ? { ...item, quantity: e.target.value } : item))} className={`${inputClass} text-right tabular-nums`} placeholder="空白" />
            <input required value={line.unit} onChange={(e) => setLines((current) => current.map((item, i) => i === index ? { ...item, unit: e.target.value } : item))} className={inputClass} />
            <button type="button" aria-label="删除这行" disabled={lines.length === 1} onClick={() => setLines((current) => current.filter((_, i) => i !== index))} className="flex h-11 w-11 items-center justify-center rounded-lg border border-stone-200 text-stone-500 hover:bg-stone-100 disabled:opacity-30"><Trash2 className="h-4 w-4" /></button>
          </div>)}
          <button type="button" onClick={() => setLines((current) => [...current, { sku_id: "", quantity: "", unit: "" }])} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-stone-200 px-3 text-sm font-semibold text-stone-700 hover:bg-stone-50"><Plus className="h-4 w-4" />增加物料</button>
        </div>
        <Field label="版本备注"><input value={notes} onChange={(e) => setNotes(e.target.value)} className={inputClass} placeholder="例：门店实测后调整" /></Field>
        <SaveButton saving={saving} label="保存新 BOM 版本" disabled={!variantId} />
      </form>
    </EditorCard>
    <section className="rounded-2xl border border-stone-200 bg-white p-5">
      <p className="text-xs font-semibold text-stone-500">版本记录</p><h2 className="mt-1 text-lg font-bold text-stone-950">可追溯，不覆盖历史</h2>
      <div className="mt-4 space-y-3">{[...context.bom_versions].reverse().map((bom) => { const variant = context.variants.find((item) => item.id === bom.variant_id); const product = context.products.find((item) => item.id === bom.product_id); return <article key={bom.id} className="rounded-xl border border-stone-200 p-4"><div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold text-stone-950">{product?.name} · {variant?.name}</p><p className="mt-1 text-xs text-stone-500">{bom.effective_date} · {bom.source}</p></div><span className="rounded-full bg-stone-900 px-2 py-1 text-xs font-semibold text-white">v{bom.version}</span></div><p className="mt-3 text-xs leading-5 text-stone-600">{bom.lines.map((line) => `${line.sku_name} ${line.quantity}${line.unit}`).join("、")}</p></article>; })}{!context.bom_versions.length && <Empty message="尚无 BOM 版本；右侧的毛利链路会继续保持数据不足。" />}</div>
    </section>
  </div>;
}

const inputClass = "h-11 w-full rounded-lg border border-stone-200 bg-white px-3 text-sm text-stone-900 outline-none transition focus:border-orange-500 focus:ring-2 focus:ring-orange-100";
function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="block text-xs font-semibold text-stone-600">{label}<span className="mt-1.5 block">{children}</span></label>; }
function Select({ value, onChange, options }: { value: string; onChange: (value: string) => void; options: Array<{ value: string; label: string }> }) { return <div className="relative"><select required value={value} onChange={(e) => onChange(e.target.value)} className={`${inputClass} appearance-none pr-9`}><option value="">请选择</option>{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select><ChevronDown className="pointer-events-none absolute right-3 top-3.5 h-4 w-4 text-stone-400" /></div>; }
function SaveButton({ saving, label, disabled }: { saving: boolean; label: string; disabled?: boolean }) { return <button disabled={saving || disabled} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-stone-900 px-5 text-sm font-semibold text-white hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-40"><Save className="h-4 w-4" />{saving ? "保存中…" : label}</button>; }
function EditorCard({ title, description, children }: { title: string; description: string; children: React.ReactNode }) { return <section className="rounded-2xl border border-stone-200 bg-white p-5"><h2 className="text-lg font-bold text-stone-950">{title}</h2><p className="mt-1 text-sm leading-6 text-stone-500">{description}</p><div className="mt-5">{children}</div></section>; }
function Empty({ message }: { message: string }) { return <div className="rounded-xl border border-dashed border-stone-300 bg-stone-50 p-6 text-center text-sm leading-6 text-stone-500">{message}</div>; }
function Metric({ value, label }: { value: number; label: string }) { return <div className="min-w-0 rounded-xl border border-white/10 bg-white/[0.06] px-2 py-3 text-center"><p className="text-xl font-bold tabular-nums">{value}</p><p className="mt-1 truncate text-[11px] text-stone-400">{label}</p></div>; }
function Fact({ label, value }: { label: string; value: string }) { return <div className="rounded-xl bg-stone-50 p-3"><p className="text-xs text-stone-500">{label}</p><p className="mt-1 text-lg font-bold tabular-nums text-stone-950">{value}</p></div>; }
function ChainStep({ index, title, body, done }: { index: string; title: string; body: string; done: boolean }) { return <div className="flex gap-3 rounded-xl border border-stone-200 p-3"><span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${done ? "bg-emerald-100 text-emerald-800" : "bg-stone-100 text-stone-500"}`}>{done ? <Check className="h-4 w-4" /> : index}</span><div><p className="text-sm font-semibold text-stone-900">{title}</p><p className="mt-0.5 text-xs leading-5 text-stone-500">{body}</p></div></div>; }
function EntryLink({ href, icon: Icon, title, description }: { href: string; icon: typeof Boxes; title: string; description: string }) { return <Link href={href} className="group flex min-h-[76px] items-center gap-3 border-b border-white/10 px-5 py-3 transition-colors hover:bg-white/[0.06] last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-orange-400/15 text-orange-300"><Icon className="h-4 w-4" /></span><span className="min-w-0 flex-1"><span className="block text-sm font-semibold">{title}</span><span className="mt-0.5 block text-xs text-stone-400">{description}</span></span><ArrowRight className="h-4 w-4 text-stone-500 transition-transform group-hover:translate-x-0.5 group-hover:text-white" /></Link>; }
