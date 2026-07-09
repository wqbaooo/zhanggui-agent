const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const DEFAULT_PROJECT_ID = "xinyu-hengtai-dakou";
const API_TIMEOUT_MS = 8000;

export interface DailyOperationEntry {
  date: string;
  revenue: number;
  orders: number;
  dine_in_revenue: number;
  dine_in_orders: number;
  delivery_revenue: number;
  delivery_orders: number;
  food_cost: number;
  packaging_cost: number;
  labor: number;
  rent_allocated: number;
  utility: number;
  other_cost: number;
  takeout_orders: number;
  platform_fee: number;
  marketing_cost: number;
  inventory_loss: number;
  bad_reviews?: number;
  repeat_orders?: number;
  new_members?: number;
  notes?: string;
  // ── 日结清算字段（2026-07-04）──
  original_amount?: number;
  actual_revenue?: number;
  merchant_discount?: number;
  refund_amount?: number;
  refund_orders?: number;
  service_fee?: number;
  delivery_fee?: number;
  surcharge?: number;
  items_sold?: number;
  customers?: number;
  visitors?: number;
  dining_customers?: number;
  sales_transactions?: number;
  avg_order_value_before_discount?: number;
  avg_order_value_after_discount?: number;
  payment_methods?: Array<{ method: string; orders: number; amount: number }>;
  channel_breakdown?: Array<{ channel: string; orders: number; original_amount: number; actual_revenue?: number | null; amount_basis?: "order_amount" | "net_settlement" }>;
  product_sales?: Array<{ name: string; quantity: number; amount: number }>;
  settlement_breakdown?: Array<{
    bucket: string;
    owner: "current_owner" | "former_owner";
    amount: number;
    status: "expected_settled_unconfirmed" | "cash_on_hand" | "pending_reconciliation" | "reconciled";
    expected_at?: string;
    methods?: string[];
  }>;
  revenue_basis?: "net_settlement" | "gross_sales";
  cost_status?: "incomplete" | "confirmed";
  // ── 数据溯源 ──
  source_type?: string;
  source_platform?: string;
  source_file_name?: string;
  source_raw_text?: string;
  source_confidence?: string;
  source_imported_at?: string;
  source_quality_score?: string;
}

export interface OperationSummary {
  days: number;
  entry_count: number;
  total_revenue: number;
  total_original_amount: number;
  total_merchant_discount: number;
  total_refund_amount: number;
  total_service_fee: number;
  total_delivery_fee: number;
  total_surcharge: number;
  total_items_sold: number;
  total_customers: number;
  total_visitors: number;
  total_dining_customers: number;
  total_sales_transactions: number;
  total_orders: number;
  avg_order_value: number;
  prev_total_revenue: number;
  prev_total_original_amount: number;
  prev_total_orders: number;
  prev_net_profit: number;
  prev_avg_order_value: number;
  total_cost: number;
  net_profit: number;
  profit_ready: boolean;
  profit_status: "confirmed" | "missing_costs";
  missing_cost_fields: string[];
  cost_coverage: number;
  food_cost_rate: number;
  labor_cost_rate: number;
  prime_cost: number;
  prime_cost_rate: number;
  platform_fee_rate: number;
  takeout_ratio: number;
  settlement_summary: {
    current_owner: number;
    former_owner: number;
    cash_on_hand: number;
    by_status: Record<string, number>;
    method: string;
  };
  product_sales: Array<{ name: string; quantity: number; amount: number }>;
  bad_review_rate: number;
  total_bad_reviews: number;
  latest_entry: DailyOperationEntry | null;
  alerts: Array<{ level: string; message: string }>;
}

export interface OperationListResponse {
  entries: DailyOperationEntry[];
  summary: OperationSummary;
}

export interface RawMaterial {
  id: string;
  source_type: string;
  source_platform: string;
  title: string;
  ai_summary?: string;
  uploaded_at?: string;
}

export interface BusinessFact {
  id: string;
  raw_material_id: string;
  fact_type: string;
  date: string;
  amount: number;
  platform: string;
  account_location: string;
  business_owner: string;
  confidence: string;
  review_status: string;
  ledger_status: string;
  state: string;
  title?: string;
  description?: string;
  impact_ledger?: string;
  profit_impact?: boolean;
  missing_fields?: string[];
  raw_material?: RawMaterial | null;
  period_start?: string | null;
  period_end?: string | null;
  metadata?: Record<string, unknown>;
  posting_key?: string;
  evidence_role?: "primary" | "supporting" | "discrepancy";
  primary_evidence_id?: string;
  supporting_evidence_ids?: string[];
  duplicate_of?: string;
  source_type?: string;
  source_platform?: string;
  source_date?: string;
  evidence_image_url?: string;
  evidence_file_ref?: string;
  extracted_fields?: Record<string, unknown>;
  posted_at?: string;
  posted_by?: string;
  affects_accounts?: string[];
  affects_inventory_items?: string[];
  source_group?: string;
}

export interface GapQuestion {
  missing: string;
  why: string;
  impact: string;
  action: string;
  priority: "P0" | "P1" | "P2" | string;
  text: string;
}

export interface MoneyView {
  date?: string | null;
  total_sales: number;
  fixture_sales?: RealFixtureSalesCard;
  former_owner?: {
    receivable_from_former_owner: string;
    transferred_to_owner: string;
    pending_allocation: string;
    unsettled: string;
    rule: string;
  };
  accounts: Record<string, number>;
  platform_accounts: Record<string, number>;
  platform_costs: number;
  purchase_spend: number;
  entries: Array<Record<string, unknown>>;
  rules: string[];
}

export interface FirstStageInventoryItem {
  id: string;
  name: string;
  category: string;
  unit: string;
  current_quantity: number;
  latest_unit_cost: number;
  safe_stock: number;
  storage_location: string;
  today_stock_in: number;
  today_estimated_consumption: number;
  today_loss: number;
  today_count_adjustment: number;
  risk_level: "high" | "watch" | "ok";
  purchase_recommendation: number;
  evidence_source?: string;
  confirmation_status?: string;
  latest_unit_cost_source?: string;
  owner_confirmed?: boolean;
}

export interface FirstStageInventory {
  date: string;
  last_count_date?: string;
  pending_inventory_facts?: number;
  inventory_value_basis?: string;
  bom_cost_status?: string;
  items: FirstStageInventoryItem[];
  movements: Array<Record<string, unknown>>;
  alerts: Array<{ level: string; title: string; body: string }>;
  consumption_methods: { theoretical: string; actual: string };
}

export interface TodayOperatingCard {
  date: string;
  sales: Record<string, number>;
  fixture_sales?: RealFixtureSalesCard;
  sources?: string[];
  money_where: MoneyView;
  today_purchase_spend: number;
  today_inventory_consumption_estimate: number;
  estimated_profit: number | null;
  profit_statement?: string;
  missing_fields: GapQuestion[];
  tomorrow_actions: string[];
}

export interface RealFixtureSalesCard {
  source: string;
  sales: {
    order_amount: number;
    net_operating_income: number;
    order_count: number;
    sales_orders: number;
    refund_orders: number;
    dine_in_income: number;
    third_party_income: number;
  };
  deductions: {
    merchant_discount: number;
    delivery_cost: number;
    service_fee: number;
    subsidy_adjustment: number;
  };
  products: Array<{ name: string; quantity: number; amount: number; source: string }>;
  money: Array<{ label: string; amount: number; status: string; source: string }>;
  inventory: { status: string; source: string };
  profit: { confirmed: string; pending: string };
}

export interface CostQuestionAnswer {
  question: string;
  answer: string;
  known_costs: string[];
  missing_fields: string[];
  can_estimate_from: string[];
  follow_up: GapQuestion;
}

export interface UtilityRecord {
  month: string;
  water: number;
  electricity: number;
  notes: string;
}

export interface LifecycleStage {
  label: string;
  status: "done" | "current" | "pending";
  battlefield: "core" | "extension";
}

export interface CockpitAction {
  id: string;
  title: string;
  priority: "high" | "medium" | "low";
  target: string;
  source: string;
  status: string;
  task_id?: string;
  due_date?: string;
}

export interface CockpitEvidence {
  label: string;
  source_type: string;
  confidence: "high" | "medium" | "low" | "missing";
  detail: string;
}

export interface ProjectCockpit {
  project_id: string;
  profile: Record<string, unknown>;
  current_stage: string;
  stages: LifecycleStage[];
  baseline: Record<string, unknown>;
  baseline_comparison: {
    projected_daily_revenue: number | null;
    actual_daily_revenue: number | null;
    revenue_gap: number | null;
    projected_daily_orders: number | null;
    actual_daily_orders: number | null;
    orders_gap: number | null;
  };
  operations: OperationSummary;
  recent_operations: DailyOperationEntry[];
  monthly_comparison: {
    current_month: number;
    available: boolean;
    revenue?: number | null;
    last_year_profit?: number;
    yoy_pct?: number | null;
    estimated_profit?: number | null;
    estimated_monthly_cost?: number;
  };
  data_quality: {
    level: "weak" | "usable";
    missing: string[];
    has_real_operations: boolean;
    operation_days: number;
    has_baseline: boolean;
  };
  decision: {
    decision: string;
    primary_contradiction: string;
    summary: string;
  };
  next_actions: CockpitAction[];
  tasks: CockpitAction[];
  integrations: StoreIntegration[];
  evidence: CockpitEvidence[];
  agent_signals: Array<{
    source: string;
    title: string;
    body: string;
    tone: "good" | "watch" | "risk" | "info";
    target: string;
  }>;
}

export interface StoreIntegration {
  id: string;
  name: string;
  scope: string;
  status: string;
  status_label: string;
  fallback: string;
  available_paths: string[];
  notes?: string;
}

export interface DeliveryImportPayload {
  source: string;
  raw_text: string;
  parsed: Record<string, unknown>;
}

export interface IntegrationListResponse {
  integrations: StoreIntegration[];
}

export async function apiPost<T = unknown>(path: string, body: unknown): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: controller.signal,
  }).finally(() => clearTimeout(timeout));
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function apiGet<T = unknown>(path: string): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  const res = await fetch(`${API_BASE}${path}`, { signal: controller.signal }).finally(() => clearTimeout(timeout));
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function apiPatch<T = unknown>(path: string, body: unknown): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: controller.signal,
  }).finally(() => clearTimeout(timeout));
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function apiPut<T = unknown>(path: string, body: unknown): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: controller.signal,
  }).finally(() => clearTimeout(timeout));
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(typeof payload?.detail === "string" ? payload.detail : `API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

export async function apiDelete(path: string): Promise<{ success: boolean }> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    signal: controller.signal,
  }).finally(() => clearTimeout(timeout));
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function apiStream(
  path: string,
  body: unknown,
  onChunk: (text: string) => void,
  onToolStart?: (name: string, id: string) => void,
  onToolEnd?: (name: string, output: string) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.trim()) continue;
      const match = line.match(/^[02]:/);
      if (!match) continue;
      try {
        const data = JSON.parse(line.slice(2));
        if (match[0] === "0") {
          onChunk(data as string);
        } else if (Array.isArray(data) && data[0]) {
          const d = data[0];
          if (d.toolName && d.output) onToolEnd?.(d.toolName, d.output);
          else if (d.toolName) onToolStart?.(d.toolName, d.toolCallId || "");
        }
      } catch { /* skip malformed */ }
    }
  }
}

export async function checkBackend(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

export function getOperationSummary(projectId = DEFAULT_PROJECT_ID, days = 7) {
  return apiGet<OperationSummary>(`/api/projects/${projectId}/operations/summary?days=${days}`);
}

export function getBusinessFacts(projectId = DEFAULT_PROJECT_ID, reviewStatus?: string) {
  const query = reviewStatus ? `?review_status=${encodeURIComponent(reviewStatus)}` : "";
  return apiGet<{ facts: BusinessFact[]; total: number }>(`/api/projects/${projectId}/business-facts${query}`);
}

export function updateBusinessFact(factId: string, patch: Partial<BusinessFact>, projectId = DEFAULT_PROJECT_ID) {
  return apiPatch<{ success: boolean; fact: BusinessFact }>(`/api/projects/${projectId}/business-facts/${factId}`, patch);
}

export function confirmBusinessFact(factId: string, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; fact: BusinessFact }>(`/api/projects/${projectId}/business-facts/${factId}/confirm`, {});
}

export function rejectBusinessFact(factId: string, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; fact: BusinessFact }>(`/api/projects/${projectId}/business-facts/${factId}/reject`, {});
}

export function markBusinessFact(factId: string, action: string, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; fact: BusinessFact }>(`/api/projects/${projectId}/business-facts/${factId}/mark`, { action });
}

export function getMoneyView(projectId = DEFAULT_PROJECT_ID, date?: string) {
  const query = date ? `?date=${encodeURIComponent(date)}` : "";
  return apiGet<MoneyView>(`/api/projects/${projectId}/money-view${query}`);
}

export interface DailyReviewCheck {
  date: string;
  can_close: boolean;
  close_status: "can_close" | "blocked" | "partial";
  confirmed_facts_count: number;
  pending_facts_count: number;
  posted_entries_count: number;
  duplicate_risks_count: number;
  low_confidence_inventory_count: number;
  missing_cost_fields: string[];
  blocking_reasons: string[];
  next_actions: string[];
  evidence_summary: {
    primary_evidence_count: number;
    supporting_evidence_count: number;
    total_sales_amount: number;
    sources: string[];
  };
  suggestions: string[];
}

export type DailyCloseCheck = DailyReviewCheck;

export function getDailyReviewCheck(projectId = DEFAULT_PROJECT_ID, date?: string) {
  const query = date ? `?date=${encodeURIComponent(date)}` : "";
  return apiGet<DailyReviewCheck>(`/api/projects/${projectId}/daily-review-check${query}`);
}

export function getDailyCloseCheck(projectId = DEFAULT_PROJECT_ID, date?: string) {
  const query = date ? `?date=${encodeURIComponent(date)}` : "";
  return apiGet<DailyCloseCheck>(`/api/projects/${projectId}/daily-close-check${query}`);
}

export function getFirstStageInventory(projectId = DEFAULT_PROJECT_ID, date?: string) {
  const query = date ? `?date=${encodeURIComponent(date)}` : "";
  return apiGet<FirstStageInventory>(`/api/projects/${projectId}/first-stage-inventory${query}`);
}

export function getTodayOperatingCard(projectId = DEFAULT_PROJECT_ID, date?: string) {
  const query = date ? `?date=${encodeURIComponent(date)}` : "";
  return apiGet<TodayOperatingCard>(`/api/projects/${projectId}/today-operating-card${query}`);
}

export function getCostQuestion(question = "一盒 6 粒章鱼烧成本是多少？", projectId = DEFAULT_PROJECT_ID) {
  return apiGet<CostQuestionAnswer>(`/api/projects/${projectId}/cost-question?question=${encodeURIComponent(question)}`);
}

export function getOperations(projectId = DEFAULT_PROJECT_ID, days = 30) {
  return apiGet<OperationListResponse>(`/api/projects/${projectId}/operations?days=${days}`);
}

export function getUtilities(projectId = DEFAULT_PROJECT_ID) {
  return apiGet<{ records: UtilityRecord[] }>(`/api/projects/${projectId}/utilities`);
}

export function updateUtility(record: UtilityRecord, projectId = DEFAULT_PROJECT_ID) {
  return apiPut<{ success: boolean; record: UtilityRecord; records: UtilityRecord[] }>(
    `/api/projects/${projectId}/utilities/${record.month}`,
    record,
  );
}

export function getProjectCockpit(projectId = DEFAULT_PROJECT_ID, days = 7) {
  return apiGet<ProjectCockpit>(`/api/projects/${projectId}/cockpit?days=${days}`);
}

export function addOperation(entry: DailyOperationEntry, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; entry: DailyOperationEntry; summary: OperationSummary }>(
    `/api/projects/${projectId}/operations`,
    entry,
  );
}

export function createProjectTask(action: CockpitAction, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; task: CockpitAction; cockpit: ProjectCockpit }>(
    `/api/projects/${projectId}/tasks`,
    {
      id: action.task_id,
      title: action.title,
      target: action.target,
      priority: action.priority,
      source: action.source,
      status: action.status && action.status !== "pending" ? action.status : "todo",
    },
  );
}

export function updateProjectTask(taskId: string, patch: Partial<CockpitAction>, projectId = DEFAULT_PROJECT_ID) {
  return fetch(`${API_BASE}/api/projects/${projectId}/tasks/${taskId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  }).then(async (res) => {
    if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
    return res.json() as Promise<{ success: boolean; task: CockpitAction; cockpit: ProjectCockpit }>;
  });
}

export function getIntegrations(projectId = DEFAULT_PROJECT_ID) {
  return apiGet<IntegrationListResponse>(`/api/projects/${projectId}/integrations`);
}

export function createDeliveryImport(payload: DeliveryImportPayload, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; import: Record<string, unknown>; imports: Record<string, unknown>[] }>(
    `/api/projects/${projectId}/delivery-imports`,
    payload,
  );
}

export interface RecognizeField {
  key: string;
  label: string;
  value: number | string;
  confidence: "high" | "medium" | "low";
}

export interface DocumentFact {
  label: string;
  value: string;
  confidence: "high" | "medium" | "low";
  evidence: string;
}

export interface RiskFlag {
  level: "high" | "medium" | "low";
  title: string;
  detail: string;
}

export interface StructuredArtifact {
  schema_version?: "capture_artifact_v1";
  source_type?: string;
  document_class?: string;
  review_status?: "needs_human_review" | "confirmed" | string;
  write_targets?: string[];
  confidence_summary?: {
    overall?: "high" | "medium" | "low";
    ocr?: "high" | "medium" | "low";
    business_mapping?: "high" | "medium" | "low";
  };
  canonical_sections?: {
    facts?: DocumentFact[];
    line_items?: Array<Record<string, unknown>>;
    checks?: string[];
    risks?: RiskFlag[];
    manual_review?: Array<Record<string, unknown>>;
    ai_next_actions?: string[];
  };
  write_payloads?: {
    sop_draft?: {
      category?: string;
      title?: string;
      source?: string;
      review_cycle_days?: number;
      steps?: Record<string, unknown>[];
    };
    purchase_order?: {
      date?: string;
      supplier?: string;
      items?: PurchaseItemCapture[];
    };
  };
  type?: string;
  title?: string;
  confidence?: "high" | "medium" | "low";
  summary?: string;
  facts?: DocumentFact[];
  risks?: RiskFlag[];
  items?: Array<Record<string, unknown>>;
  recipes?: Array<Record<string, unknown>>;
  checklist?: string[];
  quality_checks?: string[];
  required_manual_fields?: Array<Record<string, unknown>>;
  suggested_sop?: {
    category?: string;
    title?: string;
    source?: string;
    review_cycle_days?: number;
    steps?: Record<string, unknown>[];
  };
  ai_next_actions?: string[];
}

export interface RecognizeResponse {
  success: boolean;
  source_type: string;
  source_platform?: "meituan" | "taobao_flash" | "douyin" | "keyun" | "manual" | "unknown";
  capture_kind?: "operation" | "document" | "unknown";
  fields: RecognizeField[];
  document_facts?: DocumentFact[];
  risk_flags?: RiskFlag[];
  structured_artifact?: StructuredArtifact;
  recommended_destination?: string;
  can_write_operation?: boolean;
  raw_text: string;
  parse_error?: string;
}

export async function recognizeCapture(file: File): Promise<RecognizeResponse> {
  const formData = new FormData();
  formData.append("image", file);

  const controller = new AbortController();
  // 本地视觉模型首次加载可能接近 30 秒；给识别留出明确余量。
  const timeout = setTimeout(() => controller.abort(), 150000);

  const res = await fetch(`${API_BASE}/api/capture/recognize`, {
    method: "POST",
    body: formData,
    signal: controller.signal,
  }).finally(() => clearTimeout(timeout));

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body?.detail;
    if (typeof detail === "object" && detail?.code === "model_no_vision") {
      throw new Error(detail.message || "模型不支持图片识别");
    }
    throw new Error(typeof detail === "string" ? detail : `识别失败 (${res.status})`);
  }

  return res.json() as Promise<RecognizeResponse>;
}

export interface SpeechTranscription {
  success: boolean;
  text: string;
  duration_seconds: number;
  review_status: "needs_human_review";
  model: string;
}

export async function transcribeSpeech(audio: Blob): Promise<SpeechTranscription> {
  const formData = new FormData();
  formData.append("audio", audio, `语音录入-${Date.now()}.webm`);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120000);
  const res = await fetch(`${API_BASE}/api/speech/transcribe`, {
    method: "POST",
    body: formData,
    signal: controller.signal,
  }).finally(() => clearTimeout(timeout));
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(typeof payload?.detail === "string" ? payload.detail : `语音转写失败 (${res.status})`);
  }
  return res.json() as Promise<SpeechTranscription>;
}

// 模型路由状态
export interface ModelRouteInfo {
  agent: string;
  capability: string;
  provider: string;
  model: string;
  base_url: string | null;
  configured: boolean;
  free: boolean;
  notes: string;
}

export interface ModelRoutingState {
  routes: ModelRouteInfo[];
  intake_pipelines: {
    text: string[];
    image: string[];
    speech: string[];
  };
}

export function getModelRoutingState() {
  return apiGet<ModelRoutingState>("/api/model-routing");
}

// 录入审计日志
export interface CaptureAuditLogItem {
  id: string;
  timestamp: number;
  source_type: string;
  file_name: string;
  capture_kind: string;
  recognized_fields: Array<{ key: string; value: number | string }>;
  human_modified_fields: string[];
  review_status: string;
  write_target: string;
  date?: string;
  error_message?: string;
}

export function getCaptureAuditLog(projectId = DEFAULT_PROJECT_ID, limit = 50) {
  return apiGet<{ logs: CaptureAuditLogItem[]; total: number }>(
    `/api/projects/${projectId}/capture-audit-log?limit=${limit}`,
  );
}

export function confirmCaptureAudit(payload: {
  file_name: string;
  source_type: string;
  capture_kind: string;
  recognized_fields: Array<{ key: string; value: number | string }>;
  human_modified_fields?: string[];
  write_target: string;
  date?: string;
}, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean }>(`/api/capture/confirm/${projectId}`, payload);
}

// V2 Case Workspace
export async function getCaseWorkspace(caseId = DEFAULT_PROJECT_ID) {
  return apiGet<{
    project_name?: string;
    current_phase?: string;
    signability?: number;
    gates?: Array<{ id: string; label: string; status: string; emoji: string; why: string }>;
    blocker?: string;
    evidence?: Array<{ claim: string; source: string; ok: boolean }>;
    missions?: Array<{ id: string; title: string; done: boolean }>;
    next_action?: { next_best_action: string; next_action_why: string; blocker_title: string };
  }>(`/api/v2/cases/${caseId}/workspace`);
}

// ── 门店资料箱 ──

export interface StoreDocument {
  id: string;
  title: string;
  doc_type: string;
  tags: string[];
  source: string;
  file_ref: string;
  status: string;
  parties: string[];
  sign_date: string;
  expiry_date: string;
  key_terms: string[];
  extracted_fields: Record<string, unknown>;
  risk_flags: string[];
  related_to: Record<string, string>;
  notes: string;
  created_at: number;
  updated_at: number;
}

export function getDocuments(projectId = DEFAULT_PROJECT_ID, params?: { doc_type?: string; keyword?: string; expiring_days?: number }) {
  const search = new URLSearchParams();
  if (params?.doc_type) search.set("doc_type", params.doc_type);
  if (params?.keyword) search.set("keyword", params.keyword);
  if (params?.expiring_days != null) search.set("expiring_days", String(params.expiring_days));
  const query = search.toString();
  return apiGet<{ documents: StoreDocument[]; summary: { total: number; by_type: Record<string, number>; expiring_soon: number } }>(
    `/api/projects/${projectId}/documents${query ? `?${query}` : ""}`,
  );
}

export function createDocument(doc: Partial<StoreDocument> & { title: string }, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; document: StoreDocument }>(`/api/projects/${projectId}/documents`, doc);
}

export function updateDocument(docId: string, patch: Partial<StoreDocument>, projectId = DEFAULT_PROJECT_ID) {
  return apiPatch<{ success: boolean; document: StoreDocument }>(`/api/projects/${projectId}/documents/${docId}`, patch);
}

export function deleteDocument(docId: string, projectId = DEFAULT_PROJECT_ID) {
  return apiDelete(`/api/projects/${projectId}/documents/${docId}`);
}

// ── SKU 与进货 ──

export interface SkuItem {
  id: string;
  name: string;
  category: string;
  unit: string;
  safety_stock: number;
  current_stock: number;
  unit_cost: number;
  supplier: string;
  batch_cycle_days: number;
  consumption_per_day: number;
  last_purchase_date: string;
  next_purchase_est: string;
  status: string;
  notes: string;
  hq_code: string;
  hq_name: string;
  hq_image: string;
  hq_category: string;
  standard_unit: string;
  spec: string;
  pack_quantity: number;
  stock_by_location: Partial<Record<"store" | "warehouse" | "freezer" | "unallocated", number>>;
  count_units: Array<{ unit: string; factor: number; label?: string }>;
  tracking_mode: "open_pack" | "periodic_count";
  display_unit: string;
  store_target_days: number;
  supplier_lead_days: number;
  active: boolean;
}

export interface SkuAlias {
  id: string;
  sku_id: string;
  alias: string;
  supplier: string;
  unit_conversion: number;
  alias_unit: string;
  source: string;
  usage_count: number;
  created_at: number;
  updated_at: number;
}

export type MatchType = "manual" | "alias" | "fuzzy" | "none" | "ignored";

export interface PurchaseMatchDetail {
  index: number;
  name: string;
  matched: boolean;
  ignored: boolean;
  match_type: MatchType;
  sku_id: string;
  sku_name: string;
  alias_id: string;
  quantity: number;
  original_quantity: number;
  unit_cost: number;
  unit_conversion: number;
  stock_after: number | null;
}

export interface PurchaseWriteResult {
  success: boolean;
  purchase_id: string;
  purchase_date: string;
  supplier: string;
  total_items: number;
  matched_count: number;
  unmatched_count: number;
  ignored_count: number;
  total_amount: number;
  matched_amount: number;
  match_details: PurchaseMatchDetail[];
}

export interface PurchaseItem {
  sku_id: string;
  name: string;
  quantity: number;
  unit_cost: number;
  subtotal: number;
}

export interface PurchaseRecord {
  id: string;
  date: string;
  supplier: string;
  items: PurchaseItem[];
  total_cost: number;
  payment_status: string;
  paid_amount: number;
  fulfillment_status: "ordered" | "received";
  external_order_id: string;
  location: "store" | "warehouse" | "freezer";
  received_at: string;
  notes: string;
  created_at: number;
}

export interface ForecastItem {
  sku_id: string;
  name: string;
  category: string;
  unit: string;
  current_stock: number;
  store_stock: number;
  warehouse_stock: number;
  unallocated_stock: number;
  safety_stock: number;
  consumption_per_day: number;
  observed_daily_consumption: number;
  days_remaining: number | null;
  stockout_date: string | null;
  recommend_qty: number | null;
  recommend_amount: number | null;
  risk_level: "high" | "medium" | "low" | "unknown";
  action: "urgent" | "recommend" | "ok" | "not_enough_data";
  estimated_date: string;
}

export function getSkus(projectId = DEFAULT_PROJECT_ID, category?: string) {
  const query = category ? `?category=${encodeURIComponent(category)}` : "";
  return apiGet<{ skus: SkuItem[]; categories: string[]; total: number }>(`/api/projects/${projectId}/skus${query}`);
}

export function createSku(sku: Partial<SkuItem> & { name: string }, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; sku: SkuItem }>(`/api/projects/${projectId}/skus`, sku);
}

export function updateSku(skuId: string, patch: Partial<SkuItem>, projectId = DEFAULT_PROJECT_ID) {
  return apiPatch<{ success: boolean; sku: SkuItem }>(`/api/projects/${projectId}/skus/${skuId}`, patch);
}

export function deleteSku(skuId: string, projectId = DEFAULT_PROJECT_ID) {
  return apiDelete(`/api/projects/${projectId}/skus/${skuId}`);
}

export function getForecast(projectId = DEFAULT_PROJECT_ID) {
  return apiGet<{ forecast: ForecastItem[]; total_skus: number }>(`/api/projects/${projectId}/skus/forecast`);
}

export function createPurchase(purchase: {
  date: string;
  supplier?: string;
  external_order_id?: string;
  paid_amount?: number;
  items: { sku_id: string; name?: string; quantity: number; unit_cost: number }[];
  payment_status?: string;
  notes?: string;
}, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; purchase: PurchaseRecord; forecast: ForecastItem[] }>(`/api/projects/${projectId}/skus/purchase`, purchase);
}

export function getPurchases(projectId = DEFAULT_PROJECT_ID, limit = 30) {
  return apiGet<{ purchases: PurchaseRecord[]; total: number }>(`/api/projects/${projectId}/skus/purchases?limit=${limit}`);
}

export function receivePurchase(purchaseId: string, payload: {
  date: string;
  items: Array<{
    sku_id: string;
    received_quantity: number;
    allocations: Partial<Record<"store" | "warehouse" | "freezer", number>>;
  }>;
  source?: string;
  notes?: string;
}, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; purchase: PurchaseRecord; summary: InventorySummary; forecast: ForecastItem[] }>(
    `/api/projects/${projectId}/skus/purchases/${purchaseId}/receive`,
    payload,
  );
}

export interface InventoryAgentAction {
  id: string;
  level: "important" | "warning" | "info";
  title: string;
  reason: string;
  action: string;
  confidence: "high" | "medium" | "low";
  sku_id?: string;
  suggested_quantity?: number;
}

export interface InventorySummary {
  locations: Record<"store" | "warehouse" | "freezer" | "unallocated", { label: string; quantity_total: number }>;
  sku_count: number;
  allocated_skus: number;
  unallocated_skus: number;
  inventory_value: number;
  last_count: InventoryCountRecord | null;
  last_usage_log: InventoryUsageLog | null;
  work_in_process: {
    open_batches: number;
    items: ProductionBatch[];
  };
  actions: InventoryAgentAction[];
  data_status: "calibrating" | "ready";
}

export interface ProductionBatch {
  id: string;
  date: string;
  name: string;
  location: "store" | "warehouse";
  inputs: Array<{ sku_id: string; name: string; quantity: number; unit: string }>;
  output_quantity: number;
  output_unit: string;
  remaining_quantity: number;
  used_quantity: number;
  waste_quantity: number;
  pan_cycle_minutes: number;
  actual_pan_cycles: number;
  status: "open" | "closed";
  source: string;
  notes: string;
  created_at: number;
  closed_at: number;
}

export function getProductionBatches(projectId = DEFAULT_PROJECT_ID, limit = 60) {
  return apiGet<{ batches: ProductionBatch[]; total: number }>(
    `/api/projects/${projectId}/production-batches?limit=${limit}`,
  );
}

export function createProductionBatch(payload: {
  date: string;
  name: string;
  location?: "store" | "warehouse";
  inputs: Array<{ sku_id: string; quantity: number; name?: string; unit?: string }>;
  output_quantity: number;
  output_unit: string;
  pan_cycle_minutes?: number;
  source?: string;
  notes?: string;
}, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; batch: ProductionBatch; summary: InventorySummary }>(
    `/api/projects/${projectId}/production-batches`,
    payload,
  );
}

export function closeProductionBatch(batchId: string, payload: {
  used_quantity: number;
  waste_quantity?: number;
  actual_pan_cycles?: number;
  notes?: string;
}, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; batch: ProductionBatch; summary: InventorySummary }>(
    `/api/projects/${projectId}/production-batches/${batchId}/close`,
    payload,
  );
}

export interface InventoryUsageItem {
  sku_id: string;
  name: string;
  quantity: number;
  unit: string;
}

export interface InventoryUsageLog {
  id: string;
  date: string;
  location: "store" | "warehouse" | "freezer";
  items: InventoryUsageItem[];
  source: string;
  notes: string;
  created_at: number;
}

export interface InventoryCountLine {
  sku_id: string;
  name: string;
  unit: string;
  expected_quantity: number;
  counted_quantity: number;
  variance_quantity: number;
  variance_rate: number;
  components: Array<{ unit: string; quantity: number; factor: number }>;
  notes: string;
}

export interface InventoryCountRecord {
  id: string;
  date: string;
  location: "store" | "warehouse" | "freezer";
  count_type: "weekly" | "biweekly" | "monthly" | "spot";
  lines: InventoryCountLine[];
  source: string;
  notes: string;
  created_at: number;
}

export interface InventoryEvent {
  id: string;
  date: string;
  event_type: "receipt" | "transfer" | "usage" | "count_adjustment";
  sku_id: string;
  sku_name: string;
  quantity: number;
  from_location: string;
  to_location: string;
  source: string;
  notes: string;
  metadata: Record<string, unknown>;
  created_at: number;
}

export interface InventoryVariance {
  rows: Array<InventoryCountLine & {
    count_id: string;
    date: string;
    location: string;
    location_label: string;
    variance_value: number;
  }>;
  count_sessions: number;
  value_accuracy: number | null;
  absolute_variance_value: number;
  method: string;
}

export interface ConsumptionVarianceRow {
  sku_id: string;
  sku_name: string;
  base_unit: string;
  period_start: string;
  period_end: string;
  opening_stock: number;
  purchases: number;
  usage_logged: number;
  waste_logged: number;
  closing_stock: number;
  actual_consumption: number | null;
  theoretical_consumption: number | null;
  variance_quantity: number | null;
  variance_rate: number | null;
  variance_value: number;
  verification_status: "ok" | "no_bom" | "no_sales" | "over_consumption" | "under_consumption" | "missing_opening_count" | "missing_count";
  notes: string;
}

export interface ConsumptionVariance {
  period_start: string;
  period_end: string;
  rows: ConsumptionVarianceRow[];
  total_actual_consumption: number;
  total_theoretical_consumption: number | null;
  total_variance_value: number;
  verification_coverage: number;
  method: string;
}

export function getInventorySummary(projectId = DEFAULT_PROJECT_ID) {
  return apiGet<InventorySummary>(`/api/projects/${projectId}/skus/inventory-summary`);
}

export function getInventoryEvents(projectId = DEFAULT_PROJECT_ID, limit = 100) {
  return apiGet<{ events: InventoryEvent[]; total: number }>(`/api/projects/${projectId}/skus/inventory-events?limit=${limit}`);
}

export function createInventoryTransfer(payload: {
  date: string;
  from_location: "store" | "warehouse" | "freezer" | "unallocated";
  to_location: "store" | "warehouse" | "freezer";
  items: Array<{ sku_id: string; quantity: number }>;
  source?: string;
  notes?: string;
}, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; events: InventoryEvent[]; summary: InventorySummary }>(
    `/api/projects/${projectId}/skus/transfer`,
    payload,
  );
}

export function getInventoryUsageLogs(projectId = DEFAULT_PROJECT_ID, limit = 60) {
  return apiGet<{ logs: InventoryUsageLog[]; total: number }>(`/api/projects/${projectId}/skus/usage-logs?limit=${limit}`);
}

export function createInventoryUsage(payload: {
  date: string;
  location?: "store" | "warehouse";
  items: Array<{ sku_id: string; quantity: number; name?: string; unit?: string }>;
  source?: string;
  notes?: string;
}, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; log: InventoryUsageLog; summary: InventorySummary }>(
    `/api/projects/${projectId}/skus/usage-logs`,
    payload,
  );
}

export function getInventoryCounts(projectId = DEFAULT_PROJECT_ID, limit = 30) {
  return apiGet<{ counts: InventoryCountRecord[]; total: number }>(`/api/projects/${projectId}/skus/counts?limit=${limit}`);
}

export function createInventoryCount(payload: {
  date: string;
  location: "store" | "warehouse" | "freezer";
  count_type: "weekly" | "biweekly" | "monthly" | "spot";
  lines: Array<{ sku_id: string; counted_quantity: number; components?: Array<Record<string, unknown>>; notes?: string }>;
  source?: string;
  notes?: string;
}, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; count: InventoryCountRecord; summary: InventorySummary; variance: InventoryVariance }>(
    `/api/projects/${projectId}/skus/counts`,
    payload,
  );
}

export function getInventoryVariance(projectId = DEFAULT_PROJECT_ID, limit = 12) {
  return apiGet<InventoryVariance>(`/api/projects/${projectId}/skus/variance-analysis?limit=${limit}`);
}

export function getConsumptionVariance(
  projectId = DEFAULT_PROJECT_ID,
  periodStart: string,
  periodEnd: string,
) {
  return apiGet<ConsumptionVariance>(
    `/api/projects/${projectId}/skus/consumption-variance?period_start=${periodStart}&period_end=${periodEnd}`,
  );
}

// ── SOP 文档库 ──

export interface SopDocument {
  id: string;
  category: string;
  title: string;
  version: number;
  status: string;
  source: string;
  description: string;
  steps: Array<{ order: number; title: string; description: string; tools: string[]; time_estimate: string; is_critical: boolean }>;
  related_sku_ids: string[];
  related_training_skills: string[];
  last_reviewed: string;
  review_cycle_days: number;
  notes: string;
}

export interface SopSummary {
  total: number;
  by_category: Record<string, number>;
  by_status: Record<string, number>;
  stale: number;
}

export function getSops(projectId = DEFAULT_PROJECT_ID, params?: { category?: string; status?: string; keyword?: string; stale?: boolean }) {
  const search = new URLSearchParams();
  if (params?.category) search.set("category", params.category);
  if (params?.status) search.set("status", params.status);
  if (params?.keyword) search.set("keyword", params.keyword);
  if (params?.stale) search.set("stale", "true");
  const query = search.toString();
  return apiGet<{ documents: SopDocument[]; summary: SopSummary }>(`/api/projects/${projectId}/sops${query ? `?${query}` : ""}`);
}

export function createSop(sop: { title: string; category: string; source?: string; description?: string; steps?: Record<string, unknown>[] }, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; document: SopDocument }>(`/api/projects/${projectId}/sops`, sop);
}

export function updateSop(sopId: string, patch: Partial<SopDocument> & { bump_version?: boolean }, projectId = DEFAULT_PROJECT_ID) {
  return apiPatch<{ success: boolean; document: SopDocument }>(`/api/projects/${projectId}/sops/${sopId}`, patch);
}

export function deleteSop(sopId: string, projectId = DEFAULT_PROJECT_ID) {
  return apiDelete(`/api/projects/${projectId}/sops/${sopId}`);
}

// ── 工时工资 ──

export interface StaffMember {
  id: string;
  name: string;
  role: string;
  phone: string;
  health_cert_expiry: string;
  skills: string[];
  hourly_wage: number;
  monthly_base: number;
  pay_type: "auto" | "hourly" | "monthly" | "owner";
  standard_monthly_work_days: number;
  overtime_multiplier: number;
  hire_date: string;
  status: string;
  notes: string;
}

export interface WorkRecord {
  id: string;
  staff_id: string;
  date: string;
  shift: string;
  hours: number;
  overtime_hours: number;
  notes: string;
}

export interface WageDetail {
  staff_id: string;
  staff_name: string;
  year_month: string;
  work_days: number;
  total_hours: number;
  total_overtime: number;
  hourly_wage: number;
  monthly_base: number;
  pay_type: "hourly" | "monthly" | "owner";
  standard_monthly_work_days: number;
  attendance_ratio: number;
  regular_pay: number;
  base_pay: number;
  overtime_pay: number;
  cost_basis: "attendance" | "owner_opportunity_cost";
  total_wage: number;
  records: WorkRecord[];
}

export interface HealthCertAlert {
  staff_id: string;
  name: string;
  expiry_date: string;
  days_remaining: number;
}

export function getStaff(projectId = DEFAULT_PROJECT_ID) {
  return apiGet<{ staff: StaffMember[]; count: number; health_cert_alerts: HealthCertAlert[] }>(`/api/projects/${projectId}/labor/staff`);
}

export function createStaff(staff: { name: string; role?: string; pay_type?: "auto" | "hourly" | "monthly" | "owner"; hourly_wage?: number; monthly_base?: number; standard_monthly_work_days?: number; overtime_multiplier?: number; health_cert_expiry?: string; skills?: string[]; phone?: string; hire_date?: string; notes?: string }, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; staff: StaffMember }>(`/api/projects/${projectId}/labor/staff`, staff);
}

export function updateStaff(staffId: string, patch: Partial<StaffMember>, projectId = DEFAULT_PROJECT_ID) {
  return apiPatch<{ success: boolean; staff: StaffMember }>(`/api/projects/${projectId}/labor/staff/${staffId}`, patch);
}

export function deleteStaff(staffId: string, projectId = DEFAULT_PROJECT_ID) {
  return apiDelete(`/api/projects/${projectId}/labor/staff/${staffId}`);
}

export function getWorkRecords(projectId = DEFAULT_PROJECT_ID, params?: { staff_id?: string; date_from?: string; date_to?: string; limit?: number }) {
  const search = new URLSearchParams();
  if (params?.staff_id) search.set("staff_id", params.staff_id);
  if (params?.date_from) search.set("date_from", params.date_from);
  if (params?.date_to) search.set("date_to", params.date_to);
  if (params?.limit) search.set("limit", String(params.limit));
  const query = search.toString();
  return apiGet<{ records: WorkRecord[]; count: number }>(`/api/projects/${projectId}/labor/records${query ? `?${query}` : ""}`);
}

export function createWorkRecord(record: { staff_id: string; date: string; shift?: string; hours?: number; overtime_hours?: number; notes?: string }, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; record: WorkRecord }>(`/api/projects/${projectId}/labor/records`, record);
}

export function getWageSummary(projectId = DEFAULT_PROJECT_ID, yearMonth: string) {
  return apiGet<{ year_month: string; staff_count: number; total_wage: number; breakdown: WageDetail[] }>(`/api/projects/${projectId}/labor/wages?year_month=${yearMonth}`);
}

export function finalizeWages(projectId = DEFAULT_PROJECT_ID, yearMonth: string) {
  return apiPost<{ success: boolean; year_month: string; total_wage: number; operation_days: number; daily_labor_allocated: number; breakdown: WageDetail[] }>(
    `/api/projects/${projectId}/labor/wages/finalize?year_month=${yearMonth}`,
    {},
  );
}

// ── 人工效率 ──

export interface LaborEfficiency {
  staff_count: number;
  revenue_per_staff: number;
  labor_per_order: number;
  labor_cost_rate: number;
  total_labor_estimate: number;
}

export function getLaborEfficiency(projectId: string, revenue: number, orders: number) {
  return apiGet<LaborEfficiency>(`/api/projects/${projectId}/labor/efficiency?revenue=${revenue}&orders=${orders}`);
}

// ── 周报月报 ──

export interface ReportFinding {
  level: "good" | "watch" | "risk" | "info";
  title: string;
  body: string;
  type?: string;
  target?: string;
}

export interface ReportSection {
  title: string;
  metrics: Record<string, unknown>;
}

export interface ReportAction {
  action: string;
  target: string;
  priority: "high" | "medium" | "low";
}

export interface Report {
  id: string;
  report_type: "weekly" | "monthly";
  period_start: string;
  period_end: string;
  generated_at: string;
  status: string;
  total_days: number;
  total_revenue: number;
  avg_daily_revenue: number;
  total_orders: number;
  avg_order_value: number;
  net_profit: number;
  food_cost_rate: number;
  labor_cost_rate: number;
  takeout_ratio: number;
  platform_fee_total: number;
  prev_revenue: number;
  revenue_change_pct: number;
  prev_net_profit: number;
  profit_change_pct: number;
  changes: Array<{ key: string; current: number; previous: number; change_pct: number }>;
  findings: ReportFinding[];
  sections: Record<string, ReportSection>;
  actions: ReportAction[];
  narrative: string;
}

export function getReports(projectId = DEFAULT_PROJECT_ID, reportType?: string, limit = 12) {
  const search = new URLSearchParams();
  if (reportType) search.set("report_type", reportType);
  search.set("limit", String(limit));
  return apiGet<{ reports: Report[]; count: number }>(`/api/projects/${projectId}/reports?${search.toString()}`);
}

export function generateReport(projectId = DEFAULT_PROJECT_ID, reportType: "weekly" | "monthly" = "weekly") {
  return apiPost<{ success: boolean; report: Report }>(`/api/projects/${projectId}/reports/generate?report_type=${reportType}`, {});
}

// ── 天气商圈 ──

export interface WeatherForecast {
  date: string;
  weekday: string;
  weather: "sunny" | "cloudy" | "overcast" | "light_rain" | "heavy_rain" | "thunderstorm" | "snow" | "fog";
  temp_high: number;
  temp_low: number;
  humidity: number;
  wind: string;
  is_weekend: boolean;
  tips: string[];
}

export interface LocalEvent {
  date: string;
  title: string;
  type: string;
  impact: string;
}

export interface WeatherResponse {
  city: string;
  district: string;
  location: string;
  source?: "open-meteo" | "fallback";
  current: { weather: string; temperature: number; temp_high: number; temp_low: number; humidity: number; wind: string; tips: string[] };
  forecast: WeatherForecast[];
  events: LocalEvent[];
  updated_at: string;
}

export function getWeather() {
  return apiGet<WeatherResponse>("/api/weather");
}

// ── 月度营收 ──

export interface MonthlyEntry {
  year: number;
  month: number;
  revenue: number | null;
  net_profit: number | null;
  last_year_profit: number;
  daily_avg: number | null;
  last_daily_avg: number;
  estimated_profit: number | null;
  yoy_pct: number | null;
  profit_yoy_pct: number | null;
  days_in_month: number;
  revenue_review_status?: string;
  profit_review_status?: string;
}

export interface MonthlyOperatingRecord {
  year: number;
  month: number;
  revenue?: number | null;
  net_profit?: number | null;
  review_status?: "confirmed" | "needs_human_review";
  source_type?: string;
  source_file_name?: string;
  source_raw_text?: string;
}

export interface MonthlySummary {
  months: MonthlyEntry[];
  entry_count: number;
  months_with_revenue: number;
  total_revenue: number;
  total_last_year: number;
  avg_monthly_revenue: number;
  avg_monthly_last: number;
  estimated_monthly_cost: number;
  rent: number;
  labor: number;
  utility_avg: number;
  wage_per_person: number;
  current_staff_count: number;
  previous_staff_count: number;
  ytd_revenue: number;
  ytd_last_profit: number;
  current_year: number | null;
  baseline_year: number | null;
  records: MonthlyOperatingRecord[];
}

export function getMonthly(projectId = DEFAULT_PROJECT_ID) {
  return apiGet<MonthlySummary>(`/api/projects/${projectId}/monthly`);
}

export interface MonthlyOperatingUpdate {
  entries: MonthlyOperatingRecord[];
  monthly_rent?: number;
  monthly_utility_min?: number;
  monthly_utility_max?: number;
  wage_per_person?: number;
  previous_staff_count?: number;
  current_staff_count?: number;
  owner_operates?: boolean;
}

export function updateMonthlyOperating(payload: MonthlyOperatingUpdate, projectId = DEFAULT_PROJECT_ID) {
  return apiPut<{ success: boolean; updated_periods: Array<{ year: number; month: number }>; summary: MonthlySummary }>(
    `/api/projects/${projectId}/monthly`,
    payload,
  );
}

export function importDeliveryCsv(file: File, projectId = DEFAULT_PROJECT_ID) {
  const formData = new FormData();
  formData.append("file", file);
  return apiPostFile<{ success: boolean; imported: number; skipped: number; strategy: string; summary: OperationSummary }>(`/api/projects/${projectId}/import-csv/confirm`, formData);
}

export interface CsvPreviewRow {
  date: string;
  revenue: number;
  orders: number;
  dine_in_revenue: number;
  dine_in_orders: number;
  delivery_revenue: number;
  delivery_orders: number;
  platform_fee: number;
  marketing_cost: number;
  packaging_cost: number;
  source_quality_score: string;
}

export interface CsvPreviewResponse {
  success: boolean;
  columns_detected: string[];
  source_platform: string;
  preview_rows: CsvPreviewRow[];
  total_rows: number;
  preview_count: number;
  warnings: string[];
  file_name: string;
}

export function previewDeliveryCsv(file: File, projectId = DEFAULT_PROJECT_ID) {
  const formData = new FormData();
  formData.append("file", file);
  return apiPostFile<CsvPreviewResponse>(`/api/projects/${projectId}/import-csv/preview`, formData);
}

export function confirmDeliveryCsv(file: File, strategy: string = "overwrite", projectId = DEFAULT_PROJECT_ID) {
  const formData = new FormData();
  formData.append("file", file);
  return apiPostFile<{ success: boolean; imported: number; skipped: number; strategy: string; summary: OperationSummary }>(`/api/projects/${projectId}/import-csv/confirm?strategy=${strategy}`, formData);
}

function apiPostFile<T>(url: string, body: FormData): Promise<T> {
  return fetch(`${API_BASE}${url}`, {
    method: "POST",
    body,
    signal: AbortSignal.timeout(30000),
  }).then(async (res) => {
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(text || res.statusText);
    }
    return res.json();
  });
}

// ── 进货单确认写入 ──

export interface PurchaseItemCapture {
  name: string;
  quantity: number;
  unit_cost: number;
  sku_id?: string;
  unit_conversion?: number;
  is_ignored?: boolean;
}

export interface PurchaseOrderCapture {
  date: string;
  supplier: string;
  items: PurchaseItemCapture[];
  file_name?: string;
  source_type?: string;
  human_modified_fields?: string[];
  auto_create_aliases?: boolean;
}

export function writePurchaseOrder(payload: PurchaseOrderCapture, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<PurchaseWriteResult>(`/api/projects/${projectId}/capture/purchase-order`, payload);
}

// ── SKU 别名映射 ──

export interface SkuAliasCreate {
  sku_id: string;
  alias: string;
  supplier: string;
  unit_conversion: number;
  alias_unit: string;
  source: string;
}

export interface SkuAliasUpdate {
  sku_id?: string;
  alias?: string;
  supplier?: string;
  unit_conversion?: number;
  alias_unit?: string;
  source?: string;
}

export function listSkuAliases(params?: { sku_id?: string; supplier?: string }, projectId = DEFAULT_PROJECT_ID) {
  const q = new URLSearchParams();
  if (params?.sku_id) q.set("sku_id", params.sku_id);
  if (params?.supplier) q.set("supplier", params.supplier);
  return apiGet<{ aliases: SkuAlias[]; total: number }>(`/api/projects/${projectId}/skus/aliases?${q.toString()}`);
}

export function createSkuAlias(data: SkuAliasCreate, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; alias: SkuAlias }>(`/api/projects/${projectId}/skus/aliases`, data);
}

export function updateSkuAlias(aliasId: string, data: SkuAliasUpdate, projectId = DEFAULT_PROJECT_ID) {
  return fetch(`${API_BASE}/api/projects/${projectId}/skus/aliases/${aliasId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }).then((r) => r.json());
}

export function deleteSkuAlias(aliasId: string, projectId = DEFAULT_PROJECT_ID) {
  return apiDelete(`/api/projects/${projectId}/skus/aliases/${aliasId}`);
}

export function batchMatchSkuAliases(items: Array<{ name: string; supplier: string }>, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ results: Array<{
    name: string;
    supplier: string;
    matched: boolean;
    sku_id: string;
    sku_name: string;
    alias_id: string;
    unit_conversion: number;
    match_type: string;
  }> }>(`/api/projects/${projectId}/skus/aliases/batch-match`, { items });
}

// ── 考勤工时确认写入 ──

export interface WorkRecordCapture {
  staff_name: string;
  date: string;
  hours: number;
  shift: string;
  overtime_hours: number;
}

export interface WorkRecordsWriteResult {
  success: boolean;
  written_count: number;
  records: Array<Record<string, unknown>>;
}

export function writeWorkRecords(records: WorkRecordCapture[], projectId = DEFAULT_PROJECT_ID) {
  return apiPost<WorkRecordsWriteResult>(`/api/projects/${projectId}/capture/work-records`, records);
}

// ── 语音结构化字段 ──

export interface VoiceExtractedFields {
  fields: {
    revenue?: number;
    delivery_revenue?: number;
    orders?: number;
    food_cost?: number;
    date?: string;
  };
  confidence_fields: string[];
  has_structured_data: boolean;
  message: string;
}

export function getVoiceExtractedFields(text: string): VoiceExtractedFields | null {
  void text;
  // 前端通过 speech/transcribe 接口获取，这里定义类型供其他地方使用
  return null;
}

// ── 首页智能解读 ──

export interface TodayInsight {
  insight: string;
  health_status: "good" | "watch" | "risk";
  key_concern: string | null;
}

export function getTodayInsight(projectId = DEFAULT_PROJECT_ID): Promise<TodayInsight> {
  return apiGet<TodayInsight>(`/api/projects/${projectId}/analyze/today-insight`);
}

// ── 保本点分析 ──

export interface BreakEvenAnalysis {
  days: number;
  total_revenue: number;
  daily_revenue: number;
  fixed_cost: number;
  variable_cost: number;
  daily_fixed_cost: number;
  monthly_fixed_cost: number;
  variable_cost_rate: number;
  contribution_margin_rate: number;
  monthly_breakeven_revenue: number | null;
  daily_breakeven_revenue: number | null;
  is_profitable: boolean;
  gap_to_breakeven: number | null;
  breakeven_pct: number | null;
}

export function getBreakEvenAnalysis(projectId = DEFAULT_PROJECT_ID, days = 30): Promise<BreakEvenAnalysis> {
  return apiGet<BreakEvenAnalysis>(`/api/projects/${projectId}/analyze/break-even?days=${days}`);
}

export interface AmapGeocodeResponse {
  formatted_address: string;
  province: string;
  city: string;
  district: string;
  location: string;
  level: string;
}

export interface AmapLocationInfoResponse {
  geocode: AmapGeocodeResponse;
  competitors_count: number;
  nearby_anchors: Array<{ name: string; type: string; distance: number | null }>;
}

export function getAmapGeocode(address: string, city?: string) {
  return apiPost<AmapGeocodeResponse>("/api/amap/geocode", { address, city });
}

export function getAmapLocationInfo(address: string, city?: string) {
  return apiPost<AmapLocationInfoResponse>("/api/amap/location-info", { address, city });
}

export { API_BASE };
