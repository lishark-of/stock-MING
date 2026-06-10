import type { ReactNode } from "react";

export type RouteKey =
  | "home"
  | "health"
  | "evidence"
  | "next"
  | "factor"
  | "chokepoint"
  | "serenity"
  | "packets"
  | "migration"
  | "storage"
  | "tasks"
  | "quant"
  | "tradeReview"
  | "legacy";

const ROUTES: Array<{ key: RouteKey; label: string }> = [
  { key: "home", label: "Command Center" },
  { key: "health", label: "健康" },
  { key: "evidence", label: "证据雷达" },
  { key: "next", label: "次日图谱" },
  { key: "factor", label: "多因子图谱" },
  { key: "chokepoint", label: "瓶颈扫描" },
  { key: "serenity", label: "Serenity" },
  { key: "packets", label: "Packet" },
  { key: "migration", label: "迁移状态" },
  { key: "storage", label: "存储层" },
  { key: "tasks", label: "任务目录" },
  { key: "quant", label: "量化回测" },
  { key: "tradeReview", label: "交易复盘" },
  { key: "legacy", label: "Legacy" }
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
          {ROUTES.map((route) => (
            <button
              key={route.key}
              className={active === route.key ? "nav-active" : ""}
              onClick={() => onNavigate(route.key)}
            >
              {route.label}
            </button>
          ))}
        </nav>
        <p className="sidebar-note">React / FastAPI / Tauri skeleton. Streamlit 保留为 legacy/admin/debug。</p>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}
