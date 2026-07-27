#!/usr/bin/env node
/** Create the editable, print-first inventory workbook aligned with the live SKU ledger. */

import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "/Users/wqboo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const ROOT = path.resolve(import.meta.dirname, "..");
const DATA_FILE = path.join(ROOT, "project_data/xinyu-hengtai-dakou/skus.json");
const EVIDENCE_DIR = path.join(ROOT, "project_data/xinyu-hengtai-dakou/documents/evidence/inventory-purchases/2026-07");
const OUT_DIR = path.join(ROOT, "outputs/inventory-offline-forms-20260727");
const OUTPUT = path.join(OUT_DIR, "大口章鱼烧_库存线下执行表_2026-07-27.xlsx");
const PUBLIC_OUTPUT = path.join(ROOT, "web/public/downloads/大口章鱼烧_库存线下表格_2026-07-27.xlsx");
const PUBLIC_COMPAT = path.join(ROOT, "web/public/downloads/大口章鱼烧_库存线下表格_2026-07-26.xlsx");
const PUBLIC_EVIDENCE_DIR = path.join(ROOT, "web/public/downloads/inventory-evidence");

const data = JSON.parse(await fs.readFile(DATA_FILE, "utf8"));
const categoryOrder = { "常温食材": 0, "冷链食材": 1, "包装耗材": 2, "清洁耗材": 3, "低值耗材": 4 };
const nameOrder = ["章鱼预拌粉", "调料包", "原味酱", "香甜酱", "藤椒酱", "蛋黄酱", "木鱼花", "切丝海苔", "青海苔粉", "海苔肉松", "章鱼粒", "章鱼花", "鸡蛋"];
const materials = data.skus
  .filter((sku) => sku.active !== false && sku.asset_class !== "equipment" && sku.tracking_mode !== "asset_registry")
  .sort((a, b) => {
    const categoryDelta = (categoryOrder[a.category] ?? 99) - (categoryOrder[b.category] ?? 99);
    if (categoryDelta) return categoryDelta;
    const ai = nameOrder.indexOf(a.name);
    const bi = nameOrder.indexOf(b.name);
    if (ai >= 0 || bi >= 0) return (ai < 0 ? 999 : ai) - (bi < 0 ? 999 : bi);
    return a.name.localeCompare(b.name, "zh-CN");
  });
const dailyMaterials = materials.filter((sku) => sku.tracking_mode === "daily_usage");
const purchases = data.purchases
  .filter((purchase) => purchase.import_id === "owner-inventory-intake-20260726-v1")
  .sort((a, b) => `${a.date}-${a.id}`.localeCompare(`${b.date}-${b.id}`));

const COLORS = {
  ink: "#17211E", muted: "#64706C", line: "#B9C5C0", soft: "#F2F6F4",
  green: "#0F766E", greenSoft: "#DFF3ED", amber: "#B45309", amberSoft: "#FEF3C7", white: "#FFFFFF",
};
const workbook = Workbook.create();
workbook.comments.setSelf({ displayName: "掌柜Agent" });

function colName(index) {
  let value = index + 1;
  let name = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    name = String.fromCharCode(65 + remainder) + name;
    value = Math.floor((value - 1) / 26);
  }
  return name;
}

function styleTitle(sheet, endCol, title, subtitle) {
  const end = colName(endCol);
  sheet.showGridLines = false;
  sheet.mergeCells(`A1:${end}1`);
  sheet.getRange("A1").values = [[title]];
  sheet.getRange(`A1:${end}1`).format = {
    fill: COLORS.green, font: { bold: true, color: COLORS.white, size: 18 },
    horizontalAlignment: "center", verticalAlignment: "center",
  };
  sheet.getRange(`A1:${end}1`).format.rowHeight = 34;
  sheet.mergeCells(`A2:${end}2`);
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange(`A2:${end}2`).format = {
    fill: COLORS.greenSoft, font: { color: COLORS.ink, size: 10 },
    horizontalAlignment: "center", verticalAlignment: "center", wrapText: true,
  };
  sheet.getRange(`A2:${end}2`).format.rowHeight = 28;
}

function styleHeader(range) {
  range.format = {
    fill: COLORS.ink, font: { bold: true, color: COLORS.white, size: 9 },
    horizontalAlignment: "center", verticalAlignment: "center", wrapText: true,
    borders: { preset: "all", style: "thin", color: COLORS.line },
  };
  range.format.rowHeight = 25;
}

function styleBody(range) {
  range.format = {
    font: { color: COLORS.ink, size: 9 }, verticalAlignment: "center", wrapText: true,
    borders: { preset: "all", style: "thin", color: COLORS.line },
  };
  range.format.rowHeight = 25;
}

// 1) One day, one A4 landscape sheet. Only frequent operating items belong here;
// low-frequency consumables remain in the complete stocktake and purchase ledgers.
{
  const sheet = workbook.worksheets.add("每日使用表");
  styleTitle(sheet, 16, "大口章鱼烧 · 每日物料使用登记表", "营业日期：____年__月__日    只记当天实际开封/领用数量（整数）；未使用留空；低频耗材在阶段盘点表管理。打印：A4 横向、1页。");
  const groups = [
    { category: "常温食材", label: "常温食材", color: COLORS.green },
    { category: "冷链食材", label: "冷链食材", color: "#0369A1" },
    { category: "包装耗材", label: "营业包装", color: COLORS.amber },
  ];
  const headers = ["品名", "规格", "单位", "今日使用", "异常/备注"];
  const maxRows = Math.max(...groups.map((group) => dailyMaterials.filter((sku) => sku.category === group.category).length));
  for (let panel = 0; panel < groups.length; panel += 1) {
    const group = groups[panel];
    const groupItems = dailyMaterials.filter((sku) => sku.category === group.category);
    const startCol = panel * 6;
    const start = colName(startCol);
    const end = colName(startCol + 4);
    sheet.mergeCells(`${start}4:${end}4`);
    sheet.getRange(`${start}4`).values = [[`${group.label}  ·  ${groupItems.length} 项`]];
    sheet.getRange(`${start}4:${end}4`).format = {
      fill: group.color, font: { bold: true, color: COLORS.white, size: 11 },
      horizontalAlignment: "left", verticalAlignment: "center",
    };
    sheet.getRange(`${start}4:${end}4`).format.rowHeight = 26;
    sheet.getRange(`${start}5:${end}5`).values = [headers];
    styleHeader(sheet.getRange(`${start}5:${end}5`));
    const rows = [];
    for (let offset = 0; offset < maxRows; offset += 1) {
      const sku = groupItems[offset];
      rows.push(sku ? [sku.name, sku.spec || "", sku.display_unit || sku.unit, "", ""] : ["", "", "", "", ""]);
    }
    const rowEnd = 5 + maxRows;
    sheet.getRange(`${start}6:${end}${rowEnd}`).values = rows;
    styleBody(sheet.getRange(`${start}6:${end}${rowEnd}`));
    sheet.getRange(`${colName(startCol + 3)}6:${colName(startCol + 3)}${rowEnd}`).format = {
      fill: COLORS.amberSoft, font: { bold: true, color: COLORS.ink, size: 11 }, horizontalAlignment: "center",
      verticalAlignment: "center", borders: { preset: "all", style: "thin", color: COLORS.line },
    };
    if (panel < 2) sheet.getRange(`${colName(startCol + 5)}1:${colName(startCol + 5)}${rowEnd}`).format.columnWidth = 2;
    [14, 17, 6, 10, 14].forEach((width, i) => { sheet.getRange(`${colName(startCol + i)}:${colName(startCol + i)}`).format.columnWidth = width; });
  }
  const footerRow = 6 + maxRows;
  sheet.mergeCells(`A${footerRow}:Q${footerRow}`);
  sheet.getRange(`A${footerRow}`).values = [["录入线上库存时：选择同一营业日期，照纸面“今日使用”整数录入；重复保存会覆盖当天旧版，不会重复扣库。"]];
  sheet.getRange(`A${footerRow}:Q${footerRow}`).format = { fill: COLORS.soft, font: { color: COLORS.muted, size: 9 }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };
  sheet.getRange(`A${footerRow}:Q${footerRow}`).format.rowHeight = 25;
}

// 2) Periodic owner stocktake. Two panels include the only three physical locations.
{
  const sheet = workbook.worksheets.add("阶段总盘点表");
  styleTitle(sheet, 19, "大口章鱼烧 · 阶段总库存盘点表", "盘点日期：____年__月__日    老板在大盘点时填写；门店含营业区，大冰箱单独记，隔壁仓库单独记。数量统一按表内单位，不换算成个/张。打印建议：A3 横向、1页宽×1页高。");
  const panelSize = Math.ceil(materials.length / 2);
  const headers = ["序号", "类型", "品名", "规格", "单位", "门店", "大冰箱", "仓库", "合计", "异常/备注"];
  for (let panel = 0; panel < 2; panel += 1) {
    const startCol = panel * 10;
    const start = colName(startCol);
    const end = colName(startCol + 9);
    sheet.getRange(`${start}4:${end}4`).values = [headers];
    styleHeader(sheet.getRange(`${start}4:${end}4`));
    const rows = [];
    for (let offset = 0; offset < panelSize; offset += 1) {
      const index = panel * panelSize + offset;
      const sku = materials[index];
      rows.push(sku ? [index + 1, sku.category, sku.name, sku.spec || "", sku.display_unit || sku.unit, "", "", "", "", ""] : ["", "", "", "", "", "", "", "", "", ""]);
    }
    const rowEnd = 4 + panelSize;
    sheet.getRange(`${start}5:${end}${rowEnd}`).values = rows;
    styleBody(sheet.getRange(`${start}5:${end}${rowEnd}`));
    sheet.getRange(`${colName(startCol + 5)}5:${colName(startCol + 8)}${rowEnd}`).format = {
      fill: COLORS.amberSoft, font: { bold: true, color: COLORS.ink, size: 10 }, horizontalAlignment: "center", verticalAlignment: "center",
      borders: { preset: "all", style: "thin", color: COLORS.line },
    };
    [5, 10, 14, 18, 7, 8, 8, 8, 8, 13].forEach((width, i) => { sheet.getRange(`${colName(startCol + i)}:${colName(startCol + i)}`).format.columnWidth = width; });
  }
}

// 3) System/owner purchase ledger. This is not an employee form; it preserves SKU-level accounting evidence.
{
  const sheet = workbook.worksheets.add("进货台账");
  styleTitle(sheet, 15, "大口章鱼烧 · 进货台账（按订单 + SKU）", "来源：老板完成的库存补充采集表。运费保留在订单层；退款单不计入库存；金额与库存成本后续按财务边界对账，不直接当作当期费用。");
  const headers = ["下单日期", "平台", "供应商", "订单号", "物料SKU", "购买品名", "购买规格", "数量", "单位", "单价", "SKU小计", "运费(订单)", "优惠(订单)", "退款(订单)", "订单实付", "凭证文件"];
  sheet.getRange("A4:P4").values = [headers];
  styleHeader(sheet.getRange("A4:P4"));
  const rows = [];
  for (const purchase of purchases) {
    const items = purchase.items.length ? purchase.items : [{ name: "明细待补", quantity: 0, unit: "" }];
    items.forEach((item, index) => rows.push([
      purchase.date, purchase.platform || "", purchase.supplier || "", purchase.external_order_id ? `#${purchase.external_order_id}` : "",
      item.sku_id || "非库存资产/待对应", item.name || "", item.purchase_spec || "", item.quantity || 0, item.unit || "",
      item.unit_cost || 0, item.subtotal || 0, index === 0 ? purchase.freight || 0 : "", index === 0 ? purchase.discount_amount || 0 : "",
      index === 0 ? purchase.refund_amount || 0 : "", index === 0 ? purchase.total_cost || 0 : "", purchase.evidence_file || "",
    ]));
  }
  const endRow = 4 + rows.length;
  sheet.getRange(`A5:P${endRow}`).values = rows;
  styleBody(sheet.getRange(`A5:P${endRow}`));
  sheet.getRange(`D5:D${endRow}`).format.numberFormat = "@";
  sheet.getRange(`J5:O${endRow}`).format.numberFormat = "0.00";
  sheet.getRange(`J5:O${endRow}`).format.horizontalAlignment = "right";
  [12, 12, 18, 24, 24, 18, 24, 8, 8, 10, 10, 10, 10, 10, 11, 28].forEach((width, i) => { sheet.getRange(`${colName(i)}:${colName(i)}`).format.columnWidth = width; });
  sheet.freezePanes.freezeRows(4);
}

// 4) Evidence contact sheet keeps the original screenshots visibly linked to the ledger.
{
  const sheet = workbook.worksheets.add("进货凭证索引");
  styleTitle(sheet, 7, "大口章鱼烧 · 进货原始凭证索引", "每张截图的文件名与进货台账“凭证文件”一一对应；如修改台账，请保留凭证文件名以便日后核对。");
  const uniqueEvidence = [...new Set(purchases.map((purchase) => purchase.evidence_file).filter(Boolean))];
  for (let index = 0; index < uniqueEvidence.length; index += 1) {
    const fileName = uniqueEvidence[index];
    const panel = index % 4;
    const band = Math.floor(index / 4);
    const startCol = panel * 2;
    const startRow = 4 + band * 13;
    const filePath = path.join(EVIDENCE_DIR, fileName);
    try {
      const bytes = await fs.readFile(filePath);
      const mime = fileName.toLowerCase().endsWith(".png") ? "image/png" : "image/jpeg";
      sheet.images.add({
        dataUrl: `data:${mime};base64,${bytes.toString("base64")}`,
        anchor: { from: { row: startRow, col: startCol }, extent: { widthPx: 210, heightPx: 230 } },
      });
    } catch {
      // The ledger still records the evidence filename; missing file stays visibly auditable below.
    }
    const left = colName(startCol);
    const right = colName(startCol + 1);
    sheet.mergeCells(`${left}${startRow + 12}:${right}${startRow + 12}`);
    sheet.getRange(`${left}${startRow + 12}`).values = [[fileName]];
    sheet.getRange(`${left}${startRow + 12}:${right}${startRow + 12}`).format = {
      fill: COLORS.soft, font: { color: COLORS.ink, size: 8 }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true,
      borders: { preset: "outside", style: "thin", color: COLORS.line },
    };
    sheet.getRange(`${left}:${right}`).format.columnWidth = 16;
  }
}

await fs.mkdir(OUT_DIR, { recursive: true });
await fs.mkdir(path.dirname(PUBLIC_OUTPUT), { recursive: true });
await fs.mkdir(PUBLIC_EVIDENCE_DIR, { recursive: true });
for (const fileName of [...new Set(purchases.map((purchase) => purchase.evidence_file).filter(Boolean))]) {
  const source = path.join(EVIDENCE_DIR, fileName);
  const target = path.join(PUBLIC_EVIDENCE_DIR, fileName);
  await fs.unlink(target).catch(() => {});
  await fs.link(source, target).catch(async () => {
    await fs.copyFile(source, target);
  });
}
for (const sheetName of ["每日使用表", "阶段总盘点表", "进货台账"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(path.join(OUT_DIR, `${sheetName}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(OUTPUT);
await fs.copyFile(OUTPUT, PUBLIC_OUTPUT);
await fs.unlink(PUBLIC_COMPAT).catch(() => {});
await fs.link(PUBLIC_OUTPUT, PUBLIC_COMPAT);

const inspection = await workbook.inspect({ kind: "sheet,formula", maxChars: 6000, tableMaxRows: 5, tableMaxCols: 8 });
await fs.writeFile(path.join(OUT_DIR, "workbook-inspection.json"), JSON.stringify(inspection, null, 2));
console.log(JSON.stringify({ output: OUTPUT, public_output: PUBLIC_OUTPUT, material_count: materials.length, daily_usage_count: dailyMaterials.length, purchase_orders: purchases.length, previews: 3 }, null, 2));
