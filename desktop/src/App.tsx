import { lazy, Suspense, useCallback, useEffect, useState, type ComponentType, type LazyExoticComponent } from "react";
import Layout, { type RouteKey } from "./components/Layout";

const AShareEvidenceRadar = lazy(() => import("./routes/AShareEvidenceRadar"));
const CandidateRadar = lazy(() => import("./routes/CandidateRadar"));
const ChokepointScan = lazy(() => import("./routes/ChokepointScan"));
const CallLedgerAudit = lazy(() => import("./routes/CallLedgerAudit"));
const CommandCenterHome = lazy(() => import("./routes/CommandCenterHome"));
const DataCapabilityConsole = lazy(() => import("./routes/DataCapabilityConsole"));
const DataHealthTimeline = lazy(() => import("./routes/DataHealthTimeline"));
const DesktopShellPreflight = lazy(() => import("./routes/DesktopShellPreflight"));
const DisciplineLoop = lazy(() => import("./routes/DisciplineLoop"));
const FactorQuantHub = lazy(() => import("./routes/FactorQuantHub"));
const HealthStatus = lazy(() => import("./routes/HealthStatus"));
const LegacyTools = lazy(() => import("./routes/LegacyTools"));
const MarginEtf = lazy(() => import("./routes/MarginEtf"));
const MarketContext = lazy(() => import("./routes/MarketContext"));
const MigrationStatus = lazy(() => import("./routes/MigrationStatus"));
const ModelStrategy = lazy(() => import("./routes/ModelStrategy"));
const NextSessionMap = lazy(() => import("./routes/NextSessionMap"));
const PacketRegistry = lazy(() => import("./routes/PacketRegistry"));
const PositionContext = lazy(() => import("./routes/PositionContext"));
const QuantBacktestLab = lazy(() => import("./routes/QuantBacktestLab"));
const RecoveryCenter = lazy(() => import("./routes/RecoveryCenter"));
const RiskGuardrails = lazy(() => import("./routes/RiskGuardrails"));
const SerenityMethodRadar = lazy(() => import("./routes/SerenityMethodRadar"));
const SettingsConfigHealth = lazy(() => import("./routes/SettingsConfigHealth"));
const StorageOverview = lazy(() => import("./routes/StorageOverview"));
const StrategyTrace = lazy(() => import("./routes/StrategyTrace"));
const TaskCatalog = lazy(() => import("./routes/TaskCatalog"));
const TradeReviewLab = lazy(() => import("./routes/TradeReviewLab"));
const WorkerRuntime = lazy(() => import("./routes/WorkerRuntime"));

const ROUTE_STORAGE_KEY = "stock_ming_command_center_3_route";
const ROUTE_ANCHOR_SCROLL_RETRY_DELAYS_MS = [0, 80, 240, 600, 1200, 2000];
const ROUTE_KEYS: RouteKey[] = [
  "home",
  "health",
  "settings",
  "audit",
  "market",
  "models",
  "discipline",
  "evidence",
  "dataCapability",
  "dataHealth",
  "desktop",
  "recovery",
  "next",
  "position",
  "candidates",
  "marginEtf",
  "risk",
  "factor",
  "chokepoint",
  "serenity",
  "packets",
  "migration",
  "storage",
  "tasks",
  "worker",
  "strategy",
  "quant",
  "tradeReview",
  "legacy"
];

const ROUTE_COMPONENTS = {
  home: CommandCenterHome,
  health: HealthStatus,
  settings: SettingsConfigHealth,
  audit: CallLedgerAudit,
  market: MarketContext,
  models: ModelStrategy,
  discipline: DisciplineLoop,
  evidence: AShareEvidenceRadar,
  dataCapability: DataCapabilityConsole,
  dataHealth: DataHealthTimeline,
  desktop: DesktopShellPreflight,
  recovery: RecoveryCenter,
  next: NextSessionMap,
  position: PositionContext,
  candidates: CandidateRadar,
  marginEtf: MarginEtf,
  risk: RiskGuardrails,
  factor: FactorQuantHub,
  chokepoint: ChokepointScan,
  serenity: SerenityMethodRadar,
  packets: PacketRegistry,
  migration: MigrationStatus,
  storage: StorageOverview,
  tasks: TaskCatalog,
  worker: WorkerRuntime,
  strategy: StrategyTrace,
  quant: QuantBacktestLab,
  tradeReview: TradeReviewLab,
  legacy: LegacyTools
} satisfies Record<RouteKey, LazyExoticComponent<ComponentType>>;

function normalizeRouteKey(value: string | null): RouteKey | null {
  const cleaned = String(value ?? "")
    .trim()
    .replace(/^#\/?/, "")
    .split(/[/?]/)[0];
  return ROUTE_KEYS.includes(cleaned as RouteKey) ? (cleaned as RouteKey) : null;
}

function routeFromHash(): RouteKey | null {
  if (typeof window === "undefined") return null;
  return normalizeRouteKey(window.location.hash);
}

function routeAnchorFromHash(): string {
  if (typeof window === "undefined") return "";
  const cleaned = window.location.hash.trim().replace(/^#\/?/, "");
  const parts = cleaned.split("/");
  return parts.length > 1 ? parts.slice(1).join("/").split("?")[0] : "";
}

function routeFromStorage(): RouteKey | null {
  if (typeof window === "undefined") return null;
  try {
    return normalizeRouteKey(window.localStorage.getItem(ROUTE_STORAGE_KEY));
  } catch {
    return null;
  }
}

function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && window.location.protocol === "tauri:";
}

function readInitialRoute(): RouteKey {
  const explicitRoute = routeFromHash();
  if (explicitRoute) return explicitRoute;
  if (isTauriRuntime()) return "home";
  return routeFromStorage() ?? "home";
}

function persistRoute(route: RouteKey) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(ROUTE_STORAGE_KEY, route);
  } catch {
    // Tauri/WebView privacy settings may disable localStorage; hash routing remains enough.
  }
  const nextHash = `#${route}`;
  if (normalizeRouteKey(window.location.hash) !== route) {
    window.history.replaceState(null, "", nextHash);
  }
}

export default function App() {
  const [route, setRoute] = useState<RouteKey>(() => readInitialRoute());
  const [localFastapiRefreshNonce, setLocalFastapiRefreshNonce] = useState(0);
  const [hashScrollVersion, setHashScrollVersion] = useState(0);
  const ActiveRoute = ROUTE_COMPONENTS[route];

  useEffect(() => {
    persistRoute(route);
  }, [route]);

  useEffect(() => {
    const anchor = routeAnchorFromHash();
    if (!anchor) return;
    let cancelled = false;
    let observer: MutationObserver | null = null;
    const scrollToAnchor = () => {
      if (cancelled) return false;
      const target = document.getElementById(anchor);
      if (!target) return false;
      target.scrollIntoView({ block: "start" });
      return true;
    };
    observer = new MutationObserver(scrollToAnchor);
    observer.observe(document.body, { childList: true, subtree: true });
    queueMicrotask(scrollToAnchor);
    const retryTimers = ROUTE_ANCHOR_SCROLL_RETRY_DELAYS_MS.map((delayMs) => window.setTimeout(scrollToAnchor, delayMs));
    const observerTimer = window.setTimeout(() => observer?.disconnect(), Math.max(...ROUTE_ANCHOR_SCROLL_RETRY_DELAYS_MS) + 200);
    return () => {
      cancelled = true;
      observer?.disconnect();
      retryTimers.forEach((timer) => window.clearTimeout(timer));
      window.clearTimeout(observerTimer);
    };
  }, [route, localFastapiRefreshNonce, hashScrollVersion]);

  useEffect(() => {
    const onHashChange = () => {
      const nextRoute = routeFromHash();
      if (nextRoute) setRoute(nextRoute);
      setHashScrollVersion((value) => value + 1);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const handleLocalFastapiConnected = useCallback(() => {
    setLocalFastapiRefreshNonce((value) => value + 1);
  }, []);

  const navigateRoute = (nextRoute: RouteKey) => setRoute(nextRoute);

  return (
    <Layout active={route} onNavigate={navigateRoute} onLocalFastapiConnected={handleLocalFastapiConnected}>
      <Suspense fallback={<div className="panel-loading">正在加载模块...</div>}>
        <div
          className="route-stage"
          key={route}
          data-local-fastapi-refresh-nonce={localFastapiRefreshNonce}
          data-local-fastapi-refresh-boundary="local_health_only_no_route_remount"
        >
          <ActiveRoute key={route} />
        </div>
      </Suspense>
    </Layout>
  );
}
