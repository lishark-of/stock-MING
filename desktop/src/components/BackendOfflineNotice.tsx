import {
  API_BASE_CANDIDATE_DISPLAY_URLS,
  API_BASE_DISPLAY_URL,
  BACKEND_OFFLINE_ERROR,
  CONFIGURED_API_BASE_DISPLAY_URL,
} from "../api/client";

const COMMAND_CENTER_3_LAUNCHER_PATH = "scripts/start_command_center_3.command";
const COMMAND_CENTER_3_CHECK_ONLY_LAUNCHER_PATH = "scripts/check_command_center_3.command";
const COMMAND_CENTER_3_DESKTOP_SHORTCUT = "stock-MING Command Center 3.command";
const COMMAND_CENTER_3_CHECK_ONLY_COMMAND = COMMAND_CENTER_3_CHECK_ONLY_LAUNCHER_PATH;

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
    `先安全自检：运行 ${COMMAND_CENTER_3_CHECK_ONLY_COMMAND}；它只打印本机 API/Vite/open route，不启动 FastAPI/Vite、不探测 URL、不打开浏览器、不创建 task。`,
    `下一步：请双击桌面快捷方式 ${COMMAND_CENTER_3_DESKTOP_SHORTCUT}，或运行 ${COMMAND_CENTER_3_LAUNCHER_PATH}。`,
    "启动器会等待 FastAPI 和页面都 ready 后才打开入口；等启动器显示 FastAPI / bootstrap status / desktop preflight cache / React/Vite 四段 ready 后，再刷新本页。",
    "恢复联通后：先看系统健康是否变绿，再去下一票雷达输入代码；点击“确认并生成 3.0 量化推演”创建 Tushare-first 按钮门控任务。只有点击确认按钮才创建 Tushare-first 任务。"
  ];
  const ordinaryRecoveryGateSteps = [
    "未 ready：停在离线保护，不直接进入雷达、量化推演或次日图谱。",
    "四段 ready：刷新本页或系统健康页，确认本地前后端已联通。",
    "联通后：进入下一票雷达；输入代码只做本地校验，确认按钮才进入 P1 Tushare-first task。",
    "结果回放：任务完成后再看 cache / ledger / packet；DeepSeek 仍等 governed executor。"
  ];

  return (
    <div className="backend-offline-notice motion-surface" data-backend-offline="true" role="status">
      <strong>本地后端未连接</strong>
      <p>先按这四步恢复本地联通；当前画面只显示离线保护状态。</p>
      <ol aria-label="backend offline ordinary recovery checklist">
        {ordinaryRecoverySteps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      <strong>P0 恢复闸门</strong>
      <ol aria-label="backend offline p0 recovery gate checklist">
        {ordinaryRecoveryGateSteps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      <div className="actions" aria-label="backend offline local recovery links">
        <a href="#desktop" aria-label="open one click startup preflight">打开一键启动预检</a>
        <a href="#health" aria-label="open system health after local backend recovery">查看系统健康</a>
        <a href="#candidates" aria-label="open candidate radar after backend recovery">联通变绿后去下一票雷达</a>
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
        <p>只想先自检入口配置时，运行 {COMMAND_CENTER_3_CHECK_ONLY_COMMAND}；它会进入 check-only 安全自检，不会启动 FastAPI/Vite、不会打开浏览器、不会创建 task。</p>
        <p>如果刚运行启动器后仍离线，可能是旧的 React/Vite dev server 复用了不同后端地址；请关闭旧 dev server 后重新运行启动器，并查看 .stock_ming_3/logs/command_center_3_vite.log。</p>
        <p>连接地址：{apiBase}</p>
      </details>
    </div>
  );
}
