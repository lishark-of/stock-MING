import { API_BASE_DISPLAY_URL, BACKEND_OFFLINE_ERROR } from "../api/client";

export default function BackendOfflineNotice({
  error,
  warnings = [],
  apiBase = API_BASE_DISPLAY_URL,
}: {
  error?: string | null;
  warnings?: string[];
  apiBase?: string;
}) {
  if (!error?.includes(BACKEND_OFFLINE_ERROR)) {
    return null;
  }

  return (
    <div className="backend-offline-notice motion-surface" data-backend-offline="true" role="status">
      <strong>本地后端未连接</strong>
      <p>请先启动本地 FastAPI 后端服务，再刷新本页。当前画面只显示离线保护状态。</p>
      <p>连接地址：{apiBase}</p>
      <ul>
        <li>不会调用 Tushare、DeepSeek 或 GitHub。</li>
        <li>不会执行真实交易，也不会修改 strategy action。</li>
        {warnings.slice(0, 2).map((warning) => (
          <li key={warning}>{warning}</li>
        ))}
      </ul>
    </div>
  );
}
