#!/usr/bin/env node
/** Remove non-purchase opening balances and duplicate purchase shadows from the live purchase ledger. */

import fs from "node:fs/promises";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const DATA_FILE = path.join(ROOT, "project_data/xinyu-hengtai-dakou/skus.json");
const OUT_DIR = path.join(ROOT, "outputs/inventory-intake-import-20260727");
const APPLY = process.argv.includes("--apply");
const REPAIR_ID = "purchase-ledger-deduplicate-20260727-v1";

const payload = JSON.parse(await fs.readFile(DATA_FILE, "utf8"));
const purchases = payload.purchases || [];
const importedExternalIds = new Set(
  purchases
    .filter((purchase) => purchase.import_id === "owner-inventory-intake-20260726-v1")
    .map((purchase) => String(purchase.external_order_id || ""))
    .filter(Boolean),
);

const removed = [];
payload.purchases = purchases.filter((purchase) => {
  const isOpeningBalance = purchase.supplier === "原店主盘存";
  const isDuplicateShadow = purchase.import_id !== "owner-inventory-intake-20260726-v1"
    && importedExternalIds.has(String(purchase.external_order_id || ""));
  if (isOpeningBalance || isDuplicateShadow) {
    removed.push({
      id: purchase.id,
      reason: isOpeningBalance ? "opening_balance_is_not_purchase" : "duplicate_external_order_id",
      external_order_id: purchase.external_order_id || "",
      supplier: purchase.supplier || "",
    });
    return false;
  }
  return true;
});

payload.integrity_repairs ||= [];
payload.integrity_repairs = payload.integrity_repairs.filter((repair) => repair.id !== REPAIR_ID);
payload.integrity_repairs.push({
  id: REPAIR_ID,
  repaired_at: new Date().toISOString(),
  rule: "purchase_ledger_contains_only_real_orders_and_one_row_per_external_order",
  removed,
});
payload.updated_at = Date.now() / 1000;

const report = {
  mode: APPLY ? "apply" : "dry_run",
  repair_id: REPAIR_ID,
  before: purchases.length,
  after: payload.purchases.length,
  removed,
};

await fs.mkdir(OUT_DIR, { recursive: true });
await fs.writeFile(path.join(OUT_DIR, "purchase-ledger-repair-report.json"), JSON.stringify(report, null, 2));
if (APPLY) {
  await fs.copyFile(DATA_FILE, path.join(OUT_DIR, "skus.before-purchase-ledger-repair.json"));
  const temp = `${DATA_FILE}.tmp`;
  await fs.writeFile(temp, JSON.stringify(payload, null, 2));
  await fs.rename(temp, DATA_FILE);
}

console.log(JSON.stringify(report, null, 2));
