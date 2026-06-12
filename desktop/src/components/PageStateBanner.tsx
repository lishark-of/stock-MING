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
      <div className="page-state page-state-loading motion-surface" data-page-state="loading">
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
    return (
      <div className="page-state page-state-error motion-surface" data-page-state="error">
        <strong>缓存读取失败</strong>
        <p>{error}</p>
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
      <div className="page-state page-state-empty motion-surface" data-page-state="empty">
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
