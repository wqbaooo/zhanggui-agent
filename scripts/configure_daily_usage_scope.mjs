#!/usr/bin/env node
/** Keep the live daily-use scope small while preserving every SKU for stocktake and purchasing. */

import fs from "node:fs/promises";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const DATA_FILE = path.join(ROOT, "project_data/xinyu-hengtai-dakou/skus.json");
const DAILY_USAGE_NAMES = new Set([
  "章鱼预拌粉", "调料包", "原味酱", "香甜酱", "藤椒酱", "蛋黄酱", "番茄酱", "芥末酱",
  "木鱼花", "切丝海苔", "青海苔粉", "海苔肉松", "章鱼粒", "章鱼花", "玉米粒", "培根丁",
  "肉肠", "麻辣鲜蛤", "咸蛋黄", "奶酪酱", "芝士", "蟹柳",
  "章鱼烧盒子（4粒）", "章鱼烧盒子（6粒）", "全家福打包盒", "全家福打包盒塑料盖",
  "外卖塑料袋", "外卖无纺布袋", "纸巾", "竹签", "外卖贴纸", "标签纸",
  "收银纸80*80", "收银纸57*50", "烤肠竹签",
]);

const payload = JSON.parse(await fs.readFile(DATA_FILE, "utf8"));
let daily = 0;
let periodic = 0;
for (const sku of payload.skus || []) {
  if (sku.active === false || sku.asset_class === "equipment" || sku.tracking_mode === "asset_registry") continue;
  if (sku.id === "sku-local-receipt-paper-40x35") sku.name = "收银纸80*80";
  if (sku.id === "sku-local-sausage-skewer") {
    sku.spec = "包";
    sku.unit = "包";
    sku.display_unit = "包";
    sku.standard_unit = "包";
  }
  sku.tracking_mode = DAILY_USAGE_NAMES.has(sku.name) ? "daily_usage" : "periodic_count";
  sku.usage_integer_only = true;
  if (sku.tracking_mode === "daily_usage") daily += 1;
  else periodic += 1;
}
payload.metadata ||= {};
payload.metadata.daily_usage_scope = {
  updated_on: "2026-07-27",
  rule: "按老板重新整理的常用清单：常温食材12项、冷链食材10项、营业包装13项；其余改为阶段盘点",
  daily_usage_sku_count: daily,
  periodic_count_sku_count: periodic,
};
await fs.writeFile(DATA_FILE, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ daily_usage_sku_count: daily, periodic_count_sku_count: periodic }, null, 2));
