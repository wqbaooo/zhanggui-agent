const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const DEFAULT_PROJECT_ID = "demo-project";
const API_TIMEOUT_MS = 8000;

export interface DailyOperationEntry {
  date: string;
  revenue: number;
  orders: number;
  food_cost: number;
  labor: number;
  rent_allocated: number;
  utility: number;
  other_cost: number;
  takeout_orders: number;
  platform_fee: number;
  marketing_cost: number;
  inventory_loss: number;
  bad_reviews?: number;
  notes?: string;
}

export interface OperationSummary {
  days: number;
  entry_count: number;
  total_revenue: number;
  total_orders: number;
  avg_order_value: number;
  total_cost: number;
  net_profit: number;
  food_cost_rate: number;
  labor_cost_rate?: number;
  prime_cost_rate?: number;
  takeout_ratio: number;
  bad_review_rate?: number;
  latest_entry: DailyOperationEntry | null;
  alerts: Array<{ level: string; message: string }>;
}

export interface OperationListResponse {
  entries: DailyOperationEntry[];
  summary: OperationSummary;
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

export function getOperations(projectId = DEFAULT_PROJECT_ID, days = 30) {
  return apiGet<OperationListResponse>(`/api/projects/${projectId}/operations?days=${days}`);
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

export interface RecognizeResponse {
  success: boolean;
  source_type: string;
  capture_kind?: "operation" | "document" | "unknown";
  fields: RecognizeField[];
  document_facts?: DocumentFact[];
  risk_flags?: RiskFlag[];
  recommended_destination?: string;
  can_write_operation?: boolean;
  raw_text: string;
  parse_error?: string;
}

export async function recognizeCapture(file: File): Promise<RecognizeResponse> {
  const formData = new FormData();
  formData.append("image", file);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);

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
  notes: string;
  created_at: number;
}

export interface ForecastItem {
  sku_id: string;
  name: string;
  category: string;
  unit: string;
  current_stock: number;
  safety_stock: number;
  consumption_per_day: number;
  days_remaining: number | null;
  recommend_qty: number | null;
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

export function createPurchase(purchase: { date: string; supplier?: string; items: { sku_id: string; name?: string; quantity: number; unit_cost: number }[]; payment_status?: string; notes?: string }, projectId = DEFAULT_PROJECT_ID) {
  return apiPost<{ success: boolean; purchase: PurchaseRecord; forecast: ForecastItem[] }>(`/api/projects/${projectId}/skus/purchase`, purchase);
}

export function getPurchases(projectId = DEFAULT_PROJECT_ID, limit = 30) {
  return apiGet<{ purchases: PurchaseRecord[]; total: number }>(`/api/projects/${projectId}/skus/purchases?limit=${limit}`);
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

export function createStaff(staff: { name: string; role?: string; hourly_wage?: number; monthly_base?: number; health_cert_expiry?: string; skills?: string[]; phone?: string; hire_date?: string; notes?: string }, projectId = DEFAULT_PROJECT_ID) {
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
  current: { weather: string; temperature: number; temp_high: number; temp_low: number; humidity: number; wind: string; tips: string[] };
  forecast: WeatherForecast[];
  events: LocalEvent[];
  updated_at: string;
}

export function getWeather() {
  return apiGet<WeatherResponse>("/api/weather");
}

export { API_BASE };
