import {
  API_BASE_CANDIDATE_DISPLAY_URLS,
  API_BASE_DISPLAY_URL,
  BACKEND_OFFLINE_ERROR,
  CONFIGURED_API_BASE_DISPLAY_URL,
} from "../api/client";

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
  const attemptedApiBases = API_BASE_CANDIDATE_DISPLAY_URLS.length
    ? API_BASE_CANDIDATE_DISPLAY_URLS.join(" / ")
    : apiBase;
  const ordinaryRecoverySteps = [
    `双击桌面快捷方式 ${COMMAND_CENTER_3_DESKTOP_SHORTCUT}，或运行 ${COMMAND_CENTER_3_LAUNCHER_PATH}。`,
    "等启动器显示 FastAPI / bootstrap status / desktop preflight cache / React/Vite 四段 ready 后，再刷新本页。",
    "恢复联通后去下一票雷达输入代码，只有点击确认按钮才创建 Tushare-first 任务。"
  ];

  return (
    <div className="backend-offline-notice motion-surface" data-backend-offline="true" role="status">
      <strong>本地后端未连接</strong>
      <p>先按这三步恢复本地联通；当前画面只显示离线保护状态。</p>
      <ol aria-label="backend offline ordinary recovery checklist">
        {ordinaryRecoverySteps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      <div className="actions" aria-label="backend offline local recovery links">
        <a href="#desktop" aria-label="open one click startup preflight">打开一键启动预检</a>
        <a href="#health" aria-label="open system health after local backend recovery">查看系统健康</a>
        <a href="#candidates" aria-label="open candidate radar after backend recovery">恢复后去下一票雷达</a>
        <a href="#recovery" aria-label="open local recovery center">查看恢复中心</a>
      </div>
      <p>这些入口只切换本地页面；不会启动 FastAPI/Vite、不会创建 task、不会调用外部数据源或模型。</p>
      <ul>
        <li>不会调用 Tushare、DeepSeek 或 GitHub。</li>
        <li>不会执行真实交易，也不会修改 strategy action。</li>
        {warnings.slice(0, 2).map((warning) => (
          <li key={warning}>{warning}</li>
        ))}
      </ul>
      <details className="developer-audit-details">
        <summary>联通排障详情</summary>
        <p>前端已自动尝试本机 FastAPI 地址：{attemptedApiBases}；配置地址显示为 {CONFIGURED_API_BASE_DISPLAY_URL}。</p>
        <p>启动器会等待 FastAPI、bootstrap status、desktop preflight cache 和 React/Vite 页面都 ready 后才打开入口。</p>
        <p>如果刚运行启动器后仍离线，可能是旧的 React/Vite dev server 复用了不同后端地址；请关闭旧 dev server 后重新运行启动器，并查看 .stock_ming_3/logs/command_center_3_vite.log。</p>
        <p>连接地址：{apiBase}</p>
      </details>
    </div>
  );
}
