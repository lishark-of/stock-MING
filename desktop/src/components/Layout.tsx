import { useEffect, useRef, useState, type ReactNode } from "react";
import { getHealth, getTasks, type TaskRecord, type TaskStatusIndex } from "../api/client";

export type RouteKey =
  | "home"
  | "health"
  | "settings"
  | "audit"
  | "market"
  | "models"
  | "discipline"
  | "evidence"
  | "dataCapability"
  | "dataHealth"
  | "desktop"
  | "recovery"
  | "next"
  | "position"
  | "candidates"
  | "marginEtf"
  | "risk"
  | "factor"
  | "chokepoint"
  | "serenity"
  | "packets"
  | "migration"
  | "storage"
  | "tasks"
  | "worker"
  | "strategy"
  | "quant"
  | "qmt-replay"
  | "tradeReview"
  | "legacy";

const ORDINARY_NAVIGATION_BOUNDARY =
  "普通用户先用六个入口完成本地投研与安全回放；研究辅助、数据治理、系统迁移默认收起，只作补充上下文、排查、设置或回退。";
const LOCAL_FASTAPI_HEALTH_POLL_MS = 3000;
type LocalFastapiStatus = "checking" | "online" | "offline";
type ResearchActivityStatus = TaskRecord["status"] | "idle" | "offline" | "checking";

const MOBILE_PRIMARY_JUMPS: Partial<Record<RouteKey, { href: string; label: string }>> = {
  home: { href: "#home/home-p1-symbol-confirm", label: "跳到股票确认" },
  candidates: { href: "#candidates/candidate-radar-search-quant-projection", label: "跳到雷达确认" },
  factor: { href: "#factor/factor-score", label: "跳到量化结果" },
  next: { href: "#next/next-session-chart", label: "跳到次日图谱" },
  marginEtf: { href: "#marginEtf/margin-etf-cash-line", label: "跳到 ETF/融资风险" },
  "qmt-replay": { href: "#qmt-replay/qmt-replay-operator", label: "跳到本地回放" }
};

const ROUTE_GROUPS: Array<{ title: string; hint: string; primary?: boolean; routes: Array<{ key: RouteKey; label: string }> }> = [
  {
    title: "普通入口",
    hint: "先从这里开始；每页先显示下一步、来源、缺口、边界和最近缓存。",
    primary: true,
    routes: [
      { key: "home", label: "今日作战台" },
      { key: "candidates", label: "下一票雷达" },
      { key: "factor", label: "股票量化推演" },
      { key: "next", label: "次日图谱" },
      { key: "marginEtf", label: "ETF / 融资" },
      { key: "qmt-replay", label: "QMT 回放" }
    ]
  },
  {
    title: "研究辅助",
    hint: "补充上下文，只读查看研究状态，不替代普通投研主流程。",
    routes: [
      { key: "market", label: "市场环境" },
      { key: "position", label: "持仓画像" },
      { key: "risk", label: "风险护栏" },
      { key: "strategy", label: "策略 Trace" },
      { key: "chokepoint", label: "瓶颈扫描" },
      { key: "serenity", label: "Serenity" },
      { key: "tradeReview", label: "交易复盘" }
    ]
  },
  {
    title: "数据与治理",
    hint: "数据来源、结果记录和排查表在这里，不压过普通用户页面。",
    routes: [
      { key: "audit", label: "调用审计" },
      { key: "evidence", label: "证据雷达" },
      { key: "dataCapability", label: "数据能力" },
      { key: "dataHealth", label: "数据健康" },
      { key: "storage", label: "存储层" },
      { key: "packets", label: "Packet" }
    ]
  },
  {
    title: "系统迁移",
    hint: "配置、任务、迁移和旧工作台只作设置、排查或回退入口。",
    routes: [
      { key: "health", label: "健康" },
      { key: "settings", label: "配置健康" },
      { key: "models", label: "模型策略" },
      { key: "discipline", label: "交易纪律" },
      { key: "desktop", label: "桌面壳" },
      { key: "migration", label: "迁移状态" },
      { key: "tasks", label: "Task Monitor" },
      { key: "worker", label: "Worker" },
      { key: "quant", label: "量化回测" },
      { key: "recovery", label: "恢复中心" },
      { key: "legacy", label: "Legacy" }
    ]
  }
];

const PRIMARY_ROUTE_INDEX: Partial<Record<RouteKey, string>> = {
  home: "01",
  candidates: "02",
  factor: "03",
  next: "04",
  marginEtf: "05",
  "qmt-replay": "06"
};

function normalizeResearchProgress(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return 0;
  const percentage = value >= 0 && value <= 1 ? value * 100 : value;
  return Math.max(0, Math.min(100, Math.round(percentage)));
}

export default function Layout({
  active,
  onNavigate,
  onLocalFastapiConnected,
  children
}: {
  active: RouteKey;
  onNavigate: (route: RouteKey) => void;
  onLocalFastapiConnected?: () => void;
  children: ReactNode;
}) {
  const [localFastapiStatus, setLocalFastapiStatus] = useState<LocalFastapiStatus>("checking");
  const [taskIndex, setTaskIndex] = useState<TaskStatusIndex | null>(null);
  const lastLocalFastapiStatusRef = useRef<LocalFastapiStatus>("checking");

  useEffect(() => {
    let cancelled = false;

    const publishLocalFastapiStatus = (nextStatus: LocalFastapiStatus) => {
      const previousStatus = lastLocalFastapiStatusRef.current;
      lastLocalFastapiStatusRef.current = nextStatus;
      setLocalFastapiStatus(nextStatus);
      if (nextStatus === "online" && previousStatus !== "online") {
        onLocalFastapiConnected?.();
      }
    };

    const checkLocalFastapi = () => {
      void getHealth()
        .then((res) => {
          if (cancelled) return;
          const ready = res.ok === true && String(res.data?.status ?? "") === "ok";
          publishLocalFastapiStatus(ready ? "online" : "offline");
          if (ready) {
            void getTasks()
              .then((taskRes) => {
                if (!cancelled && taskRes.ok) setTaskIndex(taskRes.data);
              })
              .catch(() => undefined);
          }
        })
        .catch(() => {
          if (!cancelled) publishLocalFastapiStatus("offline");
        });
    };

    checkLocalFastapi();
    const timer = window.setInterval(checkLocalFastapi, LOCAL_FASTAPI_HEALTH_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [onLocalFastapiConnected]);

  const localFastapiLabel =
    localFastapiStatus === "online"
      ? "本地已接上"
      : localFastapiStatus === "offline"
        ? "本地未接上"
        : "正在确认本机连接";
  const localFastapiDetail =
    localFastapiStatus === "online"
      ? "FastAPI /health ready，只读本机状态"
      : localFastapiStatus === "offline"
        ? "去一键启动预检恢复"
        : "只读检查 /health";
  const mobilePrimaryJump = MOBILE_PRIMARY_JUMPS[active];
  const latestConfirmedSymbol = String(taskIndex?.latest_confirmed_symbol ?? "").trim();
  const latestConfirmedTaskId = String(taskIndex?.latest_confirmed_task_id ?? "").trim();
  const latestConfirmedTask = taskIndex?.tasks.find((task) => task.task_id === latestConfirmedTaskId) ??
    taskIndex?.tasks.find((task) => {
      const payload = task.payload_safe ?? {};
      return latestConfirmedSymbol && [payload.symbol, payload.ts_code, payload.stock_code, payload.ticker]
        .some((value) => String(value ?? "").trim() === latestConfirmedSymbol);
    }) ?? null;
  const researchActivityStatus: ResearchActivityStatus = localFastapiStatus === "checking"
    ? "checking"
    : localFastapiStatus === "offline"
      ? "offline"
      : latestConfirmedTask?.status ??
        (taskIndex?.latest_confirmed_task_status as TaskRecord["status"] | undefined) ??
        "idle";
  const researchActivityLabel = researchActivityStatus === "checking"
    ? "正在读取本地研究状态"
    : researchActivityStatus === "offline"
      ? "等待本地连接"
      : researchActivityStatus === "pending" || researchActivityStatus === "running"
        ? `${latestConfirmedSymbol || "当前标的"} · 研究处理中${latestConfirmedTask ? ` ${normalizeResearchProgress(latestConfirmedTask.progress)}%` : ""}`
        : researchActivityStatus === "success"
          ? `${latestConfirmedSymbol || "当前标的"} · 最近结果已完成`
          : researchActivityStatus === "failed" || researchActivityStatus === "cancelled"
            ? `${latestConfirmedSymbol || "当前标的"} · 最近研究待处理`
            : "等待确认股票";
  const researchActivityAction = researchActivityStatus === "success"
    ? "#factor/factor-score"
    : researchActivityStatus === "offline" || researchActivityStatus === "checking"
      ? "#desktop"
      : researchActivityStatus === "idle"
        ? "#candidates/candidate-radar-search-quant-projection"
        : "#tasks";
  const researchActivityActionLabel = researchActivityStatus === "success"
    ? "看结果"
    : researchActivityStatus === "idle"
      ? "去确认"
      : researchActivityStatus === "offline" || researchActivityStatus === "checking"
        ? "去预检"
        : "看进度";

  const activeRouteGroup = ROUTE_GROUPS.find((group) => group.routes.some((route) => route.key === active));
  const activeRouteLabel = activeRouteGroup?.routes.find((route) => route.key === active)?.label ?? "研究工作台";
  const routeButtons = (routes: Array<{ key: RouteKey; label: string }>, primary = false) => (
    <>
      {routes.map((route) => (
        <button
          key={route.key}
          aria-current={active === route.key ? "page" : undefined}
          className={active === route.key ? "nav-active" : ""}
          data-route-active={active === route.key ? "true" : "false"}
          data-route-key={route.key}
          data-nav-tier={primary ? "primary" : "support"}
          onClick={() => onNavigate(route.key)}
        >
          {primary ? <span className="nav-index" aria-hidden="true">{PRIMARY_ROUTE_INDEX[route.key]}</span> : null}
          <span className="nav-label">{route.label}</span>
          {primary ? <span className="nav-arrow" aria-hidden="true">&#8599;</span> : null}
        </button>
      ))}
    </>
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand" aria-label="stock-MING Command Center 3.0">
          <span className="brand-mark" aria-hidden="true">M</span>
          <span className="brand-copy">
            <strong>stock-MING</strong>
            <small>COMMAND CENTER 3.0</small>
          </span>
        </div>
        <div
          className="local-link-status"
          data-local-fastapi-status={localFastapiStatus}
          data-local-fastapi-boundary="local_health_only_no_provider_model_task"
          role="status"
          aria-label="local fastapi connection status"
        >
          <span className="local-link-dot" aria-hidden="true" />
          <span className="local-link-copy">
            <strong>{localFastapiLabel}</strong>
            <small>{localFastapiDetail}</small>
          </span>
          <button
            type="button"
            className="local-link-action"
            onClick={() => onNavigate(localFastapiStatus === "online" ? "health" : "desktop")}
            aria-label={localFastapiStatus === "online" ? "open local health status" : "open one click startup preflight"}
          >
            {localFastapiStatus === "online" ? "健康" : "预检"}
          </button>
        </div>
        <div
          className="research-activity-status"
          data-research-activity-status={researchActivityStatus}
          data-research-activity-boundary="local_task_index_only_no_provider_model_task"
          role="status"
          aria-label="latest local research status"
        >
          <span className="research-activity-dot" aria-hidden="true" />
          <span className="research-activity-copy">
            <strong>最近研究</strong>
            <small>{researchActivityLabel}</small>
          </span>
          <a
            className="research-activity-action"
            aria-label={`${researchActivityActionLabel}；只切换本地页面`}
            href={researchActivityAction}
          >{researchActivityActionLabel}</a>
        </div>
        <nav>
          {ROUTE_GROUPS.map((group) => (
            group.primary ? (
              <section className="nav-group" data-nav-priority="ordinary" aria-label="ordinary user entrances" key={group.title}>
                <p className="nav-group-title">{group.title}</p>
                <p className="nav-group-hint">{group.hint}</p>
                {routeButtons(group.routes, true)}
                <p className="nav-group-hint nav-ordinary-boundary">{ORDINARY_NAVIGATION_BOUNDARY}</p>
              </section>
            ) : (
              <details className="nav-group nav-group-details" data-nav-priority="developer" open={group.routes.some((route) => route.key === active) || undefined} key={group.title}>
                <summary className="nav-group-summary">
                  <span className="nav-group-title">{group.title}</span>
                  <span className="nav-group-hint">{group.hint}</span>
                </summary>
                {routeButtons(group.routes)}
              </details>
            )
          ))}
          <div className="mobile-nav-select-wrap">
            <span id="mobile-secondary-route-select-label">更多页面</span>
            <select
              id="mobile-secondary-route-select"
              aria-labelledby="mobile-secondary-route-select-label"
              value={ROUTE_GROUPS[0].routes.some((route) => route.key === active) ? "" : active}
              onChange={(event) => {
                if (event.target.value) onNavigate(event.target.value as RouteKey);
              }}
            >
              <option value="">研究 / 审计 / 设置</option>
              {ROUTE_GROUPS.filter((group) => !group.primary).map((group) => (
                <optgroup label={group.title} key={group.title}>
                  {group.routes.map((route) => (
                    <option value={route.key} key={route.key}>{route.label}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
        </nav>
        {mobilePrimaryJump ? (
          <a
            className="mobile-primary-jump"
            href={mobilePrimaryJump.href}
            aria-label={`${mobilePrimaryJump.label}；只做本地页面滚动`}
          >{mobilePrimaryJump.label}</a>
        ) : null}
        <p className="sidebar-note">普通投研主线：今日作战台 → 下一票雷达 → 股票量化推演 → 次日图谱 → QMT 本地回放；ETF / 融资风险随时可查。只做研究辅助，不下单；QMT、券商、账户与订单路径保持隔离；旧工作台仅作排查回退入口。</p>
      </aside>
      <main className="content">
        <div className="content-ambient" aria-hidden="true" />
        <header className="workspace-bar" aria-label="current research workspace">
          <span className="workspace-route">
            <small>{activeRouteGroup?.primary ? "PRIMARY RESEARCH FLOW" : activeRouteGroup?.title ?? "LOCAL WORKSPACE"}</small>
            <strong>{activeRouteLabel}</strong>
          </span>
          <span className="workspace-boundary" role="status">
            <span className="workspace-boundary-dot" aria-hidden="true" />
            研究模式 · 无下单路径
          </span>
        </header>
        <div className="content-canvas">{children}</div>
      </main>
    </div>
  );
}
