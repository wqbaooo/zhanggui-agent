#!/usr/bin/env node
/** Import the owner-completed inventory intake workbook without replaying old receipts. */

import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile } from "/Users/wqboo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const ROOT = path.resolve(import.meta.dirname, "..");
const PROJECT_ID = "xinyu-hengtai-dakou";
const SOURCE = path.join(ROOT, "outputs/inventory-data-intake-20260726/大口章鱼烧_库存资料补充采集表_含进货记录_2026-07-26.xlsx");
const DATA_FILE = path.join(ROOT, "project_data", PROJECT_ID, "skus.json");
const OUT_DIR = path.join(ROOT, "outputs/inventory-intake-import-20260727");
const APPLY = process.argv.includes("--apply");
const IMPORT_ID = "owner-inventory-intake-20260726-v1";
const DAILY_USAGE_NAMES = new Set([
  "章鱼预拌粉", "调料包", "原味酱", "香甜酱", "藤椒酱", "蛋黄酱", "番茄酱", "芥末酱",
  "木鱼花", "切丝海苔", "青海苔粉", "海苔肉松", "章鱼粒", "章鱼花", "玉米粒", "培根丁",
  "肉肠", "麻辣鲜蛤", "咸蛋黄", "奶酪酱", "芝士", "蟹柳",
  "章鱼烧盒子（4粒）", "章鱼烧盒子（6粒）", "全家福打包盒", "全家福打包盒塑料盖",
  "外卖塑料袋", "外卖无纺布袋", "纸巾", "竹签", "外卖贴纸", "标签纸",
  "收银纸80*80", "收银纸57*50", "烤肠竹签",
]);

const cleanText = (value) => {
  const text = value == null ? "" : String(value).trim();
  return text === "16" ? "" : text;
};
const number = (value) => typeof value === "number" && Number.isFinite(value) ? value : 0;
const slug = (value) => String(value || "unknown").replace(/^ID:/, "").replace(/[^0-9A-Za-z_-]+/g, "-").slice(0, 70);

const workbook = await SpreadsheetFile.importXlsx(await fs.readFile(SOURCE));
const rows = (sheetName, address) => workbook.worksheets.getItem(sheetName).getRange(address).values;
const baselineRows = rows("01_当前库存基线", "A4:M74")
  .filter((row) => cleanText(row[0]) && cleanText(row[1]));
const orderRows = rows("02_进货订单汇总", "A6:R28")
  .filter((row) => cleanText(row[0]));
const detailRows = rows("03_进货商品明细", "A4:Q44")
  .filter((row) => cleanText(row[0]) && cleanText(row[2]));

const payload = JSON.parse(await fs.readFile(DATA_FILE, "utf8"));
payload.imports ||= [];
if (payload.imports.some((item) => item.id === IMPORT_ID)) {
  console.log(JSON.stringify({ status: "already_imported", import_id: IMPORT_ID }, null, 2));
  process.exit(0);
}

const missingIds = {
  "封口袋15*22": "sku-local-seal-bag-15x22",
  "收银纸40*35": "sku-local-receipt-paper-40x35",
  "烤肠竹签": "sku-local-sausage-skewer",
  "鸡蛋": "sku-local-eggs",
  "黑色记号笔": "sku-local-marker",
  "蟑螂药": "sku-local-roach-bait",
  "总部蛤蜊新品（历史）": "sku-hq-clams-bag-history",
};

const operationalOverrides = {
  "海苔肉松": { unit: "包", spec: "2kg/2.1kg/包", unitCost: 107.9 },
  "蛤蜊": { name: "麻辣鲜蛤", unit: "盒", spec: "500g/盒", unitCost: 26.6, supplier: "1688" },
  "保鲜膜": { unit: "包", unitCost: 30 },
  "封口袋8×12": { unit: "盒", spec: "盒/100个", unitCost: 12 },
  "口罩": { unit: "盒", spec: "200只/盒（现用）", unitCost: 25.8 },
  "全家福打包盒": { unit: "包", unitCost: 29, countUnits: [{ unit: "箱", conversion: 12, base_unit: "包" }] },
  "全家福打包盒塑料盖": { unit: "包", unitCost: 7.5, countUnits: [{ unit: "箱", conversion: 12, base_unit: "包" }] },
  "外卖塑料袋": { unit: "把", unitCost: 22, countUnits: [{ unit: "件", conversion: 50, base_unit: "把" }] },
  "外卖无纺布袋": { unit: "捆", unitCost: 27.5 },
  "锡箔纸": { unit: "包", spec: "包/200张", unitCost: 40 },
  "一次性手套": { unit: "盒", spec: "盒/400只", unitCost: 39.8 },
  "章鱼烧盒子（4粒）": { unit: "组", unitCost: 43.5, countUnits: [{ unit: "箱", conversion: 10, base_unit: "组" }] },
  "章鱼烧盒子（6粒）": { unit: "组", unitCost: 36, countUnits: [{ unit: "箱", conversion: 10, base_unit: "组" }] },
  "纸巾": { unit: "提", spec: "一箱/4提/20kg", unitCost: 36.25 },
  "收银纸40*35": { name: "收银纸80*80", unit: "卷", spec: "箱/50卷/10组" },
  "烤肠竹签": { unit: "包", spec: "包" },
  "芝士": { unit: "袋", spec: "2.5kg/袋", unitCost: 88.53, supplier: "拼多多" },
};

const skuById = new Map(payload.skus.map((sku) => [sku.id, sku]));
const skuByName = new Map(payload.skus.map((sku) => [sku.name, sku]));
const activeIds = new Set();
const materialBaseline = [];
const equipmentBaseline = [];

for (const row of baselineRows) {
  const category = cleanText(row[0]);
  const originalName = cleanText(row[1]);
  const spec = cleanText(row[2]);
  const inputUnit = cleanText(row[3]);
  const isEquipment = category === "设备用品";
  const systemId = cleanText(row[12]);
  const override = operationalOverrides[originalName] || {};
  const finalName = override.name || originalName;
  let sku = (systemId && skuById.get(systemId)) || skuByName.get(originalName) || skuByName.get(finalName);
  if (!sku) {
    const id = missingIds[originalName] || `sku-local-${slug(originalName)}`;
    sku = { id, created_at: Date.now() / 1000 };
    payload.skus.push(sku);
    skuById.set(id, sku);
    skuByName.set(originalName, sku);
  }
  const unit = override.unit || inputUnit || sku.display_unit || sku.unit || "个";
  Object.assign(sku, {
    name: finalName,
    category,
    spec: override.spec || spec,
    unit,
    display_unit: unit,
    standard_unit: unit,
    count_units: override.countUnits || sku.count_units || [],
    current_stock: number(row[4]) + number(row[5]) + number(row[6]),
    stock_by_location: {
      store: number(row[4]),
      warehouse: number(row[5]),
      freezer: number(row[6]),
      unallocated: 0,
    },
    asset_class: isEquipment ? "equipment" : "inventory",
    tracking_mode: isEquipment ? "asset_registry" : DAILY_USAGE_NAMES.has(finalName) ? "daily_usage" : "periodic_count",
    reorder_enabled: !isEquipment,
    usage_integer_only: true,
    active: true,
    master_data_status: "complete",
    master_source: path.basename(SOURCE),
    master_source_row: baselineRows.indexOf(row) + 4,
    baseline_date: "2026-07-22",
    baseline_source: IMPORT_ID,
    updated_at: Date.now() / 1000,
  });
  if (override.unitCost != null) sku.unit_cost = override.unitCost;
  if (override.supplier) sku.supplier = override.supplier;
  activeIds.add(sku.id);
  (isEquipment ? equipmentBaseline : materialBaseline).push({ sku, row });
}

const extras = [
  { name: "鸡蛋", category: "冷链食材", spec: "箱/360个（总部目录）", unit: "个", stock: 0, supplier: "总部", unitCost: 280 / 360, tracking: "periodic_count", reorder: true },
  { name: "黑色记号笔", category: "低值耗材", spec: "4支/组", unit: "组", stock: 1, supplier: "淘宝", unitCost: 1.99, tracking: "periodic_count", reorder: false },
  { name: "蟑螂药", category: "清洁耗材", spec: "6枚/盒", unit: "盒", stock: 1, supplier: "淘宝闪购", unitCost: 6.08, tracking: "periodic_count", reorder: false },
];
for (const item of extras) {
  let sku = skuByName.get(item.name);
  if (!sku) {
    sku = { id: missingIds[item.name], created_at: Date.now() / 1000 };
    payload.skus.push(sku);
    skuByName.set(item.name, sku);
    skuById.set(sku.id, sku);
  }
  Object.assign(sku, {
    name: item.name, category: item.category, spec: item.spec,
    unit: item.unit, display_unit: item.unit, standard_unit: item.unit,
    current_stock: item.stock, stock_by_location: { store: item.stock, warehouse: 0, freezer: 0, unallocated: 0 },
    supplier: item.supplier, unit_cost: item.unitCost, tracking_mode: item.tracking,
    reorder_enabled: item.reorder, usage_integer_only: true, active: true,
    asset_class: "inventory", master_data_status: "complete", master_source: path.basename(SOURCE),
    updated_at: Date.now() / 1000,
  });
  activeIds.add(sku.id);
}

// Keep non-store headquarters catalogue entries as searchable history, not active store inventory.
for (const sku of payload.skus) {
  if (sku.asset_class !== "equipment" && !activeIds.has(sku.id)) sku.active = false;
  if (sku.name === "海苔肉松") {
    sku.name = "海苔肉松";
    sku.unit = "包";
    sku.display_unit = "包";
  }
}

// Headquarters clam was a different historical material and must not be merged into the current 1688 SKU.
if (!skuById.has(missingIds["总部蛤蜊新品（历史）"])) {
  payload.skus.push({
    id: missingIds["总部蛤蜊新品（历史）"], name: "总部蛤蜊新品（历史）", category: "冷链食材",
    spec: "1kg/袋", unit: "袋", display_unit: "袋", standard_unit: "袋", current_stock: 0,
    stock_by_location: {}, supplier: "总部", unit_cost: 60, active: false, asset_class: "inventory",
    tracking_mode: "periodic_count", reorder_enabled: false, usage_integer_only: true,
    master_data_status: "complete", master_source: path.basename(SOURCE), created_at: Date.now() / 1000, updated_at: Date.now() / 1000,
  });
}

// Replace only the imported 2026-07-22 baseline sessions; older evidence remains untouched.
payload.inventory_counts = (payload.inventory_counts || []).filter((count) => count.import_id !== IMPORT_ID);
for (const location of ["store", "warehouse", "freezer"]) {
  const lines = materialBaseline.map(({ sku }) => ({
    sku_id: sku.id, name: sku.name, unit: sku.unit, display_unit: sku.display_unit,
    input_quantity: number(sku.stock_by_location[location]), input_unit: sku.display_unit,
    expected_quantity: number(sku.stock_by_location[location]), counted_quantity: number(sku.stock_by_location[location]),
    variance_quantity: 0, variance_rate: 0, components: [], notes: "老板补充采集表实盘",
  }));
  payload.inventory_counts.push({
    id: `count-owner-20260722-${location}`, date: "2026-07-22", location, count_type: "baseline",
    lines, source: "owner_completed_intake", notes: "库存资料补充采集表建立的新基线", import_id: IMPORT_ID,
    created_at: Date.now() / 1000,
  });
}

const detailByOrder = new Map();
for (const row of detailRows) {
  const evidence = cleanText(row[14]);
  if (!detailByOrder.has(evidence)) detailByOrder.set(evidence, []);
  const rawSkuId = cleanText(row[10]);
  let skuId = skuById.has(rawSkuId) ? rawSkuId : "";
  const purchaseName = cleanText(row[2]);
  if (purchaseName === "蛤蜊新品") skuId = missingIds["总部蛤蜊新品（历史）"];
  if (purchaseName === "黑色记号笔") skuId = missingIds["黑色记号笔"];
  if (purchaseName === "蟑螂药") skuId = missingIds["蟑螂药"];
  let quantity = number(row[13]) || number(row[4]);
  let unit = cleanText(row[11]) || cleanText(row[5]);
  if (purchaseName === "医用外科口罩") { quantity = 1; unit = "盒"; }
  if (purchaseName === "全家福盒" || purchaseName === "全家福盖子") { quantity = 12; unit = "包"; }
  if (purchaseName === "6粒盒子") { quantity = 20; unit = "组"; }
  if (purchaseName === "外卖塑料袋") { quantity = 30; unit = "把"; }
  if (purchaseName === "竹签") { quantity = 50; unit = "包"; }
  if (purchaseName === "肉松") unit = "包";
  detailByOrder.get(evidence).push({
    sku_id: skuId, name: purchaseName, purchase_spec: cleanText(row[3]), quantity,
    unit, unit_cost: quantity > 0 ? Math.round(number(row[6]) / quantity * 1e6) / 1e6 : 0,
    subtotal: number(row[6]), match_status: skuId ? "matched" : "non_inventory_or_pending_master",
  });
}

const importedPurchases = [];
for (const row of orderRows) {
  const evidence = cleanText(row[14]);
  const externalId = cleanText(row[3]).replace(/^ID:/, "");
  const isFlash = cleanText(row[0]) === "淘宝闪购";
  const date = isFlash ? "2026-07-06" : cleanText(row[1]);
  const orderId = isFlash ? "4007370348608112207" : externalId;
  const purchase = {
    id: `purchase-intake-${slug(orderId)}`, date, platform: cleanText(row[0]), supplier: cleanText(row[4]),
    external_order_id: orderId, items: detailByOrder.get(evidence) || [], total_cost: number(row[12]),
    payment_status: number(row[12]) > 0 ? "已付款" : "已退款", paid_amount: number(row[10]),
    fulfillment_status: cleanText(row[6]) === "退款成功" ? "refunded" : "received",
    location: "warehouse", received_at: date, freight: number(row[8]), discount_amount: number(row[9]),
    refund_amount: number(row[11]), evidence_file: evidence,
    accounting_status: "inventory_asset_or_low_value_asset_pending_line_classification",
    notes: cleanText(row[15]), import_id: IMPORT_ID, created_at: Date.now() / 1000,
  };
  importedPurchases.push(purchase);
}
payload.purchases = (payload.purchases || []).filter((purchase) => purchase.import_id !== IMPORT_ID);
payload.purchases.push(...importedPurchases);

// Later receipts explicitly written by the owner after the 2026-07-22 baseline.
const laterReceipts = [
  { name: "藤椒酱", quantity: 6, date: "2026-07-22", note: "老板注明后续已到货6包" },
  { name: "玉米粒", quantity: 6, date: "2026-07-25", note: "老板注明后续已到货6包；订单截图显示5包，差1包待后续凭证核对" },
  { name: "芝士", quantity: 1, date: "2026-07-26", note: "拉斯佳2.5kg/袋，拼多多平替，实付88.53元" },
];
payload.inventory_events = (payload.inventory_events || []).filter((event) => event.import_id !== IMPORT_ID);
for (const receipt of laterReceipts) {
  const sku = skuByName.get(receipt.name);
  if (!sku) continue;
  sku.stock_by_location.store = number(sku.stock_by_location.store) + receipt.quantity;
  sku.current_stock = Object.values(sku.stock_by_location).reduce((sum, value) => sum + number(value), 0);
  payload.inventory_events.push({
    id: `event-owner-later-${sku.id}`, date: receipt.date, event_type: "receipt_adjustment", sku_id: sku.id,
    quantity: receipt.quantity, from_location: "", to_location: "store", source: "owner_completed_intake",
    notes: receipt.note, metadata: { import_id: IMPORT_ID, evidence_status: "owner_confirmed_note" },
    import_id: IMPORT_ID, created_at: Date.now() / 1000,
  });
}

payload.imports.push({
  id: IMPORT_ID, source_file: SOURCE, imported_at: new Date().toISOString(),
  baseline_date: "2026-07-22", material_count: materialBaseline.length + extras.length,
  equipment_count: equipmentBaseline.length, purchase_order_count: importedPurchases.length,
  rules: ["ignore_placeholder_16", "operational_units", "historical_receipts_not_replayed", "late_owner_receipts_applied"],
});
payload.updated_at = Date.now() / 1000;

const report = {
  mode: APPLY ? "apply" : "dry_run", import_id: IMPORT_ID,
  active_materials: payload.skus.filter((sku) => sku.active !== false && sku.asset_class !== "equipment").length,
  equipment: payload.skus.filter((sku) => sku.active !== false && sku.asset_class === "equipment").length,
  purchase_orders: importedPurchases.length,
  baseline_counts: materialBaseline.length,
  unresolved: [
    "玉米粒后续备注为6包，但已归档订单截图为5包，差1包保留待核对",
    "青芥末退款单未收货；替代采购订单资料仍待补",
    "商品级毛利仍需完整菜单BOM和各渠道销量",
    "保质期与开封后效期仍待总部规则照片",
  ],
};

await fs.mkdir(OUT_DIR, { recursive: true });
await fs.writeFile(path.join(OUT_DIR, "import-report.json"), JSON.stringify(report, null, 2));
await fs.writeFile(path.join(OUT_DIR, "skus.after.preview.json"), JSON.stringify(payload, null, 2));
if (APPLY) {
  const backup = path.join(OUT_DIR, "skus.before-import.json");
  await fs.copyFile(DATA_FILE, backup);
  const temp = `${DATA_FILE}.tmp`;
  await fs.writeFile(temp, JSON.stringify(payload, null, 2));
  await fs.rename(temp, DATA_FILE);
}
console.log(JSON.stringify(report, null, 2));
