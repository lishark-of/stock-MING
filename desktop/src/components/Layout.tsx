import { useEffect, useRef, useState, type ReactNode } from "react";
import { getHealth } from "../api/client";

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
  | "tradeReview"
  | "legacy";

const ORDINARY_NAVIGATION_BOUNDARY =
  "普通用户先用五个入口完成本地投研；研究辅助、数据治理、系统迁移默认收起，只作补充上下文、排查、设置或回退。";
const LOCAL_FASTAPI_HEALTH_POLL_MS = 3000;
type LocalFastapiStatus = "checking" | "online" | "offline";

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
      { key: "marginEtf", label: "ETF / 融资" }
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

  const routeButtons = (routes: Array<{ key: RouteKey; label: string }>) => (
    <>
      {routes.map((route) => (
        <button
          key={route.key}
          aria-current={active === route.key ? "page" : undefined}
          className={active === route.key ? "nav-active" : ""}
          data-route-active={active === route.key ? "true" : "false"}
          onClick={() => onNavigate(route.key)}
        >
          <span className="nav-label">{route.label}</span>
        </button>
      ))}
    </>
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">stock-MING 3.0</div>
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
        <nav>
          {ROUTE_GROUPS.map((group) => (
            group.primary ? (
              <section className="nav-group" data-nav-priority="ordinary" aria-label="ordinary user entrances" key={group.title}>
                <p className="nav-group-title">{group.title}</p>
                <p className="nav-group-hint">{group.hint}</p>
                {routeButtons(group.routes)}
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
        </nav>
        <p className="sidebar-note">普通投研主线：今日作战台 → 下一票雷达 → 股票量化推演 → 次日图谱；ETF / 融资风险随时可查。只做研究辅助，不下单；旧工作台仅作排查回退入口。</p>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}
