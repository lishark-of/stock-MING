export type ApiEnvelope<T = unknown> = {
  ok: boolean;
  data: T;
  error: string | null;
  call_ledger: Array<Record<string, unknown>>;
  warnings: string[];
};

export type TaskRecord = {
  task_id: string;
  task_type: string;
  status: "pending" | "running" | "success" | "failed" | "cancelled";
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
  progress: number;
  current_step: string;
  error_message_safe?: string;
  output_packet_key: string;
  call_ledger?: Array<Record<string, unknown>>;
  status_history?: Array<Record<string, unknown>>;
  backend?: string;
  external_calls_triggered?: boolean;
  tushare_called?: boolean;
  deepseek_called?: boolean;
  github_called?: boolean;
  does_not_execute_trades?: boolean;
  does_not_modify_strategy_action?: boolean;
  warnings: string[];
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8710";

async function request<T>(path: string, init?: RequestInit): Promise<ApiEnvelope<T>> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!res.ok) {
    return { ok: false, data: {} as T, error: `HTTP ${res.status}`, call_ledger: [], warnings: [] };
  }
  return (await res.json()) as ApiEnvelope<T>;
}

export function getHealth() {
  return request<Record<string, unknown>>("/health");
}

export function getPackets() {
  return request<Record<string, unknown>>("/api/packets");
}

export function getPacket(packetKey: string) {
  return request<Record<string, unknown>>(`/api/packets/${encodeURIComponent(packetKey)}`);
}

export function getMigrationStatus() {
  return request<Record<string, unknown>>("/api/migration/status");
}

export function getNextSessionCache() {
  return request<Record<string, unknown>>("/api/next-session/cache");
}

export function getEvidenceCache() {
  return request<Record<string, unknown>>("/api/evidence/cache");
}

export function getMarketContextCache() {
  return request<Record<string, unknown>>("/api/market/cache");
}

export function getDataCapabilityCache() {
  return request<Record<string, unknown>>("/api/data-capability/cache");
}

export function getFactorQuantCache() {
  return request<Record<string, unknown>>("/api/factor-quant/cache");
}

export function getSerenityCache() {
  return request<Record<string, unknown>>("/api/serenity/cache");
}

export function getChokepointCache() {
  return request<Record<string, unknown>>("/api/chokepoint/cache");
}

export function getTradeReviewCache() {
  return request<Record<string, unknown>>("/api/trade-review/cache");
}

export function getQuantCache() {
  return request<Record<string, unknown>>("/api/quant/cache");
}

export function getStrategyCache() {
  return request<Record<string, unknown>>("/api/strategy/cache");
}

export function getPositionCache() {
  return request<Record<string, unknown>>("/api/position/cache");
}

export function getCandidateRadarCache() {
  return request<Record<string, unknown>>("/api/candidate-radar/cache");
}

export function getRiskGuardrailsCache() {
  return request<Record<string, unknown>>("/api/risk/cache");
}

export function getRecoveryCenterCache() {
  return request<Record<string, unknown>>("/api/recovery/cache");
}

export function getFactorValuesStorage() {
  return request<Record<string, unknown>>("/api/storage/factor-values");
}

export function getStorageOverview() {
  return request<Record<string, unknown>>("/api/storage");
}

export function postTask(path: string, payload: Record<string, unknown> = {}) {
  return request<{ task_id: string; task: TaskRecord }>(path, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getTask(taskId: string) {
  return request<TaskRecord>(`/api/tasks/${taskId}`);
}

export function getTasks() {
  return request<{ tasks: TaskRecord[] }>("/api/tasks");
}

export function getTaskCatalog() {
  return request<Record<string, unknown>>("/api/tasks/catalog");
}
