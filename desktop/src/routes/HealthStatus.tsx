import { useEffect, useState } from "react";
import { getDesktopPreflightCache, getHealth, getMigrationStatus } from "../api/client";
import BackendOfflineNotice from "../components/BackendOfflineNotice";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

export default function HealthStatus() {
  const [health, setHealth] = useState<Record<string, unknown>>({});
  const [healthEnvelopeLedger, setHealthEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [healthEnvelopeWarnings, setHealthEnvelopeWarnings] = useState<Array<string>>([]);
  const [healthError, setHealthError] = useState("");
  const [migration, setMigration] = useState<Record<string, unknown>>({});
  const [desktopPreflight, setDesktopPreflight] = useState<Record<string, unknown>>({});
  const [desktopPreflightEnvelopeLedger, setDesktopPreflightEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [desktopPreflightEnvelopeWarnings, setDesktopPreflightEnvelopeWarnings] = useState<Array<string>>([]);
  const [desktopPreflightError, setDesktopPreflightError] = useState("");

  useEffect(() => {
    void getHealth().then((res) => {
      setHealth(res.data);
      setHealthEnvelopeLedger(res.call_ledger ?? []);
      setHealthEnvelopeWarnings(res.warnings ?? []);
      setHealthError(res.error ?? "");
    });
    void getMigrationStatus().then((res) => setMigration(res.data));
    void getDesktopPreflightCache().then((res) => {
      setDesktopPreflight(res.data);
      setDesktopPreflightEnvelopeLedger(res.call_ledger ?? []);
      setDesktopPreflightEnvelopeWarnings(res.warnings ?? []);
      setDesktopPreflightError(res.error ?? "");
    });
  }, []);

  const modelStrategy = health.deepseek_model_strategy as Record<string, unknown> | undefined;
  const modelStrategyRows = [
    { purpose: "default", model: modelStrategy?.default ?? "--", grade: "解释默认" },
    { purpose: "explain", model: modelStrategy?.explain ?? "--", grade: "解释" },
    { purpose: "projection", model: modelStrategy?.projection ?? "--", grade: "次日图谱解释" },
    { purpose: "factor_explain", model: modelStrategy?.factor_explain ?? "--", grade: "因子解释" },
    { purpose: "fast", model: modelStrategy?.fast ?? "--", grade: "轻量" },
    { purpose: "healthcheck", model: modelStrategy?.healthcheck ?? "--", grade: "健康检查" },
    { purpose: "feeder", model: modelStrategy?.feeder ?? "--", grade: "自动喂数" }
  ];
  const progress = (migration.progress_baseline as Array<Record<string, unknown>> | undefined) ?? [];
  const migrationPolicy = migration.api_policy as Record<string, unknown> | undefined;
  const healthWarnings = healthEnvelopeWarnings.length ? healthEnvelopeWarnings : ((health.warnings as Array<string> | undefined) ?? []);
  const oneClickStartupSummary = (desktopPreflight.one_click_startup_summary as Record<string, unknown> | undefined) ?? {};
  const p0LocalConnectionReceipt = (desktopPreflight.p0_local_connection_receipt as Record<string, unknown> | undefined) ?? {};
  const desktopLauncherContract = (desktopPreflight.desktop_launcher_contract as Record<string, unknown> | undefined) ?? {};
  const oneClickConnectionRows = (desktopPreflight.one_click_connection_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const p0ConnectionReady = oneClickStartupSummary.frontend_backend_connection_ready === true;
  const p0RecoverySteps = rows(desktopPreflight.p0_recovery_steps).length ? rows(desktopPreflight.p0_recovery_steps) : [
    { step: "1", title: "打开本地一键入口", action: "双击 stock-MING Command Center 3.command；或运行 scripts/start_command_center_3.command。" },
    { step: "2", title: "按启动器诊断定位失败段", action: "先看 FastAPI、bootstrap status、desktop preflight cache、React/Vite 哪一段没有 ready。" },
    { step: "3", title: "刷新健康页确认联通", action: "确认 P0 front/back、P0 receipt 和 one-click launcher 都为 ready。" }
  ];
  const p0OrdinaryConnectionRows = rows(desktopPreflight.p0_ordinary_connection_rows).length ? rows(desktopPreflight.p0_ordinary_connection_rows) : [
    {
      环节: "FastAPI",
      当前状态: p0ConnectionReady ? "ready" : "check",
      用户下一步: "如果未 ready，先看启动器 FastAPI 诊断和 command_center_3_fastapi.log。",
      通过条件: "本地 /health 返回 Command Center 3.0 JSON，且 external_calls_on_startup=false。",
      边界: "只读健康检查；GET preflight 不启动 FastAPI、不创建 task。"
    },
    {
      环节: "Bootstrap status",
      当前状态: p0ConnectionReady ? "ready" : "check",
      用户下一步: "如果未 ready，回启动器确认 bootstrap status 段是否返回 runtime-mode packet。",
      通过条件: "本地 /api/bootstrap/status 返回 command_center_3_bootstrap_runtime_mode_packet。",
      边界: "只读运行模式；不写配置、不启用 live_light。"
    },
    {
      环节: "Desktop preflight cache",
      当前状态: p0ConnectionReady ? "ready" : "check",
      用户下一步: "如果未 ready，回启动器确认 desktop preflight cache 段是否返回一键启动 packet。",
      通过条件: "本地 /api/desktop/preflight-cache 返回 command_center_3_desktop_shell_preflight_cache。",
      边界: "只读一键启动 packet；不运行 launcher、不探测当前运行时。"
    },
    {
      环节: "React/Vite",
      当前状态: p0ConnectionReady ? "ready" : "check",
      用户下一步: "如果未 ready，检查 5173 是否被占用并查看 command_center_3_vite.log。",
      通过条件: "本地 Vite 返回 Command Center 3.0 前端 HTML。",
      边界: "只读前端入口；不调用 Tushare/DeepSeek/GitHub、不执行真实交易。"
    }
  ];
  const p0FailureDiagnosticRows = rows(desktopPreflight.p0_failure_diagnostic_rows).length ? rows(desktopPreflight.p0_failure_diagnostic_rows) : [
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
  const p0PostStartupReadbackRows = rows(desktopPreflight.p0_post_startup_readback_rows).length ? rows(desktopPreflight.p0_post_startup_readback_rows) : [
    {
      复核项: "FastAPI health",
      当前状态: p0ConnectionReady ? "ready" : "check",
      页面看法: "系统健康和今日作战台显示本地前后端已联通。",
      通过条件: "GET /health 返回 Command Center 3.0 JSON，且 external_calls_on_startup=false。",
      失败下一步: "回启动器日志看 FastAPI 诊断，再检查 8710 是否被占用。",
      边界: "只读健康检查，不启动服务、不创建 task。"
    },
    {
      复核项: "Bootstrap status",
      当前状态: p0ConnectionReady ? "ready" : "check",
      页面看法: "普通入口显示运行模式和启动边界。",
      通过条件: "GET /api/bootstrap/status 返回 runtime-mode packet。",
      失败下一步: "回启动器日志看 bootstrap status 诊断。",
      边界: "只读运行模式，不写配置、不启用 live_light。"
    },
    {
      复核项: "Desktop preflight cache",
      当前状态: p0ConnectionReady ? "ready" : "check",
      页面看法: "普通入口和系统健康显示同一条 P0 一键启动 packet。",
      通过条件: "GET /api/desktop/preflight-cache 返回一键启动 packet，且 external_calls_triggered=false。",
      失败下一步: "回启动器日志看 desktop preflight cache 诊断。",
      边界: "只读预检回放，不启动服务、不创建 task。"
    },
    {
      复核项: "React/Vite 前端",
      当前状态: p0ConnectionReady ? "ready" : "check",
      页面看法: "浏览器打开 Command Center 3.0 今日作战台。",
      通过条件: "Vite 返回 Command Center 3.0 HTML，且页面入口可点击到预检、健康、雷达和量化推演。",
      失败下一步: "回启动器日志看 React/Vite 诊断，再检查 5173 是否被占用。",
      边界: "只读前端入口，不调用 Tushare/DeepSeek/GitHub、不执行真实交易。"
    }
  ];
  const p0ToP1OrdinaryHandoffRows = rows(desktopPreflight.p0_to_p1_ordinary_handoff_rows).length ? rows(desktopPreflight.p0_to_p1_ordinary_handoff_rows) : [
    {
      步骤: "1. 确认本地联通",
      用户动作: "先看 FastAPI、Bootstrap status、Desktop preflight cache、React/Vite 四段是否 ready。",
      当前状态: p0ConnectionReady ? "ready：可以进入普通投研入口" : "check：先恢复本地一键入口",
      下一步: p0ConnectionReady ? "回到今日作战台首页确认股票代码；需要详情再打开下一票雷达。" : "回到启动器诊断或桌面壳预检。",
      边界: "只读 GET health / preflight cache；不启动服务、不创建 task。"
    },
    {
      步骤: "2. 首页确认股票代码",
      用户动作: "去今日作战台首页确认卡；需要详情再打开下一票雷达确认输入区。",
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
  const desktopPreflightWarnings = desktopPreflightEnvelopeWarnings.length ? desktopPreflightEnvelopeWarnings : ((desktopPreflight.warnings as Array<string> | undefined) ?? []);

  return (
    <>
      <div className="page-head">
        <h1>系统健康</h1>
        <StatusBadge label={String(health.status ?? "loading")} tone={health.status === "ok" ? "good" : "warn"} />
      </div>
      <BackendOfflineNotice
        error={healthError || desktopPreflightError}
        warnings={[...healthWarnings, ...desktopPreflightWarnings]}
      />

      <PacketCard title="P0 前后端联通摘要" subtitle="普通用户先确认本地 FastAPI / React 是否已联通" status={String(oneClickStartupSummary.status ?? "preflight_cache_loading")}>
        <p>联通状态：{p0ConnectionReady ? "已具备本地一键联通条件" : "需要检查本地一键入口"}</p>
        <p>下一步：{String(oneClickStartupSummary.what_user_should_click_next ?? "打开桌面壳预检，按本地快捷入口重启。")}</p>
        <p>快捷入口：{String(desktopLauncherContract.desktop_shortcut_target_name ?? "stock-MING Command Center 3.command")}</p>
        <p>成功条件：{String(oneClickStartupSummary.success_condition ?? "FastAPI /health 必须返回 Command Center 3.0 健康 JSON，/api/bootstrap/status 必须返回 runtime-mode packet，/api/desktop/preflight-cache 必须返回一键启动 packet，React/Vite 必须返回 Command Center 3.0 前端 HTML 后才打开页面。")}</p>
        <p>失败处理：{String(oneClickStartupSummary.blocked_next_action ?? "先看启动器的可操作诊断：FastAPI、bootstrap status、desktop preflight cache、React/Vite 哪段失败；再检查 8710/5173 是否被占用，或进入桌面壳预检。")}</p>
        <p>诊断分段：{Array.isArray(oneClickStartupSummary.diagnostic_surfaces) ? oneClickStartupSummary.diagnostic_surfaces.join(" / ") : "FastAPI /health Command Center 3.0 JSON / bootstrap status runtime-mode packet / desktop preflight cache one-click packet / React/Vite Command Center 3.0 HTML / 8710/5173 port occupancy guidance"}</p>
        <p>P0 本地联通收据：{String(p0LocalConnectionReceipt.ordinary_label ?? "本地一键入口会先确认 FastAPI、bootstrap status、desktop preflight cache 和 React/Vite 都就绪，再打开页面。")}</p>
        <p>当前 GET 是否做实时探针：{String(p0LocalConnectionReceipt.current_runtime_probe_executed_by_get_cache ?? false)}；实时联通是否已由本页验证：{String(p0LocalConnectionReceipt.current_runtime_live_connection_verified ?? false)}</p>
        <p>只读边界：本卡只读取 GET /health 与 GET /api/desktop/preflight-cache；不会启动 FastAPI/Vite、不会创建 task、不会调用 Tushare/DeepSeek/GitHub 或交易路径。</p>
        <div aria-label="health ordinary frontend backend connection rows">
          <h3>四段联通状态</h3>
          <p className="risk-note">这张表来自本地 preflight packet，只解释启动器的四段检查；不会从页面补跑探针或启动服务。</p>
          <DataLineageTable rows={p0OrdinaryConnectionRows} />
        </div>
        <div aria-label="health p0 startup failure diagnostics">
          <h3>启动失败定位</h3>
          <p className="risk-note">如果一键入口没有打开页面，按失败段看对应日志和端口；健康页只读展示，不补跑启动器、不创建 task。</p>
          <DataLineageTable rows={p0FailureDiagnosticRows} />
        </div>
        <div aria-label="health p0 post startup readback checklist">
          <h3>启动后复核清单</h3>
          <p className="risk-note">这张清单来自 desktop preflight packet；系统健康页只回读本地 GET 结果，不补跑启动器、不创建 task。</p>
          <DataLineageTable rows={p0PostStartupReadbackRows} />
        </div>
        <div aria-label="health p0 to p1 ordinary handoff">
          <h3>联通后搜票路径</h3>
          <p className="risk-note">健康页只告诉普通用户下一步去哪；真正的 Tushare-first 工作仍要点首页或下一票雷达的确认按钮。</p>
          <DataLineageTable rows={p0ToP1OrdinaryHandoffRows} />
        </div>
        <div aria-label="health p0 startup recovery steps">
          <h3>一键启动恢复步骤</h3>
          <p className="risk-note">这张表来自 desktop preflight 的 p0_recovery_steps；健康页只读展示恢复动作，不补跑启动器、不创建 task。</p>
          <DataLineageTable rows={p0RecoverySteps} />
        </div>
        <details className="developer-audit-details">
          <summary>P0 联通明细</summary>
          <DataLineageTable rows={oneClickConnectionRows} />
        </details>
      </PacketCard>

      <MetricGrid
        items={[
          { label: "FastAPI", value: health.status as string | undefined, tone: health.status === "ok" ? "good" : "warn" },
          { label: "P0 front/back", value: p0ConnectionReady ? "ready" : "check", tone: p0ConnectionReady ? "good" : "warn" },
          { label: "one-click launcher", value: desktopLauncherContract.launcher_executable === true ? "ready" : "check", tone: desktopLauncherContract.launcher_executable === true ? "good" : "warn" },
          { label: "startup external calls", value: health.external_calls_on_startup === true ? "存在" : "无", tone: health.external_calls_on_startup === true ? "bad" : "good" },
          { label: "真实交易", value: health.real_trading_enabled === true ? "启用" : "禁用", tone: health.real_trading_enabled === true ? "bad" : "good" }
        ]}
      />

      <details className="developer-audit-details" aria-label="health advanced status readback">
        <summary>健康工程明细</summary>
        <p className="risk-note">下面是工程审计和原始回放：只读展示 GET /health、GET /api/desktop/preflight-cache 与 migration baseline；不会启动服务、创建 task、调用 provider/model 或展示 token/key。</p>

      <MetricGrid
        items={[
          { label: "FastAPI", value: health.status as string | undefined, tone: health.status === "ok" ? "good" : "warn" },
          { label: "P0 front/back", value: p0ConnectionReady ? "ready" : "check", tone: p0ConnectionReady ? "good" : "warn" },
          { label: "P0 receipt", value: p0LocalConnectionReceipt.status as string | undefined, tone: p0LocalConnectionReceipt.connection_contract_ready === true ? "good" : "warn" },
          { label: "one-click launcher", value: desktopLauncherContract.launcher_executable === true ? "ready" : "check", tone: desktopLauncherContract.launcher_executable === true ? "good" : "warn" },
          { label: "startup external calls", value: health.external_calls_on_startup === true ? "存在" : "无", tone: health.external_calls_on_startup === true ? "bad" : "good" },
          { label: "Tushare", value: health.tushare_called === true ? "已调用" : "未调用", tone: health.tushare_called === true ? "bad" : "good" },
          { label: "DeepSeek", value: health.deepseek_called === true ? "已调用" : "未调用", tone: health.deepseek_called === true ? "bad" : "good" },
          { label: "GitHub", value: health.github_called === true ? "已调用" : "未调用", tone: health.github_called === true ? "bad" : "good" },
          { label: "真实交易", value: health.real_trading_enabled === true ? "启用" : "禁用", tone: health.real_trading_enabled === true ? "bad" : "good" },
          { label: "Streamlit", value: String(health.legacy_streamlit ?? "legacy/admin/debug") },
          { label: "迁移基线", value: String(migration.status ?? "loading") },
          { label: "cache only", value: migrationPolicy?.cache_only, tone: migrationPolicy?.cache_only === false ? "bad" : "good" },
          { label: "health envelope ledger", value: healthEnvelopeLedger.length },
          { label: "desktop preflight ledger", value: desktopPreflightEnvelopeLedger.length },
          { label: "health warnings", value: healthWarnings.length },
          { label: "desktop preflight warnings", value: desktopPreflightWarnings.length }
        ]}
      />

      <div className="grid">
        <PacketCard title="启动安全边界" subtitle="GET /health 只读；不触发 Tushare、DeepSeek 或 GitHub" status="read_only">
          <p>Command Center 3.0 启动健康检查只展示服务状态，不创建任务，不读取 token/key，不执行真实交易。</p>
          <p>所有重计算和外部请求仍必须通过按钮门控 POST task，并由 call_ledger 审计。</p>
        </PacketCard>

        <PacketCard title="DeepSeek 模型策略" subtitle="可配置模型名；不在调用点硬编码；不展示密钥" status="config">
          <DataLineageTable rows={modelStrategyRows} />
          <p>contains_secret: {String(modelStrategy?.contains_secret ?? false)}</p>
          <p>source: {String(modelStrategy?.source ?? "config")}</p>
        </PacketCard>
      </div>

      <PacketCard title="迁移基线" subtitle="用户给定长期参考进度；只读展示，不重新估算" status={String(migration.status ?? "baseline")}>
        <DataLineageTable rows={progress} />
      </PacketCard>

      <PacketCard title="GET health envelope call_ledger" subtitle="GET /health 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={healthEnvelopeLedger} />
      </PacketCard>

      <PacketCard title="GET health envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={healthWarnings.map((warning, index) => ({ index: index + 1, warning }))} />
      </PacketCard>

      <PacketCard title="原始健康 payload" subtitle="调试用 JSON；不含 token/key" status="safe">
        <JsonDetails title="health raw" data={health} />
        <JsonDetails title="migration raw" data={migration} />
      </PacketCard>
      </details>
    </>
  );
}
