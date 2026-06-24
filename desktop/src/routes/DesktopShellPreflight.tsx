import { useEffect, useState } from "react";
import { getDesktopPreflightCache } from "../api/client";
import BackendOfflineNotice from "../components/BackendOfflineNotice";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

export default function DesktopShellPreflight() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    void getDesktopPreflightCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
      setError(res.error ?? "");
    });
  }, []);

  const runtime = (cache.runtime as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const apiBaseInfo = (cache.api_base_info as Record<string, unknown> | undefined) ?? {};
  const frontendBackendAutoLinkContract = (cache.frontend_backend_auto_link_contract as Record<string, unknown> | undefined) ?? {};
  const oneClickStartupSummary = (cache.one_click_startup_summary as Record<string, unknown> | undefined) ?? {};
  const p0LocalConnectionReceipt = (cache.p0_local_connection_receipt as Record<string, unknown> | undefined) ?? {};
  const desktopLauncherContract = (cache.desktop_launcher_contract as Record<string, unknown> | undefined) ?? {};
  const tauriBuildArtifact = (cache.tauri_build_artifact as Record<string, unknown> | undefined) ?? {};
  const productionReadiness = (cache.production_readiness as Record<string, unknown> | undefined) ?? {};
  const productionRuntimeContract = (cache.production_runtime_contract as Record<string, unknown> | undefined) ?? {};
  const backendOfflineUxContract = (cache.backend_offline_ux_contract as Record<string, unknown> | undefined) ?? {};
  const productionBlockerAudit = (cache.production_blocker_audit as Record<string, unknown> | undefined) ?? {};
  const packagedRuntimeQaContract = (cache.packaged_runtime_qa_contract as Record<string, unknown> | undefined) ?? {};
  const tauriReleaseManifestContract = (cache.tauri_release_manifest_contract as Record<string, unknown> | undefined) ?? {};
  const productionPackageReadinessReceipt = (cache.production_package_readiness_receipt as Record<string, unknown> | undefined) ?? {};
  const tauriPackageDurableEvidenceRecipe = (cache.tauri_package_durable_evidence_recipe as Record<string, unknown> | undefined) ?? {};
  const oneClickConnectionRows = rows(cache.one_click_connection_rows);
  const frontendBackendAutoLinkRows = rows(cache.frontend_backend_auto_link_rows);
  const p0LocalConnectionRows = rows(cache.p0_local_connection_rows);
  const p0ConnectionReady = oneClickStartupSummary.frontend_backend_connection_ready === true;
  const p0RecoverySteps = rows(cache.p0_recovery_steps).length
    ? rows(cache.p0_recovery_steps)
    : [
        { step: "1", title: "打开本地一键入口", action: "双击 stock-MING Command Center 3.command；或运行 scripts/start_command_center_3.command。" },
        { step: "2", title: "按启动器诊断定位失败段", action: "先看 FastAPI、bootstrap status、desktop preflight cache、React/Vite 哪一段没有 ready。" },
        { step: "3", title: "刷新健康页确认联通", action: "确认 P0 front/back、P0 receipt 和 one-click launcher 都为 ready。" }
      ];
  const p0PostStartupReadbackRows = rows(cache.p0_post_startup_readback_rows).length
    ? rows(cache.p0_post_startup_readback_rows)
    : [
        {
          复核项: "FastAPI health",
          页面看法: "系统健康和今日作战台显示本地前后端已联通",
          通过条件: "GET /health 返回 Command Center 3.0 JSON，且 external_calls_on_startup=false",
          失败下一步: "回启动器日志看 FastAPI 诊断，再检查 8710 是否被占用",
          边界: "只读健康检查，不启动服务、不创建 task"
        },
        {
          复核项: "Bootstrap status",
          页面看法: "今日作战台显示运行模式和启动边界",
          通过条件: "GET /api/bootstrap/status 返回 runtime-mode packet",
          失败下一步: "回启动器日志看 bootstrap status 诊断",
          边界: "只读运行模式，不写配置、不启用 live_light"
        },
        {
          复核项: "Desktop preflight cache",
          页面看法: "普通入口和系统健康显示同一条 P0 一键启动 packet",
          通过条件: "GET /api/desktop/preflight-cache 返回一键启动 packet，且 external_calls_triggered=false",
          失败下一步: "回启动器日志看 desktop preflight cache 诊断",
          边界: "只读预检回放，不启动服务、不创建 task"
        },
        {
          复核项: "React/Vite 前端",
          页面看法: "浏览器打开 Command Center 3.0 今日作战台",
          通过条件: "Vite 返回 Command Center 3.0 HTML，且页面入口可点击到预检、健康、雷达和量化推演",
          失败下一步: "回启动器日志看 React/Vite 诊断，再检查 5173 是否被占用",
          边界: "只读前端入口，不调用 Tushare/DeepSeek/GitHub、不执行真实交易"
        }
      ];
  const p0ToP1OrdinaryHandoffRows = rows(cache.p0_to_p1_ordinary_handoff_rows).length
    ? rows(cache.p0_to_p1_ordinary_handoff_rows)
    : [
        {
          步骤: "1. 确认本地联通",
          用户动作: "先看 FastAPI、Bootstrap status、Desktop preflight cache、React/Vite 四段是否 ready。",
          当前状态: oneClickStartupSummary.frontend_backend_connection_ready === true ? "ready：可以进入普通投研入口" : "check：先恢复本地一键入口",
          下一步: oneClickStartupSummary.frontend_backend_connection_ready === true ? "打开下一票雷达，输入股票代码。" : "回到启动器诊断或桌面壳预检。",
          边界: "只读 GET health / preflight cache；不启动服务、不创建 task。"
        },
        {
          步骤: "2. 进入下一票雷达",
          用户动作: "去下一票雷达的搜票量化推演卡片。",
          当前状态: "只读导航提示",
          下一步: "输入 6 位 A 股代码或带后缀代码。",
          边界: "页面切换和输入不会调用 Tushare、DeepSeek 或 GitHub。"
        },
        {
          步骤: "3. 点击确认并生成",
          用户动作: "代码通过本地校验后点击确认按钮。",
          当前状态: "确认按钮才是 P1 工作入口",
          下一步: "看本地任务编号、TaskStatusPanel 和 cache 回放。",
          边界: "只有确认按钮可创建 Tushare-first POST task / worker；DeepSeek skipped。"
        },
        {
          步骤: "4. 回放本地结果",
          用户动作: "任务完成后刷新本地 cache，再看股票量化推演和次日图谱。",
          当前状态: "结果来自 cache / ledger / packet",
          下一步: "按缺口和仅供研究边界复核。",
          边界: "GET cache / React render 不补调外部数据源，不交易、不改 strategy action。"
        }
      ];
  const p0OrdinaryReconnectRows = rows(cache.p0_ordinary_reconnect_rows).length
    ? rows(cache.p0_ordinary_reconnect_rows)
    : [
        {
          用户状态: "页面未打开或本地后端离线",
          当前状态: p0ConnectionReady ? "ready" : "check",
          用户下一步: "双击 stock-MING Command Center 3.command；或运行 scripts/start_command_center_3.command。",
          入口: "scripts/start_command_center_3.command",
          通过信号: "启动器看到 FastAPI /health、bootstrap status、desktop preflight cache、React/Vite 四段 ready 后才打开页面。",
          边界: "这是本地恢复指引；GET cache 和 React render 不启动 FastAPI/Vite、不创建 task。",
          strict_closeout_evidence: false,
          release_ready_evidence: false
        },
        {
          用户状态: "启动器没有自动打开页面",
          当前状态: p0ConnectionReady ? "ready" : "check",
          用户下一步: "按启动器输出定位 FastAPI、bootstrap status、desktop preflight cache 或 React/Vite 哪段失败。",
          入口: ".stock_ming_3/logs",
          通过信号: "日志和 8710/5173 端口指引能指出阻断段。",
          边界: "只读诊断，不读取 token/key、不调用 Tushare/DeepSeek/GitHub、不执行真实交易。",
          strict_closeout_evidence: false,
          release_ready_evidence: false
        },
        {
          用户状态: "四段联通变绿",
          当前状态: p0ConnectionReady ? "ready" : "check",
          用户下一步: "打开下一票雷达，输入股票代码。",
          入口: "#candidates",
          通过信号: "P0 联通 ready 后才进入普通投研入口。",
          边界: "页面切换和输入代码不外联；确认按钮之前不创建 POST task。",
          strict_closeout_evidence: false,
          release_ready_evidence: false
        },
        {
          用户状态: "准备生成基础投研结果",
          当前状态: p0ConnectionReady ? "ready" : "check",
          用户下一步: "点击确认按钮创建 Tushare-first P1 task；DeepSeek 仍保持 governed/skipped。",
          入口: "下一票雷达确认按钮",
          通过信号: "TaskStatusPanel 显示本地任务编号，结果回放来自 cache / ledger / packet。",
          边界: "只有确认按钮可进入 P1 task；本清单不是 14 LTG strict closeout 或 release ready 证据。",
          strict_closeout_evidence: false,
          release_ready_evidence: false
        }
      ];
  const p0OrdinaryConnectionRows = rows(cache.p0_ordinary_connection_rows).length
    ? rows(cache.p0_ordinary_connection_rows)
    : [
        {
          环节: "FastAPI",
          当前状态: oneClickStartupSummary.frontend_backend_connection_ready === true ? "ready" : "check",
          用户下一步: "如果未 ready，先看启动器 FastAPI 诊断和 command_center_3_fastapi.log",
          通过条件: "本地 /health 返回 Command Center 3.0 JSON",
          边界: "预检页只读 GET cache，不启动 FastAPI、不创建 task"
        },
        {
          环节: "Bootstrap status",
          当前状态: oneClickStartupSummary.frontend_backend_connection_ready === true ? "ready" : "check",
          用户下一步: "如果未 ready，回启动器确认 bootstrap status 段是否返回 runtime-mode packet",
          通过条件: "本地 /api/bootstrap/status 返回 runtime-mode packet",
          边界: "只读运行模式，不写配置、不启用 live_light"
        },
        {
          环节: "Desktop preflight cache",
          当前状态: oneClickStartupSummary.frontend_backend_connection_ready === true ? "ready" : "check",
          用户下一步: "如果未 ready，回启动器确认 desktop preflight cache 段是否返回一键启动 packet",
          通过条件: "本地 /api/desktop/preflight-cache 返回 command_center_3_desktop_shell_preflight_cache",
          边界: "只读一键启动 packet；不运行 launcher、不探测当前运行时"
        },
        {
          环节: "React/Vite",
          当前状态: oneClickStartupSummary.frontend_backend_connection_ready === true ? "ready" : "check",
          用户下一步: "如果未 ready，检查 5173 是否被占用并查看 command_center_3_vite.log",
          通过条件: "本地 Vite 返回 Command Center 3.0 前端 HTML",
          边界: "只读前端入口，不调用 Tushare/DeepSeek/GitHub、不执行真实交易"
        }
      ];
  const p0FailureDiagnosticRows = rows(cache.p0_failure_diagnostic_rows).length
    ? rows(cache.p0_failure_diagnostic_rows)
    : [
        {
          失败段: "FastAPI /health",
          当前状态: p0ConnectionReady ? "ready" : "check",
          怎么判断: "启动器必须看到 Command Center 3.0 health JSON，且 external_calls_on_startup=false。",
          用户动作: "如果这里 check，先看 FastAPI 日志，再检查 8710 是否被占用。",
          "日志/端口": ".stock_ming_3/logs/command_center_3_fastapi.log / 8710",
          边界: "只读诊断；GET preflight 和 React render 不启动 FastAPI、不创建 task。"
        },
        {
          失败段: "Bootstrap status",
          当前状态: p0ConnectionReady ? "ready" : "check",
          怎么判断: "启动器必须看到 /api/bootstrap/status 返回 command_center_3_bootstrap_runtime_mode_packet。",
          用户动作: "如果这里 check，说明后端已到 health 但 runtime-mode packet 未就绪，继续看 FastAPI 日志中的 bootstrap status 段。",
          "日志/端口": ".stock_ming_3/logs/command_center_3_fastapi.log / /api/bootstrap/status",
          边界: "只读运行模式诊断；不写配置、不启用 live_light、不调用 provider/model。"
        },
        {
          失败段: "Desktop preflight cache",
          当前状态: p0ConnectionReady ? "ready" : "check",
          怎么判断: "启动器必须看到 /api/desktop/preflight-cache 返回 command_center_3_desktop_shell_preflight_cache。",
          用户动作: "如果这里 check，后端 health 已可用但桌面预检 packet 未就绪，继续看 FastAPI 日志中的 desktop preflight 段。",
          "日志/端口": ".stock_ming_3/logs/command_center_3_fastapi.log / /api/desktop/preflight-cache",
          边界: "只读预检诊断；不运行 launcher、不启动服务、不创建 task。"
        },
        {
          失败段: "React/Vite HTML",
          当前状态: p0ConnectionReady ? "ready" : "check",
          怎么判断: "启动器必须看到 Vite 返回 Command Center 3.0 前端 HTML。",
          用户动作: "如果这里 check，先看 Vite 日志，再检查 5173 是否被旧 dev server 占用。",
          "日志/端口": ".stock_ming_3/logs/command_center_3_vite.log / 5173",
          边界: "只读前端入口诊断；不调用 Tushare、DeepSeek、GitHub、不执行真实交易。"
        },
        {
          失败段: "端口和日志指引",
          当前状态: "ready",
          怎么判断: "启动器失败时必须打印 FastAPI、Bootstrap status、Desktop preflight cache、React/Vite 和 8710/5173 指引。",
          用户动作: "按启动器输出关闭占用进程，或重新运行 scripts/start_command_center_3.command。",
          "日志/端口": "8710 / 5173 / .stock_ming_3/logs",
          边界: "这只是失败定位清单；不启动服务、不创建 POST task、不外联。"
        }
      ];
  const p0ShortcutInstallerRows = [
    {
      检查项: "不会覆盖同名文件",
      当前状态: desktopLauncherContract.desktop_shortcut_installer_blocks_regular_file_overwrite === true ? "ready" : "check",
      用户看法: "桌面已有同名普通文件时安装器会停止，并提示换名或移走文件",
      边界: "只安装本地 symlink，不启动 FastAPI/Vite、不创建 task"
    },
    {
      检查项: "安装后自检",
      当前状态: desktopLauncherContract.desktop_shortcut_installer_verifies_symlink_target === true ? "ready" : "check",
      用户看法: "安装后确认快捷方式指向 scripts/start_command_center_3.command",
      边界: "验证本地路径，不读取 token/key、不调用 provider/model"
    },
    {
      检查项: "双击前说明",
      当前状态: desktopLauncherContract.desktop_shortcut_installer_prints_double_click_checklist === true ? "ready" : "check",
      用户看法: "双击后启动器会先检查 FastAPI、Bootstrap status、Desktop preflight cache、React/Vite 四段 ready",
      边界: "安装器本身不启用 live_light、不执行真实交易"
    }
  ];
  const p0LauncherModeRows = [
    {
      启动方式: "普通双击",
      用户动作: "双击 stock-MING Command Center 3.command；或运行 scripts/start_command_center_3.command",
      看到什么: "四段 ready 后自动打开普通首页 #home",
      适合场景: "日常打开 Command Center 3.0",
      边界: "只启动或复用本地 FastAPI/Vite；不启用 live_light/provider/model"
    },
    {
      启动方式: "只检查",
      用户动作: "scripts/check_command_center_3.command",
      看到什么: "只读显示 health、bootstrap、frontend 和 open route",
      适合场景: "先确认入口配置，不启动服务、不打开浏览器",
      边界: "不探测 URL、不写日志、不创建 task、不调用 provider/model"
    },
    {
      启动方式: "联通验收不弹窗",
      用户动作: "COMMAND_CENTER_3_LAUNCHER_SKIP_OPEN=1 scripts/start_command_center_3.command",
      看到什么: "等待 FastAPI、Bootstrap status、Desktop preflight cache、React/Vite ready 后打印手动打开地址",
      适合场景: "验证前后端联通，但不自动弹浏览器窗口",
      边界: "只连本地前后端；不调用 Tushare/DeepSeek/GitHub、不执行真实交易"
    }
  ];
  const p0SuccessHandoffRows = [
    {
      状态: p0ConnectionReady ? "ready" : "check",
      用户下一步: String(p0LocalConnectionReceipt.success_handoff_label ?? oneClickStartupSummary.success_handoff_label ?? "联通成功后打开下一票雷达，输入股票代码；只有确认按钮创建 Tushare-first POST task，DeepSeek 保持 governed/skipped。"),
      入口: String(p0LocalConnectionReceipt.success_handoff_href ?? oneClickStartupSummary.success_handoff_href ?? "#candidates"),
      证据: String(p0LocalConnectionReceipt.success_handoff_visible ?? oneClickStartupSummary.success_handoff_visible ?? false),
      边界: String(p0LocalConnectionReceipt.success_handoff_boundary ?? oneClickStartupSummary.success_handoff_boundary ?? "启动器和预检页只暴露下一步；页面切换和输入不外联，确认按钮才进入 P1 task。"),
      creates_task_from_readback: false,
      provider_model_called_from_readback: false,
      does_not_execute_trades: true
    }
  ];
  const p0RawBlockerCount = Number(oneClickStartupSummary.blocker_count ?? counts.one_click_connection_blocker_count ?? 0);
  const p0BlockerCount = Number.isFinite(p0RawBlockerCount) ? p0RawBlockerCount : 0;
  const p0StartupReadyMetrics = [
    {
      label: "启动入口",
      value: desktopLauncherContract.launcher_executable === true ? "可双击" : "检查安装",
      tone: desktopLauncherContract.launcher_executable === true ? ("good" as const) : ("warn" as const)
    },
    {
      label: "后端状态",
      value: oneClickStartupSummary.fastapi_health_identity_validated_before_open === true ? "ready" : "check",
      tone: oneClickStartupSummary.fastapi_health_identity_validated_before_open === true ? ("good" as const) : ("warn" as const)
    },
    {
      label: "前端页面",
      value: oneClickStartupSummary.vite_frontend_identity_validated_before_open === true ? "ready" : "check",
      tone: oneClickStartupSummary.vite_frontend_identity_validated_before_open === true ? ("good" as const) : ("warn" as const)
    },
    {
      label: "打开策略",
      value: p0ConnectionReady ? "就绪后打开首页" : "先看诊断",
      tone: p0ConnectionReady ? ("good" as const) : ("warn" as const)
    },
    {
      label: "普通下一步",
      value: p0ConnectionReady ? "去下一票雷达" : "先修复联通",
      tone: p0ConnectionReady ? ("good" as const) : ("warn" as const)
    },
    {
      label: "API fallback",
      value: `${String(frontendBackendAutoLinkContract.candidate_count ?? apiBaseInfo.api_base_candidate_count ?? 0)} 本机候选`,
      tone: Number(frontendBackendAutoLinkContract.candidate_count ?? apiBaseInfo.api_base_candidate_count ?? 0) > 0 ? ("good" as const) : ("warn" as const)
    }
  ];
  const p0OrdinaryPrimaryActionHref = p0ConnectionReady ? "#candidates" : "#desktop";
  const p0OrdinaryPrimaryActionLabel = p0ConnectionReady ? "去下一票雷达确认代码" : "留在一键启动预检排障";
  const p0OrdinaryPrimaryActionBoundary = p0ConnectionReady
    ? "只切换到下一票雷达；输入代码不外联，点击确认才创建 Tushare-first POST task。"
    : "只查看本页恢复步骤和日志指引；React render 不启动 FastAPI/Vite、不创建 task、不调用 provider/model。";
  const p0OrdinaryReadyGateRows = [
    {
      闸门: "P0 可继续",
      当前状态: p0ConnectionReady ? "ready：四段联通完成，可以进入 P1 搜票确认" : "check：先留在一键启动预检恢复四段联通",
      用户下一步: p0ConnectionReady ? "点击“去下一票雷达确认代码”，输入股票代码后再点确认按钮" : "按 FastAPI / bootstrap status / desktop preflight cache / React/Vite 失败段排障",
      证据: "FastAPI health + bootstrap status + desktop preflight cache + React/Vite HTML",
      边界: "这只是本地前后端联通闸门；不调用 Tushare/DeepSeek/GitHub，不创建 task，不代表 release ready 或 14 LTG 完成。"
    },
    {
      闸门: "P1 进入条件",
      当前状态: p0ConnectionReady ? "允许切换到下一票雷达" : "未满足：不要进入 P1 投研入口",
      用户下一步: p0ConnectionReady ? "页面切换和输入保持静默；只有确认按钮触发 Tushare-first POST task" : "先让四段联通 ready，再回到今日作战台或下一票雷达",
      证据: "p0_local_connection_receipt + one_click_startup_summary",
      边界: "预检页只读 GET /api/desktop/preflight-cache；不会启动 FastAPI/Vite、写配置、写 cache 或真实交易。"
    }
  ];
  const p0CurrentNextActionRows = rows(cache.p0_current_next_action_rows).length
    ? rows(cache.p0_current_next_action_rows)
    : [
        {
          行动项: "1. 当前主入口",
          当前状态: p0ConnectionReady ? "ready：进入 P1 搜票确认" : "check：先恢复 P0 本地联通",
          用户下一步: p0ConnectionReady ? "进入下一票雷达，输入股票代码；输入保持静默，确认按钮才触发 Tushare-first。" : "留在桌面壳预检，按四段恢复。",
          入口: p0OrdinaryPrimaryActionHref,
          边界: p0OrdinaryPrimaryActionBoundary
        },
        {
          行动项: "2. P1 确认按钮",
          当前状态: p0ConnectionReady ? "可点击前必须先满足 P0 ready" : "暂不进入 P1",
          用户下一步: "代码通过本地校验后点击确认按钮，才创建 Tushare-first POST task；DeepSeek skipped。",
          入口: "下一票雷达确认按钮",
          边界: "页面打开、搜索输入和本表回读都不外联；只有确认按钮可进入 P1 task / worker。"
        }
      ];
  const devLaunchPlan = rows(cache.dev_launch_plan);
  const desktopLauncherRows = rows(cache.desktop_launcher_rows);
  const productionLaunchPlan = rows(cache.production_launch_plan);
  const productionRuntimeRows = rows(cache.production_runtime_contract_rows);
  const backendOfflineUxRows = rows(cache.backend_offline_ux_rows);
  const productionBlockerRows = rows(cache.production_blocker_rows);
  const packagedRuntimeQaRows = rows(cache.packaged_runtime_qa_rows);
  const tauriReleaseManifestRows = rows(cache.tauri_release_manifest_rows);
  const productionPackageReadinessReceiptRows = rows(cache.production_package_readiness_receipt_rows);
  const tauriPackageDurableEvidenceRows = rows(cache.tauri_package_durable_evidence_rows);
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<string> | undefined) ?? []);

  return (
    <>
      <div className="page-head">
        <h1>桌面壳预检</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "warn"} />
      </div>
      <BackendOfflineNotice error={error} warnings={cacheWarnings} />

      <PacketCard title="P0 一键启动联通摘要" subtitle="普通用户先看这里：本地前端/后端是否可以一键联通" status={String(oneClickStartupSummary.status ?? "one_click_startup_summary_missing")}>
        <div aria-label="p0 ordinary one click readiness">
          <h3>一键启动就绪</h3>
          <MetricGrid items={p0StartupReadyMetrics} />
        </div>
        <div aria-label="p0 ordinary ready gate">
          <h3>P0 可继续闸门</h3>
          <p className="risk-note">普通用户先看这个闸门：四段联通 ready 才去下一票雷达；未 ready 就留在预检页按失败段恢复。</p>
          <DataLineageTable rows={p0OrdinaryReadyGateRows} />
        </div>
        <div aria-label="p0 current next action readback">
          <h3>当前下一步</h3>
          <p className="risk-note">优先读取 desktop preflight 的 p0_current_next_action_rows：未 ready 留在预检恢复；ready 后只切到下一票雷达，确认按钮才触发 Tushare-first。</p>
          <DataLineageTable rows={p0CurrentNextActionRows} />
        </div>
        <p>下一步：{String(oneClickStartupSummary.what_user_should_click_next ?? "双击 stock-MING Command Center 3.command；或运行 scripts/start_command_center_3.command。")}</p>
        <p>成功条件：{String(oneClickStartupSummary.success_condition ?? "FastAPI /health 必须返回 Command Center 3.0 健康 JSON，/api/bootstrap/status 必须返回 runtime-mode packet，/api/desktop/preflight-cache 必须返回一键启动 packet，React/Vite 必须返回 Command Center 3.0 前端 HTML 后才打开页面。")}</p>
        <p>如果失败：{String(oneClickStartupSummary.blocked_next_action ?? "先看启动器的可操作诊断：FastAPI、bootstrap status、desktop preflight cache、React/Vite 哪段失败；再检查 8710/5173 是否被占用，或查看 .stock_ming_3/logs/command_center_3_fastapi.log 与 command_center_3_vite.log。")}</p>
        <p>诊断分段：{Array.isArray(oneClickStartupSummary.diagnostic_surfaces) ? oneClickStartupSummary.diagnostic_surfaces.join(" / ") : "FastAPI /health Command Center 3.0 JSON / bootstrap status runtime-mode packet / desktop preflight cache one-click packet / React/Vite Command Center 3.0 HTML / 8710/5173 port occupancy guidance"}</p>
        <p>安全边界：GET preflight 和 React render 不启动服务、不外联、不启用 provider/model executor、不执行真实交易。</p>
        <p>当前联通：{p0ConnectionReady ? "ready" : "check"}；需要处理：{p0BlockerCount === 0 ? "无" : `${p0BlockerCount} 项，按失败诊断处理`}。</p>
        <p>P0 本地联通收据：{String(p0LocalConnectionReceipt.status ?? "p0_local_connection_receipt_loading")}；本页只回读本地状态，不主动探测当前运行时。</p>
        <p>{String(p0LocalConnectionReceipt.ordinary_label ?? "本地一键入口会先确认 FastAPI、bootstrap status、desktop preflight cache 和 React/Vite 都就绪，再打开页面。")}</p>
        <div className="actions" aria-label="p0 ordinary primary action">
          <a href={p0OrdinaryPrimaryActionHref} aria-label="open p0 ordinary primary action">{p0OrdinaryPrimaryActionLabel}</a>
          <a href="#health" aria-label="open health status readback after p0 preflight">查看系统健康</a>
        </div>
        <p className="risk-note">{p0OrdinaryPrimaryActionBoundary}</p>
        <div aria-label="p0 ordinary reconnect to research checklist">
          <h3>P0 恢复到投研路径</h3>
          <p className="risk-note">优先读取 p0_ordinary_reconnect_rows：离线先恢复本地四段联通，联通后去下一票雷达；确认按钮之前不创建 task，这不是 14 LTG strict closeout 或 release ready 证据。</p>
          <DataLineageTable rows={p0OrdinaryReconnectRows} />
        </div>
        <div aria-label="p0 success handoff to p1 confirm">
          <h3>联通成功后的下一步</h3>
          <p className="risk-note">这条行动清单与启动器成功日志对齐：四段 ready 后去下一票雷达，输入不外联，确认按钮才创建 Tushare-first 任务。</p>
          <DataLineageTable rows={p0SuccessHandoffRows} />
        </div>
        <div aria-label="p0 ordinary launcher mode choices">
          <h3>启动模式</h3>
          <p className="risk-note">普通双击用于日常打开；只检查和联通验收不弹窗用于安全诊断，不从页面启动服务或创建 task。</p>
          <DataLineageTable rows={p0LauncherModeRows} />
        </div>
        <div aria-label="p0 ordinary shortcut installer safety checklist">
          <h3>桌面快捷入口安装状态</h3>
          <p className="risk-note">{String(desktopLauncherContract.desktop_shortcut_installer_safe_ordinary_label ?? "安全安装：不会覆盖同名普通文件；安装后验证 symlink 指向本地启动器；双击后才检查 FastAPI、bootstrap status、desktop preflight cache 和 React/Vite。")}</p>
          <DataLineageTable rows={p0ShortcutInstallerRows} />
        </div>
        <div aria-label="p0 frontend backend auto link fallback">
          <h3>本地 API 自动联通</h3>
          <p className="risk-note">前端只尝试本机 FastAPI 候选地址；失败时提示一键启动器或 check-only 诊断，本页不启动服务、不创建 task。</p>
          <p>候选地址：{Array.isArray(frontendBackendAutoLinkContract.candidate_display_urls) ? frontendBackendAutoLinkContract.candidate_display_urls.join(" / ") : String(apiBaseInfo.api_base_candidate_display_urls ?? "http://127.0.0.1:8710 / http://localhost:8710")}</p>
          <p>离线下一步：{String(frontendBackendAutoLinkContract.offline_next_action ?? "双击 stock-MING Command Center 3.command；或运行 scripts/check_command_center_3.command 做安全诊断。")}</p>
          <DataLineageTable rows={frontendBackendAutoLinkRows} />
        </div>
        <div aria-label="p0 ordinary frontend backend connection checklist">
          <h3>前后端联通状态</h3>
          <p className="risk-note">普通用户先看 FastAPI、Bootstrap status、Desktop preflight cache、React/Vite 四段是否 ready；工程行表仍在开发 / 审计详情。</p>
          <DataLineageTable rows={p0OrdinaryConnectionRows} />
        </div>
        <div aria-label="p0 ordinary startup failure diagnostics">
          <h3>启动失败定位</h3>
          <p className="risk-note">如果页面没有自动打开，按失败段看对应日志和端口；这张表只读本地 cache，不补跑启动器、不创建 task。</p>
          <DataLineageTable rows={p0FailureDiagnosticRows} />
        </div>
        <DataLineageTable rows={p0RecoverySteps} />
        <div aria-label="p0 post startup readback checklist">
          <h3>启动后复核清单</h3>
          <p className="risk-note">这张清单与启动器成功日志对齐；页面只回读本地 GET 结果，不补跑启动器、不创建 task。</p>
          <DataLineageTable rows={p0PostStartupReadbackRows} />
        </div>
        <div aria-label="p0 to p1 ordinary handoff">
          <h3>联通后搜票路径</h3>
          <p className="risk-note">预检页只说明下一步；真正的 Tushare-first 工作仍要到下一票雷达点击确认按钮。</p>
          <DataLineageTable rows={p0ToP1OrdinaryHandoffRows} />
        </div>
        <p>普通用户只看四段联通状态；完整工程行表在下方开发 / 审计详情。</p>
      </PacketCard>

      <p className="risk-note">工程联通明细、Tauri/package QA、lineage 和 raw payload 已下沉到下方开发 / 审计详情；普通用户先按上面的下一步和联通状态处理。</p>

      <details className="developer-audit-details">
        <summary>开发 / 审计详情</summary>
        <p className="risk-note">DeepSeek governed executor required before real call: {String(oneClickStartupSummary.deepseek_governed_executor_required_before_real_call ?? true)}</p>
        <p className="risk-note">frontend_backend_connection_ready / blocker_count: {String(oneClickStartupSummary.frontend_backend_connection_ready ?? false)} / {String(oneClickStartupSummary.blocker_count ?? counts.one_click_connection_blocker_count ?? 0)}；实时探针：{String(p0LocalConnectionReceipt.current_runtime_probe_executed_by_get_cache ?? false)}；current_runtime_probe_executed_by_get_cache: {String(p0LocalConnectionReceipt.current_runtime_probe_executed_by_get_cache ?? false)}</p>

      <MetricGrid
        items={[
          { label: "P0 startup", value: oneClickStartupSummary.status as string | undefined, tone: oneClickStartupSummary.frontend_backend_connection_ready === true ? "good" : "warn" },
          { label: "P0 receipt", value: p0LocalConnectionReceipt.status as string | undefined, tone: p0LocalConnectionReceipt.connection_contract_ready === true ? "good" : "warn" },
          { label: "next click", value: oneClickStartupSummary.desktop_shortcut_target_name as string | undefined },
          { label: "front/back link", value: oneClickStartupSummary.frontend_backend_connection_ready === true ? "ready" : "check", tone: oneClickStartupSummary.frontend_backend_connection_ready === true ? "good" : "warn" },
          { label: "link blockers", value: oneClickStartupSummary.blocker_count ?? counts.one_click_connection_blocker_count, tone: Number(oneClickStartupSummary.blocker_count ?? counts.one_click_connection_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "mode", value: cache.mode as string | undefined },
          { label: "API base", value: String(cache.api_base ?? "--") },
          { label: "API localhost", value: apiBaseInfo.is_localhost === true ? "yes" : "check", tone: apiBaseInfo.is_localhost === true ? "good" : "warn" },
          { label: "3.0 launcher", value: desktopLauncherContract.status as string | undefined, tone: desktopLauncherContract.status === "local_one_click_launcher_ready" ? "good" : "warn" },
          { label: "launcher executable", value: desktopLauncherContract.launcher_executable === true ? "yes" : "check", tone: desktopLauncherContract.launcher_executable === true ? "good" : "warn" },
          { label: "shortcut installer", value: desktopLauncherContract.shortcut_installer_executable === true ? "ready" : "check", tone: desktopLauncherContract.shortcut_installer_executable === true ? "good" : "warn" },
          { label: "required files", value: `${String(counts.required_file_ready_count ?? 0)} / ${String(counts.required_file_count ?? 0)}` },
          { label: "Node/npm", value: runtime.node_ready === true ? "ready" : "missing", tone: runtime.node_ready === true ? "good" : "warn" },
          { label: "Rust/Cargo", value: runtime.rust_ready === true ? "ready" : "missing", tone: runtime.rust_ready === true ? "good" : "warn" },
          { label: "Vite dev", value: runtime.vite_dev_ready === true ? "ready" : "blocked", tone: runtime.vite_dev_ready === true ? "good" : "warn" },
          { label: "Tauri dev", value: runtime.tauri_dev_ready === true ? "ready" : "needs Rust", tone: runtime.tauri_dev_ready === true ? "good" : "warn" },
          { label: "node_modules", value: runtime.node_modules_present === true ? "present" : "missing", tone: runtime.node_modules_present === true ? "good" : "warn" },
          { label: "dist", value: runtime.dist_present === true ? "present" : "missing" },
          { label: "release binary", value: tauriBuildArtifact.binary_exists === true ? "detected" : "missing", tone: tauriBuildArtifact.binary_exists === true ? "good" : "warn" },
          { label: "binary executable", value: tauriBuildArtifact.binary_executable === true ? "yes" : "no", tone: tauriBuildArtifact.binary_executable === true ? "good" : "warn" },
          { label: "binary kind", value: tauriBuildArtifact.binary_kind as string | undefined },
          { label: "app bundle", value: tauriBuildArtifact.packaged_app_bundle_detected === true ? "detected" : "missing", tone: tauriBuildArtifact.packaged_app_bundle_detected === true ? "good" : "warn" },
          { label: "DMG", value: tauriBuildArtifact.distribution_dmg_detected === true ? "detected" : "missing", tone: tauriBuildArtifact.distribution_dmg_detected === true ? "good" : "warn" },
          { label: "backend autostart", value: runtime.backend_autostart_configured === true ? "enabled" : "manual", tone: runtime.backend_autostart_configured === true ? "warn" : "good" },
          { label: "package audit", value: productionBlockerAudit.status as string | undefined, tone: productionBlockerAudit.package_ready === true ? "good" : "warn" },
          { label: "runtime contract", value: productionRuntimeContract.status as string | undefined, tone: productionRuntimeContract.config_paths_declared === true ? "good" : "warn" },
          { label: "offline UX contract", value: backendOfflineUxContract.frontend_contract_ready === true ? "source ready" : "review", tone: backendOfflineUxContract.frontend_contract_ready === true ? "good" : "warn" },
          { label: "package ready", value: productionBlockerAudit.package_ready === true ? "ready" : "blocked", tone: productionBlockerAudit.package_ready === true ? "good" : "warn" },
          { label: "tauri build", value: productionBlockerAudit.tauri_build_verified === true ? "verified" : "not verified", tone: productionBlockerAudit.tauri_build_verified === true ? "good" : "warn" },
          { label: "config/log paths", value: productionBlockerAudit.config_log_paths_declared === true ? "declared" : "pending", tone: productionBlockerAudit.config_log_paths_declared === true ? "good" : "warn" },
          { label: "packaged offline UX", value: productionRuntimeContract.backend_offline_ui_packaged_runtime_verified === true ? "verified" : "pending", tone: productionRuntimeContract.backend_offline_ui_packaged_runtime_verified === true ? "good" : "warn" },
          { label: "packaged QA", value: packagedRuntimeQaContract.status as string | undefined, tone: packagedRuntimeQaContract.packaged_runtime_validated === true ? "good" : "warn" },
          { label: "binary QA", value: packagedRuntimeQaContract.release_binary_qa_passed === true ? "passed" : "pending", tone: packagedRuntimeQaContract.release_binary_qa_passed === true ? "good" : "warn" },
          { label: "pending QA", value: packagedRuntimeQaContract.pending_qa_count as number | undefined, tone: Number(packagedRuntimeQaContract.pending_qa_count ?? 0) > 0 ? "warn" : "good" },
          { label: "release manifest", value: tauriReleaseManifestContract.local_release_manifest_ready === true ? "ready" : "review", tone: tauriReleaseManifestContract.local_release_manifest_ready === true ? "good" : "warn" },
          { label: "manifest blockers", value: tauriReleaseManifestContract.production_blocker_count as number | undefined, tone: Number(tauriReleaseManifestContract.production_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "receipt ready", value: productionPackageReadinessReceipt.local_receipt_ready === true ? "yes" : "review", tone: productionPackageReadinessReceipt.local_receipt_ready === true ? "good" : "warn" },
          { label: "receipt blockers", value: productionPackageReadinessReceipt.blocking_criterion_count ?? counts.production_package_readiness_receipt_blocker_count, tone: Number(productionPackageReadinessReceipt.blocking_criterion_count ?? counts.production_package_readiness_receipt_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "durable recipe", value: tauriPackageDurableEvidenceRecipe.local_recipe_ready === true ? "ready" : "review", tone: tauriPackageDurableEvidenceRecipe.local_recipe_ready === true ? "good" : "warn" },
          { label: "durable blockers", value: tauriPackageDurableEvidenceRecipe.durable_evidence_blocker_count ?? counts.tauri_package_durable_evidence_blocker_count, tone: Number(tauriPackageDurableEvidenceRecipe.durable_evidence_blocker_count ?? counts.tauri_package_durable_evidence_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "package blockers", value: productionBlockerAudit.blocker_count as number | undefined, tone: Number(productionBlockerAudit.blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "cache envelope ledger", value: cacheEnvelopeLedger.length },
          { label: "cache warnings", value: cacheWarnings.length }
        ]}
      />

      <div className="grid">
        <PacketCard title="桌面壳边界" subtitle="GET /api/desktop/preflight-cache 只读检查本地 scaffold" status="cache_only">
          <p>本页只读取 FastAPI desktop preflight cache，不运行 npm install、npm build、cargo 或 Tauri。</p>
          <p>不会调用 Tushare、DeepSeek 或 GitHub，不读取 token/key，不执行真实交易，不修改 strategy action。</p>
          <p>Rust/Cargo 缺失只影响 Tauri dev/build；Vite 前端和 FastAPI cache API 仍可继续推进。</p>
          <p>P0 本地一键启动器会启动或复用 FastAPI/Vite，等待前后端联通后才打开页面；本预检页不运行它。</p>
          <p>3.0 桌面快捷方式 installer 是 scripts/install_command_center_3_desktop_shortcut.sh；只有用户手动运行时才把启动脚本 symlink 到桌面。</p>
          <p>3.0 一键入口是 scripts/start_command_center_3.command；只在用户运行时启动本地 FastAPI/Vite，不启用 provider/model executor。</p>
          <p>备用路径仍是 scripts/dev_server.sh 加 Vite/Tauri dev；只供开发排障，不由本预检页执行。</p>
        </PacketCard>

        <PacketCard title="预检策略" subtitle="cache API 永不外联；构建命令必须人工触发" status="policy">
          <p>does_not_run_npm_install: {String(policy.does_not_run_npm_install ?? true)}</p>
          <p>does_not_run_npm_build: {String(policy.does_not_run_npm_build ?? true)}</p>
          <p>does_not_run_tauri: {String(policy.does_not_run_tauri ?? true)}</p>
          <p>does_not_run_cargo: {String(policy.does_not_run_cargo ?? true)}</p>
          <p>frontend_must_use_fastapi_api_client: {String(policy.frontend_must_use_fastapi_api_client ?? true)}</p>
          <p>backend_autostart_enabled: {String(policy.backend_autostart_enabled ?? false)}</p>
          <p>api_base_must_be_localhost: {String(policy.api_base_must_be_localhost ?? true)}</p>
          <p>production_runtime_contract_is_path_only: {String(policy.production_runtime_contract_is_path_only ?? true)}</p>
          <p>does_not_read_config_values: {String(policy.does_not_read_config_values ?? true)}</p>
          <p>does_not_write_log_files: {String(policy.does_not_write_log_files ?? true)}</p>
        </PacketCard>
      </div>

      <PacketCard title="开发 / 审计详情：P0 联通明细" subtitle="普通用户先看上方摘要；这里保留本地只读检查行" status="cache_only">
        <DataLineageTable rows={p0LocalConnectionRows} />
        <DataLineageTable rows={oneClickConnectionRows} />
      </PacketCard>

      <PacketCard title="备用开发启动顺序" subtitle="一键入口优先；预检页不执行命令" status="manual">
        <DataLineageTable rows={devLaunchPlan} />
      </PacketCard>

      <PacketCard title="Command Center 3.0 本地快捷入口" subtitle="P0 一键启动前后端；不是 production packaged app" status={String(desktopLauncherContract.status ?? "local_launcher_contract_missing")}>
        <p>schema_version: {String(desktopLauncherContract.schema_version ?? "command_center_3_local_launcher_contract.v1")}</p>
        <p>scope: {String(desktopLauncherContract.scope ?? "local_one_click_frontend_backend_launcher_not_production_package")}</p>
        <p>launcher_path: {String(desktopLauncherContract.launcher_path ?? "scripts/start_command_center_3.command")}</p>
        <p>shortcut_installer_path: {String(desktopLauncherContract.shortcut_installer_path ?? "scripts/install_command_center_3_desktop_shortcut.sh")}</p>
        <p>desktop_shortcut_target_name: {String(desktopLauncherContract.desktop_shortcut_target_name ?? "stock-MING Command Center 3.command")}</p>
        <p>desktop_shortcut_install_command: {String(desktopLauncherContract.desktop_shortcut_install_command ?? "scripts/install_command_center_3_desktop_shortcut.sh")}</p>
        <p>shortcut_installer_exists / executable / creates_symlink: {String(desktopLauncherContract.shortcut_installer_exists ?? false)} / {String(desktopLauncherContract.shortcut_installer_executable ?? false)} / {String(desktopLauncherContract.desktop_shortcut_installer_creates_symlink ?? false)}</p>
        <p>shortcut_installer_starts_services / reads_credentials: {String(desktopLauncherContract.desktop_shortcut_installer_starts_services ?? false)} / {String(desktopLauncherContract.desktop_shortcut_installer_reads_credentials ?? false)}</p>
        <p>uses_project_venv_first / allows_system_python_only_when_explicit: {String(desktopLauncherContract.uses_project_venv_first ?? false)} / {String(desktopLauncherContract.allows_system_python_only_when_explicit ?? false)}</p>
        <p>starts_fastapi_when_user_runs / starts_vite_when_user_runs / opens_local_browser_when_user_runs: {String(desktopLauncherContract.starts_fastapi_when_user_runs ?? false)} / {String(desktopLauncherContract.starts_vite_when_user_runs ?? false)} / {String(desktopLauncherContract.opens_local_browser_when_user_runs ?? false)}</p>
        <p>cache_get_starts_launcher / cache_get_installs_shortcut / cache_get_starts_fastapi / cache_get_starts_vite: {String(desktopLauncherContract.cache_get_starts_launcher ?? false)} / {String(desktopLauncherContract.cache_get_installs_shortcut ?? false)} / {String(desktopLauncherContract.cache_get_starts_fastapi ?? false)} / {String(desktopLauncherContract.cache_get_starts_vite ?? false)}</p>
        <p>production_package_complete: {String(desktopLauncherContract.production_package_complete ?? false)}</p>
        <p>external_calls_triggered / tushare_called / deepseek_called / github_called: {String(desktopLauncherContract.external_calls_triggered ?? false)} / {String(desktopLauncherContract.tushare_called ?? false)} / {String(desktopLauncherContract.deepseek_called ?? false)} / {String(desktopLauncherContract.github_called ?? false)}</p>
        <DataLineageTable rows={desktopLauncherRows} />
        <DataLineageTable rows={rows(desktopLauncherContract.call_ledger)} />
      </PacketCard>

      <PacketCard title="生产打包路线" subtitle="只展示命令顺序；本页不运行 build 或 Tauri" status="manual">
        <DataLineageTable rows={productionLaunchPlan} />
      </PacketCard>

      <PacketCard title="Tauri production runtime contract" subtitle="路径和启动策略只读声明；不读取配置、不写日志、不启动后端" status={String(productionRuntimeContract.status ?? "runtime_contract_ready_packaged_validation_pending")}>
        <p>backend_startup_strategy: {String(productionRuntimeContract.backend_startup_strategy ?? "manual_fastapi_process_current_sidecar_pending")}</p>
        <p>config_file_policy: {String(productionRuntimeContract.config_file_policy ?? "~/.stock_ming_3/desktop.local.json")}</p>
        <p>log_file_policy: {String(productionRuntimeContract.log_file_policy ?? "~/.stock_ming_3/logs/command_center_3.log")}</p>
        <p>packaged_runtime_validated: {String(productionRuntimeContract.packaged_runtime_validated ?? false)}</p>
        <p>token_key_frontend_exposure: {String(productionRuntimeContract.token_key_frontend_exposure ?? false)}</p>
        <DataLineageTable rows={productionRuntimeRows} />
      </PacketCard>

      <PacketCard title="Tauri backend offline UX contract" subtitle="源码合同已可审计；packaged runtime 仍需真实打开验证" status={String(backendOfflineUxContract.status ?? "frontend_offline_notice_contract_incomplete")}>
        <p>backend_offline_error_code: {String(backendOfflineUxContract.backend_offline_error_code ?? "backend_offline_or_unreachable")}</p>
        <p>frontend_contract_ready: {String(backendOfflineUxContract.frontend_contract_ready ?? false)}</p>
        <p>api_client_fetch_error_fallback_ready: {String(backendOfflineUxContract.api_client_fetch_error_fallback_ready ?? false)}</p>
        <p>api_base_display_sanitized: {String(backendOfflineUxContract.api_base_display_sanitized ?? false)}</p>
        <p>offline_notice_component_ready: {String(backendOfflineUxContract.offline_notice_component_ready ?? false)}</p>
        <p>page_state_banner_integration_ready: {String(backendOfflineUxContract.page_state_banner_integration_ready ?? false)}</p>
        <p>backend_offline_ui_packaged_runtime_verified: {String(backendOfflineUxContract.backend_offline_ui_packaged_runtime_verified ?? false)}</p>
        <DataLineageTable rows={backendOfflineUxRows} />
      </PacketCard>

      <PacketCard title="Tauri 生产包阻断审计" subtitle="preflight 不是 production package complete" status={String(productionBlockerAudit.status ?? "production_package_blocked")}>
        <p>scope: {String(productionBlockerAudit.scope ?? "local_preflight_optional_build_artifact_detection_not_packaged_runtime_qa")}</p>
        <p>package_ready: {String(productionBlockerAudit.package_ready ?? false)}</p>
        <p>tauri_build_verified: {String(productionBlockerAudit.tauri_build_verified ?? false)}</p>
        <p>tauri_build_artifact_status: {String(productionBlockerAudit.tauri_build_artifact_status ?? tauriBuildArtifact.status ?? "artifact_missing")}</p>
        <p>tauri_build_artifact_path: {String(productionBlockerAudit.tauri_build_artifact_path ?? tauriBuildArtifact.binary_path ?? "desktop/src-tauri/target/release/stock_ming_command_center")}</p>
        <p>tauri_build_artifact_size_bytes: {String(productionBlockerAudit.tauri_build_artifact_size_bytes ?? tauriBuildArtifact.binary_size_bytes ?? 0)}</p>
        <p>binary_executable / binary_kind: {String(tauriBuildArtifact.binary_executable ?? false)} / {String(tauriBuildArtifact.binary_kind ?? "missing")}</p>
        <p>bundle_app_count / packaged_app_bundle_detected: {String(tauriBuildArtifact.bundle_app_count ?? 0)} / {String(tauriBuildArtifact.packaged_app_bundle_detected ?? false)}</p>
        <p>bundle_dmg_count / distribution_dmg_detected: {String(tauriBuildArtifact.bundle_dmg_count ?? 0)} / {String(tauriBuildArtifact.distribution_dmg_detected ?? false)}</p>
        <p>manual_backend_launch_required: {String(productionBlockerAudit.manual_backend_launch_required ?? true)}</p>
        <p>backend_offline_ui_packaged_runtime_verified: {String(productionBlockerAudit.backend_offline_ui_packaged_runtime_verified ?? false)}</p>
        <p>backend_offline_ux_contract_status: {String(productionBlockerAudit.backend_offline_ux_contract_status ?? backendOfflineUxContract.status ?? "frontend_offline_notice_contract_incomplete")}</p>
        <p>backend_offline_ux_frontend_contract_ready: {String(productionBlockerAudit.backend_offline_ux_frontend_contract_ready ?? false)}</p>
        <p>config_log_paths_declared: {String(productionBlockerAudit.config_log_paths_declared ?? false)}</p>
        <p>production_runtime_contract_status: {String(productionBlockerAudit.production_runtime_contract_status ?? "runtime_contract_ready_packaged_validation_pending")}</p>
        <p>macos_signing_notarization_ready: {String(productionBlockerAudit.macos_signing_notarization_ready ?? false)}</p>
        <p>production_readiness_status: {String(productionReadiness.status ?? "desktop_scaffold_partial")}</p>
      </PacketCard>

      <PacketCard title="Tauri 生产包阻断项" subtitle="逐项说明 dev/preflight 与 production package 的缺口" status="blockers">
        <DataLineageTable rows={productionBlockerRows} />
      </PacketCard>

      <PacketCard title="Tauri packaged runtime QA contract" subtitle="生产包验收矩阵；只读合同，不运行 Tauri、不打开 packaged app" status={String(packagedRuntimeQaContract.status ?? "packaged_runtime_qa_contract_missing")}>
        <p>scope: {String(packagedRuntimeQaContract.scope ?? "local_static_qa_matrix_not_packaged_runtime_execution")}</p>
        <p>qa_contract_ready: {String(packagedRuntimeQaContract.qa_contract_ready ?? false)}</p>
        <p>packaged_runtime_validated: {String(packagedRuntimeQaContract.packaged_runtime_validated ?? false)}</p>
        <p>release_binary_qa_passed / release_binary_executable: {String(packagedRuntimeQaContract.release_binary_qa_passed ?? false)} / {String(packagedRuntimeQaContract.release_binary_executable ?? false)}</p>
        <p>packaged_app_bundle_detected / distribution_dmg_detected: {String(packagedRuntimeQaContract.packaged_app_bundle_detected ?? false)} / {String(packagedRuntimeQaContract.distribution_dmg_detected ?? false)}</p>
        <p>browser_or_packaged_app_opened: {String(packagedRuntimeQaContract.browser_or_packaged_app_opened ?? false)}</p>
        <p>npm_or_cargo_executed: {String(packagedRuntimeQaContract.npm_or_cargo_executed ?? false)}</p>
        <p>config_values_read: {String(packagedRuntimeQaContract.config_values_read ?? false)}</p>
        <p>log_files_written: {String(packagedRuntimeQaContract.log_files_written ?? false)}</p>
        <DataLineageTable rows={packagedRuntimeQaRows} />
      </PacketCard>

      <PacketCard title="Tauri release manifest contract" subtitle="发布清单合同；只读检查身份、dist、artifact ignore、后端策略、配置/日志路径和签名缺口" status={String(tauriReleaseManifestContract.status ?? "release_manifest_contract_missing")}>
        <p>schema_version: {String(tauriReleaseManifestContract.schema_version ?? "tauri_release_manifest_contract.v1")}</p>
        <p>scope: {String(tauriReleaseManifestContract.scope ?? "local_tauri_release_manifest_contract_no_build_or_runtime_execution")}</p>
        <p>product / version / identifier: {String(tauriReleaseManifestContract.product_name ?? "stock-MING Command Center")} / {String(tauriReleaseManifestContract.app_version ?? "3.0.0")} / {String(tauriReleaseManifestContract.bundle_identifier ?? "com.stockming.commandcenter")}</p>
        <p>frontend_dist / before_build_command / dev_url: {String(tauriReleaseManifestContract.frontend_dist ?? "../dist")} / {String(tauriReleaseManifestContract.before_build_command ?? "npm run build")} / {String(tauriReleaseManifestContract.dev_url ?? "http://127.0.0.1:5173")}</p>
        <p>icon_asset_present / desktop_dist_gitignored / tauri_target_gitignored: {String(tauriReleaseManifestContract.icon_asset_present ?? false)} / {String(tauriReleaseManifestContract.desktop_dist_gitignored ?? false)} / {String(tauriReleaseManifestContract.tauri_target_gitignored ?? false)}</p>
        <p>backend_startup_strategy: {String(tauriReleaseManifestContract.backend_startup_strategy ?? "manual_fastapi_process_current_sidecar_pending")}</p>
        <p>config_file_policy / log_file_policy: {String(tauriReleaseManifestContract.config_file_policy ?? "~/.stock_ming_3/desktop.local.json")} / {String(tauriReleaseManifestContract.log_file_policy ?? "~/.stock_ming_3/logs/command_center_3.log")}</p>
        <p>local_release_manifest_ready / ready_for_production_package_promotion: {String(tauriReleaseManifestContract.local_release_manifest_ready ?? false)} / {String(tauriReleaseManifestContract.ready_for_production_package_promotion ?? false)}</p>
        <p>tauri_build_executed / packaged_app_opened / fastapi_started: {String(tauriReleaseManifestContract.tauri_build_executed ?? false)} / {String(tauriReleaseManifestContract.packaged_app_opened ?? false)} / {String(tauriReleaseManifestContract.fastapi_started ?? false)}</p>
        <p>config_values_read / log_files_written / signing_notarization_done: {String(tauriReleaseManifestContract.config_values_read ?? false)} / {String(tauriReleaseManifestContract.log_files_written ?? false)} / {String(tauriReleaseManifestContract.signing_notarization_done ?? false)}</p>
        <p>external_calls_triggered / tushare_called / deepseek_called / github_called: {String(tauriReleaseManifestContract.external_calls_triggered ?? false)} / {String(tauriReleaseManifestContract.tushare_called ?? false)} / {String(tauriReleaseManifestContract.deepseek_called ?? false)} / {String(tauriReleaseManifestContract.github_called ?? false)}</p>
        <DataLineageTable rows={tauriReleaseManifestRows} />
        <DataLineageTable rows={rows(tauriReleaseManifestContract.call_ledger)} />
      </PacketCard>

      <PacketCard title="Tauri production package readiness receipt" subtitle="LTG-09 下一步收据；只允许显式 build / packaged runtime QA review" status={String(productionPackageReadinessReceipt.status ?? "tauri_package_readiness_receipt_ready_build_pending")}>
        <p>schema_version: {String(productionPackageReadinessReceipt.schema_version ?? "tauri_production_package_readiness_receipt.v1")}</p>
        <p>scope: {String(productionPackageReadinessReceipt.scope ?? "local_tauri_production_package_readiness_receipt_no_build_or_runtime_execution")}</p>
        <p>local_receipt_ready / ready_for_explicit_tauri_build: {String(productionPackageReadinessReceipt.local_receipt_ready ?? true)} / {String(productionPackageReadinessReceipt.ready_for_explicit_tauri_build ?? true)}</p>
        <p>ready_for_packaged_runtime_qa / ready_for_production_package_promotion: {String(productionPackageReadinessReceipt.ready_for_packaged_runtime_qa ?? false)} / {String(productionPackageReadinessReceipt.ready_for_production_package_promotion ?? false)}</p>
        <p>allowed_next_step: {String(productionPackageReadinessReceipt.allowed_next_step ?? "explicit_tauri_build_then_packaged_runtime_qa_review")}</p>
        <p>production_package_complete: {String(productionPackageReadinessReceipt.production_package_complete ?? false)}</p>
        <p>tauri_build_executed_by_receipt / npm_or_cargo_executed_by_receipt: {String(productionPackageReadinessReceipt.tauri_build_executed_by_receipt ?? false)} / {String(productionPackageReadinessReceipt.npm_or_cargo_executed_by_receipt ?? false)}</p>
        <p>tauri_runtime_started_by_receipt / packaged_app_opened_by_receipt / fastapi_started_by_receipt: {String(productionPackageReadinessReceipt.tauri_runtime_started_by_receipt ?? false)} / {String(productionPackageReadinessReceipt.packaged_app_opened_by_receipt ?? false)} / {String(productionPackageReadinessReceipt.fastapi_started_by_receipt ?? false)}</p>
        <p>config_values_read_by_receipt / log_files_written_by_receipt: {String(productionPackageReadinessReceipt.config_values_read_by_receipt ?? false)} / {String(productionPackageReadinessReceipt.log_files_written_by_receipt ?? false)}</p>
        <p>receipt_external_calls_triggered / tushare_called / deepseek_called / github_called: {String(productionPackageReadinessReceipt.receipt_external_calls_triggered ?? false)} / {String(productionPackageReadinessReceipt.tushare_called ?? false)} / {String(productionPackageReadinessReceipt.deepseek_called ?? false)} / {String(productionPackageReadinessReceipt.github_called ?? false)}</p>
        <p>not_allowed_next_steps: {Array.isArray(productionPackageReadinessReceipt.not_allowed_next_steps) ? productionPackageReadinessReceipt.not_allowed_next_steps.join(" / ") : "GET /api/desktop/preflight-cache npm build / GET /api/desktop/preflight-cache tauri build / GET /api/desktop/preflight-cache packaged app launch / release artifact detection as packaged runtime QA / preflight receipt as production package completion"}</p>
        <DataLineageTable rows={productionPackageReadinessReceiptRows} />
        <DataLineageTable rows={rows(productionPackageReadinessReceipt.call_ledger)} />
      </PacketCard>

      <PacketCard title="Tauri package durable evidence recipe" subtitle="LTG-09 生产包直接证据清单；只读，不运行 build/runtime" status={String(tauriPackageDurableEvidenceRecipe.status ?? "tauri_package_durable_evidence_recipe_ready_production_pending")}>
        <p>schema_version: {String(tauriPackageDurableEvidenceRecipe.schema_version ?? "tauri_package_durable_evidence_recipe.v1")}</p>
        <p>scope: {String(tauriPackageDurableEvidenceRecipe.scope ?? "local_tauri_package_durable_evidence_recipe_no_build_or_runtime_execution")}</p>
        <p>local_recipe_ready: {String(tauriPackageDurableEvidenceRecipe.local_recipe_ready ?? false)}</p>
        <p>durable_evidence_complete / durable_promotion_ready: {String(tauriPackageDurableEvidenceRecipe.durable_evidence_complete ?? false)} / {String(tauriPackageDurableEvidenceRecipe.durable_promotion_ready ?? false)}</p>
        <p>production_package_complete: {String(tauriPackageDurableEvidenceRecipe.production_package_complete ?? false)}</p>
        <p>allowed_next_step: {String(tauriPackageDurableEvidenceRecipe.allowed_next_step ?? "run_explicit_tauri_build_then_packaged_runtime_qa_then_durable_promotion_review")}</p>
        <p>preflight_runs_build / preflight_opens_packaged_app / preflight_starts_fastapi: {String(tauriPackageDurableEvidenceRecipe.preflight_runs_build ?? false)} / {String(tauriPackageDurableEvidenceRecipe.preflight_opens_packaged_app ?? false)} / {String(tauriPackageDurableEvidenceRecipe.preflight_starts_fastapi ?? false)}</p>
        <p>preflight_reads_config_values / preflight_writes_log_files: {String(tauriPackageDurableEvidenceRecipe.preflight_reads_config_values ?? false)} / {String(tauriPackageDurableEvidenceRecipe.preflight_writes_log_files ?? false)}</p>
        <p>not_allowed_next_steps: {Array.isArray(tauriPackageDurableEvidenceRecipe.not_allowed_next_steps) ? tauriPackageDurableEvidenceRecipe.not_allowed_next_steps.join(" / ") : "release binary detection as packaged app launch QA / readiness receipt as production package completion / GET preflight build/runtime execution"}</p>
        <DataLineageTable rows={[tauriPackageDurableEvidenceRecipe]} />
        <DataLineageTable rows={tauriPackageDurableEvidenceRows} />
        <DataLineageTable rows={rows(tauriPackageDurableEvidenceRecipe.call_ledger)} />
      </PacketCard>

      <PacketCard title="FastAPI 地址合同" subtitle="前端只连接本地 FastAPI，不保存 token/key" status={String(apiBaseInfo.is_localhost === true ? "localhost" : "review")}>
        <DataLineageTable rows={Object.entries(apiBaseInfo).map(([field, value]) => ({ field, value: String(value) }))} />
      </PacketCard>

      <PacketCard title="Scaffold 文件" subtitle="React/Vite/Tauri 必要文件是否存在" status="files">
        <DataLineageTable rows={rows(cache.file_rows)} />
      </PacketCard>

      <PacketCard title="本地命令可见性" subtitle="只检查命令是否存在，不运行 --version / build / dev" status="commands">
        <DataLineageTable rows={rows(cache.command_rows)} />
      </PacketCard>

      <PacketCard title="调用血缘" subtitle="payload 内部 local_desktop_shell_preflight_cache；不外联" status="lineage">
        <DataLineageTable rows={payloadCallLedger} />
      </PacketCard>

      <PacketCard title="GET desktop preflight envelope call_ledger" subtitle="GET /api/desktop/preflight-cache 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={cacheEnvelopeLedger} />
      </PacketCard>

      <PacketCard title="GET desktop preflight envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={cacheWarnings.map((warning, index) => ({ index: index + 1, warning }))} />
      </PacketCard>

      <PacketCard title="原始 desktop preflight cache payload" subtitle="调试用 JSON；不含 token/key" status="safe">
        <JsonDetails title="desktop shell preflight raw" data={cache} />
        <JsonDetails title="tauri release manifest raw" data={tauriReleaseManifestContract} />
        <JsonDetails title="tauri production package readiness receipt raw" data={productionPackageReadinessReceipt} />
      </PacketCard>
      </details>
    </>
  );
}
