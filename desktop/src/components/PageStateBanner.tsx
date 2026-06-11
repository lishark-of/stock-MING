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
      <div className="page-state page-state-loading">
        <strong>正在读取本地缓存...</strong>
        <p>默认只调用 GET cache API，不触发 Tushare、DeepSeek、GitHub 或真实交易。</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-state page-state-error">
        <strong>缓存读取失败</strong>
        <p>{error}</p>
      </div>
    );
  }

  if (empty) {
    return (
      <div className="page-state page-state-empty">
        <strong>{emptyTitle}</strong>
        <p>{emptyDetail}</p>
      </div>
    );
  }

  return null;
}
