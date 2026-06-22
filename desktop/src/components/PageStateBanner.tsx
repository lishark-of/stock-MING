import { BACKEND_OFFLINE_ERROR } from "../api/client";
import BackendOfflineNotice from "./BackendOfflineNotice";
import StateClarityRail from "./StateClarityRail";

export default function PageStateBanner({
  loading,
  error,
  empty,
  emptyTitle = "暂无缓存数据",
  emptyDetail = "当前页面只读取 FastAPI cache API；不会自动触发外部刷新。",
}: {
  loading?: boolean;
  error?: string;
  empty?: boolean;
  emptyTitle?: string;
  emptyDetail?: string;
}) {
  if (loading) {
    return (
      <div className="page-state page-state-loading motion-surface" data-page-state="loading" data-motion-scope="cache_refresh_clarity" data-motion-purpose="state_change_confirmation">
        <strong>正在读取本地缓存...</strong>
        <p>默认只调用 GET cache API，不触发 Tushare、DeepSeek、GitHub 或真实交易。</p>
        <StateClarityRail
          label="cache loading state"
          state="loading"
          steps={[
            { label: "cache", state: "active", detail: "GET" },
            { label: "ledger", state: "waiting", detail: "local" },
            { label: "boundary", state: "done", detail: "safe" }
          ]}
        />
      </div>
    );
  }

  if (error) {
    const isBackendOffline = error.includes(BACKEND_OFFLINE_ERROR);
    return (
      <div className="page-state page-state-error motion-surface" data-page-state="error" data-motion-scope="cache_refresh_clarity" data-motion-purpose="state_change_confirmation">
        <strong>缓存读取失败</strong>
        <BackendOfflineNotice error={error} />
        <p>{isBackendOffline ? "本地后端未连接；请按上方步骤使用本地启动器恢复连接。" : error}</p>
        <StateClarityRail
          label="cache error state"
          state="error"
          steps={[
            { label: "cache", state: "blocked", detail: "failed" },
            { label: "ledger", state: "waiting", detail: "review" },
            { label: "boundary", state: "done", detail: "safe" }
          ]}
        />
      </div>
    );
  }

  if (empty) {
    return (
      <div className="page-state page-state-empty motion-surface" data-page-state="empty" data-motion-scope="cache_refresh_clarity" data-motion-purpose="state_change_confirmation">
        <strong>{emptyTitle}</strong>
        <p>{emptyDetail}</p>
        <StateClarityRail
          label="empty cache state"
          state="empty"
          steps={[
            { label: "cache", state: "waiting", detail: "empty" },
            { label: "ledger", state: "done", detail: "local" },
            { label: "boundary", state: "done", detail: "safe" }
          ]}
        />
      </div>
    );
  }

  return null;
}
