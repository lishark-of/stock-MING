import { useEffect, useState } from "react";
import Layout, { type RouteKey } from "./components/Layout";
import AShareEvidenceRadar from "./routes/AShareEvidenceRadar";
import CandidateRadar from "./routes/CandidateRadar";
import ChokepointScan from "./routes/ChokepointScan";
import CallLedgerAudit from "./routes/CallLedgerAudit";
import CommandCenterHome from "./routes/CommandCenterHome";
import DataCapabilityConsole from "./routes/DataCapabilityConsole";
import DataHealthTimeline from "./routes/DataHealthTimeline";
import DesktopShellPreflight from "./routes/DesktopShellPreflight";
import DisciplineLoop from "./routes/DisciplineLoop";
import FactorQuantHub from "./routes/FactorQuantHub";
import HealthStatus from "./routes/HealthStatus";
import LegacyTools from "./routes/LegacyTools";
import MarketContext from "./routes/MarketContext";
import MigrationStatus from "./routes/MigrationStatus";
import NextSessionMap from "./routes/NextSessionMap";
import PacketRegistry from "./routes/PacketRegistry";
import PositionContext from "./routes/PositionContext";
import QuantBacktestLab from "./routes/QuantBacktestLab";
import RecoveryCenter from "./routes/RecoveryCenter";
import RiskGuardrails from "./routes/RiskGuardrails";
import SerenityMethodRadar from "./routes/SerenityMethodRadar";
import StorageOverview from "./routes/StorageOverview";
import StrategyTrace from "./routes/StrategyTrace";
import TaskCatalog from "./routes/TaskCatalog";
import TradeReviewLab from "./routes/TradeReviewLab";
import WorkerRuntime from "./routes/WorkerRuntime";

const ROUTE_STORAGE_KEY = "stock_ming_command_center_3_route";
const ROUTE_KEYS: RouteKey[] = [
  "home",
  "health",
  "audit",
  "market",
  "discipline",
  "evidence",
  "dataCapability",
  "dataHealth",
  "desktop",
  "recovery",
  "next",
  "position",
  "candidates",
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

function normalizeRouteKey(value: string | null): RouteKey | null {
  const cleaned = String(value ?? "")
    .trim()
    .replace(/^#\/?/, "");
  return ROUTE_KEYS.includes(cleaned as RouteKey) ? (cleaned as RouteKey) : null;
}

function routeFromHash(): RouteKey | null {
  if (typeof window === "undefined") return null;
  return normalizeRouteKey(window.location.hash);
}

function routeFromStorage(): RouteKey | null {
  if (typeof window === "undefined") return null;
  try {
    return normalizeRouteKey(window.localStorage.getItem(ROUTE_STORAGE_KEY));
  } catch {
    return null;
  }
}

function readInitialRoute(): RouteKey {
  return routeFromHash() ?? routeFromStorage() ?? "home";
}

function persistRoute(route: RouteKey) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(ROUTE_STORAGE_KEY, route);
  } catch {
    // Tauri/WebView privacy settings may disable localStorage; hash routing remains enough.
  }
  const nextHash = `#${route}`;
  if (window.location.hash !== nextHash) {
    window.history.replaceState(null, "", nextHash);
  }
}

export default function App() {
  const [route, setRoute] = useState<RouteKey>(() => readInitialRoute());

  useEffect(() => {
    persistRoute(route);
  }, [route]);

  useEffect(() => {
    const onHashChange = () => {
      const nextRoute = routeFromHash();
      if (nextRoute) setRoute(nextRoute);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const navigateRoute = (nextRoute: RouteKey) => setRoute(nextRoute);

  return (
    <Layout active={route} onNavigate={navigateRoute}>
      {route === "home" ? <CommandCenterHome /> : null}
      {route === "health" ? <HealthStatus /> : null}
      {route === "audit" ? <CallLedgerAudit /> : null}
      {route === "market" ? <MarketContext /> : null}
      {route === "discipline" ? <DisciplineLoop /> : null}
      {route === "evidence" ? <AShareEvidenceRadar /> : null}
      {route === "dataCapability" ? <DataCapabilityConsole /> : null}
      {route === "dataHealth" ? <DataHealthTimeline /> : null}
      {route === "desktop" ? <DesktopShellPreflight /> : null}
      {route === "recovery" ? <RecoveryCenter /> : null}
      {route === "next" ? <NextSessionMap /> : null}
      {route === "position" ? <PositionContext /> : null}
      {route === "candidates" ? <CandidateRadar /> : null}
      {route === "risk" ? <RiskGuardrails /> : null}
      {route === "factor" ? <FactorQuantHub /> : null}
      {route === "chokepoint" ? <ChokepointScan /> : null}
      {route === "serenity" ? <SerenityMethodRadar /> : null}
      {route === "packets" ? <PacketRegistry /> : null}
      {route === "migration" ? <MigrationStatus /> : null}
      {route === "storage" ? <StorageOverview /> : null}
      {route === "tasks" ? <TaskCatalog /> : null}
      {route === "worker" ? <WorkerRuntime /> : null}
      {route === "strategy" ? <StrategyTrace /> : null}
      {route === "quant" ? <QuantBacktestLab /> : null}
      {route === "tradeReview" ? <TradeReviewLab /> : null}
      {route === "legacy" ? <LegacyTools /> : null}
    </Layout>
  );
}
