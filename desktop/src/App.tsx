import { useState } from "react";
import Layout, { type RouteKey } from "./components/Layout";
import AShareEvidenceRadar from "./routes/AShareEvidenceRadar";
import CandidateRadar from "./routes/CandidateRadar";
import ChokepointScan from "./routes/ChokepointScan";
import CommandCenterHome from "./routes/CommandCenterHome";
import DataCapabilityConsole from "./routes/DataCapabilityConsole";
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

export default function App() {
  const [route, setRoute] = useState<RouteKey>("home");
  return (
    <Layout active={route} onNavigate={setRoute}>
      {route === "home" ? <CommandCenterHome /> : null}
      {route === "health" ? <HealthStatus /> : null}
      {route === "market" ? <MarketContext /> : null}
      {route === "discipline" ? <DisciplineLoop /> : null}
      {route === "evidence" ? <AShareEvidenceRadar /> : null}
      {route === "dataCapability" ? <DataCapabilityConsole /> : null}
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
      {route === "strategy" ? <StrategyTrace /> : null}
      {route === "quant" ? <QuantBacktestLab /> : null}
      {route === "tradeReview" ? <TradeReviewLab /> : null}
      {route === "legacy" ? <LegacyTools /> : null}
    </Layout>
  );
}
