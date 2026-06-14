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
  payload_safe?: Record<string, unknown>;
  storage_source?: string;
  call_ledger?: Array<Record<string, unknown>>;
  status_history?: Array<Record<string, unknown>>;
  backend?: string;
  external_calls_triggered?: boolean;
  tushare_called?: boolean;
  deepseek_called?: boolean;
  github_called?: boolean;
  does_not_execute_trades?: boolean;
  does_not_modify_strategy_action?: boolean;
  retry_policy?: Record<string, unknown>;
  warnings: string[];
};

export type TaskStatusIndex = {
  packet_key: string;
  schema_version: string;
  mode: string;
  status: string;
  tasks: TaskRecord[];
  task_count: number;
  status_counts: Record<string, number>;
  latest_task_id?: string;
  latest_task_type?: string;
  latest_task_status?: string;
  call_ledger_count: number;
  persistence?: Record<string, unknown>;
  persistence_source_rows?: Array<Record<string, unknown>>;
  policy: Record<string, unknown>;
  external_calls_triggered: boolean;
  tushare_called: boolean;
  deepseek_called: boolean;
  github_called: boolean;
  does_not_execute_trades: boolean;
  does_not_modify_strategy_action: boolean;
  call_ledger: Array<Record<string, unknown>>;
  warnings: string[];
};

export type TaskCreationData = {
  task_id: string;
  task: TaskRecord;
};

export type TaskCreationEnvelope = ApiEnvelope<TaskCreationData>;

export type StorageQueryParams = {
  limit?: number;
  cursor?: string;
  ts_code?: string;
  trade_date?: string;
  start_date?: string;
  end_date?: string;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8710";
export const API_BASE_URL = API_BASE;
export const BACKEND_OFFLINE_ERROR = "backend_offline_or_unreachable";
const RESPONSE_PARSE_ERROR = "response_parse_failed";

function safeApiBaseDisplay(value: string): string {
  try {
    const parsed = new URL(value);
    parsed.username = "";
    parsed.password = "";
    parsed.search = "";
    parsed.hash = "";
    return parsed.toString().replace(/\/$/, "");
  } catch {
    return value.split(/[?#]/)[0].slice(0, 180);
  }
}

export const API_BASE_DISPLAY_URL = safeApiBaseDisplay(API_BASE);

function errorToMessage(error: unknown): string | null {
  if (!error) return null;
  if (typeof error === "string") return error;
  if (typeof error === "object") {
    const record = error as Record<string, unknown>;
    const code = typeof record.code === "string" ? record.code : "request_not_ok";
    const message = typeof record.message === "string" ? record.message : code;
    return `${code}: ${message}`;
  }
  return String(error);
}

function safeExceptionMessage(error: unknown): string {
  if (error instanceof Error) {
    return [error.name, error.message].filter(Boolean).join(": ").slice(0, 180);
  }
  return String(error ?? "request failed").slice(0, 180);
}

function failedRequestEnvelope<T>(path: string, callStatus: string, error: unknown): ApiEnvelope<T> {
  const safeMessage = safeExceptionMessage(error);
  return {
    ok: false,
    data: {} as T,
    error: `${callStatus}: ${safeMessage}`,
    call_ledger: [
      {
        api: "frontend_fastapi_request",
        endpoint: path,
        api_base: API_BASE_DISPLAY_URL,
        call_status: callStatus,
        error_message_safe: safeMessage,
        external: false,
        external_calls_triggered: false,
        tushare_called: false,
        deepseek_called: false,
        github_called: false,
        does_not_execute_trades: true,
        does_not_modify_strategy_action: true,
      }
    ],
    warnings: [
      "本地 FastAPI 后端暂未连接；请启动本地后端服务后刷新页面。",
      "此离线提示不会调用 Tushare、DeepSeek、GitHub，也不会执行真实交易。",
    ],
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<ApiEnvelope<T>> {
  try {
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
    try {
      const payload = await res.json();
      return {
        ...payload,
        data: payload.data === null ? ({} as T) : payload.data,
        error: errorToMessage(payload.error),
        call_ledger: payload.call_ledger ?? [],
        warnings: payload.warnings ?? [],
      } as ApiEnvelope<T>;
    } catch (error) {
      return failedRequestEnvelope<T>(path, RESPONSE_PARSE_ERROR, error);
    }
  } catch (error) {
    return failedRequestEnvelope<T>(path, BACKEND_OFFLINE_ERROR, error);
  }
}

function queryString(params: Record<string, string | number | undefined | null> = {}): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    query.set(key, String(value));
  }
  const encoded = query.toString();
  return encoded ? `?${encoded}` : "";
}

export function getHealth() {
  return request<Record<string, unknown>>("/health");
}

export function getAuditCache() {
  return request<Record<string, unknown>>("/api/audit/cache");
}

export function postMotionBrowserQaReview(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/audit/motion-browser-qa-review", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postMotionProductionPromotionDryRun(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/audit/motion-production-promotion-dry-run", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getLegacyBridgeCache() {
  return request<Record<string, unknown>>("/api/legacy/cache");
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

export function getModelStrategyCache() {
  return request<Record<string, unknown>>("/api/model-strategy/cache");
}

export function getBootstrapStatus() {
  return request<Record<string, unknown>>("/api/bootstrap/status");
}

export function postBootstrapLiveStartup(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/bootstrap/live-startup", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postBootstrapProviderModelAcceptanceDryRun(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/bootstrap/provider-model-acceptance-dry-run", {
    method: "POST",
    body: JSON.stringify(payload)
  });
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

export function getDataHealthCache() {
  return request<Record<string, unknown>>("/api/data-health/cache");
}

export function postTradeCalProviderAcceptanceDryRun(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/data-health/trade-cal-provider-acceptance-dry-run", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getDesktopPreflightCache() {
  return request<Record<string, unknown>>("/api/desktop/preflight-cache");
}

export function getDisciplineLoopCache() {
  return request<Record<string, unknown>>("/api/discipline/cache");
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

export function postCandidateRadarQuickScan(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/candidate-radar/scan-quick", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postCandidateRadarQuantProjection(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/candidate-radar/quant-projection", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postCandidateRadarQuantProjectionAcceptanceDryRun(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/candidate-radar/quant-projection-acceptance-dry-run", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postCandidateRadarProviderParityDryRun(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/candidate-radar/provider-parity-dry-run", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postCandidateRadarFullPoolPlan(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/candidate-radar/full-pool-plan", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postCandidateRadarFullPoolLocalScan(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/candidate-radar/full-pool-local-scan", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postCandidateRadarDeepScanPlan(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/candidate-radar/deep-scan-plan", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postCandidateRadarDeepScanLocalReview(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/candidate-radar/deep-scan-local-review", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postCandidateRadarBrowserQaReview(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/candidate-radar/browser-qa-review", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getRiskGuardrailsCache() {
  return request<Record<string, unknown>>("/api/risk/cache");
}

export function getRecoveryCenterCache() {
  return request<Record<string, unknown>>("/api/recovery/cache");
}

export function getFactorValuesStorage(params: StorageQueryParams = {}) {
  return request<Record<string, unknown>>(`/api/storage/factor-values${queryString(params)}`);
}

export function getSQLiteMetaStorage() {
  return request<Record<string, unknown>>("/api/storage/sqlite-meta");
}

export function getStorageDataset(dataset: string, params: StorageQueryParams = {}) {
  return request<Record<string, unknown>>(`/api/storage/${encodeURIComponent(dataset)}${queryString(params)}`);
}

export function getStorageCatalog() {
  return request<Record<string, unknown>>("/api/storage/catalog");
}

export function getStorageOverview() {
  return request<Record<string, unknown>>("/api/storage");
}

export function postStorageArtifactCleanupDryRun(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/storage/artifact-hygiene/dry-run", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postStorageSchemaValidationDryRun(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/storage/schema-validation/dry-run", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postStorageSchemaValidationAcceptance(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/storage/schema-validation/acceptance", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postStorageDatasetVersionManifestDryRun(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/storage/dataset-version-manifest/dry-run", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postStorageDatasetVersionManifestReview(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/storage/dataset-version-manifest/review", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postStorageDatasetVersionManifestWrite(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/storage/dataset-version-manifest/write", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postStorageDatasetVersionManifestValidate(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/storage/dataset-version-manifest/validate", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postStoragePartitionMigrationDryRun(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/storage/partition-migration/dry-run", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postStorageCompactionDryRun(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/storage/compaction/dry-run", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postStorageCacheTtlDryRun(payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>("/api/storage/cache-ttl/dry-run", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function postTask(path: string, payload: Record<string, unknown> = {}) {
  return request<TaskCreationData>(path, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function cancelTask(taskId: string, reason = "manual_cancel_from_task_catalog") {
  return request<TaskCreationData>(`/api/tasks/${encodeURIComponent(taskId)}/cancel`, {
    method: "POST",
    body: JSON.stringify({ reason })
  });
}

export function retryTask(taskId: string, reason = "manual_retry_from_task_catalog") {
  return request<TaskCreationData>(`/api/tasks/${encodeURIComponent(taskId)}/retry`, {
    method: "POST",
    body: JSON.stringify({ reason })
  });
}

export function getTask(taskId: string) {
  return request<TaskRecord>(`/api/tasks/${encodeURIComponent(taskId)}`);
}

export function getTasks() {
  return request<TaskStatusIndex>("/api/tasks");
}

export function getTaskCatalog() {
  return request<Record<string, unknown>>("/api/tasks/catalog");
}

export function getWorkerRuntimeCache() {
  return request<Record<string, unknown>>("/api/worker/cache");
}

export function runWorkerSyntheticHealthcheck(payload: Record<string, unknown> = {}) {
  return request<Record<string, unknown>>("/api/worker/synthetic-healthcheck", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function runWorkerActivationReview(payload: Record<string, unknown> = {}) {
  return request<Record<string, unknown>>("/api/worker/activation-review", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
