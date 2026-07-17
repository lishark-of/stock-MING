export default function RouteCacheLoadingOverlay({ loading }: { loading: boolean }) {
  if (!loading) return null;
  return (
    <div
      className="route-cache-loading-overlay page-state page-state-loading motion-surface"
      data-page-state="route_cache_loading"
      data-motion-scope="cache_refresh_clarity"
      data-motion-purpose="state_change_confirmation"
      role="status"
      aria-live="polite"
    >
      <strong>正在读取本地缓存...</strong>
      <p>读取完成前保持页面布局稳定；不会触发外部数据、模型、后台 worker 或交易调用。</p>
    </div>
  );
}
