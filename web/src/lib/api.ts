const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const DEFAULT_PROJECT_ID = "xinyu-hengtai-dakou";

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
  takeout_ratio: number;
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

export interface IntegrationListResponse {
  integrations: StoreIntegration[];
}

export async function apiPost<T = unknown>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function apiGet<T = unknown>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
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

export { API_BASE };
