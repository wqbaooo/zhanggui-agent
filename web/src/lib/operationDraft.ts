import type { DailyOperationEntry } from "@/lib/api";

export interface OperationDraftField {
  key: keyof DailyOperationEntry;
  label: string;
  value: number | string;
  confidence: "high" | "medium";
}

export interface OperationDraft {
  source: string;
  entry: DailyOperationEntry;
  fields: OperationDraftField[];
  missing: string[];
  confidence: "high" | "medium";
}

const FIELD_LABELS: Partial<Record<keyof DailyOperationEntry, string>> = {
  date: "日期",
  revenue: "营收",
  orders: "订单",
  bad_reviews: "差评",
  food_cost: "食材成本",
  labor: "人工",
  rent_allocated: "租金摊销",
  utility: "水电",
  other_cost: "其他成本",
  takeout_orders: "外卖单",
  platform_fee: "平台费",
  marketing_cost: "营销/满减",
  inventory_loss: "报损",
  notes: "备注",
};

const REQUIRED_FOR_DIAGNOSIS: Array<keyof DailyOperationEntry> = [
  "revenue",
  "orders",
  "food_cost",
  "labor",
  "takeout_orders",
  "platform_fee",
  "bad_reviews",
];

export function parseOperationDraft(input: string, today = new Date()): OperationDraft | null {
  const text = input.trim();
  if (!text) return null;

  const entry: DailyOperationEntry = {
    date: toDateInputValue(today),
    revenue: 0,
    orders: 0,
    bad_reviews: 0,
    food_cost: 0,
    labor: 0,
    rent_allocated: 0,
    utility: 0,
    other_cost: 0,
    takeout_orders: 0,
    platform_fee: 0,
    marketing_cost: 0,
    inventory_loss: 0,
    notes: text,
  };

  const fields: OperationDraftField[] = [];
  captureNumber(text, /(?:营收|营业额|流水|收入)\s*(?:是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)/, entry, fields, "revenue");
  captureNumber(text, /(?:^|[，,\s])([0-9]+)\s*(?:单|订单)(?!价)/, entry, fields, "orders");
  captureNumber(text, /(?:差评|差评数|坏评)\s*(?:是|为|:|：)?\s*([0-9]+)/, entry, fields, "bad_reviews");
  captureNumber(text, /(?:外卖|外卖单|外卖订单)\s*(?:是|为|:|：)?\s*([0-9]+)\s*(?:单|订单)?/, entry, fields, "takeout_orders");
  captureNumber(text, /(?:食材|物料|原料|食材成本|物料成本)\s*(?:成本|花了|是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)/, entry, fields, "food_cost");
  captureNumber(text, /(?:人工|人工成本|工资)\s*(?:成本|花了|是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)/, entry, fields, "labor");
  captureNumber(text, /(?:租金|房租)\s*(?:摊销|成本|是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)/, entry, fields, "rent_allocated");
  captureNumber(text, /(?:水电|水电费|能耗)\s*(?:是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)/, entry, fields, "utility");
  captureNumber(text, /(?:平台费|平台佣金|佣金|扣点)\s*(?:是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)/, entry, fields, "platform_fee");
  captureNumber(text, /(?:营销|满减|活动|推广)\s*(?:成本|花了|是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)/, entry, fields, "marketing_cost");
  captureNumber(text, /(?:报损|损耗|库存损耗)\s*(?:是|为|:|：)?\s*([0-9]+(?:\.[0-9]+)?)/, entry, fields, "inventory_loss");

  if (!fields.some((field) => field.key === "revenue" || field.key === "orders")) {
    return null;
  }

  const missing = REQUIRED_FOR_DIAGNOSIS
    .filter((key) => !fields.some((field) => field.key === key))
    .map((key) => FIELD_LABELS[key] ?? String(key));

  return {
    source: text,
    entry,
    fields,
    missing,
    confidence: fields.length >= 3 ? "high" : "medium",
  };
}

export function toDateInputValue(date: Date) {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function captureNumber(
  text: string,
  pattern: RegExp,
  entry: DailyOperationEntry,
  fields: OperationDraftField[],
  key: keyof DailyOperationEntry,
) {
  const match = text.match(pattern);
  if (!match?.[1]) return;
  const value = Number(match[1]);
  if (!Number.isFinite(value)) return;
  (entry[key] as number) = value;
  fields.push({
    key,
    label: FIELD_LABELS[key] ?? String(key),
    value,
    confidence: "high",
  });
}
