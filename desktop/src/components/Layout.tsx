import type { ReactNode } from "react";

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

const ROUTE_GROUPS: Array<{ title: string; routes: Array<{ key: RouteKey; label: string }> }> = [
  {
    title: "普通入口",
    routes: [
      { key: "home", label: "今日作战台" },
      { key: "factor", label: "股票量化推演" },
      { key: "candidates", label: "下一票雷达" }
    ]
  },
  {
    title: "研究辅助",
    routes: [
      { key: "market", label: "市场环境" },
      { key: "position", label: "持仓画像" },
      { key: "next", label: "次日图谱" },
      { key: "risk", label: "风险护栏" },
      { key: "strategy", label: "策略 Trace" },
      { key: "chokepoint", label: "瓶颈扫描" },
      { key: "serenity", label: "Serenity" },
      { key: "tradeReview", label: "交易复盘" }
    ]
  },
  {
    title: "数据与治理",
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
  children
}: {
  active: RouteKey;
  onNavigate: (route: RouteKey) => void;
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">stock-MING 3.0</div>
        <nav>
          {ROUTE_GROUPS.map((group) => (
            <section className="nav-group" key={group.title}>
              <p className="nav-group-title">{group.title}</p>
              {group.routes.map((route) => (
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
            </section>
          ))}
        </nav>
        <p className="sidebar-note">三入口先行：今日作战台、股票量化推演、下一票雷达。研究-only，不下单；旧 Streamlit 仅作 legacy/admin/debug fallback。</p>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}
