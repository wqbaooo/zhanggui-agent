#!/usr/bin/env node
/** One-time integrity repair: total stock must equal the sum of physical locations. */

import fs from "node:fs/promises";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const FILE = path.join(ROOT, "project_data/xinyu-hengtai-dakou/skus.json");
const data = JSON.parse(await fs.readFile(FILE, "utf8"));
const repaired = [];

for (const sku of data.skus || []) {
  const locations = sku.stock_by_location || {};
  const total = Math.round(Object.values(locations).reduce((sum, value) => sum + (Number(value) || 0), 0) * 10000) / 10000;
  const previous = Number(sku.current_stock || 0);
  if (Math.abs(previous - total) > 0.0001) {
    repaired.push({ id: sku.id, name: sku.name, previous, total });
    sku.current_stock = total;
  }
}

data.integrity_repairs ||= [];
data.integrity_repairs.push({
  id: "location-total-repair-20260727",
  applied_at: new Date().toISOString(),
  rule: "current_stock = sum(stock_by_location)",
  repaired,
});
data.updated_at = Date.now() / 1000;
const temp = `${FILE}.tmp`;
await fs.writeFile(temp, JSON.stringify(data, null, 2));
await fs.rename(temp, FILE);
console.log(JSON.stringify({ repaired_count: repaired.length, repaired }, null, 2));
