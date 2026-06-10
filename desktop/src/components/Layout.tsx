import type { ReactNode } from "react";

export type RouteKey = "home" | "next" | "factor" | "chokepoint" | "serenity" | "migration" | "legacy";

const ROUTES: Array<{ key: RouteKey; label: string }> = [
  { key: "home", label: "Command Center" },
  { key: "next", label: "次日图谱" },
  { key: "factor", label: "多因子图谱" },
  { key: "chokepoint", label: "瓶颈扫描" },
  { key: "serenity", label: "Serenity" },
  { key: "migration", label: "迁移状态" },
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
