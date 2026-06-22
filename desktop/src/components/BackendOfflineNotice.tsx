import { API_BASE_DISPLAY_URL, BACKEND_OFFLINE_ERROR } from "../api/client";

const COMMAND_CENTER_3_LAUNCHER_PATH = "scripts/start_command_center_3.command";
const COMMAND_CENTER_3_DESKTOP_SHORTCUT = "stock-MING Command Center 3.command";

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
      <p>下一步：请双击桌面快捷方式 {COMMAND_CENTER_3_DESKTOP_SHORTCUT}，或运行 {COMMAND_CENTER_3_LAUNCHER_PATH} 重新打开 Command Center 3.0，然后刷新本页。</p>
      <p>启动器会等待 FastAPI 和页面都 ready 后才打开入口；当前画面只显示离线保护状态。</p>
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
